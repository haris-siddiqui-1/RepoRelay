---
name: h-research-github-ingestion-validation-strategy
branch: none
status: pending
created: 2025-11-26
---

# GitHub Ingestion Validation Strategy

## Problem/Goal
Develop a comprehensive validation strategy that provides confidence and assurance that:
1. A user can provide just a GitHub PAT (and optionally org name) and successfully ingest all their data
2. Real production data (not test data) flows through and powers all metrics/dashboards
3. The entire data pipeline from GitHub API → DefectDojo models → Insights Dashboard works end-to-end

This strategy should identify gaps, create validation checkpoints, and potentially spawn implementation tasks for automated validation tooling.

## Success Criteria
- [ ] Document current data flow from PAT configuration to metrics display
- [ ] Identify all failure points and validation gaps in the pipeline
- [ ] Create validation checklist spec for "first-time setup" experience
- [ ] Spec automated smoke tests for data ingestion verification
- [ ] Document test fixtures vs production data separation
- [ ] Spec user-facing validation feedback mechanisms
- [ ] Produce strategy document with implementation task recommendations

## Context Manifest

### How the PAT Configuration Flow Currently Works

**Entry Point: Web UI Configuration** (`/github/sync/configuration`)

When a user first configures GitHub ingestion, they interact with a staff/superuser-only web form located at `/github/sync/configuration`. This view is powered by `dojo/github_collector/views.py:github_sync_configuration()` (lines 58-145) and uses the **GitHubSyncConfiguration** singleton model (pk=1) stored at `dojo/models.py:6024-6136`.

The configuration flow has **two validation checkpoints**:

