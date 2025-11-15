"""
Unit tests for GitHub Findings Converter.

Tests the conversion of GitHub security alerts (Dependabot, CodeQL, Secret Scanning)
into DefectDojo Finding objects.
"""

from datetime import datetime
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from dojo.github_collector.findings_converter import GitHubFindingsConverter
from dojo.models import (
    Engagement,
    Finding,
    GitHubAlert,
    Product,
    Product_Type,
    Repository,
    Test,
    Test_Type,
    Dojo_User,
)


class TestGitHubFindingsConverter(TestCase):
    """Test cases for GitHubFindingsConverter."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test user
        self.user = Dojo_User.objects.create(
            username='test_user',
            is_superuser=True
        )

        # Create test product hierarchy
        self.product_type = Product_Type.objects.create(
            name='Test Product Type'
        )

        self.product = Product.objects.create(
            name='Test Product',
            prod_type=self.product_type
        )

        # Create test repository
        self.repository = Repository.objects.create(
            name='test-org/test-repo',
            github_repo_id=123456,
            github_url='https://github.com/test-org/test-repo',
            product=self.product
        )

        # Create test types
        self.test_type_dependabot = Test_Type.objects.create(
            name='GitHub Dependabot',
            static_tool=True
        )

        self.test_type_codeql = Test_Type.objects.create(
            name='GitHub CodeQL',
            static_tool=True
        )

        self.test_type_secret = Test_Type.objects.create(
            name='GitHub Secret Scanning',
            static_tool=True
        )

        # Initialize converter
        self.converter = GitHubFindingsConverter()

    def test_severity_mapping(self):
        """Test that GitHub severities are correctly mapped to DefectDojo severities."""
        test_cases = [
            ('critical', 'Critical'),
            ('high', 'High'),
            ('moderate', 'Medium'),
            ('medium', 'Medium'),
            ('low', 'Low'),
            ('warning', 'Low'),
            ('error', 'High'),
            ('note', 'Info'),
            ('info', 'Info'),
            ('unknown', 'Info'),  # Default
            (None, 'Info'),  # Null handling
        ]

        for github_severity, expected_dd_severity in test_cases:
            with self.subTest(github_severity=github_severity):
                result = self.converter._map_severity(github_severity)
                self.assertEqual(result, expected_dd_severity)

    def test_build_unique_id(self):
        """Test unique ID generation for deduplication."""
        alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='dependabot',
            github_alert_id='42',
            state='open',
            severity='high',
            title='Test Alert',
            html_url='https://github.com/test/alert/42'
        )

        unique_id = self.converter._build_unique_id(alert)
        expected = f'github-dependabot-{self.repository.github_repo_id}-42'

        self.assertEqual(unique_id, expected)

    def test_get_or_create_engagement(self):
        """Test engagement creation for GitHub alerts."""
        engagement = self.converter._get_or_create_engagement(self.repository)

        self.assertIsNotNone(engagement)
        self.assertEqual(engagement.product, self.product)
        self.assertIn('GitHub Security Alerts', engagement.name)
        self.assertIn(self.repository.name, engagement.name)
        self.assertTrue(engagement.active)

        # Test idempotency - should return same engagement
        engagement2 = self.converter._get_or_create_engagement(self.repository)
        self.assertEqual(engagement.id, engagement2.id)

    def test_get_or_create_test_dependabot(self):
        """Test Test creation for Dependabot alerts."""
        engagement = self.converter._get_or_create_engagement(self.repository)
        test = self.converter._get_or_create_test(
            self.repository,
            'dependabot',
            engagement
        )

        self.assertIsNotNone(test)
        self.assertEqual(test.test_type, self.test_type_dependabot)
        self.assertEqual(test.engagement, engagement)

        # Test idempotency
        test2 = self.converter._get_or_create_test(
            self.repository,
            'dependabot',
            engagement
        )
        self.assertEqual(test.id, test2.id)

    def test_get_or_create_test_codeql(self):
        """Test Test creation for CodeQL alerts."""
        engagement = self.converter._get_or_create_engagement(self.repository)
        test = self.converter._get_or_create_test(
            self.repository,
            'codeql',
            engagement
        )

        self.assertIsNotNone(test)
        self.assertEqual(test.test_type, self.test_type_codeql)

    def test_convert_dependabot_alert(self):
        """Test conversion of Dependabot alert to Finding fields."""
        alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='dependabot',
            github_alert_id='1',
            state='open',
            severity='critical',
            title='Vulnerability in test-package',
            description='This is a test vulnerability',
            html_url='https://github.com/test/alert/1',
            cve='CVE-2024-1234',
            package_name='test-package',
            package_ecosystem='npm',
            vulnerable_version='1.0.0',
            patched_version='1.0.1',
            created_at=timezone.now()
        )

        engagement = self.converter._get_or_create_engagement(self.repository)
        test = self.converter._get_or_create_test(self.repository, 'dependabot', engagement)

        fields = self.converter._convert_dependabot_alert(alert, test)

        self.assertIn('test-package', fields['title'])
        self.assertEqual(fields['severity'], 'Critical')
        self.assertEqual(fields['cve'], 'CVE-2024-1234')
        self.assertEqual(fields['component_name'], 'test-package')
        self.assertEqual(fields['component_version'], '1.0.0')
        self.assertIn('1.0.1', fields['mitigation'])
        self.assertIn(alert.html_url, fields['references'])
        self.assertEqual(fields['test'], test)
        self.assertIn('github-dependabot', fields['unique_id_from_tool'])

    def test_convert_codeql_alert(self):
        """Test conversion of CodeQL alert to Finding fields."""
        alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='codeql',
            github_alert_id='2',
            state='open',
            severity='high',
            title='SQL Injection',
            description='Potential SQL injection vulnerability',
            html_url='https://github.com/test/alert/2',
            cwe='CWE-89',
            rule_id='js/sql-injection',
            file_path='src/database.js',
            start_line=42,
            end_line=45,
            created_at=timezone.now()
        )

        engagement = self.converter._get_or_create_engagement(self.repository)
        test = self.converter._get_or_create_test(self.repository, 'codeql', engagement)

        fields = self.converter._convert_codeql_alert(alert, test)

        self.assertEqual(fields['title'], 'SQL Injection')
        self.assertEqual(fields['severity'], 'High')
        self.assertEqual(fields['cwe'], 89)  # Parsed from CWE-89
        self.assertEqual(fields['file_path'], 'src/database.js')
        self.assertEqual(fields['line'], 42)
        self.assertIn('js/sql-injection', fields['vuln_id_from_tool'])
        self.assertIn('github-codeql', fields['unique_id_from_tool'])

    def test_convert_secret_scanning_alert(self):
        """Test conversion of Secret Scanning alert to Finding fields."""
        alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='secret_scanning',
            github_alert_id='3',
            state='open',
            severity='critical',
            title='AWS Access Key Exposed',
            description='AWS credentials found in code',
            html_url='https://github.com/test/alert/3',
            secret_type='aws_access_key_id',
            file_path='config/aws.js',
            start_line=10,
            created_at=timezone.now()
        )

        engagement = self.converter._get_or_create_engagement(self.repository)
        test = self.converter._get_or_create_test(self.repository, 'secret_scanning', engagement)

        fields = self.converter._convert_secret_scanning_alert(alert, test)

        self.assertIn('aws_access_key_id', fields['title'])
        self.assertEqual(fields['severity'], 'Critical')  # Secrets always critical
        self.assertEqual(fields['file_path'], 'config/aws.js')
        self.assertEqual(fields['line'], 10)
        self.assertIn('github-secret_scanning', fields['unique_id_from_tool'])

    def test_apply_state_to_finding_open(self):
        """Test applying OPEN state to Finding."""
        alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='dependabot',
            github_alert_id='4',
            state='open',
            severity='high',
            title='Test Alert',
            html_url='https://github.com/test/alert/4'
        )

        finding = Finding()
        self.converter._apply_state_to_finding(finding, alert)

        self.assertTrue(finding.active)
        self.assertFalse(finding.verified)
        self.assertFalse(finding.is_mitigated)
        self.assertIsNone(finding.mitigated)
        self.assertFalse(finding.risk_accepted)
        self.assertFalse(finding.false_p)

    def test_apply_state_to_finding_fixed(self):
        """Test applying FIXED state to Finding."""
        fixed_time = timezone.now()
        alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='dependabot',
            github_alert_id='5',
            state='fixed',
            severity='high',
            title='Test Alert',
            html_url='https://github.com/test/alert/5',
            fixed_at=fixed_time
        )

        finding = Finding()
        self.converter._apply_state_to_finding(finding, alert)

        self.assertFalse(finding.active)
        self.assertTrue(finding.is_mitigated)
        self.assertEqual(finding.mitigated, fixed_time)

    def test_apply_state_to_finding_dismissed(self):
        """Test applying DISMISSED state to Finding."""
        alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='dependabot',
            github_alert_id='6',
            state='dismissed',
            severity='high',
            title='Test Alert',
            html_url='https://github.com/test/alert/6'
        )

        finding = Finding()
        self.converter._apply_state_to_finding(finding, alert)

        self.assertFalse(finding.active)
        self.assertTrue(finding.risk_accepted)

    def test_create_finding_from_alert(self):
        """Test end-to-end finding creation from alert."""
        alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='dependabot',
            github_alert_id='7',
            state='open',
            severity='high',
            title='Test Vulnerability',
            description='Test description',
            html_url='https://github.com/test/alert/7',
            package_name='vulnerable-pkg',
            package_ecosystem='npm',
            vulnerable_version='1.0.0',
            patched_version='2.0.0',
            created_at=timezone.now()
        )

        finding, created = self.converter.create_or_update_finding(alert)

        self.assertTrue(created)
        self.assertIsNotNone(finding)
        self.assertIsNotNone(finding.id)
        # Title is formatted as "package (ecosystem): title" so check case-insensitively
        self.assertIn('vulnerable-pkg', finding.title.lower())
        self.assertTrue(finding.active)

        # Verify alert is linked
        alert.refresh_from_db()
        self.assertEqual(alert.finding, finding)

    def test_update_existing_finding(self):
        """Test updating an existing finding when alert is re-synced."""
        # Create initial finding
        alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='dependabot',
            github_alert_id='8',
            state='open',
            severity='high',
            title='Test Vulnerability',
            html_url='https://github.com/test/alert/8',
            package_name='test-pkg',
            created_at=timezone.now()
        )

        finding1, created1 = self.converter.create_or_update_finding(alert)
        self.assertTrue(created1)

        # Update alert state to fixed
        alert.state = 'fixed'
        alert.fixed_at = timezone.now()
        alert.save()

        # Re-convert
        finding2, created2 = self.converter.create_or_update_finding(alert)

        self.assertFalse(created2)  # Should be update, not create
        self.assertEqual(finding1.id, finding2.id)  # Same finding
        self.assertTrue(finding2.is_mitigated)  # State updated

    def test_sync_repository_findings(self):
        """Test syncing all alerts for a repository."""
        # Create multiple alerts
        for i in range(5):
            GitHubAlert.objects.create(
                repository=self.repository,
                alert_type='dependabot',
                github_alert_id=str(100 + i),
                state='open',
                severity='high',
                title=f'Alert {i}',
                html_url=f'https://github.com/test/alert/{100 + i}',
                package_name=f'pkg-{i}',
                created_at=timezone.now()
            )

        stats = self.converter.sync_repository_findings(self.repository)

        self.assertEqual(stats['total_alerts'], 5)
        self.assertEqual(stats['created'], 5)
        self.assertEqual(stats['updated'], 0)
        self.assertEqual(stats['errors'], 0)

        # Verify findings created
        findings = Finding.objects.filter(test__engagement__product=self.product)
        self.assertEqual(findings.count(), 5)

    def test_error_handling_no_product(self):
        """Test error handling when repository has no product."""
        from unittest.mock import Mock

        # Create a mock repository with product=None
        mock_repo = Mock(spec=Repository)
        mock_repo.name = 'test-org/no-product'
        mock_repo.product = None

        # Test that _get_or_create_engagement raises ValueError
        with self.assertRaises(ValueError) as context:
            self.converter._get_or_create_engagement(mock_repo)

        self.assertIn('no product', str(context.exception).lower())

    def test_deduplication_across_syncs(self):
        """Test that re-syncing doesn't create duplicate findings."""
        alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='codeql',
            github_alert_id='200',
            state='open',
            severity='medium',
            title='Code Smell',
            html_url='https://github.com/test/alert/200',
            rule_id='test-rule',
            created_at=timezone.now()
        )

        # First sync
        finding1, created1 = self.converter.create_or_update_finding(alert)
        self.assertTrue(created1)
        first_id = finding1.id

        # Second sync with same alert
        finding2, created2 = self.converter.create_or_update_finding(alert)
        self.assertFalse(created2)
        self.assertEqual(finding2.id, first_id)

        # Verify only one finding exists
        findings = Finding.objects.filter(unique_id_from_tool=finding1.unique_id_from_tool)
        self.assertEqual(findings.count(), 1)


