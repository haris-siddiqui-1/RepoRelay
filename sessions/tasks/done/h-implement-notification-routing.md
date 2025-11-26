---
name: h-implement-notification-routing
branch: feature/notification-routing
status: completed
created: 2025-11-25
depends_on:
  - h-implement-triage-workflow
submodules:
  - RepoRelay
---

# Implement Notification Routing (Phase 5)

## Problem/Goal

Add intelligent notification routing based on priority buckets to reduce developer fatigue from blanket notifications. High-priority vulnerabilities get immediate alerts while low-priority items are batched into digests.

**Reference**: `sessions/docs/vulnerability-prioritization-strategy.md` - Part 6 (Phase 5)

## Success Criteria
- [x] Create PriorityRouter service for notification routing
- [x] Route notifications based on priority bucket (P0/P1 = immediate, P2-P4 = digest)
- [x] Suppress notifications for auto-accepted findings
- [x] Implement digest mode for low-priority items (daily/weekly summary)
- [x] Add notification rule configuration settings
- [x] Create priority-aware notification templates
- [x] Integrate with existing notification system (email, Slack, webhooks)
- [x] Unit tests for routing logic

## Context Manifest

### How Notifications Currently Work: DefectDojo Notification System

DefectDojo has a comprehensive multi-channel notification system that routes alerts through email, Slack, Microsoft Teams, webhooks, and in-app alerts. Understanding this existing infrastructure is critical for implementing priority-aware routing.

**Notification Architecture - Manager Pattern:**

The notification system uses a manager pattern with specialized sub-managers for each channel:

1. **Entry Point** (`dojo/notifications/helper.py:48-96`): `create_notification()` function
   - Central factory that accepts event type, finding/test/engagement/product, recipients, and kwargs
   - Routes to pluggable NotificationManager class (configurable via `NOTIFICATION_MANAGER` setting)
   - Default manager: `NotificationManager` class

2. **NotificationManager** (`dojo/notifications/helper.py:620-876`): Main orchestrator
   - `_process_notifications()` method dispatches to channel-specific managers
   - Determines recipients based on product/product_type permissions and user notification settings
   - Supports both system-level broadcasts and user-specific notifications
   - User preferences stored in Notifications model (per-event subscription choices)

3. **Channel-Specific Managers** (all in `dojo/notifications/helper.py`):
   - `EmailNotificationManger` (lines 367-414): Uses Django EmailMessage with HTML templates
   - `SlackNotificationManger` (lines 198-314): Posts to Slack API (user DMs or system channel)
   - `MSTeamsNotificationManger` (lines 316-364): Webhook-based Microsoft Teams integration
   - `WebhookNotificationManger` (lines 416-573): Generic webhook delivery with retry logic
   - `AlertNotificationManger` (lines 575-618): In-app alerts (Alerts model)

4. **Template Rendering** (`dojo/notifications/helper.py:135-176`): `_create_notification_message()`
   - Loads Django templates from `dojo/templates/notifications/{channel}/{event}.tpl`
   - Falls back to `other.tpl` if event-specific template doesn't exist
   - Available channels: `mail`, `slack`, `msteams`, `webhooks`, `alert`
   - Example: SLA breach uses `notifications/mail/sla_breach.tpl` and `notifications/slack/sla_breach.tpl`

**Notification Event Registration:**

Events are defined as fields in the Notifications model (`dojo/models.py:5301-5330`):

```python
class Notifications(models.Model):
    product_added = MultiSelectField(choices=NOTIFICATION_CHOICES, default=DEFAULT_NOTIFICATION)
    scan_added = MultiSelectField(choices=NOTIFICATION_CHOICES, default=DEFAULT_NOTIFICATION)
    sla_breach = MultiSelectField(choices=NOTIFICATION_CHOICES, default=DEFAULT_NOTIFICATION)
    sla_breach_combined = MultiSelectField(choices=NOTIFICATION_CHOICES, default=DEFAULT_NOTIFICATION)
    # ... 15+ other event types
```

Each field stores user's channel preferences: `['alert', 'mail', 'slack', 'msteams', 'webhooks']`

**NOTIFICATION_CHOICES** are defined at the top of `dojo/models.py` (around line 50):
```python
NOTIFICATION_CHOICES = (
    ("alert", "alert"),
    ("mail", "mail"),
    ("slack", "slack"),
    ("msteams", "msteams"),
    ("webhooks", "webhooks"),
)
```

