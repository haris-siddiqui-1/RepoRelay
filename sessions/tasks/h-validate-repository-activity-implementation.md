---
status: pending
created: 2025-11-22
priority: high
estimated_effort: 1-2 hours
index: phase4-migration
branch: feature/repository-activity-metrics
parent_task: h-github-activity-collection.md
---

# Validate Repository Activity & Webhook Health Implementation

## Objective

Properly test and validate the Repository Activity Metrics and Webhook Health Monitoring implementation that was completed but not tested. This includes API verification, UI testing, real data sync, and data quality validation.

## User Story

> "Did we even test? verify implementation with context7 mcp? test UI with playwright mcp?"

The implementation is complete but was never properly validated. We need to:
1. Verify GraphQL queries work against actual GitHub API
2. Test admin UI displays fields correctly
3. Run real sync with GitHub credentials
4. Validate webhook collection and analysis algorithms

## Success Criteria

### Phase 1: GraphQL API Verification (context7 MCP)
- [ ] Use context7 MCP to verify `openPullRequests: pullRequests(states: OPEN) { totalCount }` query syntax
- [ ] Confirm GitHub GraphQL API accepts our exact query structure
- [ ] Verify response includes all expected fields (totalCount, etc.)
- [ ] Test query against GitHub GraphQL Explorer with real repository
- [ ] Document any API version compatibility issues

### Phase 2: Admin UI Testing (Playwright MCP)
- [ ] Use Playwright to navigate to Django admin Repository model
- [ ] Verify "Activity Tracking" fieldset displays all 3 fields:
  - commit_count
  - open_issues_count
  - open_pr_count
- [ ] Verify "Webhook Health" fieldset displays all 4 fields:
  - has_webhooks
  - active_webhooks_count
  - webhook_cadence
  - webhook_types
- [ ] Take screenshots of admin interface for documentation
- [ ] Verify field labels and help text display correctly

### Phase 3: Database Migration Verification
- [ ] Confirm migration 0258 is applied in PostgreSQL
- [ ] Verify all 7 columns exist in dojo_repository table
- [ ] Check column types match model definitions (IntegerField, BooleanField, CharField, JSONField)
- [ ] Verify default values are set correctly
- [ ] Run `\d dojo_repository` in PostgreSQL to document schema

### Phase 4: Real GitHub Sync Test
- [ ] Check if DD_GITHUB_TOKEN environment variable is set
- [ ] Run sync with --dry-run first to preview changes
- [ ] Run actual sync: `python manage.py sync_github_repositories --incremental`
- [ ] Monitor logs for webhook collection API calls
- [ ] Verify no rate limiting errors
- [ ] Confirm sync completes successfully

### Phase 5: Data Quality Validation
- [ ] Query 10 repositories from database after sync
- [ ] Verify commit_count values are realistic (>0 for active repos)
- [ ] Verify open_issues_count matches GitHub UI
- [ ] Verify open_pr_count matches GitHub UI
- [ ] For repos with webhooks:
  - Verify has_webhooks = True
  - Verify active_webhooks_count > 0
  - Verify webhook_cadence is not "Unknown" or "Inactive" for active repos
  - Verify webhook_types array contains detected integrations
- [ ] Document any data quality issues or edge cases

### Phase 6: Webhook Collection Algorithm Testing
- [ ] Find repository with known webhook configuration
- [ ] Manually verify webhook count via GitHub UI
- [ ] Compare webhook_types detection against actual webhook URLs
- [ ] Verify webhook_cadence calculation:
  - Check if median algorithm works correctly
  - Verify time delta calculations
  - Test edge cases (no deliveries, single delivery, etc.)
- [ ] Document webhook type detection accuracy

### Phase 7: GraphQL Query Cost Analysis
- [ ] Check GitHub API rate limit before sync
- [ ] Run sync on 10 repositories
- [ ] Check rate limit after sync
- [ ] Calculate actual point cost per repository
- [ ] Verify cost is within expected range (30-40 points)
- [ ] Document REST API webhook call overhead (2-3 calls per repo)

### Phase 8: Error Handling & Edge Cases
- [ ] Test with repository that has no webhooks
- [ ] Test with repository that has inactive webhooks
- [ ] Test with repository that has webhooks but no deliveries
- [ ] Test with archived repository
- [ ] Test with private repository (if accessible)
- [ ] Verify all edge cases handle gracefully (no crashes)

## Context Manifest

### What Was Implemented (But Not Tested)

**Implementation completed in previous session:**
- 7 new fields added to Repository model (3 activity + 4 webhook)
- Migration 0258 generated and applied
- GraphQL query updated with openPullRequests alias
- 3 webhook collection methods added to collector.py:
  - `_collect_webhook_metadata()`
  - `_calculate_webhook_cadence()`
  - `_detect_webhook_types()`
- GraphQL parser updated to extract openPullRequests
- Collector metadata extraction updated
- Admin UI fieldsets updated
- Django check --deploy passed (syntax only)

