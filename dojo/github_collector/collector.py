"""
GitHub Repository Collector

Main orchestrator for syncing repository metadata from GitHub API
and updating DefectDojo Product records with enriched context.

Leverages existing DefectDojo GitHub integration patterns from dojo/github.py.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from github import Auth, Github, GithubException

from dojo.models import Product, GITHUB_Conf, GITHUB_PKey
from .signal_detector import SignalDetector
from .tier_classifier import TierClassifier
from .readme_summarizer import ReadmeSummarizer
from .graphql_client import GitHubGraphQLClient

logger = logging.getLogger(__name__)


class GitHubRepositoryCollector:
    """
    Collects repository metadata from GitHub API and enriches DefectDojo Products.

    Workflow:
    1. Authenticate with GitHub API using existing GITHUB_Conf/GITHUB_PKey models
    2. Fetch repository metadata (commits, contributors, releases, etc.)
    3. Detect binary signals using SignalDetector
    4. Classify tier using TierClassifier
    5. Summarize README using ReadmeSummarizer
    6. Update Product model with enriched data
    7. Parse CODEOWNERS and assign ownership
    """

    def __init__(self, github_token: Optional[str] = None, github_org: Optional[str] = None, use_graphql: bool = True):
        """
        Initialize collector with GitHub credentials.

        Args:
            github_token: GitHub personal access token (overrides settings)
            github_org: GitHub organization name (overrides settings)
            use_graphql: If True, use GraphQL for bulk operations (default: True)
        """
        self.github_token = github_token or getattr(settings, 'DD_GITHUB_TOKEN', '')
        self.github_org = github_org or getattr(settings, 'DD_GITHUB_ORG', '')
        self.use_graphql = use_graphql

        if not self.github_token:
            raise ValueError("GitHub token not configured. Set DD_GITHUB_TOKEN environment variable.")

        # Initialize GitHub REST client (for fallback and individual syncs)
        auth = Auth.Token(self.github_token)
        self.github_client = Github(auth=auth)

        # Initialize GraphQL client (for bulk syncs)
        if self.use_graphql:
            self.graphql_client = GitHubGraphQLClient(self.github_token)
            logger.info(f"Initialized GitHub collector with GraphQL for organization: {self.github_org}")
        else:
            self.graphql_client = None
            logger.info(f"Initialized GitHub collector with REST API for organization: {self.github_org}")

    def sync_all_repositories(self, incremental: bool = True) -> dict:
        """
        Sync all repositories from GitHub organization.

        Uses GraphQL for efficient bulk syncing with proper incremental logic:
        1. Fetch all repos with updatedAt timestamps
        2. Filter to only repos updated since last Product.updated
        3. Fetch full data only for changed repos

        Expected performance:
        - Full sync (2,451 repos): 15-20 hours (one-time)
        - Incremental sync (50-100 repos): <5 minutes (daily)

        Args:
            incremental: If True, only sync repos updated since last sync

        Returns:
            Dictionary with sync statistics
        """
        logger.info(f"Starting repository sync (incremental={incremental}, use_graphql={self.use_graphql})")

        stats = {
            'total_repos': 0,
            'updated': 0,
            'created': 0,
            'errors': 0,
            'skipped': 0
        }

        # Use GraphQL for bulk operations if enabled
        if self.use_graphql and self.graphql_client:
            return self._sync_all_with_graphql(incremental, stats)
        else:
            return self._sync_all_with_rest(incremental, stats)

    def _sync_all_with_graphql(self, incremental: bool, stats: dict) -> dict:
        """
        Sync all repositories using GraphQL API.

        Incremental sync strategy:
        1. Calculate updated_since threshold (most recent Product.updated)
        2. Fetch only repos with updatedAt > updated_since
        3. Process each repo with pre-fetched GraphQL data
        """
        try:
            # Determine updated_since for incremental sync
            updated_since = None
            if incremental:
                # Find most recent Product.updated timestamp
                most_recent = Product.objects.filter(
                    github_url__isnull=False
                ).order_by('-updated').first()

                if most_recent and most_recent.updated:
                    updated_since = most_recent.updated
                    logger.info(f"Incremental sync: fetching repos updated after {updated_since}")

            # Fetch repositories from organization (with incremental filtering)
            repos_data = self.graphql_client.get_organization_repositories(
                org=self.github_org,
                updated_since=updated_since
            )

            stats['total_repos'] = len(repos_data)
            logger.info(f"Fetched {len(repos_data)} repositories from GraphQL")

            # Process each repository with GraphQL data
            for repo_data in repos_data:
                try:
                    was_created = self._sync_repository_from_graphql(repo_data)

                    if was_created:
                        stats['created'] += 1
                    else:
                        stats['updated'] += 1

                except Exception as e:
                    repo_name = repo_data.get('nameWithOwner', 'unknown')
                    logger.error(f"Error syncing repository {repo_name}: {e}", exc_info=True)
                    stats['errors'] += 1

            logger.info(f"GraphQL sync completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"GraphQL sync failed: {e}", exc_info=True)
            logger.info("Falling back to REST API")
            # Reset stats for fresh count (GraphQL partial results discarded)
            stats = {
                'total_repos': 0,
                'updated': 0,
                'created': 0,
                'errors': stats.get('errors', 0) + 1,  # Keep GraphQL error count
                'skipped': 0
            }
            return self._sync_all_with_rest(incremental, stats)

    def _sync_all_with_rest(self, incremental: bool, stats: dict) -> dict:
        """
        Sync all repositories using REST API (fallback or explicit choice).
        """
        try:
            # Get organization
            org = self.github_client.get_organization(self.github_org)
            repos = org.get_repos()

            for repo in repos:
                stats['total_repos'] += 1

                try:
                    # Check if should skip (incremental mode)
                    if incremental and self._should_skip_repo(repo):
                        stats['skipped'] += 1
                        continue

                    # Sync repository
                    was_created = self.sync_repository(repo)

                    if was_created:
                        stats['created'] += 1
                    else:
                        stats['updated'] += 1

                except Exception as e:
                    logger.error(f"Error syncing repository {repo.full_name}: {e}", exc_info=True)
                    stats['errors'] += 1

            logger.info(f"REST sync completed: {stats}")
            return stats

        except GithubException as e:
            logger.error(f"GitHub API error during sync: {e}", exc_info=True)
            stats['errors'] += 1
            return stats

    def sync_repository(self, repo) -> bool:
        """
        Sync single repository metadata to DefectDojo Product.

        Args:
            repo: PyGithub Repository object

        Returns:
            True if Product was created, False if updated
        """
        logger.info(f"Syncing repository: {repo.full_name}")

        # Get or create Product
        product, created = self._get_or_create_product(repo)

        # Collect metadata
        metadata = self._collect_repository_metadata(repo)

        # Detect binary signals
        signal_detector = SignalDetector(repo)
        signals = signal_detector.detect_all_signals()

        # Classify tier
        classifier = TierClassifier()
        classification = classifier.classify(signals, metadata['days_since_last_commit'])

        # Summarize README
        summarizer = ReadmeSummarizer(repo)
        readme_data = summarizer.extract_and_summarize()

        # Update Product with collected data
        with transaction.atomic():
            # Repository activity
            product.last_commit_date = metadata['last_commit_date']
            product.active_contributors_90d = metadata['active_contributors_90d']
            product.days_since_last_commit = metadata['days_since_last_commit']

            # Repository metadata
            product.github_url = repo.html_url
            product.github_repo_id = str(repo.id)
            product.readme_summary = readme_data['summary']
            product.readme_length = readme_data['length']
            product.primary_language = readme_data['primary_language'] or repo.language or ''
            product.primary_framework = readme_data['primary_framework']

            # Ownership
            product.codeowners_content = metadata['codeowners_content']
            product.ownership_confidence = metadata['ownership_confidence']

            # Binary signals (all 36 fields)
            for signal_name, signal_value in signals.items():
                setattr(product, signal_name, signal_value)

            # Tier classification
            product.business_criticality = classification['business_criticality']

            # Handle archival
            if classification['tier'] == 'archived':
                product.lifecycle = Product.RETIREMENT

            product.save()

        logger.info(f"Synced {repo.full_name} - Tier: {classification['tier']}, "
                   f"Confidence: {classification['confidence_score']}%, "
                   f"Signals: {sum(signals.values())}/{len(signals)}")

        return created

    def _sync_repository_from_graphql(self, repo_data: dict) -> bool:
        """
        Sync repository from GraphQL data (no additional API calls needed).

        Args:
            repo_data: Parsed GraphQL repository data

        Returns:
            True if Product was created, False if updated
        """
        repo_name = repo_data.get('nameWithOwner', 'unknown')
        logger.info(f"Syncing repository from GraphQL data: {repo_name}")

        # Get or create Product
        product, created = self._get_or_create_product_from_graphql(repo_data)

        # Extract metadata from GraphQL data
        metadata = self._extract_metadata_from_graphql(repo_data)

        # Detect binary signals from GraphQL data
        signals = self._detect_signals_from_graphql(repo_data)

        # Classify tier
        classifier = TierClassifier()
        classification = classifier.classify(signals, metadata['days_since_last_commit'])

        # Summarize README from GraphQL data
        readme_data = self._summarize_readme_from_graphql(repo_data)

        # Update Product with collected data
        with transaction.atomic():
            # Repository activity
            product.last_commit_date = metadata['last_commit_date']
            product.active_contributors_90d = metadata['active_contributors_90d']
            product.days_since_last_commit = metadata['days_since_last_commit']

            # Repository metadata
            product.github_url = repo_data.get('url')
            product.github_repo_id = str(repo_data.get('databaseId', ''))
            product.readme_summary = readme_data['summary']
            product.readme_length = readme_data['length']
            product.primary_language = readme_data['primary_language'] or repo_data.get('primaryLanguage') or ''
            product.primary_framework = readme_data['primary_framework']

            # Ownership
            product.codeowners_content = metadata['codeowners_content']
            product.ownership_confidence = metadata['ownership_confidence']

            # Binary signals (all 36 fields)
            for signal_name, signal_value in signals.items():
                setattr(product, signal_name, signal_value)

            # Tier classification
            product.business_criticality = classification['business_criticality']

            # Handle archival
            if classification['tier'] == 'archived' or repo_data.get('isArchived'):
                product.lifecycle = Product.RETIREMENT

            product.save()

        logger.info(f"Synced {repo_name} - Tier: {classification['tier']}, "
                   f"Confidence: {classification['confidence_score']}%, "
                   f"Signals: {sum(signals.values())}/{len(signals)}")

        return created

    def _get_or_create_product(self, repo) -> tuple:
        """
        Get or create Product for repository.

        Uses repository full name (org/repo) as Product name.

        Args:
            repo: PyGithub Repository object

        Returns:
            Tuple of (Product, created_bool)
        """
        product_name = repo.full_name  # e.g., "myorg/myrepo"

        try:
            product = Product.objects.get(name=product_name)
            return product, False
        except Product.DoesNotExist:
            # Create new product
            from dojo.models import Product_Type

            # Get or create product type for organization
            product_type, _ = Product_Type.objects.get_or_create(
                name=repo.owner.login,
                defaults={'critical_product': False}
            )

            product = Product.objects.create(
                name=product_name,
                description=repo.description or f"GitHub repository: {repo.full_name}",
                prod_type=product_type,
                github_url=repo.html_url
            )

            logger.info(f"Created new Product: {product_name}")
            return product, True

    def _collect_repository_metadata(self, repo) -> dict:
        """
        Collect repository metadata from GitHub API.

        Args:
            repo: PyGithub Repository object

        Returns:
            Dictionary with metadata
        """
        metadata = {}

        # Last commit date
        try:
            commits = list(repo.get_commits()[:1])
            if commits:
                metadata['last_commit_date'] = commits[0].commit.author.date
                days_since = (datetime.now(commits[0].commit.author.date.tzinfo) - commits[0].commit.author.date).days
                metadata['days_since_last_commit'] = days_since
            else:
                metadata['last_commit_date'] = None
                metadata['days_since_last_commit'] = None
        except Exception as e:
            logger.warning(f"Could not fetch commits for {repo.full_name}: {e}")
            metadata['last_commit_date'] = None
            metadata['days_since_last_commit'] = None

        # Active contributors (90 days)
        try:
            since = datetime.now() - timedelta(days=90)
            contributors = set()
            for commit in repo.get_commits(since=since):
                if commit.commit.author and commit.commit.author.email:
                    contributors.add(commit.commit.author.email)
            metadata['active_contributors_90d'] = len(contributors)
        except Exception as e:
            logger.warning(f"Could not count contributors for {repo.full_name}: {e}")
            metadata['active_contributors_90d'] = 0

        # CODEOWNERS
        try:
            codeowners_content, ownership_confidence = self._fetch_codeowners(repo)
            metadata['codeowners_content'] = codeowners_content
            metadata['ownership_confidence'] = ownership_confidence
        except Exception as e:
            logger.warning(f"Could not fetch CODEOWNERS for {repo.full_name}: {e}")
            metadata['codeowners_content'] = ''
            metadata['ownership_confidence'] = 0

        return metadata

    def _fetch_codeowners(self, repo) -> tuple:
        """
        Fetch and parse CODEOWNERS file.

        Args:
            repo: PyGithub Repository object

        Returns:
            Tuple of (content_string, confidence_score)
        """
        try:
            # Try multiple possible locations
            codeowners_paths = ['CODEOWNERS', '.github/CODEOWNERS', 'docs/CODEOWNERS']

            for path in codeowners_paths:
                try:
                    file_content = repo.get_contents(path)
                    content = file_content.decoded_content.decode('utf-8')

                    # Calculate confidence based on coverage
                    lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
                    confidence = min(len(lines) * 10, 100)  # 10% per rule, max 100%

                    return content, confidence
                except:
                    continue

            return '', 0

        except Exception as e:
            logger.debug(f"CODEOWNERS not found for {repo.full_name}: {e}")
            return '', 0

    def _should_skip_repo(self, repo) -> bool:
        """
        Check if repository should be skipped in incremental mode.

        Skip if:
        - Product exists AND
        - Repository not updated since last Product update

        Args:
            repo: PyGithub Repository object

        Returns:
            True if should skip
        """
        try:
            product = Product.objects.get(name=repo.full_name)

            # Skip if repo not updated since last sync
            if product.updated and repo.updated_at <= product.updated:
                logger.debug(f"Skipping {repo.full_name} - no updates since last sync")
                return True

            return False

        except Product.DoesNotExist:
            return False

    def sync_product_from_github_url(self, product: Product) -> bool:
        """
        Sync specific Product using its github_url field.

        Args:
            product: Product instance with github_url set

        Returns:
            True if successful
        """
        if not product.github_url:
            logger.warning(f"Product {product.name} has no github_url set")
            return False

        try:
            # Extract org/repo from URL
            # URL format: https://github.com/org/repo
            parts = product.github_url.rstrip('/').split('/')
            if len(parts) < 2:
                logger.error(f"Invalid GitHub URL: {product.github_url}")
                return False

            org_name = parts[-2]
            repo_name = parts[-1]
            full_name = f"{org_name}/{repo_name}"

            # Fetch repository
            repo = self.github_client.get_repo(full_name)

            # Sync
            self.sync_repository(repo)
            return True

        except GithubException as e:
            logger.error(f"GitHub API error syncing {product.name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error syncing {product.name}: {e}", exc_info=True)
            return False

    # ===== GraphQL Data Processing Methods =====

    def _get_or_create_product_from_graphql(self, repo_data: dict) -> tuple:
        """
        Get or create Product from GraphQL repository data.

        Args:
            repo_data: Parsed GraphQL repository data

        Returns:
            Tuple of (Product, created_bool)
        """
        product_name = repo_data.get('nameWithOwner')  # e.g., "myorg/myrepo"

        try:
            product = Product.objects.get(name=product_name)
            return product, False
        except Product.DoesNotExist:
            # Create new product
            from dojo.models import Product_Type

            # Extract owner from nameWithOwner
            owner = product_name.split('/')[0] if '/' in product_name else 'unknown'

            # Get or create product type for organization
            product_type, _ = Product_Type.objects.get_or_create(
                name=owner,
                defaults={'critical_product': False}
            )

            product = Product.objects.create(
                name=product_name,
                description=repo_data.get('description') or f"GitHub repository: {product_name}",
                prod_type=product_type,
                github_url=repo_data.get('url')
            )

            logger.info(f"Created new Product: {product_name}")
            return product, True

    def _extract_metadata_from_graphql(self, repo_data: dict) -> dict:
        """
        Extract repository metadata from GraphQL data.

        Args:
            repo_data: Parsed GraphQL repository data

        Returns:
            Dictionary with metadata
        """
        metadata = {}

        # Extract commit data
        commits = repo_data.get('commits', {})

        # Last commit date
        last_commit_date_str = commits.get('lastCommitDate')
        if last_commit_date_str:
            last_commit_date = datetime.fromisoformat(last_commit_date_str.replace('Z', '+00:00'))
            metadata['last_commit_date'] = last_commit_date
            days_since = (timezone.now() - last_commit_date).days
            metadata['days_since_last_commit'] = days_since
        else:
            metadata['last_commit_date'] = None
            metadata['days_since_last_commit'] = None

        # Active contributors (already counted by GraphQL client)
        contributor_count = commits.get('contributorCount', 0)
        metadata['active_contributors_90d'] = contributor_count

        # CODEOWNERS
        codeowners = repo_data.get('codeowners', {})
        metadata['codeowners_content'] = codeowners.get('content', '')
        metadata['ownership_confidence'] = codeowners.get('confidence', 0)

        return metadata

    def _detect_signals_from_graphql(self, repo_data: dict) -> dict:
        """
        Detect all 36 binary signals from GraphQL data.

        Uses file tree and GitHub settings from GraphQL response.

        Args:
            repo_data: Parsed GraphQL repository data

        Returns:
            Dictionary of signal_name: bool
        """
        from .signal_detector import SignalDetector

        # Get file tree
        file_tree = repo_data.get('fileTree', [])
        file_paths = [entry.get('path', '') for entry in file_tree]

        # GitHub settings
        environments = repo_data.get('environments', {})
        releases = repo_data.get('releases', {})
        branch_protection = repo_data.get('branchProtection', {})
        pull_requests = repo_data.get('pullRequests', {})
        vulnerability_alerts = repo_data.get('vulnerabilityAlerts', {})

        # Deployment signals (Tier 1)
        signals = {
            'has_dockerfile': self._check_patterns(file_paths, SignalDetector.DOCKERFILE_PATTERNS),
            'has_kubernetes_config': self._check_patterns(file_paths, SignalDetector.KUBERNETES_PATTERNS),
            'has_ci_cd': self._check_patterns(file_paths, SignalDetector.CI_CD_PATTERNS),
            'has_terraform': self._check_patterns(file_paths, SignalDetector.TERRAFORM_PATTERNS),
            'has_deployment_scripts': self._check_patterns(file_paths, SignalDetector.DEPLOYMENT_SCRIPT_PATTERNS),
            'has_environments': environments.get('totalCount', 0) > 0,
        }

        # Production indicators (Tier 2)
        signals.update({
            'has_monitoring': self._check_patterns(file_paths, SignalDetector.MONITORING_PATTERNS),
            'has_releases': releases.get('totalCount', 0) > 0,
            'recent_release_90d': self._has_recent_release(releases),
            'has_branch_protection': branch_protection.get('totalCount', 0) > 0,
            'has_codeowners': bool(repo_data.get('codeowners', {}).get('content')),
        })

        # Development activity (Tier 3)
        commits_data = repo_data.get('commits', {})
        signals.update({
            'recent_commits_30d': self._has_recent_commits(commits_data, days=30),
            'recent_commits_90d': self._has_recent_commits(commits_data, days=90),
            'active_contributors': commits_data.get('contributorCount', 0) >= 2,
            'active_prs_30d': self._has_active_prs(pull_requests, days=30),
            'has_dependabot': self._has_dependabot_prs(pull_requests),
        })

        # Code organization (Tier 4)
        readme = repo_data.get('readme')
        signals.update({
            'has_tests': self._check_patterns(file_paths, SignalDetector.TEST_PATTERNS),
            'has_documentation': self._check_patterns(file_paths, SignalDetector.DOCS_PATTERNS),
            'has_readme': bool(readme),
            'readme_length_500': len(readme) >= 500 if readme else False,
            'has_api_spec': self._check_patterns(file_paths, SignalDetector.API_SPEC_PATTERNS),
            'has_changelog': self._check_patterns(file_paths, ['CHANGELOG', 'CHANGELOG.md', 'HISTORY.md']),
        })

        # Security signals (Tier 5)
        signals.update({
            'has_security_policy': self._check_patterns(file_paths, ['SECURITY.md', '.github/SECURITY.md']),
            'has_secret_scanning': vulnerability_alerts.get('totalCount', 0) > 0,
            'has_sbom': self._check_patterns(file_paths, ['.sbom', 'sbom.json', 'sbom.xml', 'bom.json']),
            'has_security_txt': self._check_patterns(file_paths, ['security.txt', '.well-known/security.txt']),
            'has_code_scanning': self._check_patterns(file_paths, ['.github/workflows/codeql', 'codeql']),
        })

        # Additional signals from original detector
        signals.update({
            'has_package_manager': self._check_patterns(file_paths, [
                'package.json', 'requirements.txt', 'Gemfile', 'pom.xml', 'build.gradle', 'Cargo.toml', 'go.mod'
            ]),
            'has_license': self._check_patterns(file_paths, ['LICENSE', 'LICENSE.md', 'LICENSE.txt', 'COPYING']),
            'has_contributing_guide': self._check_patterns(file_paths, ['CONTRIBUTING.md', '.github/CONTRIBUTING.md']),
            'has_code_of_conduct': self._check_patterns(file_paths, ['CODE_OF_CONDUCT.md', '.github/CODE_OF_CONDUCT.md']),
            'has_issue_templates': self._check_patterns(file_paths, ['.github/ISSUE_TEMPLATE/', '.github/issue_template.md']),
            'has_pr_template': self._check_patterns(file_paths, ['.github/pull_request_template.md', '.github/PULL_REQUEST_TEMPLATE']),
            'has_gitignore': self._check_patterns(file_paths, ['.gitignore']),
        })

        return signals

    def _check_patterns(self, file_paths: List[str], patterns: List[str]) -> bool:
        """
        Check if any pattern matches any file path.

        Uses same logic as SignalDetector._detect_pattern() for consistency.
        """
        for pattern in patterns:
            # Convert glob pattern to regex (matching SignalDetector logic)
            if '*' in pattern:
                regex_pattern = pattern.replace('.', r'\.').replace('*', '.*')
                regex = re.compile(regex_pattern, re.IGNORECASE)
                if any(regex.search(path) for path in file_paths):
                    return True
            else:
                # Direct path or directory check
                if pattern.endswith('/'):
                    # Directory check (case-insensitive)
                    if any(path.lower().startswith(pattern.lower()) for path in file_paths):
                        return True
                else:
                    # Exact file check (case-insensitive)
                    if any(pattern.lower() in path.lower() for path in file_paths):
                        return True

        return False

    def _has_recent_release(self, releases: dict, days: int = 90) -> bool:
        """Check if any release within last N days."""
        recent_releases = releases.get('recent', [])
        if not recent_releases:
            return False

        cutoff = timezone.now() - timedelta(days=days)
        for release in recent_releases:
            created_at_str = release.get('createdAt')
            if created_at_str:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                if created_at >= cutoff:
                    return True
        return False

    def _has_recent_commits(self, commits_data: dict, days: int) -> bool:
        """Check if last commit is within N days."""
        last_commit_date_str = commits_data.get('lastCommitDate')
        if not last_commit_date_str:
            return False

        last_commit_date = datetime.fromisoformat(last_commit_date_str.replace('Z', '+00:00'))
        cutoff = timezone.now() - timedelta(days=days)
        return last_commit_date >= cutoff

    def _has_active_prs(self, pull_requests: dict, days: int = 30) -> bool:
        """Check if any PR activity within last N days."""
        recent_prs = pull_requests.get('recent', [])
        if not recent_prs:
            return False

        cutoff = timezone.now() - timedelta(days=days)
        for pr in recent_prs:
            updated_at_str = pr.get('updatedAt')
            if updated_at_str:
                updated_at = datetime.fromisoformat(updated_at_str.replace('Z', '+00:00'))
                if updated_at >= cutoff:
                    return True
        return False

    def _has_dependabot_prs(self, pull_requests: dict) -> bool:
        """Check if any PRs from dependabot."""
        recent_prs = pull_requests.get('recent', [])
        for pr in recent_prs:
            author = pr.get('author', '').lower()
            if author and 'dependabot' in author:
                return True
        return False

    def _summarize_readme_from_graphql(self, repo_data: dict) -> dict:
        """
        Summarize README from GraphQL data.

        Args:
            repo_data: Parsed GraphQL repository data

        Returns:
            Dictionary with summary, length, primary_language, primary_framework
        """
        readme_content = repo_data.get('readme')

        if not readme_content:
            return {
                'summary': '',
                'length': 0,
                'primary_language': None,
                'primary_framework': None
            }

        # Use ReadmeSummarizer but with content instead of repo object
        # For now, create minimal summary
        from .readme_summarizer import ReadmeSummarizer

        # Calculate basic metrics
        length = len(readme_content)
        lines = readme_content.split('\n')
        first_paragraph = ' '.join(lines[:5]).strip()[:500]

        # Detect framework from README content
        framework = self._detect_framework_from_text(readme_content)

        return {
            'summary': first_paragraph,
            'length': length,
            'primary_language': repo_data.get('primaryLanguage'),
            'primary_framework': framework
        }

    def _detect_framework_from_text(self, text: str) -> Optional[str]:
        """Detect framework from text content."""
        text_lower = text.lower()
        frameworks = {
            'Django': ['django', 'django-'],
            'Flask': ['flask', 'flask-'],
            'React': ['react', 'reactjs'],
            'Vue': ['vue', 'vuejs'],
            'Angular': ['angular', '@angular'],
            'Spring': ['spring boot', 'springframework'],
            'Express': ['express.js', 'expressjs'],
            'FastAPI': ['fastapi', 'fast-api'],
            'Next.js': ['next.js', 'nextjs'],
            'Rails': ['rails', 'ruby on rails'],
        }

        for framework, keywords in frameworks.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return framework

        return None
