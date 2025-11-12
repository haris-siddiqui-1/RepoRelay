# Enterprise Context Enrichment - Deployment Guide

This guide walks through deploying the Enterprise Context Enrichment fork of DefectDojo.

## Prerequisites

- DefectDojo v2.52.1+ installed and running
- Docker environment (for generating migrations)
- GitHub organization with repositories to sync
- GitHub Personal Access Token with `repo` and `read:org` permissions
- PostgreSQL database (DefectDojo requirement)

## Implementation Status

✅ **Backend Complete** (~4,500 lines):
- Data model extensions (50 new fields)
- GitHub collector service (4 modules)
- EPSS service integration (3 modules)
- Auto-triage engine (2 modules)
- API extensions (4 endpoints)
- Celery tasks (3 tasks)
- Management commands (3 commands)
- Configuration settings

⏸️ **Frontend Not Implemented** (~800 lines):
- UI templates and views can be added later
- All features accessible via API and management commands

---

## Step 1: Clone and Checkout Branch

```bash
git clone <your-fork-url>
cd RepoRelay
git checkout enterprise-context-enrichment
```

---

## Step 2: Generate Database Migration

The model changes require a Django migration. This **must** be done in the DefectDojo Docker environment:

```bash
# Start DefectDojo containers
docker-compose up -d

# Generate migration
docker-compose exec uwsgi bash -c "python manage.py makemigrations"

# You should see output like:
# Migrations for 'dojo':
#   dojo/migrations/0XXX_enterprise_context_enrichment.py
#     - Add field last_commit_date to product
#     - Add field active_contributors_90d to product
#     - Add field days_since_last_commit to product
#     ... (47 Product fields)
#     - Add field auto_triage_decision to finding
#     - Add field auto_triage_reason to finding
#     - Add field auto_triaged_at to finding
```

**IMPORTANT**: Review the generated migration file before proceeding. All new fields should be nullable or have defaults for zero-downtime deployment.

---

## Step 3: Apply Migration

```bash
# Apply the migration
docker-compose exec uwsgi bash -c "python manage.py migrate"

# Verify migration applied
docker-compose exec uwsgi bash -c "python manage.py showmigrations dojo | tail -5"
```

---

## Step 4: Configure Environment Variables

Add these variables to your `.env` file or Docker environment:

```bash
# GitHub Integration (REQUIRED for GitHub sync)
DD_GITHUB_TOKEN=ghp_your_personal_access_token_here
DD_GITHUB_ORG=your-organization-name

# GitHub Sync Configuration (OPTIONAL)
DD_GITHUB_SYNC_INTERVAL_HOURS=4    # Default: 4 hours
DD_AUTO_ARCHIVE_DAYS=180           # Default: 180 days

# EPSS Integration (OPTIONAL)
DD_EPSS_API_URL=https://api.first.org/data/v1/epss  # Default
DD_EPSS_SYNC_ENABLED=true                            # Default: true

# Auto-Triage Configuration (OPTIONAL)
DD_AUTO_TRIAGE_ENABLED=false       # Default: false (enable after testing)
DD_AUTO_TRIAGE_RULES_PATH=dojo/auto_triage/rules.py  # Default
```

**Restart containers** to apply environment changes:

```bash
docker-compose restart
```

---

## Step 5: Verify Installation

Run these commands to verify the installation:

```bash
# Check management commands are available
docker-compose exec uwsgi bash -c "python manage.py help sync_github_repositories"
docker-compose exec uwsgi bash -c "python manage.py help update_epss_scores"
docker-compose exec uwsgi bash -c "python manage.py help apply_auto_triage"

# Verify new model fields exist
docker-compose exec uwsgi bash -c "python manage.py shell -c \"from dojo.models import Product; print([f.name for f in Product._meta.fields if 'github' in f.name or 'has_' in f.name][:5])\""
```

