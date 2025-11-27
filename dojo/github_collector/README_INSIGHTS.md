# GitHub Insights Dashboard

The Insights Dashboard provides repository management analytics through a configurable widget-based UI with 31 built-in insights across 6 categories.

## Overview

**URL:** `/github/insights/dashboard`  
**API Base:** `/api/v2/github_insights/`

## Architecture

### Pluggable Insights System

**BaseInsight** (`insights/base.py`)
- Abstract class defining common interface
- Required attributes: `insight_id`, `name`, `description`, `category`, `visualization_type`, `chart_type`
- Abstract method: `calculate(filters) -> Dict`
- Default cache: 300 seconds (5 minutes)
- Visualization types: 'table', 'chart'

**InsightRegistry** (`insights/registry.py`)
- Auto-discovery via `autodiscover()`
- Methods: `register()`, `get_insight()`, `get_all_insights()`, `get_insights_by_category()`

## Insight Categories

### Activity Insights (`activity.py`) - 5 insights
- Most Recently Updated Repositories
- Stale Repositories (no commits in 90 days)
- Highest Commit Frequency
- Most Active Contributors
- Recently Created Repositories

### Health Insights (`health.py`) - 5 insights
- Repositories Missing README
- Repositories Missing CI/CD
- Repositories with Open PRs > 30 Days
- Repositories with High Issue Count (>50)
- Stale Repositories (no activity in 6 months)

### Security Insights (`security.py`) - 7 insights
- Vulnerability Distribution by Severity (pie)
- Vulnerability Distribution by Type/CWE (bar)
- Critical Vulnerability Trend (line)
- Repositories with Most Critical Findings
- Activity-Vulnerability Correlation (scatter)
- Repositories with No Security Findings
- Average Finding Age by Repository

### Ownership Insights (`ownership.py`) - 4 insights
- Unassigned Repositories
- Repositories with Multiple Owners
- Orphaned Repositories (owner inactive)
- Department Distribution

### Technology Insights (`technology.py`) - 4 insights
- Most Popular Languages
- Repositories Using Docker
- Repositories with Kubernetes
- Framework Adoption Rates

### Consumption Insights (`consumption.py`) - 6 insights
- Most Consumed Repositories (top 20)
- Consumption Tier Overrides
- Shared Library Distribution (pie)
- Orphaned Libraries
- Consumption vs Activity Correlation (scatter)
- Abandoned vs Stable Analysis

## Data Models

### GitHubInsightConfiguration
```python
# OneToOne with User
widget_config = JSONField()  # [{insight_id, order, size, pinned, auto_refresh, filters}]
widget_count = IntegerField(default=10)
```

Pinned widgets:
- Bypass widget_count limit
- Shorter cache TTL (60s vs 300s)

## REST API

```bash
# List all insights
GET /api/v2/github_insights/

# Filter by category
GET /api/v2/github_insights/?category=security

# Calculate specific insight
GET /api/v2/github_insights/{insight_id}/

# Get dashboard configuration
GET /api/v2/github_insights/dashboard/

# Update dashboard configuration
POST /api/v2/github_insights/dashboard/
```

## Caching

- Cache key format: `github_insight_{insight_id}_{hash(filters)}`
- Default TTL: 300 seconds (5 minutes)
- Pinned widgets: 60 seconds
- Backend: Django cache (Redis/Valkey)

## Management Command

```bash
# List all insights
python manage.py generate_insights --list

# Generate specific insight
python manage.py generate_insights --insight vuln_distribution --output json

# Generate by category
python manage.py generate_insights --category security --days 90

# Generate all with filter
python manage.py generate_insights --all --product-type-id 5 --output json
```

## Frontend

**Template:** `dojo/templates/dojo/github_insights_dashboard.html`  
**JavaScript:** `dojo/static/dojo/js/github_insights_dashboard.js`

### Features
- Widget-based grid layout (Bootstrap 3.4.1)
- Chart.js 4.4.0 visualizations
- Configuration modal for widget selection
- Individual widget refresh
- Auto-refresh for pinned widgets (60s)
- Widget sizes: small (col-md-4), medium (col-md-6), large (col-md-12)

### Design System
- Accent: Violet (#8B5CF6)
- Background: Soft dark (#1c2128)
- Glass morphism: `backdrop-filter: blur(12px)`

## Adding Custom Insights

```python
from dojo.github_collector.insights.base import BaseInsight

class MyCustomInsight(BaseInsight):
    insight_id = 'custom_insight'
    name = 'My Custom Insight'
    description = 'Description here'
    category = 'security'
    visualization_type = 'chart'
    chart_type = 'bar'

    def calculate(self, filters=None):
        return {
            'title': 'Custom Insight',
            'data': {'labels': [...], 'values': [...]},
            'metadata': {'count': 10, 'timestamp': timezone.now()}
        }

# Auto-registered on module import
```

## Performance

- Calculation time: <2 seconds for 2,451 repos
- Dashboard load: <5 seconds for 15 widgets (cached)
- Query optimization: select_related(), prefetch_related()

## Database Migrations

| Migration | Description |
|-----------|-------------|
| 0253 | Creates github_insight_configuration table |
| 0254 | Adds repository_owner to Product |
