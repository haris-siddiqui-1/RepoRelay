# Finding Module

The Finding module provides DefectDojo's core vulnerability management capabilities including priority scoring, triage workflows, and notification routing.

## Overview

This module contains:
- **Priority Scoring** (`priority_scorer.py`) - Automated vulnerability prioritization
- **Triage Workflow** (`triage_service.py`) - Manual and automated triage capabilities
- **Notification Routing** (`priority_router.py`) - Priority-based notification delivery
- **Triage Dashboard** - Modern UI for vulnerability triage queue

## Priority Scoring System

Automated vulnerability prioritization based on tier, severity, and risk modifiers.

### Configuration

**Location:** `dojo/finding/priority_scorer.py`

**Finding Fields:**
- `priority_score` (Integer) - Calculated score
- `priority_bucket` (CharField) - P0, P1, P2, P3, or P4
- `priority_calculated_at` (DateTimeField) - Last calculation timestamp

### Scoring Formula

```
PriorityScore = (TierWeight × SeverityScore) + Modifiers
```

**Tier Weights:**
| Tier | Weight | Description |
|------|--------|-------------|
| tier1 | 5.0 | Critical production infrastructure |
| tier2 | 3.5 | Important production services |
| tier3 | 2.0 | Internal tools and services |
| tier4 | 1.0 | Low-priority repositories |
| archived | 0.2 | Archived/deprecated repositories |

**Severity Scores:**
| Severity | Score |
|----------|-------|
| Critical | 100 |
| High | 75 |
| Medium | 50 |
| Low | 25 |
| Info | 10 |

**Priority Buckets:**
| Bucket | Score Range | Response |
|--------|-------------|----------|
| P0 | ≥500 | Immediate |
| P1 | 300-499 | Same day |
| P2 | 150-299 | This week |
| P3 | 50-149 | This month |
| P4 | <50 | Backlog |

### Modifiers

**Positive Modifiers (increase priority):**
| Modifier | Points | Condition |
|----------|--------|-----------|
| KEV | +150 | In CISA Known Exploited Vulnerabilities |
| Ransomware | +100 | Associated with ransomware campaigns |
| High EPSS | +75 | EPSS score > 0.5 |
| SLA Breach | +50 | Past SLA deadline |
| Fix Available | +30 | Patched version available |
| Production Signals | +25 | Repository has production indicators |
| Active Webhooks | +15 | Repository has active CI/CD webhooks |

**Negative Modifiers (decrease priority):**
| Modifier | Points | Condition |
|----------|--------|-----------|
| Very Low EPSS | -50 | EPSS score < 0.01 |
| Dormant Repo | -40 | No commits in 180+ days |
| No Production | -30 | No production indicators |
| No Fix | -20 | No patched version available |

### Tier Resolution

Tier is resolved in this order (first match wins):
1. `Repository.consumption_tier_override` - Override from dependency graph analysis
2. `Repository.tier` - Base tier from signal classification
3. `Product.business_criticality` - Fallback for non-GitHub products
4. Default weight: 1.0

### Usage

```bash
# Calculate scores for all active findings
python manage.py calculate_priority_scores

# Force recalculation of all findings
python manage.py calculate_priority_scores --force

# Calculate for specific product
python manage.py calculate_priority_scores --product-id 123

# Dry run to preview results
python manage.py calculate_priority_scores --dry-run

# Async calculation via Celery
python manage.py calculate_priority_scores --async
```

**Programmatic Usage:**
```python
from dojo.finding.priority_scorer import PriorityScorer

scorer = PriorityScorer()
score, bucket = scorer.calculate_priority(finding)
finding.priority_score = score
finding.priority_bucket = bucket
finding.save()
```

---

## Triage Workflow System

Manual and automated triage capabilities with full audit trail.

### Configuration

**Location:** `dojo/finding/triage_service.py`

**Finding Fields:**
- `triage_state` - Current state (pending/escalated/assigned/deferred/accepted/dismissed)
- `triage_assigned_to` - Assigned user (ForeignKey)
- `triage_due_date` - Due date for action
- `triage_reason` - Reason for triage decision
- `auto_triage_rule` - Name of auto-triage rule that matched
- `auto_triage_confidence` - Confidence score (0-100)

### State Machine

```
pending → escalated → assigned → deferred
                  ↓           ↓
              accepted    dismissed
                  ↑           ↑
                  └─── reopen ───┘
```

**Valid Actions:**
| Action | From States | To State |
|--------|-------------|----------|
| escalate | pending | escalated |
| assign | pending, escalated | assigned |
| defer | pending, escalated, assigned | deferred |
| accept | pending, escalated, assigned | accepted |
| dismiss | pending, escalated, assigned | dismissed |
| reopen | accepted, dismissed, deferred | pending |

### Triage Service Functions

```python
from dojo.finding.triage_service import TriageService

service = TriageService()

# Auto-triage a finding
service.perform_auto_triage(finding, save=True)

# Manual triage action
service.perform_triage_action(
    finding=finding,
    action='assign',
    user=request.user,
    reason='Assigned for remediation',
    assigned_to=developer_user,
    due_date=date(2025, 2, 15)
)

# Bulk triage
service.bulk_triage(
    findings=Finding.objects.filter(priority_bucket='P0'),
    action='escalate',
    user=request.user,
    reason='Escalating all P0 findings'
)

# Get valid actions for current state
valid_actions = service.get_valid_actions(finding.triage_state)
```

