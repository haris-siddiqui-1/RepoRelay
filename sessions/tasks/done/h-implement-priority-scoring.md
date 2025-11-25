---
name: h-implement-priority-scoring
branch: feature/priority-scoring
status: completed
created: 2025-11-25
depends_on:
  - h-research-vulnerability-prioritization-strategy
submodules:
  - RepoRelay
---

# Implement Priority Scoring (Phase 1: Foundation)

## Problem/Goal

Implement the priority scoring system defined in the vulnerability prioritization strategy. This is the foundation phase that enables all subsequent triage features.

**Reference**: `sessions/docs/vulnerability-prioritization-strategy.md` - Part 2 & Part 4.1

## Success Criteria
- [x] Add priority_score, priority_bucket, priority_calculated_at fields to Finding model
- [x] Create migration for new fields with appropriate indexes
- [x] Implement PriorityScorer service class in `dojo/finding/priority_scorer.py`
- [x] Create management command `calculate_priority_scores` for batch scoring
- [x] Add Celery task for incremental scoring on finding create/update
- [x] Unit tests for scoring algorithm with edge cases
- [x] Backfill existing findings with priority scores

## Context Manifest

### How the Finding Model and Data Hierarchy Currently Work

DefectDojo uses a monolithic `dojo/models.py` file (238KB) containing 40+ models with a clear entity hierarchy for security findings. Understanding this data flow is CRITICAL because the priority scoring system must integrate into this exact architecture.

**The Complete Data Hierarchy:**

```
Product_Type (organization level)
  └─> Product (application/service - lines 1120-1350 in models.py)
       ├─> Engagement (time-bound testing activity - lines 2440-2560)
       │    └─> Test (specific scan instance - lines 3051-3150)
       │         └─> Finding (individual vulnerability - lines 3280-3690)
       └─> Repository (1:many relationship - lines 1623-1907)
            └─> GitHubAlert (raw security alerts - lines 1909-2050)
                 └─> Finding (converted via findings_converter.py)
```

**Finding Model Key Fields for Priority Scoring (lines 3280-3690):**

The Finding model has ~100 fields. The priority scoring implementation will ADD three new fields and CONSUME these existing fields:

**Severity & Scoring Data:**
- `severity` (CharField, line 3350): Values are "Critical", "High", "Medium", "Low", "Info" - this is the BASE for priority calculation
- `numerical_severity` (CharField, line 3481): Auto-computed values S0-S4 for sorting
- `cvssv3_score`, `cvssv4_score` (FloatField, lines 3328, 3339): CVSS numerical scores (not used in priority formula but available)

**Exploitation Intelligence (KEV/EPSS - migration 0230):**
- `epss_score` (FloatField, line 3305): Probability of exploitation in next 30 days (0.0-1.0)
- `epss_percentile` (FloatField, line 3309): Percentile ranking among all CVEs
- `known_exploited` (BooleanField, line 3313): KEV catalog flag - CRITICAL MODIFIER (+150 points)
- `ransomware_used` (BooleanField, line 3316): Ransomware campaign association (+100 points)
- `kev_date` (DateField, line 3319): Date added to KEV catalog

**Remediation Status:**
- `fix_available` (BooleanField, line 3359): Whether patch exists (+30 points if True, -20 if False)
- `is_mitigated` (BooleanField, line 3451): Whether fixed (exclude from priority queue)
- `mitigated` (DateTimeField, line 3457): Timestamp when fixed
- `active` (BooleanField, line 3390): Finding is open (only score active findings)

**SLA Fields:**
- `sla_start_date` (DateField, line 3287): When SLA clock starts
- `sla_expiration_date` (DateField, line 3292): When SLA expires (+50 points if breached)
- Calculated via `dojo/sla_config/helpers.py` with complex business logic

**Triage Status (Auto-Triage Integration - lines 3536-3555):**
- `auto_triage_decision` (CharField, line 3543): Values: PENDING, DISMISS, ESCALATE, ACCEPT_RISK
- `auto_triage_reason` (TextField, line 3549): Explanation text
- `auto_triaged_at` (DateTimeField, line 3552): Timestamp of auto-triage
- These fields are SET by `dojo/auto_triage/engine.py` and will INFORM priority scoring (but not BE the priority score)

