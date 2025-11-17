"""
URL Configuration for GitHub Collector module.
"""

from django.urls import re_path

from dojo.github_collector.insights import views as insights_views

urlpatterns = [
    # GitHub Insights Dashboard
    re_path(
        r'^github/insights/dashboard$',
        insights_views.github_insights_dashboard,
        name='github_insights_dashboard'
    ),
]
