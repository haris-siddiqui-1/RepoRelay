"""
Consumption-based insights for GitHub repositories.

Insights related to internal dependency relationships and consumption patterns.
These help identify shared libraries and critical infrastructure based on how
many other internal repositories depend on them.
"""

from typing import Dict, Any, Optional, List

from django.db.models import Count, Q, Sum, Avg, F
from django.utils import timezone

from dojo.github_collector.insights.base import BaseInsight
from dojo.github_collector.insights.registry import InsightRegistry
from dojo.models import Repository


class MostConsumedRepositories(BaseInsight):
    """Repositories with the most internal consumers."""

    insight_id = 'most_consumed_repos'
    name = 'Most Consumed Repositories'
    description = 'Internal repositories that are dependencies for other repos (shared libraries)'
    category = 'consumption'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate repositories with highest dependent_repo_count."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')
        limit = filters.get('limit', 20)

        queryset = Repository.objects.filter(
            dependent_repo_count__gt=0
        ).select_related('product')

        if product_type_id:
            queryset = queryset.filter(product__prod_type_id=product_type_id)

        repositories = queryset.order_by('-dependent_repo_count').values(
            'id',
            'name',
            'github_url',
            'tier',
            'consumption_tier_override',
            'dependent_repo_count',
            'is_shared_library',
            'days_since_last_commit',
            'cached_finding_counts',
        )[:limit]

        data = []
        for repo in repositories:
            # Calculate total findings
            finding_count = 0
            if repo['cached_finding_counts']:
                finding_count = sum(repo['cached_finding_counts'].values())

            # Show effective tier (consumption override or base tier)
            effective_tier = repo['consumption_tier_override'] or repo['tier'] or 'unknown'

            data.append({
                'repository': repo['name'],
                'dependent_count': repo['dependent_repo_count'],
                'effective_tier': effective_tier,
                'base_tier': repo['tier'] or 'unknown',
                'is_shared_library': repo['is_shared_library'],
                'github_url': repo['github_url'],
                'finding_count': finding_count,
                'days_since_commit': repo['days_since_last_commit'],
            })

        return {
            'title': 'Most Consumed Repositories',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now(),
                'description': 'Repositories ordered by number of internal consumers',
            },
            'columns': [
                {'key': 'repository', 'label': 'Repository'},
                {'key': 'dependent_count', 'label': 'Consumers'},
                {'key': 'effective_tier', 'label': 'Effective Tier'},
                {'key': 'base_tier', 'label': 'Base Tier'},
                {'key': 'finding_count', 'label': 'Findings'},
                {'key': 'days_since_commit', 'label': 'Days Since Commit'},
            ]
        }


class ConsumptionTierOverrides(BaseInsight):
    """Repositories where consumption tier differs from base tier."""

    insight_id = 'consumption_tier_overrides'
    name = 'Tier Overrides by Consumption'
    description = 'Repositories promoted to higher tiers due to high consumption'
    category = 'consumption'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate repositories with tier overrides."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        queryset = Repository.objects.filter(
            consumption_tier_override__isnull=False
        ).exclude(
            # Only show where override differs from base tier
            tier=F('consumption_tier_override')
        ).select_related('product')

        if product_type_id:
            queryset = queryset.filter(product__prod_type_id=product_type_id)

        repositories = queryset.order_by('-dependent_repo_count').values(
            'id',
            'name',
            'github_url',
            'tier',
            'consumption_tier_override',
            'dependent_repo_count',
            'days_since_last_commit',
            'cached_finding_counts',
        )

        data = []
        for repo in repositories:
            finding_count = 0
            if repo['cached_finding_counts']:
                finding_count = sum(repo['cached_finding_counts'].values())

            data.append({
                'repository': repo['name'],
                'original_tier': repo['tier'] or 'unknown',
                'new_tier': repo['consumption_tier_override'],
                'dependent_count': repo['dependent_repo_count'],
                'github_url': repo['github_url'],
                'finding_count': finding_count,
                'days_since_commit': repo['days_since_last_commit'],
            })

        return {
            'title': 'Tier Overrides by Consumption',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now(),
                'description': 'Repos promoted to higher tiers due to being consumed by many others',
            },
            'columns': [
                {'key': 'repository', 'label': 'Repository'},
                {'key': 'original_tier', 'label': 'Original Tier'},
                {'key': 'new_tier', 'label': 'Override Tier'},
                {'key': 'dependent_count', 'label': 'Consumers'},
                {'key': 'finding_count', 'label': 'Findings'},
            ]
        }


