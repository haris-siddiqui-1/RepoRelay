"""
Auto-Triage Engine

Rule evaluation engine that applies triage decisions to findings based on
contextual signals like EPSS scores, repository tier, and business criticality.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from dojo.models import Finding, Product
from .rules import TRIAGE_RULES, TriageDecision

logger = logging.getLogger(__name__)


class AutoTriageEngine:
    """
    Evaluates triage rules and applies decisions to findings.

    Workflow:
    1. Load triage rules from rules.py
    2. Evaluate each rule against finding context
    3. Apply highest-priority matching rule
    4. Update Finding with auto_triage_decision and auto_triage_reason
    5. Track statistics

    Triage Decisions:
    - DISMISS: Low risk, not actionable (e.g., low EPSS in tier 4 repo)
    - ESCALATE: High risk, needs immediate attention (e.g., high EPSS in tier 1)
    - ACCEPT_RISK: Acknowledged but accepted (e.g., internal tool, known limitation)
    - PENDING: No rule matched, requires manual triage
    """

    def __init__(self, rules: Optional[List[Dict]] = None):
        """
        Initialize engine with triage rules.

        Args:
            rules: Optional list of rule dictionaries (defaults to TRIAGE_RULES)
        """
        self.rules = rules or TRIAGE_RULES
        self.stats = {
            'total_findings': 0,
            'dismissed': 0,
            'escalated': 0,
            'accepted_risk': 0,
            'pending': 0,
            'errors': 0
        }

    def triage_all_findings(self, active_only: bool = True) -> Dict:
        """
        Triage all findings in the system.

        Args:
            active_only: Only triage active findings (default True)

        Returns:
            Dictionary with triage statistics
        """
        logger.info(f"Starting auto-triage for all findings (active_only={active_only})")

        findings = self._get_findings_for_triage(active_only=active_only)
        self.stats['total_findings'] = findings.count()

        logger.info(f"Found {self.stats['total_findings']} findings to triage")

        self._triage_findings_queryset(findings)

        logger.info(f"Auto-triage completed: {self.stats}")
        return self.stats

    def triage_findings_by_ids(self, finding_ids: List[int]) -> Dict:
        """
        Triage specific findings by ID.

        Args:
            finding_ids: List of Finding IDs

        Returns:
            Dictionary with triage statistics
        """
        logger.info(f"Starting auto-triage for {len(finding_ids)} specific findings")

        findings = Finding.objects.filter(id__in=finding_ids).select_related(
            'test__engagement__product'
        )
        self.stats['total_findings'] = findings.count()

        self._triage_findings_queryset(findings)

        logger.info(f"Auto-triage completed for specific findings: {self.stats}")
        return self.stats

    def triage_findings_by_product(self, product_id: int) -> Dict:
        """
        Triage all findings for a specific product.

        Args:
            product_id: Product ID

        Returns:
            Dictionary with triage statistics
        """
        logger.info(f"Starting auto-triage for product {product_id}")

        findings = Finding.objects.filter(
            test__engagement__product_id=product_id,
            active=True
        ).select_related('test__engagement__product')
        self.stats['total_findings'] = findings.count()

        self._triage_findings_queryset(findings)

        logger.info(f"Auto-triage completed for product {product_id}: {self.stats}")
        return self.stats

    def triage_single_finding(self, finding: Finding) -> Dict:
        """
        Triage a single finding and return the decision.

        Args:
            finding: Finding instance

        Returns:
            Dictionary with decision details:
            {
                'decision': 'DISMISS'|'ESCALATE'|'ACCEPT_RISK'|'PENDING',
                'reason': 'Rule explanation',
                'rule_name': 'rule_identifier',
                'confidence': 0-100
            }
        """
        # Ensure product relationship is loaded
        if not hasattr(finding, 'test') or not hasattr(finding.test, 'engagement'):
            finding = Finding.objects.select_related('test__engagement__product').get(id=finding.id)

        # Evaluate rules
        for rule in self.rules:
            try:
                if rule['condition'](finding):
                    return {
                        'decision': rule['decision'],
                        'reason': rule['reason'],
                        'rule_name': rule['name'],
                        'confidence': rule.get('confidence', 80)
                    }
            except Exception as e:
                logger.warning(f"Error evaluating rule {rule.get('name', 'unknown')}: {e}")
                continue

        # No rule matched
        return {
            'decision': TriageDecision.PENDING,
            'reason': 'No auto-triage rule matched - requires manual review',
            'rule_name': 'default',
            'confidence': 0
        }

    def _get_findings_for_triage(self, active_only: bool = True) -> 'QuerySet[Finding]':
        """
        Get findings that need triage evaluation.

        Args:
            active_only: Only return active findings

        Returns:
            QuerySet of findings
        """
        queryset = Finding.objects.all()

        if active_only:
            queryset = queryset.filter(active=True)

        # Select related to avoid N+1 queries
        queryset = queryset.select_related('test__engagement__product')

        return queryset

    def _triage_findings_queryset(self, findings):
        """
        Apply triage rules to a queryset of findings.

        Args:
            findings: QuerySet of Finding objects
        """
        for finding in findings:
            try:
                self._apply_triage_to_finding(finding)
            except Exception as e:
                logger.error(f"Error triaging finding {finding.id}: {e}", exc_info=True)
                self.stats['errors'] += 1

    def _apply_triage_to_finding(self, finding: Finding):
        """
        Evaluate rules and apply triage decision to a single finding.

        Args:
            finding: Finding instance
        """
        # Get triage decision
        decision_data = self.triage_single_finding(finding)

        # Skip if decision unchanged
        if finding.auto_triage_decision == decision_data['decision']:
            self.stats['pending'] += 1
            return

        # Apply decision
        with transaction.atomic():
            finding.auto_triage_decision = decision_data['decision']
            finding.auto_triage_reason = f"{decision_data['reason']} (Rule: {decision_data['rule_name']}, Confidence: {decision_data['confidence']}%)"
            finding.auto_triaged_at = timezone.now()
            finding.save(update_fields=['auto_triage_decision', 'auto_triage_reason', 'auto_triaged_at'])

        # Update stats
        if decision_data['decision'] == TriageDecision.DISMISS:
            self.stats['dismissed'] += 1
        elif decision_data['decision'] == TriageDecision.ESCALATE:
            self.stats['escalated'] += 1
        elif decision_data['decision'] == TriageDecision.ACCEPT_RISK:
            self.stats['accepted_risk'] += 1
        else:
            self.stats['pending'] += 1

        logger.debug(
            f"Triaged finding {finding.id} ({finding.cve or finding.title[:50]}): "
            f"{decision_data['decision']} - {decision_data['reason']}"
        )

    def reset_triage_decisions(self, finding_ids: Optional[List[int]] = None):
        """
        Reset auto-triage decisions back to PENDING.

        Useful when rules have been updated and need to be re-evaluated.

        Args:
            finding_ids: Optional list of specific finding IDs to reset
        """
        logger.info(f"Resetting auto-triage decisions (finding_ids={finding_ids})")

        queryset = Finding.objects.all()

        if finding_ids:
            queryset = queryset.filter(id__in=finding_ids)

        count = queryset.update(
            auto_triage_decision=TriageDecision.PENDING,
            auto_triage_reason='',
            auto_triaged_at=None
        )

        logger.info(f"Reset {count} findings to PENDING")
        return {'reset_count': count}

    def get_triage_statistics(self) -> Dict:
        """
        Get statistics about auto-triage decisions across all findings.

        Returns:
            Dictionary with decision breakdown
        """
        from django.db.models import Count

        stats = Finding.objects.filter(active=True).values('auto_triage_decision').annotate(
            count=Count('id')
        ).order_by('auto_triage_decision')

        result = {
            'total': Finding.objects.filter(active=True).count(),
            'by_decision': {}
        }

        for stat in stats:
            decision = stat['auto_triage_decision']
            count = stat['count']
            result['by_decision'][decision] = count

        # Calculate percentages
        if result['total'] > 0:
            for decision, count in result['by_decision'].items():
                pct = (count / result['total']) * 100
                result['by_decision'][decision] = {
                    'count': count,
                    'percentage': round(pct, 2)
                }

        return result

    def validate_rules(self) -> List[Dict]:
        """
        Validate that all triage rules are correctly formatted.

        Returns:
            List of validation errors (empty if all valid)
        """
        errors = []

        required_keys = ['name', 'condition', 'decision', 'reason']
        valid_decisions = [TriageDecision.DISMISS, TriageDecision.ESCALATE, TriageDecision.ACCEPT_RISK]

        for idx, rule in enumerate(self.rules):
            # Check required keys
            for key in required_keys:
                if key not in rule:
                    errors.append(f"Rule {idx}: Missing required key '{key}'")

            # Check decision validity
            if 'decision' in rule and rule['decision'] not in valid_decisions:
                errors.append(f"Rule {idx} ({rule.get('name', 'unknown')}): Invalid decision '{rule['decision']}'")

            # Check condition is callable
            if 'condition' in rule and not callable(rule['condition']):
                errors.append(f"Rule {idx} ({rule.get('name', 'unknown')}): 'condition' must be callable")

        return errors
