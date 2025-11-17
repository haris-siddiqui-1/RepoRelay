"""
GitHub Repository Insights Module.

Provides a pluggable insight system for analyzing repository data and generating
management dashboards for enterprise GitHub organizations.
"""

from dojo.github_collector.insights.registry import InsightRegistry

__all__ = ['InsightRegistry']
