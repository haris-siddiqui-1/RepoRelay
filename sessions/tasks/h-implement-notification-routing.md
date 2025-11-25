---
name: h-implement-notification-routing
branch: feature/notification-routing
status: pending
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
- [ ] Create PriorityRouter service for notification routing
- [ ] Route notifications based on priority bucket (P0/P1 = immediate, P2-P4 = digest)
- [ ] Suppress notifications for auto-accepted findings
- [ ] Implement digest mode for low-priority items (daily/weekly summary)
- [ ] Add notification rule configuration settings
- [ ] Create priority-aware notification templates
- [ ] Integrate with existing notification system (email, Slack, webhooks)
- [ ] Unit tests for routing logic

## Context Manifest
<!-- To be filled during implementation -->

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
