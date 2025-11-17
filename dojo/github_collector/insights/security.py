"""
Security-based insights for GitHub repositories.

Analytics and correlations for vulnerability management and security posture.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from django.db.models import Count, Q, Avg, Max, Min, F
from django.utils import timezone

from dojo.github_collector.insights.base import BaseInsight
from dojo.github_collector.insights.registry import InsightRegistry
from dojo.models import Product, Finding


class VulnerabilityDistribution(BaseInsight):
    """Distribution of vulnerabilities by severity across all repositories."""

    insight_id = 'vuln_distribution'
    name = 'Vulnerability Distribution'
    description = 'Distribution of active findings by severity'
    category = 'security'
    visualization_type = 'chart'
    chart_type = 'pie'
    cache_duration = 60  # 1 minute cache for pinned widgets

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate vulnerability distribution by severity."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset - active findings in GitHub-tracked products
        queryset = Finding.objects.filter(
            active=True,
            test__engagement__product__github_url__isnull=False
        )

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(
                test__engagement__product__prod_type_id=product_type_id
            )

        # Count by severity
        severity_counts = queryset.values('severity').annotate(
            count=Count('id')
        ).order_by('-count')

        # Prepare chart data
        severity_colors = {
            'Critical': '#dc3545',  # Red
            'High': '#fd7e14',      # Orange
            'Medium': '#ffc107',    # Yellow
            'Low': '#28a745',       # Green
            'Info': '#17a2b8'       # Blue
        }

        labels = [item['severity'] for item in severity_counts]
        values = [item['count'] for item in severity_counts]
        colors = [severity_colors.get(sev, '#6c757d') for sev in labels]

        total_findings = sum(values)

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
                    'title': f'Total Active Findings: {total_findings}',
                    'legend': True
                }
            },
            'metadata': {
                'count': total_findings,
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id}
            }
        }


class CriticalVulnTrend(BaseInsight):
    """Trend of critical vulnerabilities over time."""

    insight_id = 'critical_vuln_trend'
    name = 'Critical Vulnerability Trend'
    description = 'Trend of critical findings over last 90 days'
    category = 'security'
    visualization_type = 'chart'
    chart_type = 'line'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate critical vulnerability trend."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')
        days = filters.get('days', 90)

        # Generate date range for last N days
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # Base queryset
        queryset = Finding.objects.filter(
            severity='Critical',
            test__engagement__product__github_url__isnull=False,
            date__gte=start_date
        )

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(
                test__engagement__product__prod_type_id=product_type_id
            )

        # Group by week for better visualization
        from django.db.models.functions import TruncWeek

        weekly_counts = queryset.annotate(
            week=TruncWeek('date')
        ).values('week').annotate(
            count=Count('id')
        ).order_by('week')

        # Prepare chart data
        labels = [item['week'].strftime('%Y-%m-%d') for item in weekly_counts]
        values = [item['count'] for item in weekly_counts]

        return {
            'title': f'Critical Vulnerability Trend (Last {days} days)',
            'data': {
                'labels': labels,
                'values': values,
                'colors': ['#dc3545']  # Red for critical
            },
            'chart_config': {
                'type': 'line',
                'options': {
                    'title': 'Critical Findings by Week',
                    'xAxisLabel': 'Week',
                    'yAxisLabel': 'Count',
                    'fill': False
                }
            },
            'metadata': {
                'count': len(labels),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id, 'days': days},
                'total_critical': sum(values)
            }
        }


class TopVulnerableRepositories(BaseInsight):
    """Repositories with most active vulnerabilities."""

    insight_id = 'top_vulnerable_repos'
    name = 'Top Vulnerable Repositories'
    description = 'Repositories ranked by active vulnerability count'
    category = 'security'
    visualization_type = 'chart'
    chart_type = 'bar'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate most vulnerable repositories."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset
        products_query = Product.objects.filter(github_url__isnull=False)

        # Filter by product type if specified
        if product_type_id:
            products_query = products_query.filter(prod_type_id=product_type_id)

        # Count active findings per product
        products_with_counts = products_query.annotate(
            vuln_count=Count(
                'engagement__test__finding',
                filter=Q(engagement__test__finding__active=True)
            )
        ).filter(vuln_count__gt=0).order_by('-vuln_count')[:15]

        # Prepare chart data
        labels = [p.name[:20] for p in products_with_counts]  # Truncate long names
        values = [p.vuln_count for p in products_with_counts]
        colors = [
            '#dc3545' if count > 50 else  # Red
            '#ffc107' if count > 20 else  # Yellow
            '#28a745'  # Green
            for count in values
        ]

        return {
            'title': 'Top Vulnerable Repositories',
            'data': {
                'labels': labels,
                'values': values,
                'colors': colors
            },
            'chart_config': {
                'type': 'bar',
                'options': {
                    'title': 'Active Findings per Repository',
                    'xAxisLabel': 'Repository',
                    'yAxisLabel': 'Active Findings'
                }
            },
            'metadata': {
                'count': len(labels),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id}
            }
        }


class MeanTimeToRemediate(BaseInsight):
    """Average time to remediate vulnerabilities by severity."""

    insight_id = 'mttr_by_severity'
    name = 'Mean Time to Remediate'
    description = 'Average remediation time by severity'
    category = 'security'
    visualization_type = 'chart'
    chart_type = 'bar'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate mean time to remediate by severity."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset - mitigated findings in GitHub-tracked products
        queryset = Finding.objects.filter(
            active=False,
            mitigated__isnull=False,
            test__engagement__product__github_url__isnull=False
        )

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(
                test__engagement__product__prod_type_id=product_type_id
            )

        # Calculate average days to remediate per severity
        from django.db.models import ExpressionWrapper, DurationField
        from django.db.models.functions import ExtractDay

        severities = ['Critical', 'High', 'Medium', 'Low', 'Info']
        labels = []
        values = []

        for severity in severities:
            avg_days = queryset.filter(severity=severity).annotate(
                days_to_mitigate=ExpressionWrapper(
                    F('mitigated') - F('date'),
                    output_field=DurationField()
                )
            ).aggregate(
                avg=Avg('days_to_mitigate')
            )

            if avg_days['avg']:
                labels.append(severity)
                values.append(avg_days['avg'].days)

        colors = ['#dc3545', '#fd7e14', '#ffc107', '#28a745', '#17a2b8'][:len(labels)]

        return {
            'title': 'Mean Time to Remediate by Severity',
            'data': {
                'labels': labels,
                'values': values,
                'colors': colors
            },
            'chart_config': {
                'type': 'bar',
                'options': {
                    'title': 'Average Days to Remediate',
                    'xAxisLabel': 'Severity',
                    'yAxisLabel': 'Days'
                }
            },
            'metadata': {
                'count': len(labels),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id}
            }
        }


class HighEPSSScoreFindings(BaseInsight):
    """Findings with high EPSS scores requiring prioritization."""

    insight_id = 'high_epss_findings'
    name = 'High EPSS Score Findings'
    description = 'Vulnerabilities with EPSS > 0.5 (high exploitation probability)'
    category = 'security'
    visualization_type = 'table'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate findings with high EPSS scores."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')
        epss_threshold = filters.get('epss_threshold', 0.5)

        # Base queryset
        queryset = Finding.objects.filter(
            active=True,
            epss_score__gte=epss_threshold,
            test__engagement__product__github_url__isnull=False
        )

        # Filter by product type if specified
        if product_type_id:
            queryset = queryset.filter(
                test__engagement__product__prod_type_id=product_type_id
            )

        # Get high EPSS findings
        findings = queryset.order_by('-epss_score')[:20].values(
            'id',
            'title',
            'severity',
            'epss_score',
            'cve',
            'test__engagement__product__name',
            'test__engagement__product__business_criticality'
        )

        data = [
            {
                'finding_id': f['id'],
                'title': f['title'][:50],  # Truncate
                'cve': f['cve'] or 'N/A',
                'severity': f['severity'],
                'epss_score': round(f['epss_score'], 3) if f['epss_score'] else 0,
                'repository': f['test__engagement__product__name'],
                'tier': f['test__engagement__product__business_criticality'] or 'Unknown'
            }
            for f in findings
        ]

        return {
            'title': f'High EPSS Score Findings (EPSS ≥ {epss_threshold})',
            'data': data,
            'metadata': {
                'count': len(data),
                'timestamp': timezone.now(),
                'filters_applied': {
                    'product_type_id': product_type_id,
                    'epss_threshold': epss_threshold
                }
            }
        }


class SecurityPostureByCriticality(BaseInsight):
    """Security posture breakdown by business criticality tier."""

    insight_id = 'security_by_tier'
    name = 'Security by Criticality Tier'
    description = 'Vulnerability distribution across business criticality tiers'
    category = 'security'
    visualization_type = 'chart'
    chart_type = 'bar'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Calculate security posture by business criticality."""
        filters = filters or {}
        product_type_id = filters.get('product_type_id')

        # Base queryset
        products_query = Product.objects.filter(github_url__isnull=False)

        # Filter by product type if specified
        if product_type_id:
            products_query = products_query.filter(prod_type_id=product_type_id)

        # Count findings by tier
        tiers = ['very_high', 'high', 'medium', 'low', 'very_low', 'none']
        tier_labels = {
            'very_high': 'Very High',
            'high': 'High',
            'medium': 'Medium',
            'low': 'Low',
            'very_low': 'Very Low',
            'none': 'Unknown'
        }

        labels = []
        values = []

        for tier in tiers:
            tier_products = products_query.filter(business_criticality=tier)

            vuln_count = Finding.objects.filter(
                active=True,
                test__engagement__product__in=tier_products
            ).count()

            if vuln_count > 0:
                labels.append(tier_labels[tier])
                values.append(vuln_count)

        colors = ['#dc3545', '#fd7e14', '#ffc107', '#28a745', '#17a2b8', '#6c757d'][:len(labels)]

        return {
            'title': 'Security Posture by Business Criticality',
            'data': {
                'labels': labels,
                'values': values,
                'colors': colors
            },
            'chart_config': {
                'type': 'bar',
                'options': {
                    'title': 'Active Findings by Tier',
                    'xAxisLabel': 'Business Criticality',
                    'yAxisLabel': 'Active Findings'
                }
            },
            'metadata': {
                'count': len(labels),
                'timestamp': timezone.now(),
                'filters_applied': {'product_type_id': product_type_id},
                'total_findings': sum(values)
            }
        }