1. **Token Format Validation** (`dojo/github_collector/views.py:validate_github_token()`, lines 23-53):
   - Checks token starts with `ghp_` or `github_pat_`
   - Makes test API call to `https://api.github.com/user` with token
   - Returns specific error messages: "Invalid GitHub token - authentication failed" (401), "GitHub token lacks required permissions" (403)
   - If API unreachable, validation passes (doesn't fail on network errors)

2. **Account Name Validation** (`views.py:94`):
   - Simple presence check - ensures account_name field is not empty
   - No validation that the account actually exists on GitHub

**Token Storage**: Tokens are stored in the `github_token` CharField (max 255 chars) with a comment indicating they should be encrypted in production, but the actual implementation does NOT encrypt the token - it's stored in plaintext in the PostgreSQL database. This is a **validation gap**.

**Configuration Persistence**: The singleton pattern is enforced in `GitHubSyncConfiguration.save()` (lines 6129-6135) - if a record exists, it overwrites pk instead of creating new record.

**Manual Sync Trigger**: When user clicks "Trigger Sync Now" button, the view calls Django's `call_command('sync_github_repositories')` synchronously (lines 112-117), which means the HTTP request blocks until sync completes. For large organizations, this can cause request timeouts. Sync status is tracked in three fields: `last_sync` (timestamp), `last_sync_status` ('success'/'failed'), `last_sync_error` (text).

### Data Ingestion Pipeline: GitHub API → DefectDojo Models

**Phase 1: Repository Metadata Collection**

The sync process begins when `python manage.py sync_github_repositories` is invoked (either via web UI or command line). The management command (`dojo/management/commands/sync_github_repositories.py`) initializes the **GitHubRepositoryCollector** (`dojo/github_collector/collector.py`).

**Dual API Strategy**: The collector uses **GraphQL API v4 by default** for bulk operations (15-20x faster) with automatic fallback to REST API:
- GraphQL path: `collector._sync_all_with_graphql()` (lines 118-199)
- REST path: `collector._sync_all_with_rest()` (lines 201-270)
- Individual syncs: Always use REST API via `sync_product_from_github_url()` (lines 365-444)

**GraphQL Bulk Sync Flow** (Incremental Logic):
1. Calculate `updated_since` threshold from most recent `Product.updated` timestamp
2. Query GitHub GraphQL with `updatedAt > updated_since` filter (organization.graphql or user.graphql)
3. For each returned repo, call `_sync_repository_from_graphql()` which:
   - Creates or updates **Repository** record (47 enrichment fields)
   - **Dual-populates** activity metrics to both Repository AND Product models (lines 822-862)
   - Applies XSS sanitization with `bleach.clean()` to all external data (README summaries, CODEOWNERS content)
   - Collects webhook health metadata if admin:repo_hook permission available (graceful fallback to False/0/Inactive/[] if missing)

**Repository Model Fields** (`dojo/models.py:1623-1943`):
- Core: `name`, `github_repo_id` (unique), `github_url`, `product` (ForeignKey)
- Activity: `last_commit_date`, `active_contributors_90d`, `days_since_last_commit`, `commit_count`, `open_issues_count`, `open_pr_count`
- Webhook Health: `has_webhooks`, `active_webhooks_count`, `webhook_cadence`, `webhook_types` (JSONField)
- Binary Signals: 36 boolean fields across 5 categories (deployment, production, development, organization, security)
- Tier: `tier` (tier1/tier2/tier3/tier4/archived) computed from signals and activity

**REST API Path**: Fetches single repository with PyGithub, collects metadata via multiple API calls (commits, contributors, CODEOWNERS, webhooks), applies same dual-population and sanitization.

**Phase 2: Security Alerts Collection**

After repository metadata sync, security alerts are collected via `python manage.py sync_github_alerts --create-findings`. The **GitHubAlertsCollector** (`dojo/github_collector/alerts_collector.py`) handles three alert types:

1. **Dependabot Alerts** (GraphQL): `graphql_client.get_dependabot_alerts()` fetches vulnerability advisories with CVE, package info, patched versions
2. **CodeQL Alerts** (REST): `rest_client.get_codeql_alerts()` fetches code scanning results with CWE, rule IDs, file locations
3. **Secret Scanning Alerts** (REST): `rest_client.get_secret_scanning_alerts()` fetches exposed secrets with secret types

**Alert Storage** (`dojo/models.py:1945-2200`): Raw alerts are stored in **GitHubAlert** model with:
- Core: `repository` (FK), `alert_type`, `github_alert_id`, `state` (open/dismissed/fixed), `severity`, `title`, `description`, `html_url`
- Type-specific: Dependabot (`cve`, `package_name`, `package_ecosystem`, `vulnerable_version`, `patched_version`), CodeQL (`cwe`, `rule_id`, `file_path`, `start_line`, `end_line`), Secret Scanning (`secret_type`)
- Raw data: `raw_data` (JSONField) stores complete GitHub API response
- Timestamps: `created_at`, `updated_at`, `dismissed_at`, `fixed_at`
- **Finding link**: `finding` (ForeignKey to Finding, set during conversion)

**Unique Constraint**: `['repository', 'alert_type', 'github_alert_id']` prevents duplicate alert storage.

**Sync Tracking**: **GitHubAlertSync** model (`dojo/models.py:2201-2283`) tracks per-repository sync status with timestamps per alert type (`dependabot_last_sync`, `codeql_last_sync`, `secret_scanning_last_sync`), fetch counts, error tracking, and rate limit hits.

**Incremental Sync Logic**: `_should_sync()` method checks if repository was synced within `MIN_SYNC_INTERVAL` (1 hour) to prevent redundant API calls.

**Phase 3: Finding Conversion**

When `--create-findings` flag is used, **GitHubFindingsConverter** (`dojo/github_collector/findings_converter.py`) converts GitHubAlert records to DefectDojo Finding objects:

**Engagement & Test Creation**:
1. `_get_or_create_engagement()` creates one Engagement per repository: "GitHub Security Alerts - {repo_name}" (lines 99-138)
2. `_get_or_create_test()` creates three Tests per repository (one per alert type): "GitHub Dependabot", "GitHub CodeQL", "GitHub Secret Scanning" (lines 140-199)
3. Test_Type records are created during migration (see `dojo/db_migrations/0258_github_alert_test_types.py`)

**Deduplication via unique_id_from_tool**:
- Format: `"github-{alert_type}-{repo_id}-{alert_number}"` (line 213)
- Example: `"github-dependabot-950345562-42"`
- This ensures: same alert in different repos = different findings, state changes update existing finding (not create duplicate), re-imports detect state transitions

**Finding Field Mapping** (lines 215-349):
- Dependabot → Finding: Maps CVE, package info, patched version to mitigation, severity mapping (critical→Critical, moderate→Medium, etc.)
- CodeQL → Finding: Maps CWE, rule ID, file path/line numbers to description
- Secret Scanning → Finding: Maps secret type to title, location info to description
- All types: `unique_id_from_tool` for deduplication, `vuln_id_from_tool` = GitHub alert ID, `references` = GitHub URL

**State Synchronization** (`sync_repository_findings()`, lines 414-526):
- Iterates all GitHubAlert records for repository
- For each alert: get_or_create Finding using `unique_id_from_tool`
- Updates existing findings when alert state changes (open→fixed triggers `Finding.mitigated` timestamp)
- Closes findings when GitHub alerts are fixed/dismissed

### Insights/Metrics Pipeline: Repository/Finding → Dashboard

**Insights Architecture** (`dojo/github_collector/insights/`):

The insights system uses a **pluggable architecture** with BaseInsight abstract class and InsightRegistry pattern:

1. **BaseInsight** (`insights/base.py`): Defines common interface with `calculate(filters) -> Dict` method
2. **InsightRegistry** (`insights/registry.py`): Auto-discovery mechanism that registers all insight classes via `autodiscover()`
3. **25 Built-in Insights** across 5 categories:
   - Activity (`insights/activity.py`): Most updated repos, stale repos, commit frequency, active contributors, recently created
   - Health (`insights/health.py`): Missing README, missing CI/CD, old PRs, high issue count, stale repos
   - Security (`insights/security.py`): Vulnerability distribution (pie chart), vuln by type (bar chart), critical trend (line chart), repos with most critical findings, activity-vuln correlation (scatter plot)
   - Ownership (`insights/ownership.py`): Unassigned repos, multiple owners, orphaned repos, department distribution
   - Technology (`insights/technology.py`): Popular languages, Docker usage, Kubernetes usage, framework adoption

**Data Querying Pattern**: Insights query **Repository** and **Finding** models directly:
- Repository fields: tier, last_commit_date, activity metrics, binary signals
- Finding fields: severity, active, test.engagement.product (for product-level aggregation)
- Prefetch patterns: `select_related('product')`, `prefetch_related('repositories')` for performance

**REST API Endpoints** (`dojo/api_v2/views.py:GitHubInsightsViewSet`, lines 3726-3825):
- `GET /api/v2/github_insights/` - List all available insights (metadata only)
- `GET /api/v2/github_insights/?category=security` - Filter by category
- `GET /api/v2/github_insights/{insight_id}/` - Calculate specific insight with optional filters (days, product_type_id)
- `GET /api/v2/github_insights/dashboard/` - Get user's dashboard configuration (GitHubInsightConfiguration model)
- `POST /api/v2/github_insights/dashboard/` - Update dashboard widget configuration

**Caching Strategy**: Hash-based cache keys (`github_insight_{insight_id}_{hash(filters)}`) with 300s TTL (5 minutes), pinned widgets use 60s TTL.

**Web Dashboard** (`/github/insights/dashboard`):
- Template: `dojo/templates/dojo/github_insights_dashboard.html`
- JavaScript: `dojo/static/dojo/js/github_insights_dashboard.js` (670 lines) - vanilla DOM manipulation, Chart.js 4.4.0 for visualizations
- Widget-based grid layout (Bootstrap 3.4.1), configuration modal for insight selection/ordering, individual widget refresh buttons with loading spinners

**User Configuration** (`dojo/models.py:GitHubInsightConfiguration`, lines 5967-6022):
- OneToOne relationship with User
- `widget_config` (JSONField): Array of widget objects with insight_id, order, size, pinned, auto_refresh, filters
- `widget_count` (IntegerField): Number of widgets to display (pinned widgets bypass limit)

### Current Validation Points

**Token Validation** (`dojo/github_collector/views.py:23-53`):
- Format check: Validates `ghp_` or `github_pat_` prefix
- API connectivity test: Calls `https://api.github.com/user` endpoint
- Specific error codes: 401 → "authentication failed", 403 → "lacks required permissions"
- **Limitation**: Does NOT check for required scopes (repo, read:org, security_events)
- **Limitation**: Does NOT validate token hasn't expired
- **Limitation**: Gracefully passes if API unreachable (network error) - could allow invalid tokens

**GraphQL Client Error Handling** (`dojo/github_collector/graphql_client.py:85-117`):
- Checks for `"errors"` key in GraphQL response
- Raises `ValueError` with concatenated error messages
- Logs errors with logger.error
- HTTP errors raise `requests.HTTPError` via `response.raise_for_status()`
- **Catches**: GraphQL syntax errors, permission errors, rate limit errors
- **Doesn't catch**: Partial failures (some repos succeed, some fail in batch)

**Alerts Collector Error Handling** (`dojo/github_collector/alerts_collector.py:175-186`):
- Wraps sync in try/except, stores error in `GitHubAlertSync.last_sync_error` (truncated to 1000 chars)
- Logs full exception with `exc_info=True`
- Incremental sync respects `MIN_SYNC_INTERVAL` (1 hour) to prevent hammering API
- Rate limit monitoring: `_should_pause_for_rate_limits()` checks if >80% of quota consumed (lines 66-67)
- **SyncResult dataclass** tracks success/failure per repository with error list

**Management Command Validation** (`dojo/management/commands/sync_github_repositories.py:86-135`):
- Checks `DD_GITHUB_TOKEN` or `--token` is provided (raises CommandError if missing)
- Checks `DD_GITHUB_ORG` or `--org` is provided (raises CommandError if missing, unless --product-id specified)
- Try/except wrapper around collector initialization (catches ValueError for invalid token format)
- Per-repository error handling with continue-on-error pattern (line 196)
- **Limitation**: No pre-flight check that org exists before starting sync

**Sync Status Tracking**:
- `GitHubSyncConfiguration.last_sync_status`: 'success' or 'failed'
- `GitHubSyncConfiguration.last_sync_error`: Full error text
- `GitHubAlertSync.last_sync_error`: Per-repository alert sync errors
- Progress logging every 10 repositories (lines 183, 234)

**Data Integrity Validation**:
- Unique constraints: Repository.github_repo_id, GitHubAlert unique_together=['repository', 'alert_type', 'github_alert_id']
- XSS sanitization: `bleach.clean()` applied to README summaries and CODEOWNERS content
- Webhook permission fallback: Gracefully handles missing admin:repo_hook permission

### Identified Validation Gaps

**PAT Configuration Gaps**:
1. **No scope validation**: Token may be valid but lack required permissions (repo, read:org, security_events, admin:repo_hook)
2. **No expiration check**: Token may be valid today but expire mid-sync
3. **No encryption**: Tokens stored in plaintext in database (despite comment saying "stored encrypted")
4. **No organization existence check**: Can save config with non-existent org name
5. **Blocking sync trigger**: Web UI sync blocks HTTP request, can timeout for large orgs (should be async Celery task)

**Data Pipeline Gaps**:
1. **No Product_Type validation**: Repository → Product relationship requires Product to exist, but no check that Product has valid Product_Type
2. **No orphan detection**: If Product is deleted, Repository becomes orphaned (CASCADE delete), but no validation prevents this
3. **No rate limit pre-check**: Starts sync even if rate limit already exhausted (discovers mid-sync)
4. **Partial success handling**: If 100 repos sync and 50 fail, `last_sync_status` = 'success' (no distinction between full/partial success)
5. **No rollback mechanism**: If sync fails midway, already-created Repository/Alert records remain (no transaction wrapper)

**Finding Conversion Gaps**:
1. **No Test_Type validation**: Assumes Test_Type records exist for "GitHub Dependabot", "GitHub CodeQL", "GitHub Secret Scanning" (fails if migration not run)
2. **No duplicate finding check**: Relies solely on `unique_id_from_tool`, but doesn't validate hash_code matches after deduplication
3. **No state transition validation**: Doesn't validate Finding state transitions (e.g., can't go from mitigated→active directly in DefectDojo, but GitHub allows dismissed→open)
4. **No backfill for existing findings**: If findings existed before PAT configured, they don't get linked to GitHubAlert records

