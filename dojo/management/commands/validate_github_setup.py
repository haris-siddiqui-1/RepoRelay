"""
Management command to validate GitHub setup before sync.

Pre-flight validation that checks:
- Token format and scopes
- Organization/user existence and accessibility
- Rate limit availability
- Database prerequisites (Test_Type records)
- Sample repository fetch

Usage:
    # Basic validation using configured token
    python manage.py validate_github_setup

    # Override token and org
    python manage.py validate_github_setup --token ghp_xxx --org my-org

    # JSON output for CI/CD integration
    python manage.py validate_github_setup --json

Exit codes:
    0 - All checks passed
    1 - Passed with warnings
    2 - One or more checks failed
"""

import json
import sys

from django.core.management.base import BaseCommand

from dojo.models import GitHubSyncConfiguration
from dojo.github_collector.validator import GitHubValidator


class Command(BaseCommand):
    help = 'Validate GitHub setup configuration before sync'

    def add_arguments(self, parser):
        parser.add_argument(
            '--token',
            type=str,
            help='GitHub personal access token (overrides configured token)'
        )
        parser.add_argument(
            '--org',
            type=str,
            help='GitHub organization or username (overrides configured account)'
        )
        parser.add_argument(
            '--account-type',
            type=str,
            choices=['organization', 'user'],
            default='organization',
            help='Account type: organization or user (default: organization)'
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results as JSON'
        )

    def handle(self, *args, **options):
        # Get token and org from options or configuration
        token = options.get('token')
        org = options.get('org')
        account_type = options.get('account_type', 'organization')

        # Fall back to saved configuration
        if not token or not org:
            try:
                config = GitHubSyncConfiguration.objects.get(pk=1)
                if not token:
                    token = config.github_token
                if not org:
                    org = config.account_name
                    account_type = config.account_type
            except GitHubSyncConfiguration.DoesNotExist:
                pass

        # Validate we have required params
        if not token:
            if options.get('json'):
                self.stdout.write(json.dumps({
                    'valid': False,
                    'error': 'No GitHub token provided. Use --token or configure via /github/sync/configuration'
                }, indent=2))
            else:
                self.stderr.write(self.style.ERROR(
                    'No GitHub token provided. Use --token or configure via /github/sync/configuration'
                ))
            sys.exit(2)

        if not org:
            if options.get('json'):
                self.stdout.write(json.dumps({
                    'valid': False,
                    'error': 'No organization/username provided. Use --org or configure via /github/sync/configuration'
                }, indent=2))
            else:
                self.stderr.write(self.style.ERROR(
                    'No organization/username provided. Use --org or configure via /github/sync/configuration'
                ))
            sys.exit(2)

        # Run validation
        validator = GitHubValidator(token, account_type, org)
        result = validator.validate_full_setup()

        # Output results
        if options.get('json'):
            self.output_json(result, validator)
        else:
            self.output_human(result, org)

        # Exit with appropriate code
        if not result.valid:
            sys.exit(2)
        elif result.warnings:
            sys.exit(1)
        else:
            sys.exit(0)

    def output_json(self, result, validator):
        """Output validation result as JSON."""
        output = validator.to_dict(result)
        self.stdout.write(json.dumps(output, indent=2, default=str))

    def output_human(self, result, org):
        """Output validation result as human-readable text."""
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('GitHub Integration Validation Report'))
        self.stdout.write('=' * 50)
        self.stdout.write('')

        # Token validation section
        self.stdout.write(self.style.HTTP_INFO('Token Validation'))

        token_format = result.checks.get('token_format', {})
        if token_format.get('status') == 'pass':
            self.stdout.write(self.style.SUCCESS(f"  ✓ Format: {token_format.get('message', 'Valid')}"))
        else:
            self.stdout.write(self.style.ERROR(f"  ✗ Format: {token_format.get('message', 'Invalid')}"))

        token_scopes = result.checks.get('token_scopes', {})
        if token_scopes.get('status') == 'pass':
            scopes = token_scopes.get('scopes', [])
            self.stdout.write(self.style.SUCCESS(f"  ✓ Scopes: {', '.join(scopes)}"))
        else:
            self.stdout.write(self.style.ERROR(f"  ✗ Scopes: {token_scopes.get('message', 'Invalid')}"))
            missing = token_scopes.get('missing_scopes', [])
            if missing:
                self.stdout.write(self.style.WARNING(f"    Missing: {', '.join(missing)}"))

        self.stdout.write('')

        # Account validation section
        self.stdout.write(self.style.HTTP_INFO('Account Validation'))

        account_exists = result.checks.get('account_exists', {})
        if account_exists.get('status') == 'pass':
            repo_count = account_exists.get('repository_count', 0)
            self.stdout.write(self.style.SUCCESS(f"  ✓ Account '{org}' exists ({repo_count} repositories)"))
        else:
            self.stdout.write(self.style.ERROR(f"  ✗ {account_exists.get('message', 'Account not found')}"))

        self.stdout.write('')

        # Rate limits section
        self.stdout.write(self.style.HTTP_INFO('Rate Limits'))

        rate_limits = result.checks.get('rate_limits', {})
        if rate_limits.get('status') == 'pass':
            graphql = rate_limits.get('graphql_remaining', 0)
            graphql_limit = rate_limits.get('graphql_limit', 5000)
            rest = rate_limits.get('rest_remaining', 0)
            rest_limit = rate_limits.get('rest_limit', 5000)
            graphql_pct = int((graphql / graphql_limit) * 100) if graphql_limit else 0
            rest_pct = int((rest / rest_limit) * 100) if rest_limit else 0
            self.stdout.write(self.style.SUCCESS(f"  ✓ GraphQL: {graphql:,} / {graphql_limit:,} remaining ({graphql_pct}%)"))
            self.stdout.write(self.style.SUCCESS(f"  ✓ REST: {rest:,} / {rest_limit:,} remaining ({rest_pct}%)"))
        elif rate_limits.get('status') == 'fail':
            self.stdout.write(self.style.ERROR(f"  ✗ {rate_limits.get('message', 'Rate limit exhausted')}"))
        else:
            self.stdout.write(self.style.WARNING(f"  ⚠ {rate_limits.get('message', 'Could not check rate limits')}"))

        self.stdout.write('')

        # Prerequisites section
        self.stdout.write(self.style.HTTP_INFO('Prerequisites'))

        prerequisites = result.checks.get('prerequisites', {})
        if prerequisites.get('status') == 'pass':
            self.stdout.write(self.style.SUCCESS("  ✓ Test_Type 'GitHub Dependabot' exists"))
            self.stdout.write(self.style.SUCCESS("  ✓ Test_Type 'GitHub CodeQL' exists"))
            self.stdout.write(self.style.SUCCESS("  ✓ Test_Type 'GitHub Secret Scanning' exists"))
        else:
            missing = prerequisites.get('missing_types', [])
            for t in missing:
                self.stdout.write(self.style.ERROR(f"  ✗ Test_Type '{t}' missing"))
            existing = prerequisites.get('existing_types', [])
            for t in existing:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Test_Type '{t}' exists"))

        self.stdout.write('')

        # Sample fetch section
        self.stdout.write(self.style.HTTP_INFO('Sample Fetch'))

        sample_fetch = result.checks.get('sample_fetch', {})
        if sample_fetch.get('status') == 'pass':
            sample_repo = sample_fetch.get('sample_repo', '')
            if sample_repo:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Successfully fetched: {sample_repo}"))
            else:
                self.stdout.write(self.style.SUCCESS("  ✓ No repositories found (empty account)"))
        else:
            self.stdout.write(self.style.ERROR(f"  ✗ {sample_fetch.get('message', 'Failed to fetch sample')}"))

        self.stdout.write('')
        self.stdout.write('=' * 50)

        # Final status
        if result.valid and not result.warnings:
            self.stdout.write(self.style.SUCCESS('Status: READY TO SYNC'))
        elif result.valid and result.warnings:
            self.stdout.write(self.style.WARNING('Status: READY WITH WARNINGS'))
        else:
            self.stdout.write(self.style.ERROR('Status: NOT READY - FIX ISSUES ABOVE'))

        self.stdout.write('')
