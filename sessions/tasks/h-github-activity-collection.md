---
status: pending
created: 2025-11-16
updated: 2025-11-22
priority: high
estimated_effort: 2-3 hours
index: phase4-migration
branch: feature/repository-activity-metrics
---

# Enhanced Repository Activity & Webhook Health Monitoring

## Objective

Add enterprise-relevant activity metrics and webhook health monitoring to the Repository model for production deployment at scale (3,800 repositories). This enables accurate activity-based insights and integration health monitoring for GitHub organization management.

## User Story

> "This will be enterprise-org GitHub management, so star_count, fork_count is not important."

Focus on **internal activity metrics** and **webhook integration health** relevant to enterprise development teams:

**Activity Metrics:**
- Commit velocity (total commits) - development activity indicator
- Work backlog (open issues) - team workload visibility
- Work in progress (open PRs) - active development tracking

**Webhook Health Monitoring:**
- Webhook presence and active status - integration health check
- Webhook cadence analysis - detect "Hourly", "2 Hours", "Daily" patterns
- Webhook type detection - JIRA, CI/CD tools, Slack, etc.
- Event frequency baseline - 25 events analyzed for cadence calculation

## Success Criteria

### Phase 1: Documentation Verification (context7 MCP)
- [x] Use context7 MCP to fetch official GitHub GraphQL API documentation for Repository object
- [x] Verify `history.totalCount` field exists and returns total commit count
- [x] Verify `issues(states: OPEN).totalCount` field exists and returns open issue count
- [x] Verify `pullRequests(states: OPEN).totalCount` field exists and returns open PR count
- [x] Use context7 MCP to fetch GitHub REST API webhook documentation
- [x] Verify `/repos/{owner}/{repo}/hooks` endpoint lists webhooks
- [x] Verify `/repos/{owner}/{repo}/hooks/{hook_id}/deliveries` provides delivery history
- [x] Document exact API syntax from official GitHub docs

### Phase 2: Model & Database Implementation
- [ ] Repository model has 7 new fields:
  - Activity: `commit_count`, `open_issues_count`, `open_prs_count` (IntegerField)
  - Webhooks: `has_webhooks`, `active_webhooks_count` (Boolean/IntegerField)
  - Webhooks: `webhook_cadence` (CharField), `webhook_types` (JSONField)
- [ ] Database migration created and applied successfully
- [ ] Migration tested in local Docker environment

### Phase 3: GraphQL & REST API Integration
- [ ] GraphQL query `repository_full.graphql` updated to fetch `pullRequests(states: OPEN).totalCount`
- [ ] Query syntax matches official GitHub documentation from context7 verification
- [ ] REST API webhook collection added to collector (rate-limit optimized)
- [ ] Webhook deliveries fetched (last 25 events per webhook)
- [ ] Query tested against real GitHub repository

### Phase 4: Webhook Analysis Logic
- [ ] Cadence calculation algorithm implemented (median time between 25 events)
- [ ] Cadence classification: "Hourly", "2 Hours", "Daily", "Weekly", "Monthly", "Inactive"
- [ ] Webhook type detection from URL patterns (JIRA, Jenkins, CircleCI, Slack, etc.)
- [ ] Null/missing webhook data handled gracefully

### Phase 5: Collector Parser Updates
- [ ] Collector parser extracts all 7 fields from GraphQL/REST responses
- [ ] Field extraction logic handles null/missing values gracefully
- [ ] Rate limit optimization: 2-3 REST calls per repo (webhooks + deliveries)
- [ ] Progress bar added for initial PAT ingestion (tqdm or Django management command progress)
- [ ] Existing repository sync tested with real GitHub data (dry-run mode)

### Phase 6: Integration & Quality Assurance
- [ ] Admin UI displays new fields in Repository detail view
- [ ] Zero breaking changes to existing 47 enrichment fields or 36 binary signals
- [ ] Insights dashboard can query new fields for activity correlation
- [ ] Full sync tested with at least 10 real repositories with webhooks
- [ ] Webhook health monitoring validated against known webhook configurations

## Context Manifest

### How the GitHub Repository Sync Currently Works

The DefectDojo repository enrichment system uses a GraphQL-first architecture to sync GitHub repository metadata into both the Product model and the Repository model (introduced in migration 0247, November 2025). The sync flow progresses through several distinct stages, each handling specific aspects of data collection and persistence.

