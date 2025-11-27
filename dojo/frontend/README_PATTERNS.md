# UI Patterns for Modern Templates

Common patterns and best practices for DefectDojo's modern UI (Tailwind CSS, Alpine.js, Vite).

## Navigation Active State (Server-Side)

**Problem:** JavaScript-based URL matching for active navigation states is unreliable.

**Solution:** Use Django template logic with `request.resolver_match.url_name`

```django
<!-- In base_modern.html sidebar navigation -->
<a href="{% url 'dashboard_modern' %}"
   class="sidebar-nav-item {% if request.resolver_match.url_name == 'dashboard_modern' %}active{% endif %}">
    Dashboard
</a>
<a href="{% url 'finding' %}"
   class="sidebar-nav-item {% if request.resolver_match.url_name == 'finding' %}active{% endif %}">
    Findings
</a>
```

**Critical:** URL names must match exactly in `urls.py` - e.g., `name='engagement'` not `name='engagements'`

---

## Flexbox Card Layout (Prevent Icon Overflow)

**Problem:** Using `justify-between` causes icons to wrap on narrow viewports.

**Solution:** Use `gap-4` with explicit flex alignment

```html
<!-- Before (causes overflow) -->
<div class="flex items-center justify-between">
    <div class="flex items-center gap-3">
        <icon>...</icon>
        <div>
            <h3>Title</h3>
            <p>Description</p>
        </div>
    </div>
    <span class="text-2xl">123</span>
</div>

<!-- After (prevents overflow) -->
<div class="flex items-center gap-4">
    <icon>...</icon>
    <div class="flex-1">
        <h3>Title</h3>
        <p>Description</p>
    </div>
    <span class="text-2xl">123</span>
</div>
```

---

## JSON Data Passing to Alpine.js

**Problem:** Inline JSON in `x-data` attribute causes parsing errors.

**Solution:** Use separate `<script type="application/json">` tag

```django
<script id="findings-data" type="application/json">
{{ findings_json|safe }}
</script>

<div x-data="dataTable({
    data: JSON.parse(document.getElementById('findings-data').textContent),
    columns: [...]
})">
```

---

## Configure Modal (Vanilla DOM Manipulation)

**Problem:** Bootstrap modal API conflicts with Alpine.js reactivity.

**Solution:** Use vanilla JavaScript DOM manipulation

```javascript
function showConfigureModal() {
    const modal = document.getElementById('configureModal');
    modal.style.display = 'block';
    modal.classList.add('show');
    document.body.classList.add('modal-open');
}

function hideConfigureModal() {
    const modal = document.getElementById('configureModal');
    modal.style.display = 'none';
    modal.classList.remove('show');
    document.body.classList.remove('modal-open');
}
```

---

## DataTable Color Scheme

**Principle:** All DataTables use consistent violet accent.

```css
/* In dataTable.css */
:root {
    --dd-table-accent: #8B5CF6;          /* Violet primary */
    --dd-table-accent-hover: #7C3AED;    /* Violet hover */
    --dd-table-bg: #1c2128;              /* Soft dark, not pure black */
    --dd-table-card-bg: #1c2128;
}
```

**Applied to:**
- Checkbox accent color
- Sort indicators
- Hover states
- Border highlights
- Filter pills
- Pagination active state

---

## Glass Morphism with Safari Support

**Best Practice:** Include `-webkit-` prefix for Safari 17+

```css
.config-panel {
    background: rgba(28, 33, 40, 0.6);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);  /* Required for Safari */
    border: 1px solid rgba(255, 255, 255, 0.1);
}
```

---

## Table Design System (2025 Best Practices)

**Avoid:** Pure black backgrounds (`#000000`)  
**Use:** Soft dark backgrounds (`#1c2128`)

**Rationale:**
- Pure black creates harsh contrast with white text
- Soft dark (#1c2128) reduces eye strain
- Aligns with 2025 UI/UX trends (GitHub, Linear, Vercel)
- Better visual hierarchy

---

## DataTable Virtual Scrolling - Row Parity

**Problem:** CSS `:nth-child(even)` breaks with virtual scrolling (counts DOM position, not data index).

**Solution:** Alpine.js computed class binding

```html
<template x-for="(row, index) in visibleData" :key="row.id">
    <tr class="dd-table-row"
        :class="{
            'selected': isSelected(row.id),
            'expanded': isExpanded(row.id),
            'even-row': (startIndex + index) % 2 === 1
        }">
        <!-- Row content -->
    </tr>
</template>
```

```css
.dd-table-row.even-row {
    background: var(--dd-table-row-alt);
}
```

**Why:**
- Virtual scrolling renders only visible rows (e.g., rows 100-120 of 1000)
- DOM positions reset (1-20) but data indices remain (100-120)
- `(startIndex + index) % 2 === 1` maintains consistent alternating colors
- `:nth-child()` selectors DO NOT work with virtual scrolling

**Files Using This Pattern:**
- `dojo/templates/dojo/findings_list_modern.html`
- `dojo/templates/dojo/engagements_modern.html`
- `dojo/templates/dojo/product_modern.html`

---

## Design System Reference

| Element | Value |
|---------|-------|
| Primary Background | `#0f1419` |
| Card Background | `#1c2128` |
| Accent Color | `#8B5CF6` (violet) |
| Text Primary | `#F0F6FC` |
| Text Secondary | `#8b949e` |
| Border | `rgba(255, 255, 255, 0.1)` |
| Font (Display/Body) | Plus Jakarta Sans |
| Font (Code) | JetBrains Mono |
| Transition | 200ms cubic-bezier(0.4, 0, 0.2, 1) |
