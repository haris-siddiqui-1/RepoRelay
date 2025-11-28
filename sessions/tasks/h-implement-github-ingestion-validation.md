---
branch: feature/github-validation
status: active
priority: high
created: 2025-11-27
---

# Task: Implement GitHub Ingestion Validation

**Status**: Active
**Priority**: High (P0 items first)
**Estimated Effort**: 3-5 days (P0 + P1)
**Created**: 2025-11-27
**Branch**: feature/github-validation
**Strategy Doc**: `sessions/docs/github-ingestion-validation-strategy.md`

## Overview

Implement validation mechanisms to ensure users can confidently configure a GitHub PAT and organization name, then successfully ingest all their repository and security alert data into DefectDojo.

## Success Criteria

- [ ] Token scope validation catches missing scopes before sync starts
- [ ] "Test Connection" button validates all 6 checklist items
- [ ] Rate limit pre-check prevents wasted partial syncs
- [ ] Clear error messages with specific remediation steps
- [ ] `validate_github_setup` management command works

## Implementation Plan

### Sprint 1: P0 - Critical Validation (3 days)

#### Task 1.1: Comprehensive Token Validation (1.5 days)
- Add scope validation to configuration save
- Test for: repo, read:org, security_events scopes
- Show specific error messages per missing scope
- Check token expiration via API response

#### Task 1.2: "Test Connection" Button (1.5 days)
- Implement 6-step validation checklist in UI
- Real-time feedback as each step completes
- Visual checklist with pass/fail indicators

### Sprint 2: P1 - Pre-Flight & Commands (2 days)

#### Task 2.1: Rate Limit Pre-Check (0.5 days)
- Check available quota before sync starts
- Warn if GraphQL < 1000 points or REST < 500 calls
- Show reset time if insufficient

#### Task 2.2: validate_github_setup Command (1.5 days)
- Comprehensive pre-flight validation
- Human-readable and JSON output
- Exit codes: 0=pass, 1=warnings, 2=failures

## Technical Details

**Files to Modify:**
- `dojo/github_collector/views.py` - Configuration validation
- `dojo/templates/dojo/github_sync_configuration.html` - Test Connection UI
- `dojo/management/commands/validate_github_setup.py` - NEW

**Key Functions:**
- `validate_token_scopes(token)` - Check all required scopes
- `validate_account_access(token, account_type, account_name)` - Verify org/user exists
- `check_rate_limits(token)` - Get remaining quota

## References

- Strategy: `sessions/docs/github-ingestion-validation-strategy.md`
- Current config: `dojo/github_collector/views.py:github_sync_configuration()`
- Model: `GitHubSyncConfiguration` in `dojo/models.py`

---

## Context Manifest

### How GitHub Sync Configuration Currently Works

**User Entry Point:**

When a staff or superuser navigates to `/github/sync/configuration`, they land on a modern UI template (`dojo/templates/dojo/github_sync_configuration.html`) that presents a configuration form for GitHub repository synchronization. This view is powered by the `github_sync_configuration()` function in `dojo/github_collector/views.py` (lines 58-145).

**Singleton Configuration Pattern:**

DefectDojo uses a singleton pattern for GitHub sync configuration. The `GitHubSyncConfiguration` model (defined at `dojo/models.py:6024-6136`) stores system-wide settings for GitHub integration. Only one configuration record exists per DefectDojo instance, always with `pk=1`. When the view loads, it calls `GitHubSyncConfiguration.objects.get_or_create(pk=1, defaults={...})` to ensure the configuration record exists.

**Current Validation Flow (Token Format Only):**

The existing validation is minimal and happens in `dojo/github_collector/views.py:validate_github_token()` (lines 23-53):

