"""
Unit tests for Priority Scorer - Phase 1 of Vulnerability Prioritization Strategy

Tests the PriorityScorer class which calculates priority scores based on:
- Repository/Product tier (weight multiplier)
- Finding severity (base score)
- Risk modifiers (KEV, EPSS, SLA breach, etc.)

Formula: PriorityScore = (TierWeight × SeverityScore) + Modifiers
"""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from dojo.finding.priority_scorer import PriorityScorer, get_repository_for_finding
from dojo.models import Engagement, Finding, Product, Repository, Test


class TestPriorityScorerBasicCalculation(TestCase):
    """Test basic priority score calculations."""

    def setUp(self):
        self.scorer = PriorityScorer()

    def test_critical_severity_tier1_base_score(self):
        """Critical severity in tier1 should produce base score of 500."""
        # Tier1 weight: 5.0, Critical: 100
        # 5.0 × 100 = 500
        finding = self._create_mock_finding(severity="Critical")
        repository = self._create_mock_repository(tier="tier1")

        score = self.scorer.calculate(finding, repository)

        self.assertEqual(500, score)

    def test_high_severity_tier2_base_score(self):
        """High severity in tier2 should produce base score of 262."""
        # Tier2 weight: 3.5, High: 75
        # 3.5 × 75 = 262.5 -> 262 (int)
        finding = self._create_mock_finding(severity="High")
        repository = self._create_mock_repository(tier="tier2")

        score = self.scorer.calculate(finding, repository)

        self.assertEqual(262, score)

    def test_medium_severity_tier3_base_score(self):
        """Medium severity in tier3 should produce base score of 100."""
        # Tier3 weight: 2.0, Medium: 50
        # 2.0 × 50 = 100
        finding = self._create_mock_finding(severity="Medium")
        repository = self._create_mock_repository(tier="tier3")

        score = self.scorer.calculate(finding, repository)

        self.assertEqual(100, score)

    def test_low_severity_tier4_base_score(self):
        """Low severity in tier4 should produce base score of 25."""
        # Tier4 weight: 1.0, Low: 25
        # 1.0 × 25 = 25
        finding = self._create_mock_finding(severity="Low")
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        self.assertEqual(25, score)

    def test_info_severity_archived_base_score(self):
        """Info severity in archived repo should produce base score of 2."""
        # Archived weight: 0.2, Info: 10
        # 0.2 × 10 = 2
        finding = self._create_mock_finding(severity="Info")
        repository = self._create_mock_repository(tier="archived")

        score = self.scorer.calculate(finding, repository)

        self.assertEqual(2, score)

    def test_unknown_severity_defaults_to_low(self):
        """Unknown severity should default to Low (25 points)."""
        finding = self._create_mock_finding(severity="Unknown")
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        # 1.0 × 25 = 25
        self.assertEqual(25, score)

    def _create_mock_finding(self, severity="Medium", **kwargs):
        """Create a mock Finding with specified attributes."""
        finding = MagicMock(spec=Finding)
        finding.id = 1
        finding.severity = severity
        finding.known_exploited = kwargs.get("known_exploited", False)
        finding.ransomware_used = kwargs.get("ransomware_used", False)
        finding.epss_score = kwargs.get("epss_score", None)
        finding.fix_available = kwargs.get("fix_available", None)
        finding.sla_expiration_date = kwargs.get("sla_expiration_date", None)

        # Mock the test->engagement->product chain
        finding.test = MagicMock()
        finding.test.engagement = MagicMock()
        finding.test.engagement.product = MagicMock()
        finding.test.engagement.product.business_criticality = kwargs.get("business_criticality", None)

        return finding

    def _create_mock_repository(self, tier="tier4", **kwargs):
        """Create a mock Repository with specified attributes."""
        repo = MagicMock(spec=Repository)
        repo.tier = tier
        repo.has_environments = kwargs.get("has_environments", False)
        repo.has_releases = kwargs.get("has_releases", False)
        repo.active_webhooks_count = kwargs.get("active_webhooks_count", 0)
        repo.days_since_last_commit = kwargs.get("days_since_last_commit", 0)
        return repo


