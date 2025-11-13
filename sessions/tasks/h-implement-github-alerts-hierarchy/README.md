---
name: h-implement-github-alerts-hierarchy
branch: feature/github-alerts-hierarchy
status: pending
created: 2025-01-13
---

# GitHub Security Alerts → Repository → Product → Business Unit Hierarchy

## Problem/Goal

**Current Problem**: The existing DefectDojo implementation creates 1 Product per GitHub repository (2,451 Products for 2,451 repos), which violates DefectDojo's intended architecture where Products represent applications/services, not individual repositories. Additionally, GitHub security alerts (CodeQL, Dependabot, Secret Scanning) are not integrated into DefectDojo's vulnerability management workflow.

**Goal**: Implement proper data hierarchy that allows:
1. **Multi-level organization**: Business Unit (Product_Type) → Product (Application) → Repository (1:many) → Security Alerts
2. **GitHub Security Alerts integration**: Map CodeQL, Dependabot, and Secret Scanning alerts to DefectDojo Findings
3. **Multi-tier dashboards**: Executive (Business Unit), Product, and Repository-level views
4. **Backward compatibility**: Gradual migration from existing 2,451 Products without data loss

**Example hierarchy**:
```
Product_Type: "IAM Team" (Business Unit)
  └── Product: "Auth Service" (Application)
      ├── Repository: "myorg/auth-api"
      │   ├── 15 Dependabot alerts
      │   ├── 23 CodeQL alerts
      │   └── 2 Secret scanning alerts
      ├── Repository: "myorg/auth-frontend"
      └── Repository: "myorg/auth-infra"
```

## Success Criteria

**Phase 1: Repository Model**
- [ ] Repository model created with 47 fields (migrated from Product)
- [ ] Database migrations successfully applied
- [ ] Existing 2,451 Products converted to Repository records
- [ ] Admin UI can create/edit/delete Repositories

**Phase 2: GitHub Alerts Collector**
- [ ] GraphQL client extended to fetch Dependabot alerts
- [ ] REST API integration for CodeQL and Secret Scanning alerts
- [ ] Alerts sync incrementally (only changed repos)
- [ ] Rate limit consumption stays under 80% during sync

**Phase 3: Finding Integration**
- [ ] Each Repository has Engagement with 3 Tests (CodeQL, Dependabot, Secrets)
- [ ] GitHub alerts mapped to DefectDojo Findings
- [ ] Alert state changes (open→dismissed→fixed) sync bidirectionally
- [ ] Deduplication works using github_alert_id

**Phase 4: Product Grouping**
- [ ] Migration wizard UI shows suggested Product groupings
- [ ] ML clustering suggests logical repo→product assignments
- [ ] User can manually group repositories into Products
- [ ] Existing Findings remain linked during migration

**Phase 5: Dashboards**
- [ ] Repository Dashboard (individual repo health + alerts)
- [ ] Product Dashboard (aggregated view across repos)
- [ ] Business Unit Dashboard (executive summary)
- [ ] All dashboards have drill-down capability
- [ ] Dashboard loads in <2 seconds (pre-computed statistics)

**Phase 6: REST API & Automation**
- [ ] 8 new REST API endpoints for Repository CRUD and statistics
- [ ] Celery task for hourly alert sync (incremental)
- [ ] Celery task for 6-hour statistics pre-computation
- [ ] Management command for manual alert sync

**Overall Integration**
- [ ] Auto-triage engine works with GitHub alerts (EPSS + tier + severity)
- [ ] SLA tracking works for GitHub alerts
- [ ] Jira integration creates tickets for critical GitHub alerts
- [ ] Notifications trigger on new critical alerts
- [ ] Full backward compatibility with existing Products/Findings

## Architecture Overview

### Data Model

**New Model: Repository**
```python
class Repository(models.Model):
    # Core identification
    name = CharField  # "myorg/myrepo"
    github_repo_id = BigIntegerField (unique)
    github_url = URLField

    # Product relationships
    product = ForeignKey(Product)  # Primary product (1:many)
    related_products = ManyToManyField(Product)  # Shared libraries

    # All 47 enrichment fields (moved from Product)
    # - Activity: last_commit_date, active_contributors_90d, days_since_last_commit
    # - Metadata: readme_summary, primary_language, primary_framework
    # - Ownership: codeowners_content, ownership_confidence
    # - 36 binary signals: has_dockerfile, has_kubernetes_config, etc.

    # GitHub alerts metadata
    last_alert_sync = DateTimeField
    dependabot_alert_count = IntegerField
    codeql_alert_count = IntegerField
    secret_scanning_alert_count = IntegerField

    # Pre-computed statistics
    cached_finding_counts = JSONField  # {critical: 5, high: 12, ...}

    # Computed tier
    tier = CharField(choices=[tier1, tier2, tier3, tier4, archived])
```

### GitHub Alerts → DefectDojo Mapping

**Strategy**: Create Engagement per Repository with 3 Tests:

1. **Dependabot Alerts** → Test "GitHub Dependabot"
   - Fetch via GraphQL: `repository.vulnerabilityAlerts`
   - Map to Finding: CVE, severity, package info
   - EPSS integration available (CVE-based)

2. **CodeQL Alerts** → Test "GitHub CodeQL"
   - Fetch via REST: `/repos/{owner}/{repo}/code-scanning/alerts`
   - Map to Finding: CWE, rule description, file location
   - Custom auto-triage rules (no CVE)

3. **Secret Scanning** → Test "GitHub Secret Scanning"
   - Fetch via REST: `/repos/{owner}/{repo}/secret-scanning/alerts`
   - Map to Finding: Secret type, location
   - Always critical severity

**Deduplication**: Use `unique_id_from_tool = "github-{alert_type}-{alert_number}"`

### Dashboard Hierarchy

**Level 1: Repository Dashboard** (`/repository/{id}/dashboard/`)
- Alert summary cards (3 types with counts)
- Time-series chart (alerts opened/closed over 90 days)
- DataTables for each alert type
- Repository health (36 signals as badges)

**Level 2: Product Dashboard** (`/product/{id}/dashboard/`)
- Repository summary (count, tier distribution)
- Aggregated alert cards across all repos
- Top 10 repositories by alerts
- Cross-repo duplicates view
- SLA compliance metrics

