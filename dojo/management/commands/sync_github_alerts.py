"""
Django management command to sync GitHub security alerts.

Collects Dependabot, CodeQL, and Secret Scanning alerts from GitHub
and stores them in the GitHubAlert model.

Usage:
    python manage.py sync_github_alerts [options]

Examples:
    # Sync all repositories (skips recently synced)
    python manage.py sync_github_alerts

    # Force sync all repositories regardless of last sync time
    python manage.py sync_github_alerts --force

    # Sync specific repository by ID
    python manage.py sync_github_alerts --repository-id 123

    # Sync with limit for testing
    python manage.py sync_github_alerts --limit 10

    # Dry run to see what would be synced
    python manage.py sync_github_alerts --dry-run

Performance:
    - Dependabot (GraphQL): ~5-10 points per repo
    - CodeQL (REST): ~1-2 calls per repo
    - Secret Scanning (REST): ~1-2 calls per repo
    - Incremental: Only syncs repos not synced in past hour
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from dojo.github_collector.alerts_collector import GitHubAlertsCollector
from dojo.models import Repository

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync GitHub security alerts (Dependabot, CodeQL, Secret Scanning) to DefectDojo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--token',
            type=str,
            help='GitHub personal access token (overrides DD_GITHUB_TOKEN setting)'
        )
        parser.add_argument(
            '--repository-id',
            type=int,
            help='Sync only a specific repository by ID'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if recently synced (ignore minimum sync interval)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Maximum number of repositories to sync (for testing)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes'
        )
        # Note: --verbosity is provided by Django's BaseCommand, don't redefine it

    def handle(self, *args, **options):
        """Execute the sync command."""
        token = options.get('token')
        repository_id = options.get('repository_id')
        force = options.get('force', False)
        limit = options.get('limit')
        dry_run = options.get('dry_run', False)
        verbosity = options.get('verbosity', 1)

        # Configure logging based on verbosity
        if verbosity >= 2:
            logging.getLogger('dojo.github_collector').setLevel(logging.DEBUG)
        elif verbosity == 1:
            logging.getLogger('dojo.github_collector').setLevel(logging.INFO)
        else:
            logging.getLogger('dojo.github_collector').setLevel(logging.WARNING)

        # Validate configuration
        github_token = token or getattr(settings, 'DD_GITHUB_TOKEN', '')

        if not github_token:
            raise CommandError(
                'GitHub token not configured. Set DD_GITHUB_TOKEN environment variable '
                'or use --token option.'
            )

        # Initialize collector
        try:
            collector = GitHubAlertsCollector(github_token)
        except Exception as e:
            raise CommandError(f'Failed to initialize GitHub Alerts Collector: {e}')

        # Sync specific repository or all repositories
        if repository_id:
            self._sync_single_repository(collector, repository_id, force, dry_run)
        else:
            self._sync_all_repositories(collector, force, limit, dry_run)

    def _sync_single_repository(self, collector, repository_id, force, dry_run):
        """Sync a single repository by ID."""
        try:
            repository = Repository.objects.get(id=repository_id)
        except Repository.DoesNotExist:
            raise CommandError(f'Repository with ID {repository_id} not found')

        if not repository.github_repo_id:
            raise CommandError(f'Repository {repository.name} does not have a github_repo_id')

        self.stdout.write(f"Syncing repository: {repository.name}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))
            owner, name = collector._parse_repository_identifier(repository)
            self.stdout.write(f"Would sync: {owner}/{name}")
            return

        result = collector.sync_repository_alerts(repository, force=force)

        if result.success:
            self.stdout.write(self.style.SUCCESS(
                f"✓ {repository.name}: {result.total_alerts} alerts "
                f"(D:{result.dependabot_count}, C:{result.codeql_count}, S:{result.secret_scanning_count})"
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f"✗ {repository.name}: Failed - {', '.join(result.errors)}"
            ))

    def _sync_all_repositories(self, collector, force, limit, dry_run):
        """Sync all repositories."""
        # Get repositories that need syncing
        repositories = Repository.objects.filter(
            github_repo_id__isnull=False
        ).exclude(
            github_repo_id=0
        )

        if not force:
            # Use collector's logic to filter repositories
            repositories = collector._get_repositories_for_sync(force=False, limit=limit)
        else:
            repositories = list(repositories[:limit] if limit else repositories)

        total_repos = len(repositories)

        if total_repos == 0:
            self.stdout.write(self.style.WARNING("No repositories need syncing"))
            return

        self.stdout.write(f"Found {total_repos} repositories to sync")
        self.stdout.write(f"Force: {force}, Limit: {limit or 'none'}, Dry run: {dry_run}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN - No changes will be made\n"))
            for i, repo in enumerate(repositories[:10], 1):  # Show first 10
                owner, name = collector._parse_repository_identifier(repo)
                self.stdout.write(f"{i}. {repo.name} ({owner}/{name})")
            if total_repos > 10:
                self.stdout.write(f"... and {total_repos - 10} more")
            return

        # Progress tracking
        successful = 0
        failed = 0
        total_alerts = 0

        self.stdout.write("\nSyncing repositories:")
        self.stdout.write("-" * 80)

        for i, repository in enumerate(repositories, 1):
            self.stdout.write(f"\n[{i}/{total_repos}] {repository.name}")

            result = collector.sync_repository_alerts(repository, force=force)

            if result.success:
                successful += 1
                total_alerts += result.total_alerts
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ {result.total_alerts} alerts "
                    f"(Dependabot: {result.dependabot_count}, "
                    f"CodeQL: {result.codeql_count}, "
                    f"Secrets: {result.secret_scanning_count})"
                ))
            else:
                failed += 1
                error_msg = ', '.join(result.errors) if result.errors else 'Unknown error'
                self.stdout.write(self.style.ERROR(f"  ✗ Failed: {error_msg}"))

            # Check if we should pause for rate limits
            if collector._should_pause_for_rate_limits():
                self.stdout.write(self.style.WARNING(
                    "\nRate limit threshold reached. Pausing sync."
                ))
                break

        # Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS(f"\nSync Complete:"))
        self.stdout.write(f"  Total repositories processed: {successful + failed}")
        self.stdout.write(self.style.SUCCESS(f"  Successful: {successful}"))
        if failed > 0:
            self.stdout.write(self.style.ERROR(f"  Failed: {failed}"))
        self.stdout.write(f"  Total alerts synced: {total_alerts}")
        self.stdout.write(f"    - Dependabot: {sum(r.dependabot_count for r in collector._get_repositories_for_sync(force=True, limit=None))}")
        self.stdout.write(f"    - CodeQL: {sum(r.codeql_count for r in collector._get_repositories_for_sync(force=True, limit=None))}")
        self.stdout.write(f"    - Secret Scanning: {sum(r.secret_scanning_count for r in collector._get_repositories_for_sync(force=True, limit=None))}")
        self.stdout.write("")
