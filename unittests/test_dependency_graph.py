"""
Unit tests for DependencyGraphBuilder - Phase 4 of Vulnerability Prioritization Strategy

Tests the DependencyGraphBuilder class which:
- Fetches SBOM from GitHub API
- Extracts dependencies and matches to internal repos
- Updates consumption signal fields on Repository model
- Calculates tier overrides based on consumption thresholds
"""

from unittest.mock import MagicMock, patch, PropertyMock

from django.test import TestCase

from dojo.github_collector.dependency_graph import DependencyGraphBuilder


class TestDependencyGraphBuilderSBOMParsing(TestCase):
    """Test SBOM parsing and dependency extraction."""

    def setUp(self):
        # Mock settings to avoid requiring actual token
        self.patcher = patch('dojo.github_collector.dependency_graph.settings')
        self.mock_settings = self.patcher.start()
        self.mock_settings.DD_GITHUB_TOKEN = 'test-token'

    def tearDown(self):
        self.patcher.stop()

    def test_extract_npm_package_from_purl(self):
        """Test extraction of npm package names from PURL format."""
        builder = DependencyGraphBuilder(github_token='test-token')

        sbom_data = {
            'sbom': {
                'packages': [
                    {'name': 'pkg:npm/lodash@4.17.21'},
                    {'name': 'pkg:npm/@org/my-lib@1.0.0'},
                    {'name': 'pkg:npm/express@4.18.2'},
                ]
            }
        }

        dependencies = builder.extract_dependencies_from_sbom(sbom_data)

        self.assertIn('lodash', dependencies)
        self.assertIn('my-lib', dependencies)
        self.assertIn('express', dependencies)

    def test_extract_pypi_package_from_purl(self):
        """Test extraction of PyPI package names from PURL format."""
        builder = DependencyGraphBuilder(github_token='test-token')

        sbom_data = {
            'sbom': {
                'packages': [
                    {'name': 'pkg:pypi/django@5.1.0'},
                    {'name': 'pkg:pypi/requests@2.31.0'},
                ]
            }
        }

        dependencies = builder.extract_dependencies_from_sbom(sbom_data)

        self.assertIn('django', dependencies)
        self.assertIn('requests', dependencies)

    def test_extract_maven_package_from_purl(self):
        """Test extraction of Maven package names from PURL format."""
        builder = DependencyGraphBuilder(github_token='test-token')

        sbom_data = {
            'sbom': {
                'packages': [
                    {'name': 'pkg:maven/org.apache.commons/commons-lang3@3.12.0'},
                    {'name': 'pkg:maven/com.google.guava/guava@31.1-jre'},
                ]
            }
        }

        dependencies = builder.extract_dependencies_from_sbom(sbom_data)

        self.assertIn('commons-lang3', dependencies)
        self.assertIn('guava', dependencies)

    def test_extract_github_reference_from_purl(self):
        """Test extraction of GitHub repo references from PURL format."""
        builder = DependencyGraphBuilder(github_token='test-token')

        sbom_data = {
            'sbom': {
                'packages': [
                    {'name': 'pkg:github/myorg/internal-lib'},
                    {'name': 'pkg:github/myorg/shared-utils'},
                ]
            }
        }

        dependencies = builder.extract_dependencies_from_sbom(sbom_data)

        self.assertIn('internal-lib', dependencies)
        self.assertIn('shared-utils', dependencies)

    def test_empty_sbom_returns_empty_list(self):
        """Test that empty SBOM returns empty dependency list."""
        builder = DependencyGraphBuilder(github_token='test-token')

        sbom_data = {'sbom': {'packages': []}}

        dependencies = builder.extract_dependencies_from_sbom(sbom_data)

        self.assertEqual([], dependencies)

    def test_missing_sbom_key_returns_empty_list(self):
        """Test that missing sbom key returns empty dependency list."""
        builder = DependencyGraphBuilder(github_token='test-token')

        sbom_data = {}

        dependencies = builder.extract_dependencies_from_sbom(sbom_data)

        self.assertEqual([], dependencies)


