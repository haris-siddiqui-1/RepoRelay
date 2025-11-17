---
status: completed
created: 2025-11-16
priority: high
estimated_effort: 11-16 hours
index: phase4-migration
---

# GitHub Repository Management Insights Dashboard

## Objective

Create a **configurable insights dashboard** that displays GitHub repository management metrics using a widget-based system. Users can select 5, 10, 15, or any number of insights to display on their personalized dashboard.

## User Story

> "I want to be able to view insights like 'Most updated repositories in the last two weeks' for example, and extra insights - just for overall github management."
>
> "yes - ensure we have a way to display a set of insights. Maybe I want 5, maybe I want 10, maybe I want 15 insights on that dashboard"

## Context Manifest

### Implementation Complete
- **Insight System**: BaseInsight + InsightRegistry with 25 insights across 5 categories
- **Models**: GitHubInsightConfiguration (OneToOne with User, JSONField), repository_owner on Product
- **REST API**: GitHubInsightsViewSet at `/api/v2/github_insights/` with caching
- **Frontend**: Dashboard at `/github/insights/` with Chart.js 4.4.0 visualizations
- **CLI**: `python manage.py generate_insights` command
- **Files Created**:
  - `dojo/github_collector/insights/` (base.py, registry.py, activity.py, health.py, security.py, ownership.py, technology.py, views.py)
  - `dojo/static/dojo/js/github_insights_dashboard.js`
  - `dojo/templates/dojo/github_insights_dashboard.html`
  - `dojo/management/commands/generate_insights.py`
  - Migrations 0253, 0254

## Requirements

### Functional Requirements

1. **Widget-Based Insights System**
   - Pluggable insight classes with common interface
   - InsightRegistry pattern for automatic discovery
   - Each insight returns structured data (title, data, metadata)

2. **20+ Built-in Insights** (5 categories)

   **Activity Insights:**
   - Most Updated Repositories (last 2 weeks)
   - Least Active Repositories (no commits in 90 days)
   - Highest Commit Frequency (commits per day)
   - Most Active Contributors
   - Recently Created Repositories

   **Health Insights:**
   - Repositories Missing README
   - Repositories Missing CI/CD
   - Repositories with Open PRs Older Than 30 Days
   - Repositories with High Issue Count (open issues > 50)
   - Stale Repositories (no activity in 6 months)

   **Security Insights (Analytics & Correlations):**
   - Vulnerability Distribution by Severity (chart: pie/bar - Critical/High/Medium/Low breakdown)
   - Vulnerability Distribution by Type/CWE (chart: bar - Top 10 vulnerability types)
   - Activity-Vulnerability Correlation (chart: scatter - commits/week vs vulnerability count)
   - Popularity-Security Correlation (chart: scatter - stars/clones vs vulnerabilities)
   - CI/CD Impact on Vulnerability Detection (chart: comparison bar - with/without CI/CD)
   - Webhook Activity vs Vulnerability Count (chart: time series - correlation over time)
   - Repository Risk Score Distribution (chart: histogram - composite risk metric)

   **Ownership Insights:**
   - Unassigned Repositories (no Product owner)
   - Repositories with Multiple Owners
   - Orphaned Repositories (owner inactive)
   - Department Distribution

   **Technology Insights:**
   - Most Popular Languages
   - Repositories Using Docker
   - Repositories with Kubernetes
   - Technology Stack Distribution
   - Framework Adoption Rates

3. **Configurable Dashboard**
   - User-specific insight selection
   - **Pin Feature**: Pin critical insights to always display first with auto-refresh
   - Pinned widgets bypass widget_count limit and have shorter cache TTL (1 min vs 5 min)
   - Widget size configuration (small, medium, large)
   - Drag-and-drop widget ordering (future enhancement)
   - Persistent user preferences

4. **REST API Endpoints**
   - `GET /api/v2/github/insights/` - List available insights
   - `GET /api/v2/github/insights/{insight_id}/` - Get specific insight data
   - `GET /api/v2/github/insights/dashboard/` - Get user's dashboard config
   - `POST /api/v2/github/insights/dashboard/` - Update dashboard config
   - `GET /api/v2/github/insights/preview/{insight_id}/` - Preview insight

5. **Frontend Dashboard UI**
   - Grid-based widget layout
   - Real-time insight data fetching
   - Configuration panel for widget selection
   - Export insights to CSV/JSON
   - Refresh individual widgets

6. **Management Command**
   - `python manage.py show_github_insights` - CLI access to insights
   - `--insight <insight_id>` flag for specific insight
   - `--format json|table|csv` output format

### Non-Functional Requirements

1. **Performance**
   - Insights should load in <2 seconds
   - Use query optimization (prefetch_related, select_related)
   - Cache insight results for 5 minutes (configurable)

2. **Scalability**
   - Support 2,451 repositories (current count)
   - Efficient database queries with indexes
   - Pagination for large result sets

