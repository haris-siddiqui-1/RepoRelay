---
name: h-implement-consumption-signals
branch: feature/consumption-signals
status: completed
created: 2025-11-25
depends_on:
  - h-implement-priority-scoring
submodules:
  - RepoRelay
---

# Implement Consumption Signals (Phase 4)

## Problem/Goal

Add consumption signal collection to solve the "abandoned vs stable" problem. Repositories that are consumed by many others should have higher priority regardless of commit activity.

**Reference**: `sessions/docs/vulnerability-prioritization-strategy.md` - Part 4.2, Part 5

## Success Criteria
- [x] Add consumption signal fields to Repository model
- [x] Implement dependency graph parser for common package formats (Used GitHub SBOM API instead of custom parsers - more robust)
- [x] Create internal dependency graph linking repos to their consumers
- [x] Implement consumption-based tier override logic
- [x] Create management command `build_dependency_graph`
- [x] Add consumption insights to dashboard (6 new insights)
- [x] Integrate consumption tier override into priority scoring
- [x] Unit tests for dependency parsing and tier override (25 tests)

## Context Manifest

### How Consumption Signals Fit Into the Architecture: The Complete Story

DefectDojo's vulnerability prioritization system works in three interconnected layers: (1) Repository enrichment and tier classification, (2) Priority scoring for findings, and (3) Triage workflow management. Phase 4 (Consumption Signals) addresses a critical gap in layer 1: the inability to distinguish between "abandoned" repositories (no activity because nobody uses them) and "stable" repositories (no activity because they're mature and consumed by many downstream systems).

**The Current Tier Classification Flow:**

When a repository is synced from GitHub via `dojo/github_collector/collector.py`, the system goes through these steps:

1. **Signal Detection** (`dojo/github_collector/signal_detector.py`): Analyzes repository files and metadata to detect 36 binary signals across 5 categories (deployment indicators, production readiness, active development, code organization, security maturity). For example, it checks for `Dockerfile`, `kubernetes/*.yaml`, `README.md`, `.github/workflows/*`, etc. Returns a dictionary like `{'has_dockerfile': True, 'has_ci_cd': True, 'recent_commits_30d': False, ...}`.

2. **Tier Classification** (`dojo/github_collector/tier_classifier.py`): Takes the binary signals dictionary plus `days_since_last_commit` and applies rule-based logic to classify the repository into tier1 (critical production), tier2 (high priority), tier3 (medium priority), tier4 (low priority), or archived. The classifier uses signal combinations like:
   - Tier 1: `has_containers AND has_environments AND has_monitoring AND is_active`
   - Tier 2: `has_ci_cd AND has_releases AND has_branch_protection AND multiple_contributors`
   - Tier 3: `has_tests AND is_active AND has_docs`
   - Archived: `days_since_last_commit > 180`

3. **Repository Model Update** (`dojo/models.py` lines 1623-1907): The computed tier is stored in `Repository.tier` field, along with all 36 binary signal flags and enrichment metadata (README summary, primary language, CODEOWNERS content, webhook health, activity metrics).

4. **Priority Scoring Integration** (`dojo/finding/priority_scorer.py`): When findings are scored, the `PriorityScorer` class retrieves the repository tier via `get_repository_for_finding()` function and uses it as a multiplier in the formula: `PriorityScore = (TierWeight × SeverityScore) + Modifiers`. Tier weights range from 5.0 (tier1) to 0.2 (archived).

**The Problem This Phase Solves:**

The current system has a fatal flaw: A stable, mature library with 50+ downstream consumers but no recent commits gets classified as "archived" because `days_since_last_commit > 180`. This results in vulnerabilities in critical shared infrastructure being deprioritized (tier weight 0.2 instead of 5.0), creating a 25x difference in priority score.

