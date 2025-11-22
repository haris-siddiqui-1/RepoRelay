"""
Health-based insights for GitHub repositories.

Insights related to repository quality, documentation, and best practices.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from django.db.models import Count, Q, Case, When, IntegerField
from django.utils import timezone

from dojo.github_collector.insights.base import BaseInsight
from dojo.github_collector.insights.registry import InsightRegistry
from dojo.models import Product, Repository


class RepositoriesWithoutREADME(BaseInsight):
    """Repositories missing documentation files."""

    insight_id = 'repos_without_readme'
    name = 'Missing Documentation'
    description = 'Repositories without documentation (README or docs/)'
    category = 'health'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate repositories missing documentation."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Query Repository model for enrichment data
        queryset = Repository.objects.filter(has_documentation=False).select_related('product')

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(product__prod_type_id=product_type_id)

        # Get repositories with enrichment data
        repositories = queryset.values(
            'id',
            'name',
            'github_url',
            'tier',
            'days_since_last_commit',
            'active_contributors_90d',
            'cached_finding_counts',
            'dependabot_alert_count',
            'codeql_alert_count',
            'secret_scanning_alert_count',
            'has_tests',
            'has_ci_cd',
            'readme_length',
            'last_commit_date'
        )

        data = []
        for repo in repositories:
            # Calculate total finding count
            finding_count = 0
            if repo['cached_finding_counts']:
                finding_count = sum(repo['cached_finding_counts'].values())

            # Calculate total alert count
            alert_count = (
                (repo['dependabot_alert_count'] or 0) +
                (repo['codeql_alert_count'] or 0) +
                (repo['secret_scanning_alert_count'] or 0)
            )

            data.append({
                'repository': repo['name'],
                'tier': repo['tier'] or 'unknown',
                'github_url': repo['github_url'],
                'days_since_last_commit': repo['days_since_last_commit'],
                'contributors_90d': repo['active_contributors_90d'],
                'finding_count': finding_count,
                'alert_count': alert_count,
                'has_tests': repo['has_tests'],
                'has_ci_cd': repo['has_ci_cd'],
                'readme_length': repo['readme_length'] or 0,
                'last_commit_date': repo['last_commit_date'].isoformat() if repo['last_commit_date'] else None
            })

        return {
            'title': 'Repositories Without Documentation',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id}
            }
        }


class RepositoriesWithoutCICD(BaseInsight):
    """Repositories missing CI/CD pipelines."""

    insight_id = 'repos_without_cicd'
    name = 'Missing CI/CD'
    description = 'Repositories without CI/CD configurations'
    category = 'health'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate repositories missing CI/CD pipelines."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Query Repository model for enrichment data
        queryset = Repository.objects.filter(has_ci_cd=False).select_related('product')

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(product__prod_type_id=product_type_id)

        # Get repositories with enrichment data
        repositories = queryset.values(
            'id',
            'name',
            'github_url',
            'tier',
            'days_since_last_commit',
            'active_contributors_90d',
            'cached_finding_counts',
            'dependabot_alert_count',
            'codeql_alert_count',
            'secret_scanning_alert_count',
            'has_tests',
            'has_documentation',
            'last_commit_date'
        )

        data = []
        for repo in repositories:
            # Calculate total finding count
            finding_count = 0
            if repo['cached_finding_counts']:
                finding_count = sum(repo['cached_finding_counts'].values())

            # Calculate total alert count
            alert_count = (
                (repo['dependabot_alert_count'] or 0) +
                (repo['codeql_alert_count'] or 0) +
                (repo['secret_scanning_alert_count'] or 0)
            )

            data.append({
                'repository': repo['name'],
                'tier': repo['tier'] or 'unknown',
                'github_url': repo['github_url'],
                'days_since_last_commit': repo['days_since_last_commit'],
                'contributors_90d': repo['active_contributors_90d'],
                'finding_count': finding_count,
                'alert_count': alert_count,
                'has_tests': repo['has_tests'],
                'has_documentation': repo['has_documentation'],
                'last_commit_date': repo['last_commit_date'].isoformat() if repo['last_commit_date'] else None
            })

        return {
            'title': 'Repositories Without CI/CD',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id}
            }
        }


class RepositoryHealthScore(BaseInsight):
    """Overall repository health score based on best practices."""

    insight_id = 'repo_health_score'
    name = 'Repository Health Score'
    description = 'Health score based on documentation, CI/CD, and security'
    category = 'health'
    visualization_type = 'chart'
    chart_type = 'bar'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate health scores for repositories.

        Health score = % of best practices followed:
        - Documentation (33%)
        - CI/CD (33%)
        - No critical findings (33%)
        """
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset
        queryset = Product.objects.filter(github_url__isnull=False)

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(prod_type_id=product_type_id)

        # Calculate health scores
        from dojo.models import Finding

        repositories = []
        for product in queryset[:20]:  # Limit to top 20
            score = 0

            # Documentation check (33 points)
            if product.has_documentation:
                score += 33

            # CI/CD check (33 points)
            if product.has_ci_cd:
                score += 33

            # Security check - no critical findings (34 points to reach 100)
            critical_findings = Finding.objects.filter(
                test__engagement__product=product,
                severity='Critical',
                active=True
            ).count()

            if critical_findings == 0:
                score += 34

            repositories.append({
                'name': product.name,
                'score': score,
                'tier': product.business_criticality or 'Unknown'
            })

        # Sort by score descending
        repositories.sort(key=lambda x: x['score'], reverse=True)

        # Prepare chart data
        labels = [repo['name'][:20] for repo in repositories]  # Truncate long names
        values = [repo['score'] for repo in repositories]
        colors = [
            '#28a745' if score >= 75 else  # Green
            '#ffc107' if score >= 50 else  # Yellow
            '#dc3545'  # Red
            for score in values
        ]

        return {
            'title': 'Repository Health Scores',
            'data': {
                'labels': labels,
                'values': values,
                'colors': colors
            },
            'chart_config': {
                'type': 'bar',
                'options': {
                    'title': 'Health Score (Documentation + CI/CD + Security)',
                    'xAxisLabel': 'Repository',
                    'yAxisLabel': 'Health Score (%)',
                    'min': 0,
                    'max': 100
                }
            },
            'metadata': {
                'count': len(repositories),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id},
                'average_score': sum(values) / len(values) if values else 0
            }
        }


