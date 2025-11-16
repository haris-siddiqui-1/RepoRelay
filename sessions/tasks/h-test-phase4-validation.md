---
name: h-test-phase4-validation
branch: feature/phase4-validation-tests
status: pending
created: 2025-01-16
---

# Phase 4: Comprehensive Validation & Verification Testing

## Problem/Goal

Phase 4 (Product Grouping & Migration) has been implemented with core backend functionality complete:
- Hierarchical clustering engine (700 lines)
- Migration wizard backend (450 lines)
- Database schema changes (3 new Product fields)
- Management command (230 lines)
- Unit tests (30+ test cases)

**Goal**: Conduct extensive validation and verification of all implemented features before considering Phase 4 production-ready. This includes:

1. **Code Review**: Deep review of clustering algorithm, migration logic, and edge cases
2. **UI Testing**: Use Playwright MCP to test real-world workflows including:
   - Repository-to-Product mapping scenarios
   - Multiple repositories grouped into single Product
   - Migration rollback functionality
   - Edge cases (orphaned repos, duplicate assignments, etc.)
3. **Integration Testing**: Verify end-to-end workflows work correctly
4. **Performance Testing**: Ensure clustering scales to 2,451+ repositories
5. **Data Integrity Verification**: Confirm Findings/Tests/Engagements remain intact post-migration

## Success Criteria

**Code Quality & Review:**
- [ ] Code review identifies and resolves all critical issues in clustering algorithm
- [ ] Migration logic handles all edge cases correctly (duplicates, orphans, rollbacks)
- [ ] Database transactions are safe and atomic

**Testing with Real GitHub Data:**
- [ ] Ingest actual GitHub repositories using existing GitHub collector
- [ ] Test clustering on real repository dataset (organization repos)
- [ ] Verify clustering groups related repos correctly (e.g., repos with common prefixes, same language/framework)
- [ ] Test migration on real ingested data, not synthetic test fixtures

**Workflow Testing:**
- [ ] Management command: Generate clustering suggestions from real repos
- [ ] Management command: Preview migration with --dry-run
- [ ] Management command: Apply migration with auto-approve threshold
- [ ] Management command: Rollback successfully restores original state
- [ ] Playwright UI tests (when UI implemented): Test with real data

**Real-World Scenarios (using actual ingested repos):**
- [ ] Identify repos that should be grouped (same prefix, language, ownership)
- [ ] Execute migration: Multiple real repos → single Product
- [ ] Verify all GitHub Alerts (Findings) remain accessible post-migration
- [ ] Test edge cases: orphaned repos, single-repo Products, large clusters

**Performance & Scale:**
- [ ] Clustering real repository dataset completes in reasonable time (<5 seconds per 100 repos)
- [ ] Migration executes without timeout or memory issues on real data
- [ ] Preview/validation performs quickly (<2 seconds)

**Data Integrity (Real Data):**
- [ ] Zero GitHub Alert Findings lost during migration
- [ ] All repository-product relationships correct post-migration
- [ ] Audit trail (is_repository_placeholder, migrated_to_product) accurate
- [ ] GitHub Alerts sync continues to work with new Product structure

**Unit Tests:**
- [ ] All 30+ existing unit tests pass
- [ ] Unit tests updated to use realistic test data patterns

## Context Manifest

### How Phase 4 Product Migration Works (Complete End-to-End Flow)

**Phase 4 Goal**: Migrate from "1 Product per Repository" (legacy auto-created placeholders) to "1 Product per Application" (logical grouping of related repositories using ML clustering).

#### The Complete Data Journey - From GitHub to Migration

**1. Initial State: Real GitHub Data Ingestion**

When you run `python manage.py sync_github_repositories --org myorg --incremental`, here's what happens:

The GitHub collector (`dojo/github_collector/collector.py`) uses **GraphQL API v4** to fetch repository metadata from GitHub. For each repository in your organization:

- **GraphQL query** fetches: name, URL, primary language, 50 recent commits, file tree (for signal detection), README content, CODEOWNERS, release history, branch protection rules, environment count, PR activity
- **Signal detection** runs on the file tree to detect 36 binary signals (has_dockerfile, has_kubernetes_config, has_ci_cd, etc.) - see `signal_detector.py`
- **Product auto-creation**: If Product doesn't exist for this repo, creates Product with `name=repo_name`, `is_repository_placeholder=True` (the legacy 1:1 mapping)
- **Repository model creation**: Creates Repository record with ForeignKey to Product, storing all enrichment data (tier, signals, activity metrics)

**Critical architectural point**: In the legacy system, every GitHub repository gets its own Product. So if you have 2,451 repositories, you have 2,451 Products, each marked `is_repository_placeholder=True`. This is what Phase 4 seeks to consolidate.

**2. GitHub Alerts Become DefectDojo Findings (Real Vulnerability Data)**

When you run `python manage.py sync_github_alerts`, real GitHub security alerts are fetched and converted to DefectDojo Findings:

**Alert Collection Flow** (`dojo/github_collector/alerts_collector.py`):
- For each Repository with `github_repo_id`, fetch 3 alert types:
  - **Dependabot alerts** (GraphQL): Dependency vulnerabilities with CVE numbers, package info, severity
  - **CodeQL alerts** (REST API): Code scanning findings with CWE numbers, file paths, line numbers
  - **Secret Scanning alerts** (REST API): Exposed secrets/credentials with file locations
- Alerts stored in `GitHubAlert` model with all metadata (alert_type, severity, state, github_alert_id, package_name, cve, file_path, etc.)
- Repository updated with counts: `dependabot_alert_count`, `codeql_alert_count`, `secret_scanning_alert_count`

**Finding Conversion Flow** (`dojo/github_collector/findings_converter.py`):
- For each GitHubAlert, create DefectDojo Finding:
  - **Engagement creation**: Auto-creates Engagement named "GitHub Security Alerts - {repo_name}" under the Repository's Product
  - **Test creation**: Auto-creates Test with Test_Type "GitHub Dependabot", "GitHub CodeQL", or "GitHub Secret Scanning"
  - **Finding creation**: Converts alert to Finding with:
    - `unique_id_from_tool = "github-{alert_type}-{repo_id}-{alert_number}"` (for deduplication)
    - `test` = auto-created Test (which links to Engagement → Product)
    - `severity` = mapped from GitHub severity (critical/high/moderate/low → Critical/High/Medium/Low)
    - `cve`, `cwe`, `component_name`, `file_path`, `line` = alert metadata
    - `active`, `is_mitigated`, `risk_accepted` = state based on GitHub alert state (open/fixed/dismissed)
  - **Bidirectional link**: `alert.finding` points to Finding, Finding has `unique_id_from_tool` matching alert

**Data hierarchy after alert sync**:
```
Product (1:1 placeholder for repo)
  └─ Engagement ("GitHub Security Alerts - repo_name")
      ├─ Test ("repo_name - GitHub Dependabot")
      │   └─ Finding (CVE-2023-XXXX vulnerability)
      ├─ Test ("repo_name - GitHub CodeQL")
      │   └─ Finding (SQL Injection at file:line)
      └─ Test ("repo_name - GitHub Secret Scanning")
          └─ Finding (AWS Secret Key exposed)
```

**Critical migration constraint**: When we consolidate 5 repositories into 1 Product, all these Findings MUST remain accessible. The Finding → Test → Engagement → Product chain cannot break.

**3. Repository Clustering Algorithm** (`dojo/github_collector/clustering.py`)

The clustering engine uses **hierarchical agglomerative clustering** (Ward linkage) with **silhouette scoring** to group related repositories.