**Critical Pattern for Adding New Events:**

To add a new notification event (e.g., `priority_alert`), you must:

1. Add a new `MultiSelectField` to `Notifications` model (`dojo/models.py:5301+`)
2. Create migration: `python manage.py makemigrations`
3. Update `merge_notifications_list()` method (`dojo/models.py:5342-5371`) to merge the new field
4. Create templates for each channel:
   - `dojo/templates/notifications/mail/priority_alert.tpl`
   - `dojo/templates/notifications/slack/priority_alert.tpl`
   - `dojo/templates/notifications/msteams/priority_alert.tpl`
   - `dojo/templates/notifications/webhooks/priority_alert.tpl`
   - `dojo/templates/notifications/alert/priority_alert.tpl`

**Real-World Example - SLA Breach Notifications:**

The SLA breach system provides a perfect reference implementation for priority routing:

**Celery Beat Schedule** (`dojo/settings/settings.dist.py:1238-1241`):
```python
"compute-sla-age-and-notify": {
    "task": "dojo.tasks.async_sla_compute_and_notify_task",
    "schedule": crontab(hour=7, minute=30),  # Daily at 7:30 AM
},
```

**Task Implementation** (`dojo/tasks.py:173-181`):
```python
@app.task
def async_sla_compute_and_notify_task(*args, **kwargs):
    logger.debug("Computing SLAs and notifying as needed")
    try:
        system_settings = System_Settings.objects.get()
        if system_settings.enable_finding_sla:
            sla_compute_and_notify(*args, **kwargs)  # Calls dojo.utils function
    except Exception:
        logger.exception("An unexpected error was thrown calling the SLA code")
```

**Notification Dispatch** (`dojo/utils.py:1941-1967`):
```python
# Individual SLA breach notifications
for n in comb_notif_kind:
    title = _notification_title_for_finding(n.finding, kind, n.finding.sla_days_remaining())
    create_notification(
        event="sla_breach",  # Maps to Notifications.sla_breach field
        title=title,
        finding=n.finding,
        url=reverse("view_finding", args=(n.finding.id,)),
    )

# Combined SLA breach notification (batch mode)
create_notification(
    event="sla_breach_combined",  # Maps to Notifications.sla_breach_combined field
    title=title_combined,
    product=product,
    findings=findings_list,  # Multiple findings in one notification
    breach_kind=kind,
)
```

**Templates** (showing how to pass data to templates):

`dojo/templates/notifications/mail/sla_breach.tpl` (lines 1-58):
- Receives `finding`, `sla`, `sla_age`, `user`, `system_settings` in template context
- Uses Django template tags: `{% load i18n %}`, `{% url 'view_finding' finding.id as finding_url %}`
- HTML email format with links to finding detail page

`dojo/templates/notifications/slack/sla_breach.tpl` (lines 1-14):
- Plain text format optimized for Slack
- Uses `{% blocktranslate trimmed %}` for internationalization

**Key Insight for Phase 5:**

The SLA breach implementation shows two notification modes:
1. **Immediate individual alerts** (`sla_breach` event) - one notification per finding
2. **Batch digest mode** (`sla_breach_combined` event) - grouped by product/product_type

This is exactly what we need for priority routing:
- **P0/P1**: Immediate individual alerts → new event `priority_alert_immediate`
- **P2**: Standard notification with 1-hour delay → new event `priority_alert_standard`
- **P3/P4**: Daily/weekly digests → new events `priority_digest_daily`, `priority_digest_weekly`

### How Priority Scoring Works: Finding Model Fields

**Priority Fields** (`dojo/models.py:3595-3614`):

Three fields added in Phase 1 migration (`dojo/db_migrations/0259_finding_priority_fields.py`):

