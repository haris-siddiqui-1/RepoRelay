"""
Unit tests for Triage Workflow (Phase 2 of Vulnerability Prioritization Strategy)

Tests cover:
- State transition validation
- Triage service operations
- TriageHistory audit trail creation
- AutoTriageEngine integration
- REST API endpoints
"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from dojo.finding.triage_service import (
    ACTION_TO_STATE,
    VALID_TRANSITIONS,
    bulk_triage,
    get_new_state,
    get_valid_actions,
    is_valid_transition,
    perform_auto_triage,
    perform_triage_action,
    validate_triage_action,
)
from dojo.models import (
    Dojo_User,
    Engagement,
    Finding,
    Product,
    Product_Type,
    Test,
    Test_Type,
    TriageHistory,
)

User = get_user_model()


class TriageStateTransitionValidationTests(TestCase):
    """Test state transition validation logic."""

    def test_valid_transitions_from_pending(self):
        """Test all valid transitions from 'pending' state."""
        self.assertTrue(is_valid_transition('pending', 'escalate'))
        self.assertTrue(is_valid_transition('pending', 'assign'))
        self.assertTrue(is_valid_transition('pending', 'defer'))
        self.assertTrue(is_valid_transition('pending', 'accept'))
        self.assertTrue(is_valid_transition('pending', 'dismiss'))

    def test_invalid_transitions_from_pending(self):
        """Test invalid transitions from 'pending' state."""
        self.assertFalse(is_valid_transition('pending', 'reopen'))

    def test_valid_transitions_from_escalated(self):
        """Test transitions from 'escalated' state."""
        self.assertTrue(is_valid_transition('escalated', 'assign'))
        self.assertFalse(is_valid_transition('escalated', 'escalate'))
        self.assertFalse(is_valid_transition('escalated', 'dismiss'))

    def test_valid_transitions_from_assigned(self):
        """Test transitions from 'assigned' state."""
        self.assertTrue(is_valid_transition('assigned', 'defer'))
        self.assertTrue(is_valid_transition('assigned', 'accept'))
        self.assertTrue(is_valid_transition('assigned', 'dismiss'))
        self.assertFalse(is_valid_transition('assigned', 'escalate'))

    def test_valid_transitions_from_deferred(self):
        """Test transitions from 'deferred' state."""
        self.assertTrue(is_valid_transition('deferred', 'reopen'))
        self.assertTrue(is_valid_transition('deferred', 'assign'))
        self.assertFalse(is_valid_transition('deferred', 'escalate'))

    def test_valid_transitions_from_dismissed(self):
        """Test transitions from 'dismissed' state."""
        self.assertTrue(is_valid_transition('dismissed', 'reopen'))
        self.assertFalse(is_valid_transition('dismissed', 'escalate'))
        self.assertFalse(is_valid_transition('dismissed', 'assign'))

    def test_valid_transitions_from_accepted(self):
        """Test transitions from 'accepted' state."""
        self.assertTrue(is_valid_transition('accepted', 'reopen'))
        self.assertFalse(is_valid_transition('accepted', 'escalate'))
        self.assertFalse(is_valid_transition('accepted', 'dismiss'))

    def test_get_valid_actions(self):
        """Test getting valid actions for each state."""
        self.assertEqual(
            set(get_valid_actions('pending')),
            {'escalate', 'assign', 'defer', 'accept', 'dismiss'}
        )
        self.assertEqual(set(get_valid_actions('escalated')), {'assign'})
        self.assertEqual(
            set(get_valid_actions('assigned')),
            {'defer', 'accept', 'dismiss'}
        )
        self.assertEqual(set(get_valid_actions('deferred')), {'reopen', 'assign'})
        self.assertEqual(set(get_valid_actions('dismissed')), {'reopen'})
        self.assertEqual(set(get_valid_actions('accepted')), {'reopen'})

    def test_get_new_state(self):
        """Test action to state mapping."""
        self.assertEqual(get_new_state('escalate'), 'escalated')
        self.assertEqual(get_new_state('assign'), 'assigned')
        self.assertEqual(get_new_state('defer'), 'deferred')
        self.assertEqual(get_new_state('accept'), 'accepted')
        self.assertEqual(get_new_state('dismiss'), 'dismissed')
        self.assertEqual(get_new_state('reopen'), 'pending')

    def test_get_new_state_invalid_action(self):
        """Test that invalid action raises ValidationError."""
        with self.assertRaises(ValidationError):
            get_new_state('invalid_action')


class TriageServiceTests(TestCase):
    """Test triage service operations."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = Dojo_User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        cls.assignee = Dojo_User.objects.create_user(
            username='assignee',
            email='assignee@example.com',
            password='testpass123'
        )
        cls.product_type = Product_Type.objects.create(name='Test Product Type')
        cls.product = Product.objects.create(
            name='Test Product',
            prod_type=cls.product_type
        )
        cls.engagement = Engagement.objects.create(
            name='Test Engagement',
            product=cls.product,
            target_start=date.today(),
            target_end=date.today() + timedelta(days=30)
        )
        cls.test_type = Test_Type.objects.create(name='Test Type')
        cls.test = Test.objects.create(
            engagement=cls.engagement,
            test_type=cls.test_type,
            target_start=timezone.now(),
            target_end=timezone.now() + timedelta(hours=1)
        )

    def create_finding(self, triage_state='pending', **kwargs):
        """Helper to create a finding."""
        return Finding.objects.create(
            title=kwargs.get('title', 'Test Finding'),
            severity=kwargs.get('severity', 'High'),
            test=self.test,
            triage_state=triage_state,
            **{k: v for k, v in kwargs.items() if k not in ['title', 'severity']}
        )

    def test_validate_triage_action_valid(self):
        """Test validation passes for valid action."""
        finding = self.create_finding(triage_state='pending')
        # Should not raise
        validate_triage_action(finding, 'escalate')

    def test_validate_triage_action_invalid_action(self):
        """Test validation fails for invalid action."""
        finding = self.create_finding()
        with self.assertRaises(ValidationError):
            validate_triage_action(finding, 'invalid_action')

    def test_validate_triage_action_invalid_transition(self):
        """Test validation fails for invalid transition."""
        finding = self.create_finding(triage_state='dismissed')
        with self.assertRaises(ValidationError):
            validate_triage_action(finding, 'dismiss')  # Can't dismiss from dismissed

    def test_validate_triage_action_requires_reason(self):
        """Test validation requires reason for accept/dismiss."""
        finding = self.create_finding()
        with self.assertRaises(ValidationError) as ctx:
            validate_triage_action(finding, 'accept')
        self.assertIn('Reason is required', str(ctx.exception))

        with self.assertRaises(ValidationError) as ctx:
            validate_triage_action(finding, 'dismiss')
        self.assertIn('Reason is required', str(ctx.exception))

    def test_validate_triage_action_requires_assigned_to(self):
        """Test validation requires assigned_to for assign action."""
        finding = self.create_finding()
        with self.assertRaises(ValidationError) as ctx:
            validate_triage_action(finding, 'assign')
        self.assertIn('assigned_to is required', str(ctx.exception))

    def test_perform_triage_action_escalate(self):
        """Test performing escalate action."""
        finding = self.create_finding()

        result = perform_triage_action(
            finding=finding,
            action='escalate',
            user=self.user
        )

        finding.refresh_from_db()
        self.assertEqual(finding.triage_state, 'escalated')

        # Check history record was created
        history = TriageHistory.objects.filter(finding=finding).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.action, 'escalate')
        self.assertEqual(history.previous_state, 'pending')
        self.assertEqual(history.new_state, 'escalated')
        self.assertEqual(history.performed_by, self.user)

    def test_perform_triage_action_assign(self):
        """Test performing assign action."""
        finding = self.create_finding()

        perform_triage_action(
            finding=finding,
            action='assign',
            user=self.user,
            assigned_to=self.assignee
        )

        finding.refresh_from_db()
        self.assertEqual(finding.triage_state, 'assigned')
        self.assertEqual(finding.triage_assigned_to, self.assignee)

    def test_perform_triage_action_accept_with_reason(self):
        """Test performing accept action with reason."""
        finding = self.create_finding()

        perform_triage_action(
            finding=finding,
            action='accept',
            user=self.user,
            reason='Accepted because of low business impact'
        )

        finding.refresh_from_db()
        self.assertEqual(finding.triage_state, 'accepted')
        self.assertEqual(finding.triage_reason, 'Accepted because of low business impact')

    def test_perform_triage_action_dismiss_with_reason(self):
        """Test performing dismiss action with reason."""
        finding = self.create_finding()

        perform_triage_action(
            finding=finding,
            action='dismiss',
            user=self.user,
            reason='False positive - scanner error'
        )

        finding.refresh_from_db()
        self.assertEqual(finding.triage_state, 'dismissed')
        self.assertEqual(finding.triage_reason, 'False positive - scanner error')

    def test_perform_triage_action_defer_with_due_date(self):
        """Test performing defer action with due date."""
        finding = self.create_finding()
        due_date = date.today() + timedelta(days=30)

        perform_triage_action(
            finding=finding,
            action='defer',
            user=self.user,
            due_date=due_date
        )

        finding.refresh_from_db()
        self.assertEqual(finding.triage_state, 'deferred')
        self.assertEqual(finding.triage_due_date, due_date)

    def test_perform_triage_action_reopen(self):
        """Test performing reopen action clears assignment."""
        finding = self.create_finding(triage_state='dismissed')
        finding.triage_assigned_to = self.assignee
        finding.triage_due_date = date.today()
        finding.save()

        perform_triage_action(
            finding=finding,
            action='reopen',
            user=self.user
        )

        finding.refresh_from_db()
        self.assertEqual(finding.triage_state, 'pending')
        self.assertIsNone(finding.triage_assigned_to)
        self.assertIsNone(finding.triage_due_date)