### REST API Endpoints

```bash
# Single triage action
POST /api/v2/findings/{id}/triage/
{
    "action": "assign",
    "reason": "Assigned for remediation",
    "assigned_to": 123,
    "due_date": "2025-02-15"
}

# Get triage history
GET /api/v2/findings/{id}/triage_history/

# Bulk triage
POST /api/v2/findings/bulk_triage/
{
    "finding_ids": [1, 2, 3],
    "action": "escalate",
    "reason": "Escalating critical findings"
}
```

### Audit Trail

The `TriageHistory` model records every triage action:
- `finding` - Related finding
- `action` - Action performed
- `previous_state` - State before action
- `new_state` - State after action
- `reason` - Explanation for action
- `rule_name` - Auto-triage rule (if applicable)
- `confidence` - Confidence score (if auto-triaged)
- `performed_by` - User who performed action
- `performed_at` - Timestamp

---

## Notification Routing System

Intelligent notification routing that reduces alert fatigue by batching low-priority findings.

### Configuration

**Location:** `dojo/finding/priority_router.py`

**Environment Variables:**
```bash
DD_NOTIFICATION_P0_P1_IMMEDIATE=True        # Enable immediate P0/P1 alerts
DD_NOTIFICATION_P2_DELAY_MINUTES=60         # Delay for P2 notifications
DD_NOTIFICATION_DAILY_DIGEST_TIME=09:00     # Time for daily digest
DD_NOTIFICATION_WEEKLY_DIGEST_DAY=monday    # Day for weekly digest
DD_NOTIFICATION_SUPPRESS_AUTO_ACCEPTED=True # Suppress accepted/dismissed
```

### Routing Rules

| Priority | Type | Timing | Recipients |
|----------|------|--------|------------|
| P0 | Immediate alert | Real-time | Security team + repo owner |
| P1 | Immediate alert | Real-time | Security team |
| P2 | Standard | 1 hour delay | Security team |
| P3 | Daily digest | 9:00 AM | Security team |
| P4 | Weekly digest | Monday 9:00 AM | Optional |
| Auto-accepted | Suppressed | - | - |

### Celery Tasks

```python
# Registered in Celery Beat schedule
"send-priority-standard-notifications"  # Every 15 minutes
"send-priority-daily-digest"            # Daily at 9:00 AM
"send-priority-weekly-digest"           # Monday 9:00 AM
```

### Usage

```python
from dojo.finding.priority_router import PriorityRouter

router = PriorityRouter()

# Route notification based on priority
result = router.route_finding_notification(
    finding=finding,
    event="scan_added",
    product=product,
)
# Returns: 'immediate', 'queued_standard', 'queued_daily', 'queued_weekly', 'suppressed'

# Preview digest before sending
preview = router.get_digest_preview(digest_type="daily")

# Manually trigger digest (for testing)
router.send_daily_digest()
```

### Notification Templates

Templates in `dojo/templates/notifications/{channel}/{event}.tpl`:

| Event | Channels | Description |
|-------|----------|-------------|
| `priority_alert_immediate` | All | P0/P1 single finding |
| `priority_alert_standard` | All | P2 single finding |
| `priority_digest_daily` | All | P3 grouped by product |
| `priority_digest_weekly` | All | P4 grouped by product |

---

## Triage Dashboard

Modern vulnerability triage interface at `/triage/queue` and `/triage/dashboard`.

### URL Routes

```python
# dojo/finding/urls.py
re_path(r'^triage/queue$', views.triage_queue, name='triage_queue'),
re_path(r'^triage/dashboard$', views.triage_dashboard, name='triage_dashboard'),
```

### Triage Queue Features

- **Priority-Sorted DataTable** - Virtual scrolling for 1000+ findings
- **Filter Controls** - Priority bucket, triage state, severity, tier
- **Bulk Actions** - Escalate, Assign, Defer, Accept, Dismiss
- **RBAC Enforcement** - Uses `get_authorized_findings()`

### Dashboard KPIs

- Total Open Findings
- P0/P1 Count
- SLA Breaches
- Triage Rate (findings/day)

### Dashboard Charts

- Priority Distribution (pie)
- Severity Distribution (bar)
- Trend Over Time (line)

### Action Widgets

- SLA Approaching (top 10)
- KEV Matches (top 10)
- High EPSS Findings (top 10)
- Stale Findings (top 10)

---

## Database Migrations

| Migration | Description |
|-----------|-------------|
| 0260 | Adds 6 triage workflow fields to Finding |
| 0261 | Creates TriageHistory model |
| 0262 | Backfills triage_state from legacy flags |
| 0264 | Creates PriorityDigestQueue model |
| 0265 | Adds notification event fields |

---

## Design Principles

1. **Business Context First** - Repository tier drives prioritization, not just CVE severity
2. **Automated Decision Support** - Auto-triage suggests but requires human approval for risk acceptance
3. **Full Audit Trail** - Every triage decision is recorded
4. **Reduced Alert Fatigue** - Low-priority findings batched into digests
5. **State Transition Validation** - Invalid transitions rejected
