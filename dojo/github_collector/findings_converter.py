"""
GitHub Alerts to DefectDojo Findings Converter.

This module handles the conversion of GitHub security alerts (Dependabot, CodeQL,
Secret Scanning) into DefectDojo Finding objects, including field mapping, state
synchronization, and deduplication.

Phase 3: DefectDojo Finding Creation
"""

import logging
from datetime import datetime
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from dojo.models import (
    Engagement,
    Finding,
    GitHubAlert,
    Product,
    Repository,
    Test,
    Test_Type,
    Dojo_User,
)

logger = logging.getLogger(__name__)


class GitHubFindingsConverter:
    """Convert GitHub alerts to DefectDojo findings."""

    # Severity mapping from GitHub to DefectDojo
    SEVERITY_MAP = {
        'critical': 'Critical',
        'high': 'High',
        'moderate': 'Medium',
        'medium': 'Medium',
        'low': 'Low',
        'warning': 'Low',
        'error': 'High',
        'note': 'Info',
        'info': 'Info',
    }

    # Test type names
    TEST_TYPE_DEPENDABOT = 'GitHub Dependabot'
    TEST_TYPE_CODEQL = 'GitHub CodeQL'
    TEST_TYPE_SECRET_SCANNING = 'GitHub Secret Scanning'

    def __init__(self):
        """Initialize the converter."""
        self.system_user = self._get_system_user()

    def _get_system_user(self) -> Dojo_User:
        """Get or create a system user for automated Finding creation."""
        # Try to get admin user with ID 1 (default in DefectDojo)
        try:
            return Dojo_User.objects.get(id=1)
        except Dojo_User.DoesNotExist:
            # Fall back to first superuser
            return Dojo_User.objects.filter(is_superuser=True).first()

    def _map_severity(self, github_severity: str) -> str:
        """
        Map GitHub severity to DefectDojo severity.

        Args:
            github_severity: GitHub severity string (critical, high, moderate, low, etc.)

        Returns:
            DefectDojo severity (Critical, High, Medium, Low, Info)
        """
        severity = github_severity.lower() if github_severity else 'info'
        return self.SEVERITY_MAP.get(severity, 'Info')

    def _get_or_create_engagement(self, repository: Repository) -> Engagement:
        """
        Get or create an Engagement for GitHub security alerts.

        Args:
            repository: Repository instance

        Returns:
            Engagement instance
        """
        product = repository.product
        if not product:
            raise ValueError(f"Repository {repository.name} has no product")

        engagement_name = f"GitHub Security Alerts - {repository.name}"

        engagement, created = Engagement.objects.get_or_create(
            product=product,
            name=engagement_name,
            defaults={
                'target_start': timezone.now().date(),
                'target_end': timezone.now().date(),
                'active': True,
                'status': 'In Progress',
                'engagement_type': 'CI/CD',
            }
        )

        if created:
            logger.info(f"Created engagement: {engagement_name}")

        return engagement

    def _get_or_create_test(
        self,
        repository: Repository,
        alert_type: str,
        engagement: Engagement
    ) -> Test:
        """
        Get or create a Test for a specific alert type.

        Args:
            repository: Repository instance
            alert_type: Alert type (dependabot, codeql, secret_scanning)
            engagement: Engagement instance

        Returns:
            Test instance
        """
        # Map alert type to test type name
        test_type_map = {
            'dependabot': self.TEST_TYPE_DEPENDABOT,
            'codeql': self.TEST_TYPE_CODEQL,
            'secret_scanning': self.TEST_TYPE_SECRET_SCANNING,
        }

        test_type_name = test_type_map.get(alert_type)
        if not test_type_name:
            raise ValueError(f"Unknown alert type: {alert_type}")

        # Get Test_Type
        try:
            test_type = Test_Type.objects.get(name=test_type_name)
        except Test_Type.DoesNotExist:
            raise ValueError(f"Test_Type not found: {test_type_name}")

        # Get or create Test
        test_name = f"{repository.name} - {test_type_name}"

        test, created = Test.objects.get_or_create(
            engagement=engagement,
            test_type=test_type,
            defaults={
                'target_start': timezone.now(),
                'target_end': timezone.now(),
                'percent_complete': 100,
            }
        )

        if created:
            logger.info(f"Created test: {test_name}")

        return test

    def _build_unique_id(self, alert: GitHubAlert) -> str:
        """
        Build unique_id_from_tool for deduplication.

        Format: github-{alert_type}-{repo_id}-{alert_number}

        Args:
            alert: GitHubAlert instance

        Returns:
            Unique identifier string
        """
        return f"github-{alert.alert_type}-{alert.repository.github_repo_id}-{alert.github_alert_id}"

    def _convert_dependabot_alert(self, alert: GitHubAlert, test: Test) -> dict:
        """
        Convert Dependabot alert to Finding fields.

        Args:
            alert: GitHubAlert instance
            test: Test instance

        Returns:
            Dictionary of Finding fields
        """
        # Build title
        package_info = f"{alert.package_name}" if alert.package_name else "Unknown package"
        if alert.package_ecosystem:
            package_info += f" ({alert.package_ecosystem})"

        title = f"{package_info}: {alert.title}"

        # Build description
        description_parts = []
        if alert.description:
            description_parts.append(alert.description)

        if alert.package_name:
            description_parts.append(f"\n**Package:** {alert.package_name}")
        if alert.package_ecosystem:
            description_parts.append(f"**Ecosystem:** {alert.package_ecosystem}")
        if alert.vulnerable_version:
            description_parts.append(f"**Vulnerable Version:** {alert.vulnerable_version}")
        if alert.patched_version:
            description_parts.append(f"**Patched Version:** {alert.patched_version}")

        description_parts.append(f"\n**GitHub Alert:** {alert.html_url}")

        description = "\n".join(description_parts)

        # Build mitigation
        mitigation = None
        if alert.patched_version:
            mitigation = f"Upgrade {alert.package_name} to version {alert.patched_version} or later."

        return {
            'title': title[:511],  # Max length
            'description': description,
            'severity': self._map_severity(alert.severity),
            'cve': alert.cve if alert.cve else None,
            'mitigation': mitigation,
            'component_name': alert.package_name,
            'component_version': alert.vulnerable_version,
            'references': alert.html_url,
            'unique_id_from_tool': self._build_unique_id(alert),
            'vuln_id_from_tool': alert.github_alert_id,
            'test': test,
            'reporter': self.system_user,
            'date': alert.created_at.date() if alert.created_at else timezone.now().date(),
        }

    def _convert_codeql_alert(self, alert: GitHubAlert, test: Test) -> dict:
        """
        Convert CodeQL alert to Finding fields.

        Args:
            alert: GitHubAlert instance
            test: Test instance

        Returns:
            Dictionary of Finding fields
        """
        # Build title
        title = alert.title

        # Build description
        description_parts = []
        if alert.description:
            description_parts.append(alert.description)

        if alert.file_path:
            location = f"{alert.file_path}"
            if alert.start_line:
                location += f":{alert.start_line}"
                if alert.end_line and alert.end_line != alert.start_line:
                    location += f"-{alert.end_line}"
            description_parts.append(f"\n**Location:** {location}")

        if alert.rule_id:
            description_parts.append(f"**Rule:** {alert.rule_id}")

        description_parts.append(f"\n**GitHub Alert:** {alert.html_url}")

        description = "\n".join(description_parts)

        # Parse CWE number
        cwe_number = None
        if alert.cwe:
            # Extract number from "CWE-XXX" format
            try:
                cwe_number = int(alert.cwe.replace('CWE-', '').split(',')[0].strip())
            except (ValueError, AttributeError):
                logger.warning(f"Could not parse CWE from: {alert.cwe}")

        return {
            'title': title[:511],
            'description': description,
            'severity': self._map_severity(alert.severity),
            'cwe': cwe_number,
            'file_path': alert.file_path,
            'line': alert.start_line,
            'references': alert.html_url,
            'unique_id_from_tool': self._build_unique_id(alert),
            'vuln_id_from_tool': alert.rule_id or alert.github_alert_id,
            'test': test,
            'reporter': self.system_user,
            'date': alert.created_at.date() if alert.created_at else timezone.now().date(),
        }

    def _convert_secret_scanning_alert(self, alert: GitHubAlert, test: Test) -> dict:
        """
        Convert Secret Scanning alert to Finding fields.

        Args:
            alert: GitHubAlert instance
            test: Test instance

        Returns:
            Dictionary of Finding fields
        """
        # Build title
        secret_type = alert.secret_type or "Exposed Secret"
        title = f"{secret_type}: {alert.title}"

        # Build description
        description_parts = []
        if alert.description:
            description_parts.append(alert.description)

        if alert.secret_type:
            description_parts.append(f"\n**Secret Type:** {alert.secret_type}")

        if alert.file_path:
            location = f"{alert.file_path}"
            if alert.start_line:
                location += f":{alert.start_line}"
            description_parts.append(f"**Location:** {location}")

        description_parts.append(f"\n**GitHub Alert:** {alert.html_url}")

        description = "\n".join(description_parts)

        return {
            'title': title[:511],
            'description': description,
            'severity': 'Critical',  # Secrets are always critical
            'file_path': alert.file_path,
            'line': alert.start_line,
            'references': alert.html_url,
            'unique_id_from_tool': self._build_unique_id(alert),
            'vuln_id_from_tool': alert.github_alert_id,
            'test': test,
            'reporter': self.system_user,
            'date': alert.created_at.date() if alert.created_at else timezone.now().date(),
        }

    def convert_alert_to_finding_fields(self, alert: GitHubAlert, test: Test) -> dict:
        """
        Convert a GitHub alert to Finding fields based on alert type.

        Args:
            alert: GitHubAlert instance
            test: Test instance

        Returns:
            Dictionary of Finding fields
        """
        if alert.alert_type == 'dependabot':
            return self._convert_dependabot_alert(alert, test)
        elif alert.alert_type == 'codeql':
            return self._convert_codeql_alert(alert, test)
        elif alert.alert_type == 'secret_scanning':
            return self._convert_secret_scanning_alert(alert, test)
        else:
            raise ValueError(f"Unknown alert type: {alert.alert_type}")

    def _apply_state_to_finding(self, finding: Finding, alert: GitHubAlert):
        """
        Apply GitHub alert state to Finding status fields.

        Args:
            finding: Finding instance
            alert: GitHubAlert instance
        """
        if alert.state == 'open':
            finding.active = True
            finding.verified = False
            finding.is_mitigated = False
            finding.mitigated = None
            finding.mitigated_by = None
            finding.risk_accepted = False
            finding.false_p = False
            finding.out_of_scope = False

        elif alert.state == 'fixed':
            finding.active = False
            finding.is_mitigated = True
            finding.mitigated = alert.fixed_at or timezone.now()
            finding.mitigated_by = self.system_user

        elif alert.state == 'dismissed':
            finding.active = False
            finding.risk_accepted = True

    @transaction.atomic
    def create_or_update_finding(self, alert: GitHubAlert) -> tuple[Finding, bool]:
        """
        Create or update a Finding from a GitHub alert.

        Args:
            alert: GitHubAlert instance

        Returns:
            Tuple of (Finding instance, created boolean)
        """
        # Get or create Engagement and Test
        engagement = self._get_or_create_engagement(alert.repository)
        test = self._get_or_create_test(alert.repository, alert.alert_type, engagement)

        # Build unique_id for deduplication
        unique_id = self._build_unique_id(alert)

        # Check if Finding already exists
        try:
            finding = Finding.objects.get(
                test=test,
                unique_id_from_tool=unique_id
            )
            created = False
            logger.debug(f"Found existing finding: {finding.title}")
        except Finding.DoesNotExist:
            finding = Finding()
            created = True
            logger.debug(f"Creating new finding for alert: {alert.title}")

        # Convert alert to Finding fields
        finding_fields = self.convert_alert_to_finding_fields(alert, test)

        # Update Finding fields
        for field, value in finding_fields.items():
            setattr(finding, field, value)

        # Apply state-based fields
        self._apply_state_to_finding(finding, alert)

        # Save Finding
        finding.save()

        # Link Finding to GitHubAlert
        alert.finding = finding
        alert.save(update_fields=['finding'])

        logger.info(f"{'Created' if created else 'Updated'} finding: {finding.title} (ID: {finding.id})")

        return finding, created

    def sync_repository_findings(self, repository: Repository) -> dict:
        """
        Sync all alerts for a repository to Findings.

        Args:
            repository: Repository instance

        Returns:
            Dictionary with sync statistics
        """
        alerts = GitHubAlert.objects.filter(repository=repository)

        stats = {
            'total_alerts': alerts.count(),
            'created': 0,
            'updated': 0,
            'errors': 0,
        }

        for alert in alerts:
            try:
                finding, created = self.create_or_update_finding(alert)
                if created:
                    stats['created'] += 1
                else:
                    stats['updated'] += 1
            except Exception as e:
                logger.error(f"Error syncing alert {alert.id}: {e}", exc_info=True)
                stats['errors'] += 1

        logger.info(
            f"Synced findings for {repository.name}: "
            f"{stats['created']} created, {stats['updated']} updated, "
            f"{stats['errors']} errors"
        )

        return stats