class TriageHistoryTests(TestCase):
    """Test TriageHistory model and creation."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = Dojo_User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        cls.product_type = Product_Type.objects.create(name='Test Product Type')
        cls.product = Product.objects.create(
            name='Test Product',
            prod_type=cls.product_type
        )
        cls.engagement = Engagement.objects.create(
            name='Test Engagement',
            product=cls.product,
            target_start=date.today(),
            target_end=date.today() + timedelta(days=30)
        )
        cls.test_type = Test_Type.objects.create(name='Test Type')
        cls.test = Test.objects.create(
            engagement=cls.engagement,
            test_type=cls.test_type,
            target_start=timezone.now(),
            target_end=timezone.now() + timedelta(hours=1)
        )

    def test_triage_history_created_on_action(self):
        """Test that TriageHistory record is created when action performed."""
        finding = Finding.objects.create(
            title='Test Finding',
            severity='High',
            test=self.test,
            triage_state='pending'
        )

        perform_triage_action(
            finding=finding,
            action='escalate',
            user=self.user
        )

        history = TriageHistory.objects.filter(finding=finding)
        self.assertEqual(history.count(), 1)

        record = history.first()
        self.assertEqual(record.action, 'escalate')
        self.assertEqual(record.previous_state, 'pending')
        self.assertEqual(record.new_state, 'escalated')
        self.assertEqual(record.performed_by, self.user)
        self.assertIsNotNone(record.performed_at)

    def test_triage_history_ordering(self):
        """Test that history is ordered by performed_at descending."""
        finding = Finding.objects.create(
            title='Test Finding',
            severity='High',
            test=self.test,
            triage_state='pending'
        )

        # Perform multiple actions
        perform_triage_action(finding=finding, action='escalate', user=self.user)
        perform_triage_action(finding=finding, action='assign', user=self.user, assigned_to=self.user)
        perform_triage_action(finding=finding, action='dismiss', user=self.user, reason='Test dismiss')

        history = list(TriageHistory.objects.filter(finding=finding))
        self.assertEqual(len(history), 3)
        # Most recent first
        self.assertEqual(history[0].new_state, 'dismissed')
        self.assertEqual(history[1].new_state, 'assigned')
        self.assertEqual(history[2].new_state, 'escalated')


class AutoTriageIntegrationTests(TestCase):
    """Test AutoTriageEngine integration with new workflow fields."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.product_type = Product_Type.objects.create(name='Test Product Type')
        cls.product = Product.objects.create(
            name='Test Product',
            prod_type=cls.product_type
        )
        cls.engagement = Engagement.objects.create(
            name='Test Engagement',
            product=cls.product,
            target_start=date.today(),
            target_end=date.today() + timedelta(days=30)
        )
        cls.test_type = Test_Type.objects.create(name='Test Type')
        cls.test = Test.objects.create(
            engagement=cls.engagement,
            test_type=cls.test_type,
            target_start=timezone.now(),
            target_end=timezone.now() + timedelta(hours=1)
        )

    def test_perform_auto_triage_dismiss(self):
        """Test auto-triage DISMISS updates new fields."""
        finding = Finding.objects.create(
            title='Test Finding',
            severity='Low',
            test=self.test,
            triage_state='pending'
        )

        perform_auto_triage(
            finding=finding,
            decision='DISMISS',
            rule_name='dismiss_low_epss',
            reason='Very low exploitation probability',
            confidence=85
        )

        finding.refresh_from_db()
        self.assertEqual(finding.triage_state, 'dismissed')
        self.assertEqual(finding.auto_triage_rule, 'dismiss_low_epss')
        self.assertEqual(finding.auto_triage_confidence, 85)
        self.assertEqual(finding.triage_reason, 'Very low exploitation probability')

        # Check history record
        history = TriageHistory.objects.filter(finding=finding).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.action, 'auto_triaged')
        self.assertEqual(history.rule_name, 'dismiss_low_epss')
        self.assertEqual(history.confidence, 85)
        self.assertIsNone(history.performed_by)  # System action

    def test_perform_auto_triage_escalate(self):
        """Test auto-triage ESCALATE updates new fields."""
        finding = Finding.objects.create(
            title='Test Finding',
            severity='Critical',
            test=self.test,
            triage_state='pending'
        )

        perform_auto_triage(
            finding=finding,
            decision='ESCALATE',
            rule_name='critical_high_epss_tier1',
            reason='Critical severity with high EPSS in Tier 1',
            confidence=95
        )

        finding.refresh_from_db()
        self.assertEqual(finding.triage_state, 'escalated')
        self.assertEqual(finding.auto_triage_rule, 'critical_high_epss_tier1')
        self.assertEqual(finding.auto_triage_confidence, 95)

    def test_perform_auto_triage_accept_risk(self):
        """Test auto-triage ACCEPT_RISK updates new fields."""
        finding = Finding.objects.create(
            title='Test Finding',
            severity='Medium',
            test=self.test,
            triage_state='pending'
        )

        perform_auto_triage(
            finding=finding,
            decision='ACCEPT_RISK',
            rule_name='accept_archived_repo',
            reason='Finding in archived repository',
            confidence=95
        )

        finding.refresh_from_db()
        self.assertEqual(finding.triage_state, 'accepted')

    def test_perform_auto_triage_skips_unchanged(self):
        """Test auto-triage skips if state unchanged."""
        finding = Finding.objects.create(
            title='Test Finding',
            severity='High',
            test=self.test,
            triage_state='dismissed'
        )

        # Try to dismiss an already dismissed finding
        perform_auto_triage(
            finding=finding,
            decision='DISMISS',
            rule_name='test_rule',
            reason='Test reason',
            confidence=80
        )

        # Should not create history record
        self.assertEqual(TriageHistory.objects.filter(finding=finding).count(), 0)