**Example Scenario:**
- Repository: `myorg/auth-library` (authentication SDK)
- Current signals: `has_ci_cd=True, has_tests=True, has_releases=True, recent_commits_30d=False`
- Days since last commit: 240 (8 months - it's stable, not abandoned!)
- Current classification: **Archived** (tier weight 0.2)
- Actual reality: Consumed by 75 internal services
- Desired classification: **Tier 1** (tier weight 5.0)

**How Consumption Signals Fix This:**

Phase 4 adds a new data source to the tier classification pipeline: internal dependency graph analysis. The flow becomes:

1. **Dependency Graph Construction** (NEW - `dojo/github_collector/dependency_parser.py`): Parse package manifest files from all repositories to extract declared dependencies:
   - `package.json` → `dependencies`, `devDependencies` fields
   - `requirements.txt` → list of Python packages
   - `go.mod` → `require` directives
   - `pom.xml` → `<dependencies>` XML tags
   - `Gemfile` → `gem` declarations
   - `Cargo.toml` → `[dependencies]` section

2. **Internal Cross-Reference** (NEW - management command `build_dependency_graph`): For each extracted dependency name, check if it matches any internal repository name. Build a directed graph of repository → dependency relationships. Compute `dependent_repo_count` by counting how many repositories depend on each one.

3. **Consumption-Based Tier Override** (MODIFIED - `dojo/github_collector/tier_classifier.py`): Before returning the tier classification result, check if `Repository.dependent_repo_count` triggers an override:
   - `>= 50 dependents`: Force tier1 (critical shared infrastructure)
   - `>= 20 dependents`: Force tier2 (important shared library)
   - `>= 5 dependents`: Promote one tier (tier4→tier3, tier3→tier2, archived→tier3)
   - Store the override in `Repository.consumption_tier_override` field

4. **Effective Tier Resolution** (MODIFIED - `dojo/finding/priority_scorer.py`): When scoring findings, check `repository.consumption_tier_override` first, fall back to `repository.tier` if no override exists.

**Data Flow with Consumption Signals:**

```
GitHub API Sync (sync_github_repositories)
    ↓
Repository Model created/updated with binary signals
    ↓
build_dependency_graph command executed (nightly cron)
    ↓
    ├─→ Parse package.json, requirements.txt, go.mod, etc. from repo contents
    ├─→ Extract dependency names (e.g., "@myorg/auth-library")
    ├─→ Cross-reference with internal repo names
    ├─→ Update dependent_repo_count, downstream_consumers, is_shared_library
    ├─→ Compute consumption_tier_override based on threshold rules
    ↓
Finding priority scoring (calculate_priority_scores)
    ↓
    ├─→ Get repository via get_repository_for_finding()
    ├─→ Check consumption_tier_override first
    ├─→ Fall back to base tier if no override
    ├─→ Apply tier weight multiplier
    ↓
Priority bucket assignment (P0-P4) based on final score
```

**Why This Architecture is Correct:**

1. **Separation of Concerns**: Dependency parsing is a distinct concern from signal detection. Signal detection analyzes file presence, dependency parsing analyzes file contents.

2. **Incremental Computation**: Dependency graph can be rebuilt nightly without re-syncing all GitHub metadata. Only parse changed repositories (similar to incremental sync pattern).

3. **Non-Destructive Override**: The base tier classification remains stored in `Repository.tier`. The consumption-based override goes into `Repository.consumption_tier_override`. This allows debugging and auditing of tier decisions.

4. **Backward Compatible**: If dependency graph hasn't been built yet, `dependent_repo_count` defaults to 0 and no override happens. Priority scoring falls back to base tier classification.

5. **Extensible**: New package formats can be added by implementing additional parsers in `dependency_parser.py` without touching tier classification logic.

**Performance Characteristics:**

- **Dependency Parsing**: O(n) where n = number of repositories. Each repo requires 1-7 file reads (checking for each package format). Can be parallelized with Celery tasks.
- **Graph Construction**: O(n × m) where m = average dependencies per repo (~50). Using PostgreSQL JSONField for `downstream_consumers` allows efficient queries.
- **Storage Overhead**: ~1KB per repository for `downstream_consumers` JSON array (50 consumer names × ~20 bytes each).
- **Sync Frequency**: Daily is sufficient. Dependencies change infrequently compared to code changes.

### For New Feature Implementation: Integration Points and Requirements

**Where Code Changes Are Needed:**

1. **Repository Model** (`dojo/models.py` lines 1623-1907): Add 6 new fields after line 1879 (after existing `tier` field, before `created` timestamp):
   ```python
   # Consumption Signals (Phase 4)
   dependent_repo_count = models.IntegerField(
       default=0,
       validators=[MinValueValidator(0)],
       verbose_name=_("Dependent Repositories"),
       help_text=_("Number of internal repositories that depend on this one")
   )
   downstream_consumers = models.JSONField(
       default=list,
       blank=True,
       verbose_name=_("Downstream Consumers"),
       help_text=_("List of repo names that declare this as a dependency")
   )
   is_shared_library = models.BooleanField(
       default=False,
       verbose_name=_("Is Shared Library"),
       help_text=_("True if consumed by 5+ repositories")
   )
   consumption_tier_override = models.CharField(
       max_length=10,
       choices=TIER_CHOICES,
       null=True,
       blank=True,
       verbose_name=_("Consumption Tier Override"),
       help_text=_("Tier override based on consumption (high consumption = higher tier)")
   )
   clone_count_14d = models.IntegerField(
       default=0,
       validators=[MinValueValidator(0)],
       verbose_name=_("Clone Count (14d)"),
       help_text=_("Repository clones in last 14 days (requires push access)")
   )
   view_count_14d = models.IntegerField(
       default=0,
       validators=[MinValueValidator(0)],
       verbose_name=_("View Count (14d)"),
       help_text=_("Repository page views in last 14 days (requires push access)")
   )
   ```

2. **Database Migration**: Generate migration with `docker compose exec uwsgi bash -c "python manage.py makemigrations"`. This will create a new migration file in `dojo/db_migrations/` that adds the 6 fields with `default=0` or `default=list` (non-breaking change).

3. **Dependency Parser** (NEW file - `dojo/github_collector/dependency_parser.py`): Create new module with class `DependencyParser` that implements:
   - `parse_package_json(content: str) -> List[str]`: Extract dependencies from npm package.json
   - `parse_requirements_txt(content: str) -> List[str]`: Extract Python package names
   - `parse_go_mod(content: str) -> List[str]`: Extract Go module paths
   - `parse_pom_xml(content: str) -> List[str]`: Extract Maven dependencies
   - `parse_gemfile(content: str) -> List[str]`: Extract Ruby gems
   - `parse_cargo_toml(content: str) -> List[str]`: Extract Rust crates
   - `normalize_package_name(raw_name: str) -> str`: Normalize package names (strip version, scope, etc.)

4. **Dependency Graph Builder** (NEW file - `dojo/github_collector/dependency_graph.py`): Create service class `DependencyGraphBuilder` with methods:
   - `build_graph(repositories: QuerySet[Repository]) -> None`: Main orchestration method
   - `parse_repository_dependencies(repo: Repository) -> List[str]`: Get GitHub file contents and parse dependencies
   - `match_internal_dependencies(dependency_names: List[str]) -> List[Repository]`: Cross-reference with internal repos
   - `update_consumption_metrics(repo: Repository, consumer_repos: List[Repository]) -> None`: Update dependent_repo_count, downstream_consumers
   - `compute_tier_override(repo: Repository) -> Optional[str]`: Apply threshold rules

5. **Management Command** (NEW file - `dojo/management/commands/build_dependency_graph.py`): Follow pattern from `calculate_priority_scores.py` (lines 1-273). Key arguments:
   - `--full`: Build graph for all repositories (default: only changed repos)
   - `--repository-id`: Build graph for specific repository
   - `--dry-run`: Preview what would be updated
   - `--async`: Queue Celery tasks instead of blocking

6. **Tier Override Integration** (`dojo/finding/priority_scorer.py` lines 140-174): Modify `_get_effective_tier_weight()` method to check `consumption_tier_override` first:
   ```python
   def _get_effective_tier_weight(self, finding: "Finding", repository: Optional["Repository"]) -> float:
       # Priority 1: Use consumption tier override if present
       if repository and repository.consumption_tier_override:
           weight = self.TIER_WEIGHTS.get(repository.consumption_tier_override, 1.0)
           logger.debug("Using consumption tier override '%s' -> weight %.1f",
                       repository.consumption_tier_override, weight)
           return weight

       # Priority 2: Use repository tier if provided
       if repository and repository.tier:
           weight = self.TIER_WEIGHTS.get(repository.tier, 1.0)
           logger.debug("Using repository tier '%s' -> weight %.1f", repository.tier, weight)
           return weight

       # Priority 3: Fall back to product business_criticality
       # ... existing logic ...
   ```

7. **Consumption Insights** (NEW file - `dojo/github_collector/insights/consumption.py`): Add new insights following pattern from `technology.py` (lines 1-150):
   - `MostConsumedRepositories`: Table showing top 20 repos by dependent_repo_count
   - `SharedLibraryDistribution`: Pie chart of consumption tiers (50+, 20-49, 5-19, <5)
   - `OrphanedLibraries`: Table showing repos with 0 dependents but marked as library (via tags or README)
   - `ConsumptionVsActivity`: Scatter plot (x=dependent_repo_count, y=days_since_last_commit) to visualize stable vs abandoned

8. **Admin Interface Updates**: Register new fields in `dojo/admin.py` for Repository model admin view (add to `list_display` and `search_fields`).

**External Dependencies and GitHub API:**

- **GitHub Contents API** (REST): `GET /repos/{owner}/{repo}/contents/{path}` - Used to fetch package manifest files. Rate limit: 5000 requests/hour (authenticated).
- **GitHub Traffic API** (REST): `GET /repos/{owner}/{repo}/traffic/clones` and `/traffic/views` - OPTIONAL, requires push access. Most organizations won't have this, so make it gracefully optional.
- **No GraphQL Changes Needed**: Dependency parsing uses file contents, not metadata. File contents aren't available via GraphQL, so we continue using REST API with PyGithub client.

**Integration with Existing GitHub Collector:**

The `GitHubRepositoryCollector` class (`dojo/github_collector/collector.py` line 1-1500) already handles:
- GitHub authentication (lines 50-80)
- Rate limit handling (lines 100-150)
- REST client initialization (lines 200-250)
- Repository syncing orchestration (lines 400-600)

We'll add a new optional step to the sync flow:
```python
def sync_repository(self, repo_data, product=None):
    # ... existing signal detection, tier classification ...

    # NEW: Parse dependencies if requested
    if parse_dependencies:
        dependency_parser = DependencyParser(self.github_client)
        dependencies = dependency_parser.parse_repository_dependencies(repository)
        # Note: Don't update consumption metrics here - that requires graph analysis
        # Just log that dependencies were extracted
        logger.info(f"Extracted {len(dependencies)} dependencies from {repository.name}")
```

But the actual graph building happens in a separate command (`build_dependency_graph`) because it requires cross-referencing ALL repositories, not just one.

**Testing Strategy:**

1. **Unit Tests** (`unittests/github_collector/test_dependency_parser.py`):
   - Test each package format parser with sample files
   - Test package name normalization (strip versions, scopes)
   - Test parsing errors (malformed JSON, XML)

2. **Integration Tests** (`unittests/github_collector/test_dependency_graph.py`):
   - Create 5 test repositories with mock dependencies
   - Build dependency graph
   - Assert `dependent_repo_count` is correct for each repo
   - Assert `downstream_consumers` lists are accurate
   - Assert `consumption_tier_override` triggers at correct thresholds

3. **Priority Scoring Tests** (`unittests/finding/test_priority_scorer.py`):
   - Extend existing tests to include consumption tier override scenarios
   - Assert tier override takes precedence over base tier
   - Assert priority score changes correctly (0.2 → 5.0 multiplier = 25x difference)

**Migration Path:**

1. **Phase 4a - Data Model** (Week 1):
   - Add 6 fields to Repository model
   - Generate and apply migration
   - Deploy to staging, verify no errors

2. **Phase 4b - Dependency Parsing** (Week 2):
   - Implement DependencyParser class with 6 package format parsers
   - Unit test each parser with sample files
   - Create management command scaffold

3. **Phase 4c - Graph Construction** (Week 3):
   - Implement DependencyGraphBuilder class
   - Implement internal cross-referencing logic
   - Test on small dataset (10-20 repos)

4. **Phase 4d - Tier Override Integration** (Week 4):
   - Modify PriorityScorer to check consumption_tier_override
   - Run calculate_priority_scores with new logic
   - Validate priority bucket distribution changes

5. **Phase 4e - Insights Dashboard** (Week 5):
   - Create 4 consumption insights
   - Register with InsightRegistry
   - Test visualization rendering

6. **Phase 4f - Production Rollout** (Week 6):
   - Run build_dependency_graph on full dataset (may take 1-2 hours)
   - Recalculate all priority scores with --force flag
   - Monitor triage queue for changes in P0/P1 distribution

### Technical Reference Details

#### Model Field Definitions (Repository)

```python
# Add after line 1879 in dojo/models.py (after tier field)
dependent_repo_count = models.IntegerField(
    default=0,
    validators=[MinValueValidator(0)],
    verbose_name=_("Dependent Repositories"),
    help_text=_("Number of internal repositories that depend on this one")
)
downstream_consumers = models.JSONField(
    default=list,
    blank=True,
    verbose_name=_("Downstream Consumers"),
    help_text=_("List of repo names that declare this as a dependency")
)
is_shared_library = models.BooleanField(
    default=False,
    verbose_name=_("Is Shared Library"),
    help_text=_("True if consumed by 5+ repositories")
)
consumption_tier_override = models.CharField(
    max_length=10,
    choices=TIER_CHOICES,
    null=True,
    blank=True,
    verbose_name=_("Consumption Tier Override"),
    help_text=_("Tier override based on consumption (high consumption = higher tier)")
)
clone_count_14d = models.IntegerField(
    default=0,
    validators=[MinValueValidator(0)],
    verbose_name=_("Clone Count (14d)"),
    help_text=_("Repository clones in last 14 days (requires push access)")
)
view_count_14d = models.IntegerField(
    default=0,
    validators=[MinValueValidator(0)],
    verbose_name=_("View Count (14d)"),
    help_text=_("Repository page views in last 14 days (requires push access)")
)
```

#### Dependency Parser Interface

```python
# New file: dojo/github_collector/dependency_parser.py
class DependencyParser:
    """Parse package manifest files to extract dependency declarations."""

    PACKAGE_FILES = {
        'package.json': 'parse_package_json',
        'requirements.txt': 'parse_requirements_txt',
        'go.mod': 'parse_go_mod',
        'pom.xml': 'parse_pom_xml',
        'Gemfile': 'parse_gemfile',
        'Cargo.toml': 'parse_cargo_toml',
    }

    def __init__(self, github_client):
        self.github = github_client

    def parse_repository_dependencies(self, repo: Repository) -> List[str]:
        """Extract all dependencies from a repository."""
        all_dependencies = []
        for filename, parser_method in self.PACKAGE_FILES.items():
            content = self._fetch_file_content(repo, filename)
            if content:
                parser_func = getattr(self, parser_method)
                dependencies = parser_func(content)
                all_dependencies.extend(dependencies)
        return list(set(all_dependencies))  # Deduplicate

    def _fetch_file_content(self, repo: Repository, filename: str) -> Optional[str]:
        """Fetch file content from GitHub API."""
        try:
            github_repo = self.github.get_repo(repo.github_repo_id)
            file_content = github_repo.get_contents(filename)
            return file_content.decoded_content.decode('utf-8')
        except Exception as e:
            logger.debug(f"File {filename} not found in {repo.name}: {e}")
            return None

    def parse_package_json(self, content: str) -> List[str]:
        """Extract dependencies from npm package.json."""
        data = json.loads(content)
        deps = []
        deps.extend(data.get('dependencies', {}).keys())
        deps.extend(data.get('devDependencies', {}).keys())
        return [self.normalize_package_name(d) for d in deps]

    def normalize_package_name(self, raw_name: str) -> str:
        """Normalize package name (strip version, scope, URL)."""
        # Strip npm scope: @myorg/package -> package
        if raw_name.startswith('@'):
            raw_name = raw_name.split('/')[-1]
        # Strip version specifiers: package>=1.0.0 -> package
        raw_name = re.split(r'[><=!~]', raw_name)[0].strip()
        return raw_name.lower()
```

#### Tier Override Logic

```python
# dojo/github_collector/dependency_graph.py
def compute_tier_override(repo: Repository) -> Optional[str]:
    """
    Compute consumption-based tier override.

    Rules:
    - >= 50 dependents: tier1 (critical shared infrastructure)
    - >= 20 dependents: tier2 (important shared library)
    - >= 5 dependents: promote one tier
    - < 5 dependents: no override
    """
    count = repo.dependent_repo_count
    base_tier = repo.tier

    if count >= 50:
        return Repository.TIER1
    elif count >= 20:
        return Repository.TIER2
    elif count >= 5:
        # Promote one tier
        promotion_map = {
            Repository.TIER4: Repository.TIER3,
            Repository.TIER3: Repository.TIER2,
            Repository.TIER2: Repository.TIER1,
            Repository.ARCHIVED: Repository.TIER3,
        }
        return promotion_map.get(base_tier, base_tier)

    return None  # No override
```

#### Management Command Pattern

```python
# New file: dojo/management/commands/build_dependency_graph.py
class Command(BaseCommand):
    help = 'Build internal dependency graph and update consumption metrics'

    def add_arguments(self, parser):
        parser.add_argument('--full', action='store_true',
                          help='Build graph for all repos (default: only changed)')
        parser.add_argument('--repository-id', type=int,
                          help='Build graph for specific repository')
        parser.add_argument('--dry-run', action='store_true',
                          help='Preview changes without saving')
        parser.add_argument('--async', action='store_true', dest='async_mode',
                          help='Queue Celery tasks for async processing')

    def handle(self, *args, **options):
        # Build queryset
        repositories = Repository.objects.all()
        if options['repository_id']:
            repositories = repositories.filter(id=options['repository_id'])

        # Initialize builder
        builder = DependencyGraphBuilder(github_token=settings.DD_GITHUB_TOKEN)

        # Build graph
        if options['async_mode']:
            self._process_async(repositories)
        else:
            self._process_sync(repositories, dry_run=options['dry_run'])
```

#### Consumption Insights Examples

```python
# New file: dojo/github_collector/insights/consumption.py
class MostConsumedRepositories(BaseInsight):
    insight_id = 'most_consumed_repos'
    name = 'Most Consumed Repositories'
    description = 'Repositories with highest dependent count'
    category = 'consumption'
    visualization_type = 'table'

    def calculate(self, filters=None):
        repos = Repository.objects.filter(
            dependent_repo_count__gt=0
        ).order_by('-dependent_repo_count')[:20].values(
            'name', 'dependent_repo_count', 'tier',
            'consumption_tier_override', 'is_shared_library'
        )

        data = [
            {
                'repository': r['name'],
                'dependents': r['dependent_repo_count'],
                'base_tier': r['tier'],
                'effective_tier': r['consumption_tier_override'] or r['tier'],
                'is_library': 'Yes' if r['is_shared_library'] else 'No'
            }
            for r in repos
        ]

        return {
            'title': 'Most Consumed Repositories (Top 20)',
            'data': data,
            'metadata': {'count': len(data), 'timestamp': timezone.now()}
        }
```

#### File Locations

- **Model changes**: `/Users/1haris.sid/defectdojo/RepoRelay/dojo/models.py` line 1879 (after `tier` field)
- **Migration**: Generate with `makemigrations`, will create file like `dojo/db_migrations/0264_repository_consumption_signals.py`
- **Dependency parser**: `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/dependency_parser.py` (new file)
- **Graph builder**: `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/dependency_graph.py` (new file)
- **Management command**: `/Users/1haris.sid/defectdojo/RepoRelay/dojo/management/commands/build_dependency_graph.py` (new file)
- **Priority scorer modification**: `/Users/1haris.sid/defectdojo/RepoRelay/dojo/finding/priority_scorer.py` lines 140-174 (modify `_get_effective_tier_weight`)
- **Consumption insights**: `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/insights/consumption.py` (new file)
- **Unit tests**: `/Users/1haris.sid/defectdojo/RepoRelay/unittests/github_collector/test_dependency_parser.py` (new)
- **Integration tests**: `/Users/1haris.sid/defectdojo/RepoRelay/unittests/github_collector/test_dependency_graph.py` (new)

## Technical Specification

### Data Model Changes (Repository)
```python
dependent_repo_count = models.IntegerField(default=0)
downstream_consumers = models.JSONField(default=list, blank=True)
is_shared_library = models.BooleanField(default=False)
consumption_tier_override = models.CharField(max_length=10, choices=TIER_CHOICES, null=True, blank=True)
clone_count_14d = models.IntegerField(default=0)
view_count_14d = models.IntegerField(default=0)
```

### Dependency Graph Parser
Parse dependencies from:
- `package.json` (npm)
- `requirements.txt`, `setup.py`, `pyproject.toml` (Python)
- `go.mod` (Go)
- `pom.xml`, `build.gradle` (Java)
- `Gemfile` (Ruby)
- `Cargo.toml` (Rust)

### Tier Override Logic
```python
def compute_effective_tier(repo):
    if repo.dependent_repo_count >= 50:
        return 'tier1'  # Critical shared infrastructure
    elif repo.dependent_repo_count >= 20:
        return 'tier2'  # Important shared library
    elif repo.dependent_repo_count >= 5:
        # Promote one tier
        promotion_map = {'tier4': 'tier3', 'tier3': 'tier2', 'archived': 'tier3'}
        return promotion_map.get(repo.tier, repo.tier)
    return repo.tier
```

### GitHub API (Optional)
- Traffic: `/repos/{owner}/{repo}/traffic/clones` (requires push access)
- Traffic: `/repos/{owner}/{repo}/traffic/views` (requires push access)

## User Notes

This task can run in parallel with Phase 2 (triage workflow) since it only depends on Phase 1. The consumption signals address the critical gap of not being able to distinguish "abandoned" from "stable" repositories.

## Work Log

### 2025-11-25

#### Phase 4 Completion Summary

**Implementation Completed:**
- Added 6 consumption signal fields to Repository model (migration 0263)
- Created DependencyGraphBuilder using GitHub SBOM API
- Created build_dependency_graph management command
- Integrated consumption tier override into PriorityScorer
- Created 6 consumption insights for dashboard
- Wrote 25 comprehensive unit tests
- Fixed rate limit handling based on code review

**Key Implementation Decisions:**
- Used GitHub SBOM API instead of custom package file parsers for improved robustness and maintainability
- Tier override thresholds: 50+ dependents → tier1, 20+ → tier2, 5+ → promote one tier
- consumption_tier_override takes precedence over base tier in priority scoring formula
- Graceful fallback when SBOM data unavailable (uses GitHub API v4 dependency graph)

**Technical Achievements:**
- Full test coverage (25 unit tests) including edge cases
- Rate limit handling with exponential backoff and retry logic
- Async processing support via Celery tasks
- Dry-run mode for preview before applying changes
- Repository-specific and product-specific filtering support

**Files Created/Modified:**
- dojo/models.py (migration 0263 - 6 new fields)
- dojo/github_collector/dependency_graph.py (DependencyGraphBuilder)
- dojo/management/commands/build_dependency_graph.py
- dojo/finding/priority_scorer.py (consumption tier integration)
- dojo/github_collector/insights/consumption.py (6 new insights)
- unittests/github_collector/test_dependency_graph.py (25 tests)

**Validation:**
- All 25 unit tests passing
- Integration testing with live GitHub API
- Verified tier override logic with real repository data
- Confirmed priority score recalculation works correctly
