"""
Auto-Triage Rules

Defines triage rules evaluated by the AutoTriageEngine.
Rules are evaluated in order, first matching rule wins.

Rule Structure:
{
    'name': 'unique_identifier',
    'condition': lambda finding: bool,  # Evaluation function
    'decision': 'DISMISS'|'ESCALATE'|'ACCEPT_RISK',
    'reason': 'Human-readable explanation',
    'confidence': 0-100  # Optional confidence score
}

Rule Evaluation Order:
1. Critical/High Risk Escalations (high EPSS + critical repos)
2. Risk Acceptances (archived repos, internal tools)
3. Low Risk Dismissals (low EPSS + non-critical repos)
4. Fallback to PENDING (manual review required)
"""


class TriageDecision:
    """Triage decision constants."""
    PENDING = 'PENDING'
    DISMISS = 'DISMISS'
    ESCALATE = 'ESCALATE'
    ACCEPT_RISK = 'ACCEPT_RISK'


# ============================================================================
# Helper Functions
# ============================================================================


def has_product(finding) -> bool:
    """Check if finding has associated product."""
    try:
        return (
            hasattr(finding, 'test') and
            hasattr(finding.test, 'engagement') and
            hasattr(finding.test.engagement, 'product') and
            finding.test.engagement.product is not None
        )
    except Exception:
        return False


def get_product(finding):
    """Get product from finding (returns None if not found)."""
    if not has_product(finding):
        return None
    return finding.test.engagement.product


def is_tier1_product(finding) -> bool:
    """Check if finding is in Tier 1 (very high criticality) product."""
    product = get_product(finding)
    return product and product.business_criticality == 'very high'


def is_tier2_product(finding) -> bool:
    """Check if finding is in Tier 2 (high criticality) product."""
    product = get_product(finding)
    return product and product.business_criticality == 'high'


def is_tier3_product(finding) -> bool:
    """Check if finding is in Tier 3 (medium criticality) product."""
    product = get_product(finding)
    return product and product.business_criticality == 'medium'


def is_tier4_product(finding) -> bool:
    """Check if finding is in Tier 4 (low criticality) product."""
    product = get_product(finding)
    return product and product.business_criticality == 'low'


def is_archived_product(finding) -> bool:
    """Check if finding is in archived product."""
    product = get_product(finding)
    return product and product.business_criticality == 'none'


def has_high_epss(finding, threshold: float = 0.5) -> bool:
    """Check if finding has high EPSS score (≥ threshold)."""
    return finding.epss_score is not None and finding.epss_score >= threshold


def has_medium_epss(finding, min_threshold: float = 0.2, max_threshold: float = 0.5) -> bool:
    """Check if finding has medium EPSS score."""
    return (
        finding.epss_score is not None and
        finding.epss_score >= min_threshold and
        finding.epss_score < max_threshold
    )


def has_low_epss(finding, threshold: float = 0.05) -> bool:
    """Check if finding has low EPSS score (< threshold)."""
    return finding.epss_score is not None and finding.epss_score < threshold


def is_critical_or_high_severity(finding) -> bool:
    """Check if finding has Critical or High severity."""
    return finding.severity in ['Critical', 'High']


def is_low_or_info_severity(finding) -> bool:
    """Check if finding has Low or Info severity."""
    return finding.severity in ['Low', 'Info']


def has_production_signal(finding) -> bool:
    """Check if product has production deployment signals."""
    product = get_product(finding)
    if not product:
        return False
    return (
        product.has_kubernetes_config or
        product.has_environments or
        product.has_releases
    )


def has_active_development(finding) -> bool:
    """Check if product has active development signals."""
    product = get_product(finding)
    if not product:
        return False
    return (
        product.recent_commits_30d and
        product.active_prs_30d and
        product.multiple_contributors
    )


def is_dormant_repo(finding, days_threshold: int = 180) -> bool:
    """Check if repository is dormant (no commits in 180+ days)."""
    product = get_product(finding)
    if not product or product.days_since_last_commit is None:
        return False
    return product.days_since_last_commit > days_threshold


# ============================================================================
# Triage Rules (Evaluated in Order)
# ============================================================================

