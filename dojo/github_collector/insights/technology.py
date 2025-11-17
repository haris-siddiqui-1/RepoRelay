"""
Technology-based insights for GitHub repositories.

Insights related to programming languages, frameworks, and technology stack.
"""

from typing import Dict, Any, Optional

from django.db.models import Count, Q
from django.utils import timezone

from dojo.github_collector.insights.base import BaseInsight
from dojo.github_collector.insights.registry import InsightRegistry
from dojo.models import Product, App_Analysis


class TechnologyStackDistribution(BaseInsight):
    """Distribution of technologies across repositories."""

    insight_id = 'tech_stack_distribution'
    name = 'Technology Stack Distribution'
    description = 'Most common programming languages and frameworks'
    category = 'technology'
    visualization_type = 'chart'
    chart_type = 'pie'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate technology stack distribution."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset - products with GitHub URLs
        products_query = Product.objects.filter(github_url__isnull=False)

        # Filter by product type if specified
        if product_type_id:
            products_query = products_query.filter(prod_type_id=product_type_id)

        # Get technology analysis from App_Analysis (Technologies)
        tech_counts = App_Analysis.objects.filter(
            product__in=products_query
        ).values('name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # Prepare chart data
        labels = [item['name'] for item in tech_counts]
        values = [item['count'] for item in tech_counts]

        # Color palette for technologies
        colors = [
            '#007bff', '#28a745', '#ffc107', '#dc3545', '#17a2b8',
            '#6c757d', '#fd7e14', '#e83e8c', '#20c997', '#6610f2'
        ][:len(labels)]

        return {
            'title': 'Technology Stack Distribution',
            'data': {
                'labels': labels,
                'values': values,
                'colors': colors
            },
            'chart_config': {
                'type': 'pie',
                'options': {
                    'title': f'Most Common Technologies (Top 10)',
                    'legend': True
                }
            },
            'metadata': {
                'count': len(labels),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id},
                'total_products': products_query.count()
            }
        }


class RepositoriesWithoutTechStack(BaseInsight):
    """Repositories missing technology stack information."""

    insight_id = 'repos_without_tech'
    name = 'Missing Technology Info'
    description = 'Repositories without technology stack analysis'
    category = 'technology'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate repositories without technology information."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset
        products_query = Product.objects.filter(github_url__isnull=False)

        # Filter by product type if specified
        if product_type_id:
            products_query = products_query.filter(prod_type_id=product_type_id)

        # Find products without App_Analysis entries
        products_with_tech = App_Analysis.objects.filter(
            product__in=products_query
        ).values_list('product_id', flat=True).distinct()

        repositories_without_tech = products_query.exclude(
            id__in=products_with_tech
        ).values(
            'id',
            'name',
            'github_url',
            'business_criticality',
            'repository_owner'
        )

        data = [
            {
                'repository': repo['name'],
                'owner': repo['repository_owner'] or 'Unknown',
                'tier': repo['business_criticality'] or 'Unknown',
                'github_url': repo['github_url'],
                'action': 'Run Technology Analysis'
            }
            for repo in repositories_without_tech
        ]

        return {
            'title': 'Repositories Without Technology Information',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id}
            }
        }


class PrimaryLanguageDistribution(BaseInsight):
    """Distribution of primary programming languages."""

    insight_id = 'primary_language_dist'
    name = 'Primary Language Distribution'
    description = 'Distribution of primary programming languages across repositories'
    category = 'technology'
    visualization_type = 'chart'
    chart_type = 'bar'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate primary language distribution."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset
        products_query = Product.objects.filter(github_url__isnull=False)

        # Filter by product type if specified
        if product_type_id:
            products_query = products_query.filter(prod_type_id=product_type_id)

        # Get primary language from primary_language field
        language_counts = products_query.filter(
            primary_language__isnull=False
        ).values('primary_language').annotate(
            count=Count('id')
        ).order_by('-count')[:15]

        # Prepare chart data
        labels = [item['primary_language'] for item in language_counts]
        values = [item['count'] for item in language_counts]
        colors = ['#007bff'] * len(labels)

        return {
            'title': 'Primary Language Distribution',
            'data': {
                'labels': labels,
                'values': values,
                'colors': colors
            },
            'chart_config': {
                'type': 'bar',
                'options': {
                    'title': 'Repository Count by Primary Language',
                    'xAxisLabel': 'Language',
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


class ContainerizedRepositories(BaseInsight):
    """Repositories using Docker/containerization."""

    insight_id = 'containerized_repos'
    name = 'Containerized Repositories'
    description = 'Repositories with Docker/containerization'
    category = 'technology'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate repositories using containerization."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset - products with has_dockerfile flag
        queryset = Product.objects.filter(
            github_url__isnull=False,
            has_dockerfile=True
        )

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(prod_type_id=product_type_id)

        # Get containerized repositories
        repositories = queryset.values(
            'id',
            'name',
            'github_url',
            'business_criticality',
            'primary_language'
        )

        data = [
            {
                'repository': repo['name'],
                'language': repo['primary_language'] or 'Unknown',
                'tier': repo['business_criticality'] or 'Unknown',
                'github_url': repo['github_url']
            }
            for repo in repositories
        ]

        # Calculate percentage
        total_repos = Product.objects.filter(github_url__isnull=False).count()
        containerized_count = len(data)
        containerization_rate = (containerized_count / total_repos * 100) if total_repos > 0 else 0

        return {
            'title': 'Containerized Repositories',
            'data': data,
            'metadata': {
                'count': containerized_count,
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id},
                'containerization_rate': round(containerization_rate, 1),
                'total_repos': total_repos
            }
        }


class LegacyTechnologyRepositories(BaseInsight):
    """Repositories using legacy or deprecated technologies."""

    insight_id = 'legacy_tech_repos'
    name = 'Legacy Technology Repositories'
    description = 'Repositories using older or deprecated technologies'
    category = 'technology'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate repositories using legacy technologies.

        Legacy is defined as Python 2, PHP < 7, Java < 11, Node < 14, etc.
        This is a simplified heuristic based on technology names.
        """
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset
        products_query = Product.objects.filter(github_url__isnull=False)

        # Filter by product type if specified
        if product_type_id:
            products_query = products_query.filter(prod_type_id=product_type_id)

        # Legacy technology patterns (heuristic)
        legacy_patterns = [
            'Python 2',
            'PHP 5',
            'PHP 6',
            'Java 8',
            'Java 7',
            'Node 12',
            'Node 10',
            'Angular 1',
            'AngularJS',
            'jQuery'
        ]

        # Find products with App_Analysis matching legacy patterns
        legacy_products = []

        for product in products_query:
            tech_analysis = App_Analysis.objects.filter(product=product)

            for tech in tech_analysis:
                if any(pattern.lower() in tech.name.lower() for pattern in legacy_patterns):
                    legacy_products.append({
                        'repository': product.name,
                        'owner': product.repository_owner or 'Unknown',
                        'legacy_tech': tech.name,
                        'tier': product.business_criticality or 'Unknown',
                        'github_url': product.github_url
                    })
                    break  # Only count each product once

        return {
            'title': 'Legacy Technology Repositories',
            'data': legacy_products,
            'metadata': {
                'count': len(legacy_products),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id},
                'note': 'Legacy detection based on heuristic patterns'
            }
        }


# Register all insights
InsightRegistry.register(TechnologyStackDistribution)
InsightRegistry.register(RepositoriesWithoutTechStack)
InsightRegistry.register(PrimaryLanguageDistribution)
InsightRegistry.register(ContainerizedRepositories)
InsightRegistry.register(LegacyTechnologyRepositories)
