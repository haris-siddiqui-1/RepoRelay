"""
Priority Scorer - Phase 1 of Vulnerability Prioritization Strategy

Calculates priority scores for findings based on:
- Repository/Product tier (weight multiplier)
- Finding severity (base score)
- Risk modifiers (KEV, EPSS, SLA breach, etc.)

Formula: PriorityScore = (TierWeight × SeverityScore) + Modifiers
"""
import logging
from typing import TYPE_CHECKING, Optional

from django.utils import timezone

if TYPE_CHECKING:
    from dojo.models import Finding, Repository

logger = logging.getLogger(__name__)


class PriorityScorer:
    """Calculate priority scores for findings based on tier, severity, and modifiers."""

    # Tier weights - Repository tier takes precedence over Product business_criticality
    TIER_WEIGHTS = {
        # Repository tiers
        "tier1": 5.0,
        "tier2": 3.5,
        "tier3": 2.0,
        "tier4": 1.0,
        "archived": 0.2,
        # Product business_criticality mappings
        "very high": 5.0,
        "high": 3.5,
        "medium": 2.0,
        "low": 1.0,
        "very low": 0.5,
        "none": 0.2,
    }

    # Severity base scores
    SEVERITY_SCORES = {
        "Critical": 100,
        "High": 75,
        "Medium": 50,
        "Low": 25,
        "Info": 10,
    }

    # Priority bucket thresholds (score, bucket)
    PRIORITY_BUCKETS = [
        (500, "P0"),   # >= 500: Critical
        (300, "P1"),   # 300-499: High
        (150, "P2"),   # 150-299: Medium
        (50, "P3"),    # 50-149: Low
        (0, "P4"),     # < 50: Minimal
    ]

    # Modifier values
    MODIFIER_KEV = 150              # Known Exploited Vulnerability
    MODIFIER_RANSOMWARE = 100       # Used in ransomware campaigns
    MODIFIER_EPSS_HIGH = 75         # EPSS >= 0.7
    MODIFIER_EPSS_MEDIUM = 40       # EPSS >= 0.3
    MODIFIER_SLA_BREACH = 50        # SLA expired
    MODIFIER_FIX_AVAILABLE = 30     # Fix available (positive)
    MODIFIER_HAS_PROD_SIGNALS = 25  # has_environments or has_releases
    MODIFIER_HAS_WEBHOOKS = 15      # active_webhooks_count > 0

    MODIFIER_EPSS_VERY_LOW = -50    # EPSS < 0.02
    MODIFIER_EPSS_LOW = -25         # EPSS < 0.1
    MODIFIER_NO_FIX = -20           # Fix explicitly not available
    MODIFIER_DORMANT_REPO = -40     # > 180 days since last commit
    MODIFIER_NO_PROD_SIGNALS = -30  # No environments/releases

    def calculate(self, finding: "Finding", repository: Optional["Repository"] = None) -> int:
        """
        Calculate priority score for a finding.

        Args:
            finding: Finding instance (must have test.engagement.product prefetched for efficiency)
            repository: Optional Repository instance (if finding is from GitHub alert)

        Returns:
            Integer priority score (0-1500+ range possible)
        """
        # Get effective tier weight
        tier_weight = self._get_effective_tier_weight(finding, repository)

        # Get severity base score
        severity_score = self.SEVERITY_SCORES.get(finding.severity, 25)  # Default to Low if unknown

        # Calculate base score
        base_score = tier_weight * severity_score

        # Apply modifiers
        modifiers = self._calculate_modifiers(finding, repository)

        # Final score (floor at 0)
        final_score = max(0, int(base_score + modifiers))

        logger.debug(
            "Priority score for finding %s: tier_weight=%.1f, severity=%s (%d), "
            "modifiers=%d, final=%d",
            finding.id, tier_weight, finding.severity, severity_score, modifiers, final_score
        )

        return final_score

    def get_bucket(self, score: int) -> str:
        """
        Map priority score to bucket (P0-P4).

        Args:
            score: Integer priority score

        Returns:
            Priority bucket string (P0, P1, P2, P3, or P4)
        """
        for threshold, bucket in self.PRIORITY_BUCKETS:
            if score >= threshold:
                return bucket
        return "P4"  # Fallback

    def calculate_and_get_bucket(self, finding: "Finding", repository: Optional["Repository"] = None) -> tuple[int, str]:
        """
        Calculate priority score and return both score and bucket.

        Args:
            finding: Finding instance
            repository: Optional Repository instance

        Returns:
            Tuple of (priority_score, priority_bucket)
        """
        score = self.calculate(finding, repository)
        bucket = self.get_bucket(score)
        return score, bucket

    def _get_effective_tier_weight(self, finding: "Finding", repository: Optional["Repository"]) -> float:
        """
        Resolve tier weight from repository tier or product business_criticality.

        Priority: Repository.tier > Product.business_criticality > Default (1.0)

        Args:
            finding: Finding instance
            repository: Optional Repository instance

        Returns:
            Float tier weight multiplier
        """
        # Priority 1: Use repository tier if provided
        if repository and repository.tier:
            weight = self.TIER_WEIGHTS.get(repository.tier, 1.0)
            logger.debug("Using repository tier '%s' -> weight %.1f", repository.tier, weight)
            return weight

        # Priority 2: Fall back to product business_criticality
        try:
            product = finding.test.engagement.product
            if product and product.business_criticality:
                weight = self.TIER_WEIGHTS.get(product.business_criticality, 1.0)
                logger.debug(
                    "Using product business_criticality '%s' -> weight %.1f",
                    product.business_criticality, weight
                )
                return weight
        except AttributeError:
            logger.warning("Finding %s has incomplete test->engagement->product chain", finding.id)

        # Default to tier4 weight
        logger.debug("No tier/criticality found, using default weight 1.0")
        return 1.0

    def _calculate_modifiers(self, finding: "Finding", repository: Optional["Repository"]) -> int:
        """
        Calculate modifier points from various risk signals.

        Args:
            finding: Finding instance
            repository: Optional Repository instance

        Returns:
            Integer modifier value (positive or negative)
        """
        modifiers = 0

        # --- Positive modifiers ---

        # KEV (Known Exploited Vulnerability)
        if getattr(finding, "known_exploited", False):
            modifiers += self.MODIFIER_KEV
            logger.debug("Finding %s: +%d (KEV)", finding.id, self.MODIFIER_KEV)

        # Ransomware association
        if getattr(finding, "ransomware_used", False):
            modifiers += self.MODIFIER_RANSOMWARE
            logger.debug("Finding %s: +%d (ransomware)", finding.id, self.MODIFIER_RANSOMWARE)

        # EPSS score modifiers (only apply one)
        epss_score = getattr(finding, "epss_score", None)
        if epss_score is not None:
            if epss_score >= 0.7:
                modifiers += self.MODIFIER_EPSS_HIGH
                logger.debug("Finding %s: +%d (high EPSS %.2f)", finding.id, self.MODIFIER_EPSS_HIGH, epss_score)
            elif epss_score >= 0.3:
                modifiers += self.MODIFIER_EPSS_MEDIUM
                logger.debug("Finding %s: +%d (medium EPSS %.2f)", finding.id, self.MODIFIER_EPSS_MEDIUM, epss_score)
            elif epss_score < 0.02:
                modifiers += self.MODIFIER_EPSS_VERY_LOW
                logger.debug("Finding %s: %d (very low EPSS %.4f)", finding.id, self.MODIFIER_EPSS_VERY_LOW, epss_score)
            elif epss_score < 0.1:
                modifiers += self.MODIFIER_EPSS_LOW
                logger.debug("Finding %s: %d (low EPSS %.2f)", finding.id, self.MODIFIER_EPSS_LOW, epss_score)

        # Fix availability
        fix_available = getattr(finding, "fix_available", None)
        if fix_available is True:
            modifiers += self.MODIFIER_FIX_AVAILABLE
            logger.debug("Finding %s: +%d (fix available)", finding.id, self.MODIFIER_FIX_AVAILABLE)
        elif fix_available is False:
            modifiers += self.MODIFIER_NO_FIX
            logger.debug("Finding %s: %d (no fix)", finding.id, self.MODIFIER_NO_FIX)

        # SLA breach check
        sla_expiration = getattr(finding, "sla_expiration_date", None)
        if sla_expiration:
            today = timezone.now().date()
            if sla_expiration < today:
                modifiers += self.MODIFIER_SLA_BREACH
                logger.debug("Finding %s: +%d (SLA breach)", finding.id, self.MODIFIER_SLA_BREACH)

        # Repository-specific modifiers
        if repository:
            # Production signals (environments or releases)
            has_prod_signals = (
                getattr(repository, "has_environments", False) or
                getattr(repository, "has_releases", False)
            )
            if has_prod_signals:
                modifiers += self.MODIFIER_HAS_PROD_SIGNALS
                logger.debug("Finding %s: +%d (production signals)", finding.id, self.MODIFIER_HAS_PROD_SIGNALS)
            else:
                modifiers += self.MODIFIER_NO_PROD_SIGNALS
                logger.debug("Finding %s: %d (no production signals)", finding.id, self.MODIFIER_NO_PROD_SIGNALS)

            # Active webhooks (integration health)
            active_webhooks = getattr(repository, "active_webhooks_count", 0) or 0
            if active_webhooks > 0:
                modifiers += self.MODIFIER_HAS_WEBHOOKS
                logger.debug("Finding %s: +%d (active webhooks)", finding.id, self.MODIFIER_HAS_WEBHOOKS)

            # Dormant repository check
            days_since_commit = getattr(repository, "days_since_last_commit", None)
            if days_since_commit is not None and days_since_commit > 180:
                modifiers += self.MODIFIER_DORMANT_REPO
                logger.debug(
                    "Finding %s: %d (dormant repo, %d days)",
                    finding.id, self.MODIFIER_DORMANT_REPO, days_since_commit
                )

        return modifiers


