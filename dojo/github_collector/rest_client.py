"""
GitHub REST API Client for Security Alerts

Provides REST API interface for CodeQL and Secret Scanning alerts.
GraphQL API doesn't support these alert types, so we use REST API v3.

Performance:
- CodeQL alerts: ~1-2 API calls per repository (pagination if >100 alerts)
- Secret Scanning: ~1-2 API calls per repository (pagination if >100 alerts)

Reference: https://docs.github.com/en/rest/code-scanning
Reference: https://docs.github.com/en/rest/secret-scanning
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

import requests

logger = logging.getLogger(__name__)


class GitHubRestClient:
    """
    GitHub REST API client for security alerts (CodeQL and Secret Scanning).

    Provides methods for:
    - Fetching CodeQL alerts
    - Fetching Secret Scanning alerts
    - Rate limit monitoring
    """

    REST_API_BASE = "https://api.github.com"

    def __init__(self, github_token: str):
        """
        Initialize REST API client.

        Args:
            github_token: GitHub personal access token with security_events scope
        """
        self.token = github_token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        logger.info("Initialized GitHub REST API client")

    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make authenticated REST API request.

        Args:
            endpoint: API endpoint path (e.g., "/repos/owner/repo/code-scanning/alerts")
            params: Query parameters

        Returns:
            Response JSON data

        Raises:
            requests.HTTPError: If API request fails
        """
        url = f"{self.REST_API_BASE}{endpoint}"

        response = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=30
        )

        # Log rate limit info
        self._log_rate_limit(response.headers)

        response.raise_for_status()
        return response.json()

    def _make_paginated_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        per_page: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Make paginated REST API request.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            per_page: Results per page (max 100)

        Returns:
            List of all results across pages
        """
        if params is None:
            params = {}

        params["per_page"] = per_page
        params["page"] = 1

        all_results = []
        page_count = 0

        while True:
            page_count += 1
            logger.debug(f"Fetching page {page_count} from {endpoint}")

            try:
                results = self._make_request(endpoint, params)

                # Handle both list and dict responses
                if isinstance(results, list):
                    if not results:
                        break
                    all_results.extend(results)
                    if len(results) < per_page:
                        break
                    params["page"] += 1
                else:
                    # Some endpoints return dict with results array
                    break

            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    logger.warning(f"Endpoint not found or feature not enabled: {endpoint}")
                    break
                raise

        logger.info(f"Fetched {len(all_results)} total results from {endpoint} ({page_count} pages)")
        return all_results

    def get_codeql_alerts(
        self,
        owner: str,
        name: str,
        state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch CodeQL (Code Scanning) alerts for a repository.

        Args:
            owner: Repository owner
            name: Repository name
            state: Filter by state (open, dismissed, fixed). Default: None (all states)

        Returns:
            List of parsed CodeQL alert dictionaries
        """
        logger.debug(f"Fetching CodeQL alerts for {owner}/{name} (state={state})")

        endpoint = f"/repos/{owner}/{name}/code-scanning/alerts"
        params = {}
        if state:
            params["state"] = state

        try:
            alerts_data = self._make_paginated_request(endpoint, params)

            # Parse each alert
            parsed_alerts = []
            for alert in alerts_data:
                parsed = self._parse_codeql_alert(alert, owner, name)
                if parsed:
                    parsed_alerts.append(parsed)

            logger.info(f"Fetched {len(parsed_alerts)} CodeQL alerts for {owner}/{name}")
            return parsed_alerts

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"CodeQL not enabled or no access for {owner}/{name}")
                return []
            logger.error(f"HTTP error fetching CodeQL alerts for {owner}/{name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching CodeQL alerts for {owner}/{name}: {e}", exc_info=True)
            return []

    def _parse_codeql_alert(
        self,
        alert_data: Dict[str, Any],
        owner: str,
        name: str
    ) -> Dict[str, Any]:
        """
        Parse CodeQL alert data into structured format.

        Args:
            alert_data: Raw REST API alert data
            owner: Repository owner
            name: Repository name

        Returns:
            Parsed alert dictionary
        """
        # Rule information
        rule = alert_data.get("rule", {})

        # Most recent instance
        most_recent_instance = alert_data.get("most_recent_instance", {})
        location = most_recent_instance.get("location", {})

        # Dismissed information
        dismissed_by = alert_data.get("dismissed_by", {})

        parsed = {
            # Alert identification
            "github_alert_id": str(alert_data.get("number", "")),
            "alert_node_id": alert_data.get("url", ""),  # Use URL as unique ID
            "alert_type": "codeql",

            # State
            "state": alert_data.get("state", "").lower(),  # open, dismissed, fixed

            # Timestamps
            "created_at": alert_data.get("created_at"),
            "dismissed_at": alert_data.get("dismissed_at"),
            "fixed_at": alert_data.get("fixed_at"),
            "updated_at": alert_data.get("updated_at"),

            # Dismissal
            "dismiss_reason": alert_data.get("dismissed_reason"),
            "dismiss_comment": alert_data.get("dismissed_comment"),
            "dismisser": dismissed_by.get("login") if dismissed_by else None,

            # Rule information
            "rule_id": rule.get("id", ""),
            "rule_name": rule.get("name", ""),
            "rule_severity": rule.get("severity", "").lower(),
            "rule_security_severity_level": rule.get("security_severity_level", "").lower(),
            "rule_description": rule.get("description", ""),
            "rule_tags": rule.get("tags", []),

            # CWE
            "cwe": None,  # CodeQL provides CWE in tags like "external/cwe/cwe-79"
            "cwe_ids": self._extract_cwe_from_tags(rule.get("tags", [])),

            # Severity mapping
            "severity": self._map_codeql_severity(rule.get("security_severity_level")),

            # Title and description
            "title": rule.get("name", ""),
            "description": rule.get("description", ""),

            # Location
            "file_path": location.get("path", ""),
            "start_line": location.get("start_line"),
            "end_line": location.get("end_line"),
            "start_column": location.get("start_column"),
            "end_column": location.get("end_column"),

            # Tool information
            "tool_name": alert_data.get("tool", {}).get("name", "CodeQL"),
            "tool_version": alert_data.get("tool", {}).get("version"),

            # HTML URL
            "html_url": alert_data.get("html_url", ""),

            # Raw data
            "raw_data": alert_data,
        }

        return parsed

    def get_secret_scanning_alerts(
        self,
        owner: str,
        name: str,
        state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch Secret Scanning alerts for a repository.

        Args:
            owner: Repository owner
            name: Repository name
            state: Filter by state (open, resolved). Default: None (all states)

        Returns:
            List of parsed Secret Scanning alert dictionaries
        """
        logger.debug(f"Fetching Secret Scanning alerts for {owner}/{name} (state={state})")

        endpoint = f"/repos/{owner}/{name}/secret-scanning/alerts"
        params = {}
        if state:
            params["state"] = state

        try:
            alerts_data = self._make_paginated_request(endpoint, params)

            # Parse each alert
            parsed_alerts = []
            for alert in alerts_data:
                parsed = self._parse_secret_scanning_alert(alert, owner, name)
                if parsed:
                    parsed_alerts.append(parsed)

            logger.info(f"Fetched {len(parsed_alerts)} Secret Scanning alerts for {owner}/{name}")
            return parsed_alerts

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Secret Scanning not enabled or no access for {owner}/{name}")
                return []
            logger.error(f"HTTP error fetching Secret Scanning alerts for {owner}/{name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching Secret Scanning alerts for {owner}/{name}: {e}", exc_info=True)
            return []

    def _parse_secret_scanning_alert(
        self,
        alert_data: Dict[str, Any],
        owner: str,
        name: str
    ) -> Dict[str, Any]:
        """
        Parse Secret Scanning alert data into structured format.

        Args:
            alert_data: Raw REST API alert data
            owner: Repository owner
            name: Repository name

        Returns:
            Parsed alert dictionary
        """
        # Resolution information
        resolved_by = alert_data.get("resolved_by", {})

        parsed = {
            # Alert identification
            "github_alert_id": str(alert_data.get("number", "")),
            "alert_node_id": alert_data.get("url", ""),  # Use URL as unique ID
            "alert_type": "secret_scanning",

            # State
            "state": alert_data.get("state", "").lower(),  # open, resolved

            # Timestamps
            "created_at": alert_data.get("created_at"),
            "resolved_at": alert_data.get("resolved_at"),
            "updated_at": alert_data.get("updated_at"),

            # Resolution
            "resolution": alert_data.get("resolution"),  # false_positive, wont_fix, revoked, used_in_tests
            "resolution_comment": alert_data.get("resolution_comment"),
            "resolver": resolved_by.get("login") if resolved_by else None,

            # Secret type
            "secret_type": alert_data.get("secret_type", ""),
            "secret_type_display_name": alert_data.get("secret_type_display_name", ""),

            # Severity (Secret Scanning doesn't provide severity, default to high)
            "severity": "high",

            # Title and description
            "title": f"{alert_data.get('secret_type_display_name', 'Secret')} detected",
            "description": f"A {alert_data.get('secret_type_display_name', 'secret')} was detected in the repository.",

            # Locations (can be multiple)
            "locations": self._parse_secret_locations(alert_data.get("locations", [])),

            # Push protection
            "push_protection_bypassed": alert_data.get("push_protection_bypassed", False),
            "push_protection_bypassed_by": alert_data.get("push_protection_bypassed_by", {}).get("login"),
            "push_protection_bypassed_at": alert_data.get("push_protection_bypassed_at"),

            # HTML URL
            "html_url": alert_data.get("html_url", ""),

            # Raw data
            "raw_data": alert_data,
        }

        return parsed

    def _parse_secret_locations(self, locations_data: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Parse secret scanning alert locations."""
        locations = []
        for loc in locations_data:
            details = loc.get("details", {})
            locations.append({
                "type": loc.get("type", ""),  # commit, issue_title, issue_body, issue_comment
                "path": details.get("path", ""),
                "start_line": details.get("start_line"),
                "end_line": details.get("end_line"),
                "start_column": details.get("start_column"),
                "end_column": details.get("end_column"),
                "blob_sha": details.get("blob_sha", ""),
            })
        return locations

    def _extract_cwe_from_tags(self, tags: List[str]) -> List[str]:
        """Extract CWE IDs from CodeQL rule tags."""
        cwe_ids = []
        for tag in tags:
            if "external/cwe/cwe-" in tag.lower():
                # Extract CWE-NNN from "external/cwe/cwe-79"
                parts = tag.split("/")
                if len(parts) >= 3:
                    cwe_id = parts[-1].upper()  # cwe-79 -> CWE-79
                    cwe_ids.append(cwe_id)
        return cwe_ids

    def _map_codeql_severity(self, security_severity_level: Optional[str]) -> str:
        """
        Map CodeQL security_severity_level to DefectDojo severity.

        CodeQL levels: critical, high, medium, low, warning, note, error
        DefectDojo: critical, high, medium, low, info
        """
        if not security_severity_level:
            return "medium"

        level = security_severity_level.lower()
        mapping = {
            "critical": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
            "warning": "low",
            "note": "info",
            "error": "medium",
        }
        return mapping.get(level, "medium")

    def _log_rate_limit(self, headers: Dict[str, str]):
        """Log REST API rate limit information from response headers."""
        limit = headers.get("X-RateLimit-Limit")
        remaining = headers.get("X-RateLimit-Remaining")
        reset = headers.get("X-RateLimit-Reset")

        if limit and remaining:
            logger.debug(f"REST API rate limit: {remaining}/{limit} remaining "
                        f"(resets at {reset})")

            # Warn if running low
            if int(remaining) < 100:
                logger.warning(f"REST API rate limit running low: {remaining}/{limit} remaining")