class TestPriorityScorerModifiers(TestCase):
    """Test priority score modifiers."""

    def setUp(self):
        self.scorer = PriorityScorer()

    def test_kev_modifier_adds_150_points(self):
        """KEV (Known Exploited Vulnerability) should add 150 points."""
        finding = self._create_mock_finding(severity="Medium", known_exploited=True)
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, KEV: +150, no prod: -30
        # 50 + 150 - 30 = 170
        self.assertEqual(170, score)

    def test_ransomware_modifier_adds_100_points(self):
        """Ransomware association should add 100 points."""
        finding = self._create_mock_finding(severity="Medium", ransomware_used=True)
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, Ransomware: +100, no prod: -30
        # 50 + 100 - 30 = 120
        self.assertEqual(120, score)

    def test_high_epss_modifier_adds_75_points(self):
        """High EPSS (>=0.7) should add 75 points."""
        finding = self._create_mock_finding(severity="Medium", epss_score=0.85)
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, High EPSS: +75, no prod: -30
        # 50 + 75 - 30 = 95
        self.assertEqual(95, score)

    def test_medium_epss_modifier_adds_40_points(self):
        """Medium EPSS (>=0.3, <0.7) should add 40 points."""
        finding = self._create_mock_finding(severity="Medium", epss_score=0.45)
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, Medium EPSS: +40, no prod: -30
        # 50 + 40 - 30 = 60
        self.assertEqual(60, score)

    def test_very_low_epss_modifier_subtracts_50_points(self):
        """Very low EPSS (<0.02) should subtract 50 points."""
        finding = self._create_mock_finding(severity="Medium", epss_score=0.01)
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, Very low EPSS: -50, no prod: -30
        # 50 - 50 - 30 = -30 -> 0 (floor)
        self.assertEqual(0, score)

    def test_low_epss_modifier_subtracts_25_points(self):
        """Low EPSS (>=0.02, <0.1) should subtract 25 points."""
        finding = self._create_mock_finding(severity="Medium", epss_score=0.05)
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, Low EPSS: -25, no prod: -30
        # 50 - 25 - 30 = -5 -> 0 (floor)
        self.assertEqual(0, score)

    def test_fix_available_adds_30_points(self):
        """Fix available should add 30 points."""
        finding = self._create_mock_finding(severity="Medium", fix_available=True)
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, Fix: +30, no prod: -30
        # 50 + 30 - 30 = 50
        self.assertEqual(50, score)

    def test_no_fix_subtracts_20_points(self):
        """No fix available should subtract 20 points."""
        finding = self._create_mock_finding(severity="Medium", fix_available=False)
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, No fix: -20, no prod: -30
        # 50 - 20 - 30 = 0
        self.assertEqual(0, score)

    def test_sla_breach_adds_50_points(self):
        """SLA breach should add 50 points."""
        yesterday = date.today() - timedelta(days=1)
        finding = self._create_mock_finding(severity="Medium", sla_expiration_date=yesterday)
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, SLA breach: +50, no prod: -30
        # 50 + 50 - 30 = 70
        self.assertEqual(70, score)

    def test_sla_not_breached_no_modifier(self):
        """Non-breached SLA should not add points."""
        tomorrow = date.today() + timedelta(days=1)
        finding = self._create_mock_finding(severity="Medium", sla_expiration_date=tomorrow)
        repository = self._create_mock_repository(tier="tier4")

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, no prod: -30
        # 50 - 30 = 20
        self.assertEqual(20, score)

    def test_production_signals_add_25_points(self):
        """Has environments or releases should add 25 points."""
        finding = self._create_mock_finding(severity="Medium")
        repository = self._create_mock_repository(tier="tier4", has_environments=True)

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, Prod signals: +25
        # 50 + 25 = 75
        self.assertEqual(75, score)

    def test_no_production_signals_subtracts_30_points(self):
        """No environments or releases should subtract 30 points."""
        finding = self._create_mock_finding(severity="Medium")
        repository = self._create_mock_repository(tier="tier4", has_environments=False, has_releases=False)

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, No prod signals: -30
        # 50 - 30 = 20
        self.assertEqual(20, score)

    def test_active_webhooks_add_15_points(self):
        """Active webhooks should add 15 points."""
        finding = self._create_mock_finding(severity="Medium")
        repository = self._create_mock_repository(tier="tier4", active_webhooks_count=3, has_releases=True)

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, Prod signals: +25, Webhooks: +15
        # 50 + 25 + 15 = 90
        self.assertEqual(90, score)

    def test_dormant_repo_subtracts_40_points(self):
        """Dormant repository (>180 days) should subtract 40 points."""
        finding = self._create_mock_finding(severity="Medium")
        repository = self._create_mock_repository(tier="tier4", days_since_last_commit=200, has_releases=True)

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50, Prod signals: +25, Dormant: -40
        # 50 + 25 - 40 = 35
        self.assertEqual(35, score)

    def _create_mock_finding(self, severity="Medium", **kwargs):
        """Create a mock Finding with specified attributes."""
        finding = MagicMock(spec=Finding)
        finding.id = 1
        finding.severity = severity
        finding.known_exploited = kwargs.get("known_exploited", False)
        finding.ransomware_used = kwargs.get("ransomware_used", False)
        finding.epss_score = kwargs.get("epss_score", None)
        finding.fix_available = kwargs.get("fix_available", None)
        finding.sla_expiration_date = kwargs.get("sla_expiration_date", None)

        # Mock the test->engagement->product chain
        finding.test = MagicMock()
        finding.test.engagement = MagicMock()
        finding.test.engagement.product = MagicMock()
        finding.test.engagement.product.business_criticality = kwargs.get("business_criticality", None)

        return finding

    def _create_mock_repository(self, tier="tier4", **kwargs):
        """Create a mock Repository with specified attributes."""
        repo = MagicMock(spec=Repository)
        repo.tier = tier
        repo.has_environments = kwargs.get("has_environments", False)
        repo.has_releases = kwargs.get("has_releases", False)
        repo.active_webhooks_count = kwargs.get("active_webhooks_count", 0)
        repo.days_since_last_commit = kwargs.get("days_since_last_commit", 0)
        return repo


