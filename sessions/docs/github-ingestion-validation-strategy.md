# GitHub Ingestion Validation Strategy

**Document Version:** 1.0  
**Created:** 2025-11-26  
**Status:** Final  
**Task Reference:** `sessions/tasks/h-research-github-ingestion-validation-strategy.md`

---

## Executive Summary

This document provides a comprehensive validation strategy to ensure users can confidently configure a GitHub Personal Access Token (PAT) and organization name, then successfully ingest all their repository and security alert data into DefectDojo.

**Core Assurance Goals:**
1. A user provides PAT + org name → all data ingests successfully
2. Real production data (not test fixtures) powers all metrics and dashboards
3. End-to-end pipeline validation from GitHub API → DefectDojo models → Insights Dashboard

---

## 1. Current Data Flow

### 1.1 PAT Configuration Flow

```
User → /github/sync/configuration → GitHubSyncConfiguration model (singleton)
                                          ↓
                               Token Format Validation (ghp_ or github_pat_)
                                          ↓
                               API Connectivity Test (GET /user)
                                          ↓
                               Save Configuration (plaintext storage)
```

**Entry Point:** `/github/sync/configuration` (staff/superuser only)  
**View:** `dojo/github_collector/views.py:github_sync_configuration()` (lines 58-145)  
**Model:** `GitHubSyncConfiguration` singleton at `dojo/models.py:6024-6136`

### 1.2 Data Ingestion Pipeline

| Phase | Component | Output |
|-------|-----------|--------|
| 1 | `sync_github_repositories` | Repository model (47 enrichment fields) |
| 2 | `sync_github_alerts` | GitHubAlert model (Dependabot, CodeQL, Secret Scanning) |
| 3 | `--create-findings` flag | Finding model with deduplication |
| 4 | `/github/insights/dashboard` | Chart.js visualizations |

### 1.3 Key Relationships

```
Product ←── Repository (github_repo_id unique)
   └── Engagement ←── Test ←── Finding (unique_id_from_tool)
                                    ↑
GitHubAlert ─────────────────────────┘
```

---

## 2. Identified Validation Gaps

### 2.1 PAT Configuration Gaps (Critical)

| ID | Gap | Severity | Risk |
|----|-----|----------|------|
| PAT-1 | No scope validation | Critical | Sync fails mid-process |
| PAT-2 | No expiration check | High | Partial data, wasted API calls |
| PAT-3 | Plaintext token storage | High | Security vulnerability |
| PAT-4 | No org existence check | Medium | Poor UX |
| PAT-5 | Blocking sync trigger | Medium | Timeouts for large orgs |

### 2.2 Data Pipeline Gaps

| ID | Gap | Severity | Risk |
|----|-----|----------|------|
| PIPE-1 | No rate limit pre-check | High | Wasted time, partial sync |
| PIPE-2 | No transaction wrapper | High | Orphaned records |
| PIPE-3 | Partial success = success | Medium | False confidence |
| PIPE-4 | No orphan detection | Medium | Data integrity issues |
| PIPE-5 | No Test_Type validation | Medium | Cryptic errors |

### 2.3 Insights Dashboard Gaps

| ID | Gap | Severity | Risk |
|----|-----|----------|------|
| DASH-1 | No empty data handling | Medium | Confusing UX |
| DASH-2 | No error boundaries | Medium | Dashboard breaks entirely |
| DASH-3 | No stale data indicator | Low | Misleading metrics |
| DASH-4 | Test data not filtered | Low | Polluted dashboards |

---

## 3. First-Time Setup Validation Checklist Spec

### 3.1 Validation Flow (6 Steps)

```
Step 1: Token Format Validation
    ↓ [PASS]
Step 2: Token Scope Validation  ← NEW
    ↓ [PASS]
Step 3: Organization/User Existence  ← NEW
    ↓ [PASS]
Step 4: Rate Limit Availability Check  ← NEW
    ↓ [PASS]
Step 5: Test_Type Prerequisites Check  ← NEW
    ↓ [PASS]
Step 6: Sample Repository Fetch Test  ← NEW
    ↓ [PASS]
Configuration Saved → Ready to Sync
```

### 3.2 Step Specifications

#### Step 1: Token Format Validation
- **Check:** Token starts with `ghp_` or `github_pat_`, length 40-255 chars
- **Fail Messages:** "Token must start with 'ghp_' or 'github_pat_'"

#### Step 2: Token Scope Validation (NEW)
- **API Calls:**
  - `GET /user` → 200 OK (basic auth)
  - `GET /user/repos?per_page=1` → 200 OK (repo scope)
  - `GET /orgs/{org}/repos?per_page=1` → 200 OK (read:org scope)
  - `GET /repos/{org}/{repo}/code-scanning/alerts?per_page=1` → 200/404 (security_events)