```python
PRIORITY_BUCKET_CHOICES = (
    ('P0', _('Critical')),
    ('P1', _('High')),
    ('P2', _('Medium')),
    ('P3', _('Low')),
    ('P4', _('Minimal')),
)

priority_score = models.IntegerField(
    default=0,
    db_index=True,  # Important: indexed for efficient filtering
    verbose_name=_("Priority Score"),
    help_text=_("Computed priority score combining tier, severity, and modifiers (0-1000+)")
)

priority_bucket = models.CharField(
    max_length=10,
    choices=PRIORITY_BUCKET_CHOICES,
    default='P3',
    db_index=True,  # Important: indexed for filtering in PriorityRouter
    verbose_name=_("Priority Bucket"),
    help_text=_("Priority bucket based on score: P0 (>=500), P1 (300-499), P2 (150-299), P3 (50-149), P4 (<50)")
)

priority_calculated_at = models.DateTimeField(
    null=True,
    blank=True,
    verbose_name=_("Priority Calculated At"),
    help_text=_("Timestamp when priority score was last calculated")
)
```

**Scoring Logic** (`dojo/finding/priority_scorer.py:80-99`):

```python
class PriorityScorer:
    def calculate(self, finding: "Finding", repository: Optional["Repository"] = None) -> int:
        # Get effective tier weight (5.0 for tier1, down to 0.2 for archived)
        tier_weight = self._get_effective_tier_weight(finding, repository)

        # Get severity base score (Critical=100, High=75, Medium=50, Low=25, Info=10)
        severity_score = self.SEVERITY_SCORES.get(finding.severity, 25)

        # Calculate base score
        base_score = tier_weight * severity_score
        # ... applies modifiers (KEV +150, EPSS +75, SLA breach +50, etc.)
        return int(total_score)
```

**Bucket Thresholds** (`dojo/finding/priority_scorer.py:50-57`):
- P0: >= 500 (Critical tier1 findings, or tier2 with KEV)
- P1: 300-499 (High severity tier1, Critical tier2)
- P2: 150-299 (Medium/High tier2, Critical tier3)
- P3: 50-149 (Most tier3/tier4 findings)
- P4: < 50 (Low/Info findings, archived repos)

### How Triage Workflow Works: State Machine and History Tracking

**Triage State Fields** (`dojo/models.py:3616-3648`):

Added in Phase 2 migration (`dojo/db_migrations/0260_finding_triage_workflow_fields.py`):

```python
TRIAGE_STATE_CHOICES = (
    ('pending', _('Pending Review')),
    ('escalated', _('Escalated')),
    ('assigned', _('Assigned for Review')),
    ('deferred', _('Deferred')),
    ('accepted', _('Risk Accepted')),
    ('dismissed', _('Dismissed')),
)

triage_state = models.CharField(
    max_length=20,
    choices=TRIAGE_STATE_CHOICES,
    default='pending',
    db_index=True,  # Indexed for notification suppression queries
    verbose_name=_("Triage State"),
    help_text=_("Current triage workflow state")
)

triage_assigned_to = models.ForeignKey(
    'Dojo_User',
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name='assigned_findings',
    verbose_name=_("Triage Assigned To"),
    help_text=_("User assigned to triage this finding")
)

triage_due_date = models.DateField(
    null=True,
    blank=True,
    verbose_name=_("Triage Due Date"),
    help_text=_("Due date for triage completion")
)

triage_reason = models.TextField(
    blank=True,
    default='',
    verbose_name=_("Triage Reason"),
    help_text=_("Explanation for triage decision")
)

auto_triage_rule = models.CharField(
    max_length=100,
    blank=True,
    default='',
    verbose_name=_("Auto Triage Rule"),
    help_text=_("Name of the auto-triage rule that created this decision")
)

auto_triage_confidence = models.IntegerField(
    null=True,
    blank=True,
    validators=[MinValueValidator(0), MaxValueValidator(100)],
    verbose_name=_("Auto Triage Confidence"),
    help_text=_("Confidence level (0-100%) of the auto-triage decision")
)
```

**State Transition Logic** (`dojo/finding/triage_service.py:24-51`):

```python
VALID_TRANSITIONS = {
    'pending': {
        'escalate': 'escalated',
        'assign': 'assigned',
        'defer': 'deferred',
        'accept': 'accepted',
        'dismiss': 'dismissed',
    },
    'escalated': {
        'assign': 'assigned',
    },
    'assigned': {
        'defer': 'deferred',
        'accept': 'accepted',
        'dismiss': 'dismissed',
    },
    'deferred': {
        'reopen': 'pending',
        'assign': 'assigned',
    },
    'dismissed': {
        'reopen': 'pending',
    },
    'accepted': {
        'reopen': 'pending',
    },
}
```

**TriageHistory Model** (`dojo/models.py:3710-3747`):

