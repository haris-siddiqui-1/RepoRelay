# GitHub Collector Module

The GitHub Collector is DefectDojo's comprehensive integration system for GitHub repository management, security monitoring, and analytics.

## Overview

This module provides five major subsystems for GitHub integration:

1. **Setup Validation** - Pre-flight checks for token scopes, rate limits, and prerequisites
2. **Repository Metadata Enrichment** - GraphQL-powered collector for repository context
3. **Security Alerts Collection** - Automated sync of GitHub security alerts to DefectDojo Findings
4. **Insights Dashboard** - Widget-based analytics with 25 built-in insights
5. **Product Migration Wizard** - Hierarchical clustering for repository-to-product consolidation

## Architecture

```
dojo/github_collector/
├── validator.py              # GitHub setup validation (6 checks)
├── collector.py              # Main repository metadata collector (GraphQL + REST)
├── graphql_client.py         # GitHub GraphQL API v4 client
├── rest_client.py            # GitHub REST API v3 client (fallback)
├── alerts_collector.py       # Security alerts synchronization
├── findings_converter.py     # Convert GitHub alerts to DefectDojo Findings
├── clustering.py             # Hierarchical clustering for product migration
├── signal_detector.py        # Binary signal detection (36 signals)
├── tier_classifier.py        # Repository tier/criticality classification
├── readme_summarizer.py      # README summarization with LLM
├── insights/                 # Insights dashboard subsystem
│   ├── base.py              # BaseInsight abstract class
│   ├── registry.py          # InsightRegistry auto-discovery
│   ├── activity.py          # Activity insights (5)
│   ├── health.py            # Health insights (5)
│   ├── security.py          # Security insights (7)
│   ├── ownership.py         # Ownership insights (4)
│   ├── technology.py        # Technology insights (4)
│   └── views.py             # Dashboard view handler
├── queries/                  # GraphQL query templates
│   ├── repository_full.graphql
│   └── organization_batch.graphql
├── views.py                  # Web UI views (configuration, test connection)
└── urls.py                   # URL routing for insights dashboard and validation
```

## 1. Setup Validation

**Purpose**: Validate GitHub configuration before attempting sync operations to prevent wasted API quota and ensure successful data ingestion.

**Features**:
- **6-Step Validation Checklist**:
  1. Token format validation (ghp_* or github_pat_*)
  2. Token scope verification via X-OAuth-Scopes header (repo, read:org, security_events)
  3. Organization/user existence and accessibility check
  4. Rate limit availability (GraphQL ≥1000 points, REST ≥500 calls)
  5. Database prerequisites (Test_Type records for Dependabot, CodeQL, Secret Scanning)
  6. Sample repository fetch test (end-to-end API access)
- **Web UI**: "Test Connection" button at `/github/sync/configuration` with real-time progress feedback
- **Management Command**: `validate_github_setup` for CI/CD integration
- **Exit Codes**: 0=pass, 1=warnings, 2=failures
- **Output Formats**: Human-readable report or JSON

**Management Command**:
```bash
# Basic validation using configured token
python manage.py validate_github_setup

# Override token and organization
python manage.py validate_github_setup --token ghp_xxx --org myorg

# JSON output for CI/CD pipelines
python manage.py validate_github_setup --json
```

**Example Output**:
```
GitHub Integration Validation Report
==================================================

Token Validation
  ✓ Format: Token format valid
  ✓ Scopes: repo, read:org, security_events

Account Validation
  ✓ Account 'myorg' exists (142 repositories)

Rate Limits
  ✓ GraphQL: 4,500 / 5,000 remaining (90%)
  ✓ REST: 4,800 / 5,000 remaining (96%)

Prerequisites
  ✓ Test_Type 'GitHub Dependabot' exists
  ✓ Test_Type 'GitHub CodeQL' exists
  ✓ Test_Type 'GitHub Secret Scanning' exists

Sample Fetch
  ✓ Successfully fetched: myorg/example-repo

==================================================
Status: READY TO SYNC
```

**Error Messages and Remediation**:

| Error | Remediation |
|-------|-------------|
| Token missing 'repo' scope | Regenerate token with 'repo' scope selected |
| Token missing 'read:org' scope | Regenerate token with 'read:org' scope selected |
| Token missing 'security_events' scope | Regenerate token with 'security_events' scope selected |
| Organization not found | Verify organization name spelling and token access |
| Rate limit exhausted | Wait for rate limit reset or use different token |
| Test_Type missing | Run: python manage.py migrate |

