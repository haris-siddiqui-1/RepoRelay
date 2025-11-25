---
name: h-implement-priority-scoring
branch: feature/priority-scoring
status: pending
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
- [ ] Add priority_score, priority_bucket, priority_calculated_at fields to Finding model
- [ ] Create migration for new fields with appropriate indexes
- [ ] Implement PriorityScorer service class in `dojo/finding/priority_scorer.py`
- [ ] Create management command `calculate_priority_scores` for batch scoring
- [ ] Add Celery task for incremental scoring on finding create/update
- [ ] Unit tests for scoring algorithm with edge cases
- [ ] Backfill existing findings with priority scores

## Context Manifest
<!-- To be filled during implementation -->

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
- [2025-11-25] Task created from strategy document