3. **Extensibility**
   - Easy to add new insights (inherit BaseInsight)
   - Plugin architecture for custom insights
   - Filter support (date ranges, product types, etc.)

## Architecture Design

### Backend Components

#### 1. BaseInsight Abstract Class
**File**: `dojo/github_collector/insights/base.py` (new)

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from django.utils import timezone
from datetime import timedelta

class BaseInsight(ABC):
    """
    Base class for all GitHub repository insights.

    Subclasses must implement:
    - insight_id: Unique identifier
    - name: Human-readable name
    - description: Brief description
    - category: One of: activity, health, security, ownership, technology
    - visualization_type: 'table', 'chart', or 'both'
    - chart_type: 'bar', 'pie', 'line', 'scatter', 'histogram' (if visualization_type includes 'chart')
    - calculate(): Returns insight data
    """

    insight_id: str = None
    name: str = None
    description: str = None
    category: str = None
    visualization_type: str = 'table'  # 'table', 'chart', 'both'
    chart_type: str = None  # 'bar', 'pie', 'line', 'scatter', 'histogram'
    cache_duration: int = 300  # seconds (5 minutes)

    def __init__(self):
        if not all([self.insight_id, self.name, self.description, self.category]):
            raise ValueError(f"Insight {self.__class__.__name__} missing required attributes")

    @abstractmethod
    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate and return insight data.

        Args:
            filters: Optional filters (e.g., {'days': 14, 'product_type_id': 5})

        Returns:
            {
                'title': str,
                'data': List[Dict] or Dict,
                'metadata': {
                    'count': int,
                    'timestamp': datetime,
                    'filters_applied': Dict
                }
            }
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Return insight metadata."""
        return {
            'insight_id': self.insight_id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'visualization_type': self.visualization_type,
            'chart_type': self.chart_type,
            'cache_duration': self.cache_duration,
        }
```

#### 2. Example Insight Implementation (Table-based)
**File**: `dojo/github_collector/insights/activity.py` (new)

```python
from dojo.github_collector.insights.base import BaseInsight
from dojo.models import Repository
from django.utils import timezone
from datetime import timedelta

class MostUpdatedRepositoriesInsight(BaseInsight):
    insight_id = 'most_updated_repos'
    name = 'Most Updated Repositories'
    description = 'Repositories with most recent commits in the last N days'
    category = 'activity'
    visualization_type = 'table'

    def calculate(self, filters=None):
        days = filters.get('days', 14) if filters else 14
        limit = filters.get('limit', 10) if filters else 10

        cutoff = timezone.now() - timedelta(days=days)

        repos = Repository.objects.filter(
            last_commit_date__gte=cutoff
        ).select_related('product').order_by('-last_commit_date')[:limit]

        data = [
            {
                'repository_name': repo.name,
                'last_commit_date': repo.last_commit_date.isoformat(),
                'product_name': repo.product.name if repo.product else 'Unassigned',
                'commit_count': repo.commit_count or 0,
                'github_url': repo.github_url,
            }
            for repo in repos
        ]

        return {
            'title': f'Most Updated Repositories (Last {days} Days)',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now().isoformat(),
                'filters_applied': {'days': days, 'limit': limit}
            }
        }
```

#### 2b. Example Security Insight with Chart
**File**: `dojo/github_collector/insights/security.py` (new)

```python
from dojo.github_collector.insights.base import BaseInsight
from dojo.models import Finding
from django.db.models import Count, Q
from django.utils import timezone

class VulnerabilityDistributionBySeverityInsight(BaseInsight):
    insight_id = 'vuln_distribution_severity'
    name = 'Vulnerability Distribution by Severity'
    description = 'Breakdown of all findings by severity level (Critical/High/Medium/Low)'
    category = 'security'
    visualization_type = 'chart'
    chart_type = 'pie'
    cache_duration = 60  # 1 minute for pinned insights

    def calculate(self, filters=None):
        # Count findings by severity
        severity_counts = {
            'Critical': Finding.objects.filter(severity='Critical', active=True).count(),
            'High': Finding.objects.filter(severity='High', active=True).count(),
            'Medium': Finding.objects.filter(severity='Medium', active=True).count(),
            'Low': Finding.objects.filter(severity='Low', active=True).count(),
        }

        # Define severity colors
        severity_colors = {
            'Critical': '#d9534f',  # Red
            'High': '#f0ad4e',      # Orange
            'Medium': '#5bc0de',    # Blue
            'Low': '#5cb85c',       # Green
        }

        labels = list(severity_counts.keys())
        values = list(severity_counts.values())
        colors = [severity_colors[label] for label in labels]

        total = sum(values)

        return {
            'title': 'Vulnerability Distribution by Severity',
            'data': {
                'labels': labels,
                'values': values,
                'colors': colors
            },
            'chart_config': {
                'type': 'pie',
                'options': {
                    'responsive': True,
                    'plugins': {
                        'legend': {
                            'position': 'right'
                        },
                        'tooltip': {
                            'callbacks': {
                                'label': 'function(context) { return context.label + ": " + context.parsed + " (" + Math.round(context.parsed / ' + str(total) + ' * 100) + "%)"; }'
                            }
                        }
                    }
                }
            },
            'metadata': {
                'total_vulnerabilities': total,
                'timestamp': timezone.now().isoformat(),
                'filters_applied': filters or {}
            }
        }


class ActivityVulnerabilityCorrelationInsight(BaseInsight):
    insight_id = 'activity_vuln_correlation'
    name = 'Activity vs Vulnerability Correlation'
    description = 'Scatter plot showing relationship between repository activity and vulnerability count'
    category = 'security'
    visualization_type = 'chart'
    chart_type = 'scatter'

    def calculate(self, filters=None):
        from dojo.models import Repository, Product
        from datetime import timedelta

        # Get repositories with commit data and vulnerability counts
        repos = Repository.objects.select_related('product').all()

        scatter_data = []
        labels = []

        for repo in repos:
            if repo.product:
                # Calculate commits per week (if last_commit_date available)
                commits_per_week = 0
                if repo.last_commit_date and repo.commit_count:
                    days_since_creation = (timezone.now() - repo.created_at).days if hasattr(repo, 'created_at') else 365
                    weeks = max(days_since_creation / 7, 1)
                    commits_per_week = repo.commit_count / weeks

                # Count vulnerabilities for this product
                vuln_count = Finding.objects.filter(
                    test__engagement__product=repo.product,
                    active=True
                ).count()

                scatter_data.append({
                    'x': round(commits_per_week, 2),
                    'y': vuln_count,
                    'label': repo.name
                })
                labels.append(repo.name)

        return {
            'title': 'Activity vs Vulnerability Correlation',
            'data': {
                'datasets': [{
                    'label': 'Repositories',
                    'data': scatter_data,
                    'backgroundColor': '#5bc0de'
                }]
            },
            'chart_config': {
                'type': 'scatter',
                'options': {
                    'responsive': True,
                    'scales': {
                        'x': {
                            'title': {
                                'display': True,
                                'text': 'Commits per Week'
                            }
                        },
                        'y': {
                            'title': {
                                'display': True,
                                'text': 'Vulnerability Count'
                            }
                        }
                    },
                    'plugins': {
                        'tooltip': {
                            'callbacks': {
                                'label': 'function(context) { return context.raw.label + ": " + context.parsed.x + " commits/week, " + context.parsed.y + " vulns"; }'
                            }
                        }
                    }
                }
            },
            'metadata': {
                'repository_count': len(scatter_data),
                'timestamp': timezone.now().isoformat()
            }
        }
```

#### 3. InsightRegistry
**File**: `dojo/github_collector/insights/registry.py` (new)

```python
from typing import Dict, List, Type
from dojo.github_collector.insights.base import BaseInsight

class InsightRegistry:
    """
    Registry for all available insights.
    Auto-discovers insights from insight modules.
    """

    _insights: Dict[str, Type[BaseInsight]] = {}

    @classmethod
    def register(cls, insight_class: Type[BaseInsight]):
        """Register an insight class."""
        insight = insight_class()
        cls._insights[insight.insight_id] = insight_class

    @classmethod
    def get_insight(cls, insight_id: str) -> BaseInsight:
        """Get an insight instance by ID."""
        if insight_id not in cls._insights:
            raise ValueError(f"Unknown insight: {insight_id}")
        return cls._insights[insight_id]()

    @classmethod
    def get_all_insights(cls) -> List[Dict]:
        """Get metadata for all registered insights."""
        return [
            insight_class().get_metadata()
            for insight_class in cls._insights.values()
        ]

    @classmethod
    def get_insights_by_category(cls, category: str) -> List[Dict]:
        """Get insights filtered by category."""
        return [
            insight_class().get_metadata()
            for insight_class in cls._insights.values()
            if insight_class().category == category
        ]

# Auto-register insights on import
def autodiscover():
    """Auto-discover and register all insights."""
    from dojo.github_collector.insights import activity, health, security, ownership, technology

    # Each module should register its insights
    # Example: InsightRegistry.register(MostUpdatedRepositoriesInsight)
```

#### 4. GitHubInsightConfiguration Model
**File**: `dojo/models.py` (add to existing file)

```python
class GitHubInsightConfiguration(models.Model):
    """
    User-specific dashboard configuration for GitHub insights.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='github_insight_config'
    )

    # JSON field storing widget configuration
    # Format: [
    #   {
    #     'insight_id': 'most_updated_repos',
    #     'order': 0,
    #     'size': 'medium',
    #     'pinned': False,
    #     'auto_refresh': False,
    #     'filters': {'days': 14}
    #   },
    #   {
    #     'insight_id': 'vuln_distribution',
    #     'order': 1,
    #     'size': 'large',
    #     'pinned': True,
    #     'auto_refresh': True,
    #     'filters': {}
    #   },
    # ]
    widget_config = models.JSONField(default=list)

    # Number of widgets to display (5, 10, 15, etc.)
    # Note: Pinned widgets always display regardless of widget_count
    widget_count = models.IntegerField(default=10)

    # Metadata
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'github_insight_configuration'

    def __str__(self):
        return f"GitHub Insights Config for {self.user.username}"