**Level 3: Business Unit Dashboard** (`/product_type/{id}/dashboard/`)
- Executive summary (total products, repos, alerts)
- Product comparison table
- Alert distribution charts (pie, bar, line)
- Compliance metrics
- PDF export capability

### Migration Strategy

**Phase 4 will handle migration**:
1. Create Repository records from existing Products (1:1 initially)
2. Mark original Products with `is_repository_placeholder=True`
3. ML clustering suggests logical Product groupings
4. Admin wizard allows user to review/approve/modify groupings
5. Gradual migration over 3-6 months (not big-bang)

## Subtasks

This task is divided into 6 phases, each implemented as a subtask:

1. **`phase1-repository-model.md`** - Repository model, migrations, admin UI (1 week, 300 lines)
2. **`phase2-alerts-collector.md`** - GitHub alerts API integration (2 weeks, 600 lines)
3. **`phase3-finding-integration.md`** - Map alerts to Findings (1 week, 400 lines)
4. **`phase4-product-grouping.md`** - Migration wizard + ML clustering (2 weeks, 500 lines)
5. **`phase5-dashboards.md`** - 3-tier dashboard views (2 weeks, 800 lines)
6. **`phase6-api-tasks.md`** - REST API + Celery tasks (1 week, 400 lines)

**Total Estimate**: 9 weeks, ~3,000 lines of code

## Technical Design Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Repository as separate model | Enables 1:many Product→Repository | Migration complexity |
| Map alerts to Findings | Integrates with DefectDojo workflows | Loses some GitHub metadata |
| Mixed GraphQL + REST | GraphQL lacks CodeQL/Secrets support | More API calls |
| Gradual migration | Preserves data, low-risk | Takes 3-6 months |
| Pre-computed statistics | Dashboard performance | Staleness (6-hour refresh) |
| Primary + related products | Handles shared libraries | Findings to primary only |
| Incremental alert sync | Rate-limit friendly | 1-hour latency |

## Context Manifest

### How DefectDojo's Current Data Hierarchy Works

DefectDojo uses a 4-tier hierarchy for security testing and findings management:

**Tier 1: Product_Type (Business Unit)**
- Located: `dojo/models.py` lines 847-920
- Represents top-level organizational divisions (teams, offices, business units)
- Fields: `name`, `description`, `critical_product`, `key_product`, `updated`, `created`
- Relationships: One Product_Type has many Products via `prod_type` ForeignKey
- Example: "IAM Team", "Mobile Apps", "Cloud Infrastructure"
- Members/Authorization: Many-to-many with Dojo_User and Dojo_Group for RBAC

**Tier 2: Product (Application/Service)**
- Located: `dojo/models.py` lines 1120-1400+
- **CURRENTLY** being used as 1:1 with GitHub repositories (2,451 Products for 2,451 repos)
- **INTENDED** to represent logical applications/services that may span multiple repos
- Core fields:
  - `name` (CharField, unique) - Currently "org/repo", should be "Auth Service"
  - `description` (CharField, 4000 chars)
  - `prod_type` (ForeignKey to Product_Type) - Business unit assignment
  - `created`, `updated` (DateTimeField with auto_now)
  - `business_criticality` (CharField) - Choices: "very high", "high", "medium", "low", "very low", "none"
  - `platform` (CharField) - API, Desktop, IoT, Mobile, Web
  - `lifecycle` (CharField) - Construction, Production, Retirement
  - `origin` (CharField) - Third party, Purchased, Contractor, Internal, Open source, Outsourced

**47 GitHub Enrichment Fields Currently on Product Model** (Lines 1240-1380):
These will be MOVED to the new Repository model in Phase 1:

*Activity Metrics:*
- `last_commit_date` (DateTimeField, null=True)
- `active_contributors_90d` (IntegerField, default=0)
- `days_since_last_commit` (IntegerField, null=True)

*Repository Metadata:*
- `github_url` (URLField, 600 chars) - "https://github.com/org/repo"
- `github_repo_id` (CharField, 100) - GitHub's numeric ID as string
- `readme_summary` (TextField, 500 chars)
- `readme_length` (IntegerField, default=0)
- `primary_language` (CharField, 50) - "Python", "JavaScript", etc.
- `primary_framework` (CharField, 50) - "Django", "React", etc.

*Ownership:*
- `codeowners_content` (TextField) - Raw CODEOWNERS file content
- `ownership_confidence` (IntegerField, 0-100) - Calculated from CODEOWNERS coverage

*36 Binary Signals* (all BooleanField, default=False):
- **Tier 1 - Deployment (6):** `has_dockerfile`, `has_kubernetes_config`, `has_ci_cd`, `has_terraform`, `has_deployment_scripts`, `has_environments`
- **Tier 2 - Production (5):** `has_monitoring`, `has_releases`, `recent_release_90d`, `has_branch_protection`, `has_codeowners`
- **Tier 3 - Development Activity (5):** `recent_commits_30d`, `recent_commits_90d`, `active_contributors`, `active_prs_30d`, `has_dependabot`
- **Tier 4 - Code Organization (6):** `has_tests`, `has_documentation`, `has_readme`, `readme_length_500`, `has_api_spec`, `has_changelog`
- **Tier 5 - Security (5):** `has_security_policy`, `has_secret_scanning`, `has_sbom`, `has_security_txt`, `has_code_scanning`
- **Additional (9):** `has_package_manager`, `has_license`, `has_contributing_guide`, `has_code_of_conduct`, `has_issue_templates`, `has_pr_template`, `has_gitignore`, and more

**Tier 3: Engagement (Testing Activity)**
- Located: `dojo/models.py` lines 1664-1812
- Represents time-bound security testing activities within a Product
- Fields: `name`, `description`, `version`, `target_start`, `target_end`, `lead` (ForeignKey to Dojo_User)
- `product` (ForeignKey to Product) - Parent relationship
- `status` choices: "Not Started", "Blocked", "Cancelled", "Completed", "In Progress", "On Hold", "Waiting for Resource"
- `active` (BooleanField) - Auto-managed based on status
- Special purpose: `notes` (ManyToMany), `files` (ManyToMany)

