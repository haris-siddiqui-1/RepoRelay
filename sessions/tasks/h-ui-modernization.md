---
branch: feature/ui-modernization
status: active
priority: high
created: 2025-01-17
---

# Task: DefectDojo UI Modernization - Full Overhaul

**Status**: Active
**Priority**: High
**Estimated Effort**: 4 months (500-590 hours)
**Created**: 2025-01-17
**Branch**: feature/ui-modernization

## Overview

Complete modernization of DefectDojo's user interface using cutting-edge web technologies while preserving all existing functionality. Transform from Bootstrap 3 + jQuery to Tailwind CSS + Alpine.js with a custom security-focused design system.

## Objectives

1. **Modern Technology Stack**
   - Replace Bootstrap 3 (EOL 2019) with Tailwind CSS 3.x
   - Replace legacy charting (Flot, Morris.js) with Chart.js 4.x
   - Implement Alpine.js for reactive interactions
   - Set up Vite build pipeline for fast development

2. **Visual Transformation**
   - Custom "DefectDojo Security UI" design system
   - Modern color palette focused on security and trust
   - Improved typography and spacing
   - Dark mode support

3. **Enhanced UX**
   - Mobile-first responsive design
   - Smooth animations and transitions
   - Better accessibility (WCAG 2.1 AA)
   - Improved performance

4. **Developer Experience**
   - Hot module replacement (HMR)
   - Component library with Storybook
   - Reduced CSS bloat (1,914 lines → ~500 lines)
   - Modern tooling and workflow

## Technology Stack

**Current (Before):**
- Bootstrap 3.4.1 (EOL 2019)
- Font Awesome 4.0
- jQuery 3.7.1 + jQuery UI
- Flot 0.8.3 (deprecated)
- Morris.js (deprecated)
- SB Admin 2 1.0.7 (2015)
- Chosen 1.8.7