**Feature Engineering** (the "how similar are these repos?" calculation):
- **TF-IDF name similarity** (20 features): Tokenizes repo names (splits on -, _, /, camelCase) and computes TF-IDF vectors. Repos named "auth-api", "auth-frontend", "auth-shared" get high similarity scores because "auth" token appears in all.
- **Language/Framework one-hot** (10 features): Binary encoding for common languages (Python, JavaScript, TypeScript, Go, Java) and frameworks (Django, React, Spring Boot, Express, Flask). Repos with same language cluster together.
- **Ownership confidence** (1 feature): Normalized `ownership_confidence` field (0-100 → 0.0-1.0)
- **36 Binary signals** (36 features): All deployment, production, development, security signals as 0.0/1.0 floats. Repos with same infrastructure patterns (both have Dockerfile + K8s + CI/CD) cluster together.
- **Activity patterns** (3 features): Normalized active_contributors_90d (capped at 50), inverse days_since_last_commit (0-365 days), tier value (tier1=1.0, tier2=0.75, tier3=0.5, tier4=0.25, archived=0.0)

**Total feature matrix**: 70+ features per repository. StandardScaler normalizes all features to mean=0, std=1.

**Clustering execution**:
1. Compute pairwise distances between all repositories using scaled feature matrix
2. Perform hierarchical clustering with Ward linkage (minimizes within-cluster variance)
3. Generate dendrogram for visualization (D3.js compatible format with icoord, dcoord, leaves)
4. Determine optimal cut height:
   - If `suggested_num_clusters` provided: Find cut height that produces exactly k clusters
   - Otherwise: Try multiple k values (sqrt(n) to n/10), compute **silhouette score** for each, pick k with best score (measures cluster cohesion/separation)
5. Use `fcluster()` to assign cluster labels at chosen cut height
6. For each cluster:
   - **Suggest product name**: Longest common prefix/suffix in repo names (e.g., "auth-*" → "Auth Services"). Falls back to most common word appearing in 2+ repos.
   - **Extract common features**: Most common language, framework, tier. Intersection of CODEOWNERS across repos.
   - **Calculate confidence score** (0-100):
     - Intra-cluster similarity: 30 points (how tight the cluster is)
     - Feature agreement: 0-30 points (% of repos sharing same language/framework)
     - Name pattern match: 0-20 points (common prefix/suffix detected)
     - Ownership overlap: 0-10 points (shared CODEOWNERS entries)

**Example clustering result**:
```
Cluster 1: "Auth Services" (confidence: 85%)
  Repositories: myorg/auth-api, myorg/auth-frontend, myorg/auth-shared
  Common features: Language=Python, Framework=Django, Tier=tier1, Owners=[@auth-team]

Cluster 2: "Payment Services" (confidence: 78%)
  Repositories: myorg/payment-service, myorg/payment-gateway, myorg/payment-processor
  Common features: Language=Java, Framework=Spring Boot, Tier=tier2

Cluster 3: "Admin Panel" (confidence: 65%)
  Repositories: myorg/admin-ui, myorg/admin-api
  Common features: Language=TypeScript, Framework=React, Tier=tier3
```

**4. Migration Wizard Preview & Validation** (`dojo/product/migration_wizard.py`)

Before applying migration, the wizard runs **exhaustive validation** to ensure data integrity:

**Validation checks** (`preview_migration()`):
- **Repository existence**: All repository IDs exist in database
- **No duplicate assignments**: Each repository appears in exactly one grouping
- **Unique product names**: No name collisions in new Products
- **Large cluster warning**: Clusters with >20 repos get warning (consider splitting)
- **Orphaned repositories**: Repos not in any grouping will retain current Product

**Impact analysis** (counts affected objects by traversing relationships):
```python
for repo in repositories:
    product = repo.product  # Old placeholder Product
    engagements = Engagement.objects.filter(product=product)  # GitHub alert engagements
    for engagement in engagements:
        tests = Test.objects.filter(engagement=engagement)  # Dependabot/CodeQL/Secret tests
        for test in tests:
            findings = Finding.objects.filter(test=test)  # Real CVEs/vulnerabilities
```

**Preview output**:
```
Migration Impact:
  New Products to create: 3
  Repositories to migrate: 8
  Findings affected: 142  ← CRITICAL: These must survive migration!
  Tests affected: 24
  Engagements affected: 8
```