Expected output should show fields like `['github_url', 'github_repo_id', 'has_dockerfile', 'has_kubernetes_config', ...]`

---

## Step 6: Initial Data Sync

### 6.1 Test GitHub Connection

```bash
# Dry run to test GitHub API connectivity
docker-compose exec uwsgi bash -c "python manage.py sync_github_repositories --dry-run"

# Expected output:
# DRY RUN MODE - No changes will be made
# Organization: your-org-name
# Found 2451 repositories:
#   - your-org-name/repo1
#   - your-org-name/repo2
#   ...
```

### 6.2 Run Initial GitHub Sync

```bash
# Sync all repositories (this will take 10-30 minutes for 2,451 repos)
docker-compose exec uwsgi bash -c "python manage.py sync_github_repositories"

# Monitor progress in logs
docker-compose logs -f uwsgi | grep "Syncing repository"
```

**Expected Results**:
- Total repositories: 2,451
- Created: ~2,451 (first run)
- Updated: 0 (first run)
- Errors: Should be minimal

### 6.3 Fetch EPSS Scores

```bash
# Check EPSS coverage before sync
docker-compose exec uwsgi bash -c "python manage.py update_epss_scores --stats"

# Update EPSS scores for all active findings with CVEs
docker-compose exec uwsgi bash -c "python manage.py update_epss_scores"

# Check coverage after sync
docker-compose exec uwsgi bash -c "python manage.py update_epss_scores --stats"
```

**Expected Results**:
- Findings with CVE: ~17,000
- EPSS scores fetched: ~17,000 (depends on FIRST.org coverage)
- Coverage percentage: 80%+

---

## Step 7: Configure Celery Periodic Tasks

Add periodic tasks to keep data fresh. In DefectDojo admin or via Celery Beat:

```python
# Option 1: Using Django Admin
# Navigate to: /admin/django_celery_beat/periodictask/

# Option 2: Using Django Shell
docker-compose exec uwsgi bash -c "python manage.py shell"
```

```python
from django_celery_beat.models import PeriodicTask, IntervalSchedule

# GitHub Sync - Every 4 hours
schedule_4h, _ = IntervalSchedule.objects.get_or_create(
    every=4,
    period=IntervalSchedule.HOURS,
)
PeriodicTask.objects.get_or_create(
    name='GitHub Repository Metadata Sync',
    task='dojo.tasks.sync_github_metadata_task',
    interval=schedule_4h,
    kwargs='{"incremental": true}',
)

# EPSS Score Update - Daily
schedule_daily, _ = IntervalSchedule.objects.get_or_create(
    every=1,
    period=IntervalSchedule.DAYS,
)
PeriodicTask.objects.get_or_create(
    name='EPSS Score Update',
    task='dojo.tasks.update_epss_scores_task',
    interval=schedule_daily,
    kwargs='{"active_only": true, "trigger_triage": false}',
)
```

---

## Step 8: Test Auto-Triage (Optional)

Auto-triage is **disabled by default**. Test before enabling in production:

```bash
# Validate triage rules
docker-compose exec uwsgi bash -c "python manage.py apply_auto_triage --validate"

# Check current triage statistics
docker-compose exec uwsgi bash -c "python manage.py apply_auto_triage --stats"

# Dry run on specific product
docker-compose exec uwsgi bash -c "python manage.py apply_auto_triage --product-id 123 --dry-run"

# Apply to specific product (test first!)
docker-compose exec uwsgi bash -c "python manage.py apply_auto_triage --product-id 123"
```

**Enable auto-triage** after testing:

```bash
# Add to .env
DD_AUTO_TRIAGE_ENABLED=true

# Restart
docker-compose restart
```

---

## Step 9: Test API Endpoints

Test the new bulk API endpoints:

