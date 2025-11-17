"""
Management command for generating GitHub repository insights.

Usage:
    python manage.py generate_insights --list                          # List all available insights
    python manage.py generate_insights --insight vuln_distribution     # Generate specific insight
    python manage.py generate_insights --category security              # Generate all insights in category
    python manage.py generate_insights --all                            # Generate all insights
"""

import json
import logging

from django.core.management.base import BaseCommand

from dojo.github_collector.insights.registry import InsightRegistry, autodiscover

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate GitHub repository insights reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all available insights'
        )

        parser.add_argument(
            '--insight',
            type=str,
            help='Generate specific insight by ID (e.g., vuln_distribution)'
        )

        parser.add_argument(
            '--category',
            type=str,
            choices=['activity', 'health', 'security', 'ownership', 'technology'],
            help='Generate all insights in specified category'
        )

        parser.add_argument(
            '--all',
            action='store_true',
            help='Generate all insights'
        )

        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Time range filter in days (default: 30)'
        )

        parser.add_argument(
            '--product-type-id',
            type=int,
            help='Filter by product type ID'
        )

        parser.add_argument(
            '--output',
            type=str,
            choices=['json', 'table'],
            default='table',
            help='Output format (default: table)'
        )

    def handle(self, *args, **options):
        # Auto-discover all insights
        autodiscover()

        # Build filters
        filters = {}
        if options['days']:
            filters['days'] = options['days']
        if options['product_type_id']:
            filters['product_type_id'] = options['product_type_id']

        # List insights
        if options['list']:
            self.list_insights()
            return

        # Generate all insights
        if options['all']:
            self.generate_all_insights(filters, options['output'])
            return

        # Generate insights by category
        if options['category']:
            self.generate_category_insights(options['category'], filters, options['output'])
            return

        # Generate specific insight
        if options['insight']:
            self.generate_insight(options['insight'], filters, options['output'])
            return

        # No action specified
        self.stdout.write(self.style.ERROR('Error: Please specify --list, --insight, --category, or --all'))
        self.stdout.write('Use --help for more information')

    def list_insights(self):
        """List all available insights grouped by category."""
        insights = InsightRegistry.get_all_insights()

        # Group by category
        categories = {}
        for insight in insights:
            category = insight['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(insight)

        # Display
        self.stdout.write(self.style.SUCCESS('\nAvailable GitHub Repository Insights:'))
        self.stdout.write('=' * 80)

        for category in sorted(categories.keys()):
            self.stdout.write(self.style.HTTP_INFO(f'\n{category.upper()}:'))
            for insight in categories[category]:
                self.stdout.write(f"  - {insight['insight_id']:30s} {insight['name']}")
                self.stdout.write(f"    {insight['description']}")
                self.stdout.write(f"    Type: {insight['visualization_type']}, " +
                                f"Cache: {insight['cache_duration']}s\n")

        self.stdout.write(f'\nTotal: {len(insights)} insights across {len(categories)} categories')

    def generate_insight(self, insight_id, filters, output_format):
        """Generate a specific insight."""
        try:
            insight = InsightRegistry.get_insight(insight_id)
        except ValueError as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            return

        self.stdout.write(self.style.SUCCESS(f'\nGenerating insight: {insight.name}'))
        self.stdout.write(f'Insight ID: {insight_id}')
        self.stdout.write(f'Category: {insight.category}')
        self.stdout.write(f'Filters: {filters}\n')

        # Calculate insight data
        try:
            result = insight.calculate(filters)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error calculating insight: {str(e)}'))
            logger.exception(f'Failed to calculate insight {insight_id}')
            return

        # Output result
        if output_format == 'json':
            self.stdout.write(json.dumps(result, indent=2, default=str))
        else:
            self.display_table_result(result)

    def generate_category_insights(self, category, filters, output_format):
        """Generate all insights in a category."""
        insights = InsightRegistry.get_insights_by_category(category)

        if not insights:
            self.stdout.write(self.style.ERROR(f'No insights found in category: {category}'))
            return

        self.stdout.write(self.style.SUCCESS(f'\nGenerating {len(insights)} insights in category: {category}'))
        self.stdout.write(f'Filters: {filters}\n')

        for insight_meta in insights:
            self.generate_insight(insight_meta['insight_id'], filters, output_format)
            self.stdout.write('-' * 80 + '\n')

    def generate_all_insights(self, filters, output_format):
        """Generate all available insights."""
        insights = InsightRegistry.get_all_insights()

        self.stdout.write(self.style.SUCCESS(f'\nGenerating all {len(insights)} insights'))
        self.stdout.write(f'Filters: {filters}\n')

        for insight_meta in insights:
            self.generate_insight(insight_meta['insight_id'], filters, output_format)
            self.stdout.write('-' * 80 + '\n')

    def display_table_result(self, result):
        """Display insight result in table format."""
        self.stdout.write(self.style.HTTP_INFO(f"\n{result.get('title', 'Insight Result')}"))

        # Check for placeholder
        if result.get('metadata', {}).get('placeholder'):
            self.stdout.write(self.style.WARNING(f"  [PLACEHOLDER] {result['metadata']['message']}"))
            return

        # Display data
        data = result.get('data', [])

        if isinstance(data, dict):
            # Chart data
            self.stdout.write(f"\nChart Data:")
            self.stdout.write(f"  Labels: {data.get('labels', [])}")
            self.stdout.write(f"  Values: {data.get('values', [])}")

        elif isinstance(data, list) and len(data) > 0:
            # Table data
            if len(data) <= 20:
                self.stdout.write(f"\nData ({len(data)} rows):")
                for row in data:
                    self.stdout.write(f"  {row}")
            else:
                self.stdout.write(f"\nData ({len(data)} rows, showing first 10):")
                for row in data[:10]:
                    self.stdout.write(f"  {row}")
        else:
            self.stdout.write("  No data available")

        # Display metadata
        metadata = result.get('metadata', {})
        if metadata:
            self.stdout.write(f"\nMetadata:")
            self.stdout.write(f"  Count: {metadata.get('count', 0)}")
            if 'timestamp' in metadata:
                self.stdout.write(f"  Timestamp: {metadata['timestamp']}")
            if 'filters_applied' in metadata:
                self.stdout.write(f"  Filters: {metadata['filters_applied']}")