**Deduplication Fields:**
- `hash_code` (CharField, line 3510): Computed hash for dedup (64 chars max)
- `unique_id_from_tool` (CharField, line 3583): Tool-provided unique ID (500 chars max)
- `duplicate` (BooleanField, line 3402): Is this a duplicate? (exclude from priority queue)
- `duplicate_finding` (ForeignKey, line 3404): Link to original if duplicate

**Relationships (Navigation to Repository/Product):**
- `test` (ForeignKey to Test, line 3385): REQUIRED - every finding belongs to a test
- Test model (lines 3051-3150): Contains `engagement` ForeignKey
- Engagement model (lines 2440-2560): Contains `product` ForeignKey
- Product model (lines 1120-1350): Contains `business_criticality` field

**CRITICAL NAVIGATION PATH:**
```python
# To get repository tier from a finding:
finding.test.engagement.product  # -> Product instance
# Product has business_criticality: "very high", "high", "medium", "low", "none"

# To get Repository tier (if finding came from GitHub alerts):
# Check if finding has github_alert relationship
if hasattr(finding, 'githubalert'):
    repository = finding.githubalert.repository  # -> Repository instance
    tier = repository.tier  # "tier1", "tier2", "tier3", "tier4", "archived"
```

**Database Indexes (lines 3653-3669):**
The Finding model already has strategic indexes:
- Compound: `["test", "active", "verified"]`
- Compound: `["test", "unique_id_from_tool", "duplicate"]`
- Single: `["cve"]`, `["epss_score"]`, `["known_exploited"]`, `["ransomware_used"]`, `["kev_date"]`

**Priority scoring will ADD these indexes:**
- `priority_score` (single index for sorting)
- `priority_bucket` (single index for filtering)

### Repository Model - Tier Classification Source (lines 1623-1907)

The Repository model is the PRIMARY source of tier classification for GitHub-sourced findings. It has 47 enrichment fields including:

**Tier Field (line 1876):**
- `tier` (CharField): Values are "tier1", "tier2", "tier3", "tier4", "archived"
- Computed by `dojo/github_collector/tier_classifier.py` based on 36 binary signals
- Updated during repository sync via `sync_github_repositories` management command

**Activity Signals (used in tier calculation AND priority modifiers):**
- `days_since_last_commit` (IntegerField, line 1678): Dormant repo detection (>180 days = -40 points)
- `has_environments` (BooleanField, line 1780): GitHub environments configured (+25 points if True)
- `has_releases` (BooleanField, line 1785): Production readiness signal (+25 points if True)
- `active_webhooks_count` (IntegerField, line 1708): Integration health (+15 points if >0)

**Tier Weight Mapping (from strategy doc Part 2.2):**
- tier1 (very high): 5.0x multiplier - Critical production systems
- tier2 (high): 3.5x multiplier - Important production systems
- tier3 (medium): 2.0x multiplier - Development/staging systems
- tier4 (low): 1.0x multiplier - Testing/experimental systems
- archived (none): 0.2x multiplier - Inactive/deprecated systems

**CRITICAL: Product.business_criticality vs Repository.tier**

DefectDojo has TWO tier systems that must be reconciled:

1. **Product.business_criticality** (line 1212 in models.py):
   - Values: "very high", "high", "medium", "low", "very low", "none"
   - Set MANUALLY by Product Managers
   - Used by existing auto-triage rules (see `dojo/auto_triage/rules.py` lines 57-84)

2. **Repository.tier** (line 1876):
   - Values: "tier1", "tier2", "tier3", "tier4", "archived"
   - Computed AUTOMATICALLY from 36 binary signals
   - More granular and data-driven

**Priority Scorer MUST handle both:**
```python
def _get_effective_tier(self, finding, repository=None):
    # Priority: Repository tier (if GitHub alert) > Product criticality (fallback)
    if repository and repository.tier:
        return self._map_repo_tier_to_weight(repository.tier)

    product = finding.test.engagement.product
    if product.business_criticality:
        return self._map_product_criticality_to_weight(product.business_criticality)

    return 1.0  # Default tier4 weight
```