**What Was NOT Done:**
- No actual GitHub API call testing
- No admin UI verification with Playwright
- No real sync execution with GitHub credentials
- No data quality validation
- No webhook algorithm testing with real data
- No rate limiting verification

### Files to Test

**Code Files:**
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/models.py` - Lines 1681-1728 (7 new fields)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/queries/repository_full.graphql` - Lines 131-135 (openPullRequests)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/collector.py` - Lines 900-1000 (webhook methods)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/admin.py` - Lines 155-171 (fieldsets)

**Migration File:**
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/db_migrations/0258_repository_active_webhooks_count_and_more.py`

### Testing Environment

**Docker Services:**
- uwsgi container: Django application
- postgres container: PostgreSQL database
- nginx container: Web server for admin UI

**Required Credentials:**
- GitHub Personal Access Token (DD_GITHUB_TOKEN)
- GitHub Organization name (DD_GITHUB_ORG)
- Permissions: repo, admin:repo_hook (for webhook access)

### Testing Tools

**Context7 MCP:**
- Tool: `mcp__context7__get-library-docs`
- Library ID: `/github/rest-api-reference` or `/github/graphql-api-reference`
- Use to verify API syntax and response structures

**Playwright MCP:**
- Tool: `mcp__playwright__browser_navigate`
- Tool: `mcp__playwright__browser_snapshot`
- Tool: `mcp__playwright__browser_take_screenshot`
- URL: `http://localhost:8080/admin/dojo/repository/`

**Django Management Commands:**
```bash
# Dry run to preview sync
docker compose exec uwsgi bash -c "python manage.py sync_github_repositories --dry-run --incremental"

# Actual sync with incremental mode
docker compose exec uwsgi bash -c "python manage.py sync_github_repositories --incremental"

# Query data for validation
docker compose exec uwsgi bash -c "python manage.py shell -c \"
from dojo.models import Repository
repos = Repository.objects.values(
    'name', 'commit_count', 'open_issues_count', 'open_pr_count',
    'has_webhooks', 'active_webhooks_count', 'webhook_cadence', 'webhook_types'
)[:10]
for repo in repos:
    print(repo)
\""

# Check PostgreSQL schema
docker compose exec postgres psql -U defectdojo -c "\d dojo_repository"
```

## Implementation Plan

### Step 1: Context7 API Verification (15 min)
1. Use context7 MCP to fetch GitHub GraphQL API docs
2. Verify openPullRequests query syntax
3. Test query in GitHub GraphQL Explorer
4. Document actual API response structure

### Step 2: Playwright Admin UI Testing (20 min)
1. Start Playwright browser session
2. Navigate to http://localhost:8080/admin/
3. Login with admin credentials
4. Navigate to Repository model
5. Take screenshots of fieldsets
6. Verify all 7 fields display correctly

### Step 3: Database Schema Verification (10 min)
1. Connect to PostgreSQL container
2. Run \d dojo_repository command
3. Verify all 7 columns exist
4. Check column types and defaults
5. Document schema structure

### Step 4: Real Sync Execution (30 min)
1. Verify GitHub credentials are set
2. Run dry-run sync first
3. Execute actual sync with incremental mode
4. Monitor logs for errors
5. Check rate limiting status
6. Verify sync completes successfully

### Step 5: Data Quality Analysis (20 min)
1. Query 10 repositories from database
2. Compare values against GitHub UI
3. Verify webhook data accuracy
4. Document any discrepancies
5. Test edge cases

### Step 6: Algorithm Testing (15 min)
1. Select repository with known webhooks
2. Verify webhook type detection accuracy
3. Test cadence calculation logic
4. Validate median algorithm
5. Document findings

### Step 7: Rate Limiting Analysis (10 min)
1. Check GitHub rate limit before/after sync
2. Calculate actual point cost
3. Verify webhook REST calls overhead
4. Document performance metrics

### Step 8: Error Handling & Documentation (10 min)
1. Test edge cases
2. Verify graceful error handling
3. Document any issues found
4. Update parent task with test results

**Total Estimated Time:** 1-2 hours

## Acceptance Criteria

- [ ] All 8 phases completed successfully
- [ ] GraphQL query verified against actual GitHub API
- [ ] Admin UI screenshots captured and verified
- [ ] Real sync executed with at least 10 repositories
- [ ] Data quality validated against GitHub UI
- [ ] Webhook algorithms tested with real data
- [ ] Rate limiting impact documented
- [ ] All edge cases tested without crashes
- [ ] Parent task (h-github-activity-collection.md) updated with test results
- [ ] Any bugs found are documented and fixed

## Related Tasks

- **Parent Task**: h-github-activity-collection.md (implementation)
- **Depends On**: Migration 0258 must be applied
- **Blocks**: Any insights dashboard work using these fields

## Work Log

### 2025-11-22 - Task Created
- User identified that implementation was completed without proper testing
- Created comprehensive validation task covering API verification, UI testing, and data quality
- Defined 8 testing phases with specific success criteria
- Estimated 1-2 hours for complete validation