**Why this matters**: If migration loses Findings, you lose real security vulnerability data. The validation ensures we know exactly what will be affected.

**5. Migration Execution (Atomic Transaction)** (`apply_migration()`)

The migration uses **Django's @transaction.atomic decorator** to ensure all-or-nothing execution. If ANY step fails, entire migration rolls back.

**Step-by-step migration flow**:

```python
@transaction.atomic
def apply_migration(groupings):
    for group in groupings:
        # Step 1: Create new logical Product
        new_product = Product.objects.create(
            name=group['product_name'],  # e.g., "Auth Services"
            description=f"Migrated product grouping (migration {migration_id})",
            prod_type_id=group['product_type_id'],
            is_repository_placeholder=False  # This is a REAL logical product
        )

        # Step 2: Update all repositories to point to new Product
        for repo_id in group['repository_ids']:
            repo = Repository.objects.get(id=repo_id)
            old_product = repo.product

            repo.product = new_product  # Update ForeignKey
            repo.save()

            # Step 3: Mark old Product as archived placeholder
            old_product.is_repository_placeholder = True  # Still true, now archived
            old_product.migrated_to_product = new_product  # Breadcrumb trail
            old_product.migration_date = timezone.now()
            old_product.save()
```

**Critical architectural decision**: The migration does NOT move Engagements/Tests/Findings. Here's why:

**Before migration**:
```
Product "myorg/auth-api" (placeholder, id=1)
  └─ Engagement "GitHub Security Alerts - myorg/auth-api"
      └─ Test "GitHub Dependabot"
          └─ Finding "CVE-2023-12345 in requests==2.28.0"

Repository "myorg/auth-api" (id=10)
  └─ product_id = 1
```

**After migration**:
```
Product "Auth Services" (logical, id=100)  ← NEW consolidated Product

Repository "myorg/auth-api" (id=10)
  └─ product_id = 100  ← Updated ForeignKey

Product "myorg/auth-api" (placeholder, id=1)  ← OLD Product remains
  ├─ is_repository_placeholder = True
  ├─ migrated_to_product_id = 100  ← Points to new Product
  └─ Engagement "GitHub Security Alerts - myorg/auth-api"
      └─ Test "GitHub Dependabot"
          └─ Finding "CVE-2023-12345 in requests==2.28.0"  ← Still accessible!
```

**Why keep old Products?** Two reasons:
1. **Data preservation**: Findings remain under original Engagement → Product. Moving them would break historical audit trail.
2. **Rollback capability**: By keeping old Products with `migrated_to_product` pointer, we can reverse the migration.

**But how do you ACCESS Findings after migration?** Through Repository queries:
```python
# Get all Findings for new consolidated Product "Auth Services"
new_product = Product.objects.get(name="Auth Services")
repositories = Repository.objects.filter(product=new_product)  # All repos in this Product

for repo in repositories:
    old_product = Product.objects.get(name=repo.name, is_repository_placeholder=True)
    findings = Finding.objects.filter(test__engagement__product=old_product)
    # Now you have all Findings from this repository
```

Alternatively, query via migrated_to_product reverse relation:
```python
new_product = Product.objects.get(name="Auth Services")
old_products = new_product.migrated_from_products.all()  # Reverse ForeignKey
all_findings = Finding.objects.filter(test__engagement__product__in=old_products)
```

**6. Rollback Mechanism** (`rollback_migration()`)

Rollback is possible within 90-day retention window (before old Products are deleted):

