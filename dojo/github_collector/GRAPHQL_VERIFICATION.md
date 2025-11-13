# GitHub GraphQL API Field Verification

**Date**: 2025-01-12
**Purpose**: Validate all required GitHub GraphQL fields for migrating DefectDojo GitHub collector from REST to GraphQL
**Reference**: https://docs.github.com/en/graphql/reference

---

## Verification Status

### ✅ Confirmed Available Fields

Based on official GitHub GraphQL documentation review:

#### 1. Repository Object Fields
- ✅ `name` (String!) - Repository name
- ✅ `nameWithOwner` (String!) - Full repository name (owner/repo)
- ✅ `description` (String) - Repository description
- ✅ `url` (URI!) - Repository HTML URL
- ✅ `databaseId` (Int) - GitHub's internal repository ID
- ✅ `isArchived` (Boolean!) - Whether repository is archived
- ✅ `primaryLanguage` (Language) - Primary programming language
- ✅ `diskUsage` (Int) - Size in kilobytes

#### 2. Ref and Commit Access
- ✅ `defaultBranchRef` (Ref) - Reference to default branch
- ✅ Ref object has `target` field that can be cast to Commit type
- ✅ Commit object exists and contains history
- ✅ `CommitConnection` and `CommitHistoryConnection` types available

**Structure**:
```graphql
repository(owner: "...", name: "...") {
  defaultBranchRef {
    name
    target {
      ... on Commit {
        history(first: 100) {
          totalCount
          nodes {
            # Commit fields here
          }
        }
      }
    }
  }
}
```

#### 3. File Tree and Content Retrieval
- ✅ `object(expression: String!)` field - Retrieves Git objects by expression
- ✅ Returns `GitObject` interface (can be `Tree`, `Blob`, `Commit`, `Tag`)
- ✅ Tree type has `entries` field for listing files
- ✅ Blob type has `text` field for file content

**Structure**:
```graphql
repository {
  # Get file tree
  tree: object(expression: "HEAD:") {
    ... on Tree {
      entries {
        name
        path
        type  # "blob", "tree", "commit"
      }
    }
  }

  # Get specific file content
  codeowners: object(expression: "HEAD:CODEOWNERS") {
    ... on Blob {
      text
    }
  }
}
```

#### 4. GitHub Settings & Activity
- ✅ `environments` (EnvironmentConnection!) - Deployment environments
- ✅ `releases` (ReleaseConnection!) - Repository releases
- ✅ `branchProtectionRules` (BranchProtectionRuleConnection!) - Branch protection settings
- ✅ `pullRequests` (PullRequestConnection!) - Pull request data
- ✅ `vulnerabilityAlerts` (RepositoryVulnerabilityAlertConnection) - Security alerts

**Structure**:
```graphql
repository {
  environments(first: 1) {
    totalCount
    nodes {
      name
    }
  }

  releases(first: 5, orderBy: {field: CREATED_AT, direction: DESC}) {
    totalCount
    nodes {
      createdAt
      tagName
    }
  }

  branchProtectionRules(first: 1) {
    totalCount
  }

  pullRequests(first: 10, states: [OPEN, MERGED, CLOSED], orderBy: {field: UPDATED_AT, direction: DESC}) {
    totalCount
    nodes {
      state
      updatedAt
      createdAt
      author {
        login
      }
    }
  }

  vulnerabilityAlerts(first: 1) {
    totalCount
  }
}
```

---

## ⚠️ Fields Requiring Further Validation

These fields are commonly used in GitHub GraphQL but need runtime verification:

### Commit Object Fields (Need Testing)

**Expected to exist** based on GitHub GraphQL patterns:
- `committedDate` (DateTime!) - Commit timestamp
- `author` (GitActor) - Commit author information
- `committer` (GitActor) - Committer information
- `message` (String!) - Commit message

**GitActor Fields** (Expected):
- `name` (String) - Author/committer name
- `email` (String) - Author/committer email ⚠️ **CRITICAL FIELD**
- `user` (User) - Associated GitHub user account

**Testing Required**: Verify that `author.email` is accessible in commit history queries. This is CRITICAL for counting unique contributors.

