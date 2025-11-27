# Dependency Graph Analysis

Analyzes GitHub SBOM (Software Bill of Materials) data to identify internal dependency relationships and solve the "abandoned vs stable repository" problem.

## Problem Statement

Traditional tier classification can misclassify stable, mature libraries with infrequent commits as "archived" when they have many internal consumers.

**Example:** `myorg/auth-library` with 240 days since last commit gets tier weight 0.2 (archived) instead of 5.0 (tier1), creating a 25x deprioritization for critical infrastructure vulnerabilities.

## Solution

The DependencyGraphBuilder tracks which internal repositories consume other internal repositories via SBOM analysis.

**Location:** `dojo/github_collector/dependency_graph.py`

## Repository Model Fields

| Field | Type | Description |
|-------|------|-------------|
| `dependent_repo_count` | Integer | Internal repos that depend on this one |
| `downstream_consumers` | JSONField | Array of consumer repository names |
| `is_shared_library` | Boolean | True if 5+ consumers |
| `consumption_tier_override` | CharField | Computed tier override |

## Tier Override Thresholds

| Dependents | Override | Description |
|------------|----------|-------------|
| 50+ | tier1 | Critical shared infrastructure |
| 20-49 | tier2 | Widely used shared library |
| 5-19 | Promote one tier | tier4→tier3, tier3→tier2, etc. |
| <5 | No override | Use base tier |

## Management Command

```bash
# Full graph rebuild
python manage.py build_dependency_graph

# Specific organization
python manage.py build_dependency_graph --org myorg

# Specific repository
python manage.py build_dependency_graph --repository-id 123

# Dry run
python manage.py build_dependency_graph --dry-run

# Verbose logging
python manage.py build_dependency_graph --verbose
```

## Data Flow

1. Fetch SBOM via GitHub API: `GET /repos/{owner}/{repo}/dependency-graph/sbom`
2. Parse SBOM JSON to extract `packages[].name`
3. Normalize package names (strip versions, scopes, URLs)
4. Cross-reference with internal repository names
5. Build consumer map: `{consumed_repo: [consumers...]}`
6. Update Repository models in transaction-safe batches
7. Compute `consumption_tier_override` based on thresholds

## SBOM Format

```json
{
  "SPDXID": "SPDXRef-DOCUMENT",
  "packages": [
    {"name": "@myorg/auth-library", "versionInfo": "2.5.0"},
    {"name": "github.com/myorg/logging-sdk", "versionInfo": "v1.3.2"}
  ]
}
```

## Package Name Matching

| Ecosystem | Pattern | Example |
|-----------|---------|---------|
| npm | `@org/name` → `name` | `@myorg/auth-lib` → `auth-lib` |
| PyPI | `org-name` → `name` | `myorg-auth-lib` → `auth-lib` |
| Go | Exact match | `github.com/myorg/sdk` |
| Maven | `group:artifact` → `artifact` | `com.myorg:auth-lib` → `auth-lib` |

## Integration with Priority Scoring

When `calculate_priority_scores` runs, tier resolution order:
1. `Repository.consumption_tier_override` (from dependency graph)
2. `Repository.tier` (from signal classification)
3. `Product.business_criticality` (fallback)
4. Default: 1.0

## Performance

| Metric | Value |
|--------|-------|
| API calls | 1 SBOM per repo |
| Rate limit cost | ~10 points per fetch |
| Processing time | ~5-10 min for 2000 repos |
| Memory | <500MB |
| Recommended frequency | Daily |

## Error Handling

- SBOM unavailable (403/404): Skip, log warning
- Rate limit: Sleep and retry
- Invalid format: Skip, log error
- Network errors: 3 retries with backoff
- Update failure: Transaction rollback