class TestPriorityScorerTierFallback(TestCase):
    """Test tier resolution fallback from repository to product."""

    def setUp(self):
        self.scorer = PriorityScorer()

    def test_uses_repository_tier_when_available(self):
        """Repository tier takes precedence over product criticality."""
        finding = self._create_mock_finding(severity="Critical", business_criticality="low")
        repository = self._create_mock_repository(tier="tier1")

        score = self.scorer.calculate(finding, repository)

        # Should use tier1 (5.0), not low (1.0)
        # 5.0 × 100 = 500, no prod: -30 (from repo) -> wait, repo has no signals
        # Actually let me recalculate: tier1 weight 5.0 × Critical 100 = 500
        # Repo modifiers: no prod signals -30
        # 500 - 30 = 470
        self.assertEqual(470, score)

    def test_falls_back_to_product_criticality(self):
        """Uses product business_criticality when no repository provided."""
        finding = self._create_mock_finding(severity="Critical", business_criticality="very high")

        score = self.scorer.calculate(finding, repository=None)

        # Should use "very high" (5.0)
        # 5.0 × 100 = 500, no repository modifiers
        self.assertEqual(500, score)

    def test_defaults_to_tier4_weight(self):
        """Defaults to tier4 weight (1.0) when no tier info available."""
        finding = self._create_mock_finding(severity="Critical", business_criticality=None)

        score = self.scorer.calculate(finding, repository=None)

        # Should use default weight (1.0)
        # 1.0 × 100 = 100
        self.assertEqual(100, score)

    def _create_mock_finding(self, severity="Medium", **kwargs):
        """Create a mock Finding with specified attributes."""
        finding = MagicMock(spec=Finding)
        finding.id = 1
        finding.severity = severity
        finding.known_exploited = kwargs.get("known_exploited", False)
        finding.ransomware_used = kwargs.get("ransomware_used", False)
        finding.epss_score = kwargs.get("epss_score", None)
        finding.fix_available = kwargs.get("fix_available", None)
        finding.sla_expiration_date = kwargs.get("sla_expiration_date", None)

        # Mock the test->engagement->product chain
        finding.test = MagicMock()
        finding.test.engagement = MagicMock()
        finding.test.engagement.product = MagicMock()
        finding.test.engagement.product.business_criticality = kwargs.get("business_criticality", None)

        return finding

    def _create_mock_repository(self, tier="tier4", **kwargs):
        """Create a mock Repository with specified attributes."""
        repo = MagicMock(spec=Repository)
        repo.tier = tier
        repo.has_environments = kwargs.get("has_environments", False)
        repo.has_releases = kwargs.get("has_releases", False)
        repo.active_webhooks_count = kwargs.get("active_webhooks_count", 0)
        repo.days_since_last_commit = kwargs.get("days_since_last_commit", 0)
        return repo