class TestDependencyGraphBuilderTierOverride(TestCase):
    """Test tier override calculation based on consumption thresholds."""

    def setUp(self):
        self.patcher = patch('dojo.github_collector.dependency_graph.settings')
        self.mock_settings = self.patcher.start()
        self.mock_settings.DD_GITHUB_TOKEN = 'test-token'

    def tearDown(self):
        self.patcher.stop()

    def test_50_plus_consumers_override_to_tier1(self):
        """50+ consumers should override to tier1."""
        builder = DependencyGraphBuilder(github_token='test-token')

        override = builder._calculate_tier_override(50, "tier4")

        self.assertEqual("tier1", override)

    def test_51_consumers_override_to_tier1(self):
        """51 consumers should override to tier1."""
        builder = DependencyGraphBuilder(github_token='test-token')

        override = builder._calculate_tier_override(51, "archived")

        self.assertEqual("tier1", override)

    def test_20_to_49_consumers_override_to_tier2(self):
        """20-49 consumers should override to tier2."""
        builder = DependencyGraphBuilder(github_token='test-token')

        override = builder._calculate_tier_override(20, "tier4")

        self.assertEqual("tier2", override)

    def test_49_consumers_override_to_tier2(self):
        """49 consumers should override to tier2."""
        builder = DependencyGraphBuilder(github_token='test-token')

        override = builder._calculate_tier_override(49, "archived")

        self.assertEqual("tier2", override)

    def test_5_to_19_consumers_promotes_one_tier(self):
        """5-19 consumers should promote one tier level."""
        builder = DependencyGraphBuilder(github_token='test-token')

        # tier4 -> tier3
        override = builder._calculate_tier_override(5, "tier4")
        self.assertEqual("tier3", override)

        # tier3 -> tier2
        override = builder._calculate_tier_override(10, "tier3")
        self.assertEqual("tier2", override)

        # archived -> tier4
        override = builder._calculate_tier_override(15, "archived")
        self.assertEqual("tier4", override)

    def test_tier1_stays_tier1_when_promoted(self):
        """tier1 should stay tier1 when 5-19 consumers (already highest)."""
        builder = DependencyGraphBuilder(github_token='test-token')

        override = builder._calculate_tier_override(10, "tier1")

        self.assertEqual("tier1", override)

    def test_less_than_5_consumers_no_override(self):
        """<5 consumers should return None (no override)."""
        builder = DependencyGraphBuilder(github_token='test-token')

        override = builder._calculate_tier_override(4, "tier4")

        self.assertIsNone(override)

    def test_zero_consumers_no_override(self):
        """0 consumers should return None (no override)."""
        builder = DependencyGraphBuilder(github_token='test-token')

        override = builder._calculate_tier_override(0, "tier4")

        self.assertIsNone(override)


class TestDependencyGraphBuilderRepoMatching(TestCase):
    """Test internal repository matching logic."""

    def setUp(self):
        self.patcher = patch('dojo.github_collector.dependency_graph.settings')
        self.mock_settings = self.patcher.start()
        self.mock_settings.DD_GITHUB_TOKEN = 'test-token'

    def tearDown(self):
        self.patcher.stop()

    def test_exact_match_returns_repo_name(self):
        """Exact package name match should return repo name."""
        builder = DependencyGraphBuilder(github_token='test-token')
        builder._internal_repos = {'my-service', 'auth-lib', 'utils'}

        match = builder._match_to_internal_repo('my-service')

        self.assertEqual('my-service', match)

    def test_case_insensitive_match(self):
        """Matching should be case insensitive."""
        builder = DependencyGraphBuilder(github_token='test-token')
        builder._internal_repos = {'my-service', 'auth-lib', 'utils'}

        match = builder._match_to_internal_repo('MY-SERVICE')

        self.assertEqual('my-service', match)

    def test_prefix_match_returns_repo_name(self):
        """Package starting with repo name should match."""
        builder = DependencyGraphBuilder(github_token='test-token')
        builder._internal_repos = {'my-service'}

        match = builder._match_to_internal_repo('my-service-client')

        self.assertEqual('my-service', match)

    def test_contains_match_returns_repo_name(self):
        """Package containing repo name should match."""
        builder = DependencyGraphBuilder(github_token='test-token')
        builder._internal_repos = {'auth'}

        match = builder._match_to_internal_repo('@myorg/auth-utils')

        self.assertEqual('auth', match)

    def test_no_match_returns_none(self):
        """No matching repo should return None."""
        builder = DependencyGraphBuilder(github_token='test-token')
        builder._internal_repos = {'my-service', 'auth-lib'}

        match = builder._match_to_internal_repo('lodash')

        self.assertIsNone(match)


