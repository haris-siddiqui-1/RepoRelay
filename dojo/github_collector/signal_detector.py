"""
Binary Signal Detection

Analyzes repository structure to detect production indicators,
security maturity, and development patterns through file/directory presence.
"""

import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)


class SignalDetector:
    """
    Detects binary signals from repository file tree and metadata.

    Binary signals indicate repository characteristics:
    - Deployment indicators (Docker, K8s, CI/CD)
    - Production readiness (monitoring, releases, branch protection)
    - Active development (recent commits, PRs, contributors)
    - Code organization (tests, docs, API specs)
    - Security maturity (scanning configs, secret detection)
    """

    # File/directory patterns for signal detection
    DOCKERFILE_PATTERNS = [
        'Dockerfile',
        'Dockerfile.*',
        'docker/Dockerfile',
        '.docker/Dockerfile'
    ]

    KUBERNETES_PATTERNS = [
        'kubernetes/',
        'k8s/',
        '.kube/',
        'helm/',
        'charts/',
        'deployment.yaml',
        'deployment.yml',
        'kustomization.yaml'
    ]

    CI_CD_PATTERNS = [
        '.github/workflows/',
        '.gitlab-ci.yml',
        'Jenkinsfile',
        '.travis.yml',
        '.circleci/',
        'azure-pipelines.yml',
        '.buildkite/',
        'bitbucket-pipelines.yml'
    ]

    TERRAFORM_PATTERNS = [
        '*.tf',
        'terraform/',
        '.terraform/'
    ]

    DEPLOYMENT_SCRIPT_PATTERNS = [
        'deploy.sh',
        'scripts/deploy',
        'deployment/',
        'bin/deploy'
    ]

    MONITORING_PATTERNS = [
        'datadog.yaml',
        'prometheus.yml',
        'grafana/',
        'newrelic.yml',
        '.dd/',
        'apm-config'
    ]

    TEST_PATTERNS = [
        'test/',
        'tests/',
        'spec/',
        '__tests__/',
        '*.test.js',
        '*.spec.ts',
        'test_*.py'
    ]

    DOCS_PATTERNS = [
        'docs/',
        'documentation/',
        'README.md',  # Will check length separately
        'CONTRIBUTING.md'
    ]

    API_SPEC_PATTERNS = [
        'openapi.yaml',
        'openapi.json',
        'swagger.yaml',
        'swagger.json',
        'api-spec.yaml',
        'api/',
        '.spectral.yml'
    ]

    SECURITY_PATTERNS = [
        'SECURITY.md',
        'security.txt',
        '.well-known/security.txt'
    ]

    SECURITY_SCANNING_PATTERNS = [
        '.github/workflows/security',
        '.github/workflows/codeql',
        'semgrep.yml',
        '.semgrep/',
        'sonar-project.properties'
    ]

    GITLEAKS_PATTERNS = [
        '.gitleaks.toml',
        'gitleaks.toml',
        '.gitleaks.yaml'
    ]

    SAST_PATTERNS = [
        '.semgrep.yml',
        'semgrep.yaml',
        '.bandit',
        'sonar-project.properties',
        '.codeql/'
    ]

    DATABASE_MIGRATION_PATTERNS = [
        'migrations/',
        'db/migrations/',
        'alembic/',
        'flyway/',
        'liquibase/'
    ]

    SSL_PATTERNS = [
        'ssl/',
        'certs/',
        'tls.conf',
        'nginx.conf'  # Often contains SSL config
    ]

    PACKAGE_PATTERNS = {
        'node': ['package.json'],
        'python': ['requirements.txt', 'setup.py', 'pyproject.toml'],
        'go': ['go.mod'],
        'java': ['pom.xml', 'build.gradle'],
        'ruby': ['Gemfile'],
        'rust': ['Cargo.toml'],
        'php': ['composer.json']
    }

    def __init__(self, repo):
        """
        Initialize detector with GitHub repository object.

        Args:
            repo: PyGithub Repository object
        """
        self.repo = repo
        self.file_tree_cache = None

    def detect_all_signals(self) -> Dict[str, bool]:
        """
        Detect all binary signals for the repository.

        Returns:
            Dictionary mapping signal names to boolean values
        """
        logger.info(f"Detecting signals for repository: {self.repo.full_name}")

        signals = {}

        # Get file tree once for efficiency
        self._cache_file_tree()

        # Deployment Indicators
        signals['has_dockerfile'] = self._detect_pattern(self.DOCKERFILE_PATTERNS)
        signals['has_kubernetes_config'] = self._detect_pattern(self.KUBERNETES_PATTERNS)
        signals['has_ci_cd'] = self._detect_pattern(self.CI_CD_PATTERNS)
        signals['has_terraform'] = self._detect_pattern(self.TERRAFORM_PATTERNS)
        signals['has_deployment_scripts'] = self._detect_pattern(self.DEPLOYMENT_SCRIPT_PATTERNS)
        signals['has_procfile'] = self._detect_file_exact('Procfile')

        # Production Readiness
        signals['has_environments'] = self._detect_github_environments()
        signals['has_releases'] = self._detect_github_releases()
        signals['has_branch_protection'] = self._detect_branch_protection()
        signals['has_monitoring_config'] = self._detect_pattern(self.MONITORING_PATTERNS)
        signals['has_ssl_config'] = self._detect_pattern(self.SSL_PATTERNS)
        signals['has_database_migrations'] = self._detect_pattern(self.DATABASE_MIGRATION_PATTERNS)

        # Active Development (computed from API data)
        signals['recent_commits_30d'] = self._detect_recent_commits(days=30)
        signals['active_prs_30d'] = self._detect_active_prs(days=30)
        signals['multiple_contributors'] = self._detect_multiple_contributors(days=90)
        signals['has_dependabot_activity'] = self._detect_dependabot()
        signals['recent_releases_90d'] = self._detect_recent_releases(days=90)
        signals['consistent_commit_pattern'] = self._detect_commit_pattern()

        # Code Organization
        signals['has_tests'] = self._detect_pattern(self.TEST_PATTERNS)
        signals['has_documentation'] = self._detect_documentation()
        signals['has_api_specs'] = self._detect_pattern(self.API_SPEC_PATTERNS)
        signals['has_codeowners'] = self._detect_file_exact('CODEOWNERS') or self._detect_file_exact('.github/CODEOWNERS')
        signals['has_security_md'] = self._detect_pattern(self.SECURITY_PATTERNS)
        signals['is_monorepo'] = self._detect_monorepo()

        # Security Maturity
        signals['has_security_scanning'] = self._detect_pattern(self.SECURITY_SCANNING_PATTERNS)
        signals['has_secret_scanning'] = self._detect_secret_scanning_enabled()
        signals['has_dependency_scanning'] = self._detect_dependency_scanning()
        signals['has_gitleaks_config'] = self._detect_pattern(self.GITLEAKS_PATTERNS)
        signals['has_sast_config'] = self._detect_pattern(self.SAST_PATTERNS)

        logger.info(f"Detected {sum(signals.values())} signals out of {len(signals)} for {self.repo.full_name}")
        return signals

    def _cache_file_tree(self):
        """Cache repository file tree for efficient pattern matching."""
        if self.file_tree_cache is not None:
            return

        try:
            # Get default branch tree
            default_branch = self.repo.default_branch
            tree = self.repo.get_git_tree(default_branch, recursive=True)
            self.file_tree_cache = [item.path for item in tree.tree]
            logger.debug(f"Cached {len(self.file_tree_cache)} files from {self.repo.full_name}")
        except Exception as e:
            logger.warning(f"Failed to cache file tree for {self.repo.full_name}: {e}")
            self.file_tree_cache = []

    def _detect_pattern(self, patterns: list) -> bool:
        """
        Check if any file/directory matches the given patterns.

        Args:
            patterns: List of glob-style patterns or directory names

        Returns:
            True if any pattern matches
        """
        if not self.file_tree_cache:
            return False

        for pattern in patterns:
            # Convert glob pattern to regex
            if '*' in pattern:
                regex_pattern = pattern.replace('.', r'\.').replace('*', '.*')
                regex = re.compile(regex_pattern)
                if any(regex.search(path) for path in self.file_tree_cache):
                    return True
            else:
                # Direct path or directory check
                if pattern.endswith('/'):
                    # Directory check
                    if any(path.startswith(pattern) for path in self.file_tree_cache):
                        return True
                else:
                    # Exact file check
                    if pattern in self.file_tree_cache:
                        return True

        return False

    def _detect_file_exact(self, filename: str) -> bool:
        """Check if exact file exists in repository."""
        return filename in self.file_tree_cache if self.file_tree_cache else False

    def _detect_github_environments(self) -> bool:
        """Check if GitHub environments are configured."""
        try:
            environments = list(self.repo.get_environments())
            return len(environments) > 0
        except Exception as e:
            logger.debug(f"Could not check environments: {e}")
            return False

    def _detect_github_releases(self) -> bool:
        """Check if repository has any releases."""
        try:
            releases = list(self.repo.get_releases()[:1])  # Just check if any exist
            return len(releases) > 0
        except Exception as e:
            logger.debug(f"Could not check releases: {e}")
            return False

    def _detect_branch_protection(self) -> bool:
        """Check if default branch has protection rules."""
        try:
            default_branch = self.repo.get_branch(self.repo.default_branch)
            return default_branch.protected
        except Exception as e:
            logger.debug(f"Could not check branch protection: {e}")
            return False

    def _detect_recent_commits(self, days: int = 30) -> bool:
        """Check if repository has commits in last N days."""
        try:
            from datetime import datetime, timedelta
            since = datetime.now() - timedelta(days=days)
            commits = list(self.repo.get_commits(since=since)[:1])
            return len(commits) > 0
        except Exception as e:
            logger.debug(f"Could not check recent commits: {e}")
            return False

    def _detect_active_prs(self, days: int = 30) -> bool:
        """Check if repository has PRs in last N days."""
        try:
            from datetime import datetime, timedelta
            since = datetime.now() - timedelta(days=days)
            prs = self.repo.get_pulls(state='all', sort='updated', direction='desc')
            recent_prs = [pr for pr in list(prs[:10]) if pr.updated_at >= since]
            return len(recent_prs) > 0
        except Exception as e:
            logger.debug(f"Could not check active PRs: {e}")
            return False

    def _detect_multiple_contributors(self, days: int = 90) -> bool:
        """Check if repository has more than 1 contributor in last N days."""
        try:
            from datetime import datetime, timedelta
            since = datetime.now() - timedelta(days=days)
            commits = list(self.repo.get_commits(since=since)[:100])  # Sample 100 commits
            authors = set(commit.commit.author.email for commit in commits if commit.commit.author)
            return len(authors) > 1
        except Exception as e:
            logger.debug(f"Could not check contributors: {e}")
            return False

    def _detect_dependabot(self) -> bool:
        """Check if Dependabot is active (PRs or commits from dependabot)."""
        try:
            # Check recent commits for dependabot
            commits = list(self.repo.get_commits()[:20])
            for commit in commits:
                if commit.commit.author and 'dependabot' in commit.commit.author.email.lower():
                    return True

            # Check recent PRs for dependabot
            prs = list(self.repo.get_pulls(state='all', sort='updated', direction='desc')[:10])
            for pr in prs:
                if pr.user and 'dependabot' in pr.user.login.lower():
                    return True

            return False
        except Exception as e:
            logger.debug(f"Could not check Dependabot activity: {e}")
            return False

    def _detect_recent_releases(self, days: int = 90) -> bool:
        """Check if repository has releases in last N days."""
        try:
            from datetime import datetime, timedelta
            since = datetime.now() - timedelta(days=days)
            releases = list(self.repo.get_releases()[:5])
            recent_releases = [r for r in releases if r.created_at >= since]
            return len(recent_releases) > 0
        except Exception as e:
            logger.debug(f"Could not check recent releases: {e}")
            return False

    def _detect_commit_pattern(self) -> bool:
        """
        Detect if repository has consistent commit pattern.

        Returns True if commits are spread across multiple weeks (not bursty).
        """
        try:
            from datetime import timedelta
            commits = list(self.repo.get_commits()[:100])
            if len(commits) < 10:
                return False

            # Group by week
            weeks = set()
            for commit in commits:
                week_start = commit.commit.author.date - timedelta(days=commit.commit.author.date.weekday())
                weeks.add(week_start.date())

            # Consistent if commits spread across 4+ different weeks
            return len(weeks) >= 4
        except Exception as e:
            logger.debug(f"Could not detect commit pattern: {e}")
            return False

    def _detect_documentation(self) -> bool:
        """
        Check if repository has meaningful documentation.

        Returns True if has docs/ directory OR README > 500 characters.
        """
        has_docs_dir = self._detect_pattern(self.DOCS_PATTERNS[:-2])  # Exclude README patterns

        # Check README length
        try:
            readme = self.repo.get_readme()
            readme_content = readme.decoded_content.decode('utf-8')
            has_detailed_readme = len(readme_content) > 500
            return has_docs_dir or has_detailed_readme
        except Exception:
            return has_docs_dir

    def _detect_monorepo(self) -> bool:
        """
        Detect if repository is a monorepo.

        Returns True if multiple package manager files exist at different levels.
        """
        package_files_found = []

        for lang, files in self.PACKAGE_PATTERNS.items():
            for package_file in files:
                # Look for package files in subdirectories (not just root)
                matches = [path for path in self.file_tree_cache if path.endswith(package_file)]
                if len(matches) > 1:  # Multiple package files
                    package_files_found.extend(matches)

        # Monorepo if 2+ package files in different directories
        if len(package_files_found) >= 2:
            directories = set(path.rsplit('/', 1)[0] for path in package_files_found if '/' in path)
            return len(directories) >= 2

        return False

    def _detect_secret_scanning_enabled(self) -> bool:
        """Check if GitHub secret scanning is enabled."""
        try:
            # GitHub API doesn't always expose this, infer from settings
            # For now, check if repo has secret scanning alerts configured
            return self.repo.get_vulnerability_alert()
        except Exception:
            return False

    def _detect_dependency_scanning(self) -> bool:
        """Check if Dependabot or similar dependency scanning is configured."""
        try:
            # Check for Dependabot config file
            dependabot_config = self._detect_file_exact('.github/dependabot.yml') or \
                               self._detect_file_exact('.github/dependabot.yaml')

            # Or check for renovate config
            renovate_config = self._detect_file_exact('renovate.json') or \
                            self._detect_file_exact('.renovaterc')

            return dependabot_config or renovate_config
        except Exception as e:
            logger.debug(f"Could not detect dependency scanning: {e}")
            return False
