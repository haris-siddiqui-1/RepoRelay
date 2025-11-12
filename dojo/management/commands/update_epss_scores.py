"""
Django management command to update EPSS scores for findings.

Usage:
    python manage.py update_epss_scores [--all] [--product-id ID] [--finding-ids ID,ID,...] [--trigger-triage]

Examples:
    # Update all active findings with CVEs
    python manage.py update_epss_scores

    # Update all findings including inactive
    python manage.py update_epss_scores --all

    # Update specific product
    python manage.py update_epss_scores --product-id 123

    # Update specific findings
    python manage.py update_epss_scores --finding-ids 456,789,1011

    # Update and trigger auto-triage for significant changes
    python manage.py update_epss_scores --trigger-triage

    # Check EPSS coverage statistics
    python manage.py update_epss_scores --stats
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from dojo.epss_service import EPSSClient, EPSSUpdater
from dojo.models import Product, Finding

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update EPSS scores for findings from FIRST.org API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Update all findings (including inactive)'
        )
        parser.add_argument(
            '--product-id',
            type=int,
            help='Update findings for specific product by ID'
        )
        parser.add_argument(
            '--finding-ids',
            type=str,
            help='Comma-separated list of finding IDs to update'
        )
        parser.add_argument(
            '--trigger-triage',
            action='store_true',
            help='Trigger auto-triage for findings with significant EPSS changes'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Display EPSS coverage statistics only'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )

    def handle(self, *args, **options):
        """Execute the EPSS update command."""
        all_findings = options.get('all', False)
        product_id = options.get('product_id')
        finding_ids_str = options.get('finding_ids')
        trigger_triage = options.get('trigger_triage', False)
        stats_only = options.get('stats', False)
        dry_run = options.get('dry_run', False)

        # Initialize EPSS client and updater
        try:
            epss_client = EPSSClient()
            updater = EPSSUpdater(epss_client)
        except Exception as e:
            raise CommandError(f'Failed to initialize EPSS client: {e}')

        # Stats mode
        if stats_only:
            self._display_coverage_stats(updater)
            return

        # Check API status first
        if not dry_run:
            self.stdout.write('Checking EPSS API status...')
            if not epss_client.check_api_status():
                raise CommandError('EPSS API is not accessible. Please check your internet connection.')
            self.stdout.write(self.style.SUCCESS('✓ EPSS API is accessible'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Determine update mode
        if finding_ids_str:
            self._update_specific_findings(updater, finding_ids_str, trigger_triage, dry_run)
        elif product_id:
            self._update_product_findings(updater, product_id, trigger_triage, dry_run)
        else:
            self._update_all_findings(updater, all_findings, trigger_triage, dry_run)

    def _update_all_findings(self, updater, include_inactive, trigger_triage, dry_run):
        """Update all findings with CVEs."""
        active_only = not include_inactive

        self.stdout.write(f'Updating EPSS scores for all {"" if active_only else "active and inactive "}findings...')

        if dry_run:
            # Count findings that would be updated
            findings = updater._get_findings_with_cves(active_only)
            count = findings.count()
            cves = updater._extract_cves_from_findings(findings)
            unique_cves = len(set(cves.values()))

            self.stdout.write(f'Would update {count} findings with {unique_cves} unique CVEs')
            return

        # Perform update
        try:
            stats = updater.update_all_findings(active_only=active_only, trigger_triage=trigger_triage)
            self._display_results(stats, trigger_triage)
        except Exception as e:
            raise CommandError(f'Update failed: {e}')

    def _update_product_findings(self, updater, product_id, trigger_triage, dry_run):
        """Update findings for specific product."""
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise CommandError(f'Product with ID {product_id} does not exist')

        self.stdout.write(f'Updating EPSS scores for product: {product.name}')

        if dry_run:
            findings = Finding.objects.filter(
                test__engagement__product_id=product_id,
                active=True
            ).exclude(cve__isnull=True).exclude(cve='')
            count = findings.count()

            self.stdout.write(f'Would update {count} findings in product {product.name}')
            return

        # Perform update
        try:
            stats = updater.update_findings_by_product(product_id, trigger_triage=trigger_triage)
            self._display_results(stats, trigger_triage)
        except Exception as e:
            raise CommandError(f'Update failed for product {product_id}: {e}')

    def _update_specific_findings(self, updater, finding_ids_str, trigger_triage, dry_run):
        """Update specific findings by ID."""
        try:
            finding_ids = [int(fid.strip()) for fid in finding_ids_str.split(',')]
        except ValueError:
            raise CommandError('Invalid finding IDs format. Use comma-separated integers.')

        self.stdout.write(f'Updating EPSS scores for {len(finding_ids)} specific findings')

        if dry_run:
            findings = Finding.objects.filter(id__in=finding_ids)
            count = findings.count()
            findings_with_cve = findings.exclude(cve__isnull=True).exclude(cve='').count()

            self.stdout.write(f'Would update {count} findings ({findings_with_cve} have CVEs)')
            return

        # Perform update
        try:
            stats = updater.update_findings_by_ids(finding_ids, trigger_triage=trigger_triage)
            self._display_results(stats, trigger_triage)
        except Exception as e:
            raise CommandError(f'Update failed for specific findings: {e}')

    def _display_results(self, stats, trigger_triage):
        """Display update results."""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('EPSS UPDATE COMPLETED'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Total findings processed: {stats["total_findings"]}')
        self.stdout.write(f'Findings with CVEs: {stats["findings_with_cve"]}')
        self.stdout.write(f'Unique CVEs: {stats["unique_cves"]}')
        self.stdout.write(f'EPSS scores fetched: {stats["scores_fetched"]}')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✓ New scores: {stats["findings_new_score"]}'))
        self.stdout.write(self.style.SUCCESS(f'✓ Updated: {stats["findings_updated"]}'))
        self.stdout.write(f'⊘ Unchanged: {stats["findings_unchanged"]}')

        if stats['significant_changes'] > 0:
            self.stdout.write(
                self.style.WARNING(f'⚠ Significant changes (>20%): {stats["significant_changes"]}')
            )

        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f'✗ Errors: {stats["errors"]}'))

        if trigger_triage and stats['significant_changes'] > 0:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS(
                f'Auto-triage triggered for {stats["significant_changes"]} findings'
            ))

        self.stdout.write('=' * 60)

    def _display_coverage_stats(self, updater):
        """Display EPSS coverage statistics."""
        try:
            coverage = updater.get_epss_coverage_stats()

            self.stdout.write('\n' + '=' * 60)
            self.stdout.write('EPSS COVERAGE STATISTICS')
            self.stdout.write('=' * 60)
            self.stdout.write(f'Total active findings: {coverage["total_active_findings"]:,}')
            self.stdout.write(f'Findings with CVE: {coverage["findings_with_cve"]:,}')
            self.stdout.write(f'Findings with EPSS score: {coverage["findings_with_epss"]:,}')
            self.stdout.write('')
            self.stdout.write(
                self.style.SUCCESS(f'Coverage: {coverage["coverage_percentage"]}%')
            )

            if coverage['missing_epss_scores'] > 0:
                self.stdout.write(
                    self.style.WARNING(f'Missing scores: {coverage["missing_epss_scores"]:,}')
                )

            self.stdout.write('=' * 60)

            # Display high-risk findings
            self.stdout.write('\nHigh-risk findings (EPSS ≥ 0.5):')
            high_risk = updater.get_high_risk_findings(epss_threshold=0.5)[:10]

            if high_risk.exists():
                self.stdout.write('')
                for finding in high_risk:
                    self.stdout.write(
                        f'  {finding.cve}: {finding.epss_score:.4f} '
                        f'({finding.test.engagement.product.name})'
                    )

                total_high_risk = updater.get_high_risk_findings(epss_threshold=0.5).count()
                if total_high_risk > 10:
                    self.stdout.write(f'  ... and {total_high_risk - 10} more')
            else:
                self.stdout.write('  None found')

        except Exception as e:
            raise CommandError(f'Failed to retrieve coverage stats: {e}')
