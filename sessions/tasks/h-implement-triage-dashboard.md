---
name: h-implement-triage-dashboard
branch: feature/triage-dashboard
status: pending
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
<!-- To be filled during implementation -->

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