1. **Token Format Check:** Verifies token starts with `ghp_` or `github_pat_` prefix
2. **Basic API Test:** Attempts `GET https://api.github.com/user` to validate token works
3. **Error Handling:** Returns 401 if authentication fails, 403 if permissions missing, but treats other status codes as warnings (doesn't block save)

**Critical Gap - No Scope Validation:**

The current implementation does NOT validate token scopes. It only checks if the token authenticates successfully. This means a token with only `public_repo` scope will pass validation, but syncs will fail later when trying to:
- Access organization repositories (requires `read:org`)
- Fetch security alerts (requires `security_events`)
- Access private repositories (requires `repo`)

**Form Submission Flow:**

When the user submits the configuration form:

1. **POST Action Routing:** The view checks `request.POST.get('action')` to determine the action:
   - `'save_config'` → Update configuration
   - `'trigger_sync'` → Manually trigger sync via `call_command('sync_github_repositories', ...)`

2. **Save Configuration Path** (lines 81-103):
   - Extract form fields: `github_token`, `account_type`, `account_name`, `auto_sync_enabled`, `sync_schedule`, `incremental_sync`
   - Call `validate_github_token()` for format validation
   - Check `account_name` is not empty
   - Save configuration record if validation passes
   - Display success/error message via Django messages framework

3. **Trigger Sync Path** (lines 105-135):
   - Verify token and account name are configured
   - Call `sync_github_repositories` management command with arguments (blocking operation)
   - Update sync status fields: `last_sync`, `last_sync_status`, `last_sync_error`
   - **Known Issue:** This is a blocking HTTP request that will timeout for large organizations (strategy doc GAP PAT-5)

**Data Flow After Configuration:**

Once configured, the GitHub sync pipeline works in three phases:

**Phase 1: Repository Metadata Collection**
- Command: `python manage.py sync_github_repositories --incremental`
- Uses GraphQL API v4 by default (`dojo/github_collector/graphql_client.py`)
- Fetches 47 enrichment fields per repository and stores in `Repository` model
- Each repository linked to a `Product` via ForeignKey
- GraphQL cost: ~30-40 points per repository (vs 18 REST calls in old approach)

**Phase 2: Security Alerts Collection**
- Command: `python manage.py sync_github_alerts --create-findings`
- Collects three types of alerts:
  - Dependabot alerts via GraphQL (`graphql_client.py:get_dependabot_alerts()`)
  - CodeQL alerts via REST API (`rest_client.py:get_codeql_alerts()`)
  - Secret Scanning alerts via REST API (`rest_client.py:get_secret_scanning_alerts()`)
- Stores raw alerts in `GitHubAlert` model with `alert_type` field

**Phase 3: Finding Conversion**
- Handled by `dojo/github_collector/findings_converter.py`
- Converts `GitHubAlert` records to DefectDojo `Finding` objects
- Requires three `Test_Type` records to exist: "GitHub Dependabot", "GitHub CodeQL", "GitHub Secret Scanning"
- Creates one `Engagement` per repository named "GitHub Security Alerts - {repo_name}"
- Creates one `Test` per alert type per engagement
- Uses unique_id_from_tool format: `"github-{alert_type}-{repo_id}-{alert_id}"` for deduplication

**Rate Limit Tracking (Existing Implementation):**

DefectDojo has passive rate limit monitoring but no pre-flight checks:

- **GraphQL:** `graphql_client.py:_log_rate_limit()` (lines 575-589) logs rate limit info from GraphQL responses
  - Each response includes `rateLimit { cost, remaining, resetAt }` fields
  - Warns when `remaining < 500` points
  - Default quota: 5,000 points/hour

- **REST API:** `rest_client.py:_log_rate_limit()` (lines 436-448) logs from response headers
  - Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
  - Warns when `remaining < 100` calls
  - Default quota: 5,000 calls/hour

**Critical Gap - No Pre-Flight Rate Limit Check:**

Neither client has a dedicated method to check rate limits before starting a sync. The system only discovers rate limit exhaustion mid-sync when requests start failing with 403 responses.

### What Needs to Be Built

**For Token Scope Validation (Task 1.1):**

You need to implement a comprehensive token validation function that goes beyond format checking. This function should:

1. **Test Basic Auth:** `GET /user` (validates token works at all)
2. **Test Repo Scope:** `GET /user/repos?per_page=1` (validates `repo` scope)
3. **Test Org Scope:** `GET /orgs/{org}/repos?per_page=1` (validates `read:org` scope)
4. **Test Security Scope:** `GET /repos/{org}/{first_repo}/code-scanning/alerts?per_page=1` (validates `security_events` scope)

Each test should:
- Handle 401 (expired/invalid token) → Block save with clear error
- Handle 403 (missing scope) → Block save with specific scope requirement error
- Handle 404 (repo/org not found) → Accept (might be empty org or no alerts)
- Handle 200 → Mark that scope as validated

**Scope Detection via Headers:**

GitHub REST API returns scope information in response headers:
- `X-OAuth-Scopes`: Scopes the current token has (e.g., "repo, read:org, security_events")
- `X-Accepted-OAuth-Scopes`: Scopes the endpoint accepts

You can parse `X-OAuth-Scopes` from the `/user` response to check all scopes in one call.

**For "Test Connection" Button (Task 1.2):**

You need to add a new AJAX endpoint that performs the 6-step validation checklist:

1. **Frontend:** Add a "Test Connection" button to the configuration form
   - Button triggers AJAX POST to `/api/v2/github_setup/validate/` (new endpoint)
   - Show real-time progress with checkmarks/spinners as each step completes
   - Display results in an expandable checklist panel

2. **Backend:** Create validation endpoint in `dojo/api_v2/views.py`
   - Reuse token scope validation logic from Task 1.1
   - Add organization existence check via `GET /orgs/{name}` or `GET /users/{name}`
   - Add rate limit check via `GET /rate_limit` endpoint
   - Add Test_Type prerequisites check via `Test_Type.objects.filter(name__in=[...]).count()`
   - Add sample repository fetch via GraphQL or REST

3. **Response Format:** Return structured JSON with pass/fail status per check:
   ```json
   {
     "valid": true,
     "ready_to_sync": true,
     "checks": {
       "token_format": {"status": "pass"},
       "token_scopes": {"status": "pass", "scopes": ["repo", "read:org", "security_events"]},
       "account_exists": {"status": "pass", "repository_count": 142},
       "rate_limits": {"status": "pass", "graphql_remaining": 4500, "rest_remaining": 4800},
       "prerequisites": {"status": "pass", "missing_types": []},
       "sample_fetch": {"status": "pass"}
     },
     "warnings": [],
     "errors": []
   }
   ```

**For Rate Limit Pre-Check (Task 2.1):**

GitHub provides a dedicated rate limit endpoint: `GET /rate_limit`

Response structure:
```json
{
  "resources": {
    "core": {
      "limit": 5000,
      "remaining": 4800,
      "reset": 1609459200,
      "used": 200
    },
    "graphql": {
      "limit": 5000,
      "remaining": 4500,
      "reset": 1609459200,
      "used": 500
    }
  }
}
```

Implementation needs:
- Add `get_rate_limits()` method to `rest_client.py`
- Check `graphql.remaining >= 1000` (enough for ~25-30 repos with full metadata fetch)
- Check `core.remaining >= 500` (enough for security alerts on ~250 repos)
- Display reset timestamp if insufficient quota

**For validate_github_setup Command (Task 2.2):**

Create `dojo/management/commands/validate_github_setup.py` following the pattern of `sync_github_repositories.py`:

Structure:
```python
class Command(BaseCommand):
    help = 'Validate GitHub setup before sync'

    def add_arguments(self, parser):
        parser.add_argument('--token', type=str, help='Override token from config')
        parser.add_argument('--org', type=str, help='Override org from config')
        parser.add_argument('--json', action='store_true', help='Output JSON')

    def handle(self, *args, **options):
        # Load config from GitHubSyncConfiguration.objects.get(pk=1)
        # Run all 6 validation checks
        # Print human-readable report or JSON
        # Exit with code: 0=pass, 1=warnings, 2=failures
```

### Technical Reference

**Key Files:**

| File | Purpose | Line Numbers |
|------|---------|--------------|
| `dojo/github_collector/views.py` | Configuration view handler | Lines 58-145 (github_sync_configuration), Lines 23-53 (validate_github_token) |
| `dojo/templates/dojo/github_sync_configuration.html` | Modern UI template | Full template (478 lines) |
| `dojo/models.py` | GitHubSyncConfiguration model | Lines 6024-6136 |
| `dojo/models.py` | Test_Type model | Lines 933-951 |
| `dojo/github_collector/graphql_client.py` | GraphQL API client | Lines 1-669 (entire file) |
| `dojo/github_collector/rest_client.py` | REST API client | Lines 1-448 (entire file) |
| `dojo/github_collector/findings_converter.py` | Alert to Finding conversion | Lines 50-52 (Test_Type constants), Lines 169-173 (Test_Type lookup) |
| `dojo/management/commands/sync_github_repositories.py` | Repository sync command | Lines 1-100 (reference pattern) |

**Required Test_Type Records:**

The findings converter expects these Test_Type records to exist in the database:
- "GitHub Dependabot" (for Dependabot alerts)
- "GitHub CodeQL" (for CodeQL/SAST alerts)
- "GitHub Secret Scanning" (for secret scanning alerts)

If these don't exist, the `_get_or_create_test()` method at `findings_converter.py:169-173` will raise `ValueError("Test_Type not found: {name}")`.

**GitHub API Endpoints Reference:**

| Validation Step | Endpoint | Required Scope | Success Status |
|-----------------|----------|----------------|----------------|
| Token Format | N/A (client-side) | N/A | N/A |
| Basic Auth | `GET /user` | Any valid token | 200 |
| Repo Scope | `GET /user/repos?per_page=1` | `repo` or `public_repo` | 200 |
| Org Scope | `GET /orgs/{org}/repos?per_page=1` | `read:org` | 200 |
| Security Scope | `GET /repos/{owner}/{repo}/code-scanning/alerts?per_page=1` | `security_events` | 200 or 404* |
| Org Exists | `GET /orgs/{name}` or `GET /users/{name}` | Any valid token | 200 |
| Rate Limits | `GET /rate_limit` | Any valid token | 200 |
| Sample Fetch | GraphQL or `GET /orgs/{org}/repos?per_page=1` | `repo`, `read:org` | 200 |

*404 is acceptable for security scope check (means no alerts exist, but scope is valid)

**Rate Limit Thresholds:**

Based on strategy document and existing code patterns:
- **GraphQL:** Minimum 1000 points remaining (enough for ~25-30 full repo syncs)
- **REST API:** Minimum 500 calls remaining (enough for ~250 repo alert fetches)
- **Warning Thresholds:** GraphQL <500, REST <100 (already implemented in _log_rate_limit methods)

**Django Message Framework:**

The existing code uses Django's messages framework for user feedback:
```python
from django.contrib import messages

messages.success(request, 'Configuration saved successfully')
messages.error(request, 'Token validation failed: missing repo scope')
messages.warning(request, 'Rate limit low: 450 points remaining')
```

Messages automatically render in the template via `{% if messages %}` block at line 288.

**Authentication & Permissions:**

The configuration view is protected by two decorators:
- `@login_required` - User must be logged in
- `@user_passes_test(is_staff_or_superuser)` - User must have `is_staff=True` or `is_superuser=True`

This same pattern should apply to any new validation endpoints.

**AJAX Pattern (Modern UI):**

The template uses vanilla JavaScript (no jQuery) for AJAX calls. For the "Test Connection" button, you'll need:

1. Add button to template with onclick handler
2. JavaScript function that POSTs to validation endpoint
3. Update UI with spinner during validation
4. Render checklist with results (green checkmarks or red X's)
5. Show error messages with specific remediation guidance

Example pattern from `dojo/static/dojo/js/github_insights_dashboard.js`:
```javascript
async function testConnection() {
    const response = await fetch('/api/v2/github_setup/validate/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            token: document.getElementById('github_token').value,
            account_type: document.querySelector('input[name="account_type"]:checked').value,
            account_name: document.getElementById('account_name').value
        })
    });
    const data = await response.json();
    renderChecklist(data.checks);
}
```

### Environmental Requirements

**Django Settings:**

The following settings control GitHub integration behavior (from `dojo/settings/settings.dist.py`):
- `DD_GITHUB_TOKEN` - Default GitHub PAT (overridden by GitHubSyncConfiguration)
- `DD_GITHUB_ORG` - Default organization name (overridden by GitHubSyncConfiguration)

**Database Requirements:**

- PostgreSQL database with migrations applied
- Test_Type records must exist for GitHub alert types (usually created via data migration or fixture)

**Python Dependencies:**

- `requests` (already installed) - For HTTP/HTTPS API calls
- `PyGithub` (already installed) - For legacy GitHub issue integration (not used by new sync system)

**External Dependencies:**

- GitHub API v4 (GraphQL) endpoint: `https://api.github.com/graphql`
- GitHub API v3 (REST) endpoint: `https://api.github.com`
- Valid GitHub PAT with appropriate scopes

**Token Scope Requirements (Complete List):**

| Scope | Required For | Alternative |
|-------|--------------|-------------|
| `repo` | Private repo access, full repo metadata | `public_repo` (public repos only) |
| `read:org` | Organization repo listing, org metadata | N/A (required for orgs) |
| `security_events` | Dependabot, CodeQL, Secret Scanning alerts | N/A (required for alerts) |
| `admin:repo_hook` | Webhook health monitoring (optional) | Graceful fallback if missing |

### Implementation Guidance

**Start with Task 1.1 (Token Validation):**

1. Create new function `validate_token_scopes(token, account_type, account_name)` in `views.py`
2. Use `requests` library to call GitHub API endpoints
3. Parse `X-OAuth-Scopes` header from `/user` response to get all scopes
4. Check for presence of `repo` (or `public_repo`), `read:org`, `security_events`
5. Return structured dict: `{'valid': bool, 'scopes': list, 'missing_scopes': list, 'error': str}`
6. Integrate into existing `validate_github_token()` function or replace it

**Then Task 1.2 (Test Connection Button):**

1. Add API endpoint in `dojo/api_v2/views.py` - create `GitHubSetupValidationViewSet`
2. Add URL route in `dojo/api_v2/urls.py`
3. Update template to add "Test Connection" button
4. Add JavaScript to handle button click and render results
5. Use modern UI design system colors (violet accent #8B5CF6, soft dark backgrounds)

**Reusable Validation Logic:**

Create a shared validation module that both the web UI and management command can use:
```
dojo/github_collector/validator.py
  - validate_token_format(token)
  - validate_token_scopes(token, account_type, account_name)
  - validate_account_exists(token, account_type, account_name)
  - check_rate_limits(token)
  - check_test_type_prerequisites()
  - validate_sample_fetch(token, account_type, account_name)
  - validate_full_setup(token, account_type, account_name) -> ValidationResult
```

This keeps the view logic thin and makes testing easier.

**Error Message Templates:**

Use clear, actionable error messages that match the strategy document:

| Error Code | Message | Remediation |
|------------|---------|-------------|
| TOKEN_INVALID_FORMAT | "Token must start with 'ghp_' or 'github_pat_'" | "Generate a new token at https://github.com/settings/tokens" |
| TOKEN_EXPIRED | "Token has expired or been revoked" | "Generate a new token at https://github.com/settings/tokens" |
| TOKEN_MISSING_SCOPE_REPO | "Token missing 'repo' scope" | "Regenerate token with 'repo' scope selected" |
| TOKEN_MISSING_SCOPE_ORG | "Token missing 'read:org' scope" | "Regenerate token with 'read:org' scope selected" |
| TOKEN_MISSING_SCOPE_SECURITY | "Token missing 'security_events' scope" | "Regenerate token with 'security_events' scope selected" |
| ACCOUNT_NOT_FOUND | "Organization '{name}' not found or not accessible" | "Verify organization name spelling and token access" |
| RATE_LIMIT_EXHAUSTED | "API quota depleted. Resets at {reset_time}" | "Wait for rate limit reset or use different token" |
| PREREQUISITE_MISSING | "Database missing required Test_Types" | "Run: python manage.py migrate" |

**Testing Strategy:**

1. **Manual Testing:** Use your own GitHub PAT and organization for end-to-end validation
2. **Token Scope Testing:** Create test tokens with missing scopes to verify error handling
3. **Rate Limit Testing:** Hard to test without actually exhausting quota - use mock responses
4. **Invalid Org Testing:** Use non-existent org name "this-org-definitely-does-not-exist-12345"

**Success Criteria Checklist:**

- [ ] Token validation rejects tokens missing any required scope with specific error message
- [ ] "Test Connection" button shows 6 checkmarks on successful validation
- [ ] "Test Connection" button shows specific failure reason with remediation guidance
- [ ] Rate limit check prevents sync start when GraphQL <1000 or REST <500
- [ ] `validate_github_setup` command outputs human-readable report
- [ ] `validate_github_setup --json` outputs structured JSON
- [ ] Management command exits with code 0 (pass), 1 (warnings), or 2 (failures)
- [ ] All validation logic is reusable between web UI and CLI command

---

## Work Log

### 2025-11-27 - Task Created
- Created implementation task from strategy document
- Focus on P0 items: token validation + test connection button

### 2025-11-27 - Context Manifest Complete
- Comprehensive context gathered covering:
  - Current GitHub sync configuration flow (singleton pattern, form submission, validation)
  - Three-phase data pipeline (repository metadata → security alerts → findings conversion)
  - Rate limit tracking (passive logging, no pre-flight checks)
  - Token scope requirements and validation gaps
  - Test_Type prerequisites for findings conversion
  - Technical reference with file locations and line numbers
  - Implementation guidance with reusable validation module pattern
  - Error message templates and testing strategy
- Ready for implementation mode
