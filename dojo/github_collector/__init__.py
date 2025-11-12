"""
GitHub Repository Collector Module

This module provides enterprise repository context enrichment by:
- Syncing repository metadata from GitHub API
- Detecting binary signals (deployment indicators, production readiness, etc.)
- Computing repository tier classifications
- Summarizing README content
- Parsing CODEOWNERS for ownership attribution

Integrates with existing DefectDojo GitHub infrastructure (dojo/github.py)
while adding repository-level intelligence.
"""

from .collector import GitHubRepositoryCollector
from .signal_detector import SignalDetector
from .tier_classifier import TierClassifier

__all__ = ['GitHubRepositoryCollector', 'SignalDetector', 'TierClassifier']