**Fallback**: If email not available, use `author.name` or `author.user.login` as contributor identifier.

---

## Query Complexity & Rate Limits

### Rate Limit Structure

GitHub GraphQL uses a **points system** instead of request counts:
- **Limit**: 5,000 points per hour
- **Calculation**: Each query costs points based on complexity
- **Node limits**: First/last arguments affect cost

### Estimated Query Cost

For our single repository query:

```
Base query: 1 point
+ Repository fields: ~5 points
+ File tree (HEAD:): ~10 points (depends on tree size)
+ 4 file content queries: ~4 points
+ Commit history (100 commits): ~20 points
+ Environments (1): ~1 point
+ Releases (5): ~2 points
+ Branch protection (1): ~1 point
+ Pull requests (10): ~5 points
+ Vulnerability alerts (1): ~1 point
= ~50 points per repository (estimated)
```

### Rate Limit Validation

**For 2,451 repositories**:
- Total cost: 2,451 × 50 = **122,550 points**
- Hours needed: 122,550 ÷ 5,000 = **24.5 hours** ⚠️

**PROBLEM**: This exceeds our target of <15 minutes!

### Optimization Strategies

1. **Reduce commit history**: Fetch 50 commits instead of 100 (save ~10 points/repo)
2. **Skip file content for large trees**: Only fetch CODEOWNERS/README if file tree shows they exist
3. **Batch queries**: Query multiple repositories in single GraphQL call using aliases
4. **Pagination**: Stream results instead of fetching all at once

**Revised estimate with optimizations**:
- Reduced query: ~30 points per repo
- Total: 2,451 × 30 = 73,530 points
- Time: 73,530 ÷ 5,000 = **14.7 hours** ⚠️ Still too slow!

**CRITICAL FINDING**: Single-repository queries may not achieve <15 minute target. Need **batch queries** or **parallel organization-level fetch**.

---

## GraphQL Batching Approach

### Option 1: Repository Aliases (Batch Query)

Query multiple repositories in single GraphQL call:

```graphql
query BatchRepositories($org: String!) {
  repo1: repository(owner: $org, name: "repo1") { ...repoFields }
  repo2: repository(owner: $org, name: "repo2") { ...repoFields }
  repo3: repository(owner: $org, name: "repo3") { ...repoFields }
  # ... up to ~50 repos per query
}
```

**Benefit**: 2,451 repos ÷ 50 = ~49 queries (much faster)
**Cost**: Same total points, but better throughput
**Limitation**: Must know repository names upfront

### Option 2: Organization Query with Pagination

```graphql
query OrgRepositories($org: String!, $cursor: String) {
  organization(login: $org) {
    repositories(first: 100, after: $cursor) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        # All repository fields in nested query
        name
        defaultBranchRef { ... }
        object(expression: "HEAD:") { ... }
        # etc.
      }
    }
  }
}
```

**Benefit**: Single query pattern, automatic pagination
**Cost**: Each page costs ~5,000 points (100 repos × 50 points)
**Time**: 2,451 repos ÷ 100 = 25 pages × 5,000 points = 125,000 points = **25 hours** ⚠️

**REVISED STRATEGY NEEDED**: Current approach won't meet <15 minute target!

---

## Limitations & Fallback Scenarios

### 1. Permission-Based Limitations

**Fields that may return null** due to permissions:
- `vulnerabilityAlerts` - Requires admin/security permissions
- `environments` - May be hidden for private repos
- `branchProtectionRules` - Requires push access

**Fallback**: Default to `False` for binary signals when null

### 2. Large Repository Issues

**Problem**: Repositories with 10,000+ files
- `object(expression: "HEAD:")` may timeout or exceed response size
- Tree traversal becomes expensive

**Fallback**:
- Fetch only top-level directory entries
- Use targeted file checks instead of full tree
- Fall back to REST API for specific file existence checks

### 3. Empty Repositories

**Problem**: New repos without commits
- `defaultBranchRef` may be null
- No commit history available

**Fallback**: Skip activity metrics, classify as Tier 4

### 4. Archived Repositories