**Insights Dashboard Gaps**:
1. **No empty data handling**: Insights calculate on zero repositories, returns empty charts (should show "no data" message)
2. **No user feedback on stale data**: Cache TTL of 300s means user sees old data without indication
3. **No error boundary**: If insight calculation throws exception, entire dashboard breaks (should show error in widget)
4. **Test data not isolated**: Fixture data (dojo/fixtures/defect_dojo_sample_data.json) could appear in production insights if not filtered

### Test Data vs Production Data Separation

**Current Approach - NO Separation**:

DefectDojo does **not** distinguish test data from production data at the model level. There are no flags like `is_test_data` or `environment` on Product, Repository, or Finding models. This creates risk that test/fixture data appears in production dashboards.

**Fixture Data** (`dojo/fixtures/`):
- `defect_dojo_sample_data.json`: Contains sample Products, Engagements, Tests, Findings for demo purposes
- `dojo_testdata.json`: Contains test data for unit tests
- **Problem**: If fixtures loaded in production, sample data will appear in Insights Dashboard (no filtering mechanism)

**Unit Test Patterns**:
- Tests use Django TestCase with in-memory SQLite database (separate from production PostgreSQL)
- Test data created via factories or fixtures, destroyed after test run
- **Pattern**: `unittests/test_github_alerts_collector.py` creates test Product/Repository in `setUp()`, cleans up in tearDown
- **Problem**: Integration tests (`test_comprehensive_validation.py`) use actual production database, query real Product IDs (lines 31-32)

