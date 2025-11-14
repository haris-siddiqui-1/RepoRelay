"""
GitHub GraphQL Client

Provides GraphQL query interface for fetching repository metadata from GitHub API v4.
Replaces 13-18 REST API calls per repository with single GraphQL query.

Performance:
- Single query cost: ~30-40 points (vs 18 REST calls)
- Incremental sync: ~5 minutes for 50-100 repos
- Full sync: ~15-20 hours for 2,451 repos (one-time cost)

Reference: https://docs.github.com/en/graphql
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class RateLimitInfo:
    """GitHub GraphQL rate limit information."""
    cost: int
    remaining: int
    reset_at: str


class GitHubGraphQLClient:
    """
    GitHub GraphQL API client for repository data collection.

    Provides methods for:
    - Single repository queries
    - Organization-level batch queries
    - Incremental sync (only changed repos)
    - Rate limit monitoring
    """

    GRAPHQL_ENDPOINT = "https://api.github.com/graphql"

    def __init__(self, github_token: str):
        """
        Initialize GraphQL client.

        Args:
            github_token: GitHub personal access token with repo:read permissions
        """
        self.token = github_token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        # Load query templates
        self.queries_dir = Path(__file__).parent / "queries"
        self.repository_query = self._load_query("repository_full.graphql")
        self.organization_query = self._load_query("organization_batch.graphql")
        self.dependabot_alerts_query = self._load_query("dependabot_alerts.graphql")

        logger.info("Initialized GitHub GraphQL client")

    def _load_query(self, filename: str) -> str:
        """Load GraphQL query from file."""
        query_path = self.queries_dir / filename
        with open(query_path, 'r') as f:
            # Strip comments and empty lines
            lines = []
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    lines.append(line)
            return ''.join(lines)

    def execute_query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute GraphQL query.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            Response data dictionary

        Raises:
            requests.HTTPError: If API request fails
            ValueError: If response contains errors
        """
        payload = {
            "query": query,
            "variables": variables
        }

        response = requests.post(
            self.GRAPHQL_ENDPOINT,
            headers=self.headers,
            json=payload,
            timeout=30
        )

        response.raise_for_status()
        data = response.json()

        # Check for GraphQL errors
        if "errors" in data:
            error_messages = [err.get("message", str(err)) for err in data["errors"]]
            logger.error(f"GraphQL errors: {error_messages}")
            raise ValueError(f"GraphQL query failed: {'; '.join(error_messages)}")

        return data

    def get_repository_data(self, owner: str, name: str) -> Optional[Dict[str, Any]]:
        """
        Fetch complete repository data using single GraphQL query.

        Replaces 13-18 REST API calls:
        - Repository metadata (1 call)
        - Default branch (1 call)
        - Commit history (1 call)
        - Contributors (1 call)
        - File tree (1 call)
        - CODEOWNERS content (3 calls for 3 possible paths)
        - README content (1 call)
        - Environments (1 call)
        - Releases (1 call)
        - Branch protection (1 call)
        - Pull requests (1 call)
        - Vulnerability alerts (1 call)

        Args:
            owner: Repository owner (organization or user)
            name: Repository name

        Returns:
            Dictionary with repository data, or None if not found
        """
        logger.debug(f"Fetching GraphQL data for {owner}/{name}")

        try:
            variables = {
                "owner": owner,
                "name": name
            }

            result = self.execute_query(self.repository_query, variables)

            # Extract data
            repo_data = result.get("data", {}).get("repository")
            rate_limit = result.get("data", {}).get("rateLimit", {})

            if repo_data:
                # Log rate limit info
                self._log_rate_limit(rate_limit)

                # Parse and return structured data
                return self._parse_repository_data(repo_data)
            else:
                logger.warning(f"Repository {owner}/{name} not found or not accessible")
                return None

        except requests.RequestException as e:
            logger.error(f"HTTP error fetching {owner}/{name}: {e}")
            return None
        except ValueError as e:
            logger.error(f"GraphQL error fetching {owner}/{name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching {owner}/{name}: {e}", exc_info=True)
            return None

    def get_organization_repositories(
        self,
        org: str,
        updated_since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch repositories from organization with optional filtering.

        Supports incremental sync by filtering on updatedAt timestamp.

        Args:
            org: Organization login name
            updated_since: Only return repos updated after this datetime
            limit: Maximum number of repositories to return (for testing)

        Returns:
            List of repository data dictionaries
        """
        logger.info(f"Fetching organization repositories for {org} (updated_since={updated_since})")

        repositories = []
        cursor = None
        has_next_page = True
        page_count = 0

        try:
            while has_next_page:
                page_count += 1
                variables = {
                    "org": org,
                    "cursor": cursor
                }

                result = self.execute_query(self.organization_query, variables)

                # Extract data
                org_data = result.get("data", {}).get("organization", {})
                if not org_data:
                    logger.warning(f"Organization {org} not found or not accessible")
                    break

                repos_connection = org_data.get("repositories", {})
                page_info = repos_connection.get("pageInfo", {})
                nodes = repos_connection.get("nodes", [])

                # Filter by updated_since if provided
                for node in nodes:
                    if updated_since:
                        updated_at_str = node.get("updatedAt")
                        if updated_at_str:
                            updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))

                            # Ensure both datetimes are timezone-aware for comparison
                            if updated_since.tzinfo is None:
                                # Make updated_since timezone-aware (assume UTC)
                                from django.utils import timezone as tz
                                updated_since = tz.make_aware(updated_since)

                            if updated_at <= updated_since:
                                logger.debug(f"Skipping {node.get('nameWithOwner')} - not updated since {updated_since}")
                                continue

                    parsed = self._parse_repository_data(node)
                    if parsed:
                        repositories.append(parsed)

                    # Check limit
                    if limit and len(repositories) >= limit:
                        logger.info(f"Reached limit of {limit} repositories")
                        return repositories

                # Check pagination
                has_next_page = page_info.get("hasNextPage", False)
                cursor = page_info.get("endCursor")

                # Log progress
                rate_limit = result.get("data", {}).get("rateLimit", {})
                self._log_rate_limit(rate_limit, page=page_count)

                logger.info(f"Page {page_count}: Fetched {len(nodes)} repos, "
                           f"filtered to {len(repositories)} total")

            logger.info(f"Completed organization fetch: {len(repositories)} repositories")
            return repositories

        except requests.RequestException as e:
            logger.error(f"HTTP error fetching organization {org}: {e}")
            return repositories
        except ValueError as e:
            logger.error(f"GraphQL error fetching organization {org}: {e}")
            return repositories
        except Exception as e:
            logger.error(f"Unexpected error fetching organization {org}: {e}", exc_info=True)
            return repositories

    def _parse_repository_data(self, repo_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse GraphQL repository data into structured format.

        Args:
            repo_data: Raw GraphQL response data

        Returns:
            Parsed repository data dictionary
        """
        parsed = {
            # Basic metadata
            'name': repo_data.get('name'),
            'nameWithOwner': repo_data.get('nameWithOwner'),
            'description': repo_data.get('description'),
            'url': repo_data.get('url'),
            'databaseId': repo_data.get('databaseId'),
            'isArchived': repo_data.get('isArchived', False),
            'diskUsage': repo_data.get('diskUsage'),
            'updatedAt': repo_data.get('updatedAt'),

            # Primary language
            'primaryLanguage': None,
        }

        if repo_data.get('primaryLanguage'):
            parsed['primaryLanguage'] = repo_data['primaryLanguage'].get('name')

        # Commit history
        parsed['commits'] = self._parse_commit_history(repo_data.get('defaultBranchRef'))

        # File tree
        parsed['fileTree'] = self._parse_file_tree(repo_data.get('tree'))

        # Specific files
        parsed['codeowners'] = self._parse_codeowners(
            repo_data.get('codeowners1'),
            repo_data.get('codeowners2'),
            repo_data.get('codeowners3')
        )
        parsed['readme'] = self._parse_file_content(repo_data.get('readme'))

        # GitHub settings
        parsed['environments'] = self._parse_connection(repo_data.get('environments'))
        parsed['releases'] = self._parse_releases(repo_data.get('releases'))
        parsed['branchProtection'] = self._parse_connection(repo_data.get('branchProtectionRules'))
        parsed['pullRequests'] = self._parse_pull_requests(repo_data.get('pullRequests'))
        parsed['vulnerabilityAlerts'] = self._parse_connection(repo_data.get('vulnerabilityAlerts'))

        return parsed

    def _parse_commit_history(self, default_branch: Optional[Dict]) -> Dict[str, Any]:
        """Parse commit history from defaultBranchRef."""
        if not default_branch:
            return {
                'totalCount': 0,
                'lastCommitDate': None,
                'contributors': []
            }

        target = default_branch.get('target', {})
        history = target.get('history', {})
        nodes = history.get('nodes', [])

        # Extract last commit date
        last_commit_date = None
        if nodes:
            last_commit_date = nodes[0].get('committedDate')

        # Extract unique contributors (using email, login, or name)
        contributors = set()
        for node in nodes:
            author = node.get('author', {})
            email = author.get('email')
            user = author.get('user', {})
            login = user.get('login') if user else None
            name = author.get('name')

            # Prefer email, fallback to login, then name
            identifier = email or login or name
            if identifier and identifier != 'noreply@github.com':
                contributors.add(identifier)

        return {
            'totalCount': history.get('totalCount', 0),
            'lastCommitDate': last_commit_date,
            'contributors': list(contributors),
            'contributorCount': len(contributors)
        }

    def _parse_file_tree(self, tree_obj: Optional[Dict]) -> List[Dict[str, str]]:
        """Parse file tree entries."""
        if not tree_obj or 'entries' not in tree_obj:
            return []

        entries = []
        for entry in tree_obj.get('entries', []):
            entries.append({
                'name': entry.get('name'),
                'path': entry.get('path'),
                'type': entry.get('type')
            })

        return entries

    def _parse_codeowners(
        self,
        codeowners1: Optional[Dict],
        codeowners2: Optional[Dict],
        codeowners3: Optional[Dict]
    ) -> Dict[str, Any]:
        """Parse CODEOWNERS file from 3 possible locations."""
        # Check each location in priority order
        for location, obj in [
            ('CODEOWNERS', codeowners1),
            ('.github/CODEOWNERS', codeowners2),
            ('docs/CODEOWNERS', codeowners3)
        ]:
            if obj and obj.get('text'):
                content = obj['text']
                # Calculate confidence based on coverage
                lines = [line.strip() for line in content.split('\n')
                        if line.strip() and not line.startswith('#')]
                confidence = min(len(lines) * 10, 100)

                return {
                    'content': content,
                    'location': location,
                    'confidence': confidence
                }

        return {
            'content': '',
            'location': None,
            'confidence': 0
        }

    def _parse_file_content(self, file_obj: Optional[Dict]) -> Optional[str]:
        """Parse file content from Blob object."""
        if file_obj and file_obj.get('text'):
            return file_obj['text']
        return None

    def _parse_connection(self, connection: Optional[Dict]) -> Dict[str, int]:
        """Parse GraphQL connection (totalCount only)."""
        if not connection:
            return {'totalCount': 0}
        return {'totalCount': connection.get('totalCount', 0)}

    def _parse_releases(self, releases: Optional[Dict]) -> Dict[str, Any]:
        """Parse releases with recent timestamps."""
        if not releases:
            return {
                'totalCount': 0,
                'recent': []
            }

        nodes = releases.get('nodes', [])
        recent = []
        for node in nodes:
            recent.append({
                'createdAt': node.get('createdAt'),
                'tagName': node.get('tagName')
            })

        return {
            'totalCount': releases.get('totalCount', 0),
            'recent': recent
        }

    def _parse_pull_requests(self, prs: Optional[Dict]) -> Dict[str, Any]:
        """Parse pull request data."""
        if not prs:
            return {
                'totalCount': 0,
                'recent': []
            }

        nodes = prs.get('nodes', [])
        recent = []
        for node in nodes:
            author = node.get('author', {})
            recent.append({
                'state': node.get('state'),
                'updatedAt': node.get('updatedAt'),
                'createdAt': node.get('createdAt'),
                'author': author.get('login') if author else None
            })

        return {
            'totalCount': prs.get('totalCount', 0),
            'recent': recent
        }

    def _log_rate_limit(self, rate_limit: Dict[str, Any], page: Optional[int] = None):
        """Log rate limit information."""
        if not rate_limit:
            return

        cost = rate_limit.get('cost', 0)
        remaining = rate_limit.get('remaining', 0)
        reset_at = rate_limit.get('resetAt', 'unknown')

        page_str = f" (page {page})" if page else ""
        logger.info(f"Rate limit{page_str}: cost={cost}, remaining={remaining}, reset={reset_at}")

        # Warn if running low
        if remaining < 500:
            logger.warning(f"Rate limit running low: {remaining} points remaining (resets at {reset_at})")

    def get_dependabot_alerts(
        self,
        owner: str,
        name: str,
        states: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch Dependabot vulnerability alerts for a repository.

        Args:
            owner: Repository owner (organization or user)
            name: Repository name
            states: Filter by alert states (OPEN, DISMISSED, FIXED, AUTO_DISMISSED).
                   Default: None (fetches all states)

        Returns:
            List of parsed Dependabot alert dictionaries
        """
        logger.debug(f"Fetching Dependabot alerts for {owner}/{name} (states={states})")

        alerts = []
        cursor = None
        has_next_page = True
        page_count = 0

        try:
            while has_next_page:
                page_count += 1
                variables = {
                    "owner": owner,
                    "name": name,
                    "cursor": cursor,
                    "states": states  # Can be None
                }

                result = self.execute_query(self.dependabot_alerts_query, variables)

                # Extract data
                repo_data = result.get("data", {}).get("repository")
                if not repo_data:
                    logger.warning(f"Repository {owner}/{name} not found or not accessible")
                    break

                vulnerability_alerts = repo_data.get("vulnerabilityAlerts", {})
                page_info = vulnerability_alerts.get("pageInfo", {})
                nodes = vulnerability_alerts.get("nodes", [])
                total_count = vulnerability_alerts.get("totalCount", 0)

                # Parse each alert
                for node in nodes:
                    parsed = self._parse_dependabot_alert(node, repo_data.get("databaseId"))
                    if parsed:
                        alerts.append(parsed)

                # Check pagination
                has_next_page = page_info.get("hasNextPage", False)
                cursor = page_info.get("endCursor")

                # Log progress
                rate_limit = result.get("data", {}).get("rateLimit", {})
                self._log_rate_limit(rate_limit, page=page_count)

                logger.info(f"Page {page_count}: Fetched {len(nodes)} alerts, "
                           f"{len(alerts)} total (out of {total_count})")

            logger.info(f"Completed Dependabot alert fetch: {len(alerts)} alerts for {owner}/{name}")
            return alerts

        except requests.RequestException as e:
            logger.error(f"HTTP error fetching Dependabot alerts for {owner}/{name}: {e}")
            return alerts
        except ValueError as e:
            logger.error(f"GraphQL error fetching Dependabot alerts for {owner}/{name}: {e}")
            return alerts
        except Exception as e:
            logger.error(f"Unexpected error fetching Dependabot alerts for {owner}/{name}: {e}", exc_info=True)
            return alerts

    def _parse_dependabot_alert(self, alert_data: Dict[str, Any], repo_id: int) -> Dict[str, Any]:
        """
        Parse Dependabot alert data into structured format.

        Args:
            alert_data: Raw GraphQL alert node
            repo_id: Repository database ID

        Returns:
            Parsed alert dictionary
        """
        # Security advisory
        advisory = alert_data.get("securityAdvisory", {})

        # Vulnerable package
        vulnerability = alert_data.get("securityVulnerability", {})
        package = vulnerability.get("package", {})
        first_patched = vulnerability.get("firstPatchedVersion", {})

        # Extract CVE and CWE identifiers
        cve_ids = []
        ghsa_id = advisory.get("ghsaId", "")
        for identifier in advisory.get("identifiers", []):
            if identifier.get("type") == "CVE":
                cve_ids.append(identifier.get("value"))

        cwe_ids = []
        for cwe in advisory.get("cwes", {}).get("nodes", []):
            cwe_ids.append(cwe.get("cweId"))

        # Extract reference URLs
        references = [ref.get("url") for ref in advisory.get("references", []) if ref.get("url")]

        # CVSS score
        cvss = advisory.get("cvss", {})
        cvss_score = cvss.get("score") if cvss else None
        cvss_vector = cvss.get("vectorString") if cvss else None

        # Dismissal information
        dismisser = alert_data.get("dismisser", {})
        dismisser_login = dismisser.get("login") if dismisser else None

        parsed = {
            # Alert identification
            "github_alert_id": str(alert_data.get("number", "")),  # Alert number in repo
            "alert_node_id": alert_data.get("id", ""),  # GraphQL node ID
            "repository_id": repo_id,
            "alert_type": "dependabot",

            # State
            "state": alert_data.get("state", "").lower(),  # OPEN -> open

            # Timestamps
            "created_at": alert_data.get("createdAt"),
            "dismissed_at": alert_data.get("dismissedAt"),
            "fixed_at": alert_data.get("fixedAt"),

            # Dismissal
            "dismiss_reason": alert_data.get("dismissReason", "").lower() if alert_data.get("dismissReason") else None,
            "dismiss_comment": alert_data.get("dismissComment"),
            "dismisser": dismisser_login,

            # Security advisory
            "ghsa_id": ghsa_id,
            "cve": cve_ids[0] if cve_ids else None,  # Primary CVE
            "cve_ids": cve_ids,  # All CVEs
            "cwe": cwe_ids[0] if cwe_ids else None,  # Primary CWE
            "cwe_ids": cwe_ids,  # All CWEs
            "title": advisory.get("summary", ""),
            "description": advisory.get("description", ""),
            "severity": advisory.get("severity", "").lower(),

            # CVSS
            "cvss_score": cvss_score,
            "cvss_vector": cvss_vector,

            # Package information
            "package_name": package.get("name", ""),
            "package_ecosystem": package.get("ecosystem", ""),
            "vulnerable_version_range": vulnerability.get("vulnerableVersionRange", ""),
            "patched_version": first_patched.get("identifier") if first_patched else None,
            "vulnerable_requirements": alert_data.get("vulnerableRequirements"),

            # File location
            "manifest_filename": alert_data.get("vulnerableManifestFilename", ""),
            "manifest_path": alert_data.get("vulnerableManifestPath", ""),

            # References
            "references": references,

            # Advisory timestamps
            "advisory_published_at": advisory.get("publishedAt"),
            "advisory_updated_at": advisory.get("updatedAt"),
            "advisory_withdrawn_at": advisory.get("withdrawnAt"),

            # HTML URL (construct from repo and alert number)
            "html_url": f"https://github.com/{alert_data.get('repository', {}).get('nameWithOwner', '')}/security/dependabot/{alert_data.get('number', '')}",

            # Raw data for future reference
            "raw_data": alert_data,
        }

        return parsed
