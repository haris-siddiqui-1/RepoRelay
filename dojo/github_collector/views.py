"""
View handlers for GitHub Collector module.
"""

import logging
import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.management import call_command
from django.shortcuts import render, redirect
from django.utils import timezone

from dojo.models import GitHubSyncConfiguration

logger = logging.getLogger(__name__)


def is_staff_or_superuser(user):
    """Check if user is staff or superuser."""
    return user.is_staff or user.is_superuser


def validate_github_token(token):
    """
    Validate GitHub token format and optionally test with API.

    Returns: (is_valid, error_message)
    """
    if not token:
        return False, "GitHub token is required"

    # Check token format
    if not (token.startswith('ghp_') or token.startswith('github_pat_')):
        return False, "Invalid GitHub token format (must start with 'ghp_' or 'github_pat_')"

    # Optional: Test token with minimal API call
    try:
        headers = {'Authorization': f'token {token}'}
        response = requests.get('https://api.github.com/user', headers=headers, timeout=10)

        if response.status_code == 401:
            return False, "Invalid GitHub token - authentication failed"
        elif response.status_code == 403:
            return False, "GitHub token lacks required permissions"
        elif response.status_code != 200:
            logger.warning(f"GitHub token validation returned status {response.status_code}")
            # Don't fail on unexpected statuses, token format is valid

    except requests.RequestException as e:
        logger.warning(f"Could not validate token with GitHub API: {e}")
        # Don't fail validation if API is unreachable, token format is valid

    return True, None


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

            # Validation
            token_valid, token_error = validate_github_token(config.github_token)
            if not token_valid:
                messages.error(request, token_error)
            elif not config.account_name:
                messages.error(request, 'Account name is required')
            else:
                try:
                    config.save()
                    messages.success(request, 'GitHub sync configuration saved successfully')
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