**Web UI Endpoint**:
- **URL**: `/github/sync/test-connection` (POST endpoint, AJAX)
- **Request Body**: `{"token": "...", "account_type": "organization", "account_name": "myorg"}`
- **Response Format**:
```json
{
  "valid": true,
  "ready_to_sync": true,
  "checks": {
    "token_format": {"status": "pass", "message": "Token format valid"},
    "token_scopes": {"status": "pass", "scopes": ["repo", "read:org", "security_events"]},
    "account_exists": {"status": "pass", "repository_count": 142},
    "rate_limits": {"status": "pass", "graphql_remaining": 4500, "rest_remaining": 4800},
    "prerequisites": {"status": "pass", "all_present": true},
    "sample_fetch": {"status": "pass", "sample_repo": "myorg/example-repo"}
  },
  "warnings": [],
  "errors": []
}
```

**Validator Class** (`dojo/github_collector/validator.py`):
- `GitHubValidator(token, account_type, account_name)` - Main validation orchestrator
- `validate_token_format()` - Step 1: Format check
- `validate_token_scopes()` - Step 2: Scope detection via API headers
- `validate_account_exists()` - Step 3: Organization/user existence
- `check_rate_limits()` - Step 4: Available API quota
- `check_test_type_prerequisites()` - Step 5: Database prerequisites
- `validate_sample_fetch()` - Step 6: Sample repository fetch
- `validate_full_setup()` - Run all checks, return ValidationResult
- `to_dict()` - Convert ValidationResult to JSON-serializable dict

**Required Scopes**:
- `repo` - Full control of private repositories (or `public_repo` for public only)
- `read:org` - Read org and team membership
- `security_events` - Read security events (Dependabot, CodeQL, Secret Scanning alerts)

**Rate Limit Thresholds**:
- GraphQL minimum: 1,000 points (enough for ~25-30 full repository syncs)
- REST minimum: 500 calls (enough for ~250 repository alert fetches)
- Warning thresholds: GraphQL <500 points, REST <100 calls

**Use Cases**:
1. **Initial Setup**: Validate configuration before first sync attempt
2. **Troubleshooting**: Diagnose sync failures with specific error messages
3. **CI/CD Integration**: Automated validation in deployment pipelines with JSON output
4. **Token Rotation**: Verify new token has correct scopes before replacing old token
5. **Monitoring**: Proactive rate limit checks before scheduled syncs

## 2. Repository Metadata Enrichment

**Purpose**: Sync GitHub repository metadata to DefectDojo's Repository model with 47 enrichment fields.

**Features**:
- GraphQL API v4 for bulk operations (15-20x faster incremental syncs)
- Automatic REST API fallback for reliability
- **Partial Dual-Population Strategy**: Activity metrics (commit_count, open_issues_count, open_pr_count) sync to both Repository model (primary) and Product model (legacy compatibility). Webhook health fields are Repository-only.
- Incremental sync (only fetch repositories updated since last sync)
- 36 binary signals across 5 categories (deployment, production, development, organization, security)
- Repository tier/criticality classification (tier1-tier4, archived)
- **Activity Metrics**: commit_count, open_issues_count, open_pr_count (added November 2025)
- **Webhook Health Monitoring**: Detects webhook types, cadence, active count with graceful permission fallback (added November 2025)
- **XSS Sanitization**: All external GitHub data (README summaries, CODEOWNERS) sanitized with bleach.clean() before storage
- Rate limit monitoring (5,000 points/hour quota)
- **Web UI Configuration**: `/github/sync/configuration` for token management and manual sync
- **Progress Tracking**: Logs progress every 10 repositories during sync operations

**Management Command**:
```bash
python manage.py sync_github_repositories --incremental
```

**Web UI**: Navigate to `/github/sync/configuration` (staff/superuser only) for:
- GitHub token configuration with validation
- Account type selection (Organization or Personal Account)
- Auto-sync settings and schedule configuration
- Manual sync trigger with real-time status feedback

**Documentation**:
- Implementation details: [README_GRAPHQL.md](./README_GRAPHQL.md) and [GRAPHQL_VERIFICATION.md](./GRAPHQL_VERIFICATION.md)
- Web UI guide: [README_SYNC_UI.md](./README_SYNC_UI.md)

## 3. Security Alerts Collection

**Purpose**: Fetch and sync GitHub security alerts (Dependabot, CodeQL, Secret Scanning) to DefectDojo Findings.

**Features**:
- Three alert types: Dependabot, CodeQL, Secret Scanning
- Automatic deduplication using `unique_id_from_tool` format: `github-{type}-{repo_id}-{alert_id}`
- Bidirectional state synchronization (open/dismissed/fixed)
- Incremental sync with rate limit management
- Automatic Test creation per alert type
- Finding lifecycle management (create, update, close)

