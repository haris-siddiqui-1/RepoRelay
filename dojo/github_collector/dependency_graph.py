"""
Dependency Graph Builder using GitHub SBOM API

Builds internal dependency graph by analyzing Software Bill of Materials (SBOM)
from GitHub's dependency graph API. Tracks which repositories consume which,
enabling consumption-based tier overrides for vulnerability prioritization.

API Reference: https://docs.github.com/en/rest/dependency-graph/sboms

Tier Override Thresholds (from vulnerability-prioritization-strategy.md):
- 50+ dependent repos -> tier1 (critical infrastructure)
- 20+ dependent repos -> tier2 (widely used)
- 5+ dependent repos -> promote one tier level
"""

import logging
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Any

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from dojo.models import Repository

logger = logging.getLogger(__name__)


class DependencyGraphBuilder:
    """
    Builds dependency graph by analyzing GitHub SBOM data.

    Workflow:
    1. Fetch SBOM for each repository via GitHub API
    2. Extract package names from SBOM dependencies
    3. Match package names to internal repository names
    4. Update Repository model with:
       - dependent_repo_count: Number of repos that depend on this one
       - downstream_consumers: List of repo names that consume this
       - is_shared_library: True if consumed by 5+ repos
       - consumption_tier_override: Tier based on consumption thresholds
    """

    REST_API_BASE = "https://api.github.com"

    # Tier override thresholds (from strategy doc)
    TIER1_THRESHOLD = 50  # Critical infrastructure
    TIER2_THRESHOLD = 20  # Widely used
    SHARED_LIBRARY_THRESHOLD = 5  # Promote one tier

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize dependency graph builder.

        Args:
            github_token: GitHub personal access token (overrides settings)
        """
        self.github_token = github_token or getattr(settings, 'DD_GITHUB_TOKEN', '')

        if not self.github_token:
            raise ValueError("GitHub token not configured. Set DD_GITHUB_TOKEN environment variable.")

        self.headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        # Cache for dependency relationships
        # Key: repo_name, Value: Set of repos that consume it
        self._consumer_map: Dict[str, Set[str]] = defaultdict(set)

        # Cache for internal repo names for matching
        self._internal_repos: Set[str] = set()

        logger.info("Initialized DependencyGraphBuilder")

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make authenticated REST API request with rate limit handling.

        Args:
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Response JSON data or None if failed
        """
        import time

        url = f"{self.REST_API_BASE}{endpoint}"

        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )

            # Check rate limit and wait if necessary
            remaining = response.headers.get('X-RateLimit-Remaining')
            reset_time = response.headers.get('X-RateLimit-Reset')

            if remaining and remaining.isdigit():
                remaining_int = int(remaining)
                if remaining_int < 100 and reset_time:
                    try:
                        reset_timestamp = int(reset_time)
                        wait_seconds = max(0, reset_timestamp - int(time.time())) + 5
                        if 0 < wait_seconds < 3600:  # Max 1 hour wait
                            logger.warning(
                                f"Rate limit low ({remaining_int} remaining). "
                                f"Waiting {wait_seconds}s until reset."
                            )
                            time.sleep(wait_seconds)
                    except (ValueError, TypeError):
                        pass  # Ignore invalid reset time

            logger.debug(f"Rate limit remaining: {remaining}, reset: {reset_time}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.debug(f"Resource not available for endpoint: {endpoint}")
            elif e.response.status_code == 403:
                # Check if this is rate limit vs permission error
                response_text = getattr(e.response, 'text', '')
                if 'rate limit' in response_text.lower():
                    logger.warning(f"Rate limit exceeded for endpoint: {endpoint}")
                else:
                    logger.warning(f"Access denied for endpoint (may need repo scope): {endpoint}")
            else:
                logger.error(f"HTTP error fetching data: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return None

    def fetch_sbom(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """
        Fetch SBOM for a repository.

        GitHub's SBOM API returns SPDX 2.3 format with all dependencies
        detected by Dependabot/dependency graph.

        Args:
            owner: Repository owner (org or user)
            repo: Repository name

        Returns:
            SBOM data in SPDX format or None if unavailable
        """
        endpoint = f"/repos/{owner}/{repo}/dependency-graph/sbom"
        return self._make_request(endpoint)

    def extract_dependencies_from_sbom(self, sbom_data: Dict[str, Any]) -> List[str]:
        """
        Extract dependency package names from SBOM data.

        SPDX SBOM structure:
        {
            "sbom": {
                "SPDXID": "SPDXRef-DOCUMENT",
                "packages": [
                    {"name": "pkg:npm/lodash@4.17.21", "SPDXID": "SPDXRef-npm-lodash-4.17.21"},
                    ...
                ],
                "relationships": [
                    {"relationshipType": "DEPENDS_ON", "spdxElementId": "...", "relatedSpdxElement": "..."}
                ]
            }
        }

        Args:
            sbom_data: SBOM response from GitHub API

        Returns:
            List of package names (normalized)
        """
        dependencies = []

        sbom = sbom_data.get("sbom", {})
        packages = sbom.get("packages", [])

        for package in packages:
            name = package.get("name", "")
            if not name:
                continue

            # Extract package name from PURL format (pkg:type/namespace/name@version)
            # Examples:
            # - pkg:npm/lodash@4.17.21 -> lodash
            # - pkg:pypi/django@5.1.0 -> django
            # - pkg:maven/org.apache.commons/commons-lang3@3.12.0 -> commons-lang3
            # - pkg:github/owner/repo -> repo
            normalized = self._normalize_package_name(name)
            if normalized:
                dependencies.append(normalized)

        return dependencies

    def _normalize_package_name(self, purl: str) -> Optional[str]:
        """
        Extract normalized package name from Package URL (PURL).

        Args:
            purl: Package URL in format pkg:type/namespace/name@version

        Returns:
            Normalized package name or None
        """
        # Handle github type specially - this directly references repos
        if purl.startswith("pkg:github/"):
            # pkg:github/owner/repo -> repo
            match = re.match(r"pkg:github/[^/]+/([^@]+)", purl)
            if match:
                return match.group(1).lower()

        # Handle other package types - extract the name portion
        # pkg:type/namespace/name@version or pkg:type/name@version
        match = re.match(r"pkg:[^/]+/(?:[^/]+/)?([^@]+)", purl)
        if match:
            return match.group(1).lower()

        # Fallback: just use the raw name if not a PURL
        if not purl.startswith("pkg:"):
            return purl.lower()

        return None

    def _load_internal_repos(self) -> None:
        """Load all internal repository names for matching."""
        repos = Repository.objects.values_list('name', flat=True)
        self._internal_repos = {name.lower() for name in repos if name}
        logger.info(f"Loaded {len(self._internal_repos)} internal repository names for matching")

    def _match_to_internal_repo(self, package_name: str) -> Optional[str]:
        """
        Match a package name to an internal repository.

        Matching strategies:
        1. Exact match (package name == repo name)
        2. Package name contains repo name (e.g., @org/my-lib -> my-lib)
        3. Repo name is prefix of package (e.g., my-service -> my-service-client)

        Args:
            package_name: Normalized package name

        Returns:
            Matched internal repo name or None
        """
        normalized = package_name.lower()

        # Strategy 1: Exact match
        if normalized in self._internal_repos:
            return normalized

        # Strategy 2: Try to find repo that this package belongs to
        # e.g., "my-service-client" might match "my-service"
        for repo_name in self._internal_repos:
            if normalized.startswith(repo_name) or repo_name in normalized:
                return repo_name

        return None

    def build_dependency_graph(
        self,
        owner: str,
        repository_ids: Optional[List[int]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Build dependency graph for all repositories.

        Args:
            owner: GitHub organization/user name
            repository_ids: Optional list of specific repo IDs to process
            dry_run: If True, don't save changes

        Returns:
            Statistics about the dependency graph build
        """
        stats = {
            "repos_processed": 0,
            "sbom_fetched": 0,
            "sbom_failed": 0,
            "dependencies_found": 0,
            "internal_matches": 0,
            "tier_overrides_applied": 0,
            "shared_libraries_found": 0,
        }

        # Load internal repo names for matching
        self._load_internal_repos()

        # Reset consumer map
        self._consumer_map = defaultdict(set)

        # Get repositories to process
        if repository_ids:
            repos = Repository.objects.filter(id__in=repository_ids)
        else:
            repos = Repository.objects.all()

        total_repos = repos.count()
        logger.info(f"Building dependency graph for {total_repos} repositories")

        # Phase 1: Fetch SBOMs and build consumer map
        for idx, repo in enumerate(repos.iterator(), 1):
            if idx % 10 == 0:
                logger.info(f"Processing repository {idx}/{total_repos}: {repo.name}")

            stats["repos_processed"] += 1

            sbom_data = self.fetch_sbom(owner, repo.name)
            if not sbom_data:
                stats["sbom_failed"] += 1
                continue

            stats["sbom_fetched"] += 1

            # Extract dependencies
            dependencies = self.extract_dependencies_from_sbom(sbom_data)
            stats["dependencies_found"] += len(dependencies)

            # Match to internal repos and update consumer map
            for dep_name in dependencies:
                matched_repo = self._match_to_internal_repo(dep_name)
                if matched_repo:
                    self._consumer_map[matched_repo].add(repo.name)
                    stats["internal_matches"] += 1

        # Phase 2: Update Repository records with consumption data
        if not dry_run:
            self._update_repositories(stats)
        else:
            # Just count what would be updated
            for repo_name, consumers in self._consumer_map.items():
                count = len(consumers)
                if count >= self.TIER1_THRESHOLD:
                    stats["tier_overrides_applied"] += 1
                elif count >= self.TIER2_THRESHOLD:
                    stats["tier_overrides_applied"] += 1
                if count >= self.SHARED_LIBRARY_THRESHOLD:
                    stats["shared_libraries_found"] += 1

        logger.info(f"Dependency graph build complete: {stats}")
        return stats

    def _update_repositories(self, stats: Dict[str, int]) -> None:
        """
        Update Repository records with consumption data.

        Args:
            stats: Statistics dict to update
        """
        updated_count = 0

        with transaction.atomic():
            # Update repos that have consumers
            for repo_name, consumers in self._consumer_map.items():
                try:
                    repo = Repository.objects.get(name__iexact=repo_name)
                except Repository.DoesNotExist:
                    logger.warning(f"Repository not found for update: {repo_name}")
                    continue

                count = len(consumers)

                # Update consumption fields
                repo.dependent_repo_count = count
                repo.downstream_consumers = list(consumers)
                repo.is_shared_library = count >= self.SHARED_LIBRARY_THRESHOLD

                # Calculate tier override
                tier_override = self._calculate_tier_override(count, repo.tier)
                if tier_override:
                    repo.consumption_tier_override = tier_override
                    stats["tier_overrides_applied"] += 1

                if count >= self.SHARED_LIBRARY_THRESHOLD:
                    stats["shared_libraries_found"] += 1

                repo.save(update_fields=[
                    'dependent_repo_count',
                    'downstream_consumers',
                    'is_shared_library',
                    'consumption_tier_override',
                ])
                updated_count += 1

            # Also reset repos that no longer have consumers
            repos_with_consumers = set(self._consumer_map.keys())
            repos_to_reset = Repository.objects.filter(
                dependent_repo_count__gt=0
            ).exclude(name__in=repos_with_consumers)

            reset_count = repos_to_reset.update(
                dependent_repo_count=0,
                downstream_consumers=[],
                is_shared_library=False,
                consumption_tier_override=None,
            )

            logger.info(f"Updated {updated_count} repositories, reset {reset_count} repositories")

    def _calculate_tier_override(self, consumer_count: int, current_tier: Optional[str]) -> Optional[str]:
        """
        Calculate consumption-based tier override.

        Thresholds:
        - 50+ consumers -> tier1 (critical infrastructure)
        - 20+ consumers -> tier2 (widely used)
        - 5+ consumers -> promote one tier level

        Args:
            consumer_count: Number of repos that depend on this one
            current_tier: Current tier classification

        Returns:
            Tier override value or None if no override needed
        """
        if consumer_count >= self.TIER1_THRESHOLD:
            return "tier1"
        elif consumer_count >= self.TIER2_THRESHOLD:
            return "tier2"
        elif consumer_count >= self.SHARED_LIBRARY_THRESHOLD:
            # Promote one tier level
            tier_promotion = {
                "archived": "tier4",
                "tier4": "tier3",
                "tier3": "tier2",
                "tier2": "tier1",
                "tier1": "tier1",  # Already highest
            }
            if current_tier:
                return tier_promotion.get(current_tier)

        return None

    def get_traffic_stats(self, owner: str, repo: str) -> Tuple[int, int]:
        """
        Fetch clone and view counts (requires push access).

        Uses GitHub Traffic API which requires push access to the repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Tuple of (clone_count_14d, view_count_14d)
        """
        clone_count = 0
        view_count = 0

        # Fetch clone count
        clones_endpoint = f"/repos/{owner}/{repo}/traffic/clones"
        clones_data = self._make_request(clones_endpoint)
        if clones_data:
            clone_count = clones_data.get("count", 0)

        # Fetch view count
        views_endpoint = f"/repos/{owner}/{repo}/traffic/views"
        views_data = self._make_request(views_endpoint)
        if views_data:
            view_count = views_data.get("count", 0)

        return clone_count, view_count

    def update_traffic_stats(
        self,
        owner: str,
        repository_ids: Optional[List[int]] = None,
        dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Update traffic statistics for repositories.

        Args:
            owner: GitHub organization/user name
            repository_ids: Optional list of specific repo IDs to process
            dry_run: If True, don't save changes

        Returns:
            Statistics about the traffic update
        """
        stats = {
            "repos_processed": 0,
            "traffic_fetched": 0,
            "traffic_failed": 0,
        }

        # Get repositories to process
        if repository_ids:
            repos = Repository.objects.filter(id__in=repository_ids)
        else:
            repos = Repository.objects.all()

        total_repos = repos.count()
        logger.info(f"Updating traffic stats for {total_repos} repositories")

        for idx, repo in enumerate(repos.iterator(), 1):
            if idx % 10 == 0:
                logger.info(f"Processing traffic for repository {idx}/{total_repos}: {repo.name}")

            stats["repos_processed"] += 1

            clone_count, view_count = self.get_traffic_stats(owner, repo.name)

            if clone_count > 0 or view_count > 0:
                stats["traffic_fetched"] += 1

                if not dry_run:
                    repo.clone_count_14d = clone_count
                    repo.view_count_14d = view_count
                    repo.save(update_fields=['clone_count_14d', 'view_count_14d'])
            else:
                stats["traffic_failed"] += 1

        logger.info(f"Traffic stats update complete: {stats}")
        return stats