### 2025-11-22 - Validation Execution (Phases 1-5)

**Phase 1: GraphQL API Verification** ✅ PASSED
- Used web search to verify GitHub GraphQL API documentation
- Confirmed `pullRequests(states: OPEN)` query syntax is valid
- Verified `PullRequestConnection.totalCount` field exists
- Query structure at `repository_full.graphql:131-135` matches GitHub API spec

**Phase 2: Admin UI Testing** ✅ PASSED
- Used Playwright MCP to navigate to Django admin Repository model
- Verified "Activity Tracking" fieldset displays all 3 fields correctly:
  - Total Commits (spinbutton, default: 0)
  - Open Issues (spinbutton, default: 0)
  - Open Pull Requests (spinbutton, default: 0)
- Verified "Webhook Health" fieldset displays all 4 fields correctly:
  - Has Webhooks (checkbox, unchecked)
  - Active Webhooks (spinbutton, default: 0)
  - Webhook Cadence (dropdown: Hourly/2 Hours/Daily/Weekly/Monthly/Inactive/Unknown)
  - Webhook Types (JSON array, default: [])
- Screenshot saved: `.playwright-mcp/repository-admin-activity-webhook-fields.png`
- URL tested: `http://localhost:8080/admin/dojo/repository/7/change/`

**Phase 3: Database Schema Verification** ✅ PASSED
- Migration 0258 confirmed applied: 2025-11-22 08:32:33 UTC
- All 7 columns exist in `dojo_repository` table with correct types:
  - `commit_count` - integer, not null ✓
  - `open_issues_count` - integer, not null ✓
  - `open_pr_count` - integer, not null ✓
  - `has_webhooks` - boolean, not null ✓
  - `active_webhooks_count` - integer, not null ✓
  - `webhook_cadence` - character varying(20), not null ✓
  - `webhook_types` - jsonb, not null ✓
- PostgreSQL command: `\d dojo_repository` shows complete schema

**Phase 4: GitHub Token Configuration & Dry-Run Sync** ✅ PASSED
- Created `.env` file with GitHub credentials:
  - `DD_GITHUB_TOKEN=[REDACTED_GITHUB_TOKEN]`
  - `DD_GITHUB_ORG=haris-siddiqui-1` (personal account, not org)
- Rebuilt DefectDojo on port 9080 to avoid conflicts
- Ran dry-run sync: `sync_github_repositories --product-id 56 --dry-run`
- Dry-run succeeded: "Would sync: haris-siddiqui-1/CapabilityMatrix"

**Phase 4: Actual Sync Execution** ✅ PASSED
- Ran actual sync on two products:
  - Product 56: haris-siddiqui-1/CapabilityMatrix
  - Product 48: haris-siddiqui-1/RepoRelay
- Sync completed successfully for both repositories
- No exceptions or critical errors in logs
- Collector reported: "✓ Successfully synced: haris-siddiqui-1/RepoRelay"

**Phase 5: Data Validation** ❌ **CRITICAL BUG DISCOVERED**

Queried database to validate populated data:

```sql
-- Repository table (WHERE UI LOOKS - EMPTY!)
SELECT name, commit_count, open_issues_count, open_pr_count
FROM dojo_repository
WHERE name = 'haris-siddiqui-1/RepoRelay';
-- Result: commit_count=0, open_issues_count=0, open_pr_count=0 ✗

-- Product table (WHERE DATA ACTUALLY SAVED - WRONG MODEL!)
SELECT name, commit_count, open_issues_count, open_pr_count
FROM dojo_product
WHERE name = 'haris-siddiqui-1/RepoRelay';
-- Result: commit_count=13232, open_issues_count=0, open_pr_count=0 ✓
```

**ROOT CAUSE IDENTIFIED**:
- Collector code at `dojo/github_collector/collector.py:284-286` saves to `product.*` fields
- Migration 0258 added fields to Repository model
- Data is being saved to Product model (old location)
- Repository model fields remain at default values
- Admin UI displays Repository model, which has no data
- **This is why validation found zeros - wrong model being queried!**

**Bug Impact Assessment**:
- ❌ Activity metrics NOT populating in Repository model
- ❌ Webhook health fields NOT populating in Repository model
- ✅ Schema is correct (migration applied)
- ✅ Admin UI is correct (displays Repository fields)
- ✅ API calls work (collector fetches data from GitHub)
- ✅ Data is being saved (but to wrong model - Product instead of Repository)

**Action Taken**:
- Created bug fix task: `h-fix-repository-activity-bugs.md`
- Documented 3 critical bugs requiring fixes
- Proposed dual-population strategy (save to both Product and Repository)
- Suspended validation phases 6-8 until bugs are fixed

**Estimated Fix Time**: 2-3 hours

**Validation Status**: SUSPENDED - waiting for bug fixes before completing remaining phases
