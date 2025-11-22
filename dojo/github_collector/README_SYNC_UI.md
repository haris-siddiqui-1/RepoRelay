# GitHub Sync Configuration UI

Web-based configuration interface for GitHub repository synchronization in DefectDojo.

## Overview

The GitHub Sync Configuration UI provides a staff/superuser interface for configuring and managing GitHub repository synchronization settings. It replaces manual environment variable configuration with a user-friendly web form.

**URL:** `/github/sync/configuration`  
**Access:** Staff or superuser only  
**View:** `dojo/github_collector/views.py:github_sync_configuration()`  
**Template:** `dojo/templates/dojo/github_sync_configuration.html`

## Features

### 1. GitHub Token Management
- **Token Input**: Secure text field for GitHub Personal Access Token (PAT)
- **Format Validation**: Ensures token starts with `ghp_` or `github_pat_`
- **API Connectivity Test**: Validates token by testing against GitHub API `/user` endpoint
- **Error Feedback**: Clear error messages for invalid tokens or authentication failures

**Token Requirements:**
- Personal Access Token (classic) or Fine-grained Personal Access Token
- Required scopes:
  - `repo` - Full control of private repositories
  - `read:org` - Read org and team membership
  - `security_events` - Read security events (for alerts)

**Validation Function** (`dojo/github_collector/views.py:23-53`):
```python
def validate_github_token(token):
    """
    Validate GitHub token format and optionally test with API.
    
    Returns: (is_valid, error_message)
    """
    # Format check
    if not (token.startswith('ghp_') or token.startswith('github_pat_')):
        return False, "Invalid GitHub token format"
    
    # API connectivity test
    response = requests.get('https://api.github.com/user', 
                           headers={'Authorization': f'token {token}'})
    
    if response.status_code == 401:
        return False, "Invalid GitHub token - authentication failed"
    
    return True, None
```

### 2. Account Type Selection
- **Organization**: Sync all repositories from a GitHub organization
- **Personal Account**: Sync repositories from a user account (uses GraphQL `user_batch.graphql` query)

**Account Name Field:**
- Organization name (e.g., `defectdojo`)
- GitHub username (e.g., `john-doe`)

### 3. Sync Settings
- **Auto-sync Enabled**: Toggle automatic synchronization
- **Sync Schedule**: 
  - Manual (default)
  - Hourly
  - Daily (recommended for production)
  - Weekly
- **Incremental Sync**: Only fetch repositories updated since last sync (recommended: enabled)

### 4. Manual Sync Trigger
- **"Trigger Sync Now" Button**: Manually start repository synchronization
- **Real-time Feedback**: 
  - Success message: "Repository sync completed successfully for {account_name}"
  - Error message: "Sync failed: {error_details}"
- **Status Tracking**: Updates `last_sync`, `last_sync_status`, `last_sync_error` fields

**Sync Command Execution** (`dojo/github_collector/views.py:110-135`):
```python
call_command(
    'sync_github_repositories',
    token=config.github_token,
    org=config.account_name,
    incremental=config.incremental_sync
)

# Update sync status
config.last_sync = timezone.now()
config.last_sync_status = 'success'
config.save()
```

### 5. Last Sync Status Display
- **Last Sync Time**: Timestamp of last successful or failed sync
- **Status Indicator**: 
  - Success (green badge)
  - Failed (red badge with error message)
- **Error Details**: Full error message for failed syncs

## Data Model

### GitHubSyncConfiguration Model

**Location:** `dojo/models.py`  
**Pattern:** Singleton (only one configuration record exists with pk=1)

**Fields:**
```python
class GitHubSyncConfiguration(models.Model):
    # Core settings
    github_token = models.CharField(max_length=255, blank=True)
    account_type = models.CharField(
        max_length=20,
        choices=[('organization', 'Organization'), ('user', 'Personal Account')],
        default='organization'
    )
    account_name = models.CharField(max_length=255, blank=True)
    
    # Sync settings
    auto_sync_enabled = models.BooleanField(default=False)
    sync_schedule = models.CharField(
        max_length=20,
        choices=[
            ('manual', 'Manual'),
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly')
        ],
        default='manual'
    )
    incremental_sync = models.BooleanField(default=True)
    
    # Status tracking
    last_sync = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=20, blank=True)
    last_sync_error = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Migration:** `dojo/db_migrations/0257_github_sync_configuration.py`

## Usage Workflow

### Initial Setup

1. Navigate to `/github/sync/configuration` (requires staff/superuser login)
2. Enter GitHub Personal Access Token
3. Select account type (Organization or Personal Account)
4. Enter account name (org name or username)
5. Configure sync settings:
   - Enable auto-sync (optional)
   - Choose sync schedule
   - Enable incremental sync (recommended)
6. Click "Save Configuration"

**Validation:**
- Token format validated
- Token tested against GitHub API
- Account name required
- Success message displayed

### Manual Sync

1. Ensure configuration is saved
2. Click "Trigger Sync Now" button
3. Monitor sync progress in logs:
   ```bash
   docker compose logs -f uwsgi | grep "Progress:"
   ```
4. View sync status on configuration page:
   - Last sync timestamp
   - Success/failed status
   - Error details (if failed)

### Progress Tracking

**GraphQL Sync** (`dojo/github_collector/collector.py:166-187`):
- Logs progress every 10 repositories
- Example: "Progress: 50/250 repositories processed"

**REST Sync** (`dojo/github_collector/collector.py:215-238`):
- Logs progress every 10 repositories
- Example: "Progress: 100 repositories processed so far"

**Log Monitoring:**
```bash
# Follow sync progress
docker compose logs -f uwsgi | grep "github_collector"