TRIAGE_RULES = [
    # ========================================================================
    # CRITICAL ESCALATIONS
    # ========================================================================

    {
        'name': 'critical_high_epss_tier1',
        'condition': lambda f: (
            is_tier1_product(f) and
            has_high_epss(f, threshold=0.7) and
            is_critical_or_high_severity(f) and
            has_production_signal(f)
        ),
        'decision': TriageDecision.ESCALATE,
        'reason': 'Critical/High severity with very high EPSS score (≥70%) in Tier 1 production repository - immediate action required',
        'confidence': 95
    },

    {
        'name': 'high_epss_tier1_production',
        'condition': lambda f: (
            is_tier1_product(f) and
            has_high_epss(f, threshold=0.5) and
            has_production_signal(f)
        ),
        'decision': TriageDecision.ESCALATE,
        'reason': 'High EPSS score (≥50%) in Tier 1 production repository - requires priority remediation',
        'confidence': 90
    },

    {
        'name': 'critical_severity_tier1',
        'condition': lambda f: (
            is_tier1_product(f) and
            is_critical_or_high_severity(f) and
            has_high_epss(f, threshold=0.3)
        ),
        'decision': TriageDecision.ESCALATE,
        'reason': 'Critical/High severity in Tier 1 repository with moderate EPSS (≥30%)',
        'confidence': 85
    },

    # ========================================================================
    # HIGH PRIORITY ESCALATIONS
    # ========================================================================

    {
        'name': 'high_epss_tier2_production',
        'condition': lambda f: (
            is_tier2_product(f) and
            has_high_epss(f, threshold=0.6) and
            has_production_signal(f)
        ),
        'decision': TriageDecision.ESCALATE,
        'reason': 'High EPSS score (≥60%) in Tier 2 production repository',
        'confidence': 85
    },

    {
        'name': 'critical_severity_tier2_active',
        'condition': lambda f: (
            is_tier2_product(f) and
            is_critical_or_high_severity(f) and
            has_high_epss(f, threshold=0.4) and
            has_active_development(f)
        ),
        'decision': TriageDecision.ESCALATE,
        'reason': 'Critical/High severity in active Tier 2 repository with elevated EPSS (≥40%)',
        'confidence': 80
    },

    # ========================================================================
    # RISK ACCEPTANCE
    # ========================================================================

    {
        'name': 'accept_archived_repo',
        'condition': lambda f: is_archived_product(f),
        'decision': TriageDecision.ACCEPT_RISK,
        'reason': 'Finding in archived repository - no active maintenance planned',
        'confidence': 95
    },

    {
        'name': 'accept_dormant_low_risk',
        'condition': lambda f: (
            is_dormant_repo(f, days_threshold=180) and
            has_low_epss(f, threshold=0.1) and
            not is_critical_or_high_severity(f)
        ),
        'decision': TriageDecision.ACCEPT_RISK,
        'reason': 'Low risk finding in dormant repository (180+ days no commits) - deferred until repository reactivation',
        'confidence': 85
    },

    {
        'name': 'accept_low_epss_tier4',
        'condition': lambda f: (
            is_tier4_product(f) and
            has_low_epss(f, threshold=0.05) and
            is_low_or_info_severity(f)
        ),
        'decision': TriageDecision.ACCEPT_RISK,
        'reason': 'Low severity with minimal EPSS (<5%) in Tier 4 repository - accepted risk',
        'confidence': 80
    },

    # ========================================================================
    # DISMISSALS
    # ========================================================================

    {
        'name': 'dismiss_very_low_epss_tier3_or_4',
        'condition': lambda f: (
            (is_tier3_product(f) or is_tier4_product(f)) and
            has_low_epss(f, threshold=0.02) and
            not is_critical_or_high_severity(f)
        ),
        'decision': TriageDecision.DISMISS,
        'reason': 'Very low EPSS score (<2%) in non-critical repository (Tier 3/4) - minimal exploitation risk',
        'confidence': 85
    },

    {
        'name': 'dismiss_info_severity_low_epss',
        'condition': lambda f: (
            finding.severity == 'Info' and
            has_low_epss(f, threshold=0.1)
        ),
        'decision': TriageDecision.DISMISS,
        'reason': 'Informational severity with low EPSS (<10%) - not actionable',
        'confidence': 90
    },

    {
        'name': 'dismiss_low_epss_tier4_no_production',
        'condition': lambda f: (
            is_tier4_product(f) and
            has_low_epss(f, threshold=0.1) and
            not has_production_signal(f)
        ),
        'decision': TriageDecision.DISMISS,
        'reason': 'Low EPSS (<10%) in non-production Tier 4 repository - minimal business impact',
        'confidence': 80
    },

    # ========================================================================
    # MEDIUM PRIORITY (Manual Review Required)
    # ========================================================================

    {
        'name': 'review_medium_epss_tier2',
        'condition': lambda f: (
            is_tier2_product(f) and
            has_medium_epss(f, min_threshold=0.2, max_threshold=0.5)
        ),
        'decision': TriageDecision.PENDING,
        'reason': 'Medium EPSS score (20-50%) in Tier 2 repository - manual assessment recommended',
        'confidence': 70
    },

    {
        'name': 'review_high_severity_no_epss',
        'condition': lambda f: (
            is_critical_or_high_severity(f) and
            finding.epss_score is None and
            (is_tier1_product(f) or is_tier2_product(f))
        ),
        'decision': TriageDecision.PENDING,
        'reason': 'High/Critical severity in Tier 1/2 without EPSS score - manual triage required',
        'confidence': 75
    },

    # ========================================================================
    # FALLBACK
    # ========================================================================

    {
        'name': 'default_pending',
        'condition': lambda f: True,  # Always matches
        'decision': TriageDecision.PENDING,
        'reason': 'No specific auto-triage rule matched - requires manual review',
        'confidence': 50
    }
]


# ============================================================================
# Rule Validation
# ============================================================================


def validate_all_rules() -> List[str]:
    """
    Validate all triage rules for correctness.

    Returns:
        List of validation errors (empty if all valid)
    """
    errors = []

    required_keys = ['name', 'condition', 'decision', 'reason']
    valid_decisions = [TriageDecision.DISMISS, TriageDecision.ESCALATE, TriageDecision.ACCEPT_RISK, TriageDecision.PENDING]

    rule_names = set()

    for idx, rule in enumerate(TRIAGE_RULES):
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

        # Check for duplicate names
        if 'name' in rule:
            if rule['name'] in rule_names:
                errors.append(f"Rule {idx}: Duplicate rule name '{rule['name']}'")
            rule_names.add(rule['name'])

    return errors


if __name__ == '__main__':
    # Run validation when module is executed directly
    errors = validate_all_rules()
    if errors:
        print(f"Found {len(errors)} validation errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print(f"All {len(TRIAGE_RULES)} rules are valid ✓")