class TestPriorityBuckets(TestCase):
    """Test priority bucket assignment."""

    def setUp(self):
        self.scorer = PriorityScorer()

    def test_p0_bucket_at_500(self):
        """Score of 500+ should be P0."""
        self.assertEqual("P0", self.scorer.get_bucket(500))
        self.assertEqual("P0", self.scorer.get_bucket(750))
        self.assertEqual("P0", self.scorer.get_bucket(1000))

    def test_p1_bucket_300_to_499(self):
        """Score of 300-499 should be P1."""
        self.assertEqual("P1", self.scorer.get_bucket(300))
        self.assertEqual("P1", self.scorer.get_bucket(400))
        self.assertEqual("P1", self.scorer.get_bucket(499))

    def test_p2_bucket_150_to_299(self):
        """Score of 150-299 should be P2."""
        self.assertEqual("P2", self.scorer.get_bucket(150))
        self.assertEqual("P2", self.scorer.get_bucket(225))
        self.assertEqual("P2", self.scorer.get_bucket(299))

    def test_p3_bucket_50_to_149(self):
        """Score of 50-149 should be P3."""
        self.assertEqual("P3", self.scorer.get_bucket(50))
        self.assertEqual("P3", self.scorer.get_bucket(100))
        self.assertEqual("P3", self.scorer.get_bucket(149))

    def test_p4_bucket_below_50(self):
        """Score below 50 should be P4."""
        self.assertEqual("P4", self.scorer.get_bucket(0))
        self.assertEqual("P4", self.scorer.get_bucket(25))
        self.assertEqual("P4", self.scorer.get_bucket(49))


