"""
Ownership-based insights for GitHub repositories.

Insights related to repository ownership, team structure, and organizational distribution.
"""

from typing import Dict, Any, Optional

from django.db.models import Count, Q
from django.utils import timezone

from dojo.github_collector.insights.base import BaseInsight
from dojo.github_collector.insights.registry import InsightRegistry
from dojo.models import Product


class RepositoriesByOwner(BaseInsight):
    """Distribution of repositories across owners."""

    insight_id = 'repos_by_owner'
    name = 'Repositories by Owner'
    description = 'Count of repositories per owner/team'
    category = 'ownership'
    visualization_type = 'chart'
    chart_type = 'bar'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate repository distribution by owner."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset
        queryset = Product.objects.filter(github_url__isnull=False)

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(prod_type_id=product_type_id)

        # Count repositories per owner
        owner_counts = queryset.values('repository_owner').annotate(
            count=Count('id')
        ).filter(repository_owner__isnull=False).order_by('-count')[:15]

        # Prepare chart data
        labels = [item['repository_owner'] or 'Unknown' for item in owner_counts]
        values = [item['count'] for item in owner_counts]
        colors = ['#007bff'] * len(labels)

        return {
            'title': 'Repositories by Owner',
            'data': {
                'labels': labels,
                'values': values,
                'colors': colors
            },
            'chart_config': {
                'type': 'bar',
                'options': {
                    'title': 'Repository Count per Owner',
                    'xAxisLabel': 'Owner',
                    'yAxisLabel': 'Repository Count'
                }
            },
            'metadata': {
                'count': len(labels),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id},
                'total_repos': sum(values)
            }
        }


class RepositoriesWithoutOwner(BaseInsight):
    """Repositories missing ownership information."""

    insight_id = 'repos_without_owner'
    name = 'Repositories Without Owner'
    description = 'Repositories with missing or unknown owner'
    category = 'ownership'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate repositories without owner information."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset
        queryset = Product.objects.filter(
            github_url__isnull=False,
            repository_owner__isnull=True
        )

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(prod_type_id=product_type_id)

        # Get repositories without owners
        repositories = queryset.values(
            'id',
            'name',
            'github_url',
            'business_criticality'
        )

        data = [
            {
                'repository': repo['name'],
                'tier': repo['business_criticality'] or 'Unknown',
                'github_url': repo['github_url'],
                'action': 'Assign Owner'
            }
            for repo in repositories
        ]

        return {
            'title': 'Repositories Without Owner',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id}
            }
        }


class OwnershipByCriticality(BaseInsight):
    """Owner distribution across business criticality tiers."""

    insight_id = 'ownership_by_tier'
    name = 'Ownership by Criticality'
    description = 'Repository ownership across business criticality tiers'
    category = 'ownership'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate ownership distribution by criticality tier."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset
        queryset = Product.objects.filter(
            github_url__isnull=False,
            repository_owner__isnull=False
        )

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(prod_type_id=product_type_id)

        # Get counts by owner and tier
        tiers = ['very_high', 'high', 'medium', 'low', 'very_low', 'none']
        tier_labels = {
            'very_high': 'Very High',
            'high': 'High',
            'medium': 'Medium',
            'low': 'Low',
            'very_low': 'Very Low',
            'none': 'Unknown'
        }

        data = []
        for tier in tiers:
            tier_queryset = queryset.filter(business_criticality=tier)
            owner_counts = tier_queryset.values('repository_owner').annotate(
                count=Count('id')
            ).order_by('-count')[:5]

            for owner in owner_counts:
                data.append({
                    'tier': tier_labels[tier],
                    'owner': owner['repository_owner'],
                    'repo_count': owner['count']
                })

        return {
            'title': 'Ownership Distribution by Criticality Tier',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id}
            }
        }


class HighCriticalityOwners(BaseInsight):
    """Owners responsible for high/very-high criticality repositories."""

    insight_id = 'high_criticality_owners'
    name = 'High Criticality Owners'
    description = 'Owners of high and very-high criticality repositories'
    category = 'ownership'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate owners of high criticality repositories."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset - high and very high criticality repos
        queryset = Product.objects.filter(
            github_url__isnull=False,
            repository_owner__isnull=False,
            business_criticality__in=['high', 'very_high']
        )

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(prod_type_id=product_type_id)

        # Count by owner
        owner_counts = queryset.values('repository_owner').annotate(
            count=Count('id'),
            very_high_count=Count('id', filter=Q(business_criticality='very_high')),
            high_count=Count('id', filter=Q(business_criticality='high'))
        ).order_by('-very_high_count', '-high_count')

        data = [
            {
                'owner': owner['repository_owner'],
                'very_high_repos': owner['very_high_count'],
                'high_repos': owner['high_count'],
                'total_critical_repos': owner['count']
            }
            for owner in owner_counts
        ]

        return {
            'title': 'Owners of High Criticality Repositories',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id}
            }
        }


# Register all insights
InsightRegistry.register(RepositoriesByOwner)
InsightRegistry.register(RepositoriesWithoutOwner)
InsightRegistry.register(OwnershipByCriticality)
InsightRegistry.register(HighCriticalityOwners)
