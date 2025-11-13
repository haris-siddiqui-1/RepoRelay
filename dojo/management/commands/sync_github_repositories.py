"""
Django management command to sync GitHub repository metadata.

Uses GitHub GraphQL API v4 by default for efficient bulk operations.
Use --use-rest to fall back to REST API if needed.

Usage:
    python manage.py sync_github_repositories [--org ORG] [--incremental] [--archive-dormant]

Examples:
    # Daily incremental sync with GraphQL (recommended)
    python manage.py sync_github_repositories --incremental

    # Sync all repositories from configured organization
    python manage.py sync_github_repositories

    # Sync specific organization
    python manage.py sync_github_repositories --org myorg

    # Use REST API instead of GraphQL
    python manage.py sync_github_repositories --use-rest --incremental

    # Archive dormant repositories
    python manage.py sync_github_repositories --archive-dormant

    # Sync single product by ID
    python manage.py sync_github_repositories --product-id 123

Performance:
    - GraphQL (default): <5 minutes for 50-100 changed repos (incremental)
    - REST (--use-rest): ~10 minutes for same workload
    - See dojo/github_collector/README_GRAPHQL.md for details
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from dojo.github_collector import GitHubRepositoryCollector
from dojo.models import Product

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync repository metadata from GitHub API to DefectDojo Products'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org',
            type=str,
            help='GitHub organization name (overrides DD_GITHUB_ORG setting)'
        )
        parser.add_argument(
            '--token',
            type=str,
            help='GitHub personal access token (overrides DD_GITHUB_TOKEN setting)'
        )
        parser.add_argument(
            '--incremental',
            action='store_true',
            help='Only sync repositories updated since last sync'
        )
        parser.add_argument(
            '--archive-dormant',
            action='store_true',
            help='Mark repositories with no commits in 180+ days as archived'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes'
        )
        parser.add_argument(
            '--product-id',
            type=int,
            help='Sync only a specific product by ID'
        )
        parser.add_argument(
            '--use-rest',
            action='store_true',
            help='Use REST API instead of GraphQL (default: GraphQL)'
        )

    def handle(self, *args, **options):
        """Execute the sync command."""
        org = options.get('org')
        token = options.get('token')
        incremental = options.get('incremental', False)
        archive_dormant = options.get('archive_dormant', False)
        dry_run = options.get('dry_run', False)
        product_id = options.get('product_id')
        use_rest = options.get('use_rest', False)

        # Validate configuration
        github_token = token or getattr(settings, 'DD_GITHUB_TOKEN', '')
        github_org = org or getattr(settings, 'DD_GITHUB_ORG', '')

        if not github_token:
            raise CommandError(
                'GitHub token not configured. Set DD_GITHUB_TOKEN environment variable '
                'or use --token option.'
            )

        if not github_org and not product_id:
            raise CommandError(
                'GitHub organization not configured. Set DD_GITHUB_ORG environment variable '
                'or use --org option, or specify --product-id to sync a specific product.'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Initialize collector
        try:
            use_graphql = not use_rest  # Default to GraphQL unless --use-rest specified
            collector = GitHubRepositoryCollector(
                github_token=github_token,
                github_org=github_org,
                use_graphql=use_graphql
            )

            # Log API choice
            api_type = "REST API" if use_rest else "GraphQL API"
            self.stdout.write(f'Using {api_type} for sync')

        except Exception as e:
            raise CommandError(f'Failed to initialize GitHub collector: {e}')

        # Sync specific product or all repositories
        if product_id:
            self._sync_single_product(collector, product_id, dry_run)
        else:
            self._sync_all_repositories(collector, incremental, archive_dormant, dry_run)

    def _sync_single_product(self, collector, product_id, dry_run):
        """Sync a single product by ID."""
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise CommandError(f'Product with ID {product_id} does not exist')

        if not product.github_url:
            raise CommandError(f'Product "{product.name}" has no github_url set')

        self.stdout.write(f'Syncing product: {product.name} ({product.github_url})')

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'Would sync: {product.name}'))
            return

        try:
            success = collector.sync_product_from_github_url(product)
            if success:
                self.stdout.write(self.style.SUCCESS(f'✓ Successfully synced: {product.name}'))
            else:
                self.stdout.write(self.style.ERROR(f'✗ Failed to sync: {product.name}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error syncing {product.name}: {e}'))
            logger.exception(f'Error syncing product {product_id}')

    def _sync_all_repositories(self, collector, incremental, archive_dormant, dry_run):
        """Sync all repositories from GitHub organization."""
        self.stdout.write(f'Starting repository sync (incremental={incremental})')
        self.stdout.write(f'Organization: {collector.github_org}')

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run - listing repositories only'))
            try:
                org = collector.github_client.get_organization(collector.github_org)
                repos = list(org.get_repos())
                self.stdout.write(f'\nFound {len(repos)} repositories:')
                for repo in repos[:20]:  # Show first 20
                    self.stdout.write(f'  - {repo.full_name}')
                if len(repos) > 20:
                    self.stdout.write(f'  ... and {len(repos) - 20} more')
            except Exception as e:
                raise CommandError(f'Failed to list repositories: {e}')
            return

        # Perform sync
        try:
            stats = collector.sync_all_repositories(incremental=incremental)

            # Display results
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('SYNC COMPLETED'))
            self.stdout.write('=' * 60)
            self.stdout.write(f'Total repositories: {stats["total_repos"]}')
            self.stdout.write(self.style.SUCCESS(f'✓ Created: {stats["created"]}'))
            self.stdout.write(self.style.SUCCESS(f'✓ Updated: {stats["updated"]}'))
            if stats['skipped'] > 0:
                self.stdout.write(self.style.WARNING(f'⊘ Skipped: {stats["skipped"]}'))
            if stats['errors'] > 0:
                self.stdout.write(self.style.ERROR(f'✗ Errors: {stats["errors"]}'))
            self.stdout.write('=' * 60)

            # Archive dormant repositories if requested
            if archive_dormant:
                self._archive_dormant_repositories()

        except Exception as e:
            raise CommandError(f'Sync failed: {e}')

    def _archive_dormant_repositories(self):
        """Mark products with no recent commits as archived."""
        archive_days = getattr(settings, 'DD_AUTO_ARCHIVE_DAYS', 180)

        self.stdout.write(f'\nChecking for dormant repositories (>{archive_days} days since last commit)...')

        dormant = Product.objects.filter(
            days_since_last_commit__gt=archive_days,
            lifecycle__in=[Product.CONSTRUCTION, Product.PRODUCTION]
        )

        count = dormant.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No dormant repositories found'))
            return

        self.stdout.write(self.style.WARNING(f'Found {count} dormant repositories'))

        # Update lifecycle to retirement
        dormant.update(lifecycle=Product.RETIREMENT, business_criticality='none')

        self.stdout.write(self.style.SUCCESS(f'✓ Marked {count} repositories as archived'))