- **Fail Messages:**
  - 401: "Token is invalid or expired"
  - 403 on repos: "Token lacks 'repo' scope"
  - 403 on orgs: "Token lacks 'read:org' scope"
  - 403 on alerts: "Token lacks 'security_events' scope"

#### Step 3: Organization Existence (NEW)
- **API Call:** `GET /orgs/{name}` or `GET /users/{name}`
- **Fail Messages:**
  - 404: "Organization '{name}' not found on GitHub"
  - 403: "You don't have access to organization '{name}'"

#### Step 4: Rate Limit Check (NEW)
- **API Call:** `GET /rate_limit`
- **Pass Criteria:** GraphQL ≥ 1000 points, REST ≥ 500 calls
- **Fail Message:** "Insufficient API quota. Resets at {time}."

#### Step 5: Test_Type Prerequisites (NEW)
- **DB Check:** Verify existence of "GitHub Dependabot", "GitHub CodeQL", "GitHub Secret Scanning"
- **Fail Message:** "Database missing required test types. Run: python manage.py migrate"

#### Step 6: Sample Repository Fetch (NEW)
- **GraphQL Query:** Fetch first repository from org
- **Pass Criteria:** Valid response structure (empty array acceptable for new orgs)

### 3.3 UI Mockup

```
┌─────────────────────────────────────────────────────────────────┐
│  GitHub Integration Setup                                        │
├─────────────────────────────────────────────────────────────────┤
│  Personal Access Token: [ghp_xxx...] ✓                          │
│  Account Type: ○ Organization  ● Personal                        │
│  Account Name: [my-github-org] ✓                                 │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Validation Checklist                                    │    │
│  │  ✓ Token format valid                                    │    │
│  │  ✓ Token scopes verified (repo, read:org, security)     │    │
│  │  ✓ Organization accessible (142 repositories)           │    │
│  │  ✓ Rate limit available (4,500 / 5,000)                 │    │
│  │  ✓ Database prerequisites met                            │    │
│  │  ✓ Sample fetch successful                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  [Save Config]  [Save & Start Initial Sync]                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Automated Smoke Test Suite Spec

### 4.1 Management Command: `validate_github_setup`

**Purpose:** Pre-flight validation before sync  
**Location:** `dojo/management/commands/validate_github_setup.py`

```bash
# Basic usage
python manage.py validate_github_setup

# With explicit credentials
python manage.py validate_github_setup --token ghp_xxx --org my-org

# JSON output for CI/CD
python manage.py validate_github_setup --json
```

**Output (Human):**
```
GitHub Integration Validation Report
=====================================
Token Validation
  ✓ Format: Valid (ghp_* prefix)
  ✓ Scopes: repo, read:org, security_events

Account Validation
  ✓ Organization 'my-org' exists (142 repositories)

Rate Limits
  ✓ GraphQL: 4,500 / 5,000 remaining (90%)
  ✓ REST: 4,800 / 5,000 remaining (96%)

Prerequisites
  ✓ Test_Type 'GitHub Dependabot' exists
  ✓ Test_Type 'GitHub CodeQL' exists
  ✓ Test_Type 'GitHub Secret Scanning' exists

Sample Fetch
  ✓ Successfully fetched repository metadata
