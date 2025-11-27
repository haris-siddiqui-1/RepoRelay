# GitHub Collector Module

The GitHub Collector is DefectDojo's comprehensive integration system for GitHub repository management, security monitoring, and analytics.

## Overview

This module provides four major subsystems for GitHub integration:

1. **Repository Metadata Enrichment** - GraphQL-powered collector for repository context
2. **Security Alerts Collection** - Automated sync of GitHub security alerts to DefectDojo Findings
3. **Insights Dashboard** - Widget-based analytics with 25 built-in insights
4. **Product Migration Wizard** - Hierarchical clustering for repository-to-product consolidation

## Architecture

```
dojo/github_collector/
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
└── urls.py                   # URL routing for insights dashboard
```

## 1. Repository Metadata Enrichment

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

## 2. Security Alerts Collection

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

## 3. Insights Dashboard

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

## 4. Dependency Graph Analysis

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

## 5. Product Migration Wizard

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

## Testing

```bash
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
1. **Missing GitHub token**: Set `DD_GITHUB_TOKEN` environment variable
2. **Rate limit exceeded**: Wait for rate limit reset (check `X-RateLimit-Reset` header)
3. **GraphQL query too complex**: Reduce batch size or use REST fallback
4. **Insight calculation timeout**: Optimize queries or increase cache TTL

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
