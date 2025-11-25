"""
Triage Service - Phase 2 of Vulnerability Prioritization Strategy

Provides business logic for triage workflow operations:
- State transition validation
- Triage action execution
- History record creation
- Bulk triage operations
"""

import logging
from typing import TYPE_CHECKING, Optional, List, Dict, Any

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

if TYPE_CHECKING:
    from dojo.models import Finding, Dojo_User, TriageHistory

logger = logging.getLogger(__name__)


# Valid state transitions (from_state -> list of valid to_states via action)
VALID_TRANSITIONS = {
    'pending': {
        'escalate': 'escalated',
        'assign': 'assigned',
        'defer': 'deferred',
        'accept': 'accepted',
        'dismiss': 'dismissed',
    },
    'escalated': {
        'assign': 'assigned',
    },
    'assigned': {
        'defer': 'deferred',
        'accept': 'accepted',
        'dismiss': 'dismissed',
    },
    'deferred': {
        'reopen': 'pending',
        'assign': 'assigned',
    },
    'dismissed': {
        'reopen': 'pending',
    },
    'accepted': {
        'reopen': 'pending',
    },
}

# Actions that require a reason
ACTIONS_REQUIRING_REASON = {'accept', 'dismiss'}

# Action to state mapping
ACTION_TO_STATE = {
    'escalate': 'escalated',
    'assign': 'assigned',
    'defer': 'deferred',
    'accept': 'accepted',
    'dismiss': 'dismissed',
    'reopen': 'pending',
}

# Map API action verbs to TriageHistory action values (past tense for consistency)
ACTION_TO_HISTORY_ACTION = {
    'escalate': 'escalated',
    'assign': 'assigned',
    'defer': 'deferred',
    'accept': 'accepted',
    'dismiss': 'dismissed',
    'reopen': 'reopened',
}


def is_valid_transition(current_state: str, action: str) -> bool:
    """
    Check if a transition from current_state via action is valid.

    Args:
        current_state: Current triage_state value
        action: Triage action to perform

    Returns:
        True if transition is valid, False otherwise
    """
    transitions = VALID_TRANSITIONS.get(current_state, {})
    return action in transitions


def get_new_state(action: str) -> str:
    """
    Get the resulting state for an action.

    Args:
        action: Triage action

    Returns:
        New triage_state value

    Raises:
        ValidationError: If action is invalid
    """
    if action not in ACTION_TO_STATE:
        raise ValidationError(f"Invalid triage action: {action}")
    return ACTION_TO_STATE[action]


def validate_triage_action(
    finding: "Finding",
    action: str,
    reason: Optional[str] = None,
    assigned_to: Optional["Dojo_User"] = None,
) -> None:
    """
    Validate a triage action before execution.

    Args:
        finding: Finding to triage
        action: Triage action to perform
        reason: Optional reason for the action
        assigned_to: Optional user to assign (required for 'assign' action)

    Raises:
        ValidationError: If validation fails
    """
    # Check action is valid
    if action not in ACTION_TO_STATE:
        raise ValidationError(f"Invalid triage action: {action}. Valid actions: {list(ACTION_TO_STATE.keys())}")

    # Check state transition is valid
    current_state = finding.triage_state or 'pending'
    if not is_valid_transition(current_state, action):
        valid_actions = list(VALID_TRANSITIONS.get(current_state, {}).keys())
        raise ValidationError(
            f"Invalid transition: Cannot perform '{action}' from state '{current_state}'. "
            f"Valid actions: {valid_actions}"
        )

    # Check reason is provided for actions that require it
    if action in ACTIONS_REQUIRING_REASON and not reason:
        raise ValidationError(f"Reason is required for '{action}' action")

    # Check assigned_to is provided for 'assign' action
    if action == 'assign' and not assigned_to:
        raise ValidationError("assigned_to is required for 'assign' action")


