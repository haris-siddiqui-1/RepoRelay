"""
Activity-based insights for GitHub repositories.

Insights related to repository activity, commit frequency, and development velocity.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from django.db.models import Count, Max, Q
from django.utils import timezone

from dojo.github_collector.insights.base import BaseInsight
from dojo.github_collector.insights.registry import InsightRegistry
from dojo.models import Product


class MostRecentlyUpdatedRepos(BaseInsight):
    """Repositories with the most recent commit activity."""

    insight_id = 'most_updated_repos'
    name = 'Most Recently Updated'
    description = 'Repositories with the most recent commits'
    category = 'activity'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate repositories with most recent commits.

        Uses existing last_commit_date field from Repository model.
        """
        filters = filters or {}
        days = filters.get('days', 30)
        product_type_id = filters.get('product_type_id')

        # Base queryset - products with GitHub URLs and commit dates
        queryset = Product.objects.filter(
            github_url__isnull=False
        ).exclude(
            last_commit_date__isnull=True
        )

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(prod_type_id=product_type_id)

        # Filter by time range
        cutoff_date = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(last_commit_date__gte=cutoff_date)

        # Get top 20 most recently updated
        repositories = queryset.order_by('-last_commit_date')[:20].values(
            'id',
            'name',
            'github_url',
            'last_commit_date',
            'business_criticality',
            'repository_owner'
        )

        data = [
            {
                'repository': repo['name'],
                'owner': repo['repository_owner'] or 'Unknown',
                'last_commit': repo['last_commit_date'].strftime('%Y-%m-%d %H:%M') if repo['last_commit_date'] else 'Unknown',
                'tier': repo['business_criticality'] or 'Unknown',
                'github_url': repo['github_url']
            }
            for repo in repositories
        ]

        return {
            'title': f'Most Recently Updated Repositories (Last {days} days)',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now(),
                'filters_applied': {'days': days, 'product_type_id': product_type_id}
            }
        }


class StaleRepositories(BaseInsight):
    """Repositories with no recent commit activity."""

    insight_id = 'stale_repos'
    name = 'Stale Repositories'
    description = 'Repositories with no commits in specified time period'
    category = 'activity'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate repositories with stale activity.

        Uses existing last_commit_date field from Repository model.
        """
        filters = filters or {}
        days = filters.get('days', 90)  # Default to 90 days for "stale"
        product_type_id = filters.get('product_type_id')

        # Base queryset
        queryset = Product.objects.filter(
            github_url__isnull=False
        )

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(prod_type_id=product_type_id)

        # Filter for stale repos (old last_commit_date or null)
        cutoff_date = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(
            Q(last_commit_date__lt=cutoff_date) | Q(last_commit_date__isnull=True)
        )

        # Get stale repositories
        repositories = queryset.order_by('last_commit_date')[:20].values(
            'id',
            'name',
            'github_url',
            'last_commit_date',
            'business_criticality',
            'repository_owner'
        )

        data = [
            {
                'repository': repo['name'],
                'owner': repo['repository_owner'] or 'Unknown',
                'last_commit': repo['last_commit_date'].strftime('%Y-%m-%d') if repo['last_commit_date'] else 'Never',
                'days_inactive': (timezone.now().date() - repo['last_commit_date'].date()).days if repo['last_commit_date'] else 'Unknown',
                'tier': repo['business_criticality'] or 'Unknown',
                'github_url': repo['github_url']
            }
            for repo in repositories
        ]

        return {
            'title': f'Stale Repositories (No commits in {days}+ days)',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now(),
                'filters_applied': {'days': days, 'product_type_id': product_type_id}
            }
        }


class HighestCommitFrequency(BaseInsight):
    """Repositories with highest commit frequency (placeholder for activity collection)."""

    insight_id = 'highest_commit_frequency'
    name = 'Highest Commit Frequency'
    description = 'Repositories ranked by commit frequency (requires activity collection)'
    category = 'activity'
    visualization_type = 'chart'
    chart_type = 'bar'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate commit frequency ranking.

        PLACEHOLDER: Requires commit_count field from activity collection task.
        Returns placeholder data until that task is completed.
        """
        return {
            'title': 'Highest Commit Frequency',
            'data': {
                'labels': [],
                'values': [],
                'colors': []
            },
            'chart_config': {
                'type': 'bar',
                'options': {
                    'title': 'Commit Frequency (Coming Soon)',
                    'xAxisLabel': 'Repository',
                    'yAxisLabel': 'Commits (Last 30 Days)'
                }
            },
            'metadata': {
                'count': 0,
                'timestamp': timezone.now(),
                'filters_applied': filters or {},
                'placeholder': True,
                'message': 'This insight requires commit_count field. Complete activity collection task first.'
            }
        }


class HighIssueCount(BaseInsight):
    """Repositories with high open issue counts (placeholder for activity collection)."""

    insight_id = 'high_issue_count'
    name = 'High Open Issue Count'
    description = 'Repositories with most open issues (requires activity collection)'
    category = 'activity'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate repositories with high issue counts.

        PLACEHOLDER: Requires open_issues_count field from activity collection task.
        Returns placeholder data until that task is completed.
        """
        return {
            'title': 'Repositories with High Open Issue Counts',
            'data': [],
            'metadata': {
                'count': 0,
                'timestamp': timezone.now(),
                'filters_applied': filters or {},
                'placeholder': True,
                'message': 'This insight requires open_issues_count field. Complete activity collection task first.'
            }
        }


class OldOpenPullRequests(BaseInsight):
    """Repositories with old open pull requests (placeholder for activity collection)."""

    insight_id = 'old_open_prs'
    name = 'Old Open Pull Requests'
    description = 'Repositories with oldest open PRs (requires activity collection)'
    category = 'activity'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate repositories with old open PRs.

        PLACEHOLDER: Requires open_pr_count field from activity collection task.
        Returns placeholder data until that task is completed.
        """
        return {
            'title': 'Repositories with Old Open Pull Requests',
            'data': [],
            'metadata': {
                'count': 0,
                'timestamp': timezone.now(),
                'filters_applied': filters or {},
                'placeholder': True,
                'message': 'This insight requires open_pr_count field. Complete activity collection task first.'
            }
        }


# Register all insights
InsightRegistry.register(MostRecentlyUpdatedRepos)
InsightRegistry.register(StaleRepositories)
InsightRegistry.register(HighestCommitFrequency)
InsightRegistry.register(HighIssueCount)
InsightRegistry.register(OldOpenPullRequests)