```python
@transaction.atomic
def rollback_migration(migration_id):
    # Find new Products created by this migration
    migrated_products = Product.objects.filter(
        description__contains=migration_id,
        is_repository_placeholder=False
    )

    # Find archived Products that were migrated
    archived_products = Product.objects.filter(
        is_repository_placeholder=True,
        migrated_to_product__in=migrated_products
    )

    for new_product in migrated_products:
        repositories = Repository.objects.filter(product=new_product)

        for repo in repositories:
            # Find original Product by name
            original_product = archived_products.get(
                name=repo.name,  # Original Product name = repo name
                migrated_to_product=new_product
            )

            # Restore repository to original Product
            repo.product = original_product
            repo.save()

            # Un-archive original Product
            original_product.is_repository_placeholder = False  # No longer archived
            original_product.migrated_to_product = None
            original_product.migration_date = None
            original_product.save()

        # Delete new consolidated Product (now empty)
        new_product.delete()
```

**7. Management Command Interface** (`dojo/management/commands/migrate_products_to_repositories.py`)

The CLI command orchestrates the entire flow with safety checks:

```bash
# Interactive mode - prompts for approval on each cluster
python manage.py migrate_products_to_repositories

# Auto-approve high-confidence clusters (≥80%)
python manage.py migrate_products_to_repositories --auto-approve-threshold 80

# Dry-run to preview without changes
python manage.py migrate_products_to_repositories --dry-run

# Rollback a migration
python manage.py migrate_products_to_repositories --rollback mig_20250116_142301
```

**Command execution flow**:
1. **Run clustering** via `wizard.get_clustering_suggestions()`
2. **Display summary**: Total repos, clusters, confidence breakdown (high/medium/low)
3. **Filter by approval threshold**: Auto-approve clusters ≥ threshold, or prompt user interactively
4. **Preview migration** via `wizard.preview_migration()` - shows validation errors/warnings
5. **Display impact**: How many Products/Repos/Findings/Tests/Engagements affected
6. **Confirm prompt**: User must type 'y' unless `--auto-approve-all` flag set
7. **Apply migration** via `wizard.apply_migration(dry_run=False)`
8. **Show results**: Created X products, updated Y repositories, archived Z products
9. **Print rollback command**: For easy undo if needed

### Real-World Validation Scenarios (What You Need to Test)

#### Scenario 1: Clustered Repository Group with Real GitHub Alerts

**Setup**:
1. Ingest real GitHub org repos: `docker compose exec uwsgi python manage.py sync_github_repositories --org myorg`
2. Wait for completion, verify Repository records created
3. Sync GitHub alerts: `docker compose exec uwsgi python manage.py sync_github_alerts`
4. Verify GitHubAlert and Finding records created for repos with vulnerabilities

**Test clustering**:
1. Run clustering: `docker compose exec uwsgi python manage.py migrate_products_to_repositories --dry-run`
2. Identify cluster with related repos (e.g., common prefix "service-*" or same language)
3. Verify cluster has reasonable confidence score (>50%)
4. Check suggested product name makes sense

**Test migration**:
1. Apply migration with auto-approve: `docker compose exec uwsgi python manage.py migrate_products_to_repositories --auto-approve-threshold 80`
2. Verify new Product created with correct name
3. Verify Repository.product ForeignKeys updated to new Product
4. **CRITICAL**: Verify Findings still accessible:
   ```python
   new_product = Product.objects.get(name="Service Platform")
   old_products = new_product.migrated_from_products.all()
   findings = Finding.objects.filter(test__engagement__product__in=old_products)
   assert findings.count() > 0  # Findings survived migration!
   ```
5. Verify old Products marked `is_repository_placeholder=True`, `migrated_to_product` set

**Test rollback**:
1. Note migration_id from output (e.g., "mig_20250116_153022")
2. Rollback: `docker compose exec uwsgi python manage.py migrate_products_to_repositories --rollback mig_20250116_153022`
3. Verify Repositories restored to original Products
4. Verify old Products un-archived (`is_repository_placeholder=False`, `migrated_to_product=None`)
5. Verify new consolidated Product deleted
6. Verify Findings still accessible under original Products

#### Scenario 2: Large Organization (2,451+ repos) Performance Test

**Setup**:
1. Full sync: `docker compose exec uwsgi python manage.py sync_github_repositories --org large-org`
2. Wait for completion (may take 15-20 hours for initial GraphQL sync)