def perform_triage_action(
    finding: "Finding",
    action: str,
    user: Optional["Dojo_User"],
    reason: Optional[str] = None,
    assigned_to: Optional["Dojo_User"] = None,
    due_date: Optional["date"] = None,
    skip_validation: bool = False,
) -> "Finding":
    """
    Perform a triage action on a finding.

    Args:
        finding: Finding to triage
        action: Triage action to perform (escalate, assign, defer, accept, dismiss, reopen)
        user: User performing the action (None for system/auto-triage)
        reason: Optional reason for the action
        assigned_to: Optional user to assign (required for 'assign' action)
        due_date: Optional due date for deferred findings
        skip_validation: Skip validation (use with caution, for auto-triage)

    Returns:
        Updated Finding instance

    Raises:
        ValidationError: If validation fails
    """
    from dojo.models import TriageHistory

    if not skip_validation:
        validate_triage_action(finding, action, reason, assigned_to)

    old_state = finding.triage_state or 'pending'
    new_state = get_new_state(action)

    logger.info(
        "Performing triage action '%s' on finding %s: %s -> %s (by %s)",
        action, finding.id, old_state, new_state, user.username if user else "system"
    )

    with transaction.atomic():
        # Update finding fields
        finding.triage_state = new_state
        finding.triage_reason = reason or ''

        if action == 'assign':
            finding.triage_assigned_to = assigned_to
        elif action == 'reopen':
            # Clear assignment on reopen
            finding.triage_assigned_to = None
            finding.triage_due_date = None

        if action == 'defer' and due_date:
            finding.triage_due_date = due_date

        # Save finding
        update_fields = ['triage_state', 'triage_reason', 'triage_assigned_to', 'triage_due_date']
        finding.save(update_fields=update_fields)

        # Create history record
        # Map API action verbs to history action values (past tense)
        history_action = ACTION_TO_HISTORY_ACTION.get(action, action)
        TriageHistory.objects.create(
            finding=finding,
            action=history_action,
            previous_state=old_state,
            new_state=new_state,
            reason=reason or '',
            performed_by=user,
        )

        logger.debug(
            "Created TriageHistory for finding %s: %s -> %s",
            finding.id, old_state, new_state
        )

    return finding


def perform_auto_triage(
    finding: "Finding",
    decision: str,
    rule_name: str,
    reason: str,
    confidence: int,
    save: bool = True,
) -> "Finding":
    """
    Apply an auto-triage decision to a finding.

    This is called by AutoTriageEngine when a rule matches.

    Args:
        finding: Finding to triage
        decision: Triage decision (DISMISS, ESCALATE, ACCEPT_RISK, PENDING)
        rule_name: Name of the rule that matched
        reason: Explanation from the rule
        confidence: Confidence score (0-100)
        save: Whether to save the finding (default True). Set to False when
              caller will save with additional fields.

    Returns:
        Updated Finding instance (fields updated, saved only if save=True)
    """
    from dojo.models import TriageHistory

    # Map auto-triage decision to triage state
    DECISION_TO_STATE = {
        'PENDING': 'pending',
        'DISMISS': 'dismissed',
        'ESCALATE': 'escalated',
        'ACCEPT_RISK': 'accepted',
    }

    # Map decision to action for history
    DECISION_TO_ACTION = {
        'PENDING': 'auto_triaged',
        'DISMISS': 'dismissed',
        'ESCALATE': 'escalated',
        'ACCEPT_RISK': 'accepted',
    }

    new_state = DECISION_TO_STATE.get(decision, 'pending')
    old_state = finding.triage_state or 'pending'

    # Skip if state unchanged
    if old_state == new_state:
        logger.debug(
            "Auto-triage for finding %s: state unchanged (%s), skipping",
            finding.id, new_state
        )
        return finding

    logger.info(
        "Auto-triaging finding %s: %s -> %s (rule: %s, confidence: %d%%)",
        finding.id, old_state, new_state, rule_name, confidence
    )

    with transaction.atomic():
        # Update finding triage workflow fields
        finding.triage_state = new_state
        finding.triage_reason = reason
        finding.auto_triage_rule = rule_name
        finding.auto_triage_confidence = confidence

        # Save with update_fields to prevent infinite loops with signals
        # Only save if save=True (caller may want to save with additional fields)
        if save:
            update_fields = [
                'triage_state',
                'triage_reason',
                'auto_triage_rule',
                'auto_triage_confidence',
            ]
            finding.save(update_fields=update_fields)

        # Create history record
        TriageHistory.objects.create(
            finding=finding,
            action='auto_triaged',
            previous_state=old_state,
            new_state=new_state,
            reason=reason,
            rule_name=rule_name,
            confidence=confidence,
            performed_by=None,  # System action
        )

    return finding