**Management Commands**:
```bash
# Sync alerts only (no Finding creation)
python manage.py sync_github_alerts

# Sync alerts and create/update Findings
python manage.py sync_github_alerts --create-findings

# Force full sync (ignores last sync timestamp)
python manage.py sync_github_alerts --force --create-findings

# Sync specific repository
python manage.py sync_github_alerts --repository-id 123 --create-findings

# Dry run (preview without changes)
python manage.py sync_github_alerts --dry-run
```

**Documentation**: See [README_ALERTS.md](./README_ALERTS.md)

## 4. Insights Dashboard

**Purpose**: Provide repository management analytics through a configurable widget-based UI.

**Features**:
- 25 built-in insights across 5 categories (Activity, Health, Security, Ownership, Technology)
- Pluggable architecture (BaseInsight + InsightRegistry pattern)
- User-specific dashboard configuration (GitHubInsightConfiguration model)
- Chart.js 4.4.0 visualizations (pie, bar, line, scatter, histogram)
- REST API: `/api/v2/github_insights/`
- Web UI: `/github/insights/dashboard`
- 5-minute caching with hash-based cache keys
- Pinned widgets with auto-refresh (60-second intervals)

**Management Commands**:
```bash
# List all available insights
python manage.py generate_insights --list

# Generate specific insight
python manage.py generate_insights --insight vuln_distribution

# Generate all insights in a category
python manage.py generate_insights --category security --output json

# Generate all insights with filters
python manage.py generate_insights --all --days 30 --product-type-id 5
```

**Insight Categories**:
- **Activity** (5 insights): Most updated repos, stale repos, commit frequency, active contributors, recently created
- **Health** (5 insights): Missing README, missing CI/CD, old PRs, high issue count, stale repos
- **Security** (7 insights): Vulnerability distribution, severity trends, correlations, finding age analysis
- **Ownership** (4 insights): Unassigned repos, multiple owners, orphaned repos, department distribution
- **Technology** (4 insights): Popular languages, Docker adoption, Kubernetes usage, framework adoption

**Documentation**: See [README_INSIGHTS.md](./README_INSIGHTS.md)

## 5. Dependency Graph Analysis

**Purpose**: Analyze GitHub SBOM data to identify internal dependency relationships and solve the "abandoned vs stable repository" problem.

**Features**:
- Uses GitHub SBOM API for dependency analysis
- Tracks `dependent_repo_count`, `downstream_consumers`, `is_shared_library`
- Computes `consumption_tier_override` based on consumption thresholds
- Solves "abandoned vs stable" problem: High-consumption repos stay prioritized

**Management Command**:
```bash
python manage.py build_dependency_graph --verbose
```

**Documentation**: See [README_DEPENDENCY_GRAPH.md](./README_DEPENDENCY_GRAPH.md)

## 6. Product Migration Wizard

**Purpose**: Migrate from "1 Product per Repository" to "1 Product per Application" using hierarchical clustering.

**Features**:
- Hierarchical clustering to suggest logical repository groupings
- Preserves Finding → Test → Engagement → Product relationship chain
- Migrates Engagements along with Repositories to prevent Finding orphaning
- Transaction-safe operations with rollback capability
- Detailed migration reports with validation

**Management Command**:
```bash
python manage.py migrate_products_to_repositories
```

**Documentation**: See [PHASE4_VALIDATION_REPORT.md](../../PHASE4_VALIDATION_REPORT.md)

## Data Models

### Repository Model
Represents a GitHub repository with enrichment metadata (47 fields):
- Core: `name`, `github_repo_id`, `github_url`, `product` (ForeignKey)
- Activity: `last_commit_date`, `active_contributors_90d`, `days_since_last_commit`
- **Activity Metrics** (November 2025): `commit_count`, `open_issues_count`, `open_pr_count`
- **Webhook Health** (November 2025): `has_webhooks`, `active_webhooks_count`, `webhook_cadence`, `webhook_types` (JSONField)
- Metadata: `readme_summary` (XSS sanitized), `primary_language`, `primary_framework`
- Ownership: `codeowners_content` (XSS sanitized), `ownership_confidence`
- 36 binary signals (has_dockerfile, has_ci_cd, has_kubernetes, etc.)
- Alert metadata: `dependabot_alert_count`, `codeql_alert_count`, `secret_scanning_alert_count`
- Tier: `tier` (tier1, tier2, tier3, tier4, archived)

### GitHubAlert Model
Stores raw GitHub security alerts:
- Core: `repository` (ForeignKey), `alert_type`, `github_alert_id`, `state`, `severity`
- Content: `title`, `description`, `html_url`
- Type-specific: `cve`, `package_name`, `cwe`, `rule_id`, `file_path`, `secret_type`
- Raw data: `raw_data` (JSONField)
- Finding link: `finding` (ForeignKey)