```bash
# Get API token from DefectDojo UI: Settings > API Key

# 1. Trigger GitHub sync via API
curl -X POST https://your-defectdojo.com/api/v2/products/sync_github/ \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"incremental": true, "archive_dormant": false}'

# 2. Update specific product signals
curl -X POST https://your-defectdojo.com/api/v2/products/123/update_repository_signals/ \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 123}'

# 3. Apply bulk triage
curl -X POST https://your-defectdojo.com/api/v2/findings/bulk_triage/ \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"product_id": 123, "active_only": true}'

# 4. Get cross-repository duplicates
curl https://your-defectdojo.com/api/v2/findings/cross_repository_duplicates/?min_repos=5&severity=Critical,High \
  -H "Authorization: Token YOUR_API_TOKEN"
```

---

## Step 10: Query Enriched Data

Use Django shell or API to query enriched data:

```bash
docker-compose exec uwsgi bash -c "python manage.py shell"
```

```python
from dojo.models import Product, Finding

# Get Tier 1 (very high criticality) products
tier1 = Product.objects.filter(business_criticality='very high')
print(f"Tier 1 products: {tier1.count()}")

# Get products with production signals
production = Product.objects.filter(
    has_kubernetes_config=True,
    has_environments=True,
    has_monitoring_config=True
)
print(f"Production repositories: {production.count()}")

# Get high-risk findings (high EPSS + Tier 1)
high_risk = Finding.objects.filter(
    active=True,
    epss_score__gte=0.5,
    test__engagement__product__business_criticality='very high'
)
print(f"High-risk findings: {high_risk.count()}")

# Get auto-escalated findings
escalated = Finding.objects.filter(
    active=True,
    auto_triage_decision='ESCALATE'
)
print(f"Auto-escalated findings: {escalated.count()}")

# Get archived/dormant repositories
archived = Product.objects.filter(
    days_since_last_commit__gt=180,
    lifecycle='retirement'
)
print(f"Archived repositories: {archived.count()}")
```

---

## Monitoring & Maintenance

### Daily Operations
- EPSS sync runs automatically (Celery task)
- GitHub metadata sync runs every 4 hours (Celery task)
- Auto-triage triggers on imports (if enabled)

### Weekly Operations
- Review auto-triage accuracy:
  ```bash
  docker-compose exec uwsgi bash -c "python manage.py apply_auto_triage --stats"
  ```
- Check GitHub API rate limits:
  ```bash
  # GitHub API: 5,000 requests/hour
  # Monitor in GitHub Settings > Developer settings > Personal access tokens
  ```

### Monthly Operations
- Archive dormant repositories:
  ```bash
  docker-compose exec uwsgi bash -c "python manage.py sync_github_repositories --archive-dormant"
  ```
- Review tier classifications and adjust thresholds if needed

### Monitoring Metrics

Query these metrics for dashboard/alerting:

```sql
-- Products with GitHub metadata
SELECT COUNT(*) as synced_products
FROM dojo_product
WHERE github_url != '';

-- Products by tier
SELECT business_criticality, COUNT(*) as count
FROM dojo_product
GROUP BY business_criticality;

-- EPSS coverage
SELECT
    COUNT(*) FILTER (WHERE cve IS NOT NULL AND cve != '') as findings_with_cve,
    COUNT(*) FILTER (WHERE epss_score IS NOT NULL) as findings_with_epss,
    ROUND(100.0 * COUNT(*) FILTER (WHERE epss_score IS NOT NULL) /
          NULLIF(COUNT(*) FILTER (WHERE cve IS NOT NULL AND cve != ''), 0), 2) as coverage_pct
FROM dojo_finding
WHERE active = true;

-- Auto-triage statistics
SELECT auto_triage_decision, COUNT(*) as count
FROM dojo_finding
WHERE active = true
GROUP BY auto_triage_decision;
```

---

## Troubleshooting

### GitHub Sync Issues

**Error: "GitHub token not configured"**
- Check `DD_GITHUB_TOKEN` is set in environment
- Verify token has `repo` and `read:org` scopes
- Restart containers after setting token

