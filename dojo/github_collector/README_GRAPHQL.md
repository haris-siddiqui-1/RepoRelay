# GitHub GraphQL Migration

## Overview

The GitHub collector has been migrated from REST API v3 to GraphQL API v4 for improved performance and efficiency.

**Key Benefits**:
- **2x faster daily incremental syncs** (<5 minutes vs ~10 minutes)
- **Better data consistency** (atomic snapshots vs 18 separate API calls)
- **Simpler codebase** (1 GraphQL query vs 18 REST endpoints)
- **Automatic REST fallback** for error recovery

**Performance Targets**:
- Initial full sync: <24 hours (one-time operation)
- **Daily incremental sync: <5 minutes** (typical 50-100 changed repos)
- Single repository sync: <1 second

## Architecture

### Core Components

1. **`graphql_client.py`** - GitHub GraphQL API client
   - Single repository queries
   - Organization-level batch queries
   - Incremental sync filtering by `updatedAt`
   - Rate limit monitoring

2. **`collector.py`** (Enhanced) - Repository sync orchestrator
   - GraphQL support with `use_graphql=True` parameter
   - Automatic REST fallback on errors
   - Incremental sync logic (only fetch changed repos)
   - All 36 binary signal detection from GraphQL data

3. **`queries/`** - GraphQL query templates
   - `repository_full.graphql` - Complete single-repo query (~40 points)
   - `organization_batch.graphql` - Batch query for 100 repos per page

### Query Cost Analysis

Based on GitHub's complexity-based rate limiting (5,000 points/hour):

| Operation | Cost | Time | Use Case |
|-----------|------|------|----------|
| Single repo query | 30-40 points | <1 sec | Individual sync |
| Org batch (100 repos) | ~4,000 points | ~1 min | Full sync |
| Full org (2,451 repos) | 98,000 points | 15-20 hrs | Initial load |
| Incremental (50 repos) | 2,000 points | <5 min | **Daily sync** ⭐ |

### Incremental Sync Strategy

The key to fast daily syncs is **proper incremental filtering**:

1. **Find most recent sync timestamp**
   ```python
   updated_since = Product.objects.filter(
       github_url__isnull=False
   ).order_by('-updated').first().updated
   ```

2. **Fetch only changed repos**
   ```python
   repos = graphql_client.get_organization_repositories(
       org="myorg",
       updated_since=updated_since  # Filter at GraphQL level
   )
   ```

3. **Result**: Typically 50-100 repos (2-4% of total) synced in <5 minutes

## Usage

### Management Command

```bash
# Daily incremental sync with GraphQL (recommended)
python manage.py sync_github_repositories --incremental

# Full sync with GraphQL (one-time, 15-20 hours)
python manage.py sync_github_repositories

# Use REST API (fallback)
python manage.py sync_github_repositories --use-rest --incremental

# Sync specific organization
python manage.py sync_github_repositories --org myorg --incremental

# Dry run (list repos without syncing)
python manage.py sync_github_repositories --dry-run
```

### Python API

```python
from dojo.github_collector import GitHubRepositoryCollector

# Initialize with GraphQL (default)
collector = GitHubRepositoryCollector(
    github_token="ghp_...",
    github_org="myorg",
    use_graphql=True  # Default
)

# Incremental sync (recommended for daily use)
stats = collector.sync_all_repositories(incremental=True)
# Expected: 50-100 repos, <5 minutes

# Full sync (one-time)
stats = collector.sync_all_repositories(incremental=False)
# Expected: 2,451 repos, 15-20 hours

# Sync single product
from dojo.models import Product
product = Product.objects.get(name="myorg/myrepo")
collector.sync_product_from_github_url(product)
```

### Testing

```bash
# Run test suite
cd dojo/github_collector
python test_graphql.py

# Tests:
# 1. GraphQL client initialization
# 2. Single repo query cost measurement
# 3. Organization batch query
# 4. Incremental sync filtering
# 5. Signal detection from GraphQL data
# 6. Full sync simulation (10 repos)
```

## Configuration

### Environment Variables

