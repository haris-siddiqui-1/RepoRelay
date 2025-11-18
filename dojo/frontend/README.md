# DefectDojo Modern Frontend

Modern, responsive frontend built with **Tailwind CSS**, **Alpine.js**, and **Vite**.

## Tech Stack

- **Tailwind CSS 3.x** - Utility-first CSS framework
- **Alpine.js 3.x** - Lightweight reactive framework (15KB)
- **Chart.js 4.x** - Modern charting library
- **Vite 5.x** - Lightning-fast build tool
- **Heroicons** - Beautiful SVG icons

## Project Structure

```
dojo/frontend/
├── src/
│   ├── styles/
│   │   ├── tailwind.css          # Main Tailwind entry point
│   │   ├── components/           # Component-specific styles
│   │   └── utilities/            # Custom utilities
│   ├── js/
│   │   ├── main.js               # Main entry point
│   │   ├── alpine/
│   │   │   ├── components/       # Alpine.js components
│   │   │   │   ├── darkMode.js
│   │   │   │   ├── dropdown.js
│   │   │   │   ├── modal.js
│   │   │   │   └── toast.js
│   │   │   └── stores/           # Alpine stores (global state)
│   │   ├── charts/
│   │   │   └── index.js          # Chart.js utilities
│   │   └── utils/
│   │       └── helpers.js        # Helper functions
│   └── components/               # Web Components
├── docs/                         # Documentation
├── public/                       # Static assets
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

## Development

### Prerequisites

- Node.js 18+ and npm 9+

### Install Dependencies

```bash
cd dojo/frontend
npm install
```

### Development Server

```bash
npm run dev
```

This starts Vite dev server at `http://localhost:3000` with:
- ⚡ Lightning-fast HMR (< 50ms updates)
- 🔄 Proxy to Django backend (`http://localhost:8080`)
- 🎨 Tailwind JIT compilation

### Build for Production

```bash
npm run build
```

Outputs optimized assets to `../static/dist/`:
- Minified CSS (purged, ~15-25KB gzipped)
- Minified JS (~60-70KB gzipped total)
- Asset fingerprinting for cache busting

## Usage in Django Templates

### Load Assets

```html
{% load static %}

<!-- In <head> -->
<link rel="stylesheet" href="{% static 'dist/css/tailwind-[hash].css' %}">

<!-- Before </body> -->
<script type="module" src="{% static 'dist/js/main-[hash].js' %}"></script>
```

### Use Alpine.js Components

**Dark Mode Toggle:**
```html
<div x-data="darkMode">
  <button @click="toggle" class="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800">
    <svg x-show="!dark" class="w-5 h-5"><!-- sun icon --></svg>
    <svg x-show="dark" class="w-5 h-5"><!-- moon icon --></svg>
  </button>
</div>
```

**Dropdown:**
```html
<div x-data="dropdown" @keydown.escape="close">
  <button @click="toggle">Menu</button>
  <div x-show="open" x-transition @click.away="close" class="dropdown-menu">
    <!-- Dropdown items -->
  </div>
</div>
```

**Modal:**
```html
<div x-data="modal">
  <button @click="open">Open Modal</button>
  <div x-show="isOpen" x-transition class="fixed inset-0 z-50 overflow-y-auto">
    <div class="flex items-center justify-center min-h-screen p-4">
      <div @click="close" class="fixed inset-0 bg-black bg-opacity-50"></div>
      <div class="relative bg-white dark:bg-gray-800 rounded-lg p-6">
        <button @click="close">Close</button>
        <!-- Modal content -->
      </div>
    </div>
  </div>
</div>
```

**Toast Notifications:**
```html
<div x-data="toast">
  <button @click="show('Successfully saved!', 'success')">Show Toast</button>

  <!-- Toast container -->
  <div x-show="visible" x-transition
       :class="getTypeClasses()"
       class="fixed bottom-4 right-4 p-4 rounded-lg border-l-4">
    <p x-text="message"></p>
  </div>
</div>
```

### Use Tailwind Classes

```html
<!-- Card -->
<div class="dd-card">
  <div class="dd-card-header">
    <h3 class="text-lg font-semibold">Card Title</h3>
  </div>
  <div class="dd-card-body">
    <p>Card content</p>
  </div>
</div>

<!-- Button -->
<button class="dd-btn-primary">
  Primary Action
</button>

<!-- Severity Badge -->
<span class="dd-badge-critical">Critical</span>
```

### Create Charts

```html
<canvas id="severityChart" data-chart="pie" data-chart-data='{ "critical": 10, "high": 25, "medium": 30, "low": 15, "info": 5 }'></canvas>

<script>
  // Charts initialize automatically on page load
  // Or initialize manually:
  const severityData = {
    critical: 10,
    high: 25,
    medium: 30,
    low: 15,
    info: 5
  };
  window.dd.initializeCharts();
</script>
```

## Design System

See `DESIGN_SYSTEM.md` for:
- Color palette
- Typography scale
- Spacing system
- Component library
- Dark mode implementation

## Component Documentation

See `docs/components.md` for detailed component usage and examples.

## Migration Guide

See `docs/migration.md` for migrating from Bootstrap 3 to Tailwind CSS.

## Performance

### Bundle Sizes (Gzipped)

- CSS: ~15-25KB (Tailwind purged)
- Alpine.js: ~15KB
- Chart.js: ~30KB
- Custom JS: ~10-15KB
- **Total: ~70-85KB**

### Optimization Features

- Tree-shaking (unused code removed)
- CSS purging (Tailwind JIT)
- Code splitting
- Asset fingerprinting
- Lazy loading
- Image optimization

## Browser Support

- Chrome (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)
- Edge (latest 2 versions)
- Mobile Safari (iOS 14+)
- Mobile Chrome (Android 10+)

## Resources

- [Tailwind CSS Docs](https://tailwindcss.com/docs)
- [Alpine.js Docs](https://alpinejs.dev/)
- [Vite Docs](https://vitejs.dev/)
- [Chart.js Docs](https://www.chartjs.org/docs/)
- [Heroicons](https://heroicons.com/)

## Contributing

1. Follow the design system guidelines
2. Write clean, semantic HTML
3. Use Tailwind utility classes
4. Create reusable Alpine components
5. Test on all supported browsers
6. Maintain accessibility (WCAG 2.1 AA)

## License

Same as DefectDojo - BSD-3-Clause
