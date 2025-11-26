"""
Priority Router - Phase 5 of Vulnerability Prioritization Strategy

Routes finding notifications based on priority bucket:
- P0/P1: Immediate alerts (real-time)
- P2: Standard notifications (1-hour delay via queue)
- P3: Daily digest
- P4: Weekly digest
- Accepted findings: Suppressed

Reference: sessions/docs/vulnerability-prioritization-strategy.md - Part 6
"""
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Optional

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

if TYPE_CHECKING:
    from dojo.models import Finding, PriorityDigestQueue

logger = logging.getLogger(__name__)


class PriorityRouter:
    """
    Routes finding notifications based on priority bucket.

    Routing Rules:
    - P0/P1: Immediate notification (real-time)
    - P2: Queue for standard notification (configurable delay, default 1 hour)
    - P3: Add to daily digest queue
    - P4: Add to weekly digest queue
    - Auto-accepted findings: Suppress all notifications
    """

    # Default configuration (overridable via settings)
    DEFAULT_P2_DELAY_MINUTES = 60
    DEFAULT_DAILY_DIGEST_TIME = "09:00"
    DEFAULT_WEEKLY_DIGEST_DAY = "monday"

    def route_finding_notification(
        self,
        finding: "Finding",
        event: str = "scan_added",
        **kwargs,
    ) -> Optional[str]:
        """
        Route a finding notification based on priority bucket.

        Args:
            finding: Finding instance to notify about
            event: Base event type (scan_added, other, etc.)
            **kwargs: Additional context for notification

        Returns:
            Routing result: 'immediate', 'queued_standard', 'queued_daily',
            'queued_weekly', 'suppressed', or None if no action taken
        """
        # Check suppression conditions
        if self._should_suppress(finding):
            logger.debug(
                "Suppressing notification for finding %s (triage_state=%s)",
                finding.id,
                finding.triage_state
            )
            return "suppressed"

        # Route based on priority bucket
        bucket = finding.priority_bucket or "P3"  # Default to P3 if not calculated

        if bucket in ["P0", "P1"]:
            self._send_immediate(finding, bucket, **kwargs)
            return "immediate"
        elif bucket == "P2":
            self._queue_standard(finding, **kwargs)
            return "queued_standard"
        elif bucket == "P3":
            self._add_to_daily_digest(finding)
            return "queued_daily"
        else:  # P4 or unknown
            self._add_to_weekly_digest(finding)
            return "queued_weekly"

    def _should_suppress(self, finding: "Finding") -> bool:
        """
        Check if notification should be suppressed.

        Suppression conditions:
        - triage_state is 'accepted' (risk accepted)
        - triage_state is 'dismissed' (false positive, won't fix)
        - Setting NOTIFICATION_SUPPRESS_AUTO_ACCEPTED is True (default)

        Args:
            finding: Finding instance

        Returns:
            True if notification should be suppressed
        """
        suppress_auto_accepted = getattr(
            settings,
            "NOTIFICATION_SUPPRESS_AUTO_ACCEPTED",
            True
        )

        if not suppress_auto_accepted:
            return False

        # Suppress if finding has been triaged to a terminal state
        suppressed_states = {"accepted", "dismissed"}
        return finding.triage_state in suppressed_states

    def _send_immediate(
        self,
        finding: "Finding",
        bucket: str,
        **kwargs,
    ) -> None:
        """
        Send immediate notification for P0/P1 findings.

        Args:
            finding: Finding instance
            bucket: Priority bucket (P0 or P1)
            **kwargs: Additional notification context
        """
        from dojo.notifications.helper import create_notification

        # Determine event based on bucket
        event = "priority_alert_immediate"

        # Build notification title
        severity = finding.severity or "Unknown"
        title = f"[{bucket}] {severity} Priority Finding: {finding.title}"

        # Build URL
        url = kwargs.get("url") or reverse("view_finding", args=(finding.id,))

        logger.info(
            "Sending immediate notification for finding %s (bucket=%s, severity=%s)",
            finding.id, bucket, severity
        )

        create_notification(
            event=event,
            title=title,
            finding=finding,
            url=url,
            priority_bucket=bucket,
            **kwargs,
        )

    def _queue_standard(self, finding: "Finding", **kwargs) -> None:
        """
        Queue P2 finding for standard notification (1-hour delay).

        Uses PriorityDigestQueue model with digest_type='standard'.

        Args:
            finding: Finding instance
            **kwargs: Additional notification context (stored in queue)
        """
        from django.db import IntegrityError
        from dojo.models import PriorityDigestQueue

        # Use try-except with unique constraint to prevent race conditions
        try:
            PriorityDigestQueue.objects.create(
                finding=finding,
                digest_type="standard",
            )
            logger.debug("Queued finding %s for standard notification", finding.id)
        except IntegrityError:
            # Duplicate entry - already queued (constraint: unique_pending_digest_entry)
            logger.debug("Finding %s already queued for standard notification", finding.id)

    def _add_to_daily_digest(self, finding: "Finding") -> None:
        """
        Add P3 finding to daily digest queue.

        Args:
            finding: Finding instance
        """
        from django.db import IntegrityError
        from dojo.models import PriorityDigestQueue

        # Use try-except with unique constraint to prevent race conditions
        try:
            PriorityDigestQueue.objects.create(
                finding=finding,
                digest_type="daily",
            )
            logger.debug("Added finding %s to daily digest queue", finding.id)
        except IntegrityError:
            # Duplicate entry - already queued (constraint: unique_pending_digest_entry)
            logger.debug("Finding %s already queued for daily digest", finding.id)

    def _add_to_weekly_digest(self, finding: "Finding") -> None:
        """
        Add P4 finding to weekly digest queue.

        Args:
            finding: Finding instance
        """
        from django.db import IntegrityError
        from dojo.models import PriorityDigestQueue

        # Use try-except with unique constraint to prevent race conditions
        try:
            PriorityDigestQueue.objects.create(
                finding=finding,
                digest_type="weekly",
            )
            logger.debug("Added finding %s to weekly digest queue", finding.id)
        except IntegrityError:
            # Duplicate entry - already queued (constraint: unique_pending_digest_entry)
            logger.debug("Finding %s already queued for weekly digest", finding.id)

    def send_standard_notifications(self) -> int:
        """
        Send queued standard (P2) notifications that have aged past the delay.

        Called by Celery task periodically (every 15 minutes).

        Returns:
            Number of notifications sent
        """
        from dojo.models import PriorityDigestQueue
        from dojo.notifications.helper import create_notification

        delay_minutes = getattr(
            settings,
            "NOTIFICATION_P2_DELAY_MINUTES",
            self.DEFAULT_P2_DELAY_MINUTES
        )

        cutoff_time = timezone.now() - timedelta(minutes=delay_minutes)

        # Get queued items older than delay
        queued_items = PriorityDigestQueue.objects.filter(
            digest_type="standard",
            sent_at__isnull=True,
            queued_at__lte=cutoff_time,
        ).select_related(
            "finding",
            "finding__test__engagement__product",
        )

        sent_count = 0

        for item in queued_items:
            finding = item.finding

            # Skip if finding is no longer active or has been triaged
            if not finding.active or self._should_suppress(finding):
                item.sent_at = timezone.now()
                item.save(update_fields=["sent_at"])
                continue

            try:
                url = reverse("view_finding", args=(finding.id,))
                title = f"[P2] {finding.severity} Finding: {finding.title}"

                create_notification(
                    event="priority_alert_standard",
                    title=title,
                    finding=finding,
                    url=url,
                    priority_bucket="P2",
                )

                item.sent_at = timezone.now()
                item.save(update_fields=["sent_at"])
                sent_count += 1

                logger.debug("Sent standard notification for finding %s", finding.id)

            except Exception as e:
                logger.error(
                    "Failed to send standard notification for finding %s: %s",
                    finding.id, e
                )

        if sent_count > 0:
            logger.info("Sent %d standard notifications", sent_count)

        return sent_count

    def send_daily_digest(self) -> int:
        """
        Generate and send daily digest of P3 findings.

        Called by Celery Beat at configured time (default 9:00 AM).

        Returns:
            Number of findings included in digest
        """
        return self._send_digest("daily", "priority_digest_daily")

    def send_weekly_digest(self) -> int:
        """
        Generate and send weekly digest of P4 findings.

        Called by Celery Beat on configured day (default Monday 9:00 AM).

        Returns:
            Number of findings included in digest
        """
        return self._send_digest("weekly", "priority_digest_weekly")

    def _send_digest(self, digest_type: str, event: str) -> int:
        """
        Generate and send digest notification.

        Args:
            digest_type: 'daily' or 'weekly'
            event: Notification event name

        Returns:
            Number of findings included in digest
        """
        from dojo.models import PriorityDigestQueue
        from dojo.notifications.helper import create_notification

        # Get all unsent items for this digest type
        queued_items = PriorityDigestQueue.objects.filter(
            digest_type=digest_type,
            sent_at__isnull=True,
        ).select_related(
            "finding",
            "finding__test__engagement__product",
        ).order_by("-finding__priority_score")

        if not queued_items.exists():
            logger.debug("No findings to include in %s digest", digest_type)
            return 0

        # Group findings by product for organized digest
        findings_by_product = {}
        active_findings = []

        for item in queued_items:
            finding = item.finding

            # Skip inactive or suppressed findings
            if not finding.active or self._should_suppress(finding):
                item.sent_at = timezone.now()
                item.save(update_fields=["sent_at"])
                continue

            active_findings.append(finding)

            try:
                product = finding.test.engagement.product
                product_name = product.name if product else "Unknown Product"
            except AttributeError:
                product_name = "Unknown Product"

            if product_name not in findings_by_product:
                findings_by_product[product_name] = []
            findings_by_product[product_name].append(finding)

        if not active_findings:
            logger.debug("All findings in %s digest were inactive/suppressed", digest_type)
            return 0

        # Generate digest summary
        severity_counts = {}
        for finding in active_findings:
            severity = finding.severity or "Unknown"
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        bucket = "P3" if digest_type == "daily" else "P4"
        title = f"[{bucket}] {digest_type.title()} Digest: {len(active_findings)} findings"

        logger.info(
            "Sending %s digest with %d findings across %d products",
            digest_type, len(active_findings), len(findings_by_product)
        )

        try:
            create_notification(
                event=event,
                title=title,
                findings=active_findings,
                findings_by_product=findings_by_product,
                severity_counts=severity_counts,
                digest_type=digest_type,
                priority_bucket=bucket,
                url=reverse("finding"),  # Link to findings list
            )

            # Mark all as sent
            with transaction.atomic():
                queued_items.update(sent_at=timezone.now())

        except Exception as e:
            logger.error("Failed to send %s digest: %s", digest_type, e)
            return 0

        return len(active_findings)

    def get_digest_preview(self, digest_type: str) -> dict:
        """
        Get preview of pending digest without sending.

        Args:
            digest_type: 'daily' or 'weekly'

        Returns:
            Dict with findings count, severity breakdown, and sample findings
        """
        from dojo.models import PriorityDigestQueue

        queued_items = PriorityDigestQueue.objects.filter(
            digest_type=digest_type,
            sent_at__isnull=True,
        ).select_related(
            "finding",
        ).order_by("-finding__priority_score")[:100]  # Limit preview

        findings = [item.finding for item in queued_items if item.finding.active]

        severity_counts = {}
        for finding in findings:
            severity = finding.severity or "Unknown"
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return {
            "digest_type": digest_type,
            "total_count": len(findings),
            "severity_counts": severity_counts,
            "sample_findings": [
                {
                    "id": f.id,
                    "title": f.title,
                    "severity": f.severity,
                    "priority_bucket": f.priority_bucket,
                }
                for f in findings[:10]
            ],
        }


# --- Convenience Functions ---


def route_finding_notification(
    finding: "Finding",
    event: str = "scan_added",
    **kwargs,
) -> Optional[str]:
    """
    Convenience function to route a finding notification.

    This is the primary integration point for other modules.

    Args:
        finding: Finding instance
        event: Base event type
        **kwargs: Additional notification context

    Returns:
        Routing result string or None
    """
    router = PriorityRouter()
    return router.route_finding_notification(finding, event, **kwargs)


def route_escalated_finding(finding: "Finding", escalated_by: str = None) -> None:
    """
    Send immediate notification for an escalated finding.

    Called when triage_state changes to 'escalated'.

    Args:
        finding: Finding instance that was escalated
        escalated_by: Username who performed the escalation
    """
    from dojo.notifications.helper import create_notification

    url = reverse("view_finding", args=(finding.id,))
    title = f"[ESCALATED] {finding.severity} Finding: {finding.title}"

    logger.info("Sending escalation notification for finding %s", finding.id)

    create_notification(
        event="priority_alert_immediate",
        title=title,
        finding=finding,
        url=url,
        priority_bucket=finding.priority_bucket or "P1",
        escalated_by=escalated_by,
        is_escalation=True,
    )