**Recommendation for Separation**:
1. Add `environment` CharField to Product model with choices: 'production', 'staging', 'development', 'test'
2. Filter all insights queries by `product__environment='production'`
3. Add validation to PAT config to specify target environment
4. Update fixtures to set `environment='test'`

### Failure Points in Data Pipeline

**Token-Level Failures**:
- Invalid token format → Caught at configuration validation
- Expired token → Discovered mid-sync (GitHub API returns 401), sync fails, stored in `last_sync_error`
- Insufficient permissions → Discovered when accessing specific resource (e.g., alerts), partial sync succeeds

**Network-Level Failures**:
- GitHub API unreachable → `requests.RequestException`, caught and logged, sync fails
- Rate limit exceeded → Discovered mid-sync, `GitHubAlertSync.last_rate_limit_hit` updated, sync pauses/fails
- Timeout → `requests.Timeout`, caught and logged, sync fails

**Data-Level Failures**:
- Repository not found (404) → Logged as warning, skipped, sync continues
- Alert parsing error → `ValueError` in findings_converter, caught, stored in sync error, finding not created
- Unique constraint violation → `IntegrityError`, caught and logged, record skipped (should not happen with proper deduplication)

**Database-Level Failures**:
- Product deleted mid-sync → Repository CASCADE deletes, creates orphaned GitHubAlert records (FK constraint violation on next sync)
- Engagement deleted → Test CASCADE deletes, Finding CASCADE deletes, breaks GitHubAlert → Finding link
- Migration not applied → Missing Test_Type, findings_converter raises `ValueError: Test_Type not found: GitHub Dependabot`