**Entry Point - Management Command Flow:**

When `python manage.py sync_github_repositories --incremental` executes, it instantiates `GitHubRepositoryCollector` (dojo/github_collector/collector.py) with `use_graphql=True` by default. The collector initializes two clients: a PyGithub REST client for fallback scenarios and a `GitHubGraphQLClient` (dojo/github_collector/graphql_client.py) for primary operations.

The incremental sync logic (lines 71-99 in collector.py) determines which repositories need updating by comparing GitHub's `updatedAt` timestamp against DefectDojo's last sync time. For a 2,451-repository organization, this typically filters down to 50-100 repos that changed since the previous run, reducing the daily sync from hours to under 5 minutes.

**GraphQL Query Execution:**

The full repository query lives in `dojo/github_collector/queries/repository_full.graphql`. This single GraphQL query replaces 13-18 REST API calls and costs approximately 30-40 GitHub API points per repository. The query structure is carefully designed:

Lines 36-48 fetch commit history: `defaultBranchRef.target.history(first: 50)` retrieves the last 50 commits with a critical `totalCount` field at line 37. This `totalCount` represents the TOTAL number of commits in the default branch (not just the 50 fetched), which is exactly what we need for the `commit_count` field. GitHub's GraphQL API computes this server-side, so there's no additional API cost beyond the existing query.

Lines 138-140 fetch open issues: `issues(states: OPEN) { totalCount }`. This filter-at-query-time pattern means GitHub returns only the count of currently open issues, not all issues. The `totalCount` field here gives us our `open_issues_count` directly.

Lines 115-129 fetch pull request data: `pullRequests(first: 10, states: [OPEN, MERGED, CLOSED], orderBy: {field: UPDATED_AT, direction: DESC})`. **IMPORTANT**: This query currently fetches PRs in ALL states for activity analysis. The `totalCount` at line 120 represents all PRs (open + merged + closed). To get open PR count specifically, we need to ADD a separate query field: `openPullRequests: pullRequests(states: OPEN) { totalCount }`.

**GraphQL Response Parsing:**

When the GraphQL response arrives, `GitHubGraphQLClient._parse_repository_data()` (graphql_client.py:373-423) transforms the raw JSON into a structured dictionary. The parsing happens in stages:

First, `_parse_commit_history()` (lines 425-462) processes the commit data. Line 458 extracts `totalCount` with a defensive `.get('totalCount', 0)` pattern that defaults to 0 if the field is null or missing. This is the EXACT pattern we'll use for the three new activity metrics. The method also calculates contributor counts from the 50-commit sample and extracts the last commit timestamp.

Second, `_parse_pull_requests()` (lines 544-572) processes PR data. Lines 555-560 iterate through the `nodes` array counting PRs in OPEN state to derive `openCount`. This client-side counting works but is inefficient - we should let GitHub's GraphQL do this server-side with a filtered query.

Third, `_parse_connection()` (lines 517-521) is a generic helper for simple totalCount fields. It returns `{'totalCount': connection.get('totalCount', 0)}` with the same defensive pattern. This exact helper is used for environments, branch protection, vulnerability alerts, and issues.

**Metadata Extraction in Collector:**

The parsed GraphQL data flows into `GitHubRepositoryCollector._extract_metadata_from_graphql()` (collector.py:900-944). This is where repository metadata gets mapped to DefectDojo's internal structure. The current implementation:

Line 931: `metadata['commit_count'] = commits.get('totalCount', 0)` - directly extracts commit count from the parsed data. This field ALREADY exists in Product model (lines 1287-1292 in models.py) and is being populated correctly.

Line 934: `metadata['open_issues_count'] = issues.get('totalCount', 0)` - directly extracts open issue count. This field ALREADY exists in Product model (lines 1294-1299 in models.py).

Line 937: `metadata['open_pr_count'] = pull_requests.get('openCount', 0)` - extracts the client-side-calculated open PR count. This field ALREADY exists in Product model (lines 1301-1306 in models.py) but is being populated from the `openCount` derived in the parser, not from a direct GraphQL field.

**CRITICAL INSIGHT**: The Product model ALREADY HAS all three activity metrics we need (commit_count, open_issues_count, open_pr_count) since migration 0255 (November 17, 2025). Lines 1286-1306 in dojo/models.py show these fields defined with IntegerField, default=0, and MinValueValidator(0). They're in the "Enterprise Context Enrichment - Activity Metrics" section.