def bulk_triage(
    finding_ids: List[int],
    action: str,
    user: "Dojo_User",
    reason: Optional[str] = None,
    assigned_to: Optional["Dojo_User"] = None,
    due_date: Optional["date"] = None,
) -> Dict[str, Any]:
    """
    Perform a triage action on multiple findings.

    Args:
        finding_ids: List of Finding IDs to triage
        action: Triage action to perform
        user: User performing the action
        reason: Optional reason for the action
        assigned_to: Optional user to assign (for 'assign' action)
        due_date: Optional due date (for 'defer' action)

    Returns:
        Dictionary with:
        - success_count: Number of findings successfully triaged
        - error_count: Number of findings that failed
        - errors: List of error details
    """
    from dojo.models import Finding

    result = {
        'success_count': 0,
        'error_count': 0,
        'errors': [],
    }

    # Validate action first
    if action not in ACTION_TO_STATE:
        result['errors'].append({
            'finding_id': None,
            'error': f"Invalid action: {action}"
        })
        result['error_count'] = len(finding_ids)
        return result

    # Validate assigned_to for assign action
    if action == 'assign' and not assigned_to:
        result['errors'].append({
            'finding_id': None,
            'error': "assigned_to is required for 'assign' action"
        })
        result['error_count'] = len(finding_ids)
        return result

    # Validate reason for accept/dismiss actions
    if action in ACTIONS_REQUIRING_REASON and not reason:
        result['errors'].append({
            'finding_id': None,
            'error': f"Reason is required for '{action}' action"
        })
        result['error_count'] = len(finding_ids)
        return result

    # Process each finding
    findings = Finding.objects.filter(id__in=finding_ids)

    for finding in findings:
        try:
            perform_triage_action(
                finding=finding,
                action=action,
                user=user,
                reason=reason,
                assigned_to=assigned_to,
                due_date=due_date,
            )
            result['success_count'] += 1
        except ValidationError as e:
            result['error_count'] += 1
            # Django ValidationError uses .messages (list), not .message
            error_msg = e.messages[0] if hasattr(e, 'messages') and e.messages else str(e)
            result['errors'].append({
                'finding_id': finding.id,
                'error': error_msg
            })
        except Exception as e:
            result['error_count'] += 1
            result['errors'].append({
                'finding_id': finding.id,
                'error': str(e)
            })
            logger.exception("Error bulk triaging finding %s", finding.id)

    # Check for missing findings
    found_ids = set(findings.values_list('id', flat=True))
    missing_ids = set(finding_ids) - found_ids
    for missing_id in missing_ids:
        result['error_count'] += 1
        result['errors'].append({
            'finding_id': missing_id,
            'error': 'Finding not found'
        })

    logger.info(
        "Bulk triage completed: %d success, %d errors",
        result['success_count'], result['error_count']
    )

    return result


def get_valid_actions(current_state: str) -> List[str]:
    """
    Get list of valid actions for a given state.

    Args:
        current_state: Current triage_state value

    Returns:
        List of valid action strings
    """
    return list(VALID_TRANSITIONS.get(current_state, {}).keys())
