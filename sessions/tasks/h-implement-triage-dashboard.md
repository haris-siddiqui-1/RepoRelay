---
name: h-implement-triage-dashboard
branch: feature/triage-dashboard
status: in-progress
created: 2025-11-25
depends_on:
  - h-implement-triage-workflow
submodules:
  - RepoRelay
---

# Implement Triage Dashboard (Phase 3)

## Problem/Goal

Build a modern triage dashboard with priority queue view, bulk actions, and actionable widgets. This is the primary interface for vulnerability management.

**Reference**: `sessions/docs/vulnerability-prioritization-strategy.md` - Part 3

## Success Criteria
- [ ] Create priority queue DataTable view at `/triage/queue`
- [ ] Implement filters: priority bucket, tier, severity, alert type, SLA status, EPSS range, age
- [ ] Add bulk triage action controls (escalate, accept, dismiss, assign, defer)
- [ ] Create KPI widgets: total open, P0/P1 count, SLA breaches, triage rate
- [ ] Create chart widgets: priority distribution, findings by tier, trend over time
- [ ] Add action widgets: auto-triage suggestions, SLA approaching, KEV matches
- [ ] Implement filter persistence (localStorage or user preference)
- [ ] Use modern UI design system (Tailwind, Alpine.js, Chart.js)

## Context Manifest

### How the Triage Dashboard Fits Into DefectDojo's Architecture

**The Current State - What We're Building Upon:**

DefectDojo has a comprehensive vulnerability prioritization system in place as of Phase 2 (see `sessions/docs/vulnerability-prioritization-strategy.md`). The Finding model has been extended with priority scoring fields (`priority_score`, `priority_bucket`) and triage workflow fields (`triage_state`, `triage_assigned_to`, `triage_due_date`, `triage_reason`) as of migrations completed in Phase 1-2. The API layer in `dojo/api_v2/views.py` exposes a `bulk_triage` endpoint at `/api/v2/findings/bulk_triage/` (lines 1047-1080) that accepts finding IDs and triage actions (escalate, assign, defer, accept, dismiss) and calls the underlying `bulk_triage` service from `dojo/finding/triage_service.py`.

