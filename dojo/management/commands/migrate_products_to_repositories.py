"""
Management command for Product → Repository migration.

Phase 4: Product Grouping & Migration
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dojo.models import Repository, Product
from dojo.product.migration_wizard import ProductMigrationWizard


class Command(BaseCommand):
    help = 'Migrate Products to Repository groupings using ML clustering'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview migration without applying changes'
        )

        parser.add_argument(
            '--auto-approve-threshold',
            type=int,
            default=None,
            help='Auto-approve clusters with confidence >= threshold (0-100)'
        )

        parser.add_argument(
            '--auto-approve-all',
            action='store_true',
            help='Auto-approve all suggested groupings (use with caution)'
        )

        parser.add_argument(
            '--product-type',
            type=int,
            default=None,
            help='Only migrate repositories in this Product_Type ID'
        )

        parser.add_argument(
            '--num-clusters',
            type=int,
            default=None,
            help='Target number of clusters (optional, auto-detected if not specified)'
        )

        parser.add_argument(
            '--rollback',
            type=str,
            default=None,
            help='Rollback migration by ID (e.g., mig_20250116_142301)'
        )

    def handle(self, *args, **options):
        # Handle rollback
        if options['rollback']:
            self.handle_rollback(options['rollback'])
            return

        # Initialize wizard
        wizard = ProductMigrationWizard()

        self.stdout.write(self.style.SUCCESS('Product Migration Wizard'))
        self.stdout.write('=' * 60)

        # Run clustering
        self.stdout.write('\nRunning clustering analysis...')

        result = wizard.get_clustering_suggestions(
            product_type_id=options['product_type'],
            suggested_num_clusters=options['num_clusters']
        )

        if not result['success']:
            raise CommandError(f"Clustering failed: {result.get('error')}")

        self.stdout.write(self.style.SUCCESS(f"✓ Clustering complete"))

        # Display summary
        summary = result['summary']
        self.stdout.write('\nClustering Summary:')
        self.stdout.write(f"  Total repositories: {summary['total_repositories']}")
        self.stdout.write(f"  Suggested clusters: {summary['total_clusters']}")
        self.stdout.write('')
        self.stdout.write(f"  High confidence (≥80%): {summary['high_confidence_clusters']} clusters, {summary['high_confidence_repos']} repos")
        self.stdout.write(f"  Medium confidence (50-79%): {summary['medium_confidence_clusters']} clusters, {summary['medium_confidence_repos']} repos")
        self.stdout.write(f"  Low confidence (<50%): {summary['low_confidence_clusters']} clusters, {summary['low_confidence_repos']} repos")

        # Build groupings based on auto-approval settings
        groupings = []
        threshold = options.get('auto_approve_threshold')

        for cluster in result['clusters']:
            # Auto-approve logic
            should_approve = False

            if options['auto_approve_all']:
                should_approve = True
            elif threshold is not None:
                should_approve = cluster['confidence_score'] >= threshold
            else:
                # Interactive mode - ask for each cluster
                should_approve = self.prompt_cluster_approval(cluster)

            if should_approve:
                groupings.append({
                    'product_name': cluster['suggested_product_name'],
                    'repository_ids': [r['id'] for r in cluster['repositories']],
                    'product_type_id': options.get('product_type'),
                    'description': f"Migrated product grouping (confidence: {cluster['confidence_score']}%)"
                })

        if not groupings:
            self.stdout.write(self.style.WARNING('\nNo groupings approved. Exiting.'))
            return

        # Preview migration
        self.stdout.write(f'\nPreviewing migration for {len(groupings)} approved groupings...')

        preview = wizard.preview_migration(groupings)

        if not preview['success']:
            self.stdout.write(self.style.ERROR('\nValidation errors:'))
            for error in preview['validation_errors']:
                self.stdout.write(self.style.ERROR(f"  ✗ {error}"))
            raise CommandError('Migration validation failed')

        if preview['validation_warnings']:
            self.stdout.write(self.style.WARNING('\nWarnings:'))
            for warning in preview['validation_warnings']:
                self.stdout.write(self.style.WARNING(f"  ⚠ {warning}"))

        # Display impact
        impact = preview['impact']
        self.stdout.write('\nMigration Impact:')
        self.stdout.write(f"  New Products to create: {impact['new_products_count']}")
        self.stdout.write(f"  Repositories to migrate: {impact['affected_repositories']}")
        self.stdout.write(f"  Findings affected: {impact['affected_findings']}")
        self.stdout.write(f"  Tests affected: {impact['affected_tests']}")
        self.stdout.write(f"  Engagements affected: {impact['affected_engagements']}")

        # Confirm if not dry-run
        if not options['dry_run']:
            if not options['auto_approve_all']:
                confirm = input('\nProceed with migration? [y/N]: ')
                if confirm.lower() != 'y':
                    self.stdout.write(self.style.WARNING('Migration cancelled.'))
                    return

        # Apply migration
        self.stdout.write('\nApplying migration...')

        migration_result = wizard.apply_migration(
            groupings,
            dry_run=options['dry_run']
        )

        if not migration_result['success']:
            raise CommandError(f"Migration failed: {migration_result.get('error')}")

        # Display results
        if migration_result['dry_run']:
            self.stdout.write(self.style.SUCCESS('\n✓ Dry-run successful - no changes applied'))
            self.stdout.write(f"  Would create: {migration_result['created_products']} products")
            self.stdout.write(f"  Would update: {migration_result['updated_repositories']} repositories")
            self.stdout.write(f"  Would archive: {migration_result['archived_products']} products")
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Migration complete!'))
            self.stdout.write(f"  Created: {len(migration_result['created_products'])} products")
            self.stdout.write(f"  Updated: {len(migration_result['updated_repositories'])} repositories")
            self.stdout.write(f"  Archived: {len(migration_result['archived_products'])} products")

            migration_id = migration_result['migration_id']
            self.stdout.write(f"\nMigration ID: {migration_id}")
            self.stdout.write(f"Rollback command: python manage.py migrate_products_to_repositories --rollback {migration_id}")

    def prompt_cluster_approval(self, cluster):
        """Interactive prompt for cluster approval."""
        self.stdout.write('\n' + '-' * 60)
        self.stdout.write(f"Cluster: {cluster['suggested_product_name']}")
        self.stdout.write(f"Confidence: {cluster['confidence_score']}%")
        self.stdout.write(f"Repositories ({cluster['repository_count']}):")

        for repo in cluster['repositories'][:10]:  # Show first 10
            self.stdout.write(f"  - {repo['name']}")

        if cluster['repository_count'] > 10:
            self.stdout.write(f"  ... and {cluster['repository_count'] - 10} more")

        common = cluster['common_features']
        if common.get('primary_language'):
            self.stdout.write(f"Common language: {common['primary_language']}")
        if common.get('primary_framework'):
            self.stdout.write(f"Common framework: {common['primary_framework']}")

        response = input('\nApprove this grouping? [y/N]: ')
        return response.lower() == 'y'

    def handle_rollback(self, migration_id):
        """Handle migration rollback."""
        self.stdout.write(self.style.WARNING(f'Rolling back migration: {migration_id}'))

        wizard = ProductMigrationWizard()
        result = wizard.rollback_migration(migration_id)

        if not result['success']:
            raise CommandError(f"Rollback failed: {result.get('error')}")

        self.stdout.write(self.style.SUCCESS('\n✓ Rollback complete!'))
        self.stdout.write(f"  Restored: {result['restored_repositories']} repositories")
        self.stdout.write(f"  Deleted: {result['deleted_products']} migrated products")