class TestGitHubFindingsConverterIntegration(TestCase):
    """Integration tests for the findings converter with real workflow."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = Dojo_User.objects.create(username='test_user', is_superuser=True)
        self.product_type = Product_Type.objects.create(name='Test Type')
        self.product = Product.objects.create(name='Test Product', prod_type=self.product_type)
        self.repository = Repository.objects.create(
            name='integration-test/repo',
            github_repo_id=555555,
            product=self.product
        )

        # Create test types
        Test_Type.objects.get_or_create(name='GitHub Dependabot', defaults={'static_tool': True})
        Test_Type.objects.get_or_create(name='GitHub CodeQL', defaults={'static_tool': True})
        Test_Type.objects.get_or_create(name='GitHub Secret Scanning', defaults={'static_tool': True})

        self.converter = GitHubFindingsConverter()

    def test_mixed_alert_types_create_separate_tests(self):
        """Test that different alert types create separate Tests."""
        # Create alerts of different types
        GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='dependabot',
            github_alert_id='d1',
            state='open',
            severity='high',
            title='Dependabot Alert',
            html_url='https://github.com/test/d1',
            package_name='pkg1',
            created_at=timezone.now()
        )

        GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='codeql',
            github_alert_id='c1',
            state='open',
            severity='medium',
            title='CodeQL Alert',
            html_url='https://github.com/test/c1',
            rule_id='rule1',
            created_at=timezone.now()
        )

        stats = self.converter.sync_repository_findings(self.repository)

        # Should have created 2 findings
        self.assertEqual(stats['created'], 2)

        # Should have created 2 separate Tests
        engagement = Engagement.objects.get(product=self.product)
        tests = Test.objects.filter(engagement=engagement)
        self.assertEqual(tests.count(), 2)

        # Verify test types
        test_types = set(test.test_type.name for test in tests)
        self.assertIn('GitHub Dependabot', test_types)
        self.assertIn('GitHub CodeQL', test_types)

    def test_state_transition_workflow(self):
        """Test finding state transitions when alert state changes."""
        # Create OPEN alert
        alert = GitHubAlert.objects.create(
            repository=self.repository,
            alert_type='dependabot',
            github_alert_id='state-test',
            state='open',
            severity='high',
            title='State Test',
            html_url='https://github.com/test/state-test',
            package_name='state-pkg',
            created_at=timezone.now()
        )

        # Initial sync - should be active
        finding, _ = self.converter.create_or_update_finding(alert)
        self.assertTrue(finding.active)
        self.assertFalse(finding.is_mitigated)

        # Update to fixed
        alert.state = 'fixed'
        alert.fixed_at = timezone.now()
        alert.save()

        finding, _ = self.converter.create_or_update_finding(alert)
        self.assertFalse(finding.active)
        self.assertTrue(finding.is_mitigated)
        self.assertIsNotNone(finding.mitigated)

        # Update to dismissed
        alert.state = 'dismissed'
        alert.save()

        finding, _ = self.converter.create_or_update_finding(alert)
        self.assertFalse(finding.active)
        self.assertTrue(finding.risk_accepted)