Audit trail for all triage decisions, created in Phase 2 migration (`dojo/db_migrations/0261_triage_history_model.py`):

```python
class TriageHistory(models.Model):
    ACTION_CHOICES = (
        ('created', _('Finding Created')),
        ('auto_triaged', _('Auto-Triaged')),
        ('escalated', _('Escalated')),
        ('assigned', _('Assigned')),
        ('deferred', _('Deferred')),
        ('accepted', _('Risk Accepted')),
        ('dismissed', _('Dismissed')),
        ('reopened', _('Reopened')),
    )

    finding = models.ForeignKey(Finding, on_delete=models.CASCADE, related_name='triage_history')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    previous_state = models.CharField(max_length=20)
    new_state = models.CharField(max_length=20)
    reason = models.TextField(blank=True, default='')
    rule_name = models.CharField(max_length=100, blank=True, default='')
    confidence = models.IntegerField(null=True, blank=True, validators=[...])
    performed_by = models.ForeignKey(Dojo_User, null=True, blank=True, on_delete=models.SET_NULL)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-performed_at']  # Newest first
```

**Triage Service Functions** (`dojo/finding/triage_service.py`):

Key functions for notification suppression logic:

```python
def perform_auto_triage(finding, decision, rule_name, reason, confidence, save=True):
    """
    Apply auto-triage decision (called by AutoTriageEngine).
    Maps decision to triage_state:
    - 'ACCEPT_RISK' → 'accepted' (suppress notifications)
    - 'DISMISS' → 'dismissed' (suppress notifications)
    - 'ESCALATE' → 'escalated' (send notification)
    - 'PENDING' → 'pending' (send notification)

    Returns: Updated Finding instance
    """
    # Lines 229-319 show state update + TriageHistory creation
```

**Critical for Phase 5:**

The `triage_state == 'accepted'` check is the **suppression condition** for auto-accepted findings. The PriorityRouter should check this before sending any notification:

```python
if finding.triage_state == 'accepted':
    return None  # Suppress all notifications for accepted findings
```

### How to Integrate PriorityRouter: Service Location and Hooks

**Where to Create PriorityRouter Service:**

Following DefectDojo's module organization pattern, create a new module:

**Location:** `dojo/finding/priority_router.py`

**Rationale:**
- Existing finding-related services are in `dojo/finding/`:
  - `dojo/finding/priority_scorer.py` (Phase 1 - priority scoring)
  - `dojo/finding/triage_service.py` (Phase 2 - triage workflow)
  - `dojo/finding/helper.py` (core finding operations)
- Priority routing is finding-centric logic, not notification infrastructure
- Keeps related prioritization features co-located

**Integration Points for Notification Routing:**

There are two primary hooks where findings trigger notifications:

**1. Scan Import/Re-Import** (`dojo/importers/base_importer.py` and `default_importer.py`):

When parsers create/update findings during scan imports, notifications are triggered via:

```python
from dojo.notifications.helper import create_notification

# In base_importer.py or reimporter processing
if new_findings:
    create_notification(
        event="scan_added",
        title=f"Scan added: {test.scan_type}",
        finding=finding,  # or findings list
        test=test,
        url=reverse("view_test", args=(test.id,)),
    )
```

**Hook Location:** After finding save/update, before `create_notification()` call

**Integration Strategy:**
```python
from dojo.finding.priority_router import route_finding_notification

# Instead of direct create_notification
for finding in new_findings:
    route_finding_notification(finding, event="scan_added")  # Handles routing internally
```

**2. Manual Finding Creation** (`dojo/finding/views.py` and `dojo/finding/helper.py`):

When users manually create findings via UI or API:

```python
# After finding.save()
create_notification(
    event="other",  # Generic event for manual creation
    title=f"New finding: {finding.title}",
    finding=finding,
    url=reverse("view_finding", args=(finding.id,)),
)
```

**Hook Location:** In `dojo/finding/helper.py:post_process_finding_save()` function

**3. Triage State Changes** (`dojo/finding/triage_service.py`):

Currently, triage actions don't trigger notifications. Phase 5 should add this:

```python
# In perform_triage_action() after successful state change
if new_state == 'escalated':
    from dojo.finding.priority_router import route_finding_notification
    route_finding_notification(finding, event="priority_alert_immediate")
```