```bash
# Required
DD_GITHUB_TOKEN="ghp_..."        # Personal access token
DD_GITHUB_ORG="myorg"             # Organization name

# Optional
DD_AUTO_ARCHIVE_DAYS=180          # Days before marking repo as dormant
```

### GitHub Token Permissions

Required scopes:
- `repo:read` - Repository metadata and code
- `admin:org:read` - Organization members (for contributor counting)

Optional scopes:
- `security_events:read` - Vulnerability alerts (for `has_secret_scanning` signal)

## GraphQL Query Fields

### Repository Metadata
- `name`, `nameWithOwner`, `description`, `url`, `databaseId`
- `isArchived`, `diskUsage`, `updatedAt`
- `primaryLanguage { name }`

### Commit History (50 commits)
- `defaultBranchRef.target.history(first: 50)`
- `committedDate`, `author { name, email, user { login } }`
- Used for: `last_commit_date`, `active_contributors_90d`, `days_since_last_commit`

### File Tree
- `object(expression: "HEAD:") { ... on Tree { entries { name, path, type } } }`
- Used for: All file-based signal detection (Dockerfile, CI/CD configs, etc.)

### File Content
- `object(expression: "HEAD:CODEOWNERS") { ... on Blob { text } }`
- `object(expression: "HEAD:.github/CODEOWNERS") { ... on Blob { text } }`
- `object(expression: "HEAD:docs/CODEOWNERS") { ... on Blob { text } }`
- `object(expression: "HEAD:README.md") { ... on Blob { text } }`

### GitHub Settings
- `environments(first: 1) { totalCount }` - Deployment environments
- `releases(first: 3) { totalCount, nodes { createdAt, tagName } }` - Recent releases
- `branchProtectionRules(first: 1) { totalCount }` - Branch protection
- `pullRequests(first: 10) { totalCount, nodes { state, updatedAt, author } }` - PR activity
- `vulnerabilityAlerts(first: 1) { totalCount }` - Security scanning

### Rate Limit Monitoring
- `rateLimit { cost, remaining, resetAt }`
- Logged after every query for tracking

## Binary Signals (36 Total)

All 36 signals work identically with GraphQL data:

### Tier 1: Deployment (6 signals)
- `has_dockerfile`, `has_kubernetes_config`, `has_ci_cd`
- `has_terraform`, `has_deployment_scripts`, `has_environments`

### Tier 2: Production (5 signals)
- `has_monitoring`, `has_releases`, `recent_release_90d`
- `has_branch_protection`, `has_codeowners`

### Tier 3: Development Activity (5 signals)
- `recent_commits_30d`, `recent_commits_90d`, `active_contributors`
- `active_prs_30d`, `has_dependabot`

### Tier 4: Code Organization (6 signals)
- `has_tests`, `has_documentation`, `has_readme`
- `readme_length_500`, `has_api_spec`, `has_changelog`

### Tier 5: Security (5 signals)
- `has_security_policy`, `has_secret_scanning`, `has_sbom`
- `has_security_txt`, `has_code_scanning`

### Additional Signals (9 signals)
- `has_package_manager`, `has_license`, `has_contributing_guide`
- `has_code_of_conduct`, `has_issue_templates`, `has_pr_template`
- `has_gitignore`, and more

## Error Handling & Fallback

### Automatic REST Fallback

If GraphQL query fails, collector automatically falls back to REST:

```python
try:
    # Attempt GraphQL sync
    repos_data = self.graphql_client.get_organization_repositories(org)
    for repo_data in repos_data:
        self._sync_repository_from_graphql(repo_data)
except Exception as e:
    logger.error(f"GraphQL sync failed: {e}")
    logger.info("Falling back to REST API")
    # Fall back to REST
    return self._sync_all_with_rest(incremental, stats)
```

### Permission Errors

Some fields may return `null` without proper permissions:
- `vulnerabilityAlerts` - Requires security permissions
- `environments` - May be hidden for private repos
- `branchProtectionRules` - Requires push access

**Handling**: Default to `False` for binary signals when null

### Large Repositories

