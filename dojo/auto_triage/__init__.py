"""
Auto-Triage System for DefectDojo

Automatically evaluates findings based on context signals (EPSS scores,
repository tier, business criticality) and applies triage decisions.

Example:
    from dojo.auto_triage import AutoTriageEngine

    engine = AutoTriageEngine()
    stats = engine.triage_all_findings()
"""

from .engine import AutoTriageEngine

__all__ = ['AutoTriageEngine']
