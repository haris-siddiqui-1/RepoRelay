"""
EPSS (Exploit Prediction Scoring System) Service

Provides integration with FIRST.org EPSS API to fetch and update
exploit prediction scores for CVE-based findings.

The EPSS score represents the probability that a vulnerability will be
exploited in the next 30 days, helping prioritize remediation efforts.
"""

from .client import EPSSClient
from .updater import EPSSUpdater

__all__ = ['EPSSClient', 'EPSSUpdater']