**Tier 4: Test (Scan/Assessment)**
- Located: `dojo/models.py` lines 2275-2340
- Represents individual security scans or assessments
- Fields: `title`, `test_type` (ForeignKey to Test_Type), `scan_type` (TextField)
- `engagement` (ForeignKey to Engagement) - Parent relationship
- `target_start`, `target_end` (DateTimeField)
- `environment` (ForeignKey to Development_Environment)
- Version tracking: `version`, `build_id`, `commit_hash`, `branch_tag`

**Tier 5: Finding (Vulnerability)**
- Located: `dojo/models.py` lines 2504-3100+
- Individual security vulnerability instances
- **Deduplication Fields** (CRITICAL for GitHub alerts):
  - `unique_id_from_tool` (CharField, 255) - Primary deduplication key (line 64 in github_vulnerability/parser.py)
  - `hash_code` (CharField, 64) - MD5 hash for complex deduplication
  - `duplicate` (BooleanField) - True if deduplicated
  - `duplicate_finding` (ForeignKey to self) - Points to original finding
  - `vuln_id_from_tool` (CharField, 200) - Tool's vulnerability identifier
- Severity: `severity` (CharField) - Critical, High, Medium, Low, Info
- Status fields: `active`, `verified`, `false_p`, `is_mitigated`, `out_of_scope`, `risk_accepted`
- CVE integration: `cve` (CharField, 50), `epss_score`, `epss_percentile`, `known_exploited`, `ransomware_used`
- Location: `file_path`, `line`, `component_name`, `component_version`
- Relationships: `test` (ForeignKey to Test), `endpoints` (ManyToMany)

### How GitHub Integration Currently Works

**GitHub Collector System** (`dojo/github_collector/`)

The existing GitHub collector enriches Product records with repository metadata using a hybrid GraphQL + REST approach:

**1. GraphQL Client** (`graphql_client.py`, 483 lines)
- Endpoint: `https://api.github.com/graphql`
- Authentication: Bearer token in headers
- Query templates in `queries/` directory:
  - `repository_full.graphql` - Single repo (cost: 30-40 points)
  - `organization_batch.graphql` - Batch 100 repos (cost: ~4,000 points)
- Rate limit: 5,000 points/hour with `rateLimit { cost, remaining, resetAt }` tracking
- **Incremental sync strategy**: Pass `updated_since` parameter to filter repos by `updatedAt > threshold`
  - Typical daily sync: 50-100 repos in <5 minutes
  - Full sync: 2,451 repos in 15-20 hours (one-time)

**2. Repository Collector** (`collector.py`, 831 lines)
- Main orchestrator class: `GitHubRepositoryCollector`
- Initialization: `__init__(github_token, github_org, use_graphql=True)`
- Key methods:
  - `sync_all_repositories(incremental=True)` - Bulk sync with GraphQL
  - `sync_repository(repo)` - Single repo sync with REST
  - `sync_product_from_github_url(product)` - Update existing Product
  - `_sync_repository_from_graphql(repo_data)` - Process GraphQL response

**Data Collection Flow:**
```python
# GraphQL data structure (parsed in _parse_repository_data):
{
    'nameWithOwner': 'myorg/myrepo',
    'url': 'https://github.com/myorg/myrepo',
    'databaseId': 123456789,
    'primaryLanguage': 'Python',
    'commits': {
        'lastCommitDate': '2025-01-13T10:30:00Z',
        'contributorCount': 15,
        'contributors': ['user1@example.com', 'user2@example.com']
    },
    'fileTree': [
        {'path': 'Dockerfile', 'type': 'blob'},
        {'path': '.github/workflows/ci.yml', 'type': 'blob'}
    ],
    'codeowners': {
        'content': '* @myorg/platform-team',
        'confidence': 40  # 4 rules * 10%
    },
    'readme': '# My Repo\n...',
    'environments': {'totalCount': 2},
    'releases': {'totalCount': 50, 'recent': [...]},
    'branchProtection': {'totalCount': 1},
    'pullRequests': {'totalCount': 234, 'recent': [...]},
    'vulnerabilityAlerts': {'totalCount': 5}
}
```

**Product Update Logic** (lines 304-334 in collector.py):
```python
with transaction.atomic():
    # Activity
    product.last_commit_date = metadata['last_commit_date']
    product.active_contributors_90d = metadata['active_contributors_90d']
    product.days_since_last_commit = metadata['days_since_last_commit']

    # Metadata
    product.github_url = repo_data.get('url')
    product.github_repo_id = str(repo_data.get('databaseId'))
    product.readme_summary = readme_data['summary']
    product.primary_language = readme_data['primary_language']

    # Binary signals (36 fields)
    for signal_name, signal_value in signals.items():
        setattr(product, signal_name, signal_value)

    # Tier classification
    product.business_criticality = classification['business_criticality']

    # Archival
    if classification['tier'] == 'archived':
        product.lifecycle = Product.RETIREMENT

    product.save()
```

**3. Signal Detector** (`signal_detector.py`, 458 lines)
- Class: `SignalDetector(repo)`
- Main method: `detect_all_signals()` returns `Dict[str, bool]`
- Detection patterns (class attributes):
  - `DOCKERFILE_PATTERNS = ['Dockerfile', 'Dockerfile.*', 'docker/Dockerfile']`
  - `KUBERNETES_PATTERNS = ['kubernetes/', 'k8s/', 'helm/', 'deployment.yaml']`
  - `CI_CD_PATTERNS = ['.github/workflows/', '.gitlab-ci.yml', 'Jenkinsfile']`
- File tree caching: `_cache_file_tree()` fetches recursive tree once
- Pattern matching: `_detect_pattern(patterns)` with glob→regex conversion
- GitHub API checks: `_detect_github_environments()`, `_detect_github_releases()`

**4. Tier Classifier** (`tier_classifier.py`)
- Input: 36 binary signals + `days_since_last_commit`
- Output: `{'tier': 'tier1', 'business_criticality': 'very high', 'confidence_score': 85}`
- Tier thresholds:
  - **Tier 1 (Very High):** 25+ signals, deployment + production indicators, <30 days since commit
  - **Tier 2 (High):** 18-24 signals, production indicators, <90 days
  - **Tier 3 (Medium):** 12-17 signals, active development
  - **Tier 4 (Low):** 6-11 signals, some organization
  - **Archived:** 0-5 signals OR >180 days since commit