**Test clustering performance**:
1. Run clustering with timing: `time docker compose exec uwsgi python manage.py migrate_products_to_repositories --dry-run`
2. Verify clustering completes in <5 seconds per 100 repos (2,451 repos → ~2.5 minutes max)
3. Check memory usage doesn't spike (clustering uses NumPy/SciPy, should handle 2,451 repos with <500MB)
4. Verify silhouette score optimization doesn't timeout (caps at 50 cluster attempts)

**Test migration performance**:
1. Select high-confidence clusters totaling ~500 repos
2. Run migration: `time docker compose exec uwsgi python manage.py migrate_products_to_repositories --auto-approve-threshold 85`
3. Verify transaction completes without timeout (Django default 30s should be sufficient)
4. Check database for deadlocks/conflicts (multiple concurrent migrations not supported)

#### Scenario 3: Edge Cases

**Orphaned repositories** (not in any cluster):
- Some repos may not cluster well (unique names, different tech stack)
- Verify they retain their current Product assignments
- Check warning message appears in preview

**Single-repo Products** (after migration):
- Some repos may form clusters of 1
- Verify confidence score = 60 (lower than multi-repo clusters)
- Product name should be clean version of repo name (without org prefix)

**Duplicate repository assignments** (validation should catch):
- Manually construct groupings with same repo in multiple groups
- Verify `preview_migration()` returns `success=False` with error message
- Ensure transaction doesn't start if validation fails

