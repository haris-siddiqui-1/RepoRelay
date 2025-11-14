# GitHub Alerts Collection - Phase 2 Implementation

This document describes the GitHub security alerts collection system implemented in Phase 2 of the GitHub Alerts Hierarchy project.

## Overview

The alerts collection system fetches and stores GitHub security alerts (Dependabot, CodeQL, Secret Scanning) for repositories tracked in DefectDojo. This enables centralized vulnerability management across all GitHub repositories.

## Architecture

### Components

1. **Data Models** (`dojo/models.py`)
   - `GitHubAlert`: Stores raw GitHub alerts (all three types)
   - `GitHubAlertSync`: Tracks sync status per repository

2. **GraphQL Client Extension** (`dojo/github_collector/graphql_client.py`)
   - `get_dependabot_alerts()`: Fetch Dependabot vulnerability alerts
   - `_parse_dependabot_alert()`: Parse GraphQL response

3. **REST API Client** (`dojo/github_collector/rest_client.py`)
   - `get_codeql_alerts()`: Fetch CodeQL (Code Scanning) alerts
   - `get_secret_scanning_alerts()`: Fetch Secret Scanning alerts
   - Rate limit monitoring for REST API

4. **Alerts Collector** (`dojo/github_collector/alerts_collector.py`)
   - `GitHubAlertsCollector`: Main service class
   - `sync_repository_alerts()`: Sync all alert types for a repository
   - `sync_organization_alerts()`: Batch sync for multiple repositories
   - Incremental sync logic
   - Rate limit management

5. **Management Command** (`dojo/management/commands/sync_github_alerts.py`)
   - CLI interface for manual and scheduled syncs
   - Support for dry-run, force sync, and filtering

## Data Models

### GitHubAlert Model

Stores raw GitHub security alerts with the following fields:

**Core Fields:**
- `repository` (ForeignKey): Associated Repository
- `alert_type` (CharField): Alert type (dependabot, codeql, secret_scanning)
- `github_alert_id` (CharField): Alert number in GitHub
- `state` (CharField): Alert state (open, dismissed, fixed, resolved)
- `severity` (CharField): Severity level
- `title` (CharField): Alert title
- `description` (TextField): Detailed description
- `html_url` (URLField): Link to alert on GitHub

**Type-Specific Fields:**
- Dependabot: `cve`, `package_name`
- CodeQL: `cwe`, `rule_id`, `file_path`
- Secret Scanning: `secret_type`

**Metadata:**
- `raw_data` (JSONField): Complete GitHub API response
- `created_at`, `updated_at`, `dismissed_at`, `fixed_at`

**Phase 3 Integration:**
- `finding` (ForeignKey): Link to DefectDojo Finding (set in Phase 3)

**Unique Constraint:**
```python
unique_together = [['repository', 'alert_type', 'github_alert_id']]
```

### GitHubAlertSync Model

Tracks sync status per repository:

**Sync Timestamps:**
- `dependabot_last_sync`
- `codeql_last_sync`
- `secret_scanning_last_sync`

**Statistics:**
- `dependabot_alerts_fetched`
- `codeql_alerts_fetched`
- `secret_scanning_alerts_fetched`

**Error Tracking:**
- `last_sync_error`
- `last_sync_error_at`
- `last_rate_limit_hit`

**Properties:**
- `last_successful_sync`: Most recent successful sync across all types
- `total_alerts_fetched`: Sum of all alert types

## API Integration

### Dependabot Alerts (GraphQL)

**Query:** `dojo/github_collector/queries/dependabot_alerts.graphql`

**Endpoint:** `https://api.github.com/graphql`

**Fetches:**
- Alert state (OPEN, DISMISSED, FIXED, AUTO_DISMISSED)
- Security advisory (GHSA ID, CVE, CWE, CVSS score)
- Package information (name, ecosystem, vulnerable version)
- Manifest file location

**Performance:**
- Cost: ~5-10 points per repository
- Pagination: 100 alerts per page
- Rate limit: 5,000 points/hour

**Example Usage:**
```python
from dojo.github_collector.graphql_client import GitHubGraphQLClient

client = GitHubGraphQLClient(github_token)
alerts = client.get_dependabot_alerts(
    owner="myorg",
    name="myrepo",
    states=None  # Fetch all states
)
```

### CodeQL Alerts (REST API)

**Endpoint:** `/repos/{owner}/{repo}/code-scanning/alerts`

**Fetches:**
- Alert state (open, dismissed, fixed)
- Rule information (ID, name, severity, description)
- CWE from rule tags
- Location (file path, line numbers)

