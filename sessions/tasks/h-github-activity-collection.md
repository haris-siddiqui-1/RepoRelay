---
status: pending
created: 2025-11-16
priority: high
estimated_effort: 30 min - 1 hour
index: phase4-migration
---

# Enhanced Repository Activity Collection

## Objective

Add enterprise-relevant activity metrics to the Repository model that are **already being queried** via GraphQL but not currently stored. This enables accurate activity-based insights for GitHub organization management.

## User Story

> "This will be enterprise-org GitHub management, so star_count, fork_count is not important."

Focus on **internal activity metrics** relevant to enterprise development teams:
- Commit velocity (total commits)
- Work backlog (open issues)
- Work in progress (open PRs)

## Context Manifest

### Current State
**Already Querying (But Not Storing!):**
- `history.totalCount` - Total commit count (dojo/github_collector/queries/repository_full.graphql:37)
- `pullRequests.totalCount` - Total PR count (line 120)

**Easy Additions (One Line Each):**
- `issues(states: OPEN) { totalCount }` - Open issues count
- Filter existing `pullRequests` query by state OPEN - Open PR count

### Related Files
- **Model**: `dojo/models.py:Repository` class (~line 1500)
- **GraphQL Query**: `dojo/github_collector/queries/repository_full.graphql`
- **GraphQL Parser**: `dojo/github_collector/graphql_client.py` or `collector.py`
- **REST Fallback**: `dojo/github_collector/collector.py` (REST API path)

### Dependencies
- Existing GraphQL infrastructure (Phase 1-3)
- Repository model with 36 binary signals
- GitHub PAT with `repo:read` permissions

## Requirements

### Functional Requirements

1. **Add 3 New Repository Model Fields**
   ```python
   commit_count = models.IntegerField(default=0,
                                     verbose_name=_("Total Commits"),
                                     help_text=_("Total number of commits in default branch"))

   open_issues_count = models.IntegerField(default=0,
                                          verbose_name=_("Open Issues Count"),
                                          help_text=_("Number of currently open issues"))

   open_pr_count = models.IntegerField(default=0,
                                      verbose_name=_("Open PR Count"),
                                      help_text=_("Number of currently open pull requests"))
   ```

2. **Update GraphQL Query**
   Add to `repository_full.graphql`:
   ```graphql
   # Open issues count
   issues(states: OPEN) {
     totalCount
   }

   # Note: pullRequests already queried, just need to add:
   # - Store pullRequests.totalCount (all PRs)
   # - Filter by state: OPEN for open_pr_count
   ```

3. **Update GraphQL Parser**
   Store the fields in `collector.py` or `graphql_client.py`:
   ```python
   def _sync_repository_from_graphql(self, repo_data):
       # ... existing code ...

       # ADDITION: Store commit count
       commit_count = repo_data.get('defaultBranchRef', {}).get('target', {}).get('history', {}).get('totalCount', 0)

       # ADDITION: Store open issues
       open_issues_count = repo_data.get('issues', {}).get('totalCount', 0)

       # ADDITION: Count open PRs
       pr_nodes = repo_data.get('pullRequests', {}).get('nodes', [])
       open_pr_count = sum(1 for pr in pr_nodes if pr.get('state') == 'OPEN')

       # Save to repository
       repository.commit_count = commit_count
       repository.open_issues_count = open_issues_count
       repository.open_pr_count = open_pr_count
       repository.save()
   ```

4. **Update REST API Fallback**
   Add fields to REST collection path:
   ```python
   # In collector.py REST sync method
   repository.commit_count = repo.get_commits().totalCount
   repository.open_issues_count = repo.get_issues(state='open').totalCount
   repository.open_pr_count = repo.get_pulls(state='open').totalCount
   ```

5. **Database Migration**
   ```bash
   docker compose exec uwsgi bash -c "python manage.py makemigrations"
   docker compose exec uwsgi bash -c "python manage.py migrate"
   ```

6. **Backfill Existing Repositories**
   Run incremental sync to populate fields for existing 2,451 repositories:
   ```bash
   python manage.py sync_github_repositories --incremental
   ```

### Non-Functional Requirements

1. **Performance**
   - GraphQL query cost increase: <5 points (issues field is cheap)
   - No impact on existing sync time
   - Fields use standard IntegerField (indexed automatically)

2. **Backward Compatibility**
   - Default values (0) for all fields
   - Non-nullable (safe defaults)
   - No breaking changes to existing code

## Implementation Plan

### Step 1: Add Model Fields (10 min)
1. Edit `dojo/models.py`
2. Add 3 IntegerField definitions to Repository class
3. Use appropriate validators (MinValueValidator(0))

**Files Modified:**
- `dojo/models.py`

### Step 2: Update GraphQL Query (5 min)
1. Edit `dojo/github_collector/queries/repository_full.graphql`
2. Add `issues(states: OPEN) { totalCount }` after line 130
3. Verify query syntax

**Files Modified:**
- `dojo/github_collector/queries/repository_full.graphql`

### Step 3: Update GraphQL Parser (10 min)
1. Find GraphQL parsing logic in `collector.py` or `graphql_client.py`
2. Locate `_sync_repository_from_graphql()` or equivalent method
3. Add field extraction and assignment
4. Handle null/missing data gracefully

**Files Modified:**
- `dojo/github_collector/collector.py` or `graphql_client.py`

### Step 4: Update REST Fallback (5 min)
1. Find REST sync method in `collector.py`
2. Add commit_count, open_issues_count, open_pr_count collection
3. Use PyGithub API methods

**Files Modified:**
- `dojo/github_collector/collector.py`

### Step 5: Generate Migration (5 min)
1. Run makemigrations
2. Review generated migration file
3. Apply migration
4. Verify migration success

