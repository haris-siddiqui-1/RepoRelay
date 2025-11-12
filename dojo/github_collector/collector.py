"""
GitHub Repository Collector

Main orchestrator for syncing repository metadata from GitHub API
and updating DefectDojo Product records with enriched context.

Leverages existing DefectDojo GitHub integration patterns from dojo/github.py.
"""

import logging
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

    def __init__(self, github_token: Optional[str] = None, github_org: Optional[str] = None):
        """
        Initialize collector with GitHub credentials.

        Args:
            github_token: GitHub personal access token (overrides settings)
            github_org: GitHub organization name (overrides settings)
        """
        self.github_token = github_token or getattr(settings, 'DD_GITHUB_TOKEN', '')
        self.github_org = github_org or getattr(settings, 'DD_GITHUB_ORG', '')

        if not self.github_token:
            raise ValueError("GitHub token not configured. Set DD_GITHUB_TOKEN environment variable.")

        # Initialize GitHub client (following dojo/github.py pattern)
        auth = Auth.Token(self.github_token)
        self.github_client = Github(auth=auth)

        logger.info(f"Initialized GitHub collector for organization: {self.github_org}")

    def sync_all_repositories(self, incremental: bool = True) -> dict:
        """
        Sync all repositories from GitHub organization.

        Args:
            incremental: If True, only sync repos updated since last sync

        Returns:
            Dictionary with sync statistics
        """
        logger.info(f"Starting repository sync (incremental={incremental})")

        stats = {
            'total_repos': 0,
            'updated': 0,
            'created': 0,
            'errors': 0,
            'skipped': 0
        }

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

            logger.info(f"Sync completed: {stats}")
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
