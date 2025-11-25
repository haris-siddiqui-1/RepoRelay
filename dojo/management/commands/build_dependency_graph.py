"""
Django management command to build internal dependency graph using GitHub SBOM API.

Analyzes Software Bill of Materials (SBOM) from GitHub's dependency graph to:
- Track which repositories depend on which other internal repositories
- Update consumption signal fields (dependent_repo_count, downstream_consumers)
- Apply consumption-based tier overrides (50+ = tier1, 20+ = tier2, 5+ = promote)
- Identify shared libraries (consumed by 5+ repositories)

Usage:
    python manage.py build_dependency_graph [--org ORG] [--dry-run] [--traffic]

Examples:
    # Build dependency graph for all repositories
    python manage.py build_dependency_graph

    # Dry run - show what would be updated
    python manage.py build_dependency_graph --dry-run

    # Also update traffic stats (clone/view counts)
    python manage.py build_dependency_graph --traffic

    # Specify organization
    python manage.py build_dependency_graph --org myorg

Performance:
    - ~1 API call per repository for SBOM (paginated for large SBOMs)
    - ~2 API calls per repository for traffic stats (requires push access)
    - Typical run: 5-15 minutes for 1000 repositories
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from dojo.github_collector import DependencyGraphBuilder

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Build internal dependency graph using GitHub SBOM API'

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
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )
        parser.add_argument(
            '--traffic',
            action='store_true',
            help='Also update traffic stats (clone/view counts, requires push access)'
        )
        parser.add_argument(
            '--repository-id',
            type=int,
            nargs='+',
            help='Process only specific repository IDs'
        )

    def handle(self, *args, **options):
        """Execute the dependency graph build command."""
        org = options.get('org')
        token = options.get('token')
        dry_run = options.get('dry_run', False)
        include_traffic = options.get('traffic', False)
        repository_ids = options.get('repository_id')

        # Validate configuration
        github_token = token or getattr(settings, 'DD_GITHUB_TOKEN', '')
        github_org = org or getattr(settings, 'DD_GITHUB_ORG', '')

        if not github_token:
            raise CommandError(
                'GitHub token not configured. Set DD_GITHUB_TOKEN environment variable '
                'or use --token option.'
            )

        if not github_org:
            raise CommandError(
                'GitHub organization not configured. Set DD_GITHUB_ORG environment variable '
                'or use --org option.'
            )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Initialize builder
        try:
            builder = DependencyGraphBuilder(github_token=github_token)
            self.stdout.write(f'Initialized DependencyGraphBuilder for organization: {github_org}')
        except Exception as e:
            raise CommandError(f'Failed to initialize DependencyGraphBuilder: {e}')

        # Build dependency graph
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('BUILDING DEPENDENCY GRAPH')
        self.stdout.write('=' * 60)
        self.stdout.write(f'Organization: {github_org}')
        self.stdout.write('Progress will be logged every 10 repositories...')

        try:
            stats = builder.build_dependency_graph(
                owner=github_org,
                repository_ids=repository_ids,
                dry_run=dry_run
            )

            # Display results
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('DEPENDENCY GRAPH BUILD COMPLETED'))
            self.stdout.write('=' * 60)
            self.stdout.write(f'Repositories processed: {stats["repos_processed"]}')
            self.stdout.write(self.style.SUCCESS(f'SBOMs fetched: {stats["sbom_fetched"]}'))
            if stats['sbom_failed'] > 0:
                self.stdout.write(self.style.WARNING(f'SBOMs unavailable: {stats["sbom_failed"]}'))
            self.stdout.write(f'Dependencies found: {stats["dependencies_found"]}')
            self.stdout.write(self.style.SUCCESS(f'Internal matches: {stats["internal_matches"]}'))
            self.stdout.write(self.style.SUCCESS(f'Tier overrides applied: {stats["tier_overrides_applied"]}'))
            self.stdout.write(self.style.SUCCESS(f'Shared libraries found: {stats["shared_libraries_found"]}'))
            self.stdout.write('=' * 60)

        except Exception as e:
            raise CommandError(f'Dependency graph build failed: {e}')

        # Update traffic stats if requested
        if include_traffic:
            self._update_traffic_stats(builder, github_org, repository_ids, dry_run)

    def _update_traffic_stats(self, builder, github_org, repository_ids, dry_run):
        """Update traffic statistics (clone/view counts)."""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('UPDATING TRAFFIC STATS')
        self.stdout.write('=' * 60)
        self.stdout.write('Note: Traffic API requires push access to repositories')

        try:
            stats = builder.update_traffic_stats(
                owner=github_org,
                repository_ids=repository_ids,
                dry_run=dry_run
            )

            self.stdout.write('\n' + '-' * 60)
            self.stdout.write(self.style.SUCCESS('TRAFFIC STATS UPDATE COMPLETED'))
            self.stdout.write('-' * 60)
            self.stdout.write(f'Repositories processed: {stats["repos_processed"]}')
            self.stdout.write(self.style.SUCCESS(f'Traffic data fetched: {stats["traffic_fetched"]}'))
            if stats['traffic_failed'] > 0:
                self.stdout.write(self.style.WARNING(
                    f'Traffic unavailable: {stats["traffic_failed"]} '
                    f'(may lack push access)'
                ))
            self.stdout.write('-' * 60)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Traffic stats update failed: {e}'))
            logger.exception('Traffic stats update failed')