**5. Management Command** (`management/commands/sync_github_repositories.py`, 229 lines)
```bash
# Daily incremental sync (recommended)
python manage.py sync_github_repositories --incremental

# Full sync (one-time)
python manage.py sync_github_repositories

# REST fallback
python manage.py sync_github_repositories --use-rest --incremental

# Single product
python manage.py sync_github_repositories --product-id 123
```

### GitHub Security Alerts APIs

DefectDojo needs to integrate 3 GitHub security alert types. Here's what's available:

**1. Dependabot Alerts (Dependency Vulnerabilities)**

*GraphQL API (AVAILABLE):*
- Query: `repository { vulnerabilityAlerts(first: 100) { nodes { ... } } }`
- Fields available:
  - `id` (unique alert ID for deduplication)
  - `number` (alert number in repo, for URLs)
  - `state` - "OPEN", "FIXED", "DISMISSED"
  - `createdAt`, `dismissedAt`, `fixedAt`
  - `securityVulnerability { advisory { summary, description, severity, cwes, identifiers, references } }`
  - `vulnerableManifestPath` (file location)
  - `vulnerableRequirements` (version range)
  - `dependabotUpdate { pullRequest { permalink } }` (fix PR if available)
- Rate limit: ~10 points per query for 100 alerts
- **Parser exists**: `dojo/tools/github_vulnerability/parser.py` (216 lines)
  - Line 64: `unique_id_from_tool=alert.get('id')`
  - Line 88-90: State mapping: FIXED/DISMISSED → `active=False, is_mitigated=True`
  - Severity conversion: "MODERATE" → "Medium"
  - CVE extraction: `advisory.identifiers` → `finding.cve`
  - EPSS integration: `advisory.epss` → `finding.epss_score`

*REST API (FALLBACK):*
- Endpoint: `GET /repos/{owner}/{repo}/dependabot/alerts`
- Requires: `security_events:read` permission
- Response: Array of alerts with similar structure

**2. Code Scanning Alerts (SAST - CodeQL/Semgrep/etc.)**

*REST API ONLY (GraphQL NOT AVAILABLE):*
- Endpoint: `GET /repos/{owner}/{repo}/code-scanning/alerts`
- Requires: `security_events:read` permission
- Fields:
  - `number` (alert ID)
  - `state` - "open", "dismissed", "fixed"
  - `created_at`, `updated_at`, `dismissed_at`, `fixed_at`
  - `rule { id, name, description, severity, security_severity_level, tags }`
  - `most_recent_instance { ref, analysis_key, environment, category, commit_sha, location, message }`
  - `tool { name, version }` - "CodeQL", "Semgrep", etc.
  - `instances_url` - Link to all instances
- Rate limit: 1 REST call (no cost points)
- **Parser exists**: `dojo/tools/github_sast/parser.py` (if Code Scanning exports SARIF format)
- Severity mapping: `security_severity_level` → "Critical", "High", "Medium", "Low"

**3. Secret Scanning Alerts**

*REST API ONLY:*
- Endpoint: `GET /repos/{owner}/{repo}/secret-scanning/alerts`
- Requires: `security_events:read` permission
- Fields:
  - `number` (alert ID)
  - `state` - "open", "resolved"
  - `created_at`, `updated_at`, `resolved_at`
  - `secret_type` - "github_token", "aws_access_key", "private_key", etc.
  - `secret` - Redacted version of the secret
  - `resolution` - "false_positive", "revoked", "used_in_tests", etc.
  - `locations` - Array of file paths and line numbers
- Rate limit: 1 REST call
- **No existing parser** - Need to create
- **Always critical severity** per task requirements

### Finding Creation and Deduplication Patterns

**Parser Structure** (Example: `dojo/tools/github_vulnerability/parser.py`)

Every DefectDojo parser follows this contract:

```python
class MyToolParser:
    def get_scan_types(self):
        """Return list of scan type names"""
        return ["Github Vulnerability Scan"]

    def get_label_for_scan_types(self, scan_type):
        """Human-readable label for UI"""
        return scan_type

    def get_description_for_scan_types(self, scan_type):
        """Help text for import UI"""
        return "Import vulnerabilities from Github API"

    def get_findings(self, filename, test):
        """Parse file and return list of Finding objects (unsaved)"""
        data = json.load(filename)
        findings = []

        for alert in data:
            finding = Finding(
                title="Short description",
                test=test,  # Required: links to Test object
                description="Full markdown description",
                severity="Critical",  # Critical|High|Medium|Low|Info
                active=True,  # False if fixed/dismissed
                static_finding=True,  # vs dynamic_finding
                unique_id_from_tool="github-dependabot-123456",  # CRITICAL for deduplication
                date=datetime.now()
            )

            # Optional enrichment
            finding.cve = "CVE-2024-1234"
            finding.cwe = 79  # Integer
            finding.cvssv3 = "CVSS:3.1/AV:N/AC:L/..."
            finding.cvssv3_score = 9.8
            finding.epss_score = 0.95
            finding.file_path = "requirements.txt"
            finding.component_name = "django"
            finding.component_version = "3.2.0"
            finding.is_mitigated = alert['state'] == 'FIXED'

            findings.append(finding)

        return findings
```

**Deduplication Logic** (`dojo/finding/helper.py`)

DefectDojo uses `unique_id_from_tool` for primary deduplication:

1. **On import/reimport**, the importer (`dojo/importers/default_reimporter.py`) checks:
   ```python
   existing_finding = Finding.objects.filter(
       test=test,
       unique_id_from_tool=new_finding.unique_id_from_tool
   ).first()

   if existing_finding:
       # UPDATE existing finding
       existing_finding.active = new_finding.active
       existing_finding.severity = new_finding.severity
       # ... update all fields
       existing_finding.save()
       action = IMPORT_UNTOUCHED_FINDING  # or IMPORT_REACTIVATED_FINDING
   else:
       # CREATE new finding
       new_finding.save()
       action = IMPORT_CREATED_FINDING
   ```

