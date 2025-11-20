---
name: h-implement-core-pages-modern-ui
branch: feature/ui-modernization
status: pending
created: 2025-01-20
---

# Implement Modern UI for Core Pages

## Problem/Goal

Dashboard and login now use modern UI (Tailwind CSS, Alpine.js, enterprise dark theme), but all other pages still use old Bootstrap 3 templates. When users navigate from the dashboard to Findings, Products, Engagements, or Tests, they revert to the legacy UI.

**Scope**: Create modern templates for the 4 core page types listed in h-ui-modernization.md Phase 3 (Week 11-12):
1. **Finding pages**: List view + detail view
2. **Product pages**: List view + detail view
3. **Engagement pages**: List view + detail view
4. **Test pages**: Calendar view + detail view

Each modern template must:
- Extend `base_modern.html`
- Use Tailwind CSS utility classes (NOT Bootstrap 3)
- Integrate the enterprise data table component (from m-data-tables-component.md)
- Match the enterprise design system (dark mode first, violet accent #8B5CF6)
- Include Alpine.js components for interactivity

## Success Criteria

### Finding Pages
- [ ] Finding list view uses modern template with enterprise data table component
- [ ] Finding detail view uses card-based layout with timeline
- [ ] Severity badges use modern styling (matching dashboard design)
- [ ] List view supports virtual scrolling for 1000+ findings
- [ ] Filters work with modern dropdown and pill UI

### Product Pages
- [ ] Product list view has grid + list toggle
- [ ] Product detail view shows metrics cards matching dashboard style
- [ ] Navigation between list and detail preserves modern UI
- [ ] Product list integrates enterprise data table component

### Engagement Pages
- [ ] Engagement list view uses modern template
- [ ] Engagement detail view matches enterprise card design
- [ ] Timeline view uses modern styling
- [ ] Integration with data table component

### Test Pages
- [ ] Test calendar view uses modern template
- [ ] Test detail view uses card-based layout
- [ ] Calendar interactions use Alpine.js (not jQuery)
- [ ] Test list integrates enterprise data table component

### Design System Compliance
- [ ] All pages extend base_modern.html
- [ ] All pages use Tailwind CSS (no Bootstrap 3 classes)
- [ ] Dark mode works correctly on all pages
- [ ] Violet accent color (#8B5CF6) used consistently
- [ ] Plus Jakarta Sans typography throughout
- [ ] Glass morphism effects on cards where appropriate

### Integration & Testing
- [ ] Data table component used in at least 4 list views (meets m-data-tables-component.md criteria)
- [ ] View functions updated to render modern templates
- [ ] Navigation from dashboard to all core pages shows modern UI
- [ ] No visual regression when switching between pages
- [ ] All interactive elements work (sorting, filtering, expanding)

## Context Manifest
<!-- Added by context-gathering agent -->

## User Notes

**Design Requirements** (from h-ui-modernization.md):
- Finding list: Modern table with filters, severity badges, virtual scrolling
- Finding detail: Card-based layout, timeline view, activity stream
- Product list: Grid + list toggle views, metrics cards
- Product detail: Metrics dashboard cards, engagement timeline
- Engagement views: Modern layout matching dashboard aesthetic
- Test views: Calendar view with modern interactions

**Existing Old Templates to Replace**:
- `view_finding.html` (86KB) → `view_finding_modern.html`
- `view_eng.html` (76KB) → `view_eng_modern.html`
- `view_test.html` (123KB) → `view_test_modern.html`
- `view_product_details.html` (35KB) → `view_product_details_modern.html`

**Integration with Data Tables Component**:
The `m-data-tables-component.md` task created a reusable Alpine.js data table component (demonstrated in `datatable_demo.html`). This component MUST be used in the list views for Findings, Products, Engagements, and Tests to meet the success criteria of "Used in at least 2 different pages".

**View Functions to Update**:
After creating templates, these view functions need to render the modern versions:
- Finding: `ListFindings` class (dojo/finding/views.py:292), `ViewFinding` class (line 417)
- Product: `product()` function (dojo/product/views.py:140), `view_product()` function (line 244)
- Engagement: `engagements()` function (dojo/engagement/views.py:191), `ViewEngagement` class (line 422)
- Test: `test_calendar()` function, `ViewTest` class

## Work Log
- [2025-01-20] Task created - Dashboard routing fixed, but core pages still use old Bootstrap 3 UI