The modern UI framework is already established with:
- **Base Template**: `dojo/templates/base_modern.html` provides the enterprise dark-mode-first design system with collapsible sidebar navigation, command palette, and Alpine.js initialization
- **DataTable Component**: `dojo/frontend/src/js/alpine/components/dataTable.js` (753 lines) provides virtual scrolling, sorting, filtering, bulk selection, and column customization with localStorage persistence
- **DataTable Styles**: `dojo/static/dojo/css/components/dataTable.css` (959 lines) implements the violet accent (#8B5CF6) color scheme with soft dark backgrounds (#1c2128) and glass morphism effects
- **Widget Architecture**: The GitHub Insights dashboard (`dojo/templates/dojo/github_insights_dashboard.html` and `dojo/static/dojo/js/github_insights_dashboard.js`) demonstrates a working widget-based layout with Chart.js integration, filter controls, and refresh mechanisms

**The Data Flow - How Priority Scoring Works:**

When a Finding is created or updated, the priority scoring system calculates a numerical score (0-1000+) based on:
1. **Tier Weight** (0.2-5.0): Comes from the Repository model's `tier` field (tier1-tier4, archived) which is computed by `dojo/github_collector/tier_classifier.py` using 36 binary signals across deployment, production readiness, activity, code organization, and security maturity categories
2. **Severity Score** (10-100): Critical=100, High=75, Medium=50, Low=25, Info=10
3. **Modifiers** (+/- points): EPSS score (0.0-1.0 from `epss_score` field), KEV status (`known_exploited` boolean), fix availability (`fix_available`), SLA breach status (`sla_expiration_date` vs current date), production signals (Repository `has_environments`, `has_releases` booleans), and dormancy (`days_since_last_commit` from Repository model)

The formula is: `PriorityScore = (TierWeight × SeverityScore) + Modifiers`, resulting in a `priority_bucket` assignment: P0 (>=500), P1 (300-499), P2 (150-299), P3 (50-149), P4 (<50). These computed fields are stored directly on Finding records with database indexes for fast sorting.

**Where Our Dashboard Will Hook In:**

The triage dashboard will be a NEW top-level view in DefectDojo, accessible via `/triage/queue` and `/triage/dashboard` routes. Following the modern UI pattern established by `dashboard_modern` in `dojo/home/views.py` (lines 72-109), we'll create:

1. **URL Registration**: Add routes to `dojo/finding/urls.py` (similar to how `all_findings`, `open_findings` are registered)
2. **View Functions**: Create new view functions in `dojo/finding/views.py` that query authorized findings using `get_authorized_findings()` helper
3. **Templates**: Create `dojo/templates/dojo/triage_queue_modern.html` and `triage_dashboard_modern.html` extending `base_modern.html`
4. **JavaScript**: Create `dojo/static/dojo/js/triage_dashboard.js` for widget management and Chart.js initialization (following `github_insights_dashboard.js` pattern)
5. **API Integration**: Leverage existing `/api/v2/findings/` endpoints with filters for `priority_bucket`, `triage_state`, etc., and use `/api/v2/findings/bulk_triage/` for bulk actions

**The DataTable Integration - How Findings Will Display:**

The enterprise DataTable component expects data in a specific JSON format with columns configuration. For the triage queue:

```javascript
// In triage_queue_modern.html template:
<script id="findings-data" type="application/json">
{{ findings_json|safe }}
</script>

<div x-data="dataTable({
    data: JSON.parse(document.getElementById('findings-data').textContent),
    columns: [
        { key: 'priority_score', label: 'Priority', sortType: 'number' },
        { key: 'title', label: 'Finding', sortType: 'string' },
        { key: 'repository_name', label: 'Repository', sortType: 'string' },
        { key: 'tier', label: 'Tier', sortType: 'string' },
        { key: 'severity', label: 'Severity', sortType: 'severity' },
        { key: 'epss_score', label: 'EPSS', sortType: 'number' },
        { key: 'known_exploited', label: 'KEV', sortType: 'boolean' },
        { key: 'age_days', label: 'Age', sortType: 'number' },
        { key: 'sla_status', label: 'SLA', sortType: 'string' }
    ],
    defaultSort: 'priority_score',
    defaultSortDir: 'desc',
    csrfToken: '{{ csrf_token }}',
    bulkActionUrl: '{% url "findings_bulk_triage" %}'
})">
```

The view function will serialize Finding QuerySet to JSON:

```python
# In dojo/finding/views.py:
def triage_queue(request):
    findings = get_authorized_findings(Permissions.Finding_View).filter(
        triage_state='pending',
        active=True,
        duplicate=False
    ).select_related(
        'test__engagement__product__prod_type',
        'test__engagement__product__repositories'  # Access repository tier
    )

    findings_data = [
        {
            'id': f.id,
            'priority_score': f.priority_score,
            'priority_bucket': f.priority_bucket,
            'title': f.title,
            'repository_name': f.test.engagement.product.repositories.first().name if f.test.engagement.product.repositories.exists() else '',
            'tier': f.test.engagement.product.repositories.first().tier if f.test.engagement.product.repositories.exists() else 'tier4',
            'severity': f.severity,
            'epss_score': f.epss_score or 0,
            'known_exploited': f.known_exploited,
            'age_days': (timezone.now().date() - f.date).days,
            'sla_status': 'breached' if f.sla_expiration_date and f.sla_expiration_date < timezone.now().date() else 'ok'
        }
        for f in findings
    ]

    return render(request, 'dojo/triage_queue_modern.html', {
        'findings_json': json.dumps(findings_data),
        'total_findings': len(findings_data)
    })
```

**The Widget Dashboard - Following GitHub Insights Pattern:**

The triage dashboard (`/triage/dashboard`) will use a similar widget grid structure to `github_insights_dashboard.html`:

1. **Filter Panel**: Product type filter, date range selector, priority bucket filters (dropdowns at top)
2. **KPI Widget Row**: Four stat cards showing Total Open Findings, P0/P1 Count, SLA Breaches, Triage Rate (findings/day)
3. **Chart Widget Grid**:
   - Priority Distribution Pie Chart (uses Finding.objects.values('priority_bucket').annotate(count=Count('id')))
   - Findings by Tier Stacked Bar Chart (joins to Repository model via test→engagement→product→repositories)
   - Trend Over Time Line Chart (groups by created date)
   - Top Vulnerable Repositories Horizontal Bar (aggregates findings per repository)
4. **Action Widgets**:
   - Auto-Triage Suggestions (queries findings where auto_triage_confidence >= 85 and triage_state='pending')
   - SLA Approaching (filters where sla_expiration_date BETWEEN today AND today+7 days)
   - New KEV Matches (filters where known_exploited=True and date >= today-7)
   - Stale Findings (filters where triage_state='pending' and date < today-30 days)

Chart.js initialization follows the same pattern as `dashboard_modern.html` (lines 198-350):

```javascript
// In triage_dashboard.js:
const priorityPieCtx = document.getElementById('priorityPieChart');
new Chart(priorityPieCtx, {
    type: 'pie',
    data: {
        labels: ['P0 - Critical', 'P1 - High', 'P2 - Medium', 'P3 - Low', 'P4 - Minimal'],
        datasets: [{
            data: [{{ p0_count }}, {{ p1_count }}, {{ p2_count }}, {{ p3_count }}, {{ p4_count }}],
            backgroundColor: ['#DC2626', '#EA580C', '#D97706', '#2563EB', '#64748B']
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } }
    }
});
```

**The Bulk Actions Flow - How Triage Operations Work:**

When a user selects multiple findings and clicks a bulk action button:

1. **Frontend Collection**: The dataTable component's `selected` array contains finding IDs (via checkbox selection)
2. **Action Modal**: Show confirmation modal with reason text field (required for accept/dismiss actions) and date picker (for defer action)
3. **API Call**: POST to `/api/v2/findings/bulk_triage/` with payload:
```json
{
  "finding_ids": [123, 456, 789],
  "action": "escalate",
  "reason": "High EPSS score and production deployment",
  "assigned_to": 42,  // Optional user ID
  "due_date": "2025-12-01"  // Optional for defer
}
```
4. **Backend Processing**: The `bulk_triage` service in `dojo/finding/triage_service.py` iterates through findings, updates `triage_state`, creates TriageHistory records, and returns success/error counts
5. **Frontend Refresh**: On successful response, reload the DataTable data and show toast notification

**Critical Integration Points:**

1. **Authorization**: Always use `get_authorized_findings(Permissions.Finding_View)` to respect user permissions (RBAC system in `dojo/authorization/`)
2. **Performance**: Use `.select_related()` for Repository tier access (Finding → Test → Engagement → Product → Repository is a deep join chain)
3. **Design System Compliance**:
   - Color palette: Violet accent (#8B5CF6), soft dark background (#1c2128), borders rgba(255,255,255,0.1)
   - Typography: Plus Jakarta Sans for UI, JetBrains Mono for technical values
   - Animations: 200ms cubic-bezier(0.4, 0, 0.2, 1) transitions
   - Glass morphism: `backdrop-filter: blur(12px)` with `-webkit-` prefix for Safari
4. **Navigation**: Update `base_modern.html` sidebar to add Triage Queue link (lines 226-281) with active state detection via `{% if request.resolver_match.url_name == 'triage_queue' %}`
5. **Command Palette**: Add triage routes to the command palette commands array (lines 364-372 in base_modern.html)

### Technical Reference Details

#### Finding Model Fields (dojo/models.py:3280-3610)

**Priority Fields:**
- `priority_score` (IntegerField, indexed): 0-1000+ computed score
- `priority_bucket` (CharField, indexed): 'P0'/'P1'/'P2'/'P3'/'P4'
- `priority_calculated_at` (DateTimeField): Last calculation timestamp

**Triage Workflow Fields:**
- `triage_state` (CharField, indexed): 'pending'/'escalated'/'assigned'/'deferred'/'accepted'/'dismissed'
- `triage_assigned_to` (ForeignKey to Dojo_User)
- `triage_due_date` (DateField)
- `triage_reason` (TextField)
- `auto_triage_rule` (CharField): Name of matched rule
- `auto_triage_confidence` (IntegerField): 0-100 confidence score

**Security Context Fields:**
- `epss_score` (FloatField): 0.0-1.0 exploitation probability
- `epss_percentile` (FloatField): 0.0-1.0 percentile rank
- `known_exploited` (BooleanField): KEV catalog match
- `ransomware_used` (BooleanField): Ransomware campaign linkage
- `kev_date` (DateField): Date added to KEV
- `fix_available` (BooleanField): Remediation available
- `sla_start_date` (DateField): SLA calculation start
- `sla_expiration_date` (DateField): SLA deadline

**Relationship Fields:**
- `test` (ForeignKey): Links to Test model
- `test.engagement` (reverse ForeignKey): Links to Engagement
- `test.engagement.product` (reverse ForeignKey): Links to Product
- `test.engagement.product.repositories` (ManyToMany): Links to Repository model for tier access

#### Repository Model Fields (dojo/models.py:4200-4450)

**Tier Classification:**
- `tier` (CharField): 'tier1'/'tier2'/'tier3'/'tier4'/'archived'
- Tier is computed by `dojo/github_collector/tier_classifier.py` using 36 binary signals

**Binary Signals (Boolean fields):**
- Deployment: `has_dockerfile`, `has_kubernetes_config`, `has_ci_cd`, `has_terraform`, `has_deployment_scripts`, `has_procfile`
- Production: `has_environments`, `has_releases`, `has_branch_protection`, `has_monitoring_config`, `has_ssl_config`, `has_database_migrations`
- Activity: `recent_commits_30d`, `active_prs_30d`, `multiple_contributors`, `has_dependabot_activity`, `recent_releases_90d`, `consistent_commit_pattern`
- Organization: `has_tests`, `has_documentation`, `has_api_specs`, `has_codeowners`, `has_security_md`, `is_monorepo`
- Security: `has_security_scanning`, `has_secret_scanning`, `has_dependency_scanning`, `has_gitleaks_config`, `has_sast_config`

**Activity Metrics:**
- `days_since_last_commit` (IntegerField)
- `active_contributors_90d` (IntegerField)
- `active_webhooks_count` (IntegerField)

#### API Endpoints

**Bulk Triage Endpoint** (`dojo/api_v2/views.py:1047-1080`):
- **URL**: POST `/api/v2/findings/bulk_triage/`
- **Request Body**:
```json
{
  "finding_ids": [int],
  "action": "escalate"|"assign"|"defer"|"accept"|"dismiss",
  "reason": "string",  // Required for accept/dismiss
  "assigned_to": int,  // Optional user ID
  "due_date": "YYYY-MM-DD"  // Optional for defer
}
```
- **Response**:
```json
{
  "success_count": int,
  "error_count": int,
  "errors": [{"finding_id": int, "error": "string"}],
  "filtered_count": int  // Unauthorized findings excluded
}
```
- **Authorization**: Filters to only findings user has access to via `get_queryset()`

**Findings List Endpoint**:
- **URL**: GET `/api/v2/findings/`
- **Query Parameters**: `priority_bucket`, `triage_state`, `severity`, `epss_score__gte`, `known_exploited`, `active`, `duplicate`, `test__engagement__product`, `date__gte`, `date__lte`
- **Ordering**: `?ordering=-priority_score` for descending priority

**Triage History Endpoint** (`dojo/api_v2/views.py:1027-1038`):
- **URL**: GET `/api/v2/findings/{id}/triage_history/`
- **Response**: Paginated list of TriageHistory records with action, timestamps, user, reason, confidence

#### View Implementation Pattern

**File Location**: `dojo/finding/views.py`

**Pattern to Follow**:
```python
from django.shortcuts import render
from django.utils import timezone
from dojo.authorization.roles_permissions import Permissions
from dojo.finding.queries import get_authorized_findings
from dojo.utils import add_breadcrumb
import json

def triage_queue(request):
    """Priority queue view for vulnerability triage."""
    findings = get_authorized_findings(Permissions.Finding_View).filter(
        triage_state='pending',
        active=True,
        duplicate=False
    ).select_related(
        'test__engagement__product'
    ).prefetch_related(
        'test__engagement__product__repositories'
    ).order_by('-priority_score')

    # Serialize for DataTable component
    findings_data = []
    for f in findings:
        repo = f.test.engagement.product.repositories.first()
        findings_data.append({
            'id': f.id,
            'priority_score': f.priority_score,
            'priority_bucket': f.priority_bucket,
            'title': f.title,
            'repository_name': repo.name if repo else 'N/A',
            'tier': repo.tier if repo else 'tier4',
            'severity': f.severity,
            'epss_score': f.epss_score or 0.0,
            'known_exploited': f.known_exploited,
            'age_days': (timezone.now().date() - f.date).days,
            'sla_status': 'breached' if f.sla_expiration_date and f.sla_expiration_date < timezone.now().date() else 'ok'
        })

    add_breadcrumb(title="Triage Queue", top_level=True, request=request)
    return render(request, 'dojo/triage_queue_modern.html', {
        'findings_json': json.dumps(findings_data),
        'total_findings': len(findings_data)
    })
```

#### URL Registration Pattern

**File Location**: `dojo/finding/urls.py`

**Add Routes**:
```python
re_path(r'^triage/queue$', views.triage_queue, name='triage_queue'),
re_path(r'^triage/dashboard$', views.triage_dashboard, name='triage_dashboard'),
```

#### Template Structure

**File Location**: `dojo/templates/dojo/triage_queue_modern.html`

**Structure**:
```django
{% extends "base_modern.html" %}
{% load static %}

{% block add_styles %}
    {{ block.super }}
    <link rel="stylesheet" href="{% static 'dojo/css/components/dataTable.css' %}">
{% endblock %}

{% block content %}
    <!-- Page Header -->
    <div class="mb-12">
        <h1 class="font-sans text-6xl font-bold leading-tight text-enterprise-text-primary tracking-tight">
            Vulnerability Triage Queue
        </h1>
        <p class="font-sans mt-3 text-base font-light text-enterprise-text-secondary tracking-wide">
            Priority-sorted findings requiring triage
        </p>
    </div>

    <!-- Filter Controls (similar to github_insights_dashboard.html lines 670-710) -->

    <!-- DataTable Container -->
    <script id="findings-data" type="application/json">
    {{ findings_json|safe }}
    </script>

    <div class="dd-table-enterprise" x-data="dataTable({...})">
        <!-- Table markup using dataTable.css classes -->
    </div>
{% endblock %}

{% block postscript %}
    {{ block.super }}
    <script type="module">
        import dataTable from '{% static "dist/js/alpine/components/dataTable.js" %}';
        // Initialize Alpine component
    </script>
{% endblock %}
```

#### Dashboard Widget Layout

**File Location**: `dojo/templates/dojo/triage_dashboard_modern.html`

**Widget Grid** (follows `github_insights_dashboard.html:94-133`):
```css
#dashboard-widgets {
    display: grid;
    grid-template-columns: repeat(12, 1fr);
    gap: 24px;
}

.kpi-widget { grid-column: span 3; }  /* 4 KPIs across top */
.chart-widget-large { grid-column: span 6; }  /* 2 charts side-by-side */
.action-widget { grid-column: span 4; }  /* 3 action widgets */
```

#### Chart.js Configuration

**Color Scheme for Severity**:
- Critical: #DC2626 (red-600)
- High: #EA580C (orange-600)
- Medium: #D97706 (amber-600)
- Low: #2563EB (blue-600)
- Info: #64748B (slate-500)

**Priority Bucket Colors**:
- P0: #DC2626 (critical red)
- P1: #EA580C (high orange)
- P2: #D97706 (medium amber)
- P3: #2563EB (low blue)
- P4: #64748B (minimal slate)

### Implementation Checklist

**Phase 3a - Triage Queue View:**
1. Create view function `triage_queue()` in `dojo/finding/views.py`
2. Register URL route in `dojo/finding/urls.py`
3. Create template `dojo/templates/dojo/triage_queue_modern.html`
4. Add navigation link to `base_modern.html` sidebar (line ~280)
5. Add command palette entry (line ~371)
6. Implement DataTable with columns: priority, title, repository, tier, severity, EPSS, KEV, age, SLA
7. Add bulk action controls: escalate, assign, defer, accept risk, dismiss buttons
8. Integrate with `/api/v2/findings/bulk_triage/` endpoint
9. Add filter controls: priority bucket, tier, severity, alert type, SLA status, EPSS range, age range

**Phase 3b - Triage Dashboard View:**
1. Create view function `triage_dashboard()` in `dojo/finding/views.py`
2. Register URL route in `dojo/finding/urls.py`
3. Create template `dojo/templates/dojo/triage_dashboard_modern.html`
4. Create JavaScript file `dojo/static/dojo/js/triage_dashboard.js`
5. Implement KPI widgets: Total Open, P0/P1 Count, SLA Breaches, Triage Rate
6. Implement chart widgets: Priority Distribution (pie), By Tier (stacked bar), Trend (line), Top Repos (h-bar)
7. Implement action widgets: Auto-Triage Suggestions, SLA Approaching, New KEV Matches, Stale Findings
8. Add filter persistence (localStorage similar to dataTable.js lines 137-176)
9. Add refresh controls for widgets

**Phase 3c - Testing & Polish:**
1. Test authorization with different user roles
2. Test bulk actions with validation (reason required for accept/dismiss)
3. Test DataTable virtual scrolling with 1000+ findings
4. Test responsive layout on mobile (768px breakpoint)
5. Verify Chart.js animations and interactivity
6. Test filter persistence across page refreshes
7. Verify correct severity/priority badge colors match design system
8. Test with empty state (no findings to triage)
9. Add loading spinners for async operations
10. Test SLA date calculations (breach vs approaching vs OK)

## Technical Specification

### URL Routes
- `/triage/queue` - Main triage queue view
- `/triage/dashboard` - Overview dashboard with widgets

### DataTable Columns
1. Checkbox (bulk select)
2. Priority Score (colored badge by bucket)
3. Finding Title (link)
4. Repository (link)
5. Tier (badge)
6. Severity (colored badge)
7. EPSS Score (bar)
8. KEV Status (icon)
9. Age (days)
10. SLA Status (countdown/overdue)
11. Actions (dropdown)

### Widgets
**KPIs**: Total Open, P0/P1 Count, SLA Breaches, Triage Rate
**Charts**: Priority Distribution (pie), By Tier (stacked bar), Trend (line), Top Repos (horizontal bar)
**Actions**: Auto-Triage Suggestions, SLA Approaching, New KEV Matches, Stale Findings

### API Endpoints
- GET `/api/v2/triage/queue/` - Paginated queue with filters
- GET `/api/v2/triage/stats/` - Dashboard statistics
- POST `/api/v2/triage/bulk/` - Bulk actions

## User Notes

This task depends on Phase 2 (triage workflow) being complete. Uses the modern UI stack (Tailwind CSS 3.4, Alpine.js 3.13, Chart.js 4.4).

## Work Log
- [2025-11-25] Task created from strategy document
