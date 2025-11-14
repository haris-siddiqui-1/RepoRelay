"""
Unit tests for GitHub Alerts Collector

Tests the alerts collection service including:
- Dependabot alerts sync
- CodeQL alerts sync
- Secret Scanning alerts sync
- Incremental sync logic
- Rate limit handling
- Error handling
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from datetime import UTC

from django.test import TestCase
from django.utils import timezone

from dojo.models import Product, Product_Type, Repository, GitHubAlert, GitHubAlertSync
from dojo.github_collector.alerts_collector import GitHubAlertsCollector, SyncResult


class TestGitHubAlertsCollector(TestCase):
    """Test cases for GitHubAlertsCollector"""

    def setUp(self):
        """Set up test fixtures"""
        self.prod_type = Product_Type.objects.create(name="Test Product Type")
        self.product = Product.objects.create(
            name="Test Product",
            description="Test Description",
            prod_type=self.prod_type,
        )
        self.repository = Repository.objects.create(
            name="test-org/test-repo",
            github_repo_id=123456789,
            github_url="https://github.com/test-org/test-repo",
            product=self.product,
        )

        # Mock GitHub token
        self.mock_token = "ghp_test_token_1234567890"

    @patch('dojo.github_collector.alerts_collector.GitHubGraphQLClient')
    @patch('dojo.github_collector.alerts_collector.GitHubRestClient')
    def test_collector_initialization(self, mock_rest_client, mock_graphql_client):
        """Test collector initializes with both clients"""
        collector = GitHubAlertsCollector(self.mock_token)

        self.assertIsNotNone(collector.graphql_client)
        self.assertIsNotNone(collector.rest_client)
        mock_graphql_client.assert_called_once_with(self.mock_token)
        mock_rest_client.assert_called_once_with(self.mock_token)

    @patch('dojo.github_collector.alerts_collector.GitHubGraphQLClient')
    @patch('dojo.github_collector.alerts_collector.GitHubRestClient')
    def test_sync_repository_alerts_success(self, mock_rest_client, mock_graphql_client):
        """Test successful sync of all alert types"""
        # Mock GraphQL client for Dependabot alerts
        mock_graphql = MagicMock()
        mock_graphql.get_dependabot_alerts.return_value = [
            {
                "github_alert_id": "1",
                "alert_type": "dependabot",
                "state": "open",
                "severity": "high",
                "title": "Vulnerability in package",
                "description": "Test vulnerability",
                "html_url": "https://github.com/test-org/test-repo/security/dependabot/1",
                "cve": "CVE-2024-1234",
                "package_name": "test-package",
                "created_at": "2024-01-01T00:00:00Z",
                "raw_data": {}
            }
        ]
        mock_graphql_client.return_value = mock_graphql

        # Mock REST client for CodeQL and Secret Scanning
        mock_rest = MagicMock()
        mock_rest.get_codeql_alerts.return_value = [
            {
                "github_alert_id": "2",
                "alert_type": "codeql",
                "state": "open",
                "severity": "medium",
                "title": "SQL Injection",
                "description": "Potential SQL injection",
                "html_url": "https://github.com/test-org/test-repo/security/code-scanning/2",
                "cwe": "CWE-89",
                "rule_id": "sql-injection",
                "file_path": "/app/views.py",
                "created_at": "2024-01-01T00:00:00Z",
                "raw_data": {}
            }
        ]
        mock_rest.get_secret_scanning_alerts.return_value = [
            {
                "github_alert_id": "3",
                "alert_type": "secret_scanning",
                "state": "open",
                "severity": "high",
                "title": "API Key detected",
                "description": "API key found in code",
                "html_url": "https://github.com/test-org/test-repo/security/secret-scanning/3",
                "secret_type": "api_key",
                "created_at": "2024-01-01T00:00:00Z",
                "raw_data": {}
            }
        ]
        mock_rest_client.return_value = mock_rest

        # Run sync
        collector = GitHubAlertsCollector(self.mock_token)
        result = collector.sync_repository_alerts(self.repository, force=True)

        # Verify result
        self.assertTrue(result.success)
        self.assertEqual(result.dependabot_count, 1)
        self.assertEqual(result.codeql_count, 1)
        self.assertEqual(result.secret_scanning_count, 1)
        self.assertEqual(result.total_alerts, 3)
        self.assertEqual(len(result.errors), 0)

        # Verify alerts were created
        self.assertEqual(GitHubAlert.objects.filter(repository=self.repository).count(), 3)

        # Verify sync tracker was updated
        sync_tracker = GitHubAlertSync.objects.get(repository=self.repository)
        self.assertIsNotNone(sync_tracker.dependabot_last_sync)
        self.assertIsNotNone(sync_tracker.codeql_last_sync)
        self.assertIsNotNone(sync_tracker.secret_scanning_last_sync)
        self.assertTrue(sync_tracker.full_sync_completed)
        self.assertEqual(sync_tracker.dependabot_alerts_fetched, 1)
        self.assertEqual(sync_tracker.codeql_alerts_fetched, 1)
        self.assertEqual(sync_tracker.secret_scanning_alerts_fetched, 1)

        # Verify repository alert counts were updated
        self.repository.refresh_from_db()
        self.assertEqual(self.repository.dependabot_alert_count, 1)
        self.assertEqual(self.repository.codeql_alert_count, 1)
        self.assertEqual(self.repository.secret_scanning_alert_count, 1)

    @patch('dojo.github_collector.alerts_collector.GitHubGraphQLClient')
    @patch('dojo.github_collector.alerts_collector.GitHubRestClient')
    def test_sync_skips_recently_synced_repo(self, mock_rest_client, mock_graphql_client):
        """Test that sync skips repositories synced within minimum interval"""
        # Create sync tracker with recent sync
        GitHubAlertSync.objects.create(
            repository=self.repository,
            dependabot_last_sync=timezone.now() - timedelta(minutes=30),  # 30 mins ago
            codeql_last_sync=timezone.now() - timedelta(minutes=30),
            secret_scanning_last_sync=timezone.now() - timedelta(minutes=30),
        )

        collector = GitHubAlertsCollector(self.mock_token)
        result = collector.sync_repository_alerts(self.repository, force=False)

        # Should not call any API methods
        mock_graphql_client.return_value.get_dependabot_alerts.assert_not_called()
        mock_rest_client.return_value.get_codeql_alerts.assert_not_called()
        mock_rest_client.return_value.get_secret_scanning_alerts.assert_not_called()

    @patch('dojo.github_collector.alerts_collector.GitHubGraphQLClient')
    @patch('dojo.github_collector.alerts_collector.GitHubRestClient')
    def test_sync_with_force_ignores_interval(self, mock_rest_client, mock_graphql_client):
        """Test that force=True syncs regardless of last sync time"""
        # Create sync tracker with recent sync
        GitHubAlertSync.objects.create(
            repository=self.repository,
            dependabot_last_sync=timezone.now() - timedelta(minutes=30),
        )

        # Mock clients
        mock_graphql_client.return_value.get_dependabot_alerts.return_value = []
        mock_rest_client.return_value.get_codeql_alerts.return_value = []
        mock_rest_client.return_value.get_secret_scanning_alerts.return_value = []

        collector = GitHubAlertsCollector(self.mock_token)
        result = collector.sync_repository_alerts(self.repository, force=True)

        # Should call API methods even with recent sync
        mock_graphql_client.return_value.get_dependabot_alerts.assert_called_once()
        mock_rest_client.return_value.get_codeql_alerts.assert_called_once()
        mock_rest_client.return_value.get_secret_scanning_alerts.assert_called_once()

    @patch('dojo.github_collector.alerts_collector.GitHubGraphQLClient')
    @patch('dojo.github_collector.alerts_collector.GitHubRestClient')
    def test_alert_update_on_resync(self, mock_rest_client, mock_graphql_client):
        """Test that existing alerts are updated on resync"""
        # Create existing alert
        existing_alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type=GitHubAlert.DEPENDABOT,
            github_alert_id="1",
            state="open",
            severity="high",
            title="Old Title",
            html_url="https://github.com/test-org/test-repo/security/dependabot/1",
        )

        # Mock updated alert data
        mock_graphql = MagicMock()
        mock_graphql.get_dependabot_alerts.return_value = [
            {
                "github_alert_id": "1",
                "alert_type": "dependabot",
                "state": "fixed",  # State changed
                "severity": "high",
                "title": "Updated Title",  # Title changed
                "description": "Updated description",
                "html_url": "https://github.com/test-org/test-repo/security/dependabot/1",
                "cve": "CVE-2024-1234",
                "package_name": "test-package",
                "created_at": "2024-01-01T00:00:00Z",
                "fixed_at": "2024-01-15T00:00:00Z",
                "raw_data": {}
            }
        ]
        mock_graphql_client.return_value = mock_graphql
        mock_rest_client.return_value.get_codeql_alerts.return_value = []
        mock_rest_client.return_value.get_secret_scanning_alerts.return_value = []

        # Run sync
        collector = GitHubAlertsCollector(self.mock_token)
        result = collector.sync_repository_alerts(self.repository, force=True)

        # Verify alert was updated (not created new)
        self.assertEqual(GitHubAlert.objects.filter(repository=self.repository).count(), 1)

        # Verify updates
        existing_alert.refresh_from_db()
        self.assertEqual(existing_alert.state, "fixed")
        self.assertEqual(existing_alert.title, "Updated Title")
        self.assertIsNotNone(existing_alert.fixed_at)

    @patch('dojo.github_collector.alerts_collector.GitHubGraphQLClient')
    @patch('dojo.github_collector.alerts_collector.GitHubRestClient')
    def test_sync_handles_api_errors(self, mock_rest_client, mock_graphql_client):
        """Test error handling when API calls fail"""
        # Mock GraphQL client to raise exception
        mock_graphql = MagicMock()
        mock_graphql.get_dependabot_alerts.side_effect = Exception("API Error")
        mock_graphql_client.return_value = mock_graphql

        collector = GitHubAlertsCollector(self.mock_token)
        result = collector.sync_repository_alerts(self.repository, force=True)

        # Verify error was recorded
        self.assertFalse(result.success)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("API Error", result.errors[0])

        # Verify sync tracker has error
        sync_tracker = GitHubAlertSync.objects.get(repository=self.repository)
        self.assertIsNotNone(sync_tracker.last_sync_error)
        self.assertIsNotNone(sync_tracker.last_sync_error_at)

    def test_parse_repository_identifier_from_url(self):
        """Test parsing owner/name from GitHub URL"""
        collector = GitHubAlertsCollector(self.mock_token)
        owner, name = collector._parse_repository_identifier(self.repository)

        self.assertEqual(owner, "test-org")
        self.assertEqual(name, "test-repo")

    def test_parse_repository_identifier_from_name(self):
        """Test parsing owner/name from repository name"""
        repository = Repository.objects.create(
            name="another-org/another-repo",
            github_repo_id=987654321,
            github_url="",  # Empty URL
            product=self.product,
        )

        collector = GitHubAlertsCollector(self.mock_token)
        owner, name = collector._parse_repository_identifier(repository)

        self.assertEqual(owner, "another-org")
        self.assertEqual(name, "another-repo")

    def test_should_sync_new_repository(self):
        """Test that new repositories without sync history should sync"""
        collector = GitHubAlertsCollector(self.mock_token)
        should_sync = collector._should_sync(self.repository)

        self.assertTrue(should_sync)

    def test_should_sync_old_sync(self):
        """Test that repositories with old sync should sync"""
        GitHubAlertSync.objects.create(
            repository=self.repository,
            dependabot_last_sync=timezone.now() - timedelta(hours=2),  # 2 hours ago
        )

        collector = GitHubAlertsCollector(self.mock_token)
        should_sync = collector._should_sync(self.repository)

        self.assertTrue(should_sync)

    def test_should_not_sync_recent(self):
        """Test that repositories with recent sync should not sync"""
        GitHubAlertSync.objects.create(
            repository=self.repository,
            dependabot_last_sync=timezone.now() - timedelta(minutes=30),  # 30 mins ago
        )

        collector = GitHubAlertsCollector(self.mock_token)
        should_sync = collector._should_sync(self.repository)

        self.assertFalse(should_sync)

    def test_sync_result_total_alerts(self):
        """Test SyncResult total_alerts property"""
        result = SyncResult(
            repository_id=1,
            repository_name="test-repo",
            dependabot_count=5,
            codeql_count=3,
            secret_scanning_count=2
        )

        self.assertEqual(result.total_alerts, 10)

    def test_get_repositories_for_sync_filters_correctly(self):
        """Test that _get_repositories_for_sync returns correct repos"""
        # Create multiple repositories
        repo1 = Repository.objects.create(
            name="repo1",
            github_repo_id=111,
            github_url="https://github.com/org/repo1",
            product=self.product,
            last_alert_sync=timezone.now() - timedelta(hours=2),  # Old sync
        )

        repo2 = Repository.objects.create(
            name="repo2",
            github_repo_id=222,
            github_url="https://github.com/org/repo2",
            product=self.product,
            last_alert_sync=timezone.now() - timedelta(minutes=30),  # Recent sync
        )

        repo3 = Repository.objects.create(
            name="repo3",
            github_repo_id=333,
            github_url="https://github.com/org/repo3",
            product=self.product,
            last_alert_sync=None,  # Never synced
        )

        collector = GitHubAlertsCollector(self.mock_token)
        repos = collector._get_repositories_for_sync(force=False)

        # Should include repo1 (old sync) and repo3 (no sync)
        # Should exclude repo2 (recent sync)
        self.assertIn(repo1, repos)
        self.assertNotIn(repo2, repos)
        self.assertIn(repo3, repos)

    def test_get_repositories_for_sync_with_force(self):
        """Test that force=True includes all repositories"""
        repo1 = Repository.objects.create(
            name="repo1",
            github_repo_id=111,
            github_url="https://github.com/org/repo1",
            product=self.product,
            last_alert_sync=timezone.now() - timedelta(minutes=10),
        )

        collector = GitHubAlertsCollector(self.mock_token)
        repos = collector._get_repositories_for_sync(force=True)

        # Force should include even recently synced repos
        self.assertIn(repo1, repos)

    def test_get_repositories_for_sync_with_limit(self):
        """Test that limit parameter works"""
        # Create 5 repositories
        for i in range(5):
            Repository.objects.create(
                name=f"repo{i}",
                github_repo_id=100 + i,
                github_url=f"https://github.com/org/repo{i}",
                product=self.product,
            )

        collector = GitHubAlertsCollector(self.mock_token)
        repos = collector._get_repositories_for_sync(force=True, limit=3)

        # Should return only 3 repositories
        self.assertEqual(len(repos), 3)