class ActivityVulnerabilityCorrelation(BaseInsight):
    """Correlation between repository activity and vulnerability counts (placeholder)."""

    insight_id = 'activity_vuln_correlation'
    name = 'Activity-Vulnerability Correlation'
    description = 'Correlation between commit frequency and vulnerability discovery (requires activity collection)'
    category = 'security'
    visualization_type = 'chart'
    chart_type = 'scatter'

    def calculate(self, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculate correlation between activity and vulnerabilities.

        PLACEHOLDER: Requires commit_count field from activity collection task.
        Returns placeholder data until that task is completed.
        """
        return {
            'title': 'Activity-Vulnerability Correlation',
            'data': {
                'labels': [],
                'values': [],
                'colors': []
            },
            'chart_config': {
                'type': 'scatter',
                'options': {
                    'title': 'Commit Frequency vs Vulnerability Count (Coming Soon)',
                    'xAxisLabel': 'Commits (Last 30 Days)',
                    'yAxisLabel': 'Active Findings'
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


# Register all insights
InsightRegistry.register(VulnerabilityDistribution)
InsightRegistry.register(CriticalVulnTrend)
InsightRegistry.register(TopVulnerableRepositories)
InsightRegistry.register(MeanTimeToRemediate)
InsightRegistry.register(HighEPSSScoreFindings)
InsightRegistry.register(SecurityPostureByCriticality)
InsightRegistry.register(ActivityVulnerabilityCorrelation)
