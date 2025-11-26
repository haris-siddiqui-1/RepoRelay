"""
Unit tests for PriorityRouter - Phase 5 of Vulnerability Prioritization Strategy

Tests the PriorityRouter class which:
- Routes notifications based on priority bucket (P0-P4)
- Suppresses notifications for accepted/dismissed findings
- Queues findings for digest notifications
- Generates daily/weekly digests
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch, PropertyMock

from django.test import TestCase, override_settings
from django.utils import timezone

from dojo.finding.priority_router import PriorityRouter, route_finding_notification


class TestPriorityRouterRouting(TestCase):
    """Test notification routing based on priority bucket."""

    def setUp(self):
        # Mock settings
        self.settings_patcher = patch('dojo.finding.priority_router.settings')
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.NOTIFICATION_SUPPRESS_AUTO_ACCEPTED = True
        self.mock_settings.NOTIFICATION_P2_DELAY_MINUTES = 60

    def tearDown(self):
        self.settings_patcher.stop()

    def _create_mock_finding(self, priority_bucket="P3", triage_state="pending", **kwargs):
        """Create a mock Finding with specified attributes."""
        from dojo.models import Finding
        finding = MagicMock(spec=Finding)
        finding.id = 1
        finding.title = "Test Finding"
        finding.severity = kwargs.get("severity", "Medium")
        finding.priority_bucket = priority_bucket
        finding.priority_score = kwargs.get("priority_score", 100)
        finding.triage_state = triage_state
        finding.active = kwargs.get("active", True)

        # Mock the test->engagement->product chain
        finding.test = MagicMock()
        finding.test.engagement = MagicMock()
        finding.test.engagement.product = MagicMock()
        finding.test.engagement.product.name = "Test Product"

        return finding

    @patch('dojo.finding.priority_router.PriorityRouter._send_immediate')
    def test_p0_routes_to_immediate(self, mock_send_immediate):
        """P0 findings should route to immediate notification."""
        finding = self._create_mock_finding(priority_bucket="P0")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("immediate", result)
        mock_send_immediate.assert_called_once()

    @patch('dojo.finding.priority_router.PriorityRouter._send_immediate')
    def test_p1_routes_to_immediate(self, mock_send_immediate):
        """P1 findings should route to immediate notification."""
        finding = self._create_mock_finding(priority_bucket="P1")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("immediate", result)
        mock_send_immediate.assert_called_once()

    @patch('dojo.finding.priority_router.PriorityRouter._queue_standard')
    def test_p2_routes_to_standard(self, mock_queue_standard):
        """P2 findings should route to standard (delayed) notification."""
        finding = self._create_mock_finding(priority_bucket="P2")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("queued_standard", result)
        mock_queue_standard.assert_called_once()

    @patch('dojo.finding.priority_router.PriorityRouter._add_to_daily_digest')
    def test_p3_routes_to_daily_digest(self, mock_add_to_daily):
        """P3 findings should route to daily digest."""
        finding = self._create_mock_finding(priority_bucket="P3")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("queued_daily", result)
        mock_add_to_daily.assert_called_once()

    @patch('dojo.finding.priority_router.PriorityRouter._add_to_weekly_digest')
    def test_p4_routes_to_weekly_digest(self, mock_add_to_weekly):
        """P4 findings should route to weekly digest."""
        finding = self._create_mock_finding(priority_bucket="P4")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("queued_weekly", result)
        mock_add_to_weekly.assert_called_once()

    @patch('dojo.finding.priority_router.PriorityRouter._add_to_weekly_digest')
    def test_unknown_bucket_routes_to_weekly(self, mock_add_to_weekly):
        """Unknown priority bucket should default to weekly digest."""
        finding = self._create_mock_finding(priority_bucket="UNKNOWN")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("queued_weekly", result)
        mock_add_to_weekly.assert_called_once()

    @patch('dojo.finding.priority_router.PriorityRouter._add_to_daily_digest')
    def test_none_bucket_defaults_to_p3(self, mock_add_to_daily):
        """None priority bucket should default to P3 (daily digest)."""
        finding = self._create_mock_finding(priority_bucket=None)
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("queued_daily", result)
        mock_add_to_daily.assert_called_once()


class TestPriorityRouterSuppression(TestCase):
    """Test notification suppression logic."""

    def setUp(self):
        self.settings_patcher = patch('dojo.finding.priority_router.settings')
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.NOTIFICATION_SUPPRESS_AUTO_ACCEPTED = True

    def tearDown(self):
        self.settings_patcher.stop()

    def _create_mock_finding(self, triage_state="pending", priority_bucket="P0"):
        """Create a mock Finding with specified triage state."""
        from dojo.models import Finding
        finding = MagicMock(spec=Finding)
        finding.id = 1
        finding.title = "Test Finding"
        finding.severity = "High"
        finding.priority_bucket = priority_bucket
        finding.priority_score = 500
        finding.triage_state = triage_state
        finding.active = True

        finding.test = MagicMock()
        finding.test.engagement = MagicMock()
        finding.test.engagement.product = MagicMock()
        finding.test.engagement.product.name = "Test Product"

        return finding

    def test_accepted_finding_suppressed(self):
        """Findings with triage_state='accepted' should be suppressed."""
        finding = self._create_mock_finding(triage_state="accepted")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("suppressed", result)

    def test_dismissed_finding_suppressed(self):
        """Findings with triage_state='dismissed' should be suppressed."""
        finding = self._create_mock_finding(triage_state="dismissed")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("suppressed", result)

    @patch('dojo.finding.priority_router.PriorityRouter._send_immediate')
    def test_pending_finding_not_suppressed(self, mock_send_immediate):
        """Findings with triage_state='pending' should NOT be suppressed."""
        finding = self._create_mock_finding(triage_state="pending")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("immediate", result)
        mock_send_immediate.assert_called_once()

    @patch('dojo.finding.priority_router.PriorityRouter._send_immediate')
    def test_escalated_finding_not_suppressed(self, mock_send_immediate):
        """Findings with triage_state='escalated' should NOT be suppressed."""
        finding = self._create_mock_finding(triage_state="escalated")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("immediate", result)
        mock_send_immediate.assert_called_once()

    @patch('dojo.finding.priority_router.PriorityRouter._send_immediate')
    def test_assigned_finding_not_suppressed(self, mock_send_immediate):
        """Findings with triage_state='assigned' should NOT be suppressed."""
        finding = self._create_mock_finding(triage_state="assigned")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("immediate", result)
        mock_send_immediate.assert_called_once()

    @patch('dojo.finding.priority_router.PriorityRouter._send_immediate')
    def test_suppression_disabled_allows_accepted(self, mock_send_immediate):
        """When suppression is disabled, accepted findings should send notifications."""
        self.mock_settings.NOTIFICATION_SUPPRESS_AUTO_ACCEPTED = False

        finding = self._create_mock_finding(triage_state="accepted")
        router = PriorityRouter()

        result = router.route_finding_notification(finding)

        self.assertEqual("immediate", result)
        mock_send_immediate.assert_called_once()


class TestPriorityRouterDigestQueuing(TestCase):
    """Test digest queue operations."""

    def setUp(self):
        self.settings_patcher = patch('dojo.finding.priority_router.settings')
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.NOTIFICATION_SUPPRESS_AUTO_ACCEPTED = True

    def tearDown(self):
        self.settings_patcher.stop()

    def _create_mock_finding(self, priority_bucket="P3"):
        """Create a mock Finding."""
        from dojo.models import Finding
        finding = MagicMock(spec=Finding)
        finding.id = 1
        finding.title = "Test Finding"
        finding.severity = "Medium"
        finding.priority_bucket = priority_bucket
        finding.priority_score = 75
        finding.triage_state = "pending"
        finding.active = True

        finding.test = MagicMock()
        finding.test.engagement = MagicMock()
        finding.test.engagement.product = MagicMock()
        finding.test.engagement.product.name = "Test Product"

        return finding

    @patch('dojo.models.PriorityDigestQueue')
    def test_standard_queue_creates_entry(self, mock_queue_class):
        """_queue_standard should create a PriorityDigestQueue entry."""
        finding = self._create_mock_finding(priority_bucket="P2")
        router = PriorityRouter()
        router._queue_standard(finding)

        mock_queue_class.objects.create.assert_called_once_with(
            finding=finding,
            digest_type="standard",
        )

    @patch('dojo.models.PriorityDigestQueue')
    @patch('django.db.IntegrityError', Exception)
    def test_standard_queue_handles_duplicate(self, mock_queue_class):
        """_queue_standard should handle IntegrityError for duplicate entries."""
        from django.db import IntegrityError
        mock_queue_class.objects.create.side_effect = IntegrityError("duplicate")

        finding = self._create_mock_finding(priority_bucket="P2")
        router = PriorityRouter()
        # Should not raise - handles IntegrityError gracefully
        router._queue_standard(finding)

        mock_queue_class.objects.create.assert_called_once()

    @patch('dojo.models.PriorityDigestQueue')
    def test_daily_digest_queue_creates_entry(self, mock_queue_class):
        """_add_to_daily_digest should create a PriorityDigestQueue entry."""
        finding = self._create_mock_finding(priority_bucket="P3")
        router = PriorityRouter()
        router._add_to_daily_digest(finding)

        mock_queue_class.objects.create.assert_called_once_with(
            finding=finding,
            digest_type="daily",
        )

    @patch('dojo.models.PriorityDigestQueue')
    def test_weekly_digest_queue_creates_entry(self, mock_queue_class):
        """_add_to_weekly_digest should create a PriorityDigestQueue entry."""
        finding = self._create_mock_finding(priority_bucket="P4")
        router = PriorityRouter()
        router._add_to_weekly_digest(finding)

        mock_queue_class.objects.create.assert_called_once_with(
            finding=finding,
            digest_type="weekly",
        )


class TestPriorityRouterImmediateNotification(TestCase):
    """Test immediate notification sending."""

    def setUp(self):
        self.settings_patcher = patch('dojo.finding.priority_router.settings')
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.NOTIFICATION_SUPPRESS_AUTO_ACCEPTED = True

    def tearDown(self):
        self.settings_patcher.stop()

    def _create_mock_finding(self, priority_bucket="P0", severity="Critical"):
        """Create a mock Finding."""
        from dojo.models import Finding
        finding = MagicMock(spec=Finding)
        finding.id = 1
        finding.title = "Critical Vulnerability"
        finding.severity = severity
        finding.priority_bucket = priority_bucket
        finding.priority_score = 600
        finding.triage_state = "pending"
        finding.active = True

        finding.test = MagicMock()
        finding.test.engagement = MagicMock()
        finding.test.engagement.product = MagicMock()
        finding.test.engagement.product.name = "Test Product"

        return finding

    @patch('dojo.notifications.helper.create_notification')
    @patch('django.urls.reverse')
    def test_immediate_sends_correct_event(self, mock_reverse, mock_create_notification):
        """_send_immediate should send priority_alert_immediate event."""
        mock_reverse.return_value = "/finding/1"

        finding = self._create_mock_finding()
        router = PriorityRouter()
        router._send_immediate(finding, "P0")

        mock_create_notification.assert_called_once()
        call_kwargs = mock_create_notification.call_args.kwargs
        self.assertEqual("priority_alert_immediate", call_kwargs.get("event"))
        self.assertEqual("P0", call_kwargs.get("priority_bucket"))

    @patch('dojo.notifications.helper.create_notification')
    @patch('django.urls.reverse')
    def test_immediate_includes_finding_details(self, mock_reverse, mock_create_notification):
        """_send_immediate should include finding and URL in notification."""
        mock_reverse.return_value = "/finding/1"

        finding = self._create_mock_finding()
        router = PriorityRouter()
        router._send_immediate(finding, "P0")

        call_kwargs = mock_create_notification.call_args.kwargs
        self.assertEqual(finding, call_kwargs.get("finding"))
        self.assertIn("/finding/1", call_kwargs.get("url"))


class TestPriorityRouterConvenienceFunction(TestCase):
    """Test route_finding_notification convenience function."""

    def setUp(self):
        self.settings_patcher = patch('dojo.finding.priority_router.settings')
        self.mock_settings = self.settings_patcher.start()
        self.mock_settings.NOTIFICATION_SUPPRESS_AUTO_ACCEPTED = True

    def tearDown(self):
        self.settings_patcher.stop()

    @patch('dojo.finding.priority_router.PriorityRouter.route_finding_notification')
    def test_convenience_function_calls_router(self, mock_route):
        """route_finding_notification should create router and call method."""
        from dojo.models import Finding
        finding = MagicMock(spec=Finding)
        mock_route.return_value = "immediate"

        result = route_finding_notification(finding, event="test_event", extra_arg="value")

        mock_route.assert_called_once_with(finding, "test_event", extra_arg="value")
        self.assertEqual("immediate", result)


class TestPriorityRouterDigestPreview(TestCase):
    """Test digest preview functionality."""

    def setUp(self):
        self.settings_patcher = patch('dojo.finding.priority_router.settings')
        self.mock_settings = self.settings_patcher.start()

    def tearDown(self):
        self.settings_patcher.stop()

    @patch('dojo.models.PriorityDigestQueue')
    def test_get_digest_preview_returns_summary(self, mock_queue_class):
        """get_digest_preview should return findings summary."""
        # Create mock findings
        mock_finding1 = MagicMock()
        mock_finding1.id = 1
        mock_finding1.title = "Finding 1"
        mock_finding1.severity = "High"
        mock_finding1.priority_bucket = "P3"
        mock_finding1.active = True

        mock_finding2 = MagicMock()
        mock_finding2.id = 2
        mock_finding2.title = "Finding 2"
        mock_finding2.severity = "Medium"
        mock_finding2.priority_bucket = "P3"
        mock_finding2.active = True

        # Create mock queue items
        mock_item1 = MagicMock()
        mock_item1.finding = mock_finding1
        mock_item2 = MagicMock()
        mock_item2.finding = mock_finding2

        mock_queue_class.objects.filter.return_value.select_related.return_value.order_by.return_value.__getitem__.return_value = [mock_item1, mock_item2]

        router = PriorityRouter()
        preview = router.get_digest_preview("daily")

        self.assertEqual("daily", preview["digest_type"])
        self.assertEqual(2, preview["total_count"])
        self.assertIn("High", preview["severity_counts"])
        self.assertIn("Medium", preview["severity_counts"])
        self.assertEqual(2, len(preview["sample_findings"]))