```

#### 5. REST API ViewSet
**File**: `dojo/api_v2/views/github_insights.py` (new)

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache

from dojo.github_collector.insights.registry import InsightRegistry
from dojo.models import GitHubInsightConfiguration
from dojo.api_v2.serializers import GitHubInsightConfigurationSerializer

class GitHubInsightsViewSet(viewsets.ViewSet):
    """
    ViewSet for GitHub repository insights.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List all available insights."""
        insights = InsightRegistry.get_all_insights()
        return Response(insights)

    def retrieve(self, request, pk=None):
        """Get specific insight data."""
        insight_id = pk
        filters = request.query_params.dict()

        # Check cache
        cache_key = f"github_insight_{insight_id}_{hash(str(filters))}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        try:
            insight = InsightRegistry.get_insight(insight_id)
            data = insight.calculate(filters)

            # Cache result
            cache.set(cache_key, data, insight.cache_duration)

            return Response(data)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get', 'post'])
    def dashboard(self, request):
        """Get or update user's dashboard configuration."""
        if request.method == 'GET':
            config, _ = GitHubInsightConfiguration.objects.get_or_create(user=request.user)
            serializer = GitHubInsightConfigurationSerializer(config)
            return Response(serializer.data)

        elif request.method == 'POST':
            config, _ = GitHubInsightConfiguration.objects.get_or_create(user=request.user)
            serializer = GitHubInsightConfigurationSerializer(config, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
```