**Hook Location:** `dojo/finding/triage_service.py:190-226` in `perform_triage_action()`

### Celery Beat Scheduling for Digests: Periodic Task Configuration

**Celery Beat Configuration** (`dojo/settings/settings.dist.py:1214-1268`):

DefectDojo uses Celery Beat for periodic tasks. Schedule is defined in `CELERY_BEAT_SCHEDULE` dictionary:

```python
from datetime import timedelta
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "compute-sla-age-and-notify": {
        "task": "dojo.tasks.async_sla_compute_and_notify_task",
        "schedule": crontab(hour=7, minute=30),  # Daily at 7:30 AM
    },
    "add-alerts": {
        "task": "dojo.tasks.add_alerts",
        "schedule": timedelta(hours=1),  # Hourly
    },
    # ... more tasks
}
```

**For Priority Digests, Add:**

```python
"send-priority-daily-digest": {
    "task": "dojo.finding.priority_router.send_priority_digest",
    "schedule": crontab(hour=9, minute=0),  # 9:00 AM daily (configurable via DD_NOTIFICATION_DAILY_DIGEST_TIME)
    "kwargs": {"digest_type": "daily"},
},
"send-priority-weekly-digest": {
    "task": "dojo.finding.priority_router.send_priority_digest",
    "schedule": crontab(hour=9, minute=0, day_of_week=1),  # Monday 9:00 AM (configurable via DD_NOTIFICATION_WEEKLY_DIGEST_DAY)
    "kwargs": {"digest_type": "weekly"},
},
```

**Celery Task Decorator Pattern** (`dojo/tasks.py:173` example):

```python
from dojo.celery import app

@app.task
def send_priority_digest(digest_type="daily"):
    """
    Send priority digest notifications.

    Args:
        digest_type: 'daily' or 'weekly'
    """
    from dojo.finding.priority_router import PriorityRouter
    router = PriorityRouter()

    if digest_type == "daily":
        router.send_daily_digest()
    elif digest_type == "weekly":
        router.send_weekly_digest()
```

**Settings for Digest Configuration:**

Add to `dojo/settings/settings.dist.py` environment variable definitions (around line 60-110):

```python
DD_NOTIFICATION_P0_P1_IMMEDIATE=(bool, True),
DD_NOTIFICATION_P2_DELAY_MINUTES=(int, 60),
DD_NOTIFICATION_DAILY_DIGEST_TIME=(str, "09:00"),
DD_NOTIFICATION_WEEKLY_DIGEST_DAY=(str, "monday"),
DD_NOTIFICATION_SUPPRESS_AUTO_ACCEPTED=(bool, True),
```

Then in settings body (around line 1200+):

```python
NOTIFICATION_P0_P1_IMMEDIATE = env("DD_NOTIFICATION_P0_P1_IMMEDIATE")
NOTIFICATION_P2_DELAY_MINUTES = env("DD_NOTIFICATION_P2_DELAY_MINUTES")
NOTIFICATION_DAILY_DIGEST_TIME = env("DD_NOTIFICATION_DAILY_DIGEST_TIME")
NOTIFICATION_WEEKLY_DIGEST_DAY = env("DD_NOTIFICATION_WEEKLY_DIGEST_DAY")
NOTIFICATION_SUPPRESS_AUTO_ACCEPTED = env("DD_NOTIFICATION_SUPPRESS_AUTO_ACCEPTED")
```

**Accessing Settings in Code:**

```python
from django.conf import settings

if settings.NOTIFICATION_SUPPRESS_AUTO_ACCEPTED:
    if finding.triage_state == 'accepted':
        return None  # Suppress
```

### Database Considerations: Digest Tracking

**Challenge:** Tracking which findings have been included in digests

**Solution:** Add a simple tracking model or use Finding fields

**Option 1: DigestQueue Model** (Recommended)

```python
# Add to dojo/models.py
class PriorityDigestQueue(models.Model):
    """Tracks findings pending digest notification."""
    finding = models.ForeignKey(Finding, on_delete=models.CASCADE)
    digest_type = models.CharField(max_length=10, choices=[('daily', 'Daily'), ('weekly', 'Weekly')])
    queued_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['digest_type', 'sent_at']),  # Query unsent items efficiently
        ]
```

**Migration:** `python manage.py makemigrations` creates `dojo/db_migrations/0264_priority_digest_queue.py`