=====================================
Status: READY TO SYNC
```

**Exit Codes:** 0 = pass, 1 = warnings, 2 = failures

### 4.2 Management Command: `smoke_test_github_pipeline`

**Purpose:** End-to-end pipeline validation  
**Location:** `dojo/management/commands/smoke_test_github_pipeline.py`

```bash
python manage.py smoke_test_github_pipeline --repository owner/repo --cleanup
```

**Test Phases:**

| Phase | Test | Pass Criteria |
|-------|------|---------------|
| 1 | Repository Sync | Repository record created with github_repo_id |
| 2 | Alert Collection | GitHubAlert records created (or 0 if none) |
| 3 | Finding Conversion | Finding records with unique_id_from_tool |
| 4 | Insights Query | Security insight returns data for repository |

### 4.3 API Endpoints

#### `POST /api/v2/github_setup/validate/`

**Request:**
```json
{
    "token": "ghp_xxxx",
    "account_type": "organization",
    "account_name": "my-org"
}
```

**Response:**
```json
{
    "valid": true,
    "ready_to_sync": true,
    "checks": {
        "token_format": {"status": "pass"},
        "token_scopes": {"status": "pass", "scopes": ["repo", "read:org"]},
        "account_exists": {"status": "pass", "repository_count": 142},
        "rate_limits": {"status": "pass", "graphql_remaining": 4500},
        "prerequisites": {"status": "pass"},
        "sample_fetch": {"status": "pass"}
    },
    "warnings": [],
    "errors": []
}
```

#### `GET /api/v2/github_setup/health/`

**Response:**
```json
{
    "configured": true,
    "account_name": "my-org",
    "last_sync": "2025-01-15T10:30:00Z",
    "last_sync_status": "success",
    "rate_limits": {
        "graphql": {"remaining": 4500, "limit": 5000},
        "rest": {"remaining": 4800, "limit": 5000}
    },
    "statistics": {
        "repository_count": 142,
        "alert_count": 1523,
        "finding_count": 1456
    }
}
```

---

## 5. User-Facing Validation Feedback Mechanisms

### 5.1 Sync Status Widget States

| State | Visual | Information |
|-------|--------|-------------|
| Not Configured | Gray | "GitHub integration not configured" + setup link |
| Ready | Green | Last sync, repo/alert counts |
| Syncing | Blue + spinner | Progress bar, current phase |
| Warning | Amber | Partial success details |
| Error | Red | Error message + retry button |

### 5.2 Real-Time Sync Progress (Polling)

```javascript
async function pollSyncStatus() {
    const data = await fetch('/api/v2/github_setup/health/').then(r => r.json());
    updateUI(data);
    if (data.sync_in_progress) setTimeout(pollSyncStatus, 2000);
}
```

### 5.3 Insights Empty/Error States

**Empty State:** "No data available. Run GitHub sync with --create-findings."  
**Error State:** "Unable to load insight. Error: {message}. [Retry]"

### 5.4 Stale Data Indicator

| Cache Age | Color | Action |
|-----------|-------|--------|
| < 1 min | Green (Fresh) | None |
| 1-5 min | Blue (Recent) | None |
| 5-15 min | Amber (Stale) | Show refresh button |
| > 15 min | Red (Outdated) | Show refresh button |

---

## 6. Test Data vs Production Data Separation

### 6.1 Problem

DefectDojo has no `data_classification` field. Test fixtures can appear in production dashboards.

### 6.2 Solution

**Add field to Product model:**
```python
data_classification = models.CharField(
    max_length=20,
    choices=[('production', 'Production'), ('test', 'Test/Demo')],
    default='production'
)
```

**Filter insights:**
```python
qs = Repository.objects.exclude(product__data_classification='test')
```

**Update fixtures:** Set `data_classification='test'` in all fixture files.

---

## 7. Implementation Task Recommendations

### 7.1 Priority Matrix

| Priority | Tasks | Effort | Impact |
|----------|-------|--------|--------|
| **P0** | Token scope validation, async sync | 2-3 days | Critical |
| **P1** | Pre-flight, transaction wrapper, partial success | 3-5 days | High |
| **P2** | Management commands, API endpoints | 2-3 days | Medium |
| **P3** | UI feedback, empty states, data classification | 3-5 days | Medium |

### 7.2 Sprint Plan

**Sprint 1 (P0):** 3 days
- Task 1.1: Comprehensive token validation (1.5 days)
- Task 1.2: Async sync trigger via Celery (1.5 days)

**Sprint 2 (P1):** 4.5 days
- Task 2.1: Pre-flight validation (1 day)
- Task 2.2: Transaction-wrapped sync (2 days)
- Task 2.3: Partial success tracking (1.5 days)

**Sprint 3 (P2):** 3.5 days
- Task 3.1: `validate_github_setup` command (1 day)
- Task 3.2: `smoke_test_github_pipeline` command (1.5 days)
- Task 3.3: API endpoints (1 day)

**Sprint 4 (P3):** 4 days
- Task 4.1: Sync status widget (1.5 days)
- Task 4.2: Empty/error states (1 day)
- Task 4.3: Data classification field (1.5 days)

### 7.3 Success Metrics

| Metric | Target |
|--------|--------|
| First-time setup success rate | > 95% |
| Time to first successful sync | < 10 minutes |
| Sync error clarity | 100% actionable |
| Pipeline reliability | > 99% |
| Data integrity | 100% |

---

## Appendix: Error Codes

| Code | Message | Remediation |
|------|---------|-------------|
| `TOKEN_INVALID_FORMAT` | Token format not recognized | Use ghp_* or github_pat_* |
| `TOKEN_EXPIRED` | Token has expired | Generate new token |
| `TOKEN_MISSING_SCOPE_REPO` | Missing 'repo' scope | Regenerate with 'repo' |
| `TOKEN_MISSING_SCOPE_ORG` | Missing 'read:org' scope | Regenerate with 'read:org' |
| `TOKEN_MISSING_SCOPE_SECURITY` | Missing 'security_events' | Regenerate with scope |
| `ACCOUNT_NOT_FOUND` | Org/user not found | Check spelling |
| `RATE_LIMIT_EXHAUSTED` | API quota depleted | Wait for reset |
| `PREREQUISITE_MISSING` | DB prerequisites missing | Run migrate |

---

*Document generated as part of task h-research-github-ingestion-validation-strategy*