**Performance:**
- Cost: 1-2 API calls per repository
- Pagination: 100 alerts per page
- Rate limit: 5,000 requests/hour

**Example Usage:**
```python
from dojo.github_collector.rest_client import GitHubRestClient

client = GitHubRestClient(github_token)
alerts = client.get_codeql_alerts(
    owner="myorg",
    name="myrepo",
    state=None  # Fetch all states
)
```

### Secret Scanning Alerts (REST API)

**Endpoint:** `/repos/{owner}/{repo}/secret-scanning/alerts`

**Fetches:**
- Alert state (open, resolved)
- Secret type (e.g., "github_token", "aws_access_key")
- Resolution (false_positive, wont_fix, revoked, used_in_tests)
- Locations (can be multiple per alert)

**Performance:**
- Cost: 1-2 API calls per repository
- Pagination: 100 alerts per page
- Rate limit: 5,000 requests/hour

**Example Usage:**
```python
from dojo.github_collector.rest_client import GitHubRestClient

client = GitHubRestClient(github_token)
alerts = client.get_secret_scanning_alerts(
    owner="myorg",
    name="myrepo",
    state=None  # Fetch all states
)
```

## Incremental Sync Logic

The collector implements intelligent incremental syncing to minimize API calls:

### Sync Interval

**Minimum Interval:** 1 hour (configurable via `MIN_SYNC_INTERVAL`)

Repositories are skipped if:
- `last_successful_sync` < 1 hour ago
- Unless `force=True` is specified

### Sync Selection

```python
# Get repositories needing sync
repositories = collector._get_repositories_for_sync(
    force=False,  # Respect minimum interval
    limit=100     # Optional limit for testing
)
```

**Selection Criteria:**
1. Repository has `github_repo_id` set
2. Last sync older than minimum interval OR never synced
3. Ordered by `last_alert_sync` (oldest first)

### State Change Detection

All alert states are fetched on each sync to detect state transitions:

**Dependabot States:**
- OPEN → DISMISSED (user action)
- OPEN → FIXED (patched)
- OPEN → AUTO_DISMISSED (GitHub automated)

**CodeQL States:**
- open → dismissed → fixed

**Secret Scanning States:**
- open → resolved

State changes trigger Finding status updates in Phase 3.

## Rate Limit Management

### Thresholds

**GraphQL:** 80% of 5,000 points/hour (4,000 points)
**REST API:** 80% of 5,000 requests/hour (4,000 requests)

### Monitoring

Rate limit info is logged after each API call:

```
INFO Rate limit: cost=5, remaining=4850, reset=2024-01-15T12:00:00Z
WARNING Rate limit running low: 450 points remaining
```

### Pause Logic

```python
if collector._should_pause_for_rate_limits():
    logger.warning("Rate limit threshold reached, pausing sync")
    break
```

Currently returns `False` (no pause) - placeholder for future enhancement to query actual rate limit status from GitHub APIs.

## Error Handling

### Sync Failures

Errors are tracked in `GitHubAlertSync.last_sync_error`:

```python
try:
    result = collector.sync_repository_alerts(repository)
except Exception as e:
    sync_tracker.last_sync_error = str(e)[:1000]  # Truncate
    sync_tracker.last_sync_error_at = timezone.now()
    sync_tracker.save()
```

### API Errors

**404 Errors:** Logged as warnings (feature not enabled)
```
WARNING CodeQL not enabled or no access for myorg/myrepo
```

**Other Errors:** Logged as errors and re-raised
```
ERROR HTTP error fetching CodeQL alerts: 403 Forbidden
```

### Repository Parsing

If owner/name cannot be parsed from `github_url` or `name`:
```python
result.success = False
result.errors.append("Could not parse repository owner/name")
```

## Management Command

### Basic Usage

```bash
# Sync all repositories (respects minimum interval)
python manage.py sync_github_alerts

# Force sync all repositories
python manage.py sync_github_alerts --force

# Sync specific repository
python manage.py sync_github_alerts --repository-id 123

# Limit number of repositories (for testing)
python manage.py sync_github_alerts --limit 10

# Dry run
python manage.py sync_github_alerts --dry-run
```

### Advanced Options

```bash
# Custom GitHub token
python manage.py sync_github_alerts --token ghp_custom_token

# Verbose output
python manage.py sync_github_alerts --verbosity 2

# Very verbose (debug logging)
python manage.py sync_github_alerts --verbosity 3
```

### Cron Job Setup

**Daily incremental sync (recommended):**
```cron
# Run every day at 2 AM
0 2 * * * cd /app && python manage.py sync_github_alerts >> /var/log/github_alerts_sync.log 2>&1
```