**Target (After):**
- Tailwind CSS 3.x
- Heroicons (Tailwind's icon set)
- Alpine.js 3.x (15KB, reactive)
- Chart.js 4.x
- Vite 5.x (build tool)
- Custom Web Components
- Inter font (modern sans-serif)

## Implementation Phases

### Phase 1: Foundation & Infrastructure (Month 1, ~140 hours)

**Week 1-2: Build Pipeline**
- Install and configure Vite
- Set up Tailwind CSS with PostCSS
- Configure Alpine.js
- Set up HMR and development environment
- Create project structure (`dojo/frontend/`)

**Week 3-4: Design System**
- Define color palette and variables
- Typography system
- Spacing scale
- Component foundations
- Dark mode architecture
- Storybook setup

**Deliverables:**
- ✅ Vite configured and running
- ✅ Tailwind CSS compiling
- ✅ Design system specification document
- ✅ Development environment with HMR

### Phase 2: Core Components (Month 2, ~150 hours)

**Week 5-6: Layout Components**
- Modern navigation (sticky header, mobile menu)
- Sidebar redesign (collapsible, off-canvas)
- Breadcrumbs
- Footer
- Page layout templates

**Week 7-8: UI Components**
- Cards (multiple variants)
- Buttons (all states)
- Forms (inputs, selects, checkboxes, radios)
- Badges & pills
- Alerts & toasts
- Modals & dialogs
- Dropdowns
- Tables (responsive, sortable, filterable)

**Deliverables:**
- ✅ Complete component library
- ✅ Storybook documentation
- ✅ Reusable Alpine.js components
- ✅ Dark mode variants

### Phase 3: Feature Pages (Month 3, ~150 hours)

**Week 9-10: Dashboard Overhaul**
- ✅ Stat cards with trend indicators (4 enterprise-grade metric cards with glow effects)
- ✅ Modern charts (Chart.js) - Pie chart + trend line chart with date adapter
- ⏳ Activity feed
- ⏳ Quick actions
- ⏳ Recent findings widget
- ⏳ Product health indicators

**Dashboard Foundation Complete (2025-11-19)**:
- Enterprise dark-mode-first design with violet accent
- Plus Jakarta Sans + JetBrains Mono typography
- Command palette (Cmd+K)
- Collapsible sidebar navigation
- Dark/light mode toggle
- Glass morphism effects

**Week 11-12: Core Pages**
- Finding list (modern table with filters)
- Finding detail (card-based, timeline)
- Product list (grid + list views)
- Product detail (metrics cards)
- Engagement views
- Test views

**Deliverables:**
- ✅ Dashboard completely modernized
- ✅ All core pages redesigned
- ✅ Charts migrated to Chart.js
- ✅ Responsive on all devices

### Phase 4: Polish & Advanced Features (Month 4, ~120 hours)

**Week 13: Interactions**
- Page transitions
- Loading skeletons
- Micro-interactions
- Toast notifications
- Drag & drop (report builder)

**Week 14: Dark Mode**
- Complete dark mode implementation
- User preference toggle
- System preference detection
- Persistent storage

**Week 15: Mobile & Responsive**
- Mobile-first optimization
- Touch interactions
- Responsive tables
- Mobile navigation

**Week 16: Testing & Refinement**
- Visual regression testing
- Accessibility audit
- Cross-browser testing
- Performance optimization
- UAT and bug fixes

**Deliverables:**
- ✅ Polished interactions throughout
- ✅ Full dark mode support
- ✅ Excellent mobile experience
- ✅ Production-ready codebase

## Project Structure

```
dojo/frontend/
├── src/
│   ├── styles/
│   │   ├── tailwind.css          # Main Tailwind entry point
│   │   ├── components/           # Component-specific styles
│   │   └── utilities/            # Custom utilities
│   ├── js/
│   │   ├── alpine/
│   │   │   ├── components/       # Alpine components
│   │   │   └── stores/           # Alpine stores
│   │   ├── charts/               # Chart.js configurations
│   │   └── utils/                # Utility functions
│   └── components/
│       ├── data-table.js         # DataTable web component
│       ├── severity-badge.js     # Severity badge component
│       └── finding-card.js       # Finding card component
├── docs/
│   ├── design-system.md          # Design system documentation
│   ├── components.md             # Component usage guide
│   └── migration.md              # Migration guide
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
└── package.json
```

## Files to Create

### Configuration Files
1. `package.json` - Node dependencies
2. `vite.config.js` - Vite configuration
3. `tailwind.config.js` - Tailwind configuration
4. `postcss.config.js` - PostCSS configuration

### Source Files
5. `dojo/frontend/src/styles/tailwind.css` - Main CSS entry
6. `dojo/frontend/src/js/main.js` - Main JS entry
7. `dojo/frontend/src/js/alpine/components/*` - Alpine components

### Documentation
8. `DESIGN_SYSTEM.md` - Design system specification
9. `dojo/frontend/docs/components.md` - Component guide
10. `dojo/frontend/docs/migration.md` - Migration guide

### Templates (Gradually update ~100+ templates)
11. `dojo/templates/base.html` - Base template with new CSS/JS
12. `dojo/templates/dojo/dashboard.html` - Dashboard redesign
13. ... (systematic migration of all templates)

## Success Metrics

### Performance
- ✅ Build time < 2 seconds (Vite)
- ✅ HMR update < 50ms
- ✅ Page load < 1.5 seconds
- ✅ Bundle size < 100KB gzipped
- ✅ Lighthouse Performance > 95

### Code Quality
- ✅ Custom CSS reduced by 70% (1,914 → ~500 lines)
- ✅ Zero console errors
- ✅ WCAG 2.1 AA compliant
- ✅ 100% component test coverage

### User Experience
- ✅ Modern, professional appearance
- ✅ Smooth 60fps animations
- ✅ Excellent mobile experience
- ✅ Dark mode available
- ✅ Consistent design language

## Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Learning curve for new stack | High | Medium | Training week, pair programming, documentation |
| Build pipeline complexity | Medium | Low | Vite is simpler than Webpack, excellent docs |
| Template rewrite effort | High | High | Reusable components, systematic approach |
| User resistance to change | Medium | Low | Beta testing, feedback, gradual rollout |
| Performance regression | High | Low | Bundle analysis, lazy loading, optimization |

## Testing Strategy

### Manual QA
- 20 critical pages tested per phase
- Cross-browser (Chrome, Firefox, Safari, Edge)
- Responsive testing (mobile, tablet, desktop)
- Accessibility testing (keyboard, screen reader)

### Automated Testing
- Visual regression tests
- Component unit tests
- Integration tests
- Performance tests (Lighthouse CI)

## Rollout Plan

1. **Development** (Weeks 1-14) - Build and test
2. **Internal Beta** (Week 15) - Team testing
3. **External Beta** (Week 16) - Select users (10-20%)
4. **Full Rollout** (Week 17) - 100% of users
5. **Monitoring** (Week 18+) - Gather feedback, iterate

## Dependencies

**Required:**
- Node.js 18+ and npm/yarn
- Vite 5.x
- Tailwind CSS 3.x
- Alpine.js 3.x
- Chart.js 4.x
- Heroicons
- Inter font (Google Fonts)

**Optional:**
- Figma (for design mockups)
- Storybook (for component documentation)
- Percy or Chromatic (visual regression testing)

## Resources

**Team:**
- 1 Senior Frontend Developer (full-time) OR
- 2 Mid-level Frontend Developers (full-time)

**Timeline:** 16 weeks (4 months)
**Effort:** 500-590 hours

## Related Documentation

- Design System: `DESIGN_SYSTEM.md`
- Component Library: `dojo/frontend/docs/components.md`
- Migration Guide: `dojo/frontend/docs/migration.md`
- Tailwind Docs: https://tailwindcss.com/docs
- Alpine.js Docs: https://alpinejs.dev/
- Vite Docs: https://vitejs.dev/

## Notes

- This is a complete UI transformation, not an incremental upgrade
- All existing functionality must be preserved
- Focus on modern, security-focused visual design
- Mobile-first, responsive, accessible approach
- Performance and developer experience are priorities

## Context Manifest

### Technical Background
- DefectDojo currently uses Bootstrap 3 (EOL 2019) with 1,914 lines of custom CSS overrides
- Two deprecated charting libraries (Flot, Morris.js)
- Limited mobile responsiveness
- No formal design system
- Good accessibility foundation to preserve

### Key Decisions
- **Tailwind over Bootstrap 5**: More modern, flexible, better DX
- **Alpine.js over React/Vue**: Lightweight, works with Django templates, no SPA rewrite
- **Vite over Webpack**: Faster, simpler, better DX
- **Chart.js**: Modern, well-maintained charting library
- **Heroicons**: Tailwind's icon set, consistent design

### Critical Constraints
- Must preserve all existing functionality
- Must maintain Django template architecture (no SPA rewrite)
- Must maintain accessibility (WCAG 2.1 AA)
- Must work without JavaScript (progressive enhancement)
- Must support modern browsers only (no IE11)

**Status**: Ready to begin Phase 1
**Next Step**: Set up build pipeline and development environment