# Check for errors
docker compose logs uwsgi | grep -i "error" | tail -20
```

## Security Considerations

### Access Control
- **@login_required**: User must be authenticated
- **@user_passes_test(is_staff_or_superuser)**: Only staff or superuser can access
- **Token Storage**: Tokens stored in database (not encrypted by default - consider encryption at rest)

### Token Security Best Practices
- Use fine-grained Personal Access Tokens with minimal scopes
- Rotate tokens regularly (every 90 days recommended)
- Never commit tokens to version control
- Use environment variables for CI/CD automation

### API Rate Limits
- GitHub GraphQL: 5,000 points/hour
- GitHub REST: 5,000 requests/hour
- Token validation adds ~1 API call per save
- Monitor rate limits via Django logs

## API Endpoints

### Configuration View
- **URL:** `/github/sync/configuration`
- **Methods:** GET, POST
- **Authentication:** Session-based (staff/superuser)
- **CSRF Protection:** Required for POST requests

### POST Actions
1. **save_config**: Save configuration settings
   - Validates token format and API connectivity
   - Updates GitHubSyncConfiguration record
   - Returns success/error message

2. **trigger_sync**: Manually trigger repository sync
   - Calls `sync_github_repositories` management command
   - Updates last_sync status
   - Returns success/error message

## Integration with Management Commands

The UI triggers the same management command used for CLI access:

```bash
# CLI equivalent of "Trigger Sync Now" button
python manage.py sync_github_repositories \
    --token <github_token> \
    --org <account_name> \
    --incremental
```

**Command Options:**
- `--token`: GitHub Personal Access Token
- `--org`: Organization or user account name
- `--incremental`: Only sync updated repositories (default: False)
- `--use-graphql`: Use GraphQL API (default: True)

## Error Handling

### Token Validation Errors
- **Format Error**: "Invalid GitHub token format (must start with 'ghp_' or 'github_pat_')"
- **Authentication Error**: "Invalid GitHub token - authentication failed"
- **Permission Error**: "GitHub token lacks required permissions"

### Sync Errors
- **Network Error**: "Could not connect to GitHub API"
- **Rate Limit Error**: "Rate limit exceeded - retry after {reset_time}"
- **Data Error**: Specific error from sync operation (stored in `last_sync_error`)

### Logging
All errors logged to Django logger with context:
```python
logger.error(f"Manual sync failed: {e}")
logger.info(f"Manual sync triggered by {request.user.username} for {config.account_name}")
```

## Future Enhancements

### Planned Features
- **Token Encryption**: Encrypt tokens at rest in database
- **Multi-account Support**: Support multiple GitHub organizations/users
- **Scheduled Sync via Celery Beat**: Automatic background sync based on schedule
- **Sync History**: Track sync history with detailed logs
- **Repository Filtering**: Sync only specific repositories matching criteria
- **Webhook Integration**: Real-time sync triggered by GitHub webhooks

### Performance Optimizations
- **Async Sync**: Run sync in background Celery task (non-blocking UI)
- **Progress Bar**: Real-time progress updates via WebSocket or polling
- **Batch Configuration**: Configure multiple accounts at once

## Troubleshooting

### Common Issues

**Issue**: Token validation fails with "Could not validate token with GitHub API"  
**Solution**: Check network connectivity to github.com, verify firewall rules

**Issue**: Sync fails with "No repositories found"  
**Solution**: Verify account name is correct, check token has `repo` scope

**Issue**: Incremental sync doesn't skip unchanged repos  
**Solution**: Ensure `incremental_sync` is enabled, check Repository model has `last_updated` timestamps

**Issue**: Sync takes too long (>10 minutes)  
**Solution**: Enable incremental sync, check GraphQL query complexity, consider REST fallback

### Debug Mode

Enable debug logging in Django settings:
```python
LOGGING = {
    'loggers': {
        'dojo.github_collector': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    },
}
```

## Related Documentation

- **Main CLAUDE.md**: Section "GitHub Integration" → "Repository Context Enrichment"
- **README_GRAPHQL.md**: GraphQL sync implementation details
- **README_ALERTS.md**: Security alerts collection (separate from repository sync)
- **dojo/github_collector/README.md**: Module overview and architecture

## Code Review Notes

From code review session (2025-11-21):

**Status**: PASS WITH RECOMMENDATIONS

**Warnings (Non-blocking):**
1. Token validation adds API call on every save (rate limit consideration)
2. Exception handling in signal detector could be more specific
3. Logging performance on large org syncs (1000+ repos)

**Suggestions:**
- Add retry logic for transient GitHub API failures
- Improve error context in exception messages
- Optimize batch queries for large organizations
- Consider adding progress websocket for real-time updates

**Production Readiness**: Code is production-ready with current implementation.

## License

DefectDojo is licensed under the BSD-3-Clause License. See LICENSE.md for details.