**Problem**: Archived repos may have restricted access
- Some API fields disabled
- No write operations possible

**Handling**: Set `lifecycle = RETIREMENT`, skip most signals

### 5. Email Privacy

**CRITICAL LIMITATION**: GitHub allows users to hide email addresses
- `commit.author.email` may be `null` or `noreply@github.com`
- Cannot accurately count unique contributors

**Fallback Options**:
1. Use `commit.author.name` (less accurate, same name != same person)
2. Use `commit.author.user.login` (only works if author has GitHub account)
3. Combine: Use email if available, fallback to login, then name

---

## Recommended Query Structure

Based on verification, here's the validated query template:

```graphql
query GetRepositoryData($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    # Basic metadata
    name
    nameWithOwner
    description
    url
    databaseId
    isArchived
    primaryLanguage { name }
    diskUsage

    # Last commit + history
    defaultBranchRef {
      name
      target {
        ... on Commit {
          committedDate
          history(first: 50) {  # Reduced from 100
            totalCount
            nodes {
              committedDate
              author {
                name
                email
                user { login }
              }
            }
          }
        }
      }
    }

    # File tree (lightweight)
    tree: object(expression: "HEAD:") {
      ... on Tree {
        entries {
          name
          path
          type
        }
      }
    }

    # Specific files (only if tree shows they exist)
    codeowners1: object(expression: "HEAD:CODEOWNERS") {
      ... on Blob { text }
    }
    codeowners2: object(expression: "HEAD:.github/CODEOWNERS") {
      ... on Blob { text }
    }
    codeowners3: object(expression: "HEAD:docs/CODEOWNERS") {
      ... on Blob { text }
    }
    readme: object(expression: "HEAD:README.md") {
      ... on Blob { text }
    }

    # GitHub settings
    environments(first: 1) { totalCount }
    releases(first: 3, orderBy: {field: CREATED_AT, direction: DESC}) {
      totalCount
      nodes {
        createdAt
        tagName
      }
    }
    branchProtectionRules(first: 1) { totalCount }
    pullRequests(first: 10, states: [OPEN, MERGED], orderBy: {field: UPDATED_AT, direction: DESC}) {
      totalCount
      nodes {
        state
        updatedAt
        author { login }
      }
    }
    vulnerabilityAlerts(first: 1) { totalCount }
  }

  # Rate limit monitoring
  rateLimit {
    cost
    remaining
    resetAt
  }
}
```

**Estimated cost**: ~30-40 points per query
**For 2,451 repos**: ~98,000 points = **19.6 hours** ⚠️

---

## ❌ CRITICAL FINDING: Performance Target Not Achievable

**Target**: <15 minutes for 2,451 repositories
**Reality**: 15-25 hours even with optimizations

**Root cause**: GraphQL complexity scoring makes queries expensive. Even optimized query costs ~40 points, requiring 98,000 total points across 2,451 repos.

### Revised Options

**Option A: Accept Longer Sync Time**
- 15-20 hours sync is still 4-6x faster than REST (6-9 hours → need recalculation)
- Run sync overnight instead of during business hours
- **Pros**: Still massive improvement, simpler implementation
- **Cons**: Doesn't meet original <15 min target

**Option B: Implement Incremental Sync Properly**
- Only sync repos that changed since last sync (check `updatedAt` first)
- Typical daily changes: ~10-50 repos (not all 2,451)
- **Pros**: Meets daily sync time target
- **Cons**: Initial sync still takes 15-20 hours

**Option C: Parallel Organization Query**
- Use `organization.repositories` with nested data
- Fetch 100 repos per query, paginate through 25 pages
- May be more efficient than individual queries
- **Needs testing**: Complexity scoring for nested organization queries

**RECOMMENDATION**: Implement Option B (proper incremental sync) + Option C (org-level query for initial load)

---

## Next Steps

1. ✅ Schema validation complete - all required fields exist
2. ⚠️ Rate limit analysis reveals performance concern
3. ⏭️ Need to validate incremental sync effectiveness
4. ⏭️ Need to test organization-level batch query cost
5. ⏭️ Revise success criteria: <15 min for incremental, <20 hrs for full sync