class TestPriorityScorerEdgeCases(TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        self.scorer = PriorityScorer()

    def test_none_epss_score_ignored(self):
        """None EPSS score should not affect score."""
        finding = self._create_mock_finding(severity="Medium", epss_score=None)

        score = self.scorer.calculate(finding, repository=None)

        # Base: 1.0 × 50 = 50 (no EPSS modifier)
        self.assertEqual(50, score)

    def test_score_floor_at_zero(self):
        """Score should never go below 0."""
        # Low severity in archived repo with negative modifiers
        finding = self._create_mock_finding(
            severity="Info",
            epss_score=0.01,  # -50
            fix_available=False,  # -20
        )
        repository = self._create_mock_repository(
            tier="archived",  # 0.2 weight
            days_since_last_commit=200,  # -40
            has_releases=False,  # -30
        )

        score = self.scorer.calculate(finding, repository)

        # Base: 0.2 × 10 = 2
        # Modifiers: -50 -20 -30 -40 = -140
        # 2 - 140 = -138 -> floor to 0
        self.assertEqual(0, score)

    def test_missing_test_chain_handled(self):
        """Missing test->engagement->product chain should not crash."""
        finding = MagicMock(spec=Finding)
        finding.id = 1
        finding.severity = "Medium"
        finding.known_exploited = False
        finding.ransomware_used = False
        finding.epss_score = None
        finding.fix_available = None
        finding.sla_expiration_date = None
        finding.test = None  # Missing test

        score = self.scorer.calculate(finding, repository=None)

        # Should use default weight (1.0)
        # 1.0 × 50 = 50
        self.assertEqual(50, score)

    def test_calculate_and_get_bucket(self):
        """Test combined score and bucket calculation."""
        finding = self._create_mock_finding(severity="Critical")
        repository = self._create_mock_repository(tier="tier1", has_releases=True)

        score, bucket = self.scorer.calculate_and_get_bucket(finding, repository)

        # Base: 5.0 × 100 = 500, prod signals: +25
        # 500 + 25 = 525 -> P0
        self.assertEqual(525, score)
        self.assertEqual("P0", bucket)

    def _create_mock_finding(self, severity="Medium", **kwargs):
        """Create a mock Finding with specified attributes."""
        finding = MagicMock(spec=Finding)
        finding.id = 1
        finding.severity = severity
        finding.known_exploited = kwargs.get("known_exploited", False)
        finding.ransomware_used = kwargs.get("ransomware_used", False)
        finding.epss_score = kwargs.get("epss_score", None)
        finding.fix_available = kwargs.get("fix_available", None)
        finding.sla_expiration_date = kwargs.get("sla_expiration_date", None)

        # Mock the test->engagement->product chain
        finding.test = MagicMock()
        finding.test.engagement = MagicMock()
        finding.test.engagement.product = MagicMock()
        finding.test.engagement.product.business_criticality = kwargs.get("business_criticality", None)

        return finding

    def _create_mock_repository(self, tier="tier4", **kwargs):
        """Create a mock Repository with specified attributes."""
        repo = MagicMock(spec=Repository)
        repo.tier = tier
        repo.has_environments = kwargs.get("has_environments", False)
        repo.has_releases = kwargs.get("has_releases", False)
        repo.active_webhooks_count = kwargs.get("active_webhooks_count", 0)
        repo.days_since_last_commit = kwargs.get("days_since_last_commit", 0)
        return repo


class TestPriorityScorerRealWorldScenarios(TestCase):
    """Test realistic priority scoring scenarios matching strategy document examples."""

    def setUp(self):
        self.scorer = PriorityScorer()

    def test_kev_in_production_firmware_p0(self):
        """KEV in production firmware should be P0 with high score."""
        # Scenario: Critical KEV in tier1 production system
        finding = self._create_mock_finding(
            severity="Critical",
            known_exploited=True,
            epss_score=0.85,
        )
        repository = self._create_mock_repository(
            tier="tier1",
            has_environments=True,
            has_releases=True,
        )

        score, bucket = self.scorer.calculate_and_get_bucket(finding, repository)

        # Base: 5.0 × 100 = 500
        # KEV: +150, High EPSS: +75, Prod signals: +25
        # 500 + 150 + 75 + 25 = 750
        self.assertEqual(750, score)
        self.assertEqual("P0", bucket)

    def test_high_cve_in_active_service_p1(self):
        """High CVE in active service should be P1."""
        # Scenario: High severity in tier2 with fix available
        finding = self._create_mock_finding(
            severity="High",
            epss_score=0.35,
            fix_available=True,
        )
        repository = self._create_mock_repository(
            tier="tier2",
            has_releases=True,
            active_webhooks_count=2,
        )

        score, bucket = self.scorer.calculate_and_get_bucket(finding, repository)

        # Base: 3.5 × 75 = 262
        # Medium EPSS: +40, Fix: +30, Prod signals: +25, Webhooks: +15
        # 262 + 40 + 30 + 25 + 15 = 372
        self.assertEqual(372, score)
        self.assertEqual("P1", bucket)

    def test_medium_cve_in_dev_repo_p3(self):
        """Medium CVE in dev repo should be P3."""
        # Scenario: Medium severity in tier3 dev environment
        finding = self._create_mock_finding(
            severity="Medium",
            epss_score=0.15,  # Not high or very low, no EPSS modifier
        )
        repository = self._create_mock_repository(
            tier="tier3",
            has_environments=False,
            has_releases=False,
        )

        score, bucket = self.scorer.calculate_and_get_bucket(finding, repository)

        # Base: 2.0 × 50 = 100
        # No EPSS modifier (0.15 is between 0.1 and 0.3)
        # No prod signals: -30
        # 100 - 30 = 70
        self.assertEqual(70, score)
        self.assertEqual("P3", bucket)

    def test_low_cve_in_archived_repo_p4(self):
        """Low CVE in archived repo should be P4."""
        # Scenario: Low severity in archived/dormant repo
        finding = self._create_mock_finding(
            severity="Low",
            epss_score=0.01,  # Very low
            fix_available=False,
        )
        repository = self._create_mock_repository(
            tier="archived",
            has_environments=False,
            has_releases=False,
            days_since_last_commit=365,
        )

        score, bucket = self.scorer.calculate_and_get_bucket(finding, repository)

        # Base: 0.2 × 25 = 5
        # Very low EPSS: -50, No fix: -20, No prod: -30, Dormant: -40
        # 5 - 50 - 20 - 30 - 40 = -135 -> floor to 0
        self.assertEqual(0, score)
        self.assertEqual("P4", bucket)

    def _create_mock_finding(self, severity="Medium", **kwargs):
        """Create a mock Finding with specified attributes."""
        finding = MagicMock(spec=Finding)
        finding.id = 1
        finding.severity = severity
        finding.known_exploited = kwargs.get("known_exploited", False)
        finding.ransomware_used = kwargs.get("ransomware_used", False)
        finding.epss_score = kwargs.get("epss_score", None)
        finding.fix_available = kwargs.get("fix_available", None)
        finding.sla_expiration_date = kwargs.get("sla_expiration_date", None)

        # Mock the test->engagement->product chain
        finding.test = MagicMock()
        finding.test.engagement = MagicMock()
        finding.test.engagement.product = MagicMock()
        finding.test.engagement.product.business_criticality = kwargs.get("business_criticality", None)

        return finding

    def _create_mock_repository(self, tier="tier4", **kwargs):
        """Create a mock Repository with specified attributes."""
        repo = MagicMock(spec=Repository)
        repo.tier = tier
        repo.has_environments = kwargs.get("has_environments", False)
        repo.has_releases = kwargs.get("has_releases", False)
        repo.active_webhooks_count = kwargs.get("active_webhooks_count", 0)
        repo.days_since_last_commit = kwargs.get("days_since_last_commit", 0)
        return repo