**Hourly sync for critical repos:**
```cron
# Run every hour
0 * * * * cd /app && python manage.py sync_github_alerts --limit 50 >> /var/log/github_alerts_sync_hourly.log 2>&1
```

## Testing

### Unit Tests

Location: `unittests/test_github_alerts_collector.py`

**Test Coverage:**
- Collector initialization
- Successful sync of all alert types
- Incremental sync (respects interval)
- Force sync (ignores interval)
- Alert update on resync
- API error handling
- Repository identifier parsing
- Sync selection logic

**Run Tests:**
```bash
# Run all alerts collector tests
./run-unittest.sh --test-case unittests.test_github_alerts_collector.TestGitHubAlertsCollector

# Run with verbose output
./run-unittest.sh --test-case unittests.test_github_alerts_collector.TestGitHubAlertsCollector -v3
```

### Manual Testing

**Test with single repository:**
```bash
# Dry run first
python manage.py sync_github_alerts --repository-id 123 --dry-run

# Actual sync
python manage.py sync_github_alerts --repository-id 123 --verbosity 3
```

**Check results:**
```python
from dojo.models import Repository, GitHubAlert, GitHubAlertSync

repo = Repository.objects.get(id=123)
alerts = GitHubAlert.objects.filter(repository=repo)
sync_status = repo.alert_sync_status

print(f"Total alerts: {alerts.count()}")
print(f"Dependabot: {alerts.filter(alert_type='dependabot').count()}")
print(f"CodeQL: {alerts.filter(alert_type='codeql').count()}")
print(f"Secrets: {alerts.filter(alert_type='secret_scanning').count()}")
print(f"Last sync: {sync_status.last_successful_sync}")
```

## Performance Metrics

### Expected API Costs

**Per Repository:**
- Dependabot: 5-10 GraphQL points
- CodeQL: 1-2 REST calls
- Secret Scanning: 1-2 REST calls

**For 100 Repositories:**
- GraphQL: 500-1,000 points (10-12 minutes at 5,000/hour)
- REST: 200-400 calls (2-5 minutes at 5,000/hour)
- **Total: ~15 minutes** (assuming minimal alerts, no pagination)

**With Pagination (500+ alerts per repo):**
- GraphQL: 50-100 points per repo
- REST: 5-10 calls per repo
- **Total: ~1-2 hours for 100 repos**

### Incremental Sync Performance

**Daily Incremental (Typical):**
- Changed repos: 10-50 (not 2,451)
- Time: <5 minutes
- GraphQL cost: 50-500 points
- REST cost: 20-100 calls

## Future Enhancements (Phase 3 & Beyond)

### Phase 3: Finding Integration
- Map GitHubAlert → Finding
- Bidirectional state sync
- Deduplication via `unique_id_from_tool`

### Phase 4: Advanced Features
- Webhook support for real-time alerts
- Alert severity customization
- Auto-triage rules
- Slack/email notifications

### Phase 5: Analytics
- Alert trends over time
- Repository security score
- Team/organization dashboards

## Troubleshooting

### Common Issues

**1. No alerts fetched**
```
Check:
- GitHub token has security_events scope
- Repository has security features enabled
- GitHub API permissions
```

**2. 404 errors for CodeQL/Secrets**
```
This is normal - features may not be enabled on repository.
Solution: Enable features in GitHub repo settings.
```

**3. Rate limit errors**
```
Wait for rate limit reset (logged in error message).
Solution: Reduce sync frequency or increase API quota.
```

**4. Sync fails silently**
```
Check:
- GitHubAlertSync.last_sync_error for error message
- Django logs for detailed stack traces
```

### Debug Logging

Enable debug logging for detailed output:

```python
import logging

logger = logging.getLogger('dojo.github_collector')
logger.setLevel(logging.DEBUG)
```

Or via management command:
```bash
python manage.py sync_github_alerts --verbosity 3
```

## References

- [GitHub GraphQL API Documentation](https://docs.github.com/en/graphql)
- [GitHub REST API Documentation](https://docs.github.com/en/rest)
- [Dependabot Alerts API](https://docs.github.com/en/rest/dependabot/alerts)
- [Code Scanning API](https://docs.github.com/en/rest/code-scanning)
- [Secret Scanning API](https://docs.github.com/en/rest/secret-scanning)

## Related Documentation

- `README_GRAPHQL.md`: GraphQL migration for repository metadata
- `ARCHITECTURE_DECISION.md`: Design decisions for GitHub collector
- `sessions/tasks/h-implement-github-alerts-hierarchy/README.md`: Full project spec