2. **Finding state transitions**:
   - Alert goes away in next scan → `active=False`, `is_mitigated=True`
   - Alert reappears → `active=True` (reactivation)
   - Manual close → `is_mitigated=True`, `mitigated_by=user`, `mitigated=datetime`

3. **Deduplication format**: Must be unique per repository + alert:
   - Dependabot: `"github-dependabot-{alert_number}"`
   - CodeQL: `"github-codeql-{alert_number}"`
   - Secrets: `"github-secrets-{alert_number}"`
   - Alert number is stable across API calls (doesn't change on update)

**Test_Import Tracking** (`dojo/models.py` lines 2438-2502)

Every import creates a `Test_Import` record:
- `test` (ForeignKey to Test)
- `created` (auto_now_add) - Timestamp of import
- `type` (CharField) - "Import" or "Re-Import"
- Statistics via `Test_Import_Finding_Action`:
  - `IMPORT_CREATED_FINDING` - New findings
  - `IMPORT_CLOSED_FINDING` - Auto-closed (not in scan)
  - `IMPORT_REACTIVATED_FINDING` - Previously closed, now active
  - `IMPORT_UNTOUCHED_FINDING` - No changes

### REST API Architecture

**Base Patterns** (`dojo/api_v2/views.py`)

DefectDojo REST API uses Django REST Framework with custom base classes:

```python
# Base ViewSet classes
class DojoModelViewSet(viewsets.ModelViewSet, DeletePreviewModelMixin):
    """Standard CRUD ViewSet"""
    pass

class PrefetchDojoModelViewSet(
    prefetch.PrefetchListMixin,
    prefetch.PrefetchRetrieveMixin,
    DojoModelViewSet
):
    """Optimized ViewSet with prefetch for relationships"""
    pass
```

**Product ViewSet Example** (lines 1699-1740):
```python
@extend_schema_view(**schema_with_prefetch())
class ProductViewSet(
    prefetch.PrefetchListMixin,
    prefetch.PrefetchRetrieveMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
    dojo_mixins.DeletePreviewModelMixin,
):
    serializer_class = serializers.ProductSerializer
    queryset = Product.objects.none()  # Security: start with empty
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ApiProductFilter
    permission_classes = (
        IsAuthenticated,
        permissions.UserHasProductPermission,
    )

    def get_queryset(self):
        # CRITICAL: Always filter by authorization
        return get_authorized_products(Permissions.Product_View).distinct()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if get_setting("ASYNC_OBJECT_DELETE"):
            async_del = async_delete()
            async_del.delete(instance)
        else:
            instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='statistics')
    def statistics(self, request, pk=None):
        """Custom endpoint: /api/v2/products/{id}/statistics/"""
        product = self.get_object()
        stats = {
            'findings_count': product.findings_count,
            'critical': Finding.objects.filter(
                test__engagement__product=product,
                severity='Critical',
                active=True
            ).count()
        }
        return Response(stats)
```

**Serializer Pattern** (`dojo/api_v2/serializers.py` lines 2102-2132):
```python
class ProductSerializer(serializers.ModelSerializer):
    findings_count = serializers.SerializerMethodField()
    findings_list = serializers.SerializerMethodField()
    tags = TagListSerializerField(required=False)
    product_meta = ProductMetaSerializer(read_only=True, many=True)

    class Meta:
        model = Product
        exclude = (
            'tid',  # Internal field
            'updated',  # Auto-managed
            'async_updating',  # Internal flag
        )

    def validate(self, data):
        # Custom validation logic
        if self.instance and self.instance.async_updating:
            if data.get('sla_configuration') != self.instance.sla_configuration:
                raise serializers.ValidationError(
                    "Cannot change SLA during async update"
                )
        return data

    def get_findings_count(self, obj) -> int:
        return obj.findings_count  # From queryset annotation

    def get_findings_list(self, obj) -> list[int]:
        return obj.open_findings_list()  # Method on Product model
```

**Permission Pattern** (`dojo/api_v2/permissions.py`)

DefectDojo has fine-grained RBAC with roles:
- **Reader**: View-only access
- **Writer**: Create/update entities
- **Maintainer**: Delete non-critical items
- **Owner**: Full control including deletion
- **API_Importer**: Special role for scan imports

Authorization checking:
```python
from dojo.authorization.authorization import user_has_permission
from dojo.authorization.roles_permissions import Permissions

# In view:
if not user_has_permission(request.user, product, Permissions.Product_Edit):
    raise PermissionDenied()

# In queryset:
def get_queryset(self):
    return get_authorized_products(Permissions.Product_View)
```

### Celery Task Patterns

**Task Definition** (`dojo/tasks.py`)

DefectDojo uses Celery for async operations:

```python
from celery.utils.log import get_task_logger
from dojo.celery import app
from dojo.decorators import dojo_async_task

logger = get_task_logger(__name__)

# Simple task
@app.task(bind=True)
def simple_task(self, param):
    """Docstring for task"""
    logger.info(f"Starting task with {param}")
    # Do work
    return result

# Periodic task (configured in celerybeat schedule)
@app.task(bind=True)
def add_alerts(self, runinterval):
    """Runs every N hours/days"""
    now = timezone.now()

    # Example: Find upcoming engagements
    upcoming = Engagement.objects.filter(
        target_start__gt=now + timedelta(days=3),
        target_start__lt=now + timedelta(days=3) + runinterval
    )

    for engagement in upcoming:
        create_notification(
            event='upcoming_engagement',
            title=f'Upcoming: {engagement.name}',
            recipients=[engagement.lead]
        )

# Task with model serialization
@dojo_async_task
@dojo_model_to_id
@dojo_model_from_id(Finding)
def async_dedupe_finding(finding):
    """
    Decorators handle model→ID serialization for Celery
    finding parameter is actual Finding object
    """
    do_dedupe_finding(finding)
```

**Celery Configuration** (celerybeat schedule in `dojo/settings/settings.dist.py`):
```python
CELERY_BEAT_SCHEDULE = {
    'add_alerts': {
        'task': 'dojo.tasks.add_alerts',
        'schedule': timedelta(hours=1),
    },
    'dedupe_delete': {
        'task': 'dojo.tasks.async_dupe_delete',
        'schedule': timedelta(hours=24),
    },
}
```

**Error Handling**:
- Celery tasks should catch exceptions and log them
- Use `logger.exception()` to capture stack traces
- Return status/results for monitoring
- Consider retry logic with `@app.task(bind=True, max_retries=3)`

### Dashboard Patterns

**View Structure** (`dojo/home/views.py` line 23, `dojo/product/views.py`)

DefectDojo dashboards follow a standard pattern:

```python
from django.shortcuts import render
from dojo.authorization.authorization_decorators import user_is_authorized
from dojo.authorization.roles_permissions import Permissions
from dojo.models import Product, Finding, Engagement

@user_is_authorized(Product, Permissions.Product_View, 'pid')
def product_dashboard(request, pid):
    """
    Product dashboard showing findings, engagements, metrics
    URL: /product/{pid}/dashboard/
    """
    product = get_object_or_404(Product, id=pid)

    # Aggregate statistics
    findings = Finding.objects.filter(
        test__engagement__product=product,
        active=True
    )

    stats = {
        'total_findings': findings.count(),
        'critical': findings.filter(severity='Critical').count(),
        'high': findings.filter(severity='High').count(),
        'medium': findings.filter(severity='Medium').count(),
        'low': findings.filter(severity='Low').count(),
    }

    # Time-series data (for charts)
    burndown_data = get_open_findings_burndown(product)

    # Recent activity
    recent_engagements = Engagement.objects.filter(
        product=product
    ).order_by('-target_start')[:5]

    # Template context
    context = {
        'product': product,
        'stats': stats,
        'burndown_data': burndown_data,
        'recent_engagements': recent_engagements,
        'active_tab': 'dashboard',  # For navigation
    }

    return render(request, 'dojo/product_dashboard.html', context)
```

**Template Structure** (Bootstrap 3 + DataTables)

DefectDojo templates use:
- Bootstrap 3.4.1 for layout/components
- jQuery 3.7.1 for interactions
- DataTables for tables
- Chart.js for visualizations

Example template pattern:
```html
{% extends "base.html" %}
{% load display_tags %}

{% block content %}
<div class="row">
    <!-- Summary Cards -->
    <div class="col-md-3">
        <div class="panel panel-danger">
            <div class="panel-heading">
                <h3 class="panel-title">Critical Findings</h3>
            </div>
            <div class="panel-body">
                <h1>{{ stats.critical }}</h1>
            </div>
        </div>
    </div>
    <!-- Repeat for other severities -->
</div>

<div class="row">
    <div class="col-md-12">
        <div class="panel panel-default">
            <div class="panel-heading">
                <h3 class="panel-title">Findings Burndown</h3>
            </div>
            <div class="panel-body">
                <canvas id="burndown-chart"></canvas>
            </div>
        </div>
    </div>
</div>

<script>
// Chart.js initialization
var ctx = document.getElementById('burndown-chart').getContext('2d');
var chart = new Chart(ctx, {
    type: 'line',
    data: {{ burndown_data|safe }},
    options: { /* ... */ }
});
</script>
{% endblock %}
```

**Pre-computed Statistics Pattern**:

For performance, DefectDojo pre-computes expensive statistics:
1. Store in JSONField: `cached_stats = JSONField(default=dict)`
2. Update via Celery task every 6 hours
3. Dashboard reads from cache (instant load)
4. Invalidate cache on finding changes

### Django Admin Patterns

**Simple Registration** (`dojo/admin.py` lines 58-61, 100-101):
```python
from django.contrib import admin
from dojo.models import Product_Type, Product

# Simplest form - use default ModelAdmin
admin.site.register(Product_Type)
admin.site.register(Product)
```

**Custom Admin with Configuration**:
```python
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'prod_type', 'business_criticality', 'lifecycle', 'created')
    list_filter = ('prod_type', 'business_criticality', 'lifecycle')
    search_fields = ('name', 'description')
    readonly_fields = ('created', 'updated', 'tid')

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'prod_type')
        }),
        ('GitHub Integration', {
            'fields': ('github_url', 'github_repo_id', 'last_commit_date'),
            'classes': ('collapse',)  # Collapsible section
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Add annotations for list_display
        return qs.select_related('prod_type')
```

**Inline Admin (for related models)**:
```python
class RepositoryInline(admin.TabularInline):
    model = Repository
    extra = 0  # Don't show empty forms
    fields = ('name', 'github_url', 'tier', 'last_commit_date')
    readonly_fields = ('last_commit_date',)
    can_delete = True

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [RepositoryInline]
```

### Database Migrations

**Creating Migrations** (after model changes):
```bash
# Inside Docker container
docker compose exec uwsgi bash -c "python manage.py makemigrations"

# Creates: dojo/db_migrations/0XXX_auto_YYYYMMDD_HHMM.py
```

**Migration Structure**:
```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('dojo', '0157_previous_migration'),
    ]

    operations = [
        migrations.CreateModel(
            name='Repository',
            fields=[
                ('id', models.AutoField(primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('product', models.ForeignKey(
                    on_delete=models.CASCADE,
                    to='dojo.Product',
                    related_name='repositories'
                )),
            ],
        ),
        migrations.AddField(
            model_name='product',
            name='is_repository_placeholder',
            field=models.BooleanField(default=False),
        ),
    ]
```

**Data Migration** (for moving 47 fields):
```python
def migrate_product_to_repository(apps, schema_editor):
    """
    Copy Product enrichment fields to Repository model
    """
    Product = apps.get_model('dojo', 'Product')
    Repository = apps.get_model('dojo', 'Repository')

    for product in Product.objects.filter(github_url__isnull=False):
        # Create Repository from Product
        repo = Repository.objects.create(
            name=product.name,
            product=product,  # Link back to product
            github_repo_id=product.github_repo_id,
            github_url=product.github_url,
            last_commit_date=product.last_commit_date,
            # ... copy all 47 fields
        )

class Migration(migrations.Migration):
    operations = [
        migrations.RunPython(
            migrate_product_to_repository,
            reverse_code=migrations.RunPython.noop
        ),
    ]
```

### Integration Points for GitHub Alerts

**1. Auto-Triage Engine** (if exists at `dojo/auto_triage/`)
- Automatically assigns severity/priority based on:
  - EPSS score (exploit prediction)
  - Repository tier (from business_criticality)
  - Component criticality
  - Known exploited status
- GitHub alerts will feed into this: "Critical alert in Tier 1 repo + EPSS > 0.9 = Urgent"

**2. EPSS Service Integration** (likely `dojo/models.py` lines 2529-2535)
- Finding model has `epss_score` and `epss_percentile` fields
- Dependabot alerts include EPSS via GraphQL: `advisory.epss { percentage, percentile }`
- Management command to update scores: `python manage.py update_epss_scores`
- For CodeQL/Secrets (no CVE): EPSS fields remain null

**3. Notification System** (`dojo/notifications/helper.py`)
- Triggers: `create_notification(event, title, description, ...)`
- Events for GitHub alerts:
  - `'new_critical_alert'` - Critical GitHub alert opened
  - `'alert_sla_breach'` - Alert exceeds SLA
  - `'alert_fixed'` - Alert auto-closed (mitigated)
- Channels: Email, Slack, webhooks, in-app notifications
- Notification model: `Notifications` (user preferences)

**4. Jira Integration** (`dojo/jira_link/helper.py`)
- Automatic Jira issue creation for findings
- Bidirectional sync: Finding ↔ Jira Issue
- GitHub alerts can auto-create Jira tickets:
  ```python
  if product.jira_project_id and finding.severity in ['Critical', 'High']:
      jira_helper.push_to_jira(finding)
  ```
- Configuration: `GITHUB_PKey` model links GitHub to Product

**5. SLA Tracking** (`dojo/models.py` SLA_Configuration, lines 1003-1118)
- Finding has `sla_start_date` and `sla_expiration_date`
- SLA_Configuration per Product: Critical (7 days), High (14), Medium (30), Low (90)
- Task: `sla_compute_and_notify()` checks for breaches
- GitHub alerts will inherit Product's SLA configuration

### Missing Components That Need Creation

Based on this analysis, here's what doesn't exist yet:

**1. Repository Model** - NEW
- File: `dojo/models.py` (add after Product model)
- 47 fields migrated from Product
- Alert metadata: `last_alert_sync`, `dependabot_alert_count`, `codeql_alert_count`, `secret_scanning_alert_count`
- Statistics cache: `cached_finding_counts = JSONField()`

**2. GitHub Alerts Parsers** - PARTIAL (only Dependabot exists)
- `dojo/tools/github_codeql/parser.py` - NEW
- `dojo/tools/github_secrets/parser.py` - NEW
- Update `dojo/tools/github_vulnerability/parser.py` - Refactor for new data structure

**3. GitHub Alerts Collector** - NEW
- `dojo/github_collector/alerts_collector.py`
- Extend GraphQL client for Dependabot pagination
- REST client for CodeQL and Secrets
- Incremental sync: Only fetch alerts updated since `last_alert_sync`

**4. Repository Admin** - NEW
- `dojo/repository/admin.py` or extend `dojo/admin.py`
- List display: name, product, tier, alert counts
- Inline: Show on Product admin as TabularInline

**5. Repository ViewSet** - NEW
- `dojo/api_v2/views.py` - Add RepositoryViewSet
- `dojo/api_v2/serializers.py` - Add RepositorySerializer
- Endpoints:
  - `/api/v2/repositories/` - CRUD
  - `/api/v2/repositories/{id}/statistics/` - Alert counts
  - `/api/v2/repositories/{id}/sync-alerts/` - Trigger alert sync

**6. Repository Dashboard** - NEW
- `dojo/repository/views.py` - `repository_dashboard(request, rid)`
- Template: `templates/dojo/repository_dashboard.html`
- 3 alert cards (Dependabot, CodeQL, Secrets)
- DataTables for each alert type
- Time-series chart (alerts over 90 days)

**7. Product Dashboard Enhancement** - MODIFY
- Add repository summary section
- Aggregate alerts across repositories
- Top 10 repos by alerts

**8. Product_Type Dashboard** - MODIFY
- Executive summary view
- Product comparison table
- Alert distribution charts

**9. Celery Tasks** - NEW
- `sync_github_alerts_task()` - Hourly alert sync
- `compute_repository_statistics_task()` - 6-hour statistics update
- Add to CELERY_BEAT_SCHEDULE

**10. Management Commands** - NEW
- `sync_github_alerts.py` - Manual alert sync
- `migrate_products_to_repositories.py` - Phase 4 migration wizard

**11. Migration Wizard UI** - NEW (Phase 4)
- `dojo/product/views.py` - `migration_wizard(request)`
- ML clustering suggestions
- Manual repo→product assignment
- Preview changes before applying

### Key Technical Constraints

**1. Database Transaction Safety**
- Always use `with transaction.atomic():` when creating Engagement + Test + Findings
- Rollback if any step fails (e.g., API rate limit during sync)

**2. Authorization Checks**
- Every view must check permissions: `user_has_permission(user, product, Permissions.Product_View)`
- Every API endpoint must filter queryset: `get_authorized_products(Permissions.Product_View)`

**3. Deduplication Requirements**
- `unique_id_from_tool` MUST be stable across imports
- Format: `"github-{alert_type}-{alert_number}"` (alert_number from API)
- DO NOT use timestamps or changing identifiers

**4. Rate Limit Management**
- GitHub GraphQL: 5,000 points/hour
- Track with `rateLimit { cost, remaining, resetAt }`
- Dependabot query: ~10 points per 100 alerts
- CodeQL/Secrets REST: No points cost, but 5,000 requests/hour
- Incremental sync to minimize API calls

**5. Performance Targets**
- Dashboard load: <2 seconds (use pre-computed statistics)
- Alert sync: <5 minutes incremental, <2 hours full
- Statistics computation: Async via Celery, update every 6 hours

**6. Backward Compatibility**
- Existing 2,451 Products must continue working
- Add `is_repository_placeholder` flag to Product
- Gradual migration (Phase 4) over 3-6 months
- No breaking changes to existing APIs

### File Locations for Implementation

**Models:**
- `dojo/models.py` - Add Repository model after Product class (around line 1400)

**GitHub Integration:**
- `dojo/github_collector/alerts_collector.py` - NEW
- `dojo/github_collector/graphql_client.py` - EXTEND (add Dependabot pagination)
- `dojo/github_collector/queries/dependabot_alerts.graphql` - NEW

**Parsers:**
- `dojo/tools/github_codeql/parser.py` - NEW
- `dojo/tools/github_codeql/__init__.py` - NEW
- `dojo/tools/github_secrets/parser.py` - NEW
- `dojo/tools/github_secrets/__init__.py` - NEW

**API:**
- `dojo/api_v2/views.py` - Add RepositoryViewSet (append to file)
- `dojo/api_v2/serializers.py` - Add RepositorySerializer (append to file)
- `dojo/api_v2/permissions.py` - Add UserHasRepositoryPermission (if not covered by Product permissions)

**Views:**
- `dojo/repository/views.py` - NEW (dashboard, list, detail)
- `dojo/repository/urls.py` - NEW
- `dojo/product/views.py` - MODIFY (enhance dashboard)

**Templates:**
- `templates/dojo/repository_dashboard.html` - NEW
- `templates/dojo/product_dashboard.html` - MODIFY (add repository section)

**Tasks:**
- `dojo/tasks.py` - Add `sync_github_alerts_task`, `compute_repository_statistics_task`

**Management Commands:**
- `dojo/management/commands/sync_github_alerts.py` - NEW

**Migrations:**
- `dojo/db_migrations/0XXX_add_repository_model.py` - Generated by makemigrations
- `dojo/db_migrations/0XXX_migrate_product_fields.py` - Custom data migration

**Admin:**
- `dojo/admin.py` - Add RepositoryAdmin class

### Example Implementation References

**Finding Creation Pattern** - See `dojo/tools/github_vulnerability/parser.py` lines 57-139:
```python
finding = Finding(
    title=summary,
    test=test,
    description=desc,
    severity=self._convert_security(vuln.get('severity')),
    static_finding=True,
    unique_id_from_tool=alert.get('id'),  # CRITICAL
    cve=identifier if identifier.startswith('CVE-') else None,
    cwe=int(cwe_id) if cwe_id.isdigit() else None,
    file_path=alert.get('vulnerableManifestPath'),
    component_name=pkg.get('name'),
    component_version=req[2:] if req.startswith('= ') else req,
    active=alert.get('state') not in {'FIXED', 'DISMISSED'},
    is_mitigated=alert.get('state') in {'FIXED', 'DISMISSED'},
)
```

**GraphQL Incremental Sync** - See `dojo/github_collector/collector.py` lines 116-132:
```python
if incremental:
    most_recent = Product.objects.filter(
        github_url__isnull=False
    ).order_by('-updated').first()

    if most_recent and most_recent.updated:
        updated_since = most_recent.updated
        logger.info(f"Incremental: fetching repos updated after {updated_since}")

repos_data = self.graphql_client.get_organization_repositories(
    org=self.github_org,
    updated_since=updated_since
)
```

**Celery Periodic Task** - See `dojo/tasks.py` lines 31-75:
```python
@app.task(bind=True)
def add_alerts(self, runinterval):
    now = timezone.now()

    upcoming_engagements = Engagement.objects.filter(
        target_start__gt=now + timedelta(days=3),
        target_start__lt=now + timedelta(days=3) + runinterval
    ).order_by("target_start")

    for engagement in upcoming_engagements:
        create_notification(
            event="upcoming_engagement",
            title=f"Upcoming engagement: {engagement.name}",
            engagement=engagement,
            recipients=[engagement.lead],
            url=reverse("view_engagement", args=(engagement.id,))
        )
```

### Summary of What Exists vs. What's Needed

**✅ EXISTING:**
- Product/Product_Type/Engagement/Test/Finding models
- GitHub GraphQL client with incremental sync
- 36 binary signal detection system
- Tier classification logic
- Dependabot parser (github_vulnerability)
- REST API ViewSet patterns
- Celery task infrastructure
- Dashboard template patterns
- Django admin patterns
- Deduplication via unique_id_from_tool
- Authorization/RBAC system

**🆕 NEEDS CREATION:**
- Repository model (47 fields + alert metadata)
- CodeQL parser (github_codeql)
- Secrets parser (github_secrets)
- GitHub alerts collector (REST for CodeQL/Secrets)
- Repository ViewSet/Serializer
- Repository admin interface
- Repository dashboard view + template
- Alert sync Celery tasks
- Migration wizard (Phase 4)
- Database migrations for new model

**🔧 NEEDS MODIFICATION:**
- Product model (remove 47 fields, add is_repository_placeholder flag)
- Product dashboard (add repository section)
- Product_Type dashboard (add aggregate views)
- GraphQL client (add Dependabot alert pagination)

This context manifest provides the complete foundation for implementing the GitHub alerts hierarchy without requiring additional research during implementation.

## User Notes

**Key Requirements**:
- Map GitHub security alerts (CodeQL, Dependabot, Secrets) to repositories
- Group repositories into Products (applications)
- Assign Products to Business Units (Product_Type)
- Multi-level dashboards with drill-down capability
- Maintain backward compatibility with existing 2,451 Products

**GitHub API Permissions Needed**:
- `repo:read` - Repository metadata
- `security_events:read` - Vulnerability alerts, code scanning, secret scanning
- `admin:org:read` - Organization members (for contributor analysis)

**Development Guidelines**:
- **MUST use Context7 MCP** for API/library/framework verification before implementation
  - Verify GitHub GraphQL schema fields before querying
  - Confirm Django ORM patterns and best practices
  - Validate REST API endpoint design against Django REST Framework docs
  - Check scikit-learn clustering API for ML grouping
  - Confirm any third-party library usage (requests, pandas, etc.)
- Use `mcp__context7__resolve-library-id` then `mcp__context7__get-library-docs`
- No implementation without API documentation verification

**Performance Targets**:
- Dashboard load: <2 seconds
- Alert sync: <5 minutes incremental, <2 hours full sync
- Rate limit usage: <80% of 5,000 points/hour (GraphQL + REST)

## Work Log
<!-- Updated as work progresses -->
- [2025-01-13] Task created with 6-phase architecture, ultrathink analysis completed