**Repository Model Sync:**

After extracting metadata, the collector calls `_get_or_create_repository_from_graphql()` (collector.py:789-898). However, examining the `defaults` dictionary construction (lines 833-886), we see a PROBLEM:

Lines 838-841 sync the basic activity fields (last_commit_date, active_contributors_90d, days_since_last_commit) to the Repository model.

Lines 843-851 sync metadata and ownership fields.

Lines 857-885 sync all 36 binary signals.

**But nowhere in this defaults dictionary do we persist commit_count, open_issues_count, or open_pr_count to the Repository model.** The metadata exists in the `metadata` dict but is NOT being written to Repository.defaults. This is the GAP we need to fill.

The sync DOES update the Product model (lines 367-373 in _sync_repository_from_graphql), writing all three counts:
```python
product.commit_count = metadata['commit_count']
product.open_issues_count = metadata['open_issues_count']
product.open_pr_count = metadata['open_pr_count']
```

So the Product model gets updated but Repository does not.

**Webhook Collection via REST API:**

For webhook health monitoring, we'll add a NEW data collection stage using GitHub's REST API v3 (separate rate limit from GraphQL). The workflow:

1. After GraphQL sync completes, call `GET /repos/{owner}/{repo}/hooks` for each repository
2. Parse webhook list: extract `active` status, `events` array, `config.url`
3. For each active webhook, call `GET /repos/{owner}/{repo}/hooks/{hook_id}/deliveries?per_page=25`
4. Analyze delivery timestamps to calculate cadence
5. Parse `config.url` to detect webhook type (JIRA, Jenkins, etc.)

**Rate Limiting Strategy:**
- GraphQL sync: 30-40 points per repo (existing)
- REST webhook calls: 1-2 API calls per repo (separate 5,000/hour limit)
- Total cost: Negligible for 3,800 repos (incremental sync processes 50-100 repos/day)

**Progress Bar Implementation:**

The existing collector (collector.py:166-187) logs progress every 10 repositories. For initial PAT ingestion with 3,800 repos, we'll add a visual progress indicator:

```python
from tqdm import tqdm

# In sync_repositories_batch() or sync_repositories_incremental()
for repo in tqdm(repositories, desc="Syncing repositories", unit="repo"):
    self._sync_repository_from_graphql(repo_data)
```

Or use Django's management command stdout:
```python
self.stdout.write(f"Progress: {index}/{total} repositories ({int(index/total*100)}%)")
```

### For New Feature Implementation: Activity Metrics + Webhook Health

Since we're adding 7 new fields to the Repository model, the implementation must touch EIGHT distinct layers:

**Layer 1: GraphQL Query Enhancement**

The current query at `repository_full.graphql` lines 115-129 needs ONE additional field for open PR count:

```graphql
# EXISTING - keep as-is for activity analysis
pullRequests(first: 10, states: [OPEN, MERGED, CLOSED], ...) {
    totalCount         # All PRs
    nodes { ... }      # For activity signals
}

# NEW - add for open count metric
openPullRequests: pullRequests(states: OPEN) {
    totalCount         # Open PRs only
}
```

This aliased query pattern is standard GraphQL - we're querying the SAME field twice with different filters and assigning different aliases. The cost impact is minimal (roughly +1-2 API points) because GitHub caches the PR data from the first query.

The commit_count and open_issues_count fields ALREADY exist in the GraphQL query at lines 37 and 139 respectively, so no query changes needed for those.

**Layer 2: GraphQL Parser Update**

In `graphql_client.py`, the `_parse_repository_data()` method (line 373) needs to extract the new openPullRequests field:

```python
parsed['openPullRequests'] = self._parse_connection(repo_data.get('openPullRequests'))
```

This uses the existing `_parse_connection()` helper (lines 517-521) which already handles the `{'totalCount': X}` pattern. No new parsing logic needed.

**Layer 3: REST API Webhook Collection**

Add new method to `GitHubRepositoryCollector`:

```python
def _collect_webhook_metadata(self, repo_full_name):
    """Collect webhook health data via REST API."""
    owner, repo_name = repo_full_name.split('/')

    try:
        # List webhooks (1 REST API call)
        hooks = self.github_client.get_repo(repo_full_name).get_hooks()
        hooks_list = list(hooks)

        if not hooks_list:
            return {
                'has_webhooks': False,
                'active_webhooks_count': 0,
                'webhook_cadence': 'Inactive',
                'webhook_types': []
            }

        # Count active webhooks
        active_count = sum(1 for h in hooks_list if h.active)

        # Detect webhook types from URLs
        webhook_types = self._detect_webhook_types(hooks_list)

        # Calculate cadence from delivery history (1 REST call per active webhook)
        cadence = self._calculate_webhook_cadence(repo_full_name, hooks_list)

        return {
            'has_webhooks': True,
            'active_webhooks_count': active_count,
            'webhook_cadence': cadence,
            'webhook_types': webhook_types
        }
    except Exception as e:
        logger.warning(f"Failed to collect webhook metadata for {repo_full_name}: {e}")
        return {
            'has_webhooks': False,
            'active_webhooks_count': 0,
            'webhook_cadence': 'Unknown',
            'webhook_types': []
        }
```

**Layer 4: Webhook Cadence Analysis**

```python
import statistics
from datetime import datetime

def _calculate_webhook_cadence(self, repo_full_name, hooks):
    """Calculate webhook delivery cadence from last 25 events."""
    if not hooks:
        return "Inactive"

    all_deliveries = []

    # Fetch deliveries for each active webhook (max 25 events)
    for hook in hooks:
        if not hook.active:
            continue

        try:
            # REST API: GET /repos/{owner}/{repo}/hooks/{hook_id}/deliveries?per_page=25
            deliveries = hook.get_deliveries(per_page=25)
            all_deliveries.extend(list(deliveries))
        except Exception as e:
            logger.debug(f"Could not fetch deliveries for hook {hook.id}: {e}")
            continue

    if len(all_deliveries) < 2:
        return "Inactive"

    # Sort by delivered_at (most recent first)
    all_deliveries.sort(key=lambda d: d.delivered_at, reverse=True)

    # Take last 25 events across all webhooks
    recent_deliveries = all_deliveries[:25]

    # Calculate time deltas between consecutive deliveries
    deltas = []
    for i in range(len(recent_deliveries) - 1):
        t1 = recent_deliveries[i].delivered_at
        t2 = recent_deliveries[i+1].delivered_at
        delta_seconds = (t1 - t2).total_seconds()
        deltas.append(delta_seconds)

    # Use median to avoid outliers
    median_seconds = statistics.median(deltas)

    # Classify cadence
    if median_seconds < 3600:  # < 1 hour
        return "Hourly"
    elif median_seconds < 7200:  # < 2 hours
        return "2 Hours"
    elif median_seconds < 86400:  # < 1 day
        return "Daily"
    elif median_seconds < 604800:  # < 1 week
        return "Weekly"
    elif median_seconds < 2592000:  # < 30 days
        return "Monthly"
    else:
        return "Inactive"
```

**Layer 5: Webhook Type Detection**

```python
def _detect_webhook_types(self, hooks):
    """Detect webhook integration types from config URLs."""
    types = set()

    for hook in hooks:
        url = hook.config.get('url', '').lower()

        # CI/CD tools
        if 'jenkins' in url:
            types.add('CI/CD - Jenkins')
        elif 'circleci' in url:
            types.add('CI/CD - CircleCI')
        elif 'travis' in url or 'travis-ci' in url:
            types.add('CI/CD - Travis')
        elif 'github' in url and 'actions' in url:
            types.add('CI/CD - GitHub Actions')
        elif 'gitlab' in url:
            types.add('CI/CD - GitLab')
        elif 'bamboo' in url:
            types.add('CI/CD - Bamboo')

        # Issue trackers
        elif 'jira' in url or 'atlassian' in url:
            types.add('JIRA')
        elif 'linear' in url:
            types.add('Linear')

        # Communication
        elif 'slack' in url:
            types.add('Slack')
        elif 'teams' in url or 'microsoft' in url:
            types.add('Microsoft Teams')
        elif 'discord' in url:
            types.add('Discord')

        # Monitoring/Alerting
        elif 'pagerduty' in url:
            types.add('PagerDuty')
        elif 'datadog' in url:
            types.add('Datadog')
        elif 'newrelic' in url:
            types.add('New Relic')
        elif 'sentry' in url:
            types.add('Sentry')

        # Security
        elif 'snyk' in url:
            types.add('Security - Snyk')
        elif 'sonarqube' in url or 'sonarcloud' in url:
            types.add('Security - SonarQube')

        else:
            types.add('Custom')

    return sorted(list(types))
```

