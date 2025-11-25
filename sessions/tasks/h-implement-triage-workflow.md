---
name: h-implement-triage-workflow
branch: feature/triage-workflow
status: pending
created: 2025-11-25
depends_on:
  - h-implement-priority-scoring
submodules:
  - RepoRelay
---

# Implement Triage Workflow (Phase 2)

## Problem/Goal

Add triage workflow capabilities to the Finding model, integrate with existing auto-triage rules, and create an audit trail for triage decisions.

**Reference**: `sessions/docs/vulnerability-prioritization-strategy.md` - Part 4.1, 4.3

## Success Criteria
- [ ] Add triage workflow fields to Finding model (triage_state, assigned_to, due_date, reason)
- [ ] Add auto-triage tracking fields (auto_triage_rule, auto_triage_confidence)
- [ ] Create TriageHistory model for audit trail
- [ ] Integrate auto-triage rules with priority scoring
- [ ] Create AutoTriageEngine service that runs rules and records history
- [ ] Expose triage actions via REST API endpoints
- [ ] Unit tests for triage state transitions
- [ ] Backfill triage_state from existing under_review, risk_accepted flags

## Context Manifest
<!-- To be filled during implementation -->

## Technical Specification

### Data Model Changes (Finding)
```python
triage_state = models.CharField(max_length=20, choices=[
    ('pending', 'Pending Triage'),
    ('escalated', 'Escalated'),
    ('assigned', 'Assigned'),
    ('deferred', 'Deferred'),
    ('accepted', 'Risk Accepted'),
    ('dismissed', 'Dismissed'),
], default='pending', db_index=True)
triage_assigned_to = models.ForeignKey(Dojo_User, null=True, blank=True, on_delete=models.SET_NULL)
triage_due_date = models.DateField(null=True, blank=True)
triage_reason = models.TextField(blank=True)
auto_triage_rule = models.CharField(max_length=100, blank=True)
auto_triage_confidence = models.IntegerField(null=True, blank=True)
```

### New Model: TriageHistory
- finding (FK)
- action (created, auto_triaged, escalated, assigned, deferred, accepted, dismissed, reopened)
- previous_state, new_state
- reason, rule_name, confidence
- performed_by (FK), performed_at

### API Endpoints
- POST `/api/v2/findings/{id}/triage/` - Perform triage action
- GET `/api/v2/findings/{id}/triage_history/` - Get triage history
- POST `/api/v2/findings/bulk_triage/` - Bulk triage actions

## User Notes

This task depends on Phase 1 (priority scoring) being complete. The triage workflow enables manual and automated vulnerability management.

## Work Log
- [2025-11-25] Task created from strategy document