**Commands:**
```bash
docker compose exec uwsgi bash -c "python manage.py makemigrations"
docker compose exec uwsgi bash -c "python manage.py migrate"
```

### Step 6: Backfill Data (5-10 min)
1. Run incremental sync to populate existing repositories
2. Verify fields are populated
3. Check sample repositories in Django admin

**Commands:**
```bash
docker compose exec uwsgi bash -c "python manage.py sync_github_repositories --incremental"
```

### Step 7: Testing (10 min)
1. Query sample repositories to verify data
2. Check GraphQL query cost (should be ~35-45 points)
3. Verify REST fallback works
4. Test with missing data (null handling)

## Success Criteria

### Functional Criteria
- [ ] Repository model has 3 new fields (commit_count, open_issues_count, open_pr_count)
- [ ] GraphQL query fetches issues.totalCount
- [ ] GraphQL parser stores all 3 fields correctly
- [ ] REST fallback populates all 3 fields
- [ ] Database migration applied successfully
- [ ] Existing 2,451 repositories backfilled with data

### Data Quality Criteria
- [ ] commit_count > 0 for active repositories
- [ ] open_issues_count matches GitHub UI
- [ ] open_pr_count matches GitHub UI
- [ ] Fields handle null/missing data (default to 0)

### Technical Criteria
- [ ] No breaking changes to existing code
- [ ] GraphQL query cost increase < 5 points
- [ ] Migration is reversible
- [ ] Fields follow Django/DefectDojo conventions

## Testing Strategy

### Manual Testing
1. **GraphQL Query Test**
   ```bash
   # Test GraphQL query manually
   python manage.py shell
   >>> from dojo.github_collector.graphql_client import GitHubGraphQLClient
   >>> client = GitHubGraphQLClient(token="ghp_...")
   >>> repo = client.get_repository("myorg", "myrepo")
   >>> print(repo['issues']['totalCount'])
   >>> print(repo['defaultBranchRef']['target']['history']['totalCount'])
   ```

2. **Sync Test**
   ```bash
   # Sync single repository
   python manage.py sync_github_repositories --org myorg --incremental

   # Check results in Django shell
   python manage.py shell
   >>> from dojo.models import Repository
   >>> repo = Repository.objects.get(name="myorg/myrepo")
   >>> print(f"Commits: {repo.commit_count}")
   >>> print(f"Open Issues: {repo.open_issues_count}")
   >>> print(f"Open PRs: {repo.open_pr_count}")
   ```

3. **Django Admin Verification**
   - Navigate to http://localhost:8080/admin/
   - Go to Repositories
   - Check sample repositories have populated fields

### Edge Cases
- Repository with 0 commits (new/empty repo)
- Repository with no issues enabled
- Repository with null pull requests data
- Archived repository

## Code Examples

### GraphQL Query Addition
**File**: `dojo/github_collector/queries/repository_full.graphql`

Add after line 135 (after `vulnerabilityAlerts`):
```graphql
# Open issues count (enterprise work backlog metric)
issues(states: OPEN) {
  totalCount
}
```

### Model Field Definitions
**File**: `dojo/models.py`

Add to Repository class (around line 1600, in metadata section):
```python
# Activity Metrics (added for enterprise GitHub management insights)
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
```

### GraphQL Parser Update
**File**: `dojo/github_collector/collector.py` (or `graphql_client.py`)

In `_sync_repository_from_graphql()` method:
```python
def _sync_repository_from_graphql(self, repo_data, product):
    # ... existing code ...

    # Extract commit count (already queried!)
    commit_count = 0
    if repo_data.get('defaultBranchRef') and repo_data['defaultBranchRef'].get('target'):
        commit_history = repo_data['defaultBranchRef']['target'].get('history', {})
        commit_count = commit_history.get('totalCount', 0)

    # Extract open issues count
    open_issues_count = repo_data.get('issues', {}).get('totalCount', 0)

    # Extract open PR count (filter existing PR data by state)
    open_pr_count = 0
    pr_nodes = repo_data.get('pullRequests', {}).get('nodes', [])
    if pr_nodes:
        open_pr_count = sum(1 for pr in pr_nodes if pr.get('state') == 'OPEN')

    # ... existing repository creation/update code ...

    # Set new fields
    repository.commit_count = commit_count
    repository.open_issues_count = open_issues_count
    repository.open_pr_count = open_pr_count

    repository.save()

    logger.info(
        f"Repository {repository.name}: "
        f"{commit_count} commits, "
        f"{open_issues_count} open issues, "
        f"{open_pr_count} open PRs"
    )
```

## Estimated Effort

**Total**: 30 minutes - 1 hour

**Breakdown**:
- Model changes: 10 min
- GraphQL query: 5 min
- GraphQL parser: 10 min
- REST fallback: 5 min
- Migration: 5 min
- Backfill: 5-10 min
- Testing: 10 min

**Code Volume**: ~50 lines
- Model: 15 lines
- GraphQL query: 5 lines
- Parser: 20 lines
- REST: 10 lines

## Dependencies

- Existing Repository model
- GraphQL infrastructure (Phase 1-3)
- GitHub PAT with `repo:read` permissions
- PostgreSQL database

## Relation to GitHub Insights Dashboard

This task is a **prerequisite** for the following insights:
- Highest Commit Frequency (commits/week) - REQUIRES `commit_count`
- Activity-Vulnerability Correlation - REQUIRES accurate `commit_count`
- Repositories with High Issue Count - REQUIRES `open_issues_count`
- Work in Progress tracking - REQUIRES `open_pr_count`

## Work Log

### 2025-11-16 - Task Created
- Created task specification
- Identified 3 fields to add (commit_count, open_issues_count, open_pr_count)
- Estimated 30 min - 1 hour effort
- Prerequisite for GitHub Insights Dashboard task