**Layer 6: Collector Metadata Extraction**

In `collector.py`, update `_extract_metadata_from_graphql()` method (lines 900-944):

```python
# EXISTING - Activity metrics
metadata['commit_count'] = commits.get('totalCount', 0)
metadata['open_issues_count'] = issues.get('totalCount', 0)

# UPDATED - Use direct GraphQL field for open PRs
open_pull_requests = repo_data.get('openPullRequests', {})
metadata['open_pr_count'] = open_pull_requests.get('totalCount', 0)

# NEW - Webhook health metrics (collected via REST API)
webhook_metadata = self._collect_webhook_metadata(repo_data.get('nameWithOwner'))
metadata.update(webhook_metadata)
```

**Layer 7: Repository Model Persistence**

In `collector.py`, the `_get_or_create_repository_from_graphql()` method (lines 789-898) builds a `defaults` dictionary. Add after line 841:

```python
# Activity tracking
'last_commit_date': metadata['last_commit_date'],
'active_contributors_90d': metadata['active_contributors_90d'],
'days_since_last_commit': metadata['days_since_last_commit'],

# NEW - Activity metrics
'commit_count': metadata['commit_count'],
'open_issues_count': metadata['open_issues_count'],
'open_pr_count': metadata['open_pr_count'],

# NEW - Webhook health metrics
'has_webhooks': metadata['has_webhooks'],
'active_webhooks_count': metadata['active_webhooks_count'],
'webhook_cadence': metadata['webhook_cadence'],
'webhook_types': metadata['webhook_types'],
```

**Layer 8: Repository Model Definition**

In `dojo/models.py`, add 7 new fields in the Repository class after line 1680 (days_since_last_commit field):

```python
# Activity Metrics (Enterprise GitHub Management Insights)
commit_count = models.IntegerField(
    default=0,
    validators=[MinValueValidator(0)],
    verbose_name=_("Total Commits"),
    help_text=_("Total number of commits in default branch")
)
open_issues_count = models.IntegerField(
    default=0,
    validators=[MinValueValidator(0)],
    verbose_name=_("Open Issues"),
    help_text=_("Number of currently open issues")
)
open_pr_count = models.IntegerField(
    default=0,
    validators=[MinValueValidator(0)],
    verbose_name=_("Open Pull Requests"),
    help_text=_("Number of currently open pull requests")
)

# Webhook Health Monitoring (Integration Health Check)
has_webhooks = models.BooleanField(
    default=False,
    verbose_name=_("Has Webhooks"),
    help_text=_("Whether repository has any webhooks configured")
)
active_webhooks_count = models.IntegerField(
    default=0,
    validators=[MinValueValidator(0)],
    verbose_name=_("Active Webhooks"),
    help_text=_("Number of active webhooks configured")
)
webhook_cadence = models.CharField(
    max_length=20,
    default='Inactive',
    choices=[
        ('Hourly', 'Hourly'),
        ('2 Hours', '2 Hours'),
        ('Daily', 'Daily'),
        ('Weekly', 'Weekly'),
        ('Monthly', 'Monthly'),
        ('Inactive', 'Inactive'),
        ('Unknown', 'Unknown'),
    ],
    verbose_name=_("Webhook Cadence"),
    help_text=_("Baseline webhook delivery frequency based on last 25 events")
)
webhook_types = models.JSONField(
    default=list,
    blank=True,
    verbose_name=_("Webhook Types"),
    help_text=_("Detected webhook integration types (JIRA, CI/CD, Slack, etc.)")
)
```

**Database Migration:**

Create migration file `0258_repository_activity_webhook_metrics.py`:

```python
# Generated by Django 5.1.14 on 2025-11-22

import django.core.validators
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('dojo', '0257_github_sync_configuration'),
    ]

    operations = [
        # Activity Metrics
        migrations.AddField(
            model_name='repository',
            name='commit_count',
            field=models.IntegerField(
                default=0,
                help_text='Total number of commits in default branch',
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Total Commits'
            ),
        ),
        migrations.AddField(
            model_name='repository',
            name='open_issues_count',
            field=models.IntegerField(
                default=0,
                help_text='Number of currently open issues',
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Open Issues'
            ),
        ),
        migrations.AddField(
            model_name='repository',
            name='open_pr_count',
            field=models.IntegerField(
                default=0,
                help_text='Number of currently open pull requests',
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Open Pull Requests'
            ),
        ),
        # Webhook Health Metrics
        migrations.AddField(
            model_name='repository',
            name='has_webhooks',
            field=models.BooleanField(
                default=False,
                help_text='Whether repository has any webhooks configured',
                verbose_name='Has Webhooks'
            ),
        ),
        migrations.AddField(
            model_name='repository',
            name='active_webhooks_count',
            field=models.IntegerField(
                default=0,
                help_text='Number of active webhooks configured',
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='Active Webhooks'
            ),
        ),
        migrations.AddField(
            model_name='repository',
            name='webhook_cadence',
            field=models.CharField(
                default='Inactive',
                max_length=20,
                choices=[
                    ('Hourly', 'Hourly'),
                    ('2 Hours', '2 Hours'),
                    ('Daily', 'Daily'),
                    ('Weekly', 'Weekly'),
                    ('Monthly', 'Monthly'),
                    ('Inactive', 'Inactive'),
                    ('Unknown', 'Unknown'),
                ],
                help_text='Baseline webhook delivery frequency based on last 25 events',
                verbose_name='Webhook Cadence'
            ),
        ),
        migrations.AddField(
            model_name='repository',
            name='webhook_types',
            field=models.JSONField(
                default=list,
                blank=True,
                help_text='Detected webhook integration types (JIRA, CI/CD, Slack, etc.)',
                verbose_name='Webhook Types'
            ),
        ),
    ]
```

**Admin UI Update:**

In `dojo/admin.py`, update the RepositoryAdmin fieldsets at lines 155-161:

```python
('Activity Tracking', {
    'fields': (
        'last_commit_date',
        'active_contributors_90d',
        'days_since_last_commit',
        'commit_count',           # NEW
        'open_issues_count',      # NEW
        'open_pr_count',          # NEW
    )
}),
('Webhook Health', {           # NEW FIELDSET
    'fields': (
        'has_webhooks',
        'active_webhooks_count',
        'webhook_cadence',
        'webhook_types',
    )
}),
```

### Technical Reference Details

#### GitHub REST API - Webhooks (Verified via context7 MCP)

**List Repository Webhooks:**
```
GET /repos/{owner}/{repo}/hooks
Response: Array of webhook objects with:
  - id (integer)
  - active (boolean)
  - events (array of strings)
  - config.url (string)
  - created_at, updated_at (timestamps)
```

**List Webhook Deliveries:**
```
GET /repos/{owner}/{repo}/hooks/{hook_id}/deliveries?per_page=25
Response: Array of delivery objects with:
  - id (integer)
  - delivered_at (timestamp)
  - duration (number)
  - status (string)
  - event (string)
  - redelivery (boolean)
```

**Rate Limiting:**
- REST API: 5,000 requests/hour (separate from GraphQL 5,000 points/hour)
- List webhooks: 1 call per repo
- List deliveries: 1 call per active webhook
- Total: 2-3 calls per repo (negligible for incremental sync)

#### Testing Commands

```bash
# Test GraphQL query syntax (GitHub GraphQL Explorer)
# URL: https://docs.github.com/en/graphql/overview/explorer

# Generate migration after model changes
docker compose exec uwsgi bash -c "python manage.py makemigrations"

# Apply migration in local environment
docker compose exec uwsgi bash -c "python manage.py migrate"

# Verify migration in PostgreSQL
docker compose exec postgres psql -U defectdojo -c "\d dojo_repository"

# Dry run sync to test GraphQL + REST integration
docker compose exec uwsgi bash -c "python manage.py sync_github_repositories --dry-run --incremental"

# Sync 10 test repositories with webhooks
docker compose exec uwsgi bash -c "python manage.py sync_github_repositories --max-repos 10"

# Verify data in Django shell
docker compose exec uwsgi bash -c "python manage.py shell -c \"
from dojo.models import Repository
repos = Repository.objects.values(
    'name', 'commit_count', 'open_issues_count', 'open_pr_count',
    'has_webhooks', 'active_webhooks_count', 'webhook_cadence', 'webhook_types'
)[:10]
for repo in repos:
    print(repo)
\""

# Check admin UI (manual step)
# Navigate to: http://localhost:8080/admin/dojo/repository/<id>/change/
```

