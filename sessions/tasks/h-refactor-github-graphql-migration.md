---
name: h-refactor-github-graphql-migration
branch: feature/github-graphql-migration
status: pending
created: 2025-01-12
---

# GitHub API Migration: REST to GraphQL for Bulk Operations

## Problem/Goal

The current GitHub repository collector (`dojo/github_collector/`) uses PyGithub's REST API exclusively, resulting in severe performance and rate limit issues when syncing 2,451 repositories:

**Current Performance Problems**:
- **13-18 REST API calls per repository** (31,863-44,118 total calls)
- **6-9 hours sync time** due to rate limiting (5,000 calls/hour limit)
- **640% over hourly rate limit** - requires multiple sync windows
- **Expensive operations**: `get_git_tree(recursive=True)` for every repo
- **3 separate calls** just to check CODEOWNERS file locations
- **Data inconsistency risk**: Each call sees potentially different commit states

**Goal**: Replace REST API calls with optimized GraphQL queries for bulk organization syncs while maintaining REST for individual on-demand updates.

**Expected Improvements**:
- Reduce API calls by **94%** (31,863 → 2,451 calls)
- Reduce sync time by **97%** (6-9 hours → 10 minutes)
- Ensure atomic data snapshots (all data from same commit state)
- Simplify error handling (single query vs. 13-18 individual calls)
- Enable future scaling beyond 2,451 repositories

## Success Criteria

**Phase 1: GitHub API Documentation Review & Architecture Validation**
- [ ] Review GitHub GraphQL schema documentation at https://docs.github.com/en/graphql/reference
- [ ] Verify `repository` query supports all required fields (metadata, commits, files, etc.)
- [ ] Verify `object(expression:)` field works for file content retrieval
- [ ] Verify `defaultBranchRef.target.history` provides commit data with author emails
- [ ] Verify `environments`, `releases`, `branchProtectionRules` fields exist and work as expected
- [ ] Verify `vulnerabilityAlerts` field availability and structure
- [ ] Confirm rate limit calculation: query complexity vs. 5,000 points/hour quota
- [ ] Document any limitations or fields not available in GraphQL (fallback to REST)
- [ ] Create validated GraphQL query structure with all fields confirmed working
- [ ] Architecture review approved: GraphQL approach solves the performance problem

**Phase 2: Implementation (only after Phase 1 complete)**
- [ ] GraphQL client module created using validated query structure
- [ ] Single GraphQL query replaces 13-18 REST calls per repository
- [ ] Bulk sync (`sync_all_repositories`) uses GraphQL exclusively
- [ ] Individual sync (`sync_product_from_github_url`) retains REST for real-time updates
- [ ] All 36 binary signals still detected correctly from GraphQL responses
- [ ] CODEOWNERS detection works from GraphQL (checks all 3 paths in one query)
- [ ] File tree detection uses GraphQL `object(expression:)` instead of `get_git_tree()`
- [ ] Contributor counting works from GraphQL commit history
- [ ] Error handling implemented for GraphQL-specific errors (422 validation, partial responses)
- [ ] Backward compatibility: REST fallback works if GraphQL query fails

**Phase 3: Testing & Validation**
- [ ] Test sync of 10 repositories completes in <30 seconds (vs. current ~5 minutes)
- [ ] Full 2,451 repo sync completes in <15 minutes (vs. current 6-9 hours)
- [ ] Rate limit usage stays under 50% of hourly quota during full sync
- [ ] All 36 binary signals produce identical results between GraphQL and REST implementations

## Context Manifest

### How the Current GitHub Collector Works

The current implementation uses PyGithub 2.8.1 (REST API v3) with a collector → signal detector → tier classifier pipeline architecture. Here's the complete data flow:

**Entry Point: `GitHubRepositoryCollector.sync_all_repositories()`**

When syncing 2,451 repositories, the collector authenticates once using `Github(auth=Auth.Token(token))` from `dojo/github.py` patterns, then iterates through each repository sequentially. For each repository, it makes 18-19 separate REST API calls:

1. **`sync_repository(repo)`** orchestrates the workflow by calling three sub-components in sequence
2. **`_collect_repository_metadata(repo)`** makes 5 API calls to gather basic activity data
3. **`SignalDetector(repo).detect_all_signals()`** makes 12-13 API calls to detect binary indicators
4. **`ReadmeSummarizer(repo).extract_and_summarize()`** makes 1 API call (duplicate README fetch)

**Component 1: Metadata Collection (`collector.py` lines 220-269)**

The `_collect_repository_metadata()` method fetches repository activity data:

- **Call 1**: `repo.get_commits()[:1]` - Gets most recent commit for `last_commit_date` and calculates `days_since_last_commit`
- **Call 2**: `repo.get_commits(since=90_days_ago)` - Iterates ALL commits in last 90 days to count unique contributor emails for `active_contributors_90d` field (lines 247-257)
- **Calls 3-5**: Three separate `repo.get_contents(path)` calls checking CODEOWNERS in three locations: root, `.github/`, and `docs/` directories (lines 283-296). Each 404 error is silently caught until one succeeds.

This returns a dictionary: `{'last_commit_date': datetime, 'days_since_last_commit': int, 'active_contributors_90d': int, 'codeowners_content': str, 'ownership_confidence': int}`

**Component 2: Signal Detection (`signal_detector.py` lines 169-223)**

The `SignalDetector` class accepts a PyGithub `Repository` object and detects 36 binary signals organized into 5 categories. The critical performance bottleneck is the recursive file tree fetch:

- **Call 6 (THE BIG ONE)**: `repo.get_git_tree(default_branch, recursive=True)` at line 233 - This single call fetches the ENTIRE file tree recursively and caches it in `self.file_tree_cache` as a list of file paths. This is used for pattern matching against 20+ different file patterns (Dockerfile, kubernetes configs, CI/CD configs, test directories, etc.)

After caching the tree, the detector makes 12 additional API calls for metadata that cannot be inferred from file presence:

- **Call 7**: `repo.get_environments()` - GitHub environments configured (line 280)
- **Call 8**: `repo.get_releases()[:1]` - Check if any releases exist (line 289)
- **Call 9**: `repo.get_branch(default_branch)` - Check if default branch is protected (line 298)
- **Call 10**: `repo.get_commits(since=30d)[:1]` - Check for recent commits (line 309)
- **Call 11**: `repo.get_pulls(state='all', sort='updated', direction='desc')[:10]` - Check for active PRs in last 30 days (line 320)
- **Call 12**: `repo.get_commits(since=90d)[:100]` - Sample 100 commits to count unique authors for `multiple_contributors` signal (line 332)
- **Call 13**: `repo.get_commits()[:20]` - Check recent 20 commits for dependabot author emails (line 343)
- **Call 14**: `repo.get_pulls()[:10]` - Check recent 10 PRs for dependabot user (line 349)
- **Call 15**: `repo.get_releases()[:5]` - Check if any of last 5 releases are in last 90 days (line 364)
- **Call 16**: `repo.get_commits()[:100]` - Sample 100 commits to detect consistent commit pattern by grouping into weeks (line 379)
- **Call 17**: `repo.get_readme()` - Fetch README to check if length > 500 chars for documentation signal (line 405)
- **Call 18**: `repo.get_vulnerability_alert()` - Check if secret scanning alerts configured (line 439)

Returns dictionary of 36 boolean signals: `{'has_dockerfile': bool, 'has_kubernetes_config': bool, ..., 'has_sast_config': bool}`

**Signal Categories Requiring File Tree Access:**
- Deployment indicators: Dockerfile, K8s configs, CI/CD workflows, Terraform, deployment scripts, Procfile
- Infrastructure: Monitoring configs, SSL configs, database migrations
- Code organization: Test directories, docs directories, API specs, monorepo detection
- Security: SECURITY.md, gitleaks config, SAST configs, Dependabot/Renovate config files

**Signals Requiring GitHub API Metadata (NOT in file tree):**
- `has_environments`, `has_releases`, `has_branch_protection` - GitHub settings
- `recent_commits_30d`, `active_prs_30d`, `multiple_contributors`, `has_dependabot_activity`, `recent_releases_90d`, `consistent_commit_pattern` - Activity analysis
- `has_secret_scanning` - Security settings via vulnerability alerts

**Component 3: README Summarization (`readme_summarizer.py` lines 91-124)**

