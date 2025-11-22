---
status: pending
created: 2025-11-22
priority: critical
estimated_effort: 2-3 hours
index: phase4-migration
parent_task: h-validate-repository-activity-implementation.md
branch: fix/repository-activity-data-population
---

# Fix Repository Activity & Webhook Health Data Population Bugs

## Objective

Fix critical bugs discovered during validation testing where Repository model fields (activity metrics and webhook health) are not being populated during sync, despite being correctly defined in the database schema.

## Problem Statement

During Phase 4-5 validation testing, discovered that the repository activity implementation has a **critical data flow bug**:

1. ✅ **Schema is correct**: Migration 0258 successfully added 7 new fields to `dojo_repository` table
2. ✅ **Admin UI is correct**: Django admin displays all 7 fields in Repository model
3. ✅ **API calls work**: Collector successfully fetches data from GitHub API
4. ❌ **DATA FLOW BROKEN**: Collector saves data to **Product model** instead of **Repository model**

**Root Cause**: The collector code at `dojo/github_collector/collector.py:284-286` saves to `product.*` fields, but the new activity metrics were added to the Repository model in migration 0258.

**Evidence from Validation**:
```sql
-- Product table (WHERE DATA IS SAVED - WRONG!)
SELECT commit_count FROM dojo_product WHERE name = 'haris-siddiqui-1/RepoRelay';
-- Result: 13232 ✓

-- Repository table (WHERE DATA SHOULD BE - EMPTY!)
SELECT commit_count FROM dojo_repository WHERE name = 'haris-siddiqui-1/RepoRelay';
-- Result: 0 ✗
```

## Critical Bug Details

### Bug #1: Activity Metrics Saved to Wrong Model

**Location**: `dojo/github_collector/collector.py:284-286`

**Current Code** (WRONG):
```python
# Lines 284-286 in collector.py
product.commit_count = metadata['commit_count']
product.open_issues_count = metadata['open_issues_count']
product.open_pr_count = metadata['open_pr_count']
```

**Problem**: These fields don't exist in Product model anymore - they were added to Repository model in migration 0258.

**Impact**:
- Data is being saved to Product model (old location)
- Repository model fields remain at default values (0)
- Admin UI shows Repository model, which has no data
- GraphQL queries against Repository model return zeros

### Bug #2: Webhook Health Fields Not Populated

**Location**: `dojo/github_collector/collector.py` (webhook collection methods)

**Status**: Implementation exists for webhook collection methods but they're never called or data never saved to Repository:
- `_collect_webhook_metadata()` - Lines 900-950
- `_calculate_webhook_cadence()` - Lines 951-980
- `_detect_webhook_types()` - Lines 981-1000

**Problem**: Even if these methods work, the data isn't being saved to the Repository model.

**Impact**:
- `has_webhooks` always False
- `active_webhooks_count` always 0
- `webhook_cadence` always "Inactive"
- `webhook_types` always []

### Bug #3: Product vs Repository Data Model Confusion

**Architectural Issue**: The codebase has duplicate fields in both Product and Repository models:

**Product Model** (old location):
- `commit_count`
- `open_issues_count`
- `open_pr_count`
- `workflow_count`
- `workflow_runs_90d`
- etc.

**Repository Model** (new location - migration 0258):
- `commit_count`
- `open_issues_count`
- `open_pr_count`
- `has_webhooks`
- `active_webhooks_count`
- `webhook_cadence`
- `webhook_types`

**Decision Needed**: Should we:
1. **Option A**: Remove fields from Product, use only Repository (breaking change)
2. **Option B**: Populate both models (data duplication)
3. **Option C**: Keep Product for legacy, migrate dashboards to use Repository

## Success Criteria

### Phase 1: Fix Data Population
- [ ] Update collector to save activity metrics to Repository model
- [ ] Implement webhook metadata collection and save to Repository
- [ ] Verify data flows correctly during sync
- [ ] Ensure no exceptions or warnings in logs

### Phase 2: Verify Data Quality
- [ ] Run sync on 5 different repositories
- [ ] Validate commit_count matches GitHub UI
- [ ] Validate open_issues_count matches GitHub UI
- [ ] Validate open_pr_count matches GitHub UI
- [ ] Verify webhook data for repos with known webhooks