class ConsumptionDistribution(BaseInsight):
    """Distribution of repositories by consumption level."""

    insight_id = 'consumption_distribution'
    name = 'Consumption Distribution'
    description = 'Distribution of repositories by number of internal consumers'
    category = 'consumption'
    visualization_type = 'chart'
    chart_type = 'bar'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate consumption distribution."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        queryset = Repository.objects.all()

        if product_type_id:
            queryset = queryset.filter(product__prod_type_id=product_type_id)

        # Aggregate by consumption levels
        tier1_count = queryset.filter(dependent_repo_count__gte=50).count()
        tier2_count = queryset.filter(dependent_repo_count__gte=20, dependent_repo_count__lt=50).count()
        shared_library_count = queryset.filter(dependent_repo_count__gte=5, dependent_repo_count__lt=20).count()
        some_consumers = queryset.filter(dependent_repo_count__gte=1, dependent_repo_count__lt=5).count()
        no_consumers = queryset.filter(dependent_repo_count=0).count()

        labels = [
            'Critical (50+)',
            'Widely Used (20-49)',
            'Shared Library (5-19)',
            'Some Consumers (1-4)',
            'No Consumers'
        ]
        values = [tier1_count, tier2_count, shared_library_count, some_consumers, no_consumers]
        colors = ['#EF4444', '#F59E0B', '#8B5CF6', '#3B82F6', '#6B7280']

        return {
            'title': 'Consumption Distribution',
            'data': {
                'labels': labels,
                'values': values,
                'colors': colors,
            },
            'metadata': {
                'total': sum(values),
                'timestamp': timezone.now(),
            }
        }


class SharedLibraryFindings(BaseInsight):
    """Findings on shared library repositories."""

    insight_id = 'shared_library_findings'
    name = 'Shared Library Findings'
    description = 'Vulnerability findings on shared libraries (consumed by 5+ repos)'
    category = 'consumption'
    visualization_type = 'chart'
    chart_type = 'pie'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate findings distribution by severity on shared libraries."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        queryset = Repository.objects.filter(is_shared_library=True)

        if product_type_id:
            queryset = queryset.filter(product__prod_type_id=product_type_id)

        # Aggregate cached finding counts
        severity_counts = {
            'Critical': 0,
            'High': 0,
            'Medium': 0,
            'Low': 0,
            'Info': 0,
        }

        for repo in queryset.values('cached_finding_counts'):
            counts = repo['cached_finding_counts'] or {}
            for severity, count in counts.items():
                if severity in severity_counts:
                    severity_counts[severity] += count

        labels = list(severity_counts.keys())
        values = list(severity_counts.values())
        colors = ['#EF4444', '#F59E0B', '#EAB308', '#3B82F6', '#6B7280']

        return {
            'title': 'Shared Library Findings by Severity',
            'data': {
                'labels': labels,
                'values': values,
                'colors': colors,
            },
            'metadata': {
                'total_findings': sum(values),
                'shared_library_count': queryset.count(),
                'timestamp': timezone.now(),
            }
        }