The `ReadmeSummarizer` class:
- **Call 19**: `repo.get_readme()` - Fetches README content (DUPLICATE of call #17)
- Extracts first 500 characters as summary
- Detects primary language and framework via regex patterns
- Returns: `{'summary': str, 'length': int, 'primary_language': str, 'primary_framework': str, 'raw_content': str}`

**Component 4: Tier Classification (`tier_classifier.py` lines 46-96)**

The `TierClassifier` performs pure logic (NO API calls) - takes the signals dictionary and `days_since_last_commit` integer and applies rule-based classification:
- Tier 1 (Critical): Containerized + environments + monitoring + active
- Tier 2 (High): CI/CD + releases + branch protection + multiple contributors
- Tier 3 (Medium): Tests + active + documentation
- Tier 4 (Low): Everything else
- Archived: > 180 days since last commit

Returns: `{'tier': int|'archived', 'business_criticality': str, 'confidence_score': int, 'reasons': list[str]}`

**Data Persistence: Product Model Updates**

All collected data gets written to the `Product` model in `dojo/models.py` (lines 1196-1362). The Product model stores:

**Activity fields** (lines 1227-1235):
- `last_commit_date` (DateTimeField)
- `active_contributors_90d` (IntegerField)
- `days_since_last_commit` (IntegerField)

**Repository metadata** (lines 1238-1256):
- `github_url` (URLField)
- `github_repo_id` (CharField)
- `readme_summary` (TextField, max 500 chars)
- `readme_length` (IntegerField)
- `primary_language` (CharField, max 50)
- `primary_framework` (CharField, max 50)

**Ownership** (lines 1258-1262):
- `codeowners_content` (TextField)
- `ownership_confidence` (IntegerField)

**36 Binary signal fields** (lines 1267-1362):
- All 36 BooleanFields with descriptive help text

**Classification** (line 1199):
- `business_criticality` (CharField with choices: "very high", "high", "medium", "low", "none")

The update happens in a `transaction.atomic()` block at lines 146-176 of `collector.py`, using `setattr(product, signal_name, signal_value)` to write all 36 signals dynamically.

**Incremental Sync Logic (`collector.py` lines 304-329)**

The `_should_skip_repo()` method implements incremental syncing by comparing timestamps:
- Fetches Product by `repo.full_name` (e.g., "DefectDojo/django-DefectDojo")
- Compares `repo.updated_at` (GitHub's last update timestamp) vs. `product.updated` (Django's last save timestamp)
- Skips repository if `repo.updated_at <= product.updated` (no changes since last sync)
- This reduces work but doesn't reduce API calls for repos that DO need syncing

**Error Handling Patterns**

The codebase uses three error handling approaches:

1. **Top-level try/catch** in `sync_all_repositories()` (lines 110-113): Catches `GithubException` and logs error, increments `stats['errors']`, continues with next repository

2. **Individual call try/catch** in metadata/signal methods: Catches generic `Exception`, logs warning with `logger.debug()` or `logger.warning()`, returns safe default (empty string, 0, False)

3. **Silent 404 handling** in CODEOWNERS fetch (lines 285-296): Uses nested try/catch to check 3 paths, only logs debug message if all fail

**Rate Limiting Issues**

GitHub REST API v3 has a 5,000 requests/hour limit for authenticated users. With 2,451 repositories × 18 calls = 44,118 calls, this requires ~9 hours of sync time with rate limit delays. PyGithub automatically handles rate limiting by sleeping when limits are hit, but there's no explicit rate limit checking or pre-emptive throttling in the collector code.

### What the GraphQL Migration Needs to Do

The new `graphql_client.py` module must replace the 18 REST calls with a SINGLE GraphQL query per repository that fetches:

**1. Repository Metadata** (replaces REST calls 1-2):
```
repository {
  name
  description
  url
  primaryLanguage { name }
  defaultBranchRef {
    name
    target {
      ... on Commit {
        history(first: 100) {
          nodes {
            committedDate
            author { email }
          }
        }
      }
    }
  }
}
```

**2. File Tree & Content** (replaces REST calls 3-6, 17):
Must use `object(expression:)` field to fetch file tree AND specific file contents in one query:
```
object(expression: "HEAD:") {
  ... on Tree {
    entries {
      name
      path
      type
    }
  }
}
# Plus 4 separate object queries for:
# - "HEAD:CODEOWNERS"
# - "HEAD:.github/CODEOWNERS"
# - "HEAD:docs/CODEOWNERS"
# - "HEAD:README.md"
```

**3. GitHub Settings & Activity** (replaces REST calls 7-16, 18):
```
environments(first: 1) { totalCount }
releases(first: 5) { nodes { createdAt } }
branchProtectionRules(first: 1) { totalCount }
pullRequests(first: 10, states: [OPEN, MERGED, CLOSED], orderBy: {field: UPDATED_AT, direction: DESC}) {
  nodes {
    updatedAt
    author { login }
  }
}
vulnerabilityAlerts(first: 1) { totalCount }
```

**4. Data Structure Requirements**

The GraphQL response parser must produce dictionaries matching the EXACT structure that `SignalDetector` and tier classification currently expect:

For `SignalDetector` constructor modification (line 159):
- Currently accepts: `PyGithub.Repository` object
- Needs new parameter: `graphql_data: Optional[Dict] = None`
- When `graphql_data` is provided, skip all REST API calls
- Extract signals from pre-fetched data instead

The file tree cache (line 234) currently stores: `['path/to/file1.py', 'path/to/file2.js', ...]`

GraphQL will provide: `[{'name': 'file1.py', 'path': 'path/to/file1.py', 'type': 'blob'}, ...]`

Need to extract just paths: `[entry['path'] for entry in graphql_data['tree']['entries']]`

**5. Integration Points**

The GraphQL implementation must integrate at two locations:

**A) Bulk sync** (`sync_all_repositories()` at line 61):
- Add parameter: `use_graphql: bool = True`
- When True: Fetch all repos via GraphQL, parse responses, call `sync_repository()` with pre-fetched data
- When False: Keep existing REST iteration (for backward compatibility)