**Option 2: Finding Field** (Simpler but less flexible)

Add to Finding model:
```python
last_digest_notification = models.DateTimeField(null=True, blank=True)
```

**Trade-offs:**
- **DigestQueue model**: More flexible, supports retry logic, audit trail
- **Finding field**: Simpler, but harder to track "what was in each digest"

**Recommendation:** Use DigestQueue model for proper tracking.

### Technical Reference Details

#### Files to Create

1. **`dojo/finding/priority_router.py`** - PriorityRouter service
2. **`dojo/templates/notifications/mail/priority_alert_immediate.tpl`** - Email template for P0/P1
3. **`dojo/templates/notifications/slack/priority_alert_immediate.tpl`** - Slack template for P0/P1
4. **`dojo/templates/notifications/mail/priority_digest_daily.tpl`** - Daily digest email
5. **`dojo/templates/notifications/mail/priority_digest_weekly.tpl`** - Weekly digest email
6. **`unittests/test_priority_router.py`** - Unit tests

#### Files to Modify

1. **`dojo/models.py`**
   - Add new notification event fields to `Notifications` model (line ~5321)
   - Update `merge_notifications_list()` method (line ~5342)
   - Add `PriorityDigestQueue` model (if using Option 1)

2. **`dojo/settings/settings.dist.py`**
   - Add environment variable definitions (line ~90)
   - Add settings assignments (line ~1200)
   - Add Celery Beat schedule entries (line ~1238)

3. **`dojo/finding/helper.py`**
   - Integrate `route_finding_notification()` in `post_process_finding_save()` function

4. **`dojo/importers/base_importer.py`** and **`dojo/importers/default_importer.py`**
   - Replace direct `create_notification()` calls with `route_finding_notification()`

5. **`dojo/finding/triage_service.py`**
   - Add notification trigger for escalated findings (line ~220)

#### Database Migration Sequence

1. **Migration 0264**: Add notification event fields to Notifications model
2. **Migration 0265**: Add PriorityDigestQueue model (if using)

#### API Endpoints (Future Enhancement)

While not strictly required for Phase 5, consider adding:

- `POST /api/v2/findings/{id}/send_priority_notification/` - Manual trigger
- `GET /api/v2/priority_digest/preview/` - Preview digest before sending

#### Configuration Defaults

Recommended defaults for production:

```python
DD_NOTIFICATION_P0_P1_IMMEDIATE=True           # Always send immediately
DD_NOTIFICATION_P2_DELAY_MINUTES=60            # 1-hour delay for P2
DD_NOTIFICATION_DAILY_DIGEST_TIME="09:00"      # 9 AM local time
DD_NOTIFICATION_WEEKLY_DIGEST_DAY="monday"     # Monday mornings
DD_NOTIFICATION_SUPPRESS_AUTO_ACCEPTED=True    # Don't notify for auto-accepted
```

### Implementation Checklist

**Phase 5.1 - Core Service (Week 1)**
- [ ] Create `dojo/finding/priority_router.py` with `PriorityRouter` class
- [ ] Implement `route_finding_notification()` method with bucket-based routing
- [ ] Add suppression logic for `triage_state == 'accepted'`
- [ ] Create `PriorityDigestQueue` model and migration

**Phase 5.2 - Event Registration (Week 2)**
- [ ] Add 4 new fields to `Notifications` model: `priority_alert_immediate`, `priority_alert_standard`, `priority_digest_daily`, `priority_digest_weekly`
- [ ] Update `merge_notifications_list()` method
- [ ] Create migration for Notifications model changes
- [ ] Add settings to `settings.dist.py`

**Phase 5.3 - Templates (Week 2)**
- [ ] Create mail templates for immediate/standard/daily/weekly
- [ ] Create Slack templates
- [ ] Create MSTeams templates (optional)
- [ ] Create webhook templates (JSON format)

**Phase 5.4 - Integration (Week 3)**
- [ ] Modify `dojo/finding/helper.py` to use router
- [ ] Modify `dojo/importers/base_importer.py` to use router
- [ ] Add escalation notification to `triage_service.py`
- [ ] Add Celery Beat schedule entries

**Phase 5.5 - Digest Implementation (Week 3)**
- [ ] Implement `send_daily_digest()` method
- [ ] Implement `send_weekly_digest()` method
- [ ] Create Celery tasks `send_priority_digest`
- [ ] Test digest queuing and dequeuing

