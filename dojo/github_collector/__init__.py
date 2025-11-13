"""
GitHub Repository Collector Module

This module provides enterprise repository context enrichment by:
- Syncing repository metadata from GitHub API (GraphQL v4 + REST v3)
- Detecting binary signals (deployment indicators, production readiness, etc.)
- Computing repository tier classifications
- Summarizing README content
- Parsing CODEOWNERS for ownership attribution

GraphQL API Integration (January 2025):
- Uses GitHub GraphQL API v4 for bulk organization syncs
- 94% reduction in API calls (18 REST calls → 1 GraphQL query per repo)
- Sub-5-minute daily incremental syncs (50-100 changed repos)
- Automatic REST fallback for reliability
- See README_GRAPHQL.md for detailed documentation

Integrates with existing DefectDojo GitHub infrastructure (dojo/github.py)
while adding repository-level intelligence.
"""

from .collector import GitHubRepositoryCollector
from .signal_detector import SignalDetector
from .tier_classifier import TierClassifier

__all__ = ['GitHubRepositoryCollector', 'SignalDetector', 'TierClassifier']
