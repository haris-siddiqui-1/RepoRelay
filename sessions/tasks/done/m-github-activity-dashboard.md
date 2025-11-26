---
branch: feature/github-activity-dashboard
status: completed
priority: medium
created: 2025-11-19
---

# Task: GitHub Activity Dashboard Visualizations

**Status**: Pending
**Priority**: Medium
**Created**: 2025-11-19
**Branch**: feature/github-activity-dashboard

## Overview

Add GitHub-specific visualizations to the DefectDojo dashboard, leveraging the existing GitHub collector data (repositories, alerts, activity metrics). This builds on the enterprise dashboard foundation completed in `h-dashboard-refined-redesign.md`.

## Objectives

1. **Repository Activity Visualization**
   - Commit cards with avatar, message, branch, diff stats
   - PR status indicators (open/merged/closed)
   - Contributor graphs (horizontal bar with avatars)
   - Activity heatmap (calendar grid by day/hour)

2. **Security Alert Cards**
   - Three-tier visual system (Critical/Warning/Info)
   - Card anatomy: Status icon, Title, Description, CVSS badge, Time, Actions
   - Quick actions on hover (Dismiss, Assign, Create Ticket)

3. **Webhook Display**
   - Event log table (type, timestamp, status, response code, latency)
   - Payload viewer with syntax-highlighted JSON
   - Status indicators (pulsing for live, static for historical)
   - Retry visualization

## Success Criteria

### Repository Activity
- [ ] Commit cards display with avatar, message, branch pill, +/- stats
- [ ] PR status shows colored dots (green open, purple merged, grey closed)
- [ ] Contributor graph shows horizontal bars with avatar Y-axis
- [ ] Activity heatmap calendar renders intensity by day

### Security Alerts
- [ ] Critical alerts: Red 4px left border, filled icon, bold title
- [ ] Warning alerts: Orange border, outlined icon, medium weight
- [ ] Info alerts: Blue border, subtle icon, regular weight
- [ ] Hover reveals quick action buttons

### Webhooks
- [ ] Event log table with proper columns
- [ ] JSON payload in collapsible syntax-highlighted panel
- [ ] Response codes color-coded (2xx green, 4xx orange, 5xx red)
- [ ] Retry step indicators show attempt count

### Integration
- [ ] Uses existing GitHub collector data models (Repository, GitHubAlert)
- [ ] Respects existing RBAC permissions
- [ ] Matches enterprise dashboard design system (dark-mode-first, violet accent)

## Technical Context

### Data Sources

The dashboard view needs to query:
- `Repository` model with 47 enrichment fields
- `GitHubAlert` model for security alerts
- `GitHubAlertSync` model for sync status

### Existing Infrastructure

- Dashboard at `/dashboard_modern` with view in `dojo/home/views.py:72-109`
- GitHub collector in `dojo/github_collector/`
- Insights dashboard at `/github/insights/dashboard`
- Chart.js 4.4.1 with date-fns adapter already loaded

### Design System

Must follow established patterns:
- Colors: `#0f1419` background, `#1c2128` cards, `#8B5CF6` violet accent
- Typography: Plus Jakarta Sans + JetBrains Mono
- Cards: `enterprise-card` class with glass morphism
- Animations: 200ms transitions, staggered reveals

## Dependencies

- Completed: Enterprise dashboard foundation
- Required: GitHub collector data (repositories synced)
- Optional: WebSocket for real-time updates

## Notes

This task extracts GitHub-specific features from the original enterprise dashboard design brief. These visualizations complement the existing GitHub Insights Dashboard by providing activity-focused views rather than analytics.

## Work Log

- [2025-11-19] Task created from enterprise dashboard scope split