**B) Individual sync** (`sync_product_from_github_url()` at line 331):
- Keep using REST API (real-time updates, single repo = minimal performance impact)
- GraphQL optimization only worthwhile for bulk operations

**6. Backward Compatibility Strategy**

The migration must maintain REST fallback:
1. Try GraphQL query first
2. If GraphQL fails (422 validation error, field not available, etc.): Log warning and fall back to REST
3. `SignalDetector` must support both modes: `SignalDetector(repo, graphql_data=None)` where `graphql_data` being None triggers REST behavior

### Critical Implementation Details

**File Paths to Understand:**
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/collector.py` - Main orchestrator (370 lines)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/signal_detector.py` - Binary signal detection (458 lines)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/tier_classifier.py` - Tier classification logic (274 lines)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/readme_summarizer.py` - README extraction (282 lines)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github.py` - Existing GitHub integration patterns (153 lines)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/models.py` - Product model definition (lines 1196-1362)

**Authentication Pattern to Follow:**
```python
from github import Auth, Github

auth = Auth.Token(github_token)
github_client = Github(auth=auth)
```

**PyGithub Version:** 2.8.1 (from requirements.txt line 27)

**Django Transaction Pattern:**
```python
from django.db import transaction

with transaction.atomic():
    product.field1 = value1
    product.field2 = value2
    product.save()
```

**Key Data Structure: File Tree Cache**

The file tree cache is critical - it's used by `_detect_pattern()` method (lines 240-271) which implements glob-style pattern matching:
- Converts `*` wildcards to regex: `pattern.replace('*', '.*')`
- Directory checks: `path.startswith('kubernetes/')`
- Exact file checks: `'Dockerfile' in file_tree_cache`

GraphQL must provide compatible data structure: list of path strings.

**API Call Deduplication Opportunities**

Current implementation makes duplicate calls:
- `get_commits()` called 4 times with different parameters (calls 1, 2, 10, 12, 13, 16)
- `get_pulls()` called 2 times (calls 11, 14)
- `get_releases()` called 2 times (calls 8, 15)
- `get_readme()` called 2 times (calls 17, 19)

GraphQL can fetch commit history ONCE and filter in memory for all use cases.

**Performance Target Validation**

