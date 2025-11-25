"""
Insight registry for auto-discovery and management of insights.
"""

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


def autodiscover():
    """
    Auto-discover and register all insights.

    Import all insight modules to trigger registration.
    """
    try:
        from dojo.github_collector.insights import activity
        from dojo.github_collector.insights import health
        from dojo.github_collector.insights import security
        from dojo.github_collector.insights import ownership
        from dojo.github_collector.insights import technology
        from dojo.github_collector.insights import consumption
    except ImportError:
        # Insight modules not yet created, that's okay
        pass