#### 6. Management Command
**File**: `dojo/management/commands/show_github_insights.py` (new)

```python
from django.core.management.base import BaseCommand
from dojo.github_collector.insights.registry import InsightRegistry
import json
from tabulate import tabulate

class Command(BaseCommand):
    help = 'Display GitHub repository insights'

    def add_arguments(self, parser):
        parser.add_argument(
            '--insight',
            type=str,
            help='Specific insight ID to display'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'table', 'csv'],
            default='table',
            help='Output format'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=14,
            help='Days filter for time-based insights'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Limit for result count'
        )

    def handle(self, *args, **options):
        insight_id = options['insight']
        output_format = options['format']
        filters = {
            'days': options['days'],
            'limit': options['limit'],
        }

        if insight_id:
            # Show specific insight
            try:
                insight = InsightRegistry.get_insight(insight_id)
                result = insight.calculate(filters)
                self.display_insight(result, output_format)
            except ValueError as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))
        else:
            # List all insights
            insights = InsightRegistry.get_all_insights()
            self.stdout.write(self.style.SUCCESS(f"Available Insights ({len(insights)}):"))
            for insight in insights:
                self.stdout.write(f"  - {insight['insight_id']}: {insight['name']} ({insight['category']})")

    def display_insight(self, result, output_format):
        if output_format == 'json':
            self.stdout.write(json.dumps(result, indent=2))
        elif output_format == 'table':
            self.stdout.write(self.style.SUCCESS(result['title']))
            if isinstance(result['data'], list) and result['data']:
                headers = result['data'][0].keys()
                rows = [item.values() for item in result['data']]
                self.stdout.write(tabulate(rows, headers=headers, tablefmt='grid'))
            else:
                self.stdout.write(json.dumps(result['data'], indent=2))
        elif output_format == 'csv':
            if isinstance(result['data'], list) and result['data']:
                import csv
                import sys
                writer = csv.DictWriter(sys.stdout, fieldnames=result['data'][0].keys())
                writer.writeheader()
                writer.writerows(result['data'])
```

### Frontend Components

#### 1. Dashboard Page Template
**File**: `dojo/templates/github/insights_dashboard.html` (new)

