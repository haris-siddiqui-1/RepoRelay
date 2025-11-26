---
branch: feature/data-tables-component
status: completed
priority: medium
created: 2025-11-19
---

# Task: Enterprise Data Tables Component

**Status**: Pending
**Priority**: Medium
**Created**: 2025-11-19
**Branch**: feature/data-tables-component

## Overview

Create a reusable enterprise-grade data table component for DefectDojo that can handle large datasets with virtual scrolling, sticky headers, and modern interactions. This component will be used across all list views (Findings, Products, Engagements, Tests).

## Objectives

1. **Core Table Features**
   - Sticky header with frosted glass effect on scroll
   - Virtual scrolling for 100+ rows (performance)
   - Alternating row backgrounds (subtle 2% opacity)
   - Expandable rows with smooth height animation

2. **Data Display**
   - Monospace font for technical values (IDs, URLs)
   - Inline status badges with icon + text
   - Responsive column hiding on smaller screens
   - Sortable columns with visual indicators

3. **Interactions**
   - Multi-select with checkbox column
   - Bulk action bar that slides up when items selected
   - Row hover with subtle highlight
   - Click to expand row details

4. **Filtering & Search**
   - Filter bar with pills for active filters
   - Dropdown for adding new filters
   - Saved filter presets
   - Fuzzy search within table

## Success Criteria

### Performance
- [ ] Renders 1000+ rows without lag (virtual scrolling)
- [ ] Smooth 60fps scroll performance
- [ ] No layout shift on load (CLS < 0.1)

### Visual Quality
- [ ] Sticky header with backdrop-filter blur
- [ ] Custom scrollbar (8px, rounded, themed)
- [ ] Alternating rows barely visible (2% opacity)
- [ ] Monospace for IDs/URLs, sans-serif for text

### Interactions
- [ ] Checkbox select all works correctly
- [ ] Bulk action bar animates in from bottom
- [ ] Row expansion animates height smoothly
- [ ] Sort indicators show direction clearly

### Accessibility
- [ ] Keyboard navigation (arrow keys, Enter to expand)
- [ ] ARIA attributes for table semantics
- [ ] Focus visible on interactive elements
- [ ] Screen reader announces sort state

### Reusability
- [ ] Works with Django template data
- [ ] Configurable columns via data attributes
- [ ] Theme-aware (dark/light mode)
- [ ] Used in at least 2 different pages

## Technical Approach

### Component Architecture

```javascript
// Alpine.js component
Alpine.data('dataTable', (config) => ({
  data: [],
  selected: [],
  sortColumn: null,
  sortDirection: 'asc',
  expandedRows: [],

  // Virtual scrolling
  visibleStart: 0,
  visibleEnd: 50,
  rowHeight: 48,

  // Methods
  toggleSelect(id) { ... },
  toggleSelectAll() { ... },
  sort(column) { ... },
  expandRow(id) { ... },
  // ...
}))
```

### CSS Classes

```css
.dd-table-enterprise { /* Container */ }
.dd-table-header { /* Sticky with glass effect */ }
.dd-table-row { /* Alternating, expandable */ }
.dd-table-cell { /* Padding, alignment */ }
.dd-table-checkbox { /* Select column */ }
.dd-bulk-actions { /* Slide-up bar */ }
```

### Integration Points

- Findings list: `/finding` - Primary use case
- Products list: `/product`
- Engagements list: `/engagement`
- Tests list: `/test_calendar` (table view)

## Design System Compliance

Must match enterprise dashboard patterns:
- Colors: Dark mode first (#0f1419 bg, #1c2128 cards)
- Borders: 1px solid rgba(255,255,255,0.1)
- Typography: Plus Jakarta Sans for text, JetBrains Mono for technical
- Animations: 200ms cubic-bezier(0.4, 0, 0.2, 1)
- Hover: Background opacity change, not color change

## Dependencies

- Alpine.js 3.x (already installed)
- Tailwind CSS 3.x (already installed)
- Completed: Enterprise dashboard design system

## Notes

This component replaces the current DataTables jQuery implementation with a modern Alpine.js solution that matches the new design system. The classic dashboard can continue using DataTables while the modern UI uses this component.

## Work Log

- [2025-11-19] Task created from enterprise dashboard scope split