### Phase 3: Regression Testing
- [ ] Ensure Product model fields still work (if keeping dual population)
- [ ] Verify existing dashboards don't break
- [ ] Test GraphQL queries return correct data
- [ ] Verify admin UI displays correct values

### Phase 4: Documentation
- [ ] Update README_GRAPHQL.md with data flow diagram
- [ ] Document Product vs Repository field mapping
- [ ] Add inline comments explaining dual-model strategy
- [ ] Update parent task with test results

## Implementation Plan

### Step 1: Analyze Current Data Flow (30 min)

**Understand the sync flow**:
```
sync_product_from_github_url()
  → github_client.get_repo(full_name)  [REST API call]
  → sync_repository(repo)              [Main sync method]
    → _collect_repository_metadata(repo)  [Fetches data]
    → product.commit_count = metadata['commit_count']  [BUG: Wrong model!]
```

**Key Questions**:
1. Does Repository record get created during sync?
2. Is there a Repository → Product relationship?
3. Should we populate both models or migrate to Repository only?

### Step 2: Check Repository Record Creation (15 min)

**Verify Repository records exist**:
```python
from dojo.models import Product, Repository

product = Product.objects.get(name='haris-siddiqui-1/RepoRelay')
repo = Repository.objects.filter(product=product).first()

if repo:
    print(f"Repository record exists: {repo.name}")
    print(f"GitHub URL: {repo.github_url}")
else:
    print("ERROR: No Repository record linked to Product!")
```

**Expected**: Repository records should exist from Phase 4 Product Migration work.

### Step 3: Fix Activity Metrics Population (45 min)

**Location**: `dojo/github_collector/collector.py:278-299`

**Option A - Repository Only** (Clean but breaking):
```python
# Get or create Repository record
repository, _ = Repository.objects.get_or_create(
    github_url=product.github_url,
    defaults={
        'name': product.name,
        'product': product,
        'github_repo_id': repo.id
    }
)

with transaction.atomic():
    # Save to Repository model (NEW)
    repository.commit_count = metadata['commit_count']
    repository.open_issues_count = metadata['open_issues_count']
    repository.open_pr_count = metadata['open_pr_count']
    repository.last_commit_date = metadata['last_commit_date']
    repository.days_since_last_commit = metadata['days_since_last_commit']
    repository.save()
```

**Option B - Dual Population** (Safe but redundant):
```python
with transaction.atomic():
    # Save to Product (LEGACY - for existing dashboards)
    product.commit_count = metadata['commit_count']
    product.open_issues_count = metadata['open_issues_count']
    product.open_pr_count = metadata['open_pr_count']

    # Save to Repository (NEW - for future use)
    repository.commit_count = metadata['commit_count']
    repository.open_issues_count = metadata['open_issues_count']
    repository.open_pr_count = metadata['open_pr_count']

    product.save()
    repository.save()
```

**Recommendation**: Start with Option B (dual population) to avoid breaking existing code, then migrate incrementally.

### Step 4: Implement Webhook Collection (60 min)

**Location**: `dojo/github_collector/collector.py:900-1000`

**Verify methods exist**:
```bash
grep -n "_collect_webhook_metadata\|_calculate_webhook_cadence\|_detect_webhook_types" collector.py
```

**Add webhook collection to sync flow**:
```python
# In sync_repository() method, after metadata collection:

# Collect webhook metadata (NEW)
webhook_data = self._collect_webhook_metadata(repo)

# Save to Repository
with transaction.atomic():
    repository.has_webhooks = webhook_data['has_webhooks']
    repository.active_webhooks_count = webhook_data['active_webhooks_count']
    repository.webhook_cadence = webhook_data['webhook_cadence']
    repository.webhook_types = webhook_data['webhook_types']
    repository.save()
```

**Webhook collection implementation**:
- Method should already exist from previous implementation
- Needs to return dict with: has_webhooks, active_webhooks_count, webhook_cadence, webhook_types
- Uses REST API: `repo.get_hooks()` and `hook.deliveries()`
- Handles edge cases: no webhooks, no deliveries, API errors