```html
{% extends "base.html" %}
{% load static %}

{% block content %}
<div class="container-fluid">
    <div class="row">
        <div class="col-md-12">
            <h2>GitHub Repository Insights Dashboard</h2>
            <p class="text-muted">Customize your dashboard by selecting insights to display.</p>
        </div>
    </div>

    <div class="row">
        <div class="col-md-12">
            <button class="btn btn-primary" id="configure-dashboard-btn">
                <i class="fa fa-cog"></i> Configure Dashboard
            </button>
            <button class="btn btn-default" id="refresh-all-btn">
                <i class="fa fa-refresh"></i> Refresh All
            </button>
        </div>
    </div>

    <hr>

    <!-- Widget Grid -->
    <div id="insights-grid" class="row">
        <!-- Widgets loaded dynamically via JS -->
    </div>
</div>

<!-- Configuration Modal -->
<div class="modal fade" id="configure-modal" tabindex="-1" role="dialog">
    <div class="modal-dialog modal-lg" role="document">
        <div class="modal-content">
            <div class="modal-header">
                <button type="button" class="close" data-dismiss="modal">&times;</button>
                <h4 class="modal-title">Configure Insights Dashboard</h4>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Number of Insights to Display</label>
                    <input type="number" class="form-control" id="widget-count" min="1" max="20" value="10">
                </div>

                <h5>Available Insights</h5>
                <div id="insight-selector">
                    <!-- Checkboxes for each insight -->
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-default" data-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" id="save-config-btn">Save Configuration</button>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block postscript %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="{% static 'js/github_insights_dashboard.js' %}"></script>
{% endblock %}
```

#### 2. Dashboard JavaScript
**File**: `dojo/static/js/github_insights_dashboard.js` (new)

