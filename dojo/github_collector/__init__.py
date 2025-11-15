"""
GitHub Repository Collector Module

This module provides enterprise repository context enrichment and security alerts integration by:
- Syncing repository metadata from GitHub API (GraphQL v4 + REST v3)
- Detecting binary signals (deployment indicators, production readiness, etc.)
- Computing repository tier classifications
- Summarizing README content
- Parsing CODEOWNERS for ownership attribution
- Fetching GitHub security alerts (Dependabot, CodeQL, Secret Scanning)
- Converting alerts to DefectDojo Findings with deduplication

GraphQL API Integration (January 2025):
- Uses GitHub GraphQL API v4 for bulk organization syncs
- 94% reduction in API calls (18 REST calls → 1 GraphQL query per repo)
- Sub-5-minute daily incremental syncs (50-100 changed repos)
- Automatic REST fallback for reliability
- See README_GRAPHQL.md for detailed documentation

GitHub Alerts Integration (January 2025):
- Fetches Dependabot alerts via GraphQL (vulnerabilityAlerts query)
- Fetches CodeQL/Secret Scanning alerts via REST API
- Converts alerts to DefectDojo Findings with proper deduplication
- Syncs alert state changes bidirectionally (open/dismissed/fixed)
- See README_ALERTS.md for detailed documentation

Integrates with existing DefectDojo GitHub infrastructure (dojo/github.py)
while adding repository-level intelligence and centralized vulnerability management.
"""

from .alerts_collector import GitHubAlertsCollector
from .collector import GitHubRepositoryCollector
from .findings_converter import GitHubFindingsConverter
from .signal_detector import SignalDetector
from .tier_classifier import TierClassifier

__all__ = [
    'GitHubRepositoryCollector',
    'GitHubAlertsCollector',
    'GitHubFindingsConverter',
    'SignalDetector',
    'TierClassifier',
]