class BulkTriageTests(TestCase):
    """Test bulk triage operations."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = Dojo_User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        cls.assignee = Dojo_User.objects.create_user(
            username='assignee',
            email='assignee@example.com',
            password='testpass123'
        )
        cls.product_type = Product_Type.objects.create(name='Test Product Type')
        cls.product = Product.objects.create(
            name='Test Product',
            prod_type=cls.product_type
        )
        cls.engagement = Engagement.objects.create(
            name='Test Engagement',
            product=cls.product,
            target_start=date.today(),
            target_end=date.today() + timedelta(days=30)
        )
        cls.test_type = Test_Type.objects.create(name='Test Type')
        cls.test = Test.objects.create(
            engagement=cls.engagement,
            test_type=cls.test_type,
            target_start=timezone.now(),
            target_end=timezone.now() + timedelta(hours=1)
        )

    def create_findings(self, count, triage_state='pending'):
        """Helper to create multiple findings."""
        findings = []
        for i in range(count):
            finding = Finding.objects.create(
                title=f'Test Finding {i}',
                severity='High',
                test=self.test,
                triage_state=triage_state
            )
            findings.append(finding)
        return findings

    def test_bulk_triage_success(self):
        """Test bulk triage with all success."""
        findings = self.create_findings(3)
        finding_ids = [f.id for f in findings]

        result = bulk_triage(
            finding_ids=finding_ids,
            action='escalate',
            user=self.user
        )

        self.assertEqual(result['success_count'], 3)
        self.assertEqual(result['error_count'], 0)

        # Verify all findings updated
        for finding in findings:
            finding.refresh_from_db()
            self.assertEqual(finding.triage_state, 'escalated')

    def test_bulk_triage_partial_failure(self):
        """Test bulk triage with some failures."""
        pending_findings = self.create_findings(2, triage_state='pending')
        dismissed_findings = self.create_findings(1, triage_state='dismissed')

        all_ids = [f.id for f in pending_findings + dismissed_findings]

        # Try to escalate - dismissed findings can't be escalated
        result = bulk_triage(
            finding_ids=all_ids,
            action='escalate',
            user=self.user
        )

        self.assertEqual(result['success_count'], 2)
        self.assertEqual(result['error_count'], 1)
        self.assertEqual(len(result['errors']), 1)

    def test_bulk_triage_missing_findings(self):
        """Test bulk triage with non-existent finding IDs."""
        findings = self.create_findings(2)
        finding_ids = [f.id for f in findings] + [99999, 99998]  # Non-existent IDs

        result = bulk_triage(
            finding_ids=finding_ids,
            action='escalate',
            user=self.user
        )

        self.assertEqual(result['success_count'], 2)
        self.assertEqual(result['error_count'], 2)  # Two missing

    def test_bulk_triage_invalid_action(self):
        """Test bulk triage with invalid action."""
        findings = self.create_findings(2)
        finding_ids = [f.id for f in findings]

        result = bulk_triage(
            finding_ids=finding_ids,
            action='invalid_action',
            user=self.user
        )

        self.assertEqual(result['success_count'], 0)
        self.assertEqual(result['error_count'], 2)

    def test_bulk_triage_assign_without_assignee(self):
        """Test bulk assign fails without assignee."""
        findings = self.create_findings(2)
        finding_ids = [f.id for f in findings]

        result = bulk_triage(
            finding_ids=finding_ids,
            action='assign',
            user=self.user
            # Missing assigned_to
        )

        self.assertEqual(result['success_count'], 0)
        self.assertEqual(result['error_count'], 2)


class TriageWorkflowFieldsTests(TestCase):
    """Test Finding model triage workflow fields."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data."""
        cls.user = Dojo_User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        cls.product_type = Product_Type.objects.create(name='Test Product Type')
        cls.product = Product.objects.create(
            name='Test Product',
            prod_type=cls.product_type
        )
        cls.engagement = Engagement.objects.create(
            name='Test Engagement',
            product=cls.product,
            target_start=date.today(),
            target_end=date.today() + timedelta(days=30)
        )
        cls.test_type = Test_Type.objects.create(name='Test Type')
        cls.test = Test.objects.create(
            engagement=cls.engagement,
            test_type=cls.test_type,
            target_start=timezone.now(),
            target_end=timezone.now() + timedelta(hours=1)
        )

    def test_finding_default_triage_state(self):
        """Test that new findings default to 'pending' triage state."""
        finding = Finding.objects.create(
            title='Test Finding',
            severity='High',
            test=self.test
        )
        self.assertEqual(finding.triage_state, 'pending')

    def test_finding_triage_assigned_to(self):
        """Test triage_assigned_to field."""
        finding = Finding.objects.create(
            title='Test Finding',
            severity='High',
            test=self.test,
            triage_assigned_to=self.user
        )
        self.assertEqual(finding.triage_assigned_to, self.user)

    def test_finding_triage_due_date(self):
        """Test triage_due_date field."""
        due_date = date.today() + timedelta(days=14)
        finding = Finding.objects.create(
            title='Test Finding',
            severity='High',
            test=self.test,
            triage_due_date=due_date
        )
        self.assertEqual(finding.triage_due_date, due_date)

    def test_finding_auto_triage_fields(self):
        """Test auto_triage_rule and auto_triage_confidence fields."""
        finding = Finding.objects.create(
            title='Test Finding',
            severity='High',
            test=self.test,
            auto_triage_rule='test_rule',
            auto_triage_confidence=85
        )
        self.assertEqual(finding.auto_triage_rule, 'test_rule')
        self.assertEqual(finding.auto_triage_confidence, 85)

    def test_triage_state_choices(self):
        """Test all triage_state choices are valid."""
        valid_states = ['pending', 'escalated', 'assigned', 'deferred', 'accepted', 'dismissed']

        for state in valid_states:
            finding = Finding.objects.create(
                title=f'Test Finding {state}',
                severity='High',
                test=self.test,
                triage_state=state
            )
            self.assertEqual(finding.triage_state, state)