#### File Paths Summary

**Implementation Files**:
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/models.py` - Add 7 field definitions to Repository class (after line 1680)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/queries/repository_full.graphql` - Add openPullRequests query alias (after line 129)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/graphql_client.py` - Add parser extraction for openPullRequests (after line 421)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/collector.py` - Add webhook collection methods, update metadata extraction (line 937) and repository defaults (after line 841)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/admin.py` - Update RepositoryAdmin fieldsets (lines 156-165)

**Migration File**:
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/db_migrations/0258_repository_activity_webhook_metrics.py` - Create new migration with 7 AddField operations

**Documentation References**:
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/README_GRAPHQL.md` - GraphQL architecture overview
- `/Users/1haris.sid/defectdojo/RepoRelay/CLAUDE.md` - Django migration patterns and testing commands
- GitHub REST API Webhooks: https://docs.github.com/en/rest/repos/webhooks (verified via context7 MCP)

## Relation to GitHub Insights Dashboard

This task is a **prerequisite** for the following insights:

**Activity Insights:**
- Highest Commit Frequency (commits/week) - REQUIRES `commit_count`
- Activity-Vulnerability Correlation - REQUIRES accurate `commit_count`
- Repositories with High Issue Count - REQUIRES `open_issues_count`
- Work in Progress tracking - REQUIRES `open_pr_count`

**NEW - Webhook Health Insights:**
- Integration Health Dashboard - REQUIRES webhook metrics
- Webhook Type Distribution (pie chart) - REQUIRES `webhook_types`
- Webhook Cadence Analysis (bar chart) - REQUIRES `webhook_cadence`
- Inactive Webhook Detection - REQUIRES `active_webhooks_count`

## Implementation Plan

### Step 1: Verify APIs with context7 MCP (15 min)
- [x] Verify GitHub GraphQL API fields for activity metrics
- [x] Verify GitHub REST API webhooks endpoints
- [x] Document exact API syntax and response structures

### Step 2: Add Model Fields (15 min)
1. Edit `dojo/models.py`
2. Add 7 field definitions to Repository class (3 activity + 4 webhook)
3. Use appropriate validators and defaults

### Step 3: Update GraphQL Query (5 min)
1. Edit `dojo/github_collector/queries/repository_full.graphql`
2. Add `openPullRequests: pullRequests(states: OPEN) { totalCount }`

### Step 4: Add Webhook Collection Methods (30 min)
1. Add `_collect_webhook_metadata()` to collector
2. Add `_calculate_webhook_cadence()` with median algorithm
3. Add `_detect_webhook_types()` with URL pattern matching
4. Handle rate limiting and errors gracefully

### Step 5: Update Collector Parser (15 min)
1. Update `_extract_metadata_from_graphql()` to use direct GraphQL field
2. Add webhook metadata collection call
3. Update repository defaults dictionary

### Step 6: Add Progress Bar (10 min)
1. Add tqdm or Django stdout progress indicator
2. Update sync methods to show progress for 3,800 repos

### Step 7: Generate Migration (10 min)
1. Run makemigrations
2. Review generated migration file
3. Apply migration
4. Verify migration success

### Step 8: Testing (30 min)
1. Query sample repositories with webhooks
2. Verify cadence calculation accuracy
3. Verify webhook type detection
4. Check GraphQL query cost
5. Test with missing/null data

### Step 9: Admin UI & Documentation (10 min)
1. Update RepositoryAdmin fieldsets
2. Test admin interface display
3. Update documentation

**Total Estimated Time:** 2-3 hours

## Work Log

### 2025-11-16 - Task Created
- Created task specification for activity metrics
- Identified 3 activity fields (commit_count, open_issues_count, open_pr_count)
- Estimated 30 min - 1 hour effort

### 2025-11-22 - Task Expanded with Webhook Health Monitoring
- Expanded scope to include webhook health monitoring (4 additional fields)
- Used context7 MCP to verify GitHub REST API webhook capabilities
- Documented webhook cadence calculation algorithm (median of 25 events)
- Documented webhook type detection pattern matching
- Updated estimate to 2-3 hours
- Merged context from duplicate task `h-implement-repository-activity-metrics.md`
- Added comprehensive context manifest from context-gathering agent
- Verified all GitHub API endpoints via official documentation