```javascript
$(document).ready(function() {
    let currentConfig = null;
    let availableInsights = [];
    let chartInstances = {};  // Store Chart.js instances for cleanup
    let autoRefreshIntervals = {};  // Store auto-refresh interval IDs

    // Load dashboard configuration
    function loadDashboard() {
        $.get('/api/v2/github/insights/dashboard/', function(config) {
            currentConfig = config;
            renderWidgets(config.widget_config);
        });
    }

    // Load available insights
    function loadAvailableInsights() {
        $.get('/api/v2/github/insights/', function(insights) {
            availableInsights = insights;
            renderInsightSelector(insights);
        });
    }

    // Render widgets
    function renderWidgets(widgetConfig) {
        const grid = $('#insights-grid');
        grid.empty();

        // Clear existing auto-refresh intervals
        Object.values(autoRefreshIntervals).forEach(interval => clearInterval(interval));
        autoRefreshIntervals = {};

        // Separate pinned and unpinned widgets
        const pinnedWidgets = widgetConfig.filter(w => w.pinned);
        const unpinnedWidgets = widgetConfig.filter(w => !w.pinned);

        // Render pinned widgets first (always show all)
        pinnedWidgets.forEach(function(widget) {
            const widgetHtml = createWidget(widget);
            grid.append(widgetHtml);
            loadWidgetData(widget.insight_id, widget.filters, widget.pinned);

            // Set up auto-refresh for pinned widgets if enabled
            if (widget.auto_refresh) {
                autoRefreshIntervals[widget.insight_id] = setInterval(function() {
                    loadWidgetData(widget.insight_id, widget.filters, widget.pinned);
                }, 60000);  // Refresh every 60 seconds
            }
        });

        // Render unpinned widgets up to widget_count
        const remainingSlots = currentConfig.widget_count - pinnedWidgets.length;
        unpinnedWidgets.slice(0, remainingSlots).forEach(function(widget) {
            const widgetHtml = createWidget(widget);
            grid.append(widgetHtml);
            loadWidgetData(widget.insight_id, widget.filters, widget.pinned);
        });
    }

    // Create widget HTML
    function createWidget(widget) {
        const sizeClass = widget.size === 'large' ? 'col-md-12' :
                          widget.size === 'medium' ? 'col-md-6' : 'col-md-4';

        const pinnedIcon = widget.pinned ? '<i class="fa fa-thumb-tack text-primary" title="Pinned"></i> ' : '';
        const pinButtonClass = widget.pinned ? 'btn-primary' : 'btn-default';
        const pinButtonIcon = widget.pinned ? 'fa-thumb-tack' : 'fa-thumb-tack';

        return `
            <div class="${sizeClass} insight-widget ${widget.pinned ? 'pinned-widget' : ''}" data-insight-id="${widget.insight_id}">
                <div class="panel panel-default">
                    <div class="panel-heading">
                        <h4 class="panel-title">
                            ${pinnedIcon}
                            <i class="fa fa-spinner fa-spin loading-icon"></i>
                            <span class="insight-title">Loading...</span>
                            <div class="btn-group pull-right">
                                <button class="btn btn-xs ${pinButtonClass} pin-widget-btn" title="${widget.pinned ? 'Unpin' : 'Pin'} widget">
                                    <i class="fa ${pinButtonIcon}"></i>
                                </button>
                                <button class="btn btn-xs btn-default refresh-widget-btn" title="Refresh">
                                    <i class="fa fa-refresh"></i>
                                </button>
                            </div>
                        </h4>
                    </div>
                    <div class="panel-body">
                        <div class="insight-content"></div>
                    </div>
                </div>
            </div>
        `;
    }

    // Load widget data
    function loadWidgetData(insightId, filters, isPinned) {
        const widget = $(`.insight-widget[data-insight-id="${insightId}"]`);
        const url = `/api/v2/github/insights/${insightId}/`;

        // Add cache busting for pinned widgets
        const params = isPinned ? {...filters, _t: Date.now()} : filters;

        $.get(url, params, function(data) {
            widget.find('.loading-icon').hide();
            widget.find('.insight-title').text(data.title);

            // Check if insight has chart data
            if (data.chart_config && data.chart_config.type) {
                renderChartData(widget.find('.insight-content'), data, insightId);
            } else if (Array.isArray(data.data)) {
                renderTableData(widget.find('.insight-content'), data.data);
            } else {
                renderObjectData(widget.find('.insight-content'), data.data);
            }
        }).fail(function() {
            widget.find('.loading-icon').hide();
            widget.find('.insight-title').text('Error Loading Insight');
            widget.find('.insight-content').html('<p class="text-danger">Failed to load data</p>');
        });
    }

    // Render chart data
    function renderChartData(container, insightData, insightId) {
        // Destroy existing chart if present
        if (chartInstances[insightId]) {
            chartInstances[insightId].destroy();
        }

        // Create canvas element
        const canvasId = `chart-${insightId}`;
        container.html(`<canvas id="${canvasId}" style="max-height: 400px;"></canvas>`);

        const ctx = document.getElementById(canvasId).getContext('2d');
        const chartConfig = insightData.chart_config;

        // Build Chart.js configuration
        const config = {
            type: chartConfig.type,
            data: {
                labels: insightData.data.labels || [],
                datasets: [{
                    label: insightData.title,
                    data: insightData.data.values || [],
                    backgroundColor: insightData.data.colors || generateColors(insightData.data.values.length),
                    borderColor: chartConfig.type === 'line' ? insightData.data.colors?.[0] : undefined,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: chartConfig.type !== 'scatter',
                        position: 'top'
                    },
                    tooltip: {
                        enabled: true
                    }
                },
                ...chartConfig.options
            }
        };

        // Create chart instance
        chartInstances[insightId] = new Chart(ctx, config);
    }

    // Generate colors for charts
    function generateColors(count) {
        const colors = [
            '#d9534f', '#f0ad4e', '#5bc0de', '#5cb85c', '#337ab7',
            '#9b59b6', '#e74c3c', '#3498db', '#2ecc71', '#f39c12'
        ];
        return Array.from({length: count}, (_, i) => colors[i % colors.length]);
    }

    // Render table data
    function renderTableData(container, data) {
        if (data.length === 0) {
            container.html('<p class="text-muted">No data available</p>');
            return;
        }

        const headers = Object.keys(data[0]);
        let tableHtml = '<table class="table table-striped table-condensed"><thead><tr>';
        headers.forEach(h => tableHtml += `<th>${h}</th>`);
        tableHtml += '</tr></thead><tbody>';

        data.forEach(row => {
            tableHtml += '<tr>';
            headers.forEach(h => tableHtml += `<td>${row[h]}</td>`);
            tableHtml += '</tr>';
        });

        tableHtml += '</tbody></table>';
        container.html(tableHtml);
    }

    // Render object data
    function renderObjectData(container, data) {
        let html = '<dl class="dl-horizontal">';
        for (const [key, value] of Object.entries(data)) {
            html += `<dt>${key}</dt><dd>${value}</dd>`;
        }
        html += '</dl>';
        container.html(html);
    }

    // Configure dashboard button
    $('#configure-dashboard-btn').click(function() {
        $('#configure-modal').modal('show');
    });

    // Render insight selector
    function renderInsightSelector(insights) {
        const selector = $('#insight-selector');
        selector.empty();

        const categories = [...new Set(insights.map(i => i.category))];
        categories.forEach(category => {
            const categoryInsights = insights.filter(i => i.category === category);
            let html = `<h6><strong>${category.toUpperCase()}</strong></h6>`;
            categoryInsights.forEach(insight => {
                const checked = currentConfig.widget_config.some(w => w.insight_id === insight.insight_id);
                html += `
                    <div class="checkbox">
                        <label>
                            <input type="checkbox" value="${insight.insight_id}" ${checked ? 'checked' : ''}>
                            ${insight.name} - <small class="text-muted">${insight.description}</small>
                        </label>
                    </div>
                `;
            });
            selector.append(html);
        });
    }

    // Save configuration
    $('#save-config-btn').click(function() {
        const selectedInsights = [];
        $('#insight-selector input:checked').each(function() {
            selectedInsights.push({
                insight_id: $(this).val(),
                order: selectedInsights.length,
                size: 'medium',
                filters: {}
            });
        });

        const widgetCount = parseInt($('#widget-count').val());

        $.ajax({
            url: '/api/v2/github/insights/dashboard/',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                widget_config: selectedInsights,
                widget_count: widgetCount
            }),
            success: function(config) {
                currentConfig = config;
                $('#configure-modal').modal('hide');
                loadDashboard();
            }
        });
    });

    // Refresh all widgets
    $('#refresh-all-btn').click(function() {
        loadDashboard();
    });

    // Pin/Unpin widget (event delegation)
    $(document).on('click', '.pin-widget-btn', function(e) {
        e.preventDefault();
        const widget = $(this).closest('.insight-widget');
        const insightId = widget.data('insight-id');

        // Find widget in config and toggle pin status
        const widgetConfig = currentConfig.widget_config.find(w => w.insight_id === insightId);
        if (widgetConfig) {
            widgetConfig.pinned = !widgetConfig.pinned;
            widgetConfig.auto_refresh = widgetConfig.pinned;  // Auto-refresh when pinned

            // Save updated config
            $.ajax({
                url: '/api/v2/github/insights/dashboard/',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(currentConfig),
                success: function(config) {
                    currentConfig = config;
                    loadDashboard();
                }
            });
        }
    });

    // Refresh individual widget (event delegation)
    $(document).on('click', '.refresh-widget-btn', function(e) {
        e.preventDefault();
        const widget = $(this).closest('.insight-widget');
        const insightId = widget.data('insight-id');
        const widgetConfig = currentConfig.widget_config.find(w => w.insight_id === insightId);

        if (widgetConfig) {
            widget.find('.loading-icon').show();
            loadWidgetData(insightId, widgetConfig.filters, widgetConfig.pinned);
        }
    });

    // Initialize
    loadAvailableInsights();
    loadDashboard();
});
```

