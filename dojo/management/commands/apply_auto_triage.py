"""
Django management command to apply auto-triage rules to findings.

Usage:
    python manage.py apply_auto_triage [--all] [--product-id ID] [--finding-ids ID,ID,...] [--reset] [--validate]

Examples:
    # Triage all active findings
    python manage.py apply_auto_triage

    # Triage all findings including inactive
    python manage.py apply_auto_triage --all

    # Triage specific product
    python manage.py apply_auto_triage --product-id 123

    # Triage specific findings
    python manage.py apply_auto_triage --finding-ids 456,789,1011

    # Reset all triage decisions and re-evaluate
    python manage.py apply_auto_triage --reset

    # Validate triage rules without applying
    python manage.py apply_auto_triage --validate

    # Get triage statistics
    python manage.py apply_auto_triage --stats
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from dojo.auto_triage import AutoTriageEngine
from dojo.auto_triage.rules import validate_all_rules
from dojo.models import Product, Finding

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Apply auto-triage rules to findings based on EPSS scores and repository context'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Triage all findings (including inactive)'
        )
        parser.add_argument(
            '--product-id',
            type=int,
            help='Triage findings for specific product by ID'
        )
        parser.add_argument(
            '--finding-ids',
            type=str,
            help='Comma-separated list of finding IDs to triage'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all triage decisions to PENDING before re-evaluation'
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate triage rules without applying them'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Display triage statistics only'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be triaged without making changes'
        )

    def handle(self, *args, **options):
        """Execute the auto-triage command."""
        all_findings = options.get('all', False)
        product_id = options.get('product_id')
        finding_ids_str = options.get('finding_ids')
        reset = options.get('reset', False)
        validate_only = options.get('validate', False)
        stats_only = options.get('stats', False)
        dry_run = options.get('dry_run', False)

        # Check if auto-triage is enabled
        auto_triage_enabled = getattr(settings, 'DD_AUTO_TRIAGE_ENABLED', False)
        if not auto_triage_enabled and not (validate_only or stats_only):
            self.stdout.write(
                self.style.WARNING('Auto-triage is disabled in settings (DD_AUTO_TRIAGE_ENABLED=False)')
            )
            self.stdout.write('Use --validate to test rules or enable in settings to apply.')
            return

        # Validate rules mode
        if validate_only:
            self._validate_rules()
            return

        # Initialize engine
        try:
            engine = AutoTriageEngine()
        except Exception as e:
            raise CommandError(f'Failed to initialize auto-triage engine: {e}')

        # Stats mode
        if stats_only:
            self._display_statistics(engine)
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Reset mode
        if reset:
            self._reset_triage_decisions(engine, finding_ids_str, dry_run)
            if dry_run:
                return

        # Determine triage scope
        if finding_ids_str:
            self._triage_specific_findings(engine, finding_ids_str, dry_run)
        elif product_id:
            self._triage_product_findings(engine, product_id, dry_run)
        else:
            self._triage_all_findings(engine, all_findings, dry_run)

    def _validate_rules(self):
        """Validate triage rules."""
        self.stdout.write('Validating auto-triage rules...')

        errors = validate_all_rules()

        if errors:
            self.stdout.write(self.style.ERROR(f'\nFound {len(errors)} validation errors:'))
            for error in errors:
                self.stdout.write(self.style.ERROR(f'  - {error}'))
            raise CommandError('Rule validation failed')
        else:
            from dojo.auto_triage.rules import TRIAGE_RULES
            self.stdout.write(self.style.SUCCESS(f'\n✓ All {len(TRIAGE_RULES)} rules are valid'))

            # Display rule summary
            self.stdout.write('\nRule Summary:')
            for idx, rule in enumerate(TRIAGE_RULES, 1):
                self.stdout.write(
                    f"  {idx}. {rule['name']}: {rule['decision']} "
                    f"(confidence: {rule.get('confidence', 'N/A')}%)"
                )

    def _triage_all_findings(self, engine, include_inactive, dry_run):
        """Triage all findings."""
        active_only = not include_inactive

        self.stdout.write(
            f'Applying auto-triage to all {"" if active_only else "active and inactive "}findings...'
        )

        if dry_run:
            findings = engine._get_findings_for_triage(active_only=active_only)
            count = findings.count()
            self.stdout.write(f'Would triage {count} findings')
            return

        # Perform triage
        try:
            stats = engine.triage_all_findings(active_only=active_only)
            self._display_results(stats)
        except Exception as e:
            raise CommandError(f'Triage failed: {e}')

    def _triage_product_findings(self, engine, product_id, dry_run):
        """Triage findings for specific product."""
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            raise CommandError(f'Product with ID {product_id} does not exist')

        self.stdout.write(f'Applying auto-triage to product: {product.name}')

        if dry_run:
            findings = Finding.objects.filter(
                test__engagement__product_id=product_id,
                active=True
            )
            count = findings.count()
            self.stdout.write(f'Would triage {count} findings in product {product.name}')
            return

        # Perform triage
        try:
            stats = engine.triage_findings_by_product(product_id)
            self._display_results(stats)
        except Exception as e:
            raise CommandError(f'Triage failed for product {product_id}: {e}')

    def _triage_specific_findings(self, engine, finding_ids_str, dry_run):
        """Triage specific findings by ID."""
        try:
            finding_ids = [int(fid.strip()) for fid in finding_ids_str.split(',')]
        except ValueError:
            raise CommandError('Invalid finding IDs format. Use comma-separated integers.')

        self.stdout.write(f'Applying auto-triage to {len(finding_ids)} specific findings')

        if dry_run:
            findings = Finding.objects.filter(id__in=finding_ids)
            count = findings.count()
            self.stdout.write(f'Would triage {count} findings')
            return

        # Perform triage
        try:
            stats = engine.triage_findings_by_ids(finding_ids)
            self._display_results(stats)
        except Exception as e:
            raise CommandError(f'Triage failed for specific findings: {e}')

    def _reset_triage_decisions(self, engine, finding_ids_str, dry_run):
        """Reset triage decisions to PENDING."""
        finding_ids = None

        if finding_ids_str:
            try:
                finding_ids = [int(fid.strip()) for fid in finding_ids_str.split(',')]
            except ValueError:
                raise CommandError('Invalid finding IDs format. Use comma-separated integers.')

        scope = f'{len(finding_ids)} specific findings' if finding_ids else 'all findings'
        self.stdout.write(f'Resetting auto-triage decisions for {scope}...')

        if dry_run:
            if finding_ids:
                count = Finding.objects.filter(id__in=finding_ids).count()
            else:
                count = Finding.objects.count()
            self.stdout.write(f'Would reset {count} findings to PENDING')
            return

        # Perform reset
        try:
            result = engine.reset_triage_decisions(finding_ids=finding_ids)
            self.stdout.write(
                self.style.SUCCESS(f"✓ Reset {result['reset_count']} findings to PENDING")
            )
        except Exception as e:
            raise CommandError(f'Reset failed: {e}')

    def _display_results(self, stats):
        """Display triage results."""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('AUTO-TRIAGE COMPLETED'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'Total findings processed: {stats["total_findings"]}')
        self.stdout.write('')

        if stats['dismissed'] > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Dismissed: {stats["dismissed"]}')
            )

        if stats['escalated'] > 0:
            self.stdout.write(
                self.style.WARNING(f'⚠ Escalated: {stats["escalated"]}')
            )

        if stats['accepted_risk'] > 0:
            self.stdout.write(
                f'⊙ Accepted Risk: {stats["accepted_risk"]}'
            )

        if stats['pending'] > 0:
            self.stdout.write(
                f'⊘ Pending Review: {stats["pending"]}'
            )

        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f'✗ Errors: {stats["errors"]}'))

        self.stdout.write('=' * 60)

    def _display_statistics(self, engine):
        """Display triage statistics."""
        try:
            stats = engine.get_triage_statistics()

            self.stdout.write('\n' + '=' * 60)
            self.stdout.write('AUTO-TRIAGE STATISTICS')
            self.stdout.write('=' * 60)
            self.stdout.write(f'Total active findings: {stats["total"]:,}')
            self.stdout.write('')

            if 'by_decision' in stats and stats['by_decision']:
                self.stdout.write('Breakdown by decision:')
                for decision, data in stats['by_decision'].items():
                    count = data['count']
                    pct = data['percentage']

                    # Color code based on decision type
                    if decision == 'ESCALATE':
                        style = self.style.WARNING
                    elif decision == 'DISMISS':
                        style = self.style.SUCCESS
                    else:
                        style = lambda x: x

                    self.stdout.write(
                        style(f'  {decision}: {count:,} ({pct}%)')
                    )
            else:
                self.stdout.write('No triage decisions found')

            self.stdout.write('=' * 60)

            # Display sample escalated findings
            self.stdout.write('\nSample escalated findings (top 10):')
            escalated = Finding.objects.filter(
                active=True,
                auto_triage_decision='ESCALATE'
            ).select_related('test__engagement__product').order_by('-epss_score')[:10]

            if escalated.exists():
                self.stdout.write('')
                for finding in escalated:
                    epss = finding.epss_score if finding.epss_score else 'N/A'
                    product = finding.test.engagement.product
                    self.stdout.write(
                        f'  {finding.cve or finding.title[:40]}: EPSS={epss} '
                        f'({product.name}, Tier={product.business_criticality})'
                    )
            else:
                self.stdout.write('  None found')

        except Exception as e:
            raise CommandError(f'Failed to retrieve statistics: {e}')