### Step 5: Testing & Validation (30 min)

**Test sync with multiple repositories**:
```bash
# Sync 5 different repos
python manage.py sync_github_repositories --token $DD_GITHUB_TOKEN --product-id 48  # RepoRelay
python manage.py sync_github_repositories --token $DD_GITHUB_TOKEN --product-id 56  # CapabilityMatrix
python manage.py sync_github_repositories --token $DD_GITHUB_TOKEN --product-id 52  # WebGoat
```

**Validate data in database**:
```sql
SELECT
    r.name,
    r.commit_count,
    r.open_issues_count,
    r.open_pr_count,
    r.has_webhooks,
    r.active_webhooks_count,
    r.webhook_cadence
FROM dojo_repository r
WHERE r.name IN ('haris-siddiqui-1/RepoRelay', 'haris-siddiqui-1/CapabilityMatrix')
ORDER BY r.name;
```

**Expected Results**:
- commit_count > 0 for active repos
- open_issues_count matches GitHub UI
- open_pr_count matches GitHub UI
- webhook fields populated for repos with webhooks

### Step 6: Update Admin UI Test (15 min)

**Re-run Playwright test from validation**:
```bash
# Navigate to http://localhost:9080/admin/dojo/repository/
# View repository detail page
# Screenshot showing NON-ZERO values in activity fields
```

**Expected Screenshot**:
- Total Commits: 13232 (not 0)
- Open Issues: 0 (matches GitHub)
- Open Pull Requests: 0 (matches GitHub)
- Webhook fields showing actual data

## Files to Modify

### Primary Changes

1. **`dojo/github_collector/collector.py`** (Lines 278-350)
   - Update `sync_repository()` to populate Repository model
   - Ensure Repository record exists before saving
   - Add webhook metadata collection call
   - Save webhook data to Repository fields

2. **`dojo/models.py`** (Optional - if removing Product fields)
   - Consider deprecating duplicate fields in Product model
   - Add migration to remove fields (breaking change)

### Testing Files

3. **`unittests/github_collector/test_collector.py`** (If exists)
   - Update tests to verify Repository population
   - Add webhook collection tests
   - Mock GitHub API responses

## Acceptance Criteria

- [ ] All 3 activity metric fields populate correctly in Repository model
- [ ] All 4 webhook health fields populate correctly in Repository model
- [ ] Sync completes without errors or warnings
- [ ] Data matches actual GitHub repository values
- [ ] Admin UI displays non-zero values after sync
- [ ] No regression in existing Product model dashboards
- [ ] Parent validation task updated with bug fix results

## Related Tasks

- **Parent Task**: h-validate-repository-activity-implementation.md (validation revealed bugs)
- **Original Implementation**: h-github-activity-collection.md (incomplete implementation)
- **Depends On**: Migration 0258 (schema is correct)
- **Blocks**: Any insights dashboard work using Repository model fields

## Work Log

### 2025-11-22 - Bug Discovery During Validation

**Context**: Running validation task h-validate-repository-activity-implementation.md

**Bugs Found**:
1. ✅ Phase 1-3 passed: GraphQL API, Admin UI, Database schema all correct
2. ❌ Phase 4-5 failed: Data not populating in Repository model
3. 🔍 Root cause: Collector saves to Product model instead of Repository model

**Evidence Collected**:
```
PostgreSQL Query Results:
- dojo_product.commit_count: 13232 ✓ (data saved here)
- dojo_repository.commit_count: 0 ✗ (should be here but empty)

Admin UI Screenshots:
- Repository admin page shows zeros (correct page, wrong data)
- Would need to check Product admin page to see actual data
```

**Decision**: Create this bug fix task before completing validation phases 6-8.

**Estimated Fix Time**: 2-3 hours
- 1 hour for Repository model population fix
- 1 hour for webhook collection integration
- 1 hour for testing and validation

### Next Steps

1. Get user approval on dual-population strategy (Option B recommended)
2. Implement Repository model population
3. Add webhook collection integration
4. Re-run validation phases 4-8 with fixed code
5. Update parent validation task with results