### GitHubAlertSync Model
Tracks alert sync status per repository:
- Sync timestamps: `dependabot_last_sync`, `codeql_last_sync`, `secret_scanning_last_sync`
- Statistics: alerts fetched counts per type
- Error tracking: `last_sync_error`, `last_rate_limit_hit`

### GitHubInsightConfiguration Model
User-specific dashboard configuration:
- OneToOne with User
- `widget_config` (JSONField): Array of widget configurations
- `widget_count` (IntegerField): Number of widgets to display (default: 10)
- Pinned widgets bypass widget_count limit

## API Endpoints

### Repository Metadata
- GraphQL queries via `graphql_client.py`
- REST fallback via `rest_client.py`

### Security Alerts
- GitHub REST API v3 (alerts endpoints)
- Incremental sync using last_sync timestamps

### Insights Dashboard
- `GET /api/v2/github_insights/` - List available insights
- `GET /api/v2/github_insights/{insight_id}/` - Calculate insight
- `GET /api/v2/github_insights/dashboard/` - Get user configuration
- `POST /api/v2/github_insights/dashboard/` - Update configuration

## Performance Characteristics

### Repository Sync
- Initial full sync: <24 hours (one-time, 2,451 repos)
- Daily incremental sync: <5 minutes (50-100 changed repos)
- Single repository sync: <1 second

### Alerts Sync
- Incremental sync: <5 minutes per repository
- Rate limit: 5,000 requests/hour (REST API)

### Insights Dashboard
- Insight calculation: <2 seconds per insight
- Dashboard load: <5 seconds for 15 widgets (with cache)
- Cache TTL: 300 seconds (5 minutes), 60 seconds for pinned widgets

## Configuration

All GitHub integration requires:
- `DD_GITHUB_TOKEN` - GitHub Personal Access Token with required scopes:
  - `repo` - Full control of private repositories
  - `read:org` - Read org and team membership
  - `security_events` - Read security events (alerts)

**Validation**: Before first sync, run `python manage.py validate_github_setup` to verify token scopes, rate limits, and prerequisites. See [Section 1: Setup Validation](#1-setup-validation) for details.

## Testing

```bash
# Validate GitHub setup (recommended first step)
python manage.py validate_github_setup
python manage.py validate_github_setup --json

# Test GraphQL client
python dojo/github_collector/test_graphql.py

# Test insights system
python manage.py generate_insights --list
python manage.py generate_insights --insight vuln_distribution

# Dry run alerts sync
python manage.py sync_github_alerts --dry-run
```

## Troubleshooting

### Rate Limits
- GraphQL: 5,000 points/hour
- REST: 5,000 requests/hour
- Secondary rate limits apply (undocumented thresholds)

### Common Issues
1. **Missing GitHub token**: Set `DD_GITHUB_TOKEN` environment variable or configure via `/github/sync/configuration`
2. **Invalid token scopes**: Run `python manage.py validate_github_setup` to identify missing scopes
3. **Rate limit exceeded**: Run `python manage.py validate_github_setup` to check available quota before sync
4. **Missing Test_Type records**: Run `python manage.py migrate` to create required database prerequisites
5. **Organization not found**: Verify organization name spelling and token access permissions
6. **GraphQL query too complex**: Reduce batch size or use REST fallback
7. **Insight calculation timeout**: Optimize queries or increase cache TTL

**Debugging Tip**: Always run `python manage.py validate_github_setup` first when troubleshooting sync issues. It provides specific error messages and remediation steps.

## Contributing

### Adding New Insights

1. Create insight class in appropriate category module:
```python
# dojo/github_collector/insights/security.py
from dojo.github_collector.insights.base import BaseInsight

class MyInsight(BaseInsight):
    insight_id = 'my_insight'
    name = 'My Insight'
    description = 'Description'
    category = 'security'
    visualization_type = 'chart'
    chart_type = 'bar'

    def calculate(self, filters=None):
        # Query and return data
        return {'title': '...', 'data': {...}, 'metadata': {...}}
```

2. Register with InsightRegistry (automatic via module import)

3. Test with management command:
```bash
python manage.py generate_insights --insight my_insight
```

## References

- [CLAUDE.md](../../CLAUDE.md) - Main project documentation
- [README_GRAPHQL.md](./README_GRAPHQL.md) - GraphQL migration details
- [README_SYNC_UI.md](./README_SYNC_UI.md) - Web UI configuration guide (NEW)
- [README_ALERTS.md](./README_ALERTS.md) - Security alerts integration
- [ARCHITECTURE_DECISION.md](./ARCHITECTURE_DECISION.md) - GraphQL migration decision
- [PHASE4_VALIDATION_REPORT.md](../../PHASE4_VALIDATION_REPORT.md) - Product migration validation

## License

DefectDojo is licensed under the BSD-3-Clause License. See [LICENSE.md](../../LICENSE.md) for details.