def get_repository_for_finding(finding: "Finding") -> Optional["Repository"]:
    """
    Attempt to get the Repository associated with a finding.

    Checks if the finding came from a GitHub alert and returns the associated repository.

    Args:
        finding: Finding instance

    Returns:
        Repository instance if found, None otherwise
    """
    # Check if finding has a linked GitHub alert
    try:
        if hasattr(finding, "githubalert") and finding.githubalert:
            return finding.githubalert.repository
    except Exception:
        pass  # No linked alert

    # Try to get repository through product relationship
    try:
        product = finding.test.engagement.product
        # Get primary repository if one exists
        repositories = product.repositories.all()
        if repositories.exists():
            # Return first repository (typically the primary one)
            return repositories.first()
    except AttributeError:
        pass

    return None


# --- Celery Task for Async Priority Calculation ---

from dojo.decorators import dojo_async_task


@dojo_async_task
def calculate_finding_priority_task(finding_id: int) -> None:
    """
    Celery task to calculate priority score for a single finding.

    This task is triggered:
    - On finding create/update via the pre_save signal hook
    - By the calculate_priority_scores management command with --async flag

    Args:
        finding_id: Primary key of Finding to score

    Side Effects:
        Updates finding.priority_score, finding.priority_bucket, finding.priority_calculated_at
    """
    from dojo.models import Finding

    logger.debug("Calculating priority for finding %s", finding_id)

    try:
        finding = Finding.objects.select_related(
            'test__engagement__product'
        ).prefetch_related(
            'test__engagement__product__repositories'
        ).get(id=finding_id)
    except Finding.DoesNotExist:
        logger.warning("Finding %s not found, skipping priority calculation", finding_id)
        return

    # Skip inactive, duplicate, or mitigated findings
    if not finding.active or finding.duplicate or finding.is_mitigated:
        logger.debug("Finding %s is not active/duplicate/mitigated, skipping", finding_id)
        return

    # Get repository if available
    repository = get_repository_for_finding(finding)

    # Calculate priority
    scorer = PriorityScorer()
    score, bucket = scorer.calculate_and_get_bucket(finding, repository)

    # Update finding (only if changed to avoid unnecessary saves)
    if finding.priority_score != score or finding.priority_bucket != bucket:
        finding.priority_score = score
        finding.priority_bucket = bucket
        finding.priority_calculated_at = timezone.now()
        finding.save(update_fields=['priority_score', 'priority_bucket', 'priority_calculated_at'])
        logger.info("Updated priority for finding %s: score=%d, bucket=%s", finding_id, score, bucket)
    else:
        logger.debug("Priority unchanged for finding %s: score=%d, bucket=%s", finding_id, score, bucket)
