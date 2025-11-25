"""
Django management command to calculate priority scores for findings.

Implements Phase 1 of the vulnerability prioritization strategy by calculating
priority scores based on tier, severity, and risk modifiers.

Usage:
    python manage.py calculate_priority_scores [options]

Examples:
    # Calculate priority for all active findings (skips already scored)
    python manage.py calculate_priority_scores

    # Force recalculation of all active findings
    python manage.py calculate_priority_scores --force

    # Calculate for specific test's findings
    python manage.py calculate_priority_scores --test-id 123

    # Calculate for specific product's findings
    python manage.py calculate_priority_scores --product-id 456

    # Limit batch size for testing
    python manage.py calculate_priority_scores --limit 1000

    # Dry run to preview what would be scored
    python manage.py calculate_priority_scores --dry-run

    # Queue async Celery tasks instead of blocking
    python manage.py calculate_priority_scores --async

Performance:
    - Batch processing: 1000 findings per batch
    - Query optimization: select_related/prefetch_related for minimal DB hits
    - Progress logging: Every 100 findings processed
"""

import logging
import time

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from dojo.finding.priority_scorer import PriorityScorer, get_repository_for_finding
from dojo.models import Finding

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Calculate priority scores for findings based on tier, severity, and risk modifiers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-id',
            type=int,
            help='Calculate priority only for findings in a specific test'
        )
        parser.add_argument(
            '--product-id',
            type=int,
            help='Calculate priority only for findings in a specific product'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Maximum number of findings to process (for testing)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Recalculate even if already scored (ignore priority_calculated_at)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview calculations without saving to database'
        )
        parser.add_argument(
            '--async',
            action='store_true',
            dest='async_mode',
            help='Queue Celery tasks for async processing instead of blocking'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Number of findings to process per batch (default: 1000)'
        )
        # Note: --verbosity is provided by Django's BaseCommand

    def handle(self, *args, **options):
        """Execute the priority calculation command."""
        test_id = options.get('test_id')
        product_id = options.get('product_id')
        limit = options.get('limit')
        force = options.get('force', False)
        dry_run = options.get('dry_run', False)
        async_mode = options.get('async_mode', False)
        batch_size = options.get('batch_size', 1000)
        verbosity = options.get('verbosity', 1)

        # Configure logging based on verbosity
        if verbosity >= 2:
            logging.getLogger('dojo.finding.priority_scorer').setLevel(logging.DEBUG)
        elif verbosity == 1:
            logging.getLogger('dojo.finding.priority_scorer').setLevel(logging.INFO)
        else:
            logging.getLogger('dojo.finding.priority_scorer').setLevel(logging.WARNING)

        # Build queryset
        queryset = self._build_queryset(test_id, product_id, force)

        # Apply limit if specified
        if limit:
            queryset = queryset[:limit]
            self.stdout.write(f"Limited to {limit} findings")

        # Count total findings
        total_count = queryset.count() if not limit else min(limit, queryset.count())
        self.stdout.write(f"Found {total_count} findings to process")

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("No findings to process"))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))

        if async_mode and not dry_run:
            self._process_async(queryset, total_count)
        else:
            self._process_sync(queryset, total_count, batch_size, dry_run, verbosity)

    def _build_queryset(self, test_id, product_id, force):
        """Build the Finding queryset with appropriate filters and prefetches."""
        # Base filter: active, non-duplicate, non-mitigated findings
        queryset = Finding.objects.filter(
            active=True,
            duplicate=False,
            is_mitigated=False
        ).select_related(
            'test__engagement__product'
        ).prefetch_related(
            'test__engagement__product__repositories'
        )

        # Filter by test if specified
        if test_id:
            queryset = queryset.filter(test_id=test_id)
            self.stdout.write(f"Filtering by test ID: {test_id}")

        # Filter by product if specified
        if product_id:
            queryset = queryset.filter(test__engagement__product_id=product_id)
            self.stdout.write(f"Filtering by product ID: {product_id}")

        # Skip already scored findings unless force is set
        if not force:
            queryset = queryset.filter(
                Q(priority_calculated_at__isnull=True) | Q(priority_score=0)
            )
            self.stdout.write("Skipping already scored findings (use --force to recalculate)")

        return queryset.order_by('id')

    def _process_sync(self, queryset, total_count, batch_size, dry_run, verbosity):
        """Process findings synchronously with batch updates."""
        scorer = PriorityScorer()
        processed = 0
        updated = 0
        errors = 0
        start_time = time.time()

        # Statistics tracking
        bucket_counts = {'P0': 0, 'P1': 0, 'P2': 0, 'P3': 0, 'P4': 0}

        # Process in batches
        batch_start = 0
        while batch_start < total_count:
            batch = list(queryset[batch_start:batch_start + batch_size])
            if not batch:
                break

            findings_to_update = []

            for finding in batch:
                try:
                    # Get repository if available
                    repository = get_repository_for_finding(finding)

                    # Calculate priority score
                    score, bucket = scorer.calculate_and_get_bucket(finding, repository)

                    if not dry_run:
                        finding.priority_score = score
                        finding.priority_bucket = bucket
                        finding.priority_calculated_at = timezone.now()
                        findings_to_update.append(finding)

                    bucket_counts[bucket] += 1
                    updated += 1

                    if verbosity >= 2:
                        self.stdout.write(
                            f"  Finding {finding.id}: {finding.severity} -> score={score}, bucket={bucket}"
                        )

                except Exception as e:
                    errors += 1
                    logger.error("Error calculating priority for finding %s: %s", finding.id, e)
                    if verbosity >= 2:
                        self.stdout.write(self.style.ERROR(f"  Error on finding {finding.id}: {e}"))

                processed += 1

            # Bulk update the batch
            if findings_to_update and not dry_run:
                Finding.objects.bulk_update(
                    findings_to_update,
                    ['priority_score', 'priority_bucket', 'priority_calculated_at'],
                    batch_size=batch_size
                )

            # Progress logging
            if processed % 100 == 0 or processed == total_count:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                self.stdout.write(
                    f"Progress: {processed}/{total_count} ({rate:.1f}/s) - "
                    f"Updated: {updated}, Errors: {errors}"
                )

            batch_start += batch_size

        # Summary
        elapsed = time.time() - start_time
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Completed in {elapsed:.1f}s"))
        self.stdout.write(f"  Total processed: {processed}")
        self.stdout.write(f"  Successfully updated: {updated}")
        self.stdout.write(f"  Errors: {errors}")
        self.stdout.write("")
        self.stdout.write("Priority bucket distribution:")
        for bucket, count in bucket_counts.items():
            self.stdout.write(f"  {bucket}: {count}")

    def _process_async(self, queryset, total_count):
        """Queue Celery tasks for async processing."""
        from dojo.finding.priority_scorer import calculate_finding_priority_task

        self.stdout.write(f"Queuing {total_count} Celery tasks for async processing...")

        queued = 0
        errors = 0

        for finding in queryset.only('id'):
            try:
                calculate_finding_priority_task.delay(finding.id)
                queued += 1

                if queued % 1000 == 0:
                    self.stdout.write(f"Queued: {queued}/{total_count}")

            except Exception as e:
                errors += 1
                logger.error("Error queuing task for finding %s: %s", finding.id, e)

        self.stdout.write(self.style.SUCCESS(f"Queued {queued} tasks, {errors} errors"))
        self.stdout.write("Check Celery worker logs for processing status")
