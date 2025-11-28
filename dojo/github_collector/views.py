"""
View handlers for GitHub Collector module.
"""

import json
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from dojo.models import GitHubSyncConfiguration
from dojo.github_collector.validator import GitHubValidator

logger = logging.getLogger(__name__)


def is_staff_or_superuser(user):
    """Check if user is staff or superuser."""
    return user.is_staff or user.is_superuser


def validate_github_config(token, account_type, account_name):
    """
    Validate GitHub configuration with comprehensive scope checking.

    Uses GitHubValidator to check:
    - Token format (ghp_* or github_pat_*)
    - Token scopes (repo, read:org, security_events)
    - Account existence and accessibility

    Returns: (is_valid, error_message, details)
    """
    validator = GitHubValidator(token, account_type, account_name)

    # Check token format first
    format_check = validator.validate_token_format()
    if format_check.status == 'fail':
        remediation = format_check.details.get('remediation', '')
        error_msg = format_check.message
        if remediation:
            error_msg = f"{error_msg}. {remediation}"
        return False, error_msg, format_check.details

    # Check token scopes
    scope_check = validator.validate_token_scopes()
    if scope_check.status == 'fail':
        remediation = scope_check.details.get('remediation', '')
        error_msg = scope_check.message
        if remediation:
            error_msg = f"{error_msg}. {remediation}"
        return False, error_msg, scope_check.details

    # Check account exists
    account_check = validator.validate_account_exists()
    if account_check.status == 'fail':
        remediation = account_check.details.get('remediation', '')
        error_msg = account_check.message
        if remediation:
            error_msg = f"{error_msg}. {remediation}"
        return False, error_msg, account_check.details

    return True, None, {
        'scopes': scope_check.details.get('scopes', []),
        'account_name': account_name,
        'repository_count': account_check.details.get('repository_count', 0)
    }


@login_required
@user_passes_test(is_staff_or_superuser)
def github_sync_configuration(request):
    """
    GitHub Sync Configuration page.

    Allows staff/superuser to configure GitHub repository synchronization settings.
    Only one configuration record exists (singleton pattern).
    """
    # Get or create the singleton configuration
    config, created = GitHubSyncConfiguration.objects.get_or_create(
        pk=1,
        defaults={
            'account_type': GitHubSyncConfiguration.ORGANIZATION,
            'account_name': '',
            'github_token': '',
            'auto_sync_enabled': False,
            'sync_schedule': GitHubSyncConfiguration.MANUAL,
            'incremental_sync': True,
        }
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_config':
            # Update configuration from form
            config.github_token = request.POST.get('github_token', '').strip()
            config.account_type = request.POST.get('account_type', GitHubSyncConfiguration.ORGANIZATION)
            config.account_name = request.POST.get('account_name', '').strip()
            config.auto_sync_enabled = request.POST.get('auto_sync_enabled') == 'on'
            config.sync_schedule = request.POST.get('sync_schedule', GitHubSyncConfiguration.MANUAL)
            config.incremental_sync = request.POST.get('incremental_sync') == 'on'

            # Comprehensive validation (format, scopes, account existence)
            config_valid, config_error, config_details = validate_github_config(
                config.github_token,
                config.account_type,
                config.account_name
            )
            if not config_valid:
                messages.error(request, config_error)
            elif not config.account_name:
                messages.error(request, 'Account name is required')
            else:
                try:
                    config.save()
                    repo_count = config_details.get('repository_count', 0)
                    messages.success(
                        request,
                        f'GitHub sync configuration saved successfully. '
                        f'Found {repo_count} repositories in {config.account_name}.'
                    )
                    logger.info(f"GitHub sync config updated by {request.user.username}")
                except Exception as e:
                    messages.error(request, f'Error saving configuration: {str(e)}')
                    logger.error(f"Error saving GitHub sync config: {e}")

        elif action == 'trigger_sync':
            # Trigger manual sync
            if not config.github_token or not config.account_name:
                messages.error(request, 'Please configure GitHub token and account name first')
            else:
                try:
                    # Call management command
                    call_command(
                        'sync_github_repositories',
                        token=config.github_token,
                        org=config.account_name,
                        incremental=config.incremental_sync
                    )

                    # Update sync status
                    config.last_sync = timezone.now()
                    config.last_sync_status = 'success'
                    config.last_sync_error = ''
                    config.save()

                    messages.success(request, f'Repository sync completed successfully for {config.account_name}')
                    logger.info(f"Manual sync triggered by {request.user.username} for {config.account_name}")
                except Exception as e:
                    # Update sync status with error
                    config.last_sync = timezone.now()
                    config.last_sync_status = 'failed'
                    config.last_sync_error = str(e)
                    config.save()

                    messages.error(request, f'Sync failed: {str(e)}')
                    logger.error(f"Manual sync failed: {e}")

        return redirect('github_sync_configuration')

    context = {
        'config': config,
        'account_types': GitHubSyncConfiguration.ACCOUNT_TYPE_CHOICES,
        'sync_schedules': GitHubSyncConfiguration.SYNC_SCHEDULE_CHOICES,
    }

    return render(request, 'dojo/github_sync_configuration.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def github_test_connection(request):
    """
    AJAX endpoint for testing GitHub connection.

    Runs all 6 validation checks and returns structured JSON response.

    POST /github/sync/test-connection
    Body: {"token": "...", "account_type": "...", "account_name": "..."}

    Returns:
        {
            "valid": true/false,
            "ready_to_sync": true/false,
            "checks": {...},
            "warnings": [...],
            "errors": [...]
        }
    """
    try:
        # Parse JSON body
        data = json.loads(request.body)
        token = data.get('token', '').strip()
        account_type = data.get('account_type', 'organization')
        account_name = data.get('account_name', '').strip()

        # Run full validation
        validator = GitHubValidator(token, account_type, account_name)
        result = validator.validate_full_setup()

        logger.info(
            f"GitHub test connection by {request.user.username}: "
            f"valid={result.valid}, account={account_name}"
        )

        return JsonResponse(validator.to_dict(result))

    except json.JSONDecodeError:
        return JsonResponse({
            'valid': False,
            'ready_to_sync': False,
            'checks': {},
            'warnings': [],
            'errors': [{'message': 'Invalid JSON in request body'}]
        }, status=400)
    except Exception as e:
        logger.error(f"GitHub test connection error: {e}")
        return JsonResponse({
            'valid': False,
            'ready_to_sync': False,
            'checks': {},
            'warnings': [],
            'errors': [{'message': f'Server error: {str(e)}'}]
        }, status=500)
