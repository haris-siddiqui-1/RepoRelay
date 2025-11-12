"""
EPSS Score Updater

Bulk updates Finding records with EPSS scores from FIRST.org API.
Handles batching, error recovery, and auto-triage triggering.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone

from dojo.models import Finding
from .client import EPSSClient

logger = logging.getLogger(__name__)


class EPSSUpdater:
    """
    Updates Finding records with EPSS scores from FIRST.org API.

    Workflow:
    1. Fetch active findings with CVE identifiers
    2. Batch CVEs and fetch scores from EPSS API
    3. Update Finding records with epss_score and epss_percentile
    4. Track statistics and handle errors gracefully
    5. Optionally trigger auto-triage for significantly changed scores
    """

    BATCH_SIZE = 100  # Match EPSSClient.MAX_CVES_PER_REQUEST
    SIGNIFICANT_CHANGE_THRESHOLD = 0.2  # 20% change triggers re-triage

    def __init__(self, epss_client: Optional[EPSSClient] = None):
        """
        Initialize updater.

        Args:
            epss_client: Optional EPSSClient instance (creates default if not provided)
        """
        self.epss_client = epss_client or EPSSClient()
        self.stats = {
            'total_findings': 0,
            'findings_with_cve': 0,
            'unique_cves': 0,
            'scores_fetched': 0,
            'findings_updated': 0,
            'findings_unchanged': 0,
            'findings_new_score': 0,
            'significant_changes': 0,
            'errors': 0
        }

    def update_all_findings(self, active_only: bool = True, trigger_triage: bool = False) -> Dict:
        """
        Update EPSS scores for all findings with CVE identifiers.

        Args:
            active_only: Only update active findings (default True)
            trigger_triage: Trigger auto-triage for significantly changed scores

        Returns:
            Dictionary with update statistics
        """
        logger.info(f"Starting EPSS score update (active_only={active_only})")

        # Get findings with CVE identifiers
        findings = self._get_findings_with_cves(active_only)
        self.stats['total_findings'] = findings.count()

        if self.stats['total_findings'] == 0:
            logger.warning("No findings with CVE identifiers found")
            return self.stats

        logger.info(f"Found {self.stats['total_findings']} findings with CVE identifiers")

        # Extract unique CVEs
        cves = self._extract_cves_from_findings(findings)
        self.stats['findings_with_cve'] = len(cves)
        self.stats['unique_cves'] = len(set(cves.values()))

        logger.info(f"Extracted {self.stats['unique_cves']} unique CVEs")

        # Fetch EPSS scores
        scores = self._fetch_epss_scores(list(set(cves.values())))
        self.stats['scores_fetched'] = len(scores)

        logger.info(f"Fetched {self.stats['scores_fetched']} EPSS scores")

        # Update findings
        self._update_findings_with_scores(findings, cves, scores, trigger_triage)

        logger.info(f"EPSS update completed: {self.stats}")
        return self.stats

    def update_findings_by_ids(self, finding_ids: List[int], trigger_triage: bool = False) -> Dict:
        """
        Update EPSS scores for specific findings by ID.

        Args:
            finding_ids: List of Finding IDs to update
            trigger_triage: Trigger auto-triage for significantly changed scores

        Returns:
            Dictionary with update statistics
        """
        logger.info(f"Updating EPSS scores for {len(finding_ids)} specific findings")

        findings = Finding.objects.filter(id__in=finding_ids)
        self.stats['total_findings'] = findings.count()

        # Extract CVEs
        cves = self._extract_cves_from_findings(findings)
        self.stats['findings_with_cve'] = len(cves)
        self.stats['unique_cves'] = len(set(cves.values()))

        # Fetch scores
        scores = self._fetch_epss_scores(list(set(cves.values())))
        self.stats['scores_fetched'] = len(scores)

        # Update findings
        self._update_findings_with_scores(findings, cves, scores, trigger_triage)

        logger.info(f"EPSS update completed for specific findings: {self.stats}")
        return self.stats

    def update_findings_by_product(self, product_id: int, trigger_triage: bool = False) -> Dict:
        """
        Update EPSS scores for all findings in a product.

        Args:
            product_id: Product ID to update
            trigger_triage: Trigger auto-triage for significantly changed scores

        Returns:
            Dictionary with update statistics
        """
        logger.info(f"Updating EPSS scores for product {product_id}")

        findings = Finding.objects.filter(
            test__engagement__product_id=product_id,
            active=True
        )
        self.stats['total_findings'] = findings.count()

        # Extract CVEs
        cves = self._extract_cves_from_findings(findings)
        self.stats['findings_with_cve'] = len(cves)
        self.stats['unique_cves'] = len(set(cves.values()))

        # Fetch scores
        scores = self._fetch_epss_scores(list(set(cves.values())))
        self.stats['scores_fetched'] = len(scores)

        # Update findings
        self._update_findings_with_scores(findings, cves, scores, trigger_triage)

        logger.info(f"EPSS update completed for product {product_id}: {self.stats}")
        return self.stats

    def _get_findings_with_cves(self, active_only: bool) -> 'QuerySet[Finding]':
        """
        Get findings that have CVE identifiers.

        Args:
            active_only: Only return active findings

        Returns:
            QuerySet of findings with non-empty cve field
        """
        queryset = Finding.objects.exclude(Q(cve__isnull=True) | Q(cve=''))

        if active_only:
            queryset = queryset.filter(active=True)

        return queryset.select_related('test__engagement__product')

    def _extract_cves_from_findings(self, findings) -> Dict[int, str]:
        """
        Extract CVE identifiers from findings.

        Args:
            findings: QuerySet of Finding objects

        Returns:
            Dictionary mapping finding_id to CVE string
        """
        cves = {}

        for finding in findings:
            if finding.cve:
                # Handle multiple CVEs (comma or space separated)
                # Take the first CVE if multiple present
                cve = finding.cve.strip().split(',')[0].split()[0].upper()
                if cve.startswith('CVE-'):
                    cves[finding.id] = cve

        return cves

    def _fetch_epss_scores(self, cves: List[str]) -> Dict[str, Dict]:
        """
        Fetch EPSS scores for list of CVEs in batches.

        Args:
            cves: List of CVE identifiers

        Returns:
            Dictionary mapping CVE to score data
        """
        all_scores = {}

        # Process in batches
        for i in range(0, len(cves), self.BATCH_SIZE):
            batch = cves[i:i + self.BATCH_SIZE]

            try:
                batch_scores = self.epss_client.get_scores(batch)
                all_scores.update(batch_scores)
            except Exception as e:
                logger.error(f"Error fetching EPSS scores for batch {i}-{i+len(batch)}: {e}")
                self.stats['errors'] += 1

        return all_scores

    def _update_findings_with_scores(
        self,
        findings,
        cves: Dict[int, str],
        scores: Dict[str, Dict],
        trigger_triage: bool
    ):
        """
        Update findings with fetched EPSS scores.

        Args:
            findings: QuerySet of findings to update
            cves: Dictionary mapping finding_id to CVE
            scores: Dictionary mapping CVE to score data
            trigger_triage: Whether to trigger auto-triage for significant changes
        """
        findings_to_triage = []

        for finding in findings:
            finding_id = finding.id
            cve = cves.get(finding_id)

            if not cve:
                continue

            score_data = scores.get(cve)

            if not score_data:
                # No score available for this CVE
                continue

            # Get new score values
            new_epss = score_data['epss']
            new_percentile = score_data['percentile']

            # Check for significant change
            old_epss = finding.epss_score or 0.0
            is_significant_change = abs(new_epss - old_epss) >= self.SIGNIFICANT_CHANGE_THRESHOLD

            # Track if this is a new score or update
            if finding.epss_score is None:
                self.stats['findings_new_score'] += 1
            elif finding.epss_score == new_epss and finding.epss_percentile == new_percentile:
                self.stats['findings_unchanged'] += 1
                continue  # Skip update if unchanged
            else:
                self.stats['findings_updated'] += 1

            if is_significant_change:
                self.stats['significant_changes'] += 1
                if trigger_triage:
                    findings_to_triage.append(finding_id)

            # Update finding
            try:
                with transaction.atomic():
                    finding.epss_score = new_epss
                    finding.epss_percentile = new_percentile
                    finding.save(update_fields=['epss_score', 'epss_percentile'])
            except Exception as e:
                logger.error(f"Error updating finding {finding_id}: {e}")
                self.stats['errors'] += 1

        # Trigger auto-triage if requested
        if trigger_triage and findings_to_triage:
            self._trigger_auto_triage(findings_to_triage)

    def _trigger_auto_triage(self, finding_ids: List[int]):
        """
        Trigger auto-triage for findings with significant EPSS changes.

        Args:
            finding_ids: List of finding IDs to re-triage
        """
        logger.info(f"Triggering auto-triage for {len(finding_ids)} findings with significant EPSS changes")

        try:
            # Import here to avoid circular dependency
            from dojo.auto_triage.engine import AutoTriageEngine

            engine = AutoTriageEngine()
            triage_stats = engine.triage_findings_by_ids(finding_ids)

            logger.info(f"Auto-triage completed: {triage_stats}")
        except ImportError:
            logger.warning("Auto-triage engine not available (module not yet implemented)")
        except Exception as e:
            logger.error(f"Error triggering auto-triage: {e}", exc_info=True)

    def get_epss_coverage_stats(self) -> Dict:
        """
        Get statistics about EPSS score coverage across findings.

        Returns:
            Dictionary with coverage statistics
        """
        total_findings = Finding.objects.filter(active=True).count()
        findings_with_cve = Finding.objects.filter(active=True).exclude(Q(cve__isnull=True) | Q(cve='')).count()
        findings_with_epss = Finding.objects.filter(active=True, epss_score__isnull=False).count()

        coverage_pct = (findings_with_epss / findings_with_cve * 100) if findings_with_cve > 0 else 0

        return {
            'total_active_findings': total_findings,
            'findings_with_cve': findings_with_cve,
            'findings_with_epss': findings_with_epss,
            'coverage_percentage': round(coverage_pct, 2),
            'missing_epss_scores': findings_with_cve - findings_with_epss
        }

    def get_high_risk_findings(self, epss_threshold: float = 0.5) -> 'QuerySet[Finding]':
        """
        Get active findings with high EPSS scores.

        Args:
            epss_threshold: Minimum EPSS score (default 0.5 = 50% exploitation probability)

        Returns:
            QuerySet of high-risk findings
        """
        return Finding.objects.filter(
            active=True,
            epss_score__gte=epss_threshold
        ).select_related('test__engagement__product').order_by('-epss_score')