class DormantSharedLibraries(BaseInsight):
    """Shared libraries with no recent activity - high risk for stale vulnerabilities."""

    insight_id = 'dormant_shared_libraries'
    name = 'Dormant Shared Libraries'
    description = 'Shared libraries (5+ consumers) with no commits in 90+ days'
    category = 'consumption'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate dormant shared libraries."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')
        dormant_days = filters.get('dormant_days', 90)

        queryset = Repository.objects.filter(
            is_shared_library=True,
            days_since_last_commit__gte=dormant_days
        ).select_related('product')

        if product_type_id:
            queryset = queryset.filter(product__prod_type_id=product_type_id)

        repositories = queryset.order_by('-dependent_repo_count').values(
            'id',
            'name',
            'github_url',
            'tier',
            'consumption_tier_override',
            'dependent_repo_count',
            'days_since_last_commit',
            'cached_finding_counts',
        )

        data = []
        for repo in repositories:
            finding_count = 0
            if repo['cached_finding_counts']:
                finding_count = sum(repo['cached_finding_counts'].values())

            effective_tier = repo['consumption_tier_override'] or repo['tier'] or 'unknown'

            data.append({
                'repository': repo['name'],
                'dependent_count': repo['dependent_repo_count'],
                'effective_tier': effective_tier,
                'days_since_commit': repo['days_since_last_commit'],
                'github_url': repo['github_url'],
                'finding_count': finding_count,
            })

        return {
            'title': 'Dormant Shared Libraries',
            'data': data,
            'metadata': {
                'count': len(data),
                'dormant_threshold_days': dormant_days,
                'timestamp': timezone.now(),
                'description': f'Shared libraries with no commits in {dormant_days}+ days',
            },
            'columns': [
                {'key': 'repository', 'label': 'Repository'},
                {'key': 'dependent_count', 'label': 'Consumers'},
                {'key': 'effective_tier', 'label': 'Tier'},
                {'key': 'days_since_commit', 'label': 'Days Dormant'},
                {'key': 'finding_count', 'label': 'Findings'},
            ]
        }


class ConsumptionSummary(BaseInsight):
    """Summary statistics for dependency graph."""

    insight_id = 'consumption_summary'
    name = 'Consumption Summary'
    description = 'Overview of internal dependency relationships'
    category = 'consumption'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate consumption summary statistics."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        queryset = Repository.objects.all()

        if product_type_id:
            queryset = queryset.filter(product__prod_type_id=product_type_id)

        total_repos = queryset.count()

        # Aggregations
        stats = queryset.aggregate(
            total_dependent_count=Sum('dependent_repo_count'),
            avg_dependent_count=Avg('dependent_repo_count'),
            shared_library_count=Count('id', filter=Q(is_shared_library=True)),
            tier_override_count=Count('id', filter=Q(consumption_tier_override__isnull=False)),
            critical_infra_count=Count('id', filter=Q(dependent_repo_count__gte=50)),
            widely_used_count=Count('id', filter=Q(dependent_repo_count__gte=20)),
        )

        data = [
            {'metric': 'Total Repositories', 'value': total_repos},
            {'metric': 'Total Dependency Links', 'value': stats['total_dependent_count'] or 0},
            {'metric': 'Avg Consumers per Repo', 'value': round(stats['avg_dependent_count'] or 0, 2)},
            {'metric': 'Shared Libraries (5+)', 'value': stats['shared_library_count']},
            {'metric': 'Critical Infrastructure (50+)', 'value': stats['critical_infra_count']},
            {'metric': 'Widely Used (20+)', 'value': stats['widely_used_count']},
            {'metric': 'Tier Overrides Applied', 'value': stats['tier_override_count']},
        ]

        return {
            'title': 'Consumption Summary',
            'data': data,
            'metadata': {
                'timestamp': timezone.now(),
            },
            'columns': [
                {'key': 'metric', 'label': 'Metric'},
                {'key': 'value', 'label': 'Value'},
            ]
        }


# Register all insights
InsightRegistry.register(MostConsumedRepositories)
InsightRegistry.register(ConsumptionTierOverrides)
InsightRegistry.register(ConsumptionDistribution)
InsightRegistry.register(SharedLibraryFindings)
InsightRegistry.register(DormantSharedLibraries)
InsightRegistry.register(ConsumptionSummary)