### Finding Lifecycle and Signal Management

**Finding Creation Flow (where priority scoring will hook in):**

1. **Scanner Import** (`dojo/importers/default_importer.py`):
   - Parser reads scan file (211 tool types supported)
   - Creates Finding objects with `test` relationship
   - Calls `finding.save()` which triggers pre_save signal

2. **Pre-Save Signal Hook** (`dojo/finding/helper.py` lines 60-96):
   - `pre_save_changed` signal connected to Finding model
   - Monitors fields: "id", "active", "verified", "false_p", "is_mitigated", "out_of_scope", "risk_accepted"
   - Calls `update_finding_status()` function (line 99)
   - **THIS IS WHERE PRIORITY SCORING WILL HOOK IN**

3. **Post-Save Processing**:
   - Deduplication via `do_dedupe_finding()` in `dojo/utils.py`
   - Auto-triage evaluation via `dojo/auto_triage/engine.py`
   - **Priority calculation via NEW `calculate_finding_priority()` Celery task**

**CRITICAL: Celery Task Pattern**

DefectDojo uses a custom decorator pattern for Celery tasks (see `dojo/decorators.py`):

```python
from dojo.decorators import dojo_async_task, dojo_model_from_id, dojo_model_to_id

@dojo_async_task
@dojo_model_to_id
def calculate_finding_priority(finding_id):
    """Calculate priority score for a single finding (async)."""
    from dojo.models import Finding
    from dojo.finding.priority_scorer import PriorityScorer

    finding = Finding.objects.select_related(
        'test__engagement__product'
    ).prefetch_related(
        'test__engagement__product__repositories'
    ).get(id=finding_id)

    scorer = PriorityScorer()
    score = scorer.calculate(finding)
    bucket = scorer.get_bucket(score)

    finding.priority_score = score
    finding.priority_bucket = bucket
    finding.priority_calculated_at = timezone.now()
    finding.save(update_fields=['priority_score', 'priority_bucket', 'priority_calculated_at'])
```

**Why NOT use @app.task or @shared_task:**
- DefectDojo's Celery setup uses `dojo/celery.py` with custom app instance
- The `@dojo_async_task` decorator handles:
  - Database connection pooling
  - Transaction management
  - Error logging to DefectDojo's alert system
  - Retry logic with exponential backoff
- See `dojo/tasks.py` lines 1-100 for existing task patterns

### Auto-Triage Integration Points

The auto-triage system (`dojo/auto_triage/`) is CLOSELY related but SEPARATE from priority scoring:

**Auto-Triage Rules** (`dojo/auto_triage/rules.py`):
- 16 predefined rules that evaluate findings
- Rules use helper functions like `is_tier1_product()`, `has_high_epss()` (lines 37-100)
- Returns decisions: DISMISS, ESCALATE, ACCEPT_RISK, PENDING
- Confidence scores: 50-95