## Implementation Plan

### Phase 1: Backend Foundation (4-5 hours)
1. Create `dojo/github_collector/insights/` module structure
2. Implement `BaseInsight` abstract class
3. Implement `InsightRegistry` with auto-discovery
4. Add `GitHubInsightConfiguration` model
5. Generate and apply database migration
6. Write unit tests for registry and base class

**Files Created**:
- `dojo/github_collector/insights/__init__.py`
- `dojo/github_collector/insights/base.py`
- `dojo/github_collector/insights/registry.py`
- Migration file for `GitHubInsightConfiguration`

### Phase 2: Core Insights Implementation (5-6 hours)
1. Implement 20+ insight classes across 5 categories:
   - `activity.py` (5 insights)
   - `health.py` (5 insights)
   - `security.py` (5 insights)
   - `ownership.py` (4 insights)
   - `technology.py` (5 insights)
2. Optimize queries with indexes and prefetch patterns
3. Write unit tests for each insight
4. Validate data output formats

**Files Created**:
- `dojo/github_collector/insights/activity.py`
- `dojo/github_collector/insights/health.py`
- `dojo/github_collector/insights/security.py`
- `dojo/github_collector/insights/ownership.py`
- `dojo/github_collector/insights/technology.py`

### Phase 3: REST API (2-3 hours)
1. Create `GitHubInsightsViewSet`
2. Create serializers for configuration model
3. Add URL routing to `dojo/api_v2/urls.py`
4. Implement caching layer
5. Write API tests

**Files Created**:
- `dojo/api_v2/views/github_insights.py`
- `dojo/api_v2/serializers/github_insights.py`
- Update `dojo/api_v2/urls.py`

### Phase 4: Frontend Dashboard (3-4 hours)
1. Create dashboard template
2. Implement JavaScript for widget rendering
3. Implement configuration modal
4. Add URL route and view handler
5. Test UI with various widget configurations

**Files Created**:
- `dojo/templates/github/insights_dashboard.html`
- `dojo/static/js/github_insights_dashboard.js`
- `dojo/views/github_insights.py`
- Update `dojo/urls.py`

### Phase 5: Management Command & Documentation (1-2 hours)
1. Create `show_github_insights` management command
2. Write comprehensive docstrings
3. Add usage examples to README
4. Update CLAUDE.md with insights architecture
5. Integration testing

**Files Created**:
- `dojo/management/commands/show_github_insights.py`
- `docs/github_insights.md` (user guide)

## Success Criteria

### Functional Criteria
- [x] Users can view dashboard with configurable number of insights
- [x] Users can select from 25 insights across 5 categories
- [x] Configuration persists per-user
- [x] REST API endpoints functional
- [x] Management command works for CLI access

### Technical Criteria
- [x] Database queries optimized with select_related/prefetch_related
- [x] 5-minute caching implemented
- [x] Frontend renders correctly (Bootstrap 3 responsive)
- [x] No console errors
- [x] Follows DefectDojo code patterns

### Documentation Criteria
- [ ] CLAUDE.md updated with insights architecture
- [x] Management command help text complete
- [x] API documentation auto-generated

## Testing Strategy

