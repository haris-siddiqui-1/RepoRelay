# Quick Start Guide

Get the DefectDojo Modern Frontend up and running in 5 minutes.

## Prerequisites

- **Node.js 18+** and npm 9+
- Django backend running at `http://localhost:8080`

## Setup

```bash
# Navigate to frontend directory
cd dojo/frontend

# Run setup script
./setup.sh

# Or manually:
npm install
```

## Development

```bash
# Start dev server with HMR
npm run dev
```

Visit `http://localhost:3000` - changes auto-reload!

## Building for Production

```bash
# Build optimized assets
npm run build
```

Outputs to `../static/dist/` with fingerprinted filenames.

## Using in Django Templates

### 1. Load Static Files

```html
{% load static %}

<!DOCTYPE html>
<html lang="en">
<head>
    <!-- Load Tailwind CSS -->
    <link rel="stylesheet" href="{% static 'dist/css/tailwind-[hash].css' %}">

    <!-- Load Google Fonts (Inter) -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
</head>
<body>
    <!-- Your content -->

    <!-- Load Alpine.js and custom JS -->
    <script type="module" src="{% static 'dist/js/main-[hash].js' %}"></script>
</body>
</html>
```

### 2. Use Tailwind Utility Classes

```html
<!-- Modern card -->
<div class="dd-card">
    <div class="dd-card-header">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
            Critical Findings
        </h3>
    </div>
    <div class="dd-card-body">
        <p class="text-gray-600 dark:text-gray-400">
            You have 247 critical findings to address.
        </p>
    </div>
    <div class="dd-card-footer">
        <a href="/findings?severity=Critical" class="dd-btn-primary">
            View Findings
        </a>
    </div>
</div>
```

### 3. Use Alpine.js Components

```html
<!-- Dark mode toggle -->
<div x-data="darkMode">
    <button @click="toggle" class="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800">
        <svg x-show="!dark" class="w-5 h-5"><!-- sun icon --></svg>
        <svg x-show="dark" class="w-5 h-5"><!-- moon icon --></svg>
    </button>
</div>

<!-- Toast notifications -->
<div x-data="toast">
    <button @click="show('Saved successfully!', 'success')">
        Save
    </button>
</div>
```

### 4. Create Charts

```html
<canvas
    id="severityChart"
    data-chart="pie"
    data-chart-data='{"critical": 10, "high": 25, "medium": 30}'
    class="h-64">
</canvas>

<script>
    // Charts initialize automatically
    document.addEventListener('DOMContentLoaded', () => {
        window.dd.initializeCharts();
    });
</script>
```

## Common Components

### Stat Card

```html
<div class="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
    <div class="flex items-start justify-between">
        <div>
            <p class="text-sm font-medium text-gray-600 dark:text-gray-400">Total Findings</p>
            <p class="mt-2 text-3xl font-bold text-gray-900 dark:text-white">1,247</p>
            <p class="mt-1 text-sm text-green-600 dark:text-green-400">
                <span class="inline-flex items-center">
                    ↑ 12% from last week
                </span>
            </p>
        </div>
        <div class="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
            <svg class="w-6 h-6 text-blue-600 dark:text-blue-400"><!-- icon --></svg>
        </div>
    </div>
</div>
```

### Severity Badge

```html
<span class="dd-badge-critical">Critical</span>
<span class="dd-badge-high">High</span>
<span class="dd-badge-medium">Medium</span>
<span class="dd-badge-low">Low</span>
<span class="dd-badge-info">Info</span>
```

### Button Variants

```html
<button class="dd-btn-primary">Primary Action</button>
<button class="dd-btn-secondary">Secondary Action</button>
<button class="dd-btn-danger">Delete</button>
```

### Form Input

```html
<div class="space-y-1">
    <label for="title" class="block text-sm font-medium text-gray-700 dark:text-gray-300">
        Finding Title
    </label>
    <input type="text" id="title" class="dd-input" placeholder="Enter title">
</div>
```

## Dark Mode

Dark mode is automatically detected from system preferences and can be toggled:

```html
<div x-data="darkMode">
    <button @click="toggle">
        Toggle Dark Mode
    </button>
</div>
```

Preference is saved to `localStorage`.

## Helper Functions

```javascript
// Debounce
const search = window.dd.debounce((query) => {
    console.log('Searching for:', query);
}, 300);

// Throttle
const onScroll = window.dd.throttle(() => {
    console.log('Scrolled');
}, 100);

// Initialize charts
window.dd.initializeCharts();
```

## Troubleshooting

**HMR not working?**
- Ensure Django backend is running at `http://localhost:8080`
- Check Vite dev server is running at `http://localhost:3000`
- Check browser console for errors

**Styles not loading?**
- Run `npm run build` to generate assets
- Check that manifest.json exists in `../static/dist/`
- Verify static file paths in Django templates

**Charts not rendering?**
- Ensure Chart.js is loaded
- Check data attribute format: `data-chart-data='{"key": "value"}'`
- Call `window.dd.initializeCharts()` after DOM ready

## Next Steps

- Review the [Design System](../DESIGN_SYSTEM.md)
- Check [Component Documentation](docs/components.md)
- Read [Migration Guide](docs/migration.md)

## Getting Help

- Check the [README](README.md)
- Review [Tailwind CSS Docs](https://tailwindcss.com/docs)
- Review [Alpine.js Docs](https://alpinejs.dev/)