**Insights-Level Failures**:
- Insight calculation timeout → No timeout configured, long-running query blocks web request
- Missing Repository records → Insights return empty data (no error)
- Cache corruption → Rare, cache keys are deterministic, but if cache backend fails (Redis down), falls back to database (degrades performance, doesn't break)

### Implementation Task Recommendations

Based on this research, the validation strategy should address these priorities:

**P0 - PAT Configuration Validation**:
1. Implement comprehensive token validation that checks required scopes (repo, read:org, security_events)
2. Add organization/user existence check before saving configuration
3. Move sync trigger to async Celery task to prevent HTTP timeouts
4. Add token encryption using Django's `encrypt()` utility

**P1 - Data Pipeline Health Checks**:
1. Add pre-flight validation: check rate limit quota before starting sync, check Product_Type exists, check Test_Type records exist
2. Implement transaction-wrapped sync with rollback on failure
3. Add partial success tracking: distinguish between full success, partial success (N of M repos), and total failure
4. Add orphan detection job: find Repository records with deleted Products, GitHubAlert records with deleted Findings

**P2 - Finding Conversion Validation**:
1. Add hash_code verification after deduplication: ensure Finding.hash_code matches expected value
2. Add state transition validation: prevent invalid transitions (e.g., mitigated→active without reopening)
3. Add backfill command: link existing Findings to GitHubAlert records based on unique_id_from_tool

**P3 - Insights Dashboard Robustness**:
1. Add empty data handling: show "No data available" message in widgets
2. Add error boundaries: catch insight calculation exceptions, show error in widget (don't break entire dashboard)
3. Add stale data indicator: show cache age in widget footer
4. Add test data filtering: filter insights by `product__environment='production'` (requires new field)

**Automated Validation Tooling**:
1. `validate_github_setup` management command: runs all pre-flight checks, reports issues before sync
2. `smoke_test_github_pipeline` management command: creates test repository, syncs it, verifies Finding created, cleans up
3. API endpoint `/api/v2/github_setup/validate/` for web UI feedback
4. Health check endpoint `/api/v2/github_setup/health/` showing sync status, last error, rate limit quota

## User Notes
<!-- Any specific notes or requirements from the developer -->

## Work Log
<!-- Updated as work progresses -->
- [2025-11-26] Task created