**Missing Product_Type** (shouldn't happen with real data):
- All Products require prod_type ForeignKey
- Use first available Product_Type if not specified in grouping

#### Scenario 4: GitHub Alerts Continue Working Post-Migration

**Setup**:
1. Complete migration as in Scenario 1
2. New GitHub alerts appear in repos (or manually trigger re-sync)

**Test alert sync post-migration**:
1. Run: `docker compose exec uwsgi python manage.py sync_github_alerts --force`
2. Verify new GitHubAlert records created
3. Verify Finding creation uses ORIGINAL placeholder Product (not new consolidated Product)
4. Why? Because `findings_converter.py` creates Engagement under `repository.product`, and if you update repository.product to consolidated Product, new Findings would go to wrong place.

**POTENTIAL BUG TO INVESTIGATE**: After migration, `repository.product` points to new consolidated Product. But `findings_converter._get_or_create_engagement()` uses `repository.product` to create Engagement. This means NEW alerts post-migration would create Engagements under the consolidated Product, not the original placeholder. Is this desired behavior? Or should we store `repository.original_product` to maintain consistency?

**Recommendation**: Add `Repository.original_product` ForeignKey (nullable) that stores the pre-migration Product, and update findings_converter to use that for Engagement creation. This keeps all Findings (old and new) under same Product hierarchy.

### Technical Reference Details

#### Component Interfaces & Critical Functions

**RepositoryClusteringEngine** (`clustering.py`):
```python
def cluster_repositories(
    repositories: List[Repository],
    suggested_num_clusters: int = None
) -> Dict[str, Any]:
    # Returns: {dendrogram, suggested_cut_height, num_clusters, clusters}
```

**ProductMigrationWizard** (`migration_wizard.py`):
```python
def get_clustering_suggestions(
    product_type_id: Optional[int] = None,
    suggested_num_clusters: Optional[int] = None
) -> Dict[str, Any]:
    # Returns: {success, clusters, summary, dendrogram}

def preview_migration(groupings: List[Dict]) -> Dict[str, Any]:
    # Returns: {success, validation_errors, validation_warnings, impact, breakdown}

@transaction.atomic
def apply_migration(
    groupings: List[Dict],
    dry_run: bool = False
) -> Dict[str, Any]:
    # Returns: {success, migration_id, created_products, updated_repositories, archived_products}

@transaction.atomic
def rollback_migration(migration_id: str) -> Dict[str, Any]:
    # Returns: {success, migration_id, restored_repositories, deleted_products}
```

**Management Commands**:
```bash
# Repository sync (GraphQL for bulk, REST for single)
python manage.py sync_github_repositories [--org ORG] [--incremental] [--product-id ID] [--use-rest]

# Alert sync (creates GitHubAlert records)
python manage.py sync_github_alerts [--repository-id ID] [--force] [--create-findings]

# Migration
python manage.py migrate_products_to_repositories [--dry-run] [--auto-approve-threshold N] [--rollback ID]
```

#### Data Structures

**Product model** (new migration fields):
```python
is_repository_placeholder = models.BooleanField(default=False)  # Legacy 1:1 placeholder
migrated_to_product = models.ForeignKey('self', null=True, related_name='migrated_from_products')
migration_date = models.DateTimeField(null=True)
```

**Repository model** (already exists):
```python
product = models.ForeignKey(Product, related_name="repositories")  # Updated during migration
github_repo_id = models.BigIntegerField(unique=True)
primary_language, primary_framework, tier, codeowners_content  # Clustering features
has_dockerfile, has_kubernetes_config, ...  # 36 binary signals
```

**GitHubAlert model** (stores raw alerts):
```python
repository = models.ForeignKey(Repository, related_name="github_alerts")
finding = models.ForeignKey(Finding, null=True)  # Link after conversion
alert_type = models.CharField(choices=['dependabot', 'codeql', 'secret_scanning'])
github_alert_id = models.CharField()  # Alert number from GitHub
severity, state, cve, cwe, package_name, file_path, ...  # Alert metadata
```

**Finding model** (vulnerability records):
```python
test = models.ForeignKey(Test)  # → Engagement → Product chain
unique_id_from_tool = models.CharField()  # "github-{type}-{repo_id}-{alert_number}"
severity, cve, cwe, title, description, mitigation  # Vulnerability details
active, is_mitigated, risk_accepted, false_p  # State fields
```

#### Database Migration

**Migration 0252** adds three fields to Product:
```python
migrations.AddField(
    model_name='product',
    name='is_repository_placeholder',
    field=models.BooleanField(default=False, help_text='True if this Product was auto-created as a 1:1 placeholder for a single repository (before Phase 4 migration)')
)
migrations.AddField(
    model_name='product',
    name='migrated_to_product',
    field=models.ForeignKey(..., on_delete=models.SET_NULL, related_name='migrated_from_products')
)
migrations.AddField(
    model_name='product',
    name='migration_date',
    field=models.DateTimeField(null=True, help_text='When this Product was migrated to a new grouping (Phase 4)')
)
```

#### Docker Environment Setup

**Run management command in Docker**:
```bash
# Start services
docker compose up -d

# Wait for initializer (creates DB schema, ~3 minutes)
docker compose logs -f initializer

# Execute command in uwsgi container
docker compose exec uwsgi bash -c "python manage.py sync_github_repositories --org myorg"

# Or enter shell
docker compose exec uwsgi bash
python manage.py migrate_products_to_repositories --dry-run
```

**Environment variables** (set in docker-compose.yml or .env):
```bash
DD_GITHUB_TOKEN=ghp_xxxxx  # Personal access token with repo:read, admin:org:read
DD_GITHUB_ORG=myorg        # Organization name
DD_DATABASE_URL=postgresql://defectdojo:defectdojo@postgres:5432/defectdojo
```

**Run unit tests**:
```bash
# Test clustering
./run-unittest.sh --test-case unittests.test_repository_clustering.RepositoryClusteringEngineTest

# Test migration wizard
./run-unittest.sh --test-case unittests.test_product_migration.ProductMigrationWizardTest

# All Phase 4 tests
./run-unittest.sh --test-case unittests.test_repository_clustering
./run-unittest.sh --test-case unittests.test_product_migration
```

### Critical Validation Checklist

**Before any migration**:
- [ ] Real GitHub repositories ingested (not test fixtures)
- [ ] GitHubAlert records exist for repos with vulnerabilities
- [ ] Finding records created from alerts (use --create-findings flag)
- [ ] Clustering produces reasonable groupings (confidence >50%)
- [ ] Preview shows expected impact (correct Finding count)

**During migration**:
- [ ] Transaction completes without errors
- [ ] New Products created with correct names
- [ ] Repository ForeignKeys updated
- [ ] Old Products archived with migration metadata
- [ ] No Findings lost (count before = count after)

**After migration**:
- [ ] Findings accessible via migrated_from_products reverse relation
- [ ] Rollback restores original state completely
- [ ] New GitHub alert sync still works
- [ ] UI displays consolidated Products correctly (when UI implemented)

### Known Limitations & Edge Cases

1. **No Engagement/Test/Finding migration**: Old Products remain as archived containers for historical data. This preserves audit trail but means queries need to traverse migrated_to_product relations.

2. **Post-migration alert sync behavior**: New alerts after migration go to consolidated Product (via repository.product), mixing with pre-migration alerts under old Products. Consider adding `repository.original_product` field.

3. **Concurrent migrations not supported**: Single management command must run to completion. Multiple migrations would cause ForeignKey conflicts.

4. **90-day rollback window**: After old Products are deleted, rollback impossible. Should add safeguard against deletion of migrated Products.

5. **Large cluster performance**: Clustering 2,451 repos with 70+ features uses ~500MB memory, completes in ~2 minutes. If dataset grows to 10,000+ repos, may need batch processing or distributed clustering.

6. **GraphQL rate limits**: Initial full sync of 2,451 repos takes ~98,000 points (15-20 hours). GitHub limit is 5,000 points/hour. Incremental sync (50-100 repos) uses ~2,000 points (<5 minutes). Always use `--incremental` for daily syncs.

### Files to Examine During Validation

**Phase 4 implementation**:
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/clustering.py` (700 lines, clustering algorithm)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/product/migration_wizard.py` (450 lines, migration logic)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/management/commands/migrate_products_to_repositories.py` (230 lines, CLI)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/db_migrations/0252_product_migration_tracking.py` (schema changes)

**GitHub integration** (for understanding real data):
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/collector.py` (repository sync)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/alerts_collector.py` (alert fetching)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/findings_converter.py` (alert → Finding)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/README_GRAPHQL.md` (GraphQL API docs)

**Models** (data structure):
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/models.py` (Product lines 1120-1400, Repository lines 1537-1750, GitHubAlert lines 1769-2024, Finding lines 3140-3600)

**Unit tests** (validation examples):
- `/Users/1haris.sid/defectdojo/RepoRelay/unittests/test_repository_clustering.py` (238 lines, 16 test cases)
- `/Users/1haris.sid/defectdojo/RepoRelay/unittests/test_product_migration.py` (391 lines, 15 test cases)

**Management commands** (real data ingestion):
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/management/commands/sync_github_repositories.py` (GraphQL sync)
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/management/commands/sync_github_alerts.py` (alert sync)

## User Notes
**Testing Approach - Use REAL GitHub Data**:
- Ingest actual GitHub organization repositories using `python manage.py sync_github_repositories`
- DO NOT use synthetic/mock test data - all validation must use real ingested repos
- Code review critical components first
- Test management command with real repository data
- Use Playwright MCP for UI testing (when UI is implemented) with real data
- Verify backward compatibility with existing Products/Findings from real GitHub alerts

**Data Ingestion Setup**:
1. Use existing GitHub collector to ingest repos: `python manage.py sync_github_repositories --org [org-name]`
2. Verify Repository records created with real metadata (language, framework, signals)
3. Sync GitHub alerts: `python manage.py sync_github_alerts` to populate real Findings
4. Confirm real GitHub Alerts exist before testing migration

**Key Real-World Scenarios**:
1. Find repos with common prefixes in real data (e.g., "auth-*", "payment-*", "admin-*")
2. Test clustering groups these related repos correctly
3. Execute migration on real grouped repos → verify new Products created
4. Confirm real GitHub Alert Findings still accessible after migration
5. Test rollback restores original structure with real data intact

## Work Log
<!-- Updated as work progresses -->
