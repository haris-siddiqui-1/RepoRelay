"""
GitHub setup validation module.

Provides comprehensive validation for GitHub PAT configuration including:
- Token format validation
- Token scope detection via X-OAuth-Scopes header
- Organization/user existence check
- Rate limit availability check
- Test_Type prerequisites check
- Sample repository fetch test

Usage:
    from dojo.github_collector.validator import GitHubValidator

    validator = GitHubValidator(token, account_type, account_name)
    result = validator.validate_full_setup()

    if result['valid']:
        # Proceed with sync
    else:
        # Show errors to user
"""

import logging
import requests
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Required scopes for full GitHub integration
REQUIRED_SCOPES = {'repo', 'read:org', 'security_events'}

# Rate limit thresholds
GRAPHQL_MIN_REMAINING = 1000  # Enough for ~25-30 full repo syncs
REST_MIN_REMAINING = 500  # Enough for ~250 repo alert fetches

# Error codes and messages
ERROR_MESSAGES = {
    'TOKEN_INVALID_FORMAT': {
        'message': "Token must start with 'ghp_' or 'github_pat_'",
        'remediation': "Generate a new token at https://github.com/settings/tokens"
    },
    'TOKEN_EXPIRED': {
        'message': "Token has expired or been revoked",
        'remediation': "Generate a new token at https://github.com/settings/tokens"
    },
    'TOKEN_MISSING_SCOPE_REPO': {
        'message': "Token missing 'repo' scope",
        'remediation': "Regenerate token with 'repo' scope selected"
    },
    'TOKEN_MISSING_SCOPE_ORG': {
        'message': "Token missing 'read:org' scope",
        'remediation': "Regenerate token with 'read:org' scope selected"
    },
    'TOKEN_MISSING_SCOPE_SECURITY': {
        'message': "Token missing 'security_events' scope",
        'remediation': "Regenerate token with 'security_events' scope selected"
    },
    'ACCOUNT_NOT_FOUND': {
        'message': "Organization or user '{name}' not found or not accessible",
        'remediation': "Verify the account name spelling and token access"
    },
    'RATE_LIMIT_EXHAUSTED': {
        'message': "API quota depleted. Resets at {reset_time}",
        'remediation': "Wait for rate limit reset or use a different token"
    },
    'PREREQUISITE_MISSING': {
        'message': "Database missing required Test_Types: {missing}",
        'remediation': "Run: python manage.py migrate"
    },
}


