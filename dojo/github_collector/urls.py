"""
URL Configuration for GitHub Collector module.
"""

from django.urls import re_path

from dojo.github_collector import views as github_collector_views
from dojo.github_collector.insights import views as insights_views

urlpatterns = [
    # GitHub Sync Configuration
    re_path(
        r'^github/sync/configuration$',
        github_collector_views.github_sync_configuration,
        name='github_sync_configuration'
    ),

    # GitHub Test Connection (AJAX endpoint)
    re_path(
        r'^github/sync/test-connection$',
        github_collector_views.github_test_connection,
        name='github_test_connection'
    ),

    # GitHub Insights Dashboard
    re_path(
        r'^github/insights/dashboard$',
        insights_views.github_insights_dashboard,
        name='github_insights_dashboard'
    ),
]
