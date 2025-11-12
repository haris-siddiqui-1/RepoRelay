"""
Repository Tier Classification

Maps binary signals to business criticality tiers (1-4) which correspond
to DefectDojo's business_criticality field values.

Tier Mapping:
- Tier 1 (Critical) → "very high"
- Tier 2 (High) → "high"
- Tier 3 (Medium) → "medium"
- Tier 4 (Low) → "low"
- Archived → "none"
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class TierClassifier:
    """
    Classifies repositories into tiers based on binary signals.

    Uses signal combinations to infer production criticality:
    - Tier 1: High-confidence production with monitoring and active maintenance
    - Tier 2: Likely production with good practices
    - Tier 3: Active development or staging
    - Tier 4: Everything else
    """

    # Business criticality values matching DefectDojo Product model
    TIER_MAPPING = {
        1: "very high",
        2: "high",
        3: "medium",
        4: "low",
        "archived": "none"
    }

    def __init__(self):
        self.tier = 4  # Default to lowest tier
        self.confidence_score = 0
        self.reasons = []

    def classify(self, signals: Dict[str, bool], days_since_last_commit: int = None) -> Dict:
        """
        Classify repository tier based on binary signals.

        Args:
            signals: Dictionary of binary signal names to boolean values
            days_since_last_commit: Days since last commit (for archival check)

        Returns:
            Dictionary containing:
            - tier: Integer 1-4 or "archived"
            - business_criticality: Mapped string value for DefectDojo
            - confidence_score: Integer 0-100
            - reasons: List of strings explaining classification
        """
        self.reasons = []

        # Check for archival first
        if days_since_last_commit and days_since_last_commit > 180:
            logger.info(f"Repository classified as archived ({days_since_last_commit} days since last commit)")
            return {
                'tier': 'archived',
                'business_criticality': self.TIER_MAPPING['archived'],
                'confidence_score': 100,
                'reasons': [f'No commits in {days_since_last_commit} days']
            }

        # Tier 1: High confidence production
        if self._is_tier_1(signals):
            self.tier = 1
            self.confidence_score = self._calculate_confidence(signals, tier=1)
            return self._build_result()

        # Tier 2: Likely production
        if self._is_tier_2(signals):
            self.tier = 2
            self.confidence_score = self._calculate_confidence(signals, tier=2)
            return self._build_result()

        # Tier 3: Active development
        if self._is_tier_3(signals):
            self.tier = 3
            self.confidence_score = self._calculate_confidence(signals, tier=3)
            return self._build_result()

        # Tier 4: Default
        self.tier = 4
        self.confidence_score = self._calculate_confidence(signals, tier=4)
        self.reasons.append("Does not meet criteria for higher tiers")

        return self._build_result()

    def _is_tier_1(self, signals: Dict[str, bool]) -> bool:
        """
        Tier 1 (Critical): High-confidence production system.

        Criteria:
        - Containerized (Docker OR K8s)
        - Has environments configured
        - Has monitoring
        - Recent activity
        """
        has_containers = signals.get('has_dockerfile', False) or signals.get('has_kubernetes_config', False)
        has_environments = signals.get('has_environments', False)
        has_monitoring = signals.get('has_monitoring_config', False)
        is_active = signals.get('recent_commits_30d', False)

        if has_containers and has_environments and has_monitoring and is_active:
            self.reasons.append("Containerized production system with monitoring and active maintenance")
            return True

        # Alternative: K8s + releases + branch protection + monitoring
        has_k8s = signals.get('has_kubernetes_config', False)
        has_releases = signals.get('has_releases', False)
        has_protection = signals.get('has_branch_protection', False)

        if has_k8s and has_releases and has_protection and has_monitoring:
            self.reasons.append("Kubernetes-based production system with release management")
            return True

        return False

    def _is_tier_2(self, signals: Dict[str, bool]) -> bool:
        """
        Tier 2 (High): Likely production or critical staging.

        Criteria:
        - Has CI/CD
        - Has releases
        - Has branch protection
        - Multiple contributors
        """
        has_cicd = signals.get('has_ci_cd', False)
        has_releases = signals.get('has_releases', False)
        has_protection = signals.get('has_branch_protection', False)
        multiple_contributors = signals.get('multiple_contributors', False)

        if has_cicd and has_releases and has_protection and multiple_contributors:
            self.reasons.append("Well-maintained codebase with release process and team collaboration")
            return True

        # Alternative: Production indicators without full tier 1
        has_containers = signals.get('has_dockerfile', False) or signals.get('has_kubernetes_config', False)
        has_monitoring = signals.get('has_monitoring_config', False)
        is_active = signals.get('recent_commits_30d', False)

        if has_containers and (has_monitoring or has_cicd) and is_active:
            self.reasons.append("Containerized system with production indicators")
            return True

        return False

    def _is_tier_3(self, signals: Dict[str, bool]) -> bool:
        """
        Tier 3 (Medium): Active development or staging.

        Criteria:
        - Has tests
        - Recent commits
        - Has documentation
        """
        has_tests = signals.get('has_tests', False)
        is_active = signals.get('recent_commits_30d', False)
        has_docs = signals.get('has_documentation', False)

        if has_tests and is_active and has_docs:
            self.reasons.append("Active development with testing and documentation")
            return True

        # Alternative: Recent activity with CI/CD
        has_cicd = signals.get('has_ci_cd', False)
        if has_cicd and is_active:
            self.reasons.append("Active development with automated testing")
            return True

        # Alternative: Recent activity with multiple contributors
        multiple_contributors = signals.get('multiple_contributors', False)
        if is_active and multiple_contributors:
            self.reasons.append("Actively maintained by team")
            return True

        return False

    def _calculate_confidence(self, signals: Dict[str, bool], tier: int) -> int:
        """
        Calculate confidence score (0-100) for tier classification.

        Higher score = more signals support the classification.

        Args:
            signals: Binary signals dictionary
            tier: Assigned tier (1-4)

        Returns:
            Confidence score 0-100
        """
        # Define signal weights by category
        production_signals = [
            'has_dockerfile', 'has_kubernetes_config', 'has_environments',
            'has_releases', 'has_monitoring_config', 'has_branch_protection'
        ]

        development_signals = [
            'has_ci_cd', 'has_tests', 'recent_commits_30d', 'active_prs_30d',
            'multiple_contributors', 'consistent_commit_pattern'
        ]

        security_signals = [
            'has_security_scanning', 'has_secret_scanning',
            'has_dependency_scanning', 'has_sast_config'
        ]

        organization_signals = [
            'has_documentation', 'has_api_specs', 'has_codeowners',
            'has_security_md'
        ]

        # Count signals in each category
        prod_count = sum(signals.get(s, False) for s in production_signals)
        dev_count = sum(signals.get(s, False) for s in development_signals)
        sec_count = sum(signals.get(s, False) for s in security_signals)
        org_count = sum(signals.get(s, False) for s in organization_signals)

        # Weight by tier
        if tier == 1:
            # Tier 1: Production signals weighted most
            score = (prod_count * 15) + (dev_count * 5) + (sec_count * 5) + (org_count * 3)
        elif tier == 2:
            # Tier 2: Production and development balanced
            score = (prod_count * 10) + (dev_count * 10) + (sec_count * 5) + (org_count * 3)
        elif tier == 3:
            # Tier 3: Development signals weighted most
            score = (prod_count * 5) + (dev_count * 12) + (sec_count * 5) + (org_count * 5)
        else:  # tier == 4
            # Tier 4: Organization signals matter more
            score = (prod_count * 3) + (dev_count * 5) + (sec_count * 3) + (org_count * 10)

        # Cap at 100
        return min(score, 100)

    def _build_result(self) -> Dict:
        """Build classification result dictionary."""
        return {
            'tier': self.tier,
            'business_criticality': self.TIER_MAPPING[self.tier],
            'confidence_score': self.confidence_score,
            'reasons': self.reasons
        }

    @staticmethod
    def explain_tier(tier: int) -> str:
        """
        Get human-readable explanation of tier level.

        Args:
            tier: Tier number (1-4) or "archived"

        Returns:
            Explanation string
        """
        explanations = {
            1: "Critical Production: Containerized, monitored, actively maintained system in production",
            2: "High Priority: Well-maintained codebase with release process and team collaboration",
            3: "Medium Priority: Active development with testing and documentation",
            4: "Low Priority: Limited production indicators or development activity",
            "archived": "Archived: No recent activity, repository marked for archival"
        }
        return explanations.get(tier, "Unknown tier")
