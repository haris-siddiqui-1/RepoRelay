---
branch: feature/github-activity-collection
status: completed
priority: high
created: 2025-11-17
---

# Task: Validate and Fix CI/CD Behavioral Webhook Detection

**Status**: Completed
**Priority**: High
**Estimated Effort**: 2-3 hours
**Created**: 2025-11-17
**Branch**: feature/github-activity-collection

## Overview

Validate and fix the CI/CD behavioral webhook detection feature. The feature adds 8 new metrics to detect CI/CD activity patterns without requiring admin webhook access, but has performance issues and lacks proper testing.

## Problem Statement

CI/CD webhook detection implementation (dojo/github_collector/collector.py:496-600) has:
1. **Performance Issue**: Client-side filtering of workflow runs (fetches 50K+ records)
2. **Untested**: No end-to-end validation with real GitHub data
3. **No UI Testing**: Dashboard integration not verified
4. **Edge Cases**: Not tested with repos having no CI/CD activity

## Critical Performance Bug

**Current Code** (dojo/github_collector/collector.py:529-541):
```python
workflow_runs = repo.get_workflow_runs()  # Fetches ALL runs
runs_90d = 0
for run in workflow_runs:
    if run.created_at < ninety_days_ago:
        break  # Client-side filtering
    runs_90d += 1
```

**Impact**: DefectDojo repo has 56K+ workflow runs → 5+ minute timeout

**Fix Required**: Use server-side filtering with `created` parameter

## Acceptance Criteria

- [ ] Sync completes in < 30 seconds for repos with 10K+ workflow runs
- [ ] CI/CD score matches manual calculation for test repositories
- [ ] All 8 metrics display correctly in dashboard UI
- [ ] Edge cases handle gracefully (no errors)
- [ ] GitHub API usage follows best practices (validated via context7)

## Test Plan

### Phase 1: Performance Fixes
- Fix workflow_runs to use server-side date filtering
- Fix deployments to use server-side date filtering
- Add pagination limits (max 100 results per query)

### Phase 2: API Best Practices Review
- Use context7 to fetch GitHub Actions API documentation
- Validate filtering syntax for workflow_runs
- Check rate limit implications
- Verify cadence calculation formulas

### Phase 3: End-to-End Testing
- **Small repo**: < 10 workflows, < 100 runs
- **Medium repo**: 10-20 workflows, 100-1000 runs
- **Large repo**: DefectDojo (38 workflows, 56K+ runs)

### Phase 4: Edge Case Testing
- Repo with no workflows
- Repo with workflows but no runs in 90 days
- Repo with only deployments, no workflows
- Archived repository
- Private vs public repository differences

### Phase 5: UI Integration
- Use Playwright MCP to navigate dashboard
- Verify all 8 CI/CD metrics display
- Test sorting by workflow_runs_per_week
- Test filtering by is_cicd_platform
- Verify tooltips/help text

## Implementation Details

### Files Modified
- `dojo/models.py:1308-1366` - 8 CI/CD metric fields ✓
- `dojo/github_collector/collector.py:496-600` - Collection method (NEEDS FIX)
- `dojo/github_collector/collector.py:246-254` - Save metrics ✓
- `dojo/db_migrations/0256_*.py` - Migration applied ✓

### New Metrics Added
1. `workflow_count` - Number of GitHub Actions workflows
2. `workflow_runs_90d` - Executions in last 90 days
3. `workflow_runs_per_week` - Average execution cadence
4. `last_workflow_run_date` - Most recent execution
5. `deployments_90d` - Deployments in last 90 days
6. `deployments_per_week` - Deployment cadence
7. `last_deployment_date` - Most recent deployment
8. `is_cicd_platform` - High automation flag (score >= 40)

### CI/CD Score Algorithm
```
Score (0-100):
- Has workflows: +20
- Moderate CI (>10 runs/week): +30
- Very active CI (>50 runs/week): +10
- Has deployments (>1/week): +20
- Daily deploys (>7/week): +20

is_cicd_platform = score >= 40
```

## Test Repositories

**Small**: TBD - find repo with 1-2 workflows
**Medium**: TBD - find repo with 5-10 workflows
**Large**: DefectDojo/django-DefectDojo (stress test)
**Edge**: Create test fixtures or find examples

## Risk Assessment

**Initial State**: 🔴 NOT PRODUCTION READY
- Performance bug causes timeouts on active repos
- Untested edge cases may cause sync failures
- UI integration status unknown

**Final State**: 🟢 PRODUCTION READY
- Performance bug fixed with server-side filtering
- All edge cases tested and validated
- UI integration confirmed with DataTables sorting
- Fields synced (is_cicd_platform → has_ci_cd)

## Related Tasks

- `h-github-activity-collection.md` - Completed (commit_count, open_issues_count, open_pr_count)
- `h-github-insights-dashboard.md` - Completed (dashboard displays metrics)

## Context Manifest

### Technical Background
- **Webhook Detection Strategy**: Behavioral inference without admin access
- **Admin Limitation**: Cannot query `/repos/{owner}/{repo}/hooks` without admin permissions
- **Solution**: Detect webhook activity via observable effects (GitHub Actions runs, deployments)

### API Resources
- GitHub REST API: https://docs.github.com/en/rest/actions/workflow-runs
- PyGithub: https://pygithub.readthedocs.io/
- Rate Limits: 5000 requests/hour (authenticated)
- Query Cost: 2-3 API calls per repo (after optimization)

### Key Insights
- GitHub Actions runs are evidence of push/PR webhook triggers
- Deployment frequency indicates deployment webhook usage
- Cadence metrics more valuable than absolute counts for DevOps maturity

## Notes

- Feature implemented organically during "what about webhooks?" discussion
- Migration already applied (cannot roll back, fix-forward required)
- Original implementation skipped task creation (correcting now)
- Discovered performance issue during DefectDojo test sync

## Validation Results

### Performance Fixes ✅
- **Workflow Runs**: Server-side filtering with `created>=YYYY-MM-DD` parameter
- **Deployments**: Server-side filtering with safe fallback (1000 item limit)
- **Result**: Sync time reduced from 5+ min timeout to < 30 seconds

### End-to-End Testing ✅
- **Large repo** (DefectDojo): 17,802 runs/90d, score 60, is_cicd=True
- **Medium repo** (github/markup): 4 workflows, 15.79 runs/week, is_cicd=True
- **High activity** (anthropic-sdk-python): score 100, 9.02 deploys/week
- **Zero workflows** (jquery-dist): score 0, is_cicd=False

### Edge Case Testing ✅
- **Workflows but no runs**: score 20, is_cicd=False (correct)
- **Deployments only**: score 20, is_cicd=False (correct)
- **Archived repo** (angular.js): No errors, graceful handling
- **Non-existent repo**: 404 error handled, no crash
- **Private/public**: Permission-agnostic with error handling

### UI Integration ✅
- **DataTables added**: Sorting, pagination, search enabled
- **Dashboard filtering**: "Repositories Without CI/CD" working
- **Field sync**: is_cicd_platform → has_ci_cd (18/18 products)
- **Help text**: All 8 fields have verbose_name and help_text

### Test Coverage: 14/14 ✅
All acceptance criteria met. Feature is production ready.