**Phase 5.6 - Testing (Week 4)**
- [ ] Unit tests for routing logic (all 5 priority buckets)
- [ ] Unit tests for suppression logic
- [ ] Integration tests for digest generation
- [ ] Manual testing with real findings
- [ ] Performance testing with 10,000+ findings

### Key Design Decisions

**1. Why Not Modify NotificationManager Directly?**

The existing NotificationManager is infrastructure code used by 18+ different event types across the entire application. Injecting priority-specific logic there would:
- Create coupling between notification infrastructure and vulnerability prioritization business logic
- Require modifying a stable, widely-used system
- Make it harder to maintain both systems independently

Instead, PriorityRouter is a **domain service** that uses NotificationManager as a dependency.

**2. Why Separate Events for Each Priority Bucket?**

Each event (`priority_alert_immediate`, `priority_alert_standard`, etc.) allows users to customize channel preferences:
- Security team might want P0/P1 on Slack + Email
- Developers might want only email for P3/P4 digests
- Executives might want only weekly summaries

This follows DefectDojo's existing pattern (see `sla_breach` vs `sla_breach_combined`).

**3. Why Use PriorityDigestQueue Instead of Filtering Findings Directly?**

Direct filtering has race conditions:
- Finding could be created after digest query but before send
- Finding could be updated between digest cycles
- No audit trail of "what was in each digest"

The queue pattern provides:
- Idempotent digest generation (retry-safe)
- Audit trail (when was finding queued/sent)
- Ability to preview digests before sending

**4. Why 1-Hour Delay for P2?**

P2 findings are important but not critical. The 1-hour delay allows:
- Batching multiple P2 findings from same scan
- Avoiding alert fatigue for high-volume scans
- Security team time to manually escalate if needed

This can be tuned via `DD_NOTIFICATION_P2_DELAY_MINUTES` setting.

## Technical Specification

### Notification Routing Rules

| Priority | Notification Type | Timing | Recipients |
|----------|------------------|--------|------------|
| P0 | Immediate alert | Real-time | Security team + repo owner |
| P1 | Immediate alert | Real-time | Security team |
| P2 | Standard notification | Within 1 hour | Security team |
| P3 | Daily digest | Once daily | Security team |
| P4 | Weekly digest | Once weekly | Optional |
| Auto-accepted | None | Suppressed | - |

### Service: PriorityRouter
```python
class PriorityRouter:
    def route_finding_notification(self, finding):
        """Determine notification routing based on priority."""
        if finding.triage_state == 'accepted':
            return None  # Suppress

        bucket = finding.priority_bucket
        if bucket in ['P0', 'P1']:
            return self._send_immediate(finding)
        elif bucket == 'P2':
            return self._queue_standard(finding)
        elif bucket == 'P3':
            return self._add_to_daily_digest(finding)
        else:
            return self._add_to_weekly_digest(finding)
```

### Configuration Settings
```python
DD_NOTIFICATION_P0_P1_IMMEDIATE = True
DD_NOTIFICATION_P2_DELAY_MINUTES = 60
DD_NOTIFICATION_DAILY_DIGEST_TIME = "09:00"
DD_NOTIFICATION_WEEKLY_DIGEST_DAY = "monday"
DD_NOTIFICATION_SUPPRESS_AUTO_ACCEPTED = True
```

### Celery Tasks
- `send_priority_digest` - Daily/weekly digest generation
- `check_sla_approaching` - SLA warning notifications

## User Notes

This task depends on Phase 2 (triage workflow) for triage states. It addresses the developer fatigue problem by reducing noise from low-priority vulnerabilities.

## Work Log
- [2025-11-25] Task created from strategy document
- [2025-11-26] Implementation complete:
  - Created PriorityRouter service (dojo/finding/priority_router.py)
  - Added PriorityDigestQueue model with unique constraint for race condition prevention
  - Added 4 notification event fields to Notifications model
  - Created migrations 0264 (PriorityDigestQueue) and 0265 (notification fields)
  - Added 5 settings + 3 Celery Beat schedule entries
  - Created 20 notification templates (mail, slack, webhooks, alert, msteams)
  - 21 unit tests passing
  - Code review: 0 critical issues, addressed race condition warning