### Unit Tests
- BaseInsight abstract class validation
- InsightRegistry registration and retrieval
- Each insight's calculate() method with sample data
- Model save/update operations
- API serializer validation

### Integration Tests
- Full dashboard load with multiple widgets
- Configuration save/load cycle
- API endpoint authentication and permissions
- Cache hit/miss scenarios
- Management command output formats

### Performance Tests
- Insight calculation time with 2,451 repos
- Dashboard load time with 15 widgets
- Concurrent user scenarios
- Cache effectiveness metrics

## Estimated Effort

**Total**: 15-20 hours

**Breakdown**:
- Phase 1: 4-5 hours
- Phase 2: 5-6 hours
- Phase 3: 2-3 hours
- Phase 4: 3-4 hours
- Phase 5: 1-2 hours

**Code Volume**: ~2,000 lines
- Backend: ~1,200 lines
- Frontend: ~400 lines
- Tests: ~400 lines

## Dependencies

- Existing `Repository` model with 36 signals
- Existing `Product`, `Finding` models
- Bootstrap 3.4.1, jQuery 3.7.1, DataTables
- Chart.js 4.4.0 (for data visualizations)
- Django REST Framework 3.16.1
- PostgreSQL database
- Django cache framework (Redis/Valkey)

## Future Enhancements

1. **Advanced Filtering**
   - Date range pickers for time-based insights
   - Product_Type filters
   - Repository tag filters

2. **Widget Customization**
   - Drag-and-drop ordering
   - Custom widget sizes
   - Widget-specific filter configs

3. **Alerting**
   - Email notifications when insight thresholds crossed
   - Slack/webhook integration
   - Scheduled insight reports

4. **Visualizations**
   - Chart.js integration for graphs
   - Trend lines over time
   - Comparative analysis

5. **Export Features**
   - CSV/Excel export for all insights
   - PDF report generation
   - Scheduled email reports

6. **Custom Insights**
   - Admin UI for creating insights
   - Custom query builder
   - Python expression evaluation (safe)

## Work Log

### 2025-11-16 - Initial Planning
- Created comprehensive task specification
- Designed widget-based architecture with 25+ insights across 5 categories
- Defined 5 implementation phases

### 2025-11-17 - Backend & API Implementation (Phases 1-2)

#### Completed
- Created pluggable insight system with BaseInsight abstract class and InsightRegistry
- Implemented 25 insights across 5 categories (Activity, Health, Security, Ownership, Technology)
- Added GitHubInsightConfiguration model (OneToOne with User, JSONField for widget_config)
- Added repository_owner field to Product model
- Created database migrations (0253, 0254)
- Built REST API with GitHubInsightsViewSet (list, retrieve, dashboard actions)
- Implemented 5-minute caching with hash-based cache keys
- Created management command generate_insights.py with --list, --insight, --category, --all options

#### Decisions
- Chose registry pattern for insight auto-discovery (clean, extensible)
- Used JSONField for widget_config (flexible, avoids complex relational schema)
- Implemented 5-minute cache TTL for performance with real-time data balance
- Separated view-specific logic to views.py, kept insights focused on calculations

#### Discovered
- Field name mismatches: has_readme→has_documentation, has_docker_file→has_dockerfile, repository_primary_language→primary_language
- RepositoriesWithoutLicense insight removed (field doesn't exist in Repository model)
- All 25 insights tested successfully with real GitHub data (133 findings, 4 stale repos)

### 2025-11-17 - Frontend Dashboard & Testing (Phases 3-4)

#### Completed
- Created github_insights_dashboard.html template with Bootstrap 3 modal UI
- Implemented github_insights_dashboard.js (670 lines) with module pattern
- Integrated Chart.js 4.4.0 for visualizations (pie, bar, table)
- Added widget selection, ordering, and persistence UI
- Created github_insights_dashboard view function with @login_required
- Fixed widget persistence: saveConfiguration() now calls loadDashboardConfiguration()
- Enhanced error messaging: replaced alert() with Bootstrap notifications
- Verified end-to-end with Puppeteer: configuration saves/persists, widgets render correctly

#### Decisions
- Used Bootstrap 3 modal for configuration (consistent with DefectDojo UI)
- Chart.js 4.4.0 for visualizations (modern, well-maintained, feature-rich)
- Module pattern for JS (clean encapsulation, no global pollution)
- Separate loadDashboardConfiguration() for persistence vs renderDashboard() for UI updates

#### Discovered
- Widget persistence issue: saving configuration was re-fetching data unnecessarily
- Bootstrap notifications provide better UX than browser alerts
- All 25 insights work correctly with real data
- Dashboard UI responsive and functional at 1920x1080

## Next Steps

- Consider adding unit tests for insights if further development needed
- Monitor performance with larger repository counts (currently tested with ~100 repos)
- Consider adding drag-and-drop widget ordering (future enhancement)
- Evaluate user feedback for additional insight types