**Auto-Triage Engine** (`dojo/auto_triage/engine.py`):
- Evaluates all rules in order, first match wins
- Sets `finding.auto_triage_decision` and `finding.auto_triage_reason`
- Does NOT set priority_score (that's our job)

**How They Work Together:**

```
Finding Created
  ├─> Auto-Triage Engine evaluates rules
  │    └─> Sets auto_triage_decision (DISMISS, ESCALATE, etc.)
  │
  └─> Priority Scorer calculates numeric score
       ├─> Reads auto_triage_decision as INPUT (optional modifier)
       ├─> Computes priority_score based on tier + severity + modifiers
       └─> Sets priority_bucket (P0-P4)

Triage Dashboard displays:
  - priority_score (sortable column)
  - priority_bucket (filter option)
  - auto_triage_decision (suggested action)
```

**CRITICAL: Priority Score is Independent of Auto-Triage**

The priority score should be calculated REGARDLESS of auto-triage decision. A finding can be:
- P0 priority (score 750) AND auto-dismissed (because it's in archived repo)
- P3 priority (score 100) AND auto-escalated (because it meets a specific rule)

The priority score is for RANKING/SORTING. The auto-triage decision is for FILTERING/ACTIONS.

### Management Command Pattern (Batch Processing)

For the `calculate_priority_scores` management command, follow the pattern from `sync_github_alerts.py`:

**Command Structure** (`dojo/management/commands/sync_github_alerts.py` lines 1-100):

```python
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Calculate priority scores for findings'

    def add_arguments(self, parser):
        parser.add_argument('--test-id', type=int, help='Score findings for specific test')
        parser.add_argument('--limit', type=int, help='Maximum findings to process')
        parser.add_argument('--force', action='store_true', help='Recalculate even if already scored')
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')

    def handle(self, *args, **options):
        # Validate options
        # Build queryset with filters
        # Process in batches
        # Update progress every 100 findings
```

**Key Patterns:**
- Use Django's `BaseCommand` class (provides --verbosity, --help automatically)
- Add `--dry-run` for testing
- Add `--force` to override "already processed" checks
- Log progress every N records (use `logger.info()` not `self.stdout.write()` for production)
- Use `select_related()` and `prefetch_related()` for query optimization

**Query Optimization Pattern:**

```python
findings = Finding.objects.filter(
    active=True,
    duplicate=False,
    is_mitigated=False
).select_related(
    'test__engagement__product'
).prefetch_related(
    'test__engagement__product__repositories'
)

# Process in batches to avoid memory issues
batch_size = 1000
for i in range(0, findings.count(), batch_size):
    batch = findings[i:i+batch_size]
    for finding in batch:
        # Calculate priority
        pass
```

### Database Migration Strategy

**Migration Pattern** (based on migration 0230 - KEV fields):

```python
# dojo/db_migrations/0259_finding_priority_fields.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('dojo', '0258_repository_active_webhooks_count_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='finding',
            name='priority_score',
            field=models.IntegerField(
                default=0,
                db_index=True,
                verbose_name='Priority Score',
                help_text='Computed priority score combining tier, severity, and modifiers'
            ),
        ),
        migrations.AddField(
            model_name='finding',
            name='priority_bucket',
            field=models.CharField(
                max_length=10,
                choices=[
                    ('P0', 'Critical'),
                    ('P1', 'High'),
                    ('P2', 'Medium'),
                    ('P3', 'Low'),
                    ('P4', 'Minimal')
                ],
                default='P3',
                db_index=True,
                verbose_name='Priority Bucket'
            ),
        ),
        migrations.AddField(
            model_name='finding',
            name='priority_calculated_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                verbose_name='Priority Calculated At'
            ),
        ),
        migrations.AddIndex(
            model_name='finding',
            index=models.Index(fields=['priority_score'], name='dojo_finding_priority_score_idx'),
        ),
        migrations.AddIndex(
            model_name='finding',
            index=models.Index(fields=['priority_bucket'], name='dojo_finding_priority_bucket_idx'),
        ),
    ]
```

**CRITICAL Migration Considerations:**

1. **Default Value = 0**: All existing findings will get priority_score=0, priority_bucket='P3'
2. **Backfill Required**: Must run `calculate_priority_scores --force` after migration
3. **Index Creation**: PostgreSQL creates indexes WITH CONCURRENTLY to avoid table locks (Django handles this)
4. **No Data Migration**: Separate data backfill from schema migration

**Backfill Strategy:**

```bash
# After migration is applied:
docker compose exec uwsgi bash -c "python manage.py migrate"

# Backfill all findings (async via Celery):
docker compose exec uwsgi bash -c "python manage.py calculate_priority_scores --async"

# OR bulk update (synchronous, shows progress):
docker compose exec uwsgi bash -c "python manage.py calculate_priority_scores --limit 10000"
```

### Technical Reference Details

#### File Locations

**MUST CREATE:**
- `dojo/finding/priority_scorer.py` - PriorityScorer service class (200-300 lines)
- `dojo/management/commands/calculate_priority_scores.py` - Batch scoring command (150-200 lines)
- `dojo/db_migrations/0259_finding_priority_fields.py` - Database migration (50 lines)

**MUST MODIFY:**
- `dojo/models.py` lines 3280-3690 (Finding model) - Add 3 fields
- `dojo/finding/helper.py` lines 99-150 (update_finding_status) - Hook in priority calculation trigger
- `dojo/admin.py` - Register priority fields in Finding admin (if not auto-discovered)

**WILL READ (no modifications):**
- `dojo/models.py` lines 1623-1907 (Repository model) - Tier source
- `dojo/models.py` lines 1120-1350 (Product model) - Business criticality source
- `dojo/auto_triage/rules.py` - Helper functions for tier detection
- `dojo/github_collector/tier_classifier.py` - Tier calculation logic (reference only)

#### Component Interfaces & Signatures

**PriorityScorer Class:**

```python
class PriorityScorer:
    """Calculate priority scores for findings based on tier, severity, and modifiers."""

    TIER_WEIGHTS = {
        'tier1': 5.0, 'very high': 5.0,
        'tier2': 3.5, 'high': 3.5,
        'tier3': 2.0, 'medium': 2.0,
        'tier4': 1.0, 'low': 1.0,
        'archived': 0.2, 'none': 0.2,
    }

    SEVERITY_SCORES = {
        'Critical': 100, 'High': 75, 'Medium': 50, 'Low': 25, 'Info': 10,
    }

    PRIORITY_BUCKETS = [
        (500, 'P0'),  # >=500
        (300, 'P1'),  # 300-499
        (150, 'P2'),  # 150-299
        (50, 'P3'),   # 50-149
        (0, 'P4'),    # <50
    ]

    def calculate(self, finding: Finding, repository: Optional[Repository] = None) -> int:
        """
        Calculate priority score for a finding.

        Args:
            finding: Finding instance (must have test.engagement.product prefetched)
            repository: Optional Repository instance (if finding from GitHub alert)

        Returns:
            Integer priority score (0-1000+)
        """
        pass

    def get_bucket(self, score: int) -> str:
        """Map score to priority bucket (P0-P4)."""
        pass

    def _get_effective_tier(self, finding: Finding, repository: Optional[Repository]) -> str:
        """Resolve tier from repository or product business_criticality."""
        pass

    def _calculate_modifiers(self, finding: Finding, repository: Optional[Repository]) -> int:
        """Calculate modifier points (+/-) from KEV, EPSS, SLA, etc."""
        pass
```

**Celery Task Signature:**

```python
@dojo_async_task
@dojo_model_to_id
def calculate_finding_priority(finding_id: int) -> None:
    """
    Async task to calculate priority score for a single finding.

    Args:
        finding_id: Primary key of Finding to score

    Side Effects:
        Updates finding.priority_score, finding.priority_bucket, finding.priority_calculated_at
    """
    pass
```

**Management Command Interface:**

```bash
# Calculate priority for all active findings
python manage.py calculate_priority_scores

# Force recalculation even if already scored
python manage.py calculate_priority_scores --force

# Score specific test's findings only
python manage.py calculate_priority_scores --test-id 123

# Limit batch size for testing
python manage.py calculate_priority_scores --limit 1000

# Preview changes without saving
python manage.py calculate_priority_scores --dry-run

# Async mode (queue Celery tasks instead of blocking)
python manage.py calculate_priority_scores --async
```

#### Data Structures

**Priority Score Calculation Logic:**

```python
# Base score = tier_weight × severity_score
base_score = TIER_WEIGHTS[effective_tier] * SEVERITY_SCORES[finding.severity]

# Positive modifiers
if finding.known_exploited:
    base_score += 150
if finding.ransomware_used:
    base_score += 100
if finding.epss_score >= 0.7:
    base_score += 75
elif finding.epss_score >= 0.3:
    base_score += 40
if finding.fix_available is True:
    base_score += 30
if repository and (repository.has_environments or repository.has_releases):
    base_score += 25
if repository and repository.active_webhooks_count > 0:
    base_score += 15
if finding.sla_expiration_date and finding.sla_expiration_date < timezone.now().date():
    base_score += 50

# Negative modifiers
if finding.epss_score and finding.epss_score < 0.02:
    base_score -= 50
elif finding.epss_score and finding.epss_score < 0.1:
    base_score -= 25
if finding.fix_available is False:
    base_score -= 20
if repository and repository.days_since_last_commit and repository.days_since_last_commit > 180:
    base_score -= 40
if repository and not (repository.has_environments or repository.has_releases):
    base_score -= 30

# Floor at 0
final_score = max(0, int(base_score))
```

**Example Calculations:**

| Scenario | Tier | Severity | Modifiers | Score | Bucket |
|----------|------|----------|-----------|-------|--------|
| KEV in production firmware | tier1 (5.0) | Critical (100) | KEV +150, EPSS 0.85 +75, has_environments +25 | 750 | P0 |
| High CVE in active service | tier2 (3.5) | High (75) | EPSS 0.35 +40, fix_available +30 | 333 | P1 |
| Medium CVE in dev repo | tier3 (2.0) | Medium (50) | EPSS 0.15, no prod -30 | 70 | P3 |
| Low CVE in archived repo | archived (0.2) | Low (25) | EPSS 0.01 -50, dormant -40, no prod -30 | 0 | P4 |

#### Configuration Requirements

**Environment Variables (no new ones required):**
- Uses existing `DD_CELERY_BROKER_URL` for async tasks
- Uses existing `DD_DATABASE_URL` for PostgreSQL

**Django Settings (no changes required):**
- Priority scoring uses existing Finding model
- Celery tasks use existing `dojo/celery.py` app instance
- No new middleware or apps needed

**Celery Configuration:**
- Task will be auto-discovered from `dojo/finding/` via Celery's autodiscover pattern
- Default retry: 3 attempts with exponential backoff (inherited from `@dojo_async_task`)
- Task timeout: 300 seconds (5 minutes) for batch operations

#### Error Handling Patterns

**Common Edge Cases:**

1. **Finding without test relationship:**
   ```python
   if not hasattr(finding, 'test') or finding.test is None:
       logger.warning(f"Finding {finding.id} has no test, defaulting to tier4")
       return 1.0  # tier4 weight
   ```

2. **Repository not found for GitHub alert:**
   ```python
   repository = None
   if hasattr(finding, 'githubalert') and finding.githubalert:
       repository = finding.githubalert.repository
   ```

3. **Missing EPSS data (null values):**
   ```python
   if finding.epss_score is None:
       # Skip EPSS modifiers entirely
       pass
   elif finding.epss_score >= 0.7:
       modifiers += 75
   ```

4. **SLA date comparison with None:**
   ```python
   if finding.sla_expiration_date:
       from django.utils import timezone
       if finding.sla_expiration_date < timezone.now().date():
           modifiers += 50
   ```

### Environmental Requirements

**Django Version:** 5.1.14 (line 1 in CLAUDE.md)
**Python Version:** 3.13
**Database:** PostgreSQL (exclusive - no MySQL/SQLite)
**Async Worker:** Celery 5.5.3 with Valkey/Redis broker

**Docker Services Required:**
- `uwsgi` - Django application server (for management command execution)
- `celeryworker` - Background task processing (for async priority calculation)
- `postgres` - Database (for schema migration)
- `valkey` - Message broker (for Celery task queue)

**Running Commands:**

```bash
# Generate migration
docker compose exec uwsgi bash -c "python manage.py makemigrations"

# Apply migration
docker compose exec uwsgi bash -c "python manage.py migrate"

# Backfill priority scores
docker compose exec uwsgi bash -c "python manage.py calculate_priority_scores"

# Check Celery worker status
docker compose logs celeryworker --tail 50

# Test async task queuing
docker compose exec uwsgi bash -c "python manage.py shell"
>>> from dojo.finding.priority_scorer import calculate_finding_priority
>>> calculate_finding_priority.delay(finding_id=123)
```

### Performance Considerations

**Query Optimization:**

Finding model has 3.6 million records in large deployments. Priority scoring MUST be efficient:

```python
# GOOD: Prefetch related data in single query
findings = Finding.objects.filter(active=True).select_related(
    'test__engagement__product'
).prefetch_related(
    'test__engagement__product__repositories'
)

# BAD: N+1 query problem (1 query per finding)
for finding in Finding.objects.filter(active=True):
    product = finding.test.engagement.product  # NEW QUERY EACH TIME
```

**Batch Processing:**

Management command should process in batches:

```python
batch_size = 1000
total = findings.count()
for i in range(0, total, batch_size):
    batch = findings[i:i+batch_size]
    for finding in batch:
        scorer.calculate(finding)
    logger.info(f"Processed {min(i+batch_size, total)}/{total} findings")
```

**Async vs Sync Trade-offs:**

- **Sync Mode (default)**: Blocking, shows progress, good for one-time backfill
- **Async Mode (--async flag)**: Queues Celery tasks, non-blocking, good for continuous updates
- **Recommendation**: Use sync for initial backfill, async for ongoing updates

### Testing Strategy

**Unit Tests Required:**

```python
# unittests/finding/test_priority_scorer.py
class TestPriorityScorer(TestCase):
    def test_tier1_critical_kev(self):
        """P0 - KEV in tier1 repo with critical severity"""
        # Score should be 750+
        pass

    def test_tier4_low_archived(self):
        """P4 - Low severity in archived repo"""
        # Score should be near 0
        pass

    def test_missing_epss_data(self):
        """Handle None EPSS gracefully"""
        pass

    def test_repository_tier_override(self):
        """Repository tier takes precedence over product criticality"""
        pass
```

**Integration Tests:**

```bash
# Create test finding with known values
# Calculate priority
# Assert score matches expected formula
./run-unittest.sh --test-case unittests.finding.test_priority_scorer.TestPriorityScorer -v3
```

### Prescribed Files to Read During Implementation

**MUST READ BEFORE CODING:**
1. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/models.py` lines 3280-3690 (Finding model complete)
2. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/models.py` lines 1623-1907 (Repository model complete)
3. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/finding/helper.py` lines 1-150 (Signal hooks)
4. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/auto_triage/rules.py` lines 1-100 (Helper functions)
5. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/management/commands/sync_github_alerts.py` (Command pattern)
6. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/db_migrations/0230_add_finding_kev_fields.py` (Migration pattern)
7. `/Users/1haris.sid/defectdojo/RepoRelay/sessions/docs/vulnerability-prioritization-strategy.md` (Complete strategy)

**REFERENCE DURING IMPLEMENTATION:**
8. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/decorators.py` (Celery task decorators)
9. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/tasks.py` lines 1-100 (Celery task patterns)
10. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/github_collector/tier_classifier.py` (Tier logic reference)

### Implementation Gotchas

**CRITICAL ERRORS TO AVOID:**

1. **DO NOT modify Finding.save() method directly**
   - Use pre_save signal hook instead (`dojo/finding/helper.py` line 82)
   - Modifying save() causes infinite loops and breaks deduplication

2. **DO NOT calculate priority in API serializer**
   - Priority is a STORED field, not a computed property
   - Calculate on finding create/update, not on every API read

3. **DO NOT use @app.task or @shared_task decorators**
   - Use `@dojo_async_task` from `dojo.decorators` (line 14 in helper.py)
   - DefectDojo's custom decorator handles transactions correctly

4. **DO NOT forget to handle None values**
   - EPSS can be None (not all CVEs have EPSS scores)
   - Repository can be None (not all findings from GitHub)
   - SLA dates can be None (not all products have SLA)

5. **DO NOT score duplicate or mitigated findings**
   - Filter: `active=True, duplicate=False, is_mitigated=False`
   - Scoring closed findings wastes resources

6. **DO NOT use timezone-naive datetime comparisons**
   - Always use `timezone.now()` not `datetime.now()`
   - Django settings: `USE_TZ = True`

**Data Integrity Checks:**

```python
# Before scoring, validate:
assert finding.test is not None, f"Finding {finding.id} has no test"
assert finding.severity in ['Critical', 'High', 'Medium', 'Low', 'Info'], f"Invalid severity: {finding.severity}"

# After scoring, validate:
assert 0 <= priority_score <= 1500, f"Score out of range: {priority_score}"
assert priority_bucket in ['P0', 'P1', 'P2', 'P3', 'P4'], f"Invalid bucket: {priority_bucket}"
```

### Success Verification Checklist

After implementation, verify:

- [ ] Migration creates 3 fields with correct indexes
- [ ] PriorityScorer.calculate() returns expected scores for test cases
- [ ] Management command processes findings without errors
- [ ] Celery task appears in worker logs
- [ ] Finding admin shows priority_score and priority_bucket fields
- [ ] Existing tests still pass (no regression)
- [ ] New unit tests pass (edge cases covered)
- [ ] Backfill completes on test dataset (1000+ findings)
- [ ] Database query count is optimized (no N+1 queries)
- [ ] Priority scores update when finding severity changes

## Technical Specification

### Data Model Changes (Finding)
```python
priority_score = models.IntegerField(default=0, db_index=True)
priority_bucket = models.CharField(max_length=10, choices=[...], default='P3', db_index=True)
priority_calculated_at = models.DateTimeField(null=True, blank=True)
```

### Priority Formula
```
PriorityScore = (TierWeight × SeverityScore) + Modifiers
```

### Tier Weights
- Tier 1: 5.0, Tier 2: 3.5, Tier 3: 2.0, Tier 4: 1.0, Archived: 0.2

### Severity Scores
- Critical: 100, High: 75, Medium: 50, Low: 25, Info: 10

### Modifiers
- KEV: +150, Ransomware: +100, High EPSS: +75, SLA Breach: +50
- Very Low EPSS: -50, Dormant Repo: -40, No Production: -30

### Priority Buckets
- P0: >=500, P1: 300-499, P2: 150-299, P3: 50-149, P4: <50

## User Notes

This task implements Phase 1 of the vulnerability prioritization strategy. It provides the foundation for the triage workflow and dashboard.

## Work Log

### 2025-11-24

#### Completed
- Added priority_score, priority_bucket, priority_calculated_at fields to Finding model (dojo/models.py lines 3557-3578)
- Created database migration 0259_finding_priority_fields.py with appropriate indexes
- Implemented PriorityScorer service class in dojo/finding/priority_scorer.py (~350 lines)
  - calculate() method: Computes priority score using tier weight × severity score + modifiers
  - get_bucket() method: Maps scores to P0-P4 buckets
  - calculate_and_get_bucket() method: Combined calculation and bucketing
  - get_repository_for_finding() helper: Resolves repository from finding relationships
- Created calculate_priority_scores management command (~200 lines)
  - Options: --force, --test-id, --product-id, --limit, --dry-run, --async, --batch-size
  - Batch processing with progress reporting every 100 findings
  - Supports both synchronous and asynchronous modes
- Added calculate_finding_priority_task Celery task for incremental scoring
  - Decorated with @dojo_async_task for proper transaction handling
  - Skips inactive, duplicate, or mitigated findings
  - Updates only if score/bucket changed to avoid unnecessary saves
- Added post_save signal hook in dojo/finding/helper.py (lines 99-123)
  - Triggers async priority calculation after finding save
  - Graceful error handling prevents save failures
- Created comprehensive unit tests in unittests/test_priority_scorer.py (~450 lines)
  - 25+ test cases covering base scores, modifiers, tier fallback, edge cases
  - Real-world scenarios: KEV in tier1, high EPSS, SLA breaches, dormant repos
- Applied migration successfully
- Backfilled 1 existing finding: High severity → score=75 → P3 bucket

#### Decisions
- Used post_save signal instead of pre_save for async task triggering (finding needs ID before async processing)
- Repository tier takes precedence over Product business_criticality when both available
- Celery task skips findings that are inactive/duplicate/mitigated to avoid wasted computation
- Management command defaults to synchronous mode for one-time backfills, --async flag for ongoing updates
- Unit tests placed in top-level unittests/ directory following existing pattern (no unittests/finding/ subdirectory)

#### Discovered
- Finding model already has indexed fields for severity, EPSS, KEV (migration 0230)
- Existing pre_save_changed signal pattern in helper.py for status field changes
- DojoTestCase base class provides fixtures and helper methods for test setup
- Django's @receiver decorator preferred over manual signal.connect() calls for clarity

#### Next Steps
- Phase 2: Implement triage workflow UI (h-implement-triage-workflow)
- Phase 3: Build triage dashboard with priority filters (h-implement-triage-dashboard)
- Phase 4: Add consumption signals collection (h-implement-consumption-signals)
- Phase 5: Implement priority-based notification routing (h-implement-notification-routing)

### 2025-11-25
- Task created from strategy document