**Error: "API rate limit exceeded"**
- GitHub allows 5,000 requests/hour per token
- Use `--incremental` flag to reduce API calls
- Consider increasing `DD_GITHUB_SYNC_INTERVAL_HOURS`

**Error: "Repository not found"**
- Verify GitHub organization name is correct
- Check token has access to private repositories
- Ensure organization membership is visible

### EPSS Sync Issues

**Error: "EPSS API is not accessible"**
- Check internet connectivity from container
- Verify FIRST.org API is online: https://api.first.org/data/v1/epss
- Check firewall rules allow HTTPS to api.first.org

**Low EPSS coverage (<80%)**
- Some CVEs may not have EPSS scores yet
- FIRST.org updates scores daily
- Run update again: `python manage.py update_epss_scores`

### Auto-Triage Issues

**Error: "Auto-triage engine module not available"**
- Verify `dojo/auto_triage/` directory exists
- Check migration was applied successfully
- Restart uwsgi container

**Unexpected triage decisions**
- Review rules: `python manage.py apply_auto_triage --validate`
- Check rule evaluation order in `dojo/auto_triage/rules.py`
- Reset and re-evaluate: `python manage.py apply_auto_triage --reset`

---

## Performance Considerations

### Initial Sync Performance
- **2,451 repositories**: ~20-30 minutes
- **17,000 findings**: ~10-15 minutes for EPSS sync
- GitHub API rate limit: 5,000 requests/hour

### Ongoing Sync Performance
- **Incremental sync**: ~5-10 minutes (only changed repos)
- **EPSS daily sync**: ~10 minutes
- Database indexes recommended on:
  - `dojo_product.github_url`
  - `dojo_product.business_criticality`
  - `dojo_finding.epss_score`
  - `dojo_finding.auto_triage_decision`

---

## Rollback Plan

If issues occur, rollback migration:

```bash
# Check current migration number
docker-compose exec uwsgi bash -c "python manage.py showmigrations dojo | tail -1"

# Rollback to previous migration (replace 0XXX with actual number)
docker-compose exec uwsgi bash -c "python manage.py migrate dojo 0XXX"

# Checkout previous git commit
git checkout master
docker-compose restart
```

**Note**: New fields are nullable, so rollback is safe. Data will be preserved if you re-apply later.

---

## Support

- **Documentation**: See CUSTOMIZATIONS.md for detailed technical documentation
- **Implementation Status**: See IMPLEMENTATION_STATUS.md for roadmap
- **Issues**: File with `[ENTERPRISE]` tag if fork-specific
- **Upstream**: https://github.com/DefectDojo/django-DefectDojo/issues

---

## Next Steps: UI Implementation (Optional)

The backend is fully functional. To add UI:

1. **Study existing DefectDojo UI patterns**:
   - Bootstrap 3.4.1 templates in `dojo/templates/`
   - DataTables for data grids
   - Tab navigation in product views

2. **Create templates** (estimated ~800 lines):
   - `dojo/templates/dojo/product_repository.html` - Repository health tab
   - `dojo/templates/dojo/repository_dashboard.html` - Global dashboard
   - `dojo/templates/dojo/product_cross_repo_duplicates.html` - Dedup view

3. **Add views** to `dojo/product/views.py`:
   - `view_product_repository(request, pid)`
   - `repository_dashboard(request)`
   - `product_cross_repo_duplicates(request, pid)`

4. **Add URL routes** to `dojo/urls.py` or `dojo/asset/urls.py`

5. **Extend ProductFilter** in `dojo/filters.py`:
   - Add filters for `business_criticality`, `has_dockerfile`, etc.

6. **Update base template** to add Repository tab to product navigation

All data is already available via API and database queries, making UI implementation straightforward.

---

**Deployment complete!** 🚀

Your DefectDojo instance now has enterprise-grade context enrichment with automated tier classification, EPSS scoring, and intelligent auto-triage capabilities.