class TestPriorityScorerConsumptionTierOverride(TestCase):
    """Test PriorityScorer with consumption tier override."""

    def setUp(self):
        from dojo.finding.priority_scorer import PriorityScorer
        self.scorer = PriorityScorer()

    def test_consumption_tier_override_takes_precedence(self):
        """consumption_tier_override should take precedence over base tier."""
        finding = self._create_mock_finding(severity="Critical")
        # Repo has archived base tier but tier1 consumption override
        repository = self._create_mock_repository(
            tier="archived",
            consumption_tier_override="tier1"
        )

        score = self.scorer.calculate(finding, repository)

        # Should use tier1 weight (5.0), not archived (0.2)
        # 5.0 × 100 = 500, no prod signals: -30 = 470
        # The key assertion is that score is much higher than archived would give
        # Archived would be: 0.2 × 100 - 30 = -10 (floored to 0)
        self.assertEqual(470, score)

    def test_no_consumption_override_uses_base_tier(self):
        """Without consumption_tier_override, should use base tier."""
        finding = self._create_mock_finding(severity="Critical")
        repository = self._create_mock_repository(
            tier="archived",
            consumption_tier_override=None
        )

        score = self.scorer.calculate(finding, repository)

        # Should use archived weight (0.2)
        # 0.2 × 100 = 20 (plus modifiers)
        self.assertLess(score, 100)

    def test_high_consumption_modifier_adds_50_points(self):
        """50+ dependent repos should add 50 modifier points."""
        finding = self._create_mock_finding(severity="Medium")
        repository = self._create_mock_repository(
            tier="tier4",
            dependent_repo_count=50
        )

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50
        # High consumption: +50
        # No prod signals: -30
        # Expected: 50 + 50 - 30 = 70
        self.assertEqual(70, score)

    def test_medium_consumption_modifier_adds_30_points(self):
        """20-49 dependent repos should add 30 modifier points."""
        finding = self._create_mock_finding(severity="Medium")
        repository = self._create_mock_repository(
            tier="tier4",
            dependent_repo_count=25
        )

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50
        # Medium consumption: +30
        # No prod signals: -30
        # Expected: 50 + 30 - 30 = 50
        self.assertEqual(50, score)

    def test_shared_library_modifier_adds_20_points(self):
        """is_shared_library=True should add 20 modifier points."""
        finding = self._create_mock_finding(severity="Medium")
        repository = self._create_mock_repository(
            tier="tier4",
            dependent_repo_count=7,  # Above 5 but below 20
            is_shared_library=True
        )

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50
        # Shared library: +20
        # No prod signals: -30
        # Expected: 50 + 20 - 30 = 40
        self.assertEqual(40, score)

    def test_no_consumption_signals_no_modifier(self):
        """<5 dependent repos should not add consumption modifier."""
        finding = self._create_mock_finding(severity="Medium")
        repository = self._create_mock_repository(
            tier="tier4",
            dependent_repo_count=2,
            is_shared_library=False
        )

        score = self.scorer.calculate(finding, repository)

        # Base: 1.0 × 50 = 50
        # No consumption modifier
        # No prod signals: -30
        # Expected: 50 - 30 = 20
        self.assertEqual(20, score)

    def _create_mock_finding(self, severity="Medium", **kwargs):
        """Create a mock Finding with specified attributes."""
        from dojo.models import Finding
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
        from dojo.models import Repository
        repo = MagicMock(spec=Repository)
        repo.tier = tier
        repo.consumption_tier_override = kwargs.get("consumption_tier_override", None)
        repo.dependent_repo_count = kwargs.get("dependent_repo_count", 0)
        repo.is_shared_library = kwargs.get("is_shared_library", False)
        repo.has_environments = kwargs.get("has_environments", False)
        repo.has_releases = kwargs.get("has_releases", False)
        repo.active_webhooks_count = kwargs.get("active_webhooks_count", 0)
        repo.days_since_last_commit = kwargs.get("days_since_last_commit", 0)
        return repo
