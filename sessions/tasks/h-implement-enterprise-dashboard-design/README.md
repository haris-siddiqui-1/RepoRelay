---
name: h-implement-enterprise-dashboard-design
branch: feature/enterprise-dashboard-design
status: complete-foundation
created: 2025-11-18
---

# Enterprise Security & GitHub Activity Dashboard - Sophisticated UI Redesign

> **Note (2025-11-19)**: Dashboard foundation is complete. Remaining items have been split into focused subtasks:
> - `h-github-activity-dashboard.md` - GitHub-specific visualizations (repo activity, webhooks, contributor graphs)
> - `h-data-tables-component.md` - Virtual scrolling tables with sticky headers
>
> See completed foundation work in: `sessions/tasks/done/h-dashboard-refined-redesign.md`

## Problem/Goal

Transform the DefectDojo modern dashboard into a sophisticated, enterprise-grade interface inspired by Tines' clean aesthetic and 2024-2025 enterprise SaaS design patterns. The current v1 implementation has the right foundation (Tailwind + Alpine.js, refined fonts, staggered animations) but needs to reach the next level of visual sophistication and interaction design.

**Core Philosophy**: Create "sophisticated simplicity" - generous white space, micromodule discipline, and progressive complexity. The interface should feel premium and engineered, not generic or templated.

**Target Aesthetic**: Interface that a security engineer would be proud to show in a board presentation - sophisticated, clear, and unmistakably premium.

## Success Criteria