class BestPracticeAdoption(BaseInsight):
    """Distribution of best practice adoption across repositories."""

    insight_id = 'best_practice_adoption'
    name = 'Best Practice Adoption'
    description = 'Percentage of repositories following each best practice'
    category = 'health'
    visualization_type = 'chart'
    chart_type = 'pie'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate best practice adoption rates."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset
        queryset = Product.objects.filter(github_url__isnull=False)

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(prod_type_id=product_type_id)

        total_repos = queryset.count()

        if total_repos == 0:
            return {
                'title': 'Best Practice Adoption',
                'data': {'labels': [], 'values': [], 'colors': []},
                'chart_config': {
                    'type': 'pie',
                    'options': {'title': 'No repositories found'}
                },
                'metadata': {
                    'count': 0,
                    'timestamp': timezone.now(),
                    'filters_applied': {'product_type_id': product_type_id}
                }
            }

        # Calculate adoption percentages
        docs_count = queryset.filter(has_documentation=True).count()
        cicd_count = queryset.filter(has_ci_cd=True).count()

        labels = ['Documentation', 'CI/CD', 'None']
        values = [
            docs_count,
            cicd_count,
            max(0, total_repos - max(docs_count, cicd_count))
        ]
        colors = ['#28a745', '#ffc107', '#dc3545']

        return {
            'title': 'Best Practice Adoption',
            'data': {
                'labels': labels,
                'values': values,
                'colors': colors
            },
            'chart_config': {
                'type': 'pie',
                'options': {
                    'title': f'Best Practice Adoption (Total: {total_repos} repos)',
                    'legend': True
                }
            },
            'metadata': {
                'count': total_repos,
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id},
                'percentages': {
                    'documentation': round((docs_count / total_repos) * 100, 1),
                    'cicd': round((cicd_count / total_repos) * 100, 1)
                }
            }
        }


# Register all insights
InsightRegistry.register(RepositoriesWithoutREADME)
InsightRegistry.register(RepositoriesWithoutCICD)
InsightRegistry.register(RepositoryHealthScore)
InsightRegistry.register(BestPracticeAdoption)