Repos with 10,000+ files may timeout on file tree queries:
- GraphQL query only fetches top-level tree (not recursive)
- If timeout occurs, REST fallback is used
- Individual file checks use targeted queries

### Email Privacy

GitHub users can hide email addresses:
- `commit.author.email` may be `null` or `noreply@github.com`
- **Fallback**: Use `commit.author.user.login` or `commit.author.name`
- Contributor counting uses email → login → name priority

## Migration Notes

### Backward Compatibility

- ✅ All existing REST code paths preserved
- ✅ Can switch between GraphQL and REST with `use_graphql` parameter
- ✅ Individual product sync still uses REST (real-time updates)
- ✅ All 36 binary signals produce identical results

### Performance Comparison

| Scenario | REST API | GraphQL | Winner |
|----------|----------|---------|--------|
| Initial full sync (2,451 repos) | 6-9 hours | 15-20 hours | ❌ REST |
| Daily incremental sync (50 repos) | ~10 minutes | **<5 minutes** | ✅ **GraphQL** |
| Single repo sync | Instant | Instant | ✅ Equal |

**Recommendation**: Use GraphQL for bulk operations, REST for individual syncs

### Breaking Changes

**None** - GraphQL is additive, not replacing:
- REST fallback ensures zero downtime
- Can opt-out with `--use-rest` flag
- All APIs remain unchanged

## Troubleshooting

### High Rate Limit Usage

**Symptom**: "Rate limit running low" warnings in logs

**Solutions**:
1. Use incremental sync (`--incremental`)
2. Reduce batch size in organization query
3. Run sync during off-hours
4. Check if multiple syncs are running concurrently

### GraphQL Query Errors

**Symptom**: "GraphQL query failed" errors

**Solutions**:
1. Check token permissions (`repo:read`, `admin:org:read`)
2. Verify organization name is correct
3. Check if repository is accessible (not private without access)
4. Review GraphQL error message for specific field issues

### Slow Incremental Sync

**Symptom**: Incremental sync taking >5 minutes

**Solutions**:
1. Check how many repos are being synced (should be <100)
2. Verify `Product.updated` timestamps are recent
3. Check rate limit remaining (may be throttled)
4. Review logs for slow individual repo syncs

### Signal Detection Mismatches

**Symptom**: Signals differ between GraphQL and REST

**Solutions**:
1. Check file tree completeness (large repos may be truncated)
2. Verify GraphQL data parsing in `_detect_signals_from_graphql()`
3. Compare REST vs GraphQL results for specific repo
4. File issue if systematic mismatch found

## Performance Optimization Tips

1. **Always use incremental sync for daily operations**
   ```bash
   python manage.py sync_github_repositories --incremental
   ```

2. **Schedule full sync during off-hours**
   ```bash
   # Cron: Run full sync weekly at 2 AM Sunday
   0 2 * * 0 python manage.py sync_github_repositories
   ```

3. **Monitor rate limit usage**
   ```bash
   # Check logs for rate limit warnings
   grep "Rate limit" /var/log/defectdojo/github_sync.log
   ```

4. **Use REST for single repo updates**
   ```python
   # For real-time updates, REST is instant
   collector = GitHubRepositoryCollector(use_graphql=False)
   collector.sync_product_from_github_url(product)
   ```

## Future Enhancements

Potential optimizations for future versions:

1. **Parallel GraphQL queries** - Fetch multiple repos simultaneously
2. **Smart batch sizing** - Adjust batch size based on rate limit
3. **Delta sync** - Only update changed fields, not full product
4. **Query caching** - Cache organization-level metadata
5. **Webhook integration** - Real-time updates instead of polling

## References

- [GitHub GraphQL API Documentation](https://docs.github.com/en/graphql)
- [GraphQL Rate Limiting](https://docs.github.com/en/graphql/overview/resource-limitations)
- [Repository Object Schema](https://docs.github.com/en/graphql/reference/objects#repository)
- [Architecture Decision Record](./ARCHITECTURE_DECISION.md)
- [Field Verification](./GRAPHQL_VERIFICATION.md)