@dataclass
class ValidationCheck:
    """Result of a single validation check."""
    name: str
    status: str  # 'pass', 'fail', 'warning', 'skip'
    message: str = ''
    details: dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Complete validation result."""
    valid: bool
    ready_to_sync: bool
    checks: dict
    warnings: list
    errors: list


class GitHubValidator:
    """
    Validates GitHub setup configuration.

    Performs 6-step validation:
    1. Token format check
    2. Token scope validation
    3. Account existence check
    4. Rate limit availability
    5. Test_Type prerequisites
    6. Sample repository fetch
    """

    GITHUB_API_BASE = 'https://api.github.com'

    def __init__(self, token: str, account_type: str, account_name: str):
        """
        Initialize validator.

        Args:
            token: GitHub Personal Access Token
            account_type: 'organization' or 'user'
            account_name: GitHub org name or username
        """
        self.token = token
        self.account_type = account_type
        self.account_name = account_name
        self._headers = {'Authorization': f'token {token}'} if token else {}
        self._detected_scopes = set()

    def _api_get(self, endpoint: str, timeout: int = 10) -> requests.Response:
        """Make authenticated GET request to GitHub API."""
        url = f"{self.GITHUB_API_BASE}{endpoint}"
        return requests.get(url, headers=self._headers, timeout=timeout)

    def validate_token_format(self) -> ValidationCheck:
        """
        Step 1: Validate token format.

        Valid formats: ghp_* or github_pat_*
        """
        if not self.token:
            return ValidationCheck(
                name='token_format',
                status='fail',
                message="GitHub token is required",
                details={'error_code': 'TOKEN_REQUIRED'}
            )

        if not (self.token.startswith('ghp_') or self.token.startswith('github_pat_')):
            return ValidationCheck(
                name='token_format',
                status='fail',
                message=ERROR_MESSAGES['TOKEN_INVALID_FORMAT']['message'],
                details={
                    'error_code': 'TOKEN_INVALID_FORMAT',
                    'remediation': ERROR_MESSAGES['TOKEN_INVALID_FORMAT']['remediation']
                }
            )

        return ValidationCheck(
            name='token_format',
            status='pass',
            message="Token format valid",
            details={'prefix': self.token[:4] + '...' if len(self.token) > 4 else '***'}
        )

    def validate_token_scopes(self) -> ValidationCheck:
        """
        Step 2: Validate token scopes via X-OAuth-Scopes header.

        Required scopes: repo, read:org, security_events
        """
        try:
            response = self._api_get('/user')

            if response.status_code == 401:
                return ValidationCheck(
                    name='token_scopes',
                    status='fail',
                    message=ERROR_MESSAGES['TOKEN_EXPIRED']['message'],
                    details={
                        'error_code': 'TOKEN_EXPIRED',
                        'remediation': ERROR_MESSAGES['TOKEN_EXPIRED']['remediation']
                    }
                )

            if response.status_code == 403:
                return ValidationCheck(
                    name='token_scopes',
                    status='fail',
                    message="Token lacks required permissions",
                    details={'http_status': 403}
                )

            # Parse scopes from header
            scopes_header = response.headers.get('X-OAuth-Scopes', '')
            self._detected_scopes = {s.strip() for s in scopes_header.split(',') if s.strip()}

            # Check for required scopes
            missing_scopes = REQUIRED_SCOPES - self._detected_scopes

            # Handle 'public_repo' as partial repo scope
            if 'repo' in missing_scopes and 'public_repo' in self._detected_scopes:
                missing_scopes.discard('repo')

            if missing_scopes:
                # Return specific error for first missing scope
                if 'repo' in missing_scopes:
                    error_key = 'TOKEN_MISSING_SCOPE_REPO'
                elif 'read:org' in missing_scopes:
                    error_key = 'TOKEN_MISSING_SCOPE_ORG'
                else:
                    error_key = 'TOKEN_MISSING_SCOPE_SECURITY'

                return ValidationCheck(
                    name='token_scopes',
                    status='fail',
                    message=ERROR_MESSAGES[error_key]['message'],
                    details={
                        'error_code': error_key,
                        'detected_scopes': list(self._detected_scopes),
                        'missing_scopes': list(missing_scopes),
                        'remediation': ERROR_MESSAGES[error_key]['remediation']
                    }
                )

            return ValidationCheck(
                name='token_scopes',
                status='pass',
                message=f"Token scopes verified ({len(self._detected_scopes)} scopes)",
                details={
                    'scopes': list(self._detected_scopes),
                    'required_scopes': list(REQUIRED_SCOPES)
                }
            )

        except requests.Timeout:
            return ValidationCheck(
                name='token_scopes',
                status='fail',
                message="GitHub API request timed out",
                details={'error': 'timeout'}
            )
        except requests.RequestException as e:
            return ValidationCheck(
                name='token_scopes',
                status='fail',
                message=f"Failed to connect to GitHub API: {str(e)}",
                details={'error': str(e)}
            )

    def validate_account_exists(self) -> ValidationCheck:
        """
        Step 3: Validate organization or user exists and is accessible.
        """
        if not self.account_name:
            return ValidationCheck(
                name='account_exists',
                status='fail',
                message="Account name is required",
                details={'error_code': 'ACCOUNT_REQUIRED'}
            )

        try:
            # Try org endpoint first, then user endpoint
            if self.account_type == 'organization':
                response = self._api_get(f'/orgs/{self.account_name}')
            else:
                response = self._api_get(f'/users/{self.account_name}')

            if response.status_code == 404:
                return ValidationCheck(
                    name='account_exists',
                    status='fail',
                    message=ERROR_MESSAGES['ACCOUNT_NOT_FOUND']['message'].format(name=self.account_name),
                    details={
                        'error_code': 'ACCOUNT_NOT_FOUND',
                        'account_type': self.account_type,
                        'account_name': self.account_name,
                        'remediation': ERROR_MESSAGES['ACCOUNT_NOT_FOUND']['remediation']
                    }
                )

            if response.status_code == 403:
                return ValidationCheck(
                    name='account_exists',
                    status='fail',
                    message=f"You don't have access to {self.account_type} '{self.account_name}'",
                    details={
                        'error_code': 'ACCOUNT_ACCESS_DENIED',
                        'account_type': self.account_type,
                        'account_name': self.account_name
                    }
                )

            if response.status_code != 200:
                return ValidationCheck(
                    name='account_exists',
                    status='warning',
                    message=f"Unexpected response checking account: HTTP {response.status_code}",
                    details={'http_status': response.status_code}
                )

            # Get repository count
            data = response.json()
            repo_count = data.get('public_repos', 0) + data.get('total_private_repos', 0)

            return ValidationCheck(
                name='account_exists',
                status='pass',
                message=f"{self.account_type.title()} '{self.account_name}' accessible",
                details={
                    'account_type': self.account_type,
                    'account_name': self.account_name,
                    'repository_count': repo_count
                }
            )

        except requests.RequestException as e:
            return ValidationCheck(
                name='account_exists',
                status='fail',
                message=f"Failed to check account: {str(e)}",
                details={'error': str(e)}
            )

    def check_rate_limits(self) -> ValidationCheck:
        """
        Step 4: Check rate limit availability.

        Thresholds:
        - GraphQL: >= 1000 points remaining
        - REST: >= 500 calls remaining
        """
        try:
            response = self._api_get('/rate_limit')

            if response.status_code != 200:
                return ValidationCheck(
                    name='rate_limits',
                    status='warning',
                    message=f"Could not check rate limits: HTTP {response.status_code}",
                    details={'http_status': response.status_code}
                )

            data = response.json()
            resources = data.get('resources', {})

            graphql = resources.get('graphql', {})
            core = resources.get('core', {})

            graphql_remaining = graphql.get('remaining', 0)
            graphql_limit = graphql.get('limit', 5000)
            graphql_reset = graphql.get('reset', 0)

            rest_remaining = core.get('remaining', 0)
            rest_limit = core.get('limit', 5000)
            rest_reset = core.get('reset', 0)

            # Check if we have enough quota
            issues = []
            if graphql_remaining < GRAPHQL_MIN_REMAINING:
                issues.append(f"GraphQL: {graphql_remaining}/{graphql_limit} (need {GRAPHQL_MIN_REMAINING})")
            if rest_remaining < REST_MIN_REMAINING:
                issues.append(f"REST: {rest_remaining}/{rest_limit} (need {REST_MIN_REMAINING})")

            if issues:
                from datetime import datetime
                reset_time = datetime.fromtimestamp(max(graphql_reset, rest_reset)).strftime('%H:%M:%S')
                return ValidationCheck(
                    name='rate_limits',
                    status='fail',
                    message=ERROR_MESSAGES['RATE_LIMIT_EXHAUSTED']['message'].format(reset_time=reset_time),
                    details={
                        'error_code': 'RATE_LIMIT_EXHAUSTED',
                        'graphql_remaining': graphql_remaining,
                        'graphql_limit': graphql_limit,
                        'rest_remaining': rest_remaining,
                        'rest_limit': rest_limit,
                        'reset_time': reset_time,
                        'issues': issues,
                        'remediation': ERROR_MESSAGES['RATE_LIMIT_EXHAUSTED']['remediation']
                    }
                )

            return ValidationCheck(
                name='rate_limits',
                status='pass',
                message=f"Rate limits OK (GraphQL: {graphql_remaining}/{graphql_limit}, REST: {rest_remaining}/{rest_limit})",
                details={
                    'graphql_remaining': graphql_remaining,
                    'graphql_limit': graphql_limit,
                    'rest_remaining': rest_remaining,
                    'rest_limit': rest_limit
                }
            )

        except requests.RequestException as e:
            return ValidationCheck(
                name='rate_limits',
                status='warning',
                message=f"Could not check rate limits: {str(e)}",
                details={'error': str(e)}
            )

    def check_test_type_prerequisites(self) -> ValidationCheck:
        """
        Step 5: Check that required Test_Type records exist in database.

        Required: GitHub Dependabot, GitHub CodeQL, GitHub Secret Scanning
        """
        try:
            from dojo.models import Test_Type

            required_types = ['GitHub Dependabot', 'GitHub CodeQL', 'GitHub Secret Scanning']
            existing = set(Test_Type.objects.filter(name__in=required_types).values_list('name', flat=True))
            missing = set(required_types) - existing

            if missing:
                return ValidationCheck(
                    name='prerequisites',
                    status='fail',
                    message=ERROR_MESSAGES['PREREQUISITE_MISSING']['message'].format(missing=', '.join(missing)),
                    details={
                        'error_code': 'PREREQUISITE_MISSING',
                        'required_types': required_types,
                        'existing_types': list(existing),
                        'missing_types': list(missing),
                        'remediation': ERROR_MESSAGES['PREREQUISITE_MISSING']['remediation']
                    }
                )

            return ValidationCheck(
                name='prerequisites',
                status='pass',
                message="Database prerequisites met",
                details={
                    'required_types': required_types,
                    'all_present': True
                }
            )

        except Exception as e:
            return ValidationCheck(
                name='prerequisites',
                status='fail',
                message=f"Failed to check prerequisites: {str(e)}",
                details={'error': str(e)}
            )

    def validate_sample_fetch(self) -> ValidationCheck:
        """
        Step 6: Test fetching a sample repository from the account.

        Verifies end-to-end API access with actual data retrieval.
        """
        try:
            # Fetch first repository from org/user
            if self.account_type == 'organization':
                endpoint = f'/orgs/{self.account_name}/repos?per_page=1&sort=updated'
            else:
                endpoint = f'/users/{self.account_name}/repos?per_page=1&sort=updated'

            response = self._api_get(endpoint)

            if response.status_code == 404:
                return ValidationCheck(
                    name='sample_fetch',
                    status='fail',
                    message=f"Could not access repositories for '{self.account_name}'",
                    details={'http_status': 404}
                )

            if response.status_code != 200:
                return ValidationCheck(
                    name='sample_fetch',
                    status='warning',
                    message=f"Unexpected response fetching repositories: HTTP {response.status_code}",
                    details={'http_status': response.status_code}
                )

            repos = response.json()

            if not repos:
                return ValidationCheck(
                    name='sample_fetch',
                    status='pass',
                    message="No repositories found (empty account is valid)",
                    details={'repository_count': 0}
                )

            sample_repo = repos[0]
            return ValidationCheck(
                name='sample_fetch',
                status='pass',
                message=f"Successfully fetched sample repository: {sample_repo.get('name', 'unknown')}",
                details={
                    'sample_repo': sample_repo.get('full_name'),
                    'sample_repo_id': sample_repo.get('id'),
                    'sample_repo_updated': sample_repo.get('updated_at')
                }
            )

        except requests.RequestException as e:
            return ValidationCheck(
                name='sample_fetch',
                status='fail',
                message=f"Failed to fetch sample repository: {str(e)}",
                details={'error': str(e)}
            )

    def validate_full_setup(self) -> ValidationResult:
        """
        Run all 6 validation checks and return complete result.

        Returns:
            ValidationResult with valid, ready_to_sync, checks dict, warnings, errors
        """
        checks = {}
        warnings = []
        errors = []

        # Run all checks in order
        check_methods = [
            self.validate_token_format,
            self.validate_token_scopes,
            self.validate_account_exists,
            self.check_rate_limits,
            self.check_test_type_prerequisites,
            self.validate_sample_fetch,
        ]

        for method in check_methods:
            check = method()
            checks[check.name] = {
                'status': check.status,
                'message': check.message,
                **check.details
            }

            if check.status == 'fail':
                errors.append({
                    'check': check.name,
                    'message': check.message,
                    'details': check.details
                })
            elif check.status == 'warning':
                warnings.append({
                    'check': check.name,
                    'message': check.message,
                    'details': check.details
                })

        # Determine overall status
        has_failures = any(c['status'] == 'fail' for c in checks.values())
        valid = not has_failures
        ready_to_sync = valid and len(warnings) == 0

        return ValidationResult(
            valid=valid,
            ready_to_sync=ready_to_sync,
            checks=checks,
            warnings=warnings,
            errors=errors
        )

    def to_dict(self, result: ValidationResult) -> dict:
        """Convert ValidationResult to JSON-serializable dict."""
        return {
            'valid': result.valid,
            'ready_to_sync': result.ready_to_sync,
            'checks': result.checks,
            'warnings': result.warnings,
            'errors': result.errors
        }