### Visual Quality
- [x] Typography system with 6+ weights creates clear hierarchy (hero metrics at 48px down to captions at 12px) - Plus Jakarta Sans with 300-800 weights
- [x] Custom font implementation (Geist Sans, Roobert, Basier Circle, or Plus Jakarta Sans) - NOT Inter/Roboto - Plus Jakarta Sans + JetBrains Mono
- [x] Dark mode first with deep grey backgrounds (#0f1419), cards at #1c2128, never pure black - Implemented with CSS variables
- [x] Distinctive brand accent color implemented (violet/cyan/emerald) throughout interface - Violet #8B5CF6
- [ ] Aurora-inspired mesh gradients for empty states and backgrounds
- [ ] Subtle noise texture overlay for depth (CSS filter)

### Layout & Spacing
- [x] 4px base grid system with consistent spacing scale (4, 8, 16, 24, 32, 48, 64px) - Implemented in tailwind.config.js
- [x] Inverted L-shape layout with collapsible sidebar (200px→64px) and 64px top bar - Sidebar at 208px→64px, nav at 64px
- [x] 24px card padding, 16px gaps, 1px subtle borders (rgba(255,255,255,0.1)) - enterprise-card class
- [x] Max width 1440px container maintains elegance at all breakpoints - max-w-7xl (1280px)
- [x] Generous white space between sections (not cramped) - mb-16 gaps, py-12 padding

### Interactive Patterns
- [x] Page transitions: 200ms fade with 20px Y translation - slideUp animation with staggered delays
- [x] Card hover: Scale(1.02) with shadow elevation - enterprise-card:hover transform
- [x] Command palette (Cmd+K) with fuzzy search working - Full implementation with keyboard navigation
- [x] Skeleton screens matching final layout (show after 300ms delay) - .skeleton class defined
- [ ] Real-time updates with gentle pulse animation
- [ ] All animations respect prefers-reduced-motion

### Component Quality
- [ ] Top metrics bar with 4-5 hero metric cards showing sparklines and trend comparison
- [ ] Activity feed with chronological cards, event icons, hover expansion
- [ ] Security alert cards with three-tier visual system (not color-only)
- [ ] Repository activity visualization with commit cards, PR status, contributor graphs
- [ ] Data tables with sticky frosted glass header, virtual scrolling for 100+ rows
- [ ] Forms with proper focus states, error handling, inline validation

### Advanced Features
- [x] Glass morphism effects on overlays and sticky headers - Sidebar and command palette use backdrop-filter: blur
- [ ] Gradient borders with subtle animation on focus states
- [ ] Custom scrollbars (8px, rounded, themed)
- [ ] Inline editing with dotted underline on hover
- [ ] Multi-select with bulk action bar that slides up
- [ ] Toast notifications (bottom-right, max 3 stacked, 5s auto-dismiss)

### Technical Standards
- [ ] WCAG AA compliance for all color contrasts
- [ ] Lighthouse performance score >90
- [ ] No layout shift (CLS <0.1)
- [ ] All interactions <100ms response time
- [ ] Works in Chrome, Firefox, Safari, Edge
- [ ] Mobile responsive with fluid grid

### Polish & Distinctiveness
- [x] Interface does NOT look generic or templated - Dark-mode-first with custom violet accent
- [x] Has distinctive visual signature different from Bootstrap/Material UI - Command palette, glass morphism sidebar
- [x] Micro-interactions are polished and intentional - Staggered reveals, hover transforms
- [x] User reaction: "this looks like a modern enterprise SaaS product" - User feedback: "wow this is great"
- [x] Design feels "engineered" not "assembled from components" - Cohesive design system throughout

## Context Manifest

### How the Current Dashboard System Works

When a user navigates to `/dashboard_modern`, the request hits the `dashboard_modern` view function in `/Users/1haris.sid/defectdojo/RepoRelay/dojo/home/views.py` (lines 72-109). This function performs the following operations:

1. **Authentication & Authorization**: Uses `get_authorized_engagements(Permissions.Engagement_View)` and `get_authorized_findings(Permissions.Finding_View)` to fetch only data the user has permission to view. This is critical - all data displayed respects RBAC permissions.

2. **Data Collection**: The view computes 7-day rolling statistics:
   - `engagement_count`: Active engagements count
   - `finding_count`: New findings in last 7 days
   - `mitigated_count`: Closed findings in last 7 days
   - `accepted_count`: Risk-accepted findings in last 7 days

3. **Severity Aggregation**: Two key functions provide chart data:
   - `get_severities_all(findings)` returns a dict with counts for Critical/High/Medium/Low/Info
   - `get_severities_by_month(findings, today)` returns 6 months of trend data in format `[{'y': '2025-01', 'a': 10, 'b': 20, ...}]` where a=Critical, b=High, c=Medium, d=Low, e=Info

4. **Template Rendering**: Data is passed to `dojo/templates/dojo/dashboard_modern.html` which extends `base_modern.html`

The URL routing is defined in `/Users/1haris.sid/defectdojo/RepoRelay/dojo/home/urls.py` line 9:
```python
re_path(r"^dashboard_modern$", views.dashboard_modern, name="dashboard_modern"),
```

### Current Frontend Architecture

**Build Pipeline**: The frontend uses Vite 5.0 for bundling, configured in `/Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend/vite.config.js`. Entry points are:
- `src/js/main.js` - JavaScript entry
- `src/styles/tailwind.css` - CSS entry

Output goes to `../static/dist/` with hashed filenames for cache busting:
- CSS: `css/[name]-[hash].css` (currently `styles-CQtxVRrk.css`)
- JS: `js/[name]-[hash].js` (currently `main--lRnQmxy.js`)

To rebuild assets after changes:
```bash
cd dojo/frontend && npm run build
```

**Alpine.js Components**: Four Alpine.js components are registered in `/Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend/src/js/main.js`:

1. **darkMode** (`src/js/alpine/components/darkMode.js`): Toggle dark mode via `toggle()` method. Persists to localStorage, respects system preference, updates `document.documentElement` class. Usage: `x-data="darkMode"` with `@click="toggle"`.

2. **dropdown** (`src/js/alpine/components/dropdown.js`): Simple open/close toggle with Escape key support.

3. **modal** (`src/js/alpine/components/modal.js`): Modal with body scroll lock, Escape key close.

4. **toast** (`src/js/alpine/components/toast.js`): Notification system with type-based styling (info/success/warning/error), auto-dismiss after configurable duration. Usage: `show(message, type, duration)`.

**Chart.js Configuration**: Located in `/Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend/src/js/charts/index.js`. Default config uses `Inter, sans-serif` font family (needs updating). Provides utility functions:
- `createSeverityPieChart(element, severityData)`
- `createSeverityTrendChart(element, trendData)`
- `colors` object with semantic colors for charts

**Utility Functions**: `/Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend/src/js/utils/helpers.js` provides:
- `debounce()`, `throttle()` - Rate limiting
- `formatDate()`, `formatRelativeTime()` - Date formatting
- `copyToClipboard()`, `scrollToElement()` - UI utilities
- `fetchWithTimeout()` - HTTP utilities
- `formatNumber()`, `truncate()` - String utilities

### Current Typography & Font System

**Current Fonts** (need to be replaced):
- Display: `"Cormorant Garamond"` - Elegant serif, loaded via Google Fonts
- Sans: `"IBM Plex Sans"` - Clean sans-serif with weights 300/400/500/600
- Mono: `"JetBrains Mono"`, `"Fira Code"` - For code (keep this)

Fonts loaded in `base_modern.html` line 12:
```html
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
```

CSS custom properties in `base_modern.html` lines 33-34:
```css
--font-display: 'Cormorant Garamond', Georgia, serif;
--font-body: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
```

Tailwind font families in `tailwind.config.js` lines 123-127:
```javascript
fontFamily: {
  display: ['"Cormorant Garamond"', 'Georgia', 'ui-serif', 'serif'],
  sans: ['"IBM Plex Sans"', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
  mono: ['"JetBrains Mono"', '"Fira Code"', 'Consolas', 'Monaco', 'monospace'],
},
```

**Target Fonts**: Replace with Geist Sans, Roobert, Basier Circle, or Plus Jakarta Sans (avoid Inter/Roboto). Need to implement full 6-weight hierarchy: 300/400/500/600/700/800.

### Current Color Palette

**"Refined" Colors** (need to be replaced with dark-mode-first):
```javascript
// tailwind.config.js lines 141-152
'refined': {
  'warm-gray': '#F5F5F3',
  'sage': '#8B9B8E',
  'charcoal': '#2C2C2C',
  'accent': '#B4A7A0',
  'off-white': '#FAFAF9',
  'whisper': '#E8E8E6',
  'terracotta': '#C45653',
  'sage-green': '#6B8E75',
},
```

**DefectDojo Severity Colors** (already good):
- Critical: `#DC2626` (red-600)
- High: `#F97316` (orange-500) / `#EA580C` (orange-600)
- Medium: `#F59E0B` (amber-500) / `#D97706` (amber-600)
- Low: `#3B82F6` (blue-500) / `#2563EB` (blue-600)
- Info: `#64748B` (slate-500)

**Target Color System**:
- Dark background: `#0f1419` (never pure black)
- Card background: `#1c2128`
- Text on dark: `#F0F6FC` (high contrast for WCAG AA)
- Accent color: Violet `#8B5CF6`, Cyan `#06B6D4`, or Emerald `#10B981`
- Semantic: Success `#10B981`, Warning `#F59E0B`, Error `#EF4444`, Info `#3B82F6`
- Subtle border: `rgba(255,255,255,0.1)`

### Current Animation System

Defined in `tailwind.config.js` lines 173-191:
```javascript
animation: {
  'fade-in': 'fadeIn 0.6s ease-out',
  'slide-up': 'slideUp 0.6s ease-out',
  'scale-in': 'scaleIn 0.4s ease-out',
},
keyframes: {
  fadeIn: {
    '0%': { opacity: '0' },
    '100%': { opacity: '1' },
  },
  slideUp: {
    '0%': { opacity: '0', transform: 'translateY(20px)' },
    '100%': { opacity: '1', transform: 'translateY(0)' },
  },
  scaleIn: {
    '0%': { opacity: '0', transform: 'scale(0.95)' },
    '100%': { opacity: '1', transform: 'scale(1)' },
  },
},
```

Current usage in dashboard template with staggered delays (lines 14-20):
```css
.card-1 { animation-delay: 0ms; }
.card-2 { animation-delay: 100ms; }
/* ... up to chart-2 at 500ms */
```

**Target Animation System** (per design brief):
- Page transitions: 200ms fade with 20px Y translation
- Card hover: Scale(1.02) with shadow elevation
- New items: Slide in from top with fade (300ms ease-out)
- Skeleton screens: Show after 300ms delay
- Micro-interactions: Button press scale(0.98)
- Real-time updates: Gentle pulse animation
- Must respect `prefers-reduced-motion`

### Current Spacing & Layout

**Tailwind Spacing** (lines 168-172):
```javascript
spacing: {
  '18': '4.5rem',
  '88': '22rem',
  '128': '32rem',
},
```

**Border Radius** (lines 160-167):
```javascript
borderRadius: {
  'dd-sm': '0.125rem',  // 2px
  'dd': '0.25rem',      // 4px
  'dd-md': '0.375rem',  // 6px
  'dd-lg': '0.5rem',    // 8px
  'dd-xl': '0.75rem',   // 12px
  'dd-2xl': '1rem',     // 16px
},
```

**Current Layout** (`base_modern.html` lines 101-119):
- Nav: `h-20` (80px), `max-w-7xl`, `px-8 sm:px-12 lg:px-16`
- Main: `max-w-7xl`, `px-8 sm:px-12 lg:px-16`, `py-16`
- Dashboard grid: `gap-8`, `mb-16`

**Target Layout** (per design brief):
- 4px base grid: 4, 8, 16, 24, 32, 48, 64px spacing scale
- Inverted L-shape: Collapsible sidebar (200px→64px), 64px top bar
- Cards: 24px padding, 16px gaps
- Subtle borders: `1px solid rgba(255,255,255,0.1)`
- Max width: 1440px container

### Current Component Library

**Card Components** (`tailwind.css` lines 50-66 and 114-131):
```css
.dd-card { /* Standard card with shadow and border */ }
.dd-card-header { /* 24px padding with bottom border */ }
.dd-card-body { /* 24px padding */ }
.dd-card-footer { /* 12px vertical, 24px horizontal */ }

.refined-card { /* Gradient background with hover transform */ }
```

**Button Components** (lines 67-82):
```css
.dd-btn { /* Base button with focus ring */ }
.dd-btn-primary { /* Blue background */ }
.dd-btn-secondary { /* White background with border */ }
.dd-btn-danger { /* Red background */ }
```

**Badge Components** (lines 89-112):
```css
.dd-badge { /* Base pill badge */ }
.dd-badge-critical { /* Red severity */ }
.dd-badge-high { /* Orange severity */ }
.dd-badge-medium { /* Yellow severity */ }
.dd-badge-low { /* Blue severity */ }
.dd-badge-info { /* Gray severity */ }
```

**Table Components** (lines 133-152):
```css
.dd-table { /* Divided table */ }
.dd-table th { /* Uppercase headers */ }
.dd-table td { /* Whitespace nowrap */ }
```

**Alert Components** (lines 154-173):
```css
.dd-alert { /* Left-bordered alert */ }
.dd-alert-info/success/warning/error { /* Semantic variants */ }
```

**Utility Classes** (lines 176-223):
- `.dd-scrollbar` - Custom scrollbar (8px, rounded)
- `.dd-gradient-primary/critical` - Background gradients
- `.dd-transition-smooth` - 150ms transition
- `.dd-loading`, `.dd-skeleton` - Loading states

### Critical Files to Modify

**Primary Files** (will need significant changes):

1. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend/tailwind.config.js`
   - Replace font families with Geist Sans/Plus Jakarta Sans
   - Add dark-mode-first color palette (#0f1419, #1c2128)
   - Add distinctive accent color (violet/cyan/emerald)
   - Extend animations for enterprise patterns
   - Add 4px grid spacing scale

2. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend/src/styles/tailwind.css`
   - Update base body styles for dark-mode-first
   - Add glass morphism utilities
   - Add gradient border utilities
   - Add noise texture overlay utility
   - Add skeleton loader improvements
   - Update scrollbar for dark theme

3. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/templates/base_modern.html`
   - Replace Google Fonts link with new font choice
   - Update CSS custom properties for new colors
   - Add sidebar navigation structure
   - Add command palette markup (Cmd+K)
   - Add toast notification container

4. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/templates/dojo/dashboard_modern.html`
   - Redesign metrics cards with sparklines and trend pills
   - Add hero metrics bar (48px numbers)
   - Update chart configurations for dark theme
   - Add three-tier security alert system
   - Implement activity feed pattern

**Secondary Files** (will need updates):

5. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend/src/js/main.js`
   - Add command palette Alpine component
   - Add toast notification system component
   - Add sidebar toggle component

6. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend/src/js/charts/index.js`
   - Update default font to new font choice
   - Update color palette for dark theme
   - Add sparkline chart configuration

7. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend/src/js/alpine/components/darkMode.js`
   - Already well-implemented, may need minor adjustments for body class naming

8. `/Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend/src/js/alpine/components/toast.js`
   - Update to support max 3 stacked, auto-dismiss 5s, bottom-right positioning

### Dependencies & Resources

**Current NPM Packages** (`package.json`):
```json
{
  "dependencies": {
    "alpinejs": "^3.13.3",    // Keep - lightweight reactivity
    "chart.js": "^4.4.1",     // Keep - charting
    "heroicons": "^2.1.1"     // Keep - icon library
  },
  "devDependencies": {
    "@tailwindcss/forms": "^0.5.7",        // Keep - form styling
    "@tailwindcss/typography": "^0.5.10",  // Keep - prose styling
    "@tailwindcss/aspect-ratio": "^0.4.2", // Keep - aspect ratios
    "tailwindcss": "^3.4.0",               // Keep - CSS framework
    "vite": "^5.0.10"                      // Keep - bundler
  }
}
```

**Potential New Dependencies**:
- `fuse.js` - Fuzzy search for command palette
- `@radix-ui/react-*` - Accessible primitives (if using React islands)
- `chart.js/auto` - Already included

**CDN Resources** (currently in `base_modern.html` line 19):
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
```
Note: Chart.js is loaded both via CDN and npm bundle. Consider consolidating.

**Font Resources** (need to update):
- Current: Google Fonts (Cormorant Garamond, IBM Plex Sans)
- Target Options:
  - Geist Sans: `https://cdn.jsdelivr.net/npm/geist@1/dist/fonts/geist-sans/`
  - Plus Jakarta Sans: Google Fonts available
  - Basier Circle: Commercial font, requires license
  - Roobert: Commercial font, requires license

### Data Available to Dashboard Template

From `views.py` `dashboard_modern` function, the following context variables are passed:

```python
{
    "engagement_count": int,      # Active engagements
    "finding_count": int,         # New findings (7 days)
    "mitigated_count": int,       # Closed findings (7 days)
    "accepted_count": int,        # Risk accepted (7 days)
    "critical": int,              # Total critical findings
    "high": int,                  # Total high findings
    "medium": int,                # Total medium findings
    "low": int,                   # Total low findings
    "info": int,                  # Total info findings
    "by_month": list[dict],       # 6 months trend data
}
```

The `by_month` format:
```python
[
  {'y': '2024-06', 'a': 5, 'b': 10, 'c': 15, 'd': 3, 'e': 2, None: 0},
  {'y': '2024-07', 'a': 8, 'b': 12, 'c': 20, 'd': 5, 'e': 1, None: 0},
  # ... 6 months
]
# a=Critical, b=High, c=Medium, d=Low, e=Info
```

**For Enterprise Dashboard Enhancement**, the view may need to be extended to provide:
- Trend comparison (% change from previous period)
- Sparkline data points (daily granularity for 7-day charts)
- Recent activity feed items
- GitHub repository activity (if integrating with existing GitHub features)
- Top critical findings list for alert cards

### Dark Mode Implementation

Dark mode uses the `class` strategy (`tailwind.config.js` line 7):
```javascript
darkMode: 'class',
```

Implementation pattern:
1. Toggle adds/removes `dark` class on `document.documentElement`
2. CSS uses `dark:` prefix for dark variants
3. Persisted to `localStorage.darkMode`
4. Respects `prefers-color-scheme: dark` if no saved preference

Current body styles (`base_modern.html` lines 38-48):
```css
body {
  background-color: var(--color-warm-gray);  /* Light: #F5F5F3 */
}
body.dark {
  background-color: #1A1A1A;  /* Too dark - needs #0f1419 */
}
```

**Note**: Current dark mode uses `body.dark` class but Alpine component adds `dark` to `document.documentElement`. This is a bug - needs alignment.

### Build & Development Commands

```bash
# Development server with HMR
cd /Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend && npm run dev

# Production build
cd /Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend && npm run build

# Lint JavaScript
cd /Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend && npm run lint

# Format code
cd /Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend && npm run format

# Storybook (component documentation)
cd /Users/1haris.sid/defectdojo/RepoRelay/dojo/frontend && npm run storybook
```

After building, static files are at:
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/static/dist/css/`
- `/Users/1haris.sid/defectdojo/RepoRelay/dojo/static/dist/js/`

**Important**: When changing the build output filenames, update the `base_modern.html` template to reference the new hashed filenames:
```html
<link rel="stylesheet" href="{% static 'dist/css/styles-[NEW_HASH].css' %}">
<script type="module" src="{% static 'dist/js/main-[NEW_HASH].js' %}"></script>
```

### Implementation Strategy Notes

**Phased Approach Recommended**:

1. **Phase 1 - Foundation**: Update tailwind.config.js with new colors, fonts, spacing. Update CSS custom properties. Ensure dark mode works correctly.

2. **Phase 2 - Typography**: Install new font, update font families throughout, implement 6-weight hierarchy with proper sizing scale.

3. **Phase 3 - Color System**: Implement dark-mode-first palette, update all color references, add distinctive accent color.

4. **Phase 4 - Layout**: Add sidebar navigation, update container widths, implement 4px grid system.

5. **Phase 5 - Components**: Build hero metrics with sparklines, security alert cards, activity feed pattern.

6. **Phase 6 - Advanced Features**: Command palette (Cmd+K), glass morphism, gradient borders, custom scrollbars.

7. **Phase 7 - Animation & Polish**: Page transitions, hover states, skeleton loaders, microinteractions.

**Key Patterns to Preserve**:
- Alpine.js component registration pattern
- Django template inheritance (`{% extends %}`, `{% block %}`)
- Tailwind utility-first approach
- Chart.js for visualizations
- Authorization-aware data fetching in views

**Key Patterns to Change**:
- Light-mode-first to dark-mode-first
- Serif display font to modern sans-serif
- Warm neutral palette to cool/dark palette
- Simple cards to enterprise metric cards with sparklines
- Basic alerts to three-tier security alert system

### Accessibility Requirements

Per design brief WCAG AA compliance:
- Color contrast ratio 4.5:1 for normal text, 3:1 for large text
- Focus indicators: 2px accent color with 4px offset (already in `tailwind.css` line 44)
- Keyboard navigation: Escape key handlers already in modal/dropdown components
- Screen reader support: `.sr-only` class already defined (line 259)
- Reduced motion: Must add `@media (prefers-reduced-motion)` queries

### Performance Targets

Per design brief:
- Lighthouse score >90
- CLS (Cumulative Layout Shift) <0.1
- All interactions <100ms response time

Current potential issues:
- External font loading may cause layout shift
- Chart.js loaded twice (CDN + npm)
- No skeleton loaders implemented yet

Solutions:
- Use `font-display: swap` with size-adjusted fallback fonts
- Consolidate Chart.js loading
- Implement skeleton loaders matching final layout

## User Notes

### Full Design Brief

**UI Redesign Brief: Enterprise Security & GitHub Activity Dashboard**

Transform this DefectDojo fork into a sophisticated, modern interface inspired by Tines' clean aesthetic and 2024-2025 enterprise SaaS design patterns. Focus purely on visual design and interaction patterns.

#### Core Design Philosophy

Create a "sophisticated simplicity" aesthetic similar to Tines - generous white space, micromodule discipline, and progressive complexity. The interface should feel premium and engineered, not generic or templated.

#### Typography System

- **Primary Font**: Use Geist Sans, Roobert, Basier Circle, or Plus Jakarta Sans (avoid Inter/Roboto)
- **Monospace**: JetBrains Mono or Fira Code for all technical content
- **Scale**: 48px (hero metrics) → 32px (section headers) → 18px (subheaders) → 16px (body) → 14px (labels) → 12px (captions)
- **Weights**: Use 6+ weights for clear hierarchy. Bold (700) for metrics, Medium (500) for headers, Regular (400) for body
- **Implementation**: Variable fonts with responsive sizing

#### Color & Theming

- **Dark Mode First**: Deep grey backgrounds (#0f1419), never pure black. Cards at #1c2128
- **Accent System**: Choose distinctive brand color (avoid generic blue) - consider violet #8B5CF6, cyan #06B6D4, or emerald #10B981
- **Semantic Colors**: Success #10B981, Warning #F59E0B, Error #EF4444, Info #3B82F6
- **Subtle Gradients**: Aurora-inspired mesh gradients for empty states or backgrounds
- **Text**: High contrast - #F0F6FC on dark, careful attention to WCAG AA compliance

#### Layout Architecture

- **Framework**: Tailwind CSS with 4px base grid (4, 8, 16, 24, 32, 48, 64px spacing scale)
- **Pattern**: Inverted L-shape - collapsible left sidebar (200px collapsed to 64px), persistent top bar (64px), main canvas
- **Cards**: 24px internal padding, 16px gaps, subtle borders (1px solid rgba(255,255,255,0.1))
- **Max Width**: 1440px container for content, full-width for canvas views
- **Responsive**: Fluid grid that maintains elegance at all breakpoints

#### Dashboard Structure

**Top Metrics Bar**
- 4-5 large metric cards in a horizontal strip
- Hero number at 48px font weight 700
- Sparkline graph (no axes, just trend line)
- Period comparison as colored pill (+12% ↑ in green)
- Subtle animated number transitions

**Activity Feed Design**
- Chronological cards with newest first
- Left: Event type icon (24px, colored by type)
- Center: Rich content with primary action bold, context regular
- Right: Relative timestamp, overflow menu
- Hover: Subtle scale (1.02) and shadow elevation
- Click: Smooth expansion revealing full details

**Data Tables**
- Sticky header with frosted glass effect on scroll
- Alternating row backgrounds (subtle 2% opacity difference)
- Monospace for technical values (IDs, URLs, codes)
- Inline status badges with icon + text
- Expandable rows with smooth height animation
- Virtual scrolling for 100+ rows

**Security Alert Cards**
- Three-tier visual system without relying on color alone:
  - Critical: Red accent bar (4px left border), filled icon, bold title, persistent positioning
  - Warning: Orange accent bar, outlined icon, medium weight
  - Info: Blue accent bar, subtle icon, regular weight
- Card anatomy: Status icon → Title → Description → CVSS badge → Time → Actions
- Hover reveals quick actions (Dismiss, Assign, Create Ticket)

**Repository Activity Visualization**
- Commit Cards: Avatar (32px) → Message (truncated) → Branch pill → +/- diff stats
- PR Status: Colored dot + text (Open green, Merged purple, Closed grey)
- Contributor Graph: Horizontal bar chart with avatars as Y-axis labels
- Activity Heatmap: Calendar grid showing intensity by day/hour
- Clone Tracking: Time-series area chart with gradient fill

**Webhook Display Pattern**
- Event Log: Table with Event Type | Timestamp | Status Badge | Response Code | Latency
- Payload Viewer: Syntax-highlighted JSON in collapsible panel
- Status Indicators: Animated pulsing dot for live, static for historical
- Response Codes: Color-coded monospace (2xx green, 4xx orange, 5xx red)
- Retry Visualization: Step indicators showing attempt count and timing

#### Animation & Interaction Patterns

- **Page Transitions**: 200ms fade with 20px Y translation
- **Card Hover**: Scale(1.02) with box-shadow elevation
- **New Items**: Slide in from top with fade (300ms ease-out)
- **Loading**: Skeleton screens matching final layout (show after 300ms)
- **Micro-interactions**: Button press scale(0.98), switch toggles, checkbox fills
- **Scroll Animations**: Parallax for hero sections, fade-in for cards below fold
- **Real-time Updates**: Gentle pulse animation on data refresh

#### Advanced UI Patterns

- **Command Palette**: Cmd+K overlay with fuzzy search, recent actions, quick navigation
- **Filter Bar**: Pills for active filters, dropdown for adding, saved filter presets
- **Time Range Picker**: Preset buttons (1h, 24h, 7d, 30d) + custom date picker
- **Multi-select**: Checkbox column with select all, bulk action bar slides up
- **Inline Editing**: Click to edit with subtle dotted underline on hover
- **Toasts**: Bottom-right, max 3 stacked, auto-dismiss after 5s
- **Empty States**: Illustration + helpful message + primary action button

#### Component Details

**Buttons**
- Primary: Filled with accent color, white text, hover brightness +10%
- Secondary: Border only, hover fills with 10% opacity
- Danger: Red variants for destructive actions
- Sizes: Small (32px), Medium (40px), Large (48px height)
- Loading state: Spinner replaces text, maintains width

**Form Inputs**
- Dark background (#1c2128), 1px border on focus
- 12px padding, 16px for text areas
- Labels above, helper text below in muted color
- Error states with red border + icon + message
- Focus ring: 2px accent color with 4px offset

**Modals**
- Backdrop blur with 50% black opacity
- Modal at 90% viewport max, centered
- Smooth scale animation on open (0.95 to 1)
- Close button top-right + Escape key support

**Navigation**
- Icons (20px) + Labels in sidebar, collapsible to icons only
- Active state: Accent background with 4px left border
- Hover: 5% white opacity background
- Breadcrumbs: Slash separators, last item bold

#### Distinctive Visual Signatures

- **Glass Morphism**: Frosted glass effects for overlays and sticky headers
- **Gradient Borders**: Subtle animated gradients on focus states
- **Mesh Gradients**: Aurora-style backgrounds for empty states
- **Neumorphism Accents**: Very subtle for toggle switches and buttons
- **Custom Scrollbars**: Thin (8px), rounded, matching theme
- **Noise Texture**: Subtle grain overlay for depth (CSS filter)

#### Technical Implementation Notes

- Use Radix UI primitives for accessibility
- Implement container queries for responsive cards
- CSS custom properties for theming
- Framer Motion for React animations (or Alpine.js alternatives)
- Virtual scrolling for performance
- WebSocket for real-time updates
- Optimistic UI updates without loading states

#### What Makes This "Not Generic"

- Custom typography choices beyond system fonts
- Generous but purposeful white space
- Sophisticated color usage with custom gradients
- Attention to micro-interactions and transitions
- Mixed content types in single view (not just tables)
- Progressive disclosure without overwhelming
- Real-time feel through WebSocket updates
- Command palette for power users
- Unique visual treatments (gradients, glass effects)
- Professional polish in every detail

**Goal**: Create an interface that a security engineer would be proud to show in a board presentation - sophisticated, clear, and unmistakably premium.

### Current Foundation (v1)

We've already implemented:
- ✅ Tailwind CSS 3.x with custom configuration
- ✅ Alpine.js 3.x for lightweight interactivity
- ✅ Custom fonts: Cormorant Garamond (display) + IBM Plex Sans (sans)
- ✅ Refined color palette: warm-gray, sage, charcoal, terracotta, sage-green
- ✅ `.refined-card` component with gradient backgrounds
- ✅ Staggered page-load animations (fadeIn, slideUp, scaleIn)
- ✅ Utility-first template with no inline styles
- ✅ Dark mode support structure

### Key Differences from Current Design

**Typography**: Need to switch from Cormorant Garamond to Geist Sans/Roobert/Plus Jakarta Sans and implement full 6-weight hierarchy

**Color**: Need to switch from warm neutrals to dark-mode-first (#0f1419 backgrounds) with distinctive accent color (not current sage)

**Layout**: Need to add sidebar navigation, hero metrics bar, and 4px grid system

**Components**: Need to build enterprise-grade components (command palette, data tables with virtual scrolling, security alert cards, etc.)

**Interactions**: Need advanced patterns (glass morphism, gradient borders, inline editing, multi-select, etc.)

## Work Log

- [2025-11-18] Task created based on comprehensive design brief
- [2025-11-19] Phase 1 foundation completed:
  - Plus Jakarta Sans + JetBrains Mono typography system
  - Enterprise dark-mode-first color palette (#0f1419, #1c2128)
  - Violet accent (#8B5CF6) throughout interface
  - 4px grid spacing system
  - Collapsible sidebar navigation (208px→64px)
  - Command palette (Cmd+K) with keyboard navigation
  - Glass morphism effects on sidebar and overlays
  - Dark/light mode toggle
  - 4 stat cards with glow effects
  - Chart.js pie and line charts with date adapter
  - Staggered reveal animations
  - All "Polish & Distinctiveness" criteria met
  - User feedback: "wow this is great"
  - See completed task: sessions/tasks/done/h-dashboard-refined-redesign.md