Current state: 2,451 repos × 18 calls = 44,118 REST calls
Target state: 2,451 repos × 1 call = 2,451 GraphQL calls
Reduction: 94% fewer API calls

Time reduction: 6-9 hours → ~10 minutes assumes:
- GraphQL query takes ~250ms per repo (network + processing)
- No rate limit delays (staying under 5,000 calls/hour)
- 2,451 calls × 0.25 seconds = 613 seconds = ~10 minutes

**Error Cases to Handle**

1. **404 errors**: File doesn't exist (CODEOWNERS, README)
   - Current: Silently catch exception, return empty string
   - GraphQL: Check if `object(expression:)` returns null, return empty string

2. **Rate limit errors**: GitHub responds with rate limit exceeded
   - Current: PyGithub automatically sleeps
   - GraphQL: Need manual rate limit checking via `rateLimit { remaining, resetAt }` field

3. **Validation errors**: GraphQL query syntax invalid (422 status)
   - New error type: Log error, fall back to REST for this repository

4. **Partial data**: Some fields not available (repository settings hidden)
   - GraphQL returns null for unavailable fields
   - Default to False for missing binary signals

**Testing Strategy**

The implementation must be testable with:
1. Unit tests: Mock GraphQL responses, verify parsing produces correct signal dictionaries
2. Integration test: Run on 10 real repositories, compare GraphQL vs REST results for all 36 signals
3. Performance test: Measure actual API call count and time for 10, 50, 100 repository batches
4. Fallback test: Simulate GraphQL failure, verify REST fallback works correctly

## Implementation Notes

### Files to Modify

1. **NEW**: `dojo/github_collector/graphql_client.py` (~200 lines)
   - GraphQL query templates
   - Response parsing logic
   - Error handling for GraphQL-specific failures

2. **MODIFY**: `dojo/github_collector/collector.py` (~50 lines changed)
   - Add `use_graphql=True` parameter to `sync_all_repositories()`
   - Replace `_collect_repository_metadata()` with GraphQL batch query
   - Keep REST path for `sync_product_from_github_url()` (individual syncs)

3. **MODIFY**: `dojo/github_collector/signal_detector.py` (~100 lines changed)
   - Add constructor parameter to accept pre-fetched GraphQL data
   - Replace individual API calls with data extraction from GraphQL response
   - Keep REST fallback for when GraphQL data not available

### GraphQL Query Structure to Verify

The main query will fetch:
- Repository metadata (name, description, url, language, etc.)
- Last commit date and author
- Commit history (last 100 commits for contributor analysis)
- File tree (via `object(expression: "HEAD:")` - NOT recursive get_git_tree)
- CODEOWNERS content (check 3 paths: root, .github/, docs/)
- README content
- Environments list
- Releases list
- Branch protection status
- Pull requests (recent 10)
- Vulnerability alerts count

**Verification Required**: Confirm all fields exist in GitHub GraphQL schema v4 at https://docs.github.com/en/graphql/reference

### Testing Strategy

1. **Unit Tests**: Mock GraphQL responses, verify parsing logic
2. **Integration Test**: Sync 10 real repositories, compare results with REST
3. **Performance Test**: Measure API calls and time for 10, 50, 100 repositories
4. **Rate Limit Test**: Monitor rate limit consumption during test syncs
5. **Fallback Test**: Verify REST fallback when GraphQL query fails

### API Documentation References

- GitHub GraphQL Schema: https://docs.github.com/en/graphql/reference
- GitHub GraphQL Explorer: https://docs.github.com/en/graphql/overview/explorer
- Rate Limiting: https://docs.github.com/en/graphql/overview/resource-limitations
- Best Practices: https://docs.github.com/en/graphql/guides/forming-calls-with-graphql

## User Notes

**Requirements from user**:
- Integrate GraphQL replacing REST where applicable
- Confirm all details with GitHub API docs for verification
- Test logic thoroughly before deployment

**Constraints**:
- EPSS integration remains separate (FIRST.org API) - no change needed
- Custom Properties API not required - no change needed
- Webhooks not needed - polling strategy acceptable
- Must maintain existing functionality - no breaking changes to signal detection

## Work Log
<!-- Updated as work progresses -->
- [2025-01-12] Task created, performance analysis completed
