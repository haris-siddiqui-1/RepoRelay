import datetime
from datetime import UTC
from unittest import skip

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from dojo.models import Product, Product_Type, Repository


class TestRepositoryModel(TestCase):
    """Test cases for the Repository model"""

    def setUp(self):
        """Set up test fixtures"""
        self.prod_type = Product_Type.objects.create(name="Test Product Type")
        self.product = Product.objects.create(
            name="Test Product",
            description="Test Description",
            prod_type=self.prod_type,
        )

    def test_empty(self):
        """Test creating an empty Repository instance"""
        repository = Repository()
        # CharField defaults to empty string, not None
        self.assertEqual(repository.name, '')
        self.assertIsNone(repository.github_repo_id)
        # URLField defaults to empty string, not None
        self.assertEqual(repository.github_url, '')
        self.assertIsNone(repository.product_id)

    def test_create_basic_repository(self):
        """Test creating a basic Repository with required fields"""
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
        )
        self.assertEqual(repository.name, "test-repo")
        self.assertEqual(repository.github_repo_id, 123456789)
        self.assertEqual(repository.github_url, "https://github.com/org/test-repo")
        self.assertEqual(repository.product, self.product)
        self.assertEqual(repository.tier, "tier4")  # Default tier
        self.assertEqual(repository.total_alert_count, 0)  # No alerts by default

    def test_repository_str(self):
        """Test Repository __str__ method"""
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
        )
        self.assertEqual(str(repository), "test-repo")

    @skip("URL routing will be implemented in Phase 2-4")
    def test_repository_get_absolute_url(self):
        """Test Repository get_absolute_url method"""
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
        )
        expected_url = f"/repository/{repository.id}"
        self.assertEqual(repository.get_absolute_url(), expected_url)

    def test_tier_choices(self):
        """Test Repository tier classification choices"""
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
            tier=Repository.TIER1,
        )
        self.assertEqual(repository.tier, "tier1")

        repository.tier = Repository.TIER2
        repository.save()
        self.assertEqual(repository.tier, "tier2")

        repository.tier = Repository.ARCHIVED
        repository.save()
        self.assertEqual(repository.tier, "archived")

    def test_total_alert_count_property(self):
        """Test total_alert_count property calculation"""
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
            dependabot_alert_count=5,
            codeql_alert_count=3,
            secret_scanning_alert_count=2,
        )
        self.assertEqual(repository.total_alert_count, 10)

    def test_binary_signals_defaults(self):
        """Test that all binary signal fields default to False"""
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
        )

        # Deployment Indicators
        self.assertFalse(repository.has_dockerfile)
        self.assertFalse(repository.has_kubernetes_config)
        self.assertFalse(repository.has_ci_cd)
        self.assertFalse(repository.has_terraform)
        self.assertFalse(repository.has_deployment_scripts)
        self.assertFalse(repository.has_procfile)

        # Production Readiness
        self.assertFalse(repository.has_environments)
        self.assertFalse(repository.has_releases)
        self.assertFalse(repository.has_branch_protection)
        self.assertFalse(repository.has_monitoring_config)
        self.assertFalse(repository.has_ssl_config)
        self.assertFalse(repository.has_database_migrations)

        # Active Development
        self.assertFalse(repository.recent_commits_30d)
        self.assertFalse(repository.active_prs_30d)
        self.assertFalse(repository.multiple_contributors)
        self.assertFalse(repository.has_dependabot_activity)
        self.assertFalse(repository.recent_releases_90d)
        self.assertFalse(repository.consistent_commit_pattern)

        # Code Organization
        self.assertFalse(repository.has_tests)
        self.assertFalse(repository.has_documentation)
        self.assertFalse(repository.has_api_specs)
        self.assertFalse(repository.has_codeowners)
        self.assertFalse(repository.has_security_md)
        self.assertFalse(repository.is_monorepo)

        # Security Maturity
        self.assertFalse(repository.has_security_scanning)
        self.assertFalse(repository.has_secret_scanning)
        self.assertFalse(repository.has_dependency_scanning)
        self.assertFalse(repository.has_gitleaks_config)
        self.assertFalse(repository.has_sast_config)

    def test_activity_tracking_fields(self):
        """Test repository activity tracking fields"""
        last_commit = datetime.datetime(2025, 1, 1, tzinfo=UTC)
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
            last_commit_date=last_commit,
            active_contributors_90d=5,
            days_since_last_commit=10,
        )
        self.assertEqual(repository.last_commit_date, last_commit)
        self.assertEqual(repository.active_contributors_90d, 5)
        self.assertEqual(repository.days_since_last_commit, 10)

    def test_repository_metadata_fields(self):
        """Test repository metadata fields"""
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
            readme_summary="This is a test repository",
            readme_length=500,
            primary_language="Python",
            primary_framework="Django",
        )
        self.assertEqual(repository.readme_summary, "This is a test repository")
        self.assertEqual(repository.readme_length, 500)
        self.assertEqual(repository.primary_language, "Python")
        self.assertEqual(repository.primary_framework, "Django")

    def test_ownership_tracking_fields(self):
        """Test repository ownership tracking fields"""
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
            codeowners_content="* @team-lead\n/docs/ @doc-team",
            ownership_confidence=85,
        )
        self.assertEqual(repository.codeowners_content, "* @team-lead\n/docs/ @doc-team")
        self.assertEqual(repository.ownership_confidence, 85)

    def test_ownership_confidence_validation(self):
        """Test ownership_confidence field validation (0-100)"""
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
            ownership_confidence=0,
        )
        repository.full_clean()  # Should not raise

        repository.ownership_confidence = 100
        repository.full_clean()  # Should not raise

        repository.ownership_confidence = -1
        with self.assertRaises(ValidationError):
            repository.full_clean()

        repository.ownership_confidence = 101
        with self.assertRaises(ValidationError):
            repository.full_clean()

    def test_related_products(self):
        """Test ManyToMany related_products field"""
        product2 = Product.objects.create(
            name="Related Product",
            description="Related Description",
            prod_type=self.prod_type,
        )

        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
        )

        repository.related_products.add(product2)
        self.assertEqual(repository.related_products.count(), 1)
        self.assertIn(product2, repository.related_products.all())

    def test_cached_finding_counts(self):
        """Test cached_finding_counts JSONField"""
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
            cached_finding_counts={
                "critical": 5,
                "high": 10,
                "medium": 20,
                "low": 30,
            },
        )
        self.assertEqual(repository.cached_finding_counts["critical"], 5)
        self.assertEqual(repository.cached_finding_counts["high"], 10)

    def test_github_alerts_fields(self):
        """Test GitHub alerts tracking fields"""
        last_sync = datetime.datetime(2025, 1, 1, tzinfo=UTC)
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
            last_alert_sync=last_sync,
            dependabot_alert_count=10,
            codeql_alert_count=5,
            secret_scanning_alert_count=2,
        )
        self.assertEqual(repository.last_alert_sync, last_sync)
        self.assertEqual(repository.dependabot_alert_count, 10)
        self.assertEqual(repository.codeql_alert_count, 5)
        self.assertEqual(repository.secret_scanning_alert_count, 2)

    def test_unique_github_repo_id(self):
        """Test github_repo_id uniqueness constraint"""
        Repository.objects.create(
            name="test-repo-1",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo-1",
            product=self.product,
        )

        # Attempting to create another repository with the same github_repo_id should fail
        with self.assertRaises(Exception):  # IntegrityError
            Repository.objects.create(
                name="test-repo-2",
                github_repo_id=123456789,
                github_url="https://github.com/org/test-repo-2",
                product=self.product,
            )

    def test_repository_ordering(self):
        """Test Repository default ordering by name"""
        Repository.objects.create(
            name="zebra-repo",
            github_repo_id=111,
            github_url="https://github.com/org/zebra-repo",
            product=self.product,
        )
        Repository.objects.create(
            name="alpha-repo",
            github_repo_id=222,
            github_url="https://github.com/org/alpha-repo",
            product=self.product,
        )
        Repository.objects.create(
            name="middle-repo",
            github_repo_id=333,
            github_url="https://github.com/org/middle-repo",
            product=self.product,
        )

        repositories = list(Repository.objects.all())
        self.assertEqual(repositories[0].name, "alpha-repo")
        self.assertEqual(repositories[1].name, "middle-repo")
        self.assertEqual(repositories[2].name, "zebra-repo")

    def test_repository_indexes(self):
        """Test that Repository model has expected indexes"""
        # This test verifies the Meta.indexes are defined correctly
        from django.db import connection
        with connection.cursor() as cursor:
            # Get table name
            table_name = Repository._meta.db_table
            # Check that indexes exist (this is database-specific)
            # For PostgreSQL, we can query pg_indexes
            if connection.vendor == 'postgresql':
                cursor.execute(f"""
                    SELECT indexname FROM pg_indexes
                    WHERE tablename = '{table_name}'
                    AND indexname LIKE '%github_repo_id%'
                """)
                indexes = cursor.fetchall()
                self.assertGreater(len(indexes), 0, "github_repo_id index should exist")

    def test_timestamps_auto_now(self):
        """Test that created and updated timestamps work correctly"""
        repository = Repository.objects.create(
            name="test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/org/test-repo",
            product=self.product,
        )

        created_time = repository.created
        updated_time = repository.updated

        self.assertIsNotNone(created_time)
        self.assertIsNotNone(updated_time)

        # Update the repository
        import time
        time.sleep(0.1)  # Ensure time difference
        repository.name = "updated-repo"
        repository.save()

        repository.refresh_from_db()
        self.assertEqual(repository.created, created_time)  # Created should not change
        self.assertGreater(repository.updated, updated_time)  # Updated should change
