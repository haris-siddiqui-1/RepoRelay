# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Additional Guidance

@sessions/CLAUDE.sessions.md

This file provides instructions for Claude Code for working in the cc-sessions framework.

---

# DefectDojo - DevSecOps & Vulnerability Management Platform

DefectDojo is an OWASP Flagship project that provides DevSecOps and vulnerability management capabilities, supporting 211+ security scanning tools.

## Tech Stack

**Backend:** Python 3.13 + Django 5.1.14 + Django REST Framework 3.16.1
**Database:** PostgreSQL (exclusive - no MySQL/SQLite support)
**Async:** Celery 5.5.3 with Valkey/Redis broker
**Frontend (Classic):** Bootstrap 3.4.1, jQuery 3.7.1, DataTables
**Frontend (Modern Preview):** Tailwind CSS 3.4, Alpine.js 3.13, Chart.js 4.4, Vite 5.0
**Deployment:** Docker Compose with uWSGI and NGINX

## Key Commands

### Development Setup
```bash
# Check Docker compatibility
./docker/docker-compose-check.sh

# Build and start services
docker compose build
docker compose up -d

# Get admin credentials (initializer takes ~3 minutes)
docker compose logs -f initializer
docker compose logs initializer | grep "Admin password:"

# Access application
open http://localhost:8080
```

### Testing
```bash
# Run specific unit test
./run-unittest.sh --test-case unittests.tools.test_stackhawk_parser.TestStackHawkParser

# Run with extra verbosity and fail-fast
./run-unittest.sh --test-case <test_path> -v3 --failfast

# Run all integration tests
./run-integration-tests.sh

# Inside container - run Django tests
docker compose exec uwsgi bash -c "python manage.py test <test_path>"
```

### Database Migrations
```bash
# Generate new migration after model changes
docker compose exec uwsgi bash -c "python manage.py makemigrations"

# Apply migrations
docker compose exec uwsgi bash -c "python manage.py migrate"
```

### Code Quality
```bash
# Ruff is configured in ruff.toml with Python 3.13 target
# Line length: 120 characters
# Extensive rule set for security, Django best practices, and code quality
```

### Shell Access
```bash
# Django shell
docker compose exec uwsgi bash -c "python manage.py shell"

# Container bash
docker compose exec uwsgi bash
```

### GitHub Integration Commands
```bash
# Sync repository metadata (GraphQL-based, incremental)
docker compose exec uwsgi bash -c "python manage.py sync_github_repositories --incremental"

# Sync GitHub security alerts (incremental)
docker compose exec uwsgi bash -c "python manage.py sync_github_alerts"

# Sync alerts and create DefectDojo Findings
docker compose exec uwsgi bash -c "python manage.py sync_github_alerts --create-findings"

# Force full sync (ignores last sync timestamp)
docker compose exec uwsgi bash -c "python manage.py sync_github_alerts --force --create-findings"

# Sync specific repository
docker compose exec uwsgi bash -c "python manage.py sync_github_alerts --repository-id 123 --create-findings"

# Dry run (preview without changes)
docker compose exec uwsgi bash -c "python manage.py sync_github_alerts --dry-run"

# Generate insights reports (CLI access)
docker compose exec uwsgi bash -c "python manage.py generate_insights --list"
docker compose exec uwsgi bash -c "python manage.py generate_insights --insight vuln_distribution"
docker compose exec uwsgi bash -c "python manage.py generate_insights --category security --output json"
docker compose exec uwsgi bash -c "python manage.py generate_insights --all --days 30"
```

## Architecture Overview

### Monolithic Models with Domain Modules
The codebase uses a **monolithic `dojo/models.py`** (238KB) containing 40+ core models, with feature-specific modules that extend functionality:

**Core Entity Hierarchy:**
- `Product_Type` → `Product` → `Repository` → `Test` → `Finding`
- `Product_Type` → `Product` → `Engagement` → `Test` → `Finding` (traditional path)
- `Repository` - NEW (January 2025): GitHub repository with 47 enrichment fields, links to Product (1:many)
- `GitHubAlert` - NEW (January 2025): Raw GitHub security alerts (Dependabot, CodeQL, Secret Scanning)
- `Engagement` - Time-bound security testing activities
- `Endpoint` - Network targets and services
- `Tool_Type`/`Tool_Configuration` - Integration configs for 211+ tools

**Domain Modules Structure** (`dojo/<feature>/`):
Each feature module follows a consistent pattern:
- `models.py` - Domain-specific data models
- `views.py` - View handlers and URL routing
- `helper.py` / `services.py` - Business logic
- `queries.py` - Query optimization with prefetch patterns
- `urls.py` - URL routing
- API integration in `api_v2/`

**Key Modules:**
- `dojo/finding/` - Core vulnerability management with complex deduplication logic (dojo/finding/helper.py:712)
- `dojo/importers/` - Scan file parsing framework (base_importer.py, default_importer.py, default_reimporter.py)
- `dojo/tools/` - 211 security tool parsers (each with parser.py implementing get_fields, get_dedupe_fields, get_scan_types)
- `dojo/authorization/` - RBAC with roles: Reader, API_Importer, Writer, Maintainer, Owner
- `dojo/api_v2/` - REST API with serializers (116KB), permissions (39KB), and viewsets
- `dojo/github_collector/` - GitHub integration with three major subsystems:
  - Repository metadata enrichment (collector.py, graphql_client.py) - See README_GRAPHQL.md
  - Security alerts collection (alerts_collector.py, findings_converter.py) - See README_ALERTS.md
  - **Insights dashboard** (insights/ module) - 25 insights across 5 categories with widget-based UI
  - Supports GraphQL API v4 (bulk operations) with REST API fallback
- `dojo/frontend/` - Modern UI build system (NEW - November 2025):
  - Vite 5.0 build tool with HMR development server
  - Tailwind CSS 3.4 with JIT compilation
  - Alpine.js 3.13 reactive components (dark mode, dropdown, modal, toast)
  - Chart.js 4.4 for visualizations
  - See README at dojo/frontend/README.md

### REST API Architecture
**Base URL:** `/api/v2/`

**Design Pattern:** ViewSet-based with DRF
**Authentication:** Token-based, session-based, OAuth2/SAML2, remote user SSO
**Permissions:** Fine-grained RBAC with 100+ permission types (dojo/authorization/roles_permissions.py)
**Documentation:** OpenAPI/Swagger via drf-spectacular

**Key Endpoints:**
- `/products/`, `/engagements/`, `/tests/`, `/findings/`
- `/scan-imports/`, `/re-scan-imports/` - Bulk vulnerability import/update
- `/github_insights/` - GitHub repository insights and dashboard configuration
- Pagination, filtering (django-filter), and bulk operations supported

### Settings & Configuration
Uses **django-split-settings** with environment variable configuration:

**Settings Location:** `dojo/settings/settings.dist.py`
**Environment Variables:** Prefix all configs with `DD_*`
- `DD_DEBUG` - Debug mode
- `DD_SECRET_KEY` - Django secret key
- `DD_DATABASE_URL` - PostgreSQL connection string
- `DD_CELERY_BROKER_URL` - Celery broker (Valkey/Redis)
- `DD_MEDIA_ROOT` - File upload directory

**Local Overrides:** Create `local_settings.py` for development-specific settings

### Async Task Processing
**Celery Configuration:**
- Broker: Valkey/Redis
- Result backend: Django DB or Redis
- Beat scheduler for cron jobs
- Task serialization: Pickle (models passed by ID)

**Common Tasks:**
- Async scan imports and re-imports
- Vulnerability deduplication processing
- Notification delivery (email, webhooks, Slack, Jira)
- Search index updates (django-watson with async threshold)

### Security Tool Integration
**211 supported parsers** in `dojo/tools/<tool_name>/`:

**Parser Structure:**
```python
# Each tool has parser.py with:
class MyToolParser:
    def get_scan_types(self):
        return ["MyTool Scan"]

    def get_label_for_scan_types(self, scan_type):
        return "MyTool Scan"

    def get_description_for_scan_types(self, scan_type):
        return "Import MyTool results"

    def get_findings(self, file, test):
        # Parse and return Finding objects
```

**Tool Categories:**
- Web app scanners (Acunetix, Burp, Nessus)
- SAST (Checkmarx, Fortify, SonarQube)
- Container/Dependency (Anchore, Trivy, Grype)
- Cloud security (AWS Security Hub, Azure)
- API-based (BlackDuck, Cobalt, Edgescan)

### GitHub Integration

DefectDojo has five GitHub integration patterns:

1. **Issue Tracking** (`dojo/github.py`) - Traditional GitHub issue creation/sync for findings
   - Uses PyGithub REST API
   - Creates/updates GitHub issues for security findings
   - Associated with GITHUB_PKey and GITHUB_Issue models

2. **Repository Context Enrichment** (`dojo/github_collector/`) - GraphQL-powered metadata collector
   - Syncs repository metadata to Repository model (separate from Product)
   - Detects 36 binary signals (deployment indicators, security posture, activity metrics)
   - Classifies repository tier/criticality (tier1-tier4, archived)
   - **Partial Dual-Population Strategy**: Activity metrics (commit_count, open_issues_count, open_pr_count) sync to both Repository model (primary) and Product model (legacy compatibility). Webhook health fields (has_webhooks, active_webhooks_count, webhook_cadence, webhook_types) are Repository-only.
   - **GraphQL API v4 for bulk operations** (15-20x faster incremental syncs)
   - **REST API path**: Individual repository syncs with full enrichment field population (fixed November 2025)
   - Automatic REST fallback for reliability
   - **XSS Sanitization**: All user-controlled GitHub data (README summaries, CODEOWNERS) sanitized with bleach.clean()
   - Webhook health monitoring: Detects webhook types, cadence, active count (requires admin:repo_hook permission)
   - Progress tracking: Logs every 10 repositories during sync operations
   - Web UI: `/github/sync/configuration` for configuration and manual sync
   - Management command: `python manage.py sync_github_repositories`
   - See detailed documentation: dojo/github_collector/README_GRAPHQL.md

3. **Security Alerts Collection** (`dojo/github_collector/alerts_collector.py`) - NEW (January 2025)
   - Fetches GitHub security alerts (Dependabot, CodeQL, Secret Scanning)
   - Converts alerts to DefectDojo Findings with automatic deduplication
   - Syncs alert state changes bidirectionally (open/dismissed/fixed)
   - Supports incremental sync with rate limit management
   - Management command: `python manage.py sync_github_alerts --create-findings`
   - See detailed documentation: dojo/github_collector/README_ALERTS.md

4. **Insights Dashboard** (`dojo/github_collector/insights/`) - NEW (January 2025)
   - Widget-based analytics dashboard with 25 built-in insights
   - 5 categories: Activity, Health, Security, Ownership, Technology
   - Pluggable architecture (BaseInsight + InsightRegistry pattern)
   - User-specific dashboard configuration (GitHubInsightConfiguration model)
   - Chart.js 4.4.0 visualizations (pie, bar, line, scatter, histogram)
   - REST API: `/api/v2/github_insights/` and web UI: `/github/insights/dashboard`
   - Management command: `python manage.py generate_insights`
   - See detailed documentation in "GitHub Insights Dashboard" section below

5. **Product Migration Wizard** (`dojo/product/migration_wizard.py`) - NEW (January 2025)
   - Migrates from "1 Product per Repository" to "1 Product per Application"
   - Uses hierarchical clustering to suggest logical repository groupings
   - Preserves Finding → Test → Engagement → Product relationship chain
   - **Critical Feature**: Migrates Engagements along with Repositories to prevent Finding orphaning
   - Transaction-safe operations with rollback capability
   - Clustering engine: `dojo/github_collector/clustering.py`
   - Management command: `python manage.py migrate_products_to_repositories`

**GraphQL Migration (January 2025):**
The repository collector now uses GitHub GraphQL API v4 for bulk organization syncs, reducing API calls by 94% and enabling sub-5-minute daily incremental syncs. REST API remains as fallback and for individual repository updates. Webhook health monitoring requires REST API as GitHub GraphQL does not expose webhook data.

**GitHub Alerts Integration (January 2025):**
The alerts collector creates a data hierarchy: Product → Repository → GitHubAlert → Finding. This enables centralized vulnerability management across all GitHub repositories with proper deduplication using unique_id_from_tool format: "github-{type}-{repo_id}-{alert_id}".

**Key Features:**
- Repository Model: Separate entity with 47 enrichment fields, links to Product (1:many relationship)
- Incremental sync: Only fetch repositories/alerts updated since last sync
- Query cost: ~40 points per repo for metadata, ~10 points per repo for Dependabot alerts
- Rate limit monitoring: 5,000 points/hour quota
- Alert types: Dependabot (GraphQL), CodeQL (REST), Secret Scanning (REST)
- Finding integration: Automatic Test creation per alert type, state synchronization
- Admin UI: Complete CRUD for Repository, GitHubAlert, GitHubAlertSync models
- **Data Integrity**: Partial dual-population strategy ensures activity metrics stay synchronized between Repository and Product models. Webhook health fields are Repository-only.
- **Security Hardening**: XSS sanitization applied to all external GitHub data (README, CODEOWNERS) using bleach.clean()
- **Webhook Monitoring**: Automatic webhook health tracking (types, cadence, active count) with graceful permission fallback
- **Sync Configuration UI**: Web-based configuration at `/github/sync/configuration` (staff/superuser only)
  - GitHub token management with validation (format check + API connectivity test)
  - Account type selection (Organization or Personal Account)
  - Auto-sync settings with schedule options (manual, hourly, daily, weekly)
  - Manual sync trigger button with real-time status feedback
  - Last sync timestamp and status display (success/failed with error details)

**Product Migration (Phase 4 - January 2025):**
- ProductMigrationWizard class provides clustering-based repository grouping
- Migration preserves all data relationships: Finding → Test → Engagement → Product
- Engagement Migration Fix: Engagements are moved along with Repositories during consolidation (dojo/product/migration_wizard.py:336-347)
- Rollback Limitation: Repository rollback is fully automated; Engagement rollback is not automated due to lack of tracking metadata (documented at lines 471-479)
- Validated with 133 real GitHub security alerts: 100% data preservation, 100% hash code stability
- See validation report: PHASE4_VALIDATION_REPORT.md

### Data Persistence Patterns
**Advanced Django Features:**
- **Audit Logging:** django-auditlog (3.2.1) tracks all model changes
- **History Tracking:** django-pghistory (3.8.3) for PostgreSQL-native versioning
- **Full-text Search:** django-watson (1.6.3) with async index updates
- **Tags:** django-tagulous (2.1.0) for flexible taxonomy
- **Soft Deletes:** Status fields (active, verified, duplicate, false_p, risk_accepted)

**Query Optimization:**
- Prefetch patterns in API layer
- Module-specific query managers (e.g., `dojo/endpoint/queries.py`)
- Aggregations for statistics computation

### Deduplication System
Complex algorithm for finding duplicate detection:
- Located in `dojo/finding/helper.py`
- Configurable per-tool field matching
- Background Celery task processing
- Dedicated logging stream for troubleshooting
- Fields: `hash_code`, `unique_id_from_tool`, configurable deduplication keys

**GitHub Alerts Deduplication:**
GitHub alerts use a standardized unique_id_from_tool format:
- Dependabot: `"github-dependabot-{repo_id}-{alert_id}"`
- CodeQL: `"github-codeql-{repo_id}-{alert_id}"`
- Secret Scanning: `"github-secret_scanning-{repo_id}-{alert_id}"`
- Re-imports automatically update existing findings based on this identifier
- State changes (open→dismissed→fixed) sync bidirectionally between GitHub and DefectDojo

### GitHub Data Models (January 2025)

**Repository Model** (`dojo/models.py`)
Represents a GitHub repository with enrichment metadata:
- Core fields: `name`, `github_repo_id` (unique), `github_url`
- Relationships: `product` (ForeignKey), `related_products` (ManyToMany)
- Activity tracking: `last_commit_date`, `active_contributors_90d`, `days_since_last_commit`
- **Activity metrics** (added November 2025): `commit_count`, `open_issues_count`, `open_pr_count`
- **Webhook health** (added November 2025): Integration health monitoring fields
  - `has_webhooks` (Boolean): True if repository has configured webhooks
  - `active_webhooks_count` (Integer): Count of active webhooks
  - `webhook_cadence` (String): Delivery frequency (Hourly, 2 Hours, Daily, Weekly, Monthly, Inactive, Unknown)
  - `webhook_types` (JSONField): Array of detected webhook integration types (Jenkins, CircleCI, JIRA, Slack, etc.)
  - Requires admin:repo_hook permission; fails gracefully to False/0/Inactive/[] if missing
  - Collected via REST API only (GitHub GraphQL does not expose webhook data)
- Metadata: `readme_summary`, `primary_language`, `primary_framework` (XSS sanitized with bleach.clean())
- Ownership: `codeowners_content` (XSS sanitized), `ownership_confidence`
- 36 binary signals across 5 categories (deployment, production, development, organization, security)
- Alert metadata: `last_alert_sync`, `dependabot_alert_count`, `codeql_alert_count`, `secret_scanning_alert_count`
- Pre-computed statistics: `cached_finding_counts` (JSONField)
- Tier classification: `tier` (tier1, tier2, tier3, tier4, archived)

**GitHubAlert Model** (`dojo/models.py`)
Stores raw GitHub security alerts:
- Core fields: `repository` (ForeignKey), `alert_type`, `github_alert_id`, `state`, `severity`
- Content: `title`, `description`, `html_url`
- Type-specific: `cve`, `package_name` (Dependabot), `cwe`, `rule_id`, `file_path` (CodeQL), `secret_type` (Secret Scanning)
- Raw data: `raw_data` (JSONField) - Complete GitHub API response
- Timestamps: `created_at`, `updated_at`, `dismissed_at`, `fixed_at`
- Finding link: `finding` (ForeignKey) - Links to DefectDojo Finding after conversion
- Unique constraint: `['repository', 'alert_type', 'github_alert_id']`

**GitHubAlertSync Model** (`dojo/models.py`)
Tracks alert sync status per repository:
- Sync timestamps: `dependabot_last_sync`, `codeql_last_sync`, `secret_scanning_last_sync`
- Statistics: `dependabot_alerts_fetched`, `codeql_alerts_fetched`, `secret_scanning_alerts_fetched`
- Error tracking: `last_sync_error`, `last_sync_error_at`, `last_rate_limit_hit`
- OneToOne relationship with Repository

**GitHubSyncConfiguration Model** (`dojo/models.py`) - NEW (January 2025)
Singleton configuration for GitHub repository synchronization:
- Core fields: `github_token`, `account_type` (organization/user), `account_name`
- Sync settings: `auto_sync_enabled`, `sync_schedule` (manual/hourly/daily/weekly), `incremental_sync`
- Status tracking: `last_sync`, `last_sync_status`, `last_sync_error`
- Singleton pattern: Only one configuration record exists (pk=1)
- Associated view: `/github/sync/configuration` (staff/superuser only)

**Test Types for GitHub Alerts:**
Three new Test_Type records created automatically:
- "GitHub Dependabot" - Dependency vulnerability alerts
- "GitHub CodeQL" - Code scanning/SAST alerts
- "GitHub Secret Scanning" - Exposed secrets alerts

**Data Hierarchy Flow:**
1. Repository record created/updated via `sync_github_repositories` command (dual-population to Repository + Product models)
2. Activity metrics (commit_count, open_issues_count, open_pr_count) synced from GitHub API
3. Webhook health metadata collected (requires admin:repo_hook permission, fails gracefully if missing)
4. All external GitHub data (README summaries, CODEOWNERS content) sanitized with bleach.clean() before storage
5. GitHubAlert records synced via `sync_github_alerts` command
6. Findings created with `--create-findings` flag, linked to appropriate Test
7. Finding updates trigger on re-sync based on alert state changes
8. Each Repository gets one Engagement with three Tests (one per alert type)

**Webhook Health Monitoring Implementation Details:**

The webhook health monitoring system (`dojo/github_collector/collector.py`) provides integration health insights by analyzing configured webhooks:

**Data Collection** (`_collect_webhook_metadata` method, lines 1196-1241):
1. **List Webhooks**: Calls `repo.get_hooks()` via REST API (1 API call per repository)
2. **Count Active**: Filters webhooks where `hook.active == True`
3. **Detect Types**: Parses webhook URLs to identify integrations:
   - Jenkins: URLs containing `/jenkins/`, `/hudson/`
   - CircleCI: URLs containing `/circleci.com/`, `/circle-ci.com/`
   - JIRA: URLs containing `/jira/`, `/atlassian.net/`
   - Slack: URLs containing `/slack.com/`, `/hooks.slack/`
   - GitHub Actions: URLs containing `/actions/`, `/github.com/actions/`
   - And 15+ more integration types
4. **Calculate Cadence**: Fetches last 25 delivery events per webhook, computes median time delta
   - Hourly: < 1 hour median
   - 2 Hours: 1-2 hours median
   - Daily: 2-24 hours median
   - Weekly: 1-7 days median
   - Monthly: 7-30 days median
   - Inactive: > 30 days median or no deliveries
   - Unknown: Unable to determine (permission error, no delivery history)

**Permission Requirements**:
- Requires `admin:repo_hook` GitHub permission
- Graceful degradation: If permission missing, defaults to:
  - `has_webhooks = False`
  - `active_webhooks_count = 0`
  - `webhook_cadence = 'Unknown'`
  - `webhook_types = []`
- Logs warning but does not fail the sync operation

**Integration Points**:
- Called from `sync_repository()` at line 538-549 (REST API path)
- GraphQL path does not collect webhook data (API limitation)
- Results stored in Repository model fields only (not dual-populated to Product)

**Performance Characteristics**:
- REST API cost: 1 call for webhook list + N calls for delivery history (N = number of webhooks)
- Typical overhead: 1-5 API calls per repository with webhooks
- Repositories without webhooks: 1 API call (list returns empty)
- Rate limit impact: Minimal (<5% of total sync API calls for typical organization)

**Error Handling**:
- Permission errors: Caught and handled gracefully with default values
- Network errors: Retry with exponential backoff (inherited from PyGithub client)
- Invalid webhook data: Skipped with warning log
- Empty delivery history: Cadence set to 'Inactive'


### GitHub Insights Dashboard (January 2025)

**Overview:**
The Insights Dashboard provides repository management analytics through a configurable widget-based UI with 25 built-in insights across 5 categories: Activity, Health, Security, Ownership, and Technology.

**Architecture Pattern - Pluggable Insights System:**

**BaseInsight Abstract Class** (`dojo/github_collector/insights/base.py`)
- Defines common interface for all insights
- Required attributes: `insight_id`, `name`, `description`, `category`, `visualization_type`, `chart_type`
- Abstract method: `calculate(filters) -> Dict` - Returns structured data with title, data, metadata
- Default cache duration: 300 seconds (5 minutes)
- Supports two visualization types: 'table' (tabular data), 'chart' (Chart.js visualizations)

**InsightRegistry Pattern** (`dojo/github_collector/insights/registry.py`)
- Auto-discovery mechanism for insight classes
- Central registry for all available insights
- Methods: `register()`, `get_insight()`, `get_all_insights()`, `get_insights_by_category()`
- Lazy loading via `autodiscover()` function

**Insight Categories & Examples:**

1. **Activity Insights** (`activity.py`) - 5 insights
   - Most Recently Updated Repositories
   - Stale Repositories (no commits in 90 days)
   - Highest Commit Frequency
   - Most Active Contributors
   - Recently Created Repositories

2. **Health Insights** (`health.py`) - 5 insights
   - Repositories Missing README
   - Repositories Missing CI/CD
   - Repositories with Open PRs Older Than 30 Days
   - Repositories with High Issue Count (>50 open issues)
   - Stale Repositories (no activity in 6 months)

3. **Security Insights** (`security.py`) - 7 insights
   - Vulnerability Distribution by Severity (pie chart)
   - Vulnerability Distribution by Type/CWE (bar chart)
   - Critical Vulnerability Trend (line chart)
   - Repositories with Most Critical Findings
   - Activity-Vulnerability Correlation (scatter plot)
   - Repositories with No Security Findings
   - Average Finding Age by Repository

4. **Ownership Insights** (`ownership.py`) - 4 insights
   - Unassigned Repositories (no Product owner)
   - Repositories with Multiple Owners
   - Orphaned Repositories (owner inactive)
   - Department Distribution

5. **Technology Insights** (`technology.py`) - 4 insights
   - Most Popular Languages
   - Repositories Using Docker
   - Repositories with Kubernetes
   - Framework Adoption Rates

**Data Models:**

**GitHubInsightConfiguration Model** (`dojo/models.py:5547-5604`)
- OneToOne relationship with User
- `widget_config` (JSONField) - Array of widget configurations with insight_id, order, size, pinned, auto_refresh, filters
- `widget_count` (IntegerField) - Number of widgets to display (default: 10)
- Pinned widgets bypass widget_count limit and have shorter cache TTL (60s vs 300s)
- Created/updated timestamps for audit trail

**Product.repository_owner Field** (`dojo/models.py:1281-1284`)
- New CharField added to Product model
- Stores GitHub organization or user that owns the repository
- Used by ownership insights for department/owner analysis

**REST API Endpoints:**

**GitHubInsightsViewSet** (`dojo/api_v2/views.py:3604-3687`)
- Base URL: `/api/v2/github_insights/`
- Authentication: IsAuthenticated required
- Endpoints:
  - `GET /api/v2/github_insights/` - List all available insights (metadata only)
  - `GET /api/v2/github_insights/?category=security` - Filter by category
  - `GET /api/v2/github_insights/{insight_id}/` - Calculate specific insight with optional filters
  - `GET /api/v2/github_insights/dashboard/` - Get user's dashboard configuration
  - `POST /api/v2/github_insights/dashboard/` - Update dashboard configuration

**Caching Strategy:**
- Hash-based cache keys: `github_insight_{insight_id}_{hash(filters)}`
- Default TTL: 300 seconds (5 minutes)
- Pinned widgets: 60 seconds (1 minute) - configurable via `cache_duration` attribute
- Django cache framework with Redis/Valkey backend

**Frontend Dashboard:**

**URL:** `/github/insights/dashboard`
**Template:** `dojo/templates/dojo/github_insights_dashboard.html`
**JavaScript:** `dojo/static/dojo/js/github_insights_dashboard.js` (670 lines)

**Design System (Updated January 2025):**
- **Accent Color:** Violet (#8B5CF6) - consistent with modern UI templates
- **Background:** Soft dark (#1c2128) - follows 2025 UI/UX best practices (not pure black)
- **DataTables Integration:** Uses violet accent for interactive elements, filters, and buttons
- **Glass Morphism:** `backdrop-filter: blur(12px)` with `-webkit-` prefix for config panel

**Features:**
- Widget-based grid layout (Bootstrap 3.4.1 responsive)
- Chart.js 4.4.0 for visualizations (pie, bar, line, scatter, histogram)
- Configuration modal for widget selection and ordering (vanilla DOM manipulation)
- Individual widget refresh buttons with loading spinners and error handling
- Real-time data fetching via REST API
- Automatic refresh for pinned widgets (60-second intervals)
- Pin/unpin functionality for critical insights
- Widget size options: small (col-md-4), medium (col-md-6), large (col-md-12)

**Management Command:**

**Command:** `python manage.py generate_insights`
**Purpose:** CLI access to insights for automation, testing, and reporting
**Options:**
- `--list` - List all available insights grouped by category
- `--insight <insight_id>` - Generate specific insight (e.g., `--insight vuln_distribution`)
- `--category <category>` - Generate all insights in category (activity, health, security, ownership, technology)
- `--all` - Generate all insights
- `--days <n>` - Time range filter in days (default: 30)
- `--product-type-id <id>` - Filter by product type
- `--output <format>` - Output format: json, table (default: table)

**Usage Examples:**
```bash
# List all available insights
python manage.py generate_insights --list

# Generate vulnerability distribution chart
python manage.py generate_insights --insight vuln_distribution --output json

# Generate all security insights for last 90 days
python manage.py generate_insights --category security --days 90

# Generate all insights with product type filter
python manage.py generate_insights --all --product-type-id 5 --output json
```

**Performance Characteristics:**
- Insight calculation time: <2 seconds for 2,451 repositories
- Dashboard load time: <5 seconds for 15 widgets (with cache hits)
- Query optimization: Uses select_related(), prefetch_related() patterns
- Database indexes on GitHub-related fields (github_url, last_commit_date)

**Extensibility - Adding Custom Insights:**

1. Create new insight class inheriting from BaseInsight
2. Implement required attributes and calculate() method
3. Register with InsightRegistry (automatic via module import)
4. Place in appropriate category module (activity, health, security, ownership, technology)

Example:
```python
# dojo/github_collector/insights/security.py
from dojo.github_collector.insights.base import BaseInsight
from dojo.github_collector.insights.registry import InsightRegistry

class MyCustomInsight(BaseInsight):
    insight_id = 'custom_insight'
    name = 'My Custom Insight'
    description = 'Description of what this insight provides'
    category = 'security'
    visualization_type = 'chart'
    chart_type = 'bar'

    def calculate(self, filters=None):
        # Query data and return structured result
        return {
            'title': 'Custom Insight Title',
            'data': {'labels': [...], 'values': [...]},
            'metadata': {'count': 10, 'timestamp': timezone.now()}
        }

# Auto-registration via InsightRegistry.register(MyCustomInsight)
```

**Database Migrations:**
- Migration 0253: Creates `github_insight_configuration` table
- Migration 0254: Adds `repository_owner` field to Product model

**Integration with Existing GitHub Features:**
- Uses Repository model's 47 enrichment fields (36 binary signals)
- Queries Finding model for vulnerability analytics
- Leverages Product model's GitHub URL and business_criticality fields
- Compatible with GraphQL-based repository sync (README_GRAPHQL.md)
- Works with GitHub Alerts integration (README_ALERTS.md)

**Future Enhancement Opportunities:**
- Advanced filtering: Date range pickers, tag filters, custom query builder
- Widget customization: Drag-and-drop ordering, custom sizes, per-widget filters
- Alerting: Email/Slack notifications when insight thresholds crossed
- Scheduled reports: CSV/PDF export, automated email delivery
- Custom insights: Admin UI for creating insights without code
- Trend analysis: Historical data tracking, time-series visualizations

### Modern Dashboard UI (Preview - November 2025)

**Overview:**
A redesigned dashboard interface using a modern frontend stack (Tailwind CSS, Alpine.js, Vite) with an enterprise dark-mode-first aesthetic. This is a preview feature that runs alongside the classic Bootstrap-based UI.

**Phase 1 Status (January 2025):** ✅ COMPLETE
- Comprehensive UI audit completed with 26 issues identified and fixed
- All core pages validated with Playwright browser testing
- Navigation, DataTables, modals, and widgets fully functional
- Design system unified across all modern templates

**URL:** `/dashboard_modern`
**View:** `dojo/home/views.py:dashboard_modern()` (lines 72-109)
**Templates:**
- `dojo/templates/base_modern.html` - Base template with shared assets, navigation, command palette
- `dojo/templates/dojo/dashboard_modern.html` - Dashboard content with stat cards and charts

**Design System (Finalized January 2025):**

**Color Palette - Enterprise Dark-Mode-First:**
- **Primary Background:** `#0f1419` (dark slate, not pure black)
- **Card Background:** `#1c2128` (soft dark, recommended for 2025 UI/UX)
- **Accent Color:** `#8B5CF6` (violet) - used consistently across all modern pages
- **Text Primary:** `#F0F6FC` (off-white for readability)
- **Text Secondary:** `#8b949e` (muted gray)
- **Border:** `rgba(255, 255, 255, 0.1)` (10% white opacity)

**Typography:**
- **Display/Body:** Plus Jakarta Sans (weights 300-800)
- **Code/Monospace:** JetBrains Mono (weights 400-600)
- **Letter spacing:** -0.01em (body), -0.02em (headings)

**Effects:**
- **Glass morphism:** `backdrop-filter: blur(12px)` with `-webkit-` prefix for Safari
- **Shadows:** Subtle layered shadows for depth
- **Transitions:** 200ms cubic-bezier(0.4, 0, 0.2, 1) for all interactions
- **Hover states:** Violet glow (box-shadow) on accent elements

**Grid & Spacing:**
- **Base unit:** 4px spacing system
- **Card padding:** 24px (6 units) or 32px (8 units) for large cards
- **Gap utilities:** `gap-4` (16px) preferred over `justify-between` to prevent icon overflow

**Animations:**
- **Staggered reveal:** 200ms delays between elements on page load
- **Easing:** cubic-bezier(0.16, 1, 0.3, 1) for smooth entrances

**Key Features:**

1. **Collapsible Sidebar Navigation** - Responsive sidebar with smooth transitions
   - **Active State Pattern:** Uses Django template logic `{% if request.resolver_match.url_name == 'dashboard_modern' %}active{% endif %}`
   - **Not JavaScript-based:** Server-rendered active state for reliability
   - **URL Name Matching:** Requires exact Django URL name matching (e.g., 'engagement' not 'engagements')

2. **Command Palette** - Keyboard-driven navigation (Cmd+K / Ctrl+K)
   - Full arrow key navigation
   - Enter to select, Escape to close
   - Fuzzy search across all navigation items

3. **Dark/Light Mode Toggle** - CSS custom properties with localStorage persistence

4. **Stat Cards** - Glass morphism cards with hover effects
   - **Layout Pattern:** `flex gap-4` instead of `justify-between` to prevent icon overflow on narrow viewports
   - Active Engagements
   - Findings Last 7 Days
   - Closed Findings
   - Risk Accepted

5. **Chart.js Visualizations** - Pie chart (severity distribution), line chart (trends by month)
   - Date-fns adapter for time-axis support (chartjs-adapter-date-fns@3.0.0 required)
   - Responsive containers with proper aspect ratio handling

**DataTables Component (Alpine.js):**

**File:** `dojo/frontend/src/js/alpine/components/dataTable.js`
**Styles:** `dojo/static/dojo/css/components/dataTable.css`

**Design System Compliance:**
- Violet accent (#8B5CF6) for all interactive elements (checkboxes, buttons, hover states)
- Soft dark background (#1c2128) instead of pure black (#000000) for better 2025 aesthetics
- Glass morphism header with `backdrop-filter: blur(12px)`
- Consistent 200ms transitions for all interactions

**Features:**
- Virtual scrolling for performance (48px row height)
- Column sorting (number, string, severity, date types)
- Search/filtering
- Bulk actions with checkbox selection
- Expandable rows with `dd-expand-toggle` button
- Pagination controls

**Usage Pattern:**
```django
<script id="findings-data" type="application/json">
{{ findings_json|safe }}
</script>
<div x-data="dataTable({
    data: JSON.parse(document.getElementById('findings-data').textContent),
    columns: [
        { key: 'id', label: 'ID', sortType: 'number' },
        { key: 'severity', label: 'Severity', sortType: 'severity' }
    ],
    csrfToken: '{{ csrf_token }}',
    bulkActionUrl: '{% url "finding_bulk_update_all" %}'
})">
```

**Frontend Build System:**

Located in `dojo/frontend/`:
- **Package:** `npm install` in dojo/frontend/
- **Dev Server:** `npm run dev` (http://localhost:3000 with HMR)
- **Production Build:** `npm run build` (outputs to ../static/dist/)
- **Assets:** Fingerprinted filenames for cache busting (e.g., `styles-i1SwRXYS.css`)
- **Static Collection:** Run `python manage.py collectstatic` after each build

**Dependencies:**
- Tailwind CSS 3.4.0
- Alpine.js 3.13.3
- Chart.js 4.4.1 (with chartjs-adapter-date-fns@3.0.0)
- Vite 5.0.10
- Heroicons 2.1.1

**Alpine.js Components:**
- `darkMode` - Theme toggle with system preference detection
- `dropdown` - Accessible dropdown menus
- `modal` - Dialog/modal windows
- `toast` - Toast notifications (success, error, warning, info)
- `dataTable` - Enterprise data table with virtual scrolling

**URL Routing Pattern:**

**Best Practice:** Always use Django template `{% url %}` tag, never hardcode URLs
```django
<!-- Correct -->
<a href="{% url 'view_finding' finding.id %}">View Finding</a>
<a href="{% url 'engagement' eng.id %}">View Engagement</a>

<!-- Incorrect -->
<a href="/finding/{{ finding.id }}">View Finding</a>
```

**Critical:** Django URL names must match exactly in `urls.py` - e.g., `name='engagement'` not `name='engagements'`

**Integration Notes:**
- Uses same backend data as classic dashboard (engagement counts, findings, severity stats)
- Breadcrumb system maintained for navigation consistency
- Session-based authentication (same as classic UI)
- Classic UI remains default at `/dashboard`
- Toggle between views via navigation link

**Phase 1 Fixes (January 2025):**

**Issues Resolved:**
1. Modal action buttons (Save/Cancel/Delete) - Fixed event handlers
2. DataTable expand/collapse toggles - Implemented functional buttons
3. Bulk action controls - Added checkbox selection with sticky bottom bar
4. Search box focus states - Corrected border and placeholder colors
5. Widget refresh buttons (GitHub Insights) - Fixed API calls and loading states
6. Pagination controls - Repaired prev/next navigation
7. Dashboard card icon overflow - Changed from `justify-between` to `gap-4` flexbox
8. Navigation active state - Migrated from JavaScript to Django template logic
9. Table color scheme - Unified violet accent across all DataTables
10. Configure modal (GitHub Insights) - Fixed vanilla DOM manipulation
11. **DataTable virtual scrolling row parity** (November 2025) - Fixed alternating row colors breaking with virtual scroll
    - Changed from CSS `:nth-child(even)` to Alpine.js computed `.even-row` class binding
    - Applied to findings_list_modern.html, engagements_modern.html, product_modern.html

**Files Modified:**
- `dojo/templates/base_modern.html` - Navigation active state pattern
- `dojo/templates/dojo/dashboard_modern.html` - Card layout flexbox fix
- `dojo/templates/dojo/github_insights_dashboard.html` - Modal and refresh functionality
- `dojo/static/dojo/css/components/dataTable.css` - Violet accent, soft dark backgrounds, virtual scroll fix
- `dojo/static/dojo/js/github_insights_dashboard.js` - Configure modal, error handling
- `dojo/templates/dojo/findings_list_modern.html` - Virtual scroll row parity fix
- `dojo/templates/dojo/engagements_modern.html` - Virtual scroll row parity fix
- `dojo/templates/dojo/product_modern.html` - Virtual scroll row parity fix

**Validation:**
- Playwright browser testing across 5 core pages
- Visual regression screenshots captured
- Cross-browser testing (Chrome, Firefox, Safari)
- Mobile responsiveness verified (375px to 1920px)

**Performance:**
- Bundle sizes (gzipped): CSS ~15-25KB, Alpine.js ~15KB, Chart.js ~30KB, Custom JS ~10-15KB
- Total: ~70-85KB gzipped
- Tree-shaking and CSS purging enabled via Vite
- Virtual scrolling enables smooth rendering of 1000+ row tables

**Browser Support:**
- Chrome, Firefox, Safari, Edge (latest 2 versions)
- Mobile Safari (iOS 14+), Mobile Chrome (Android 10+)
- Safari 17+ requires `-webkit-backdrop-filter` prefix for glass morphism

**Known Limitations:**
- Dashboard card icon overflow persists on viewports <375px (edge case)
- DataTables pagination edge case when total items exactly divisible by page size
- Chart.js requires `chartjs-adapter-date-fns@3.0.0` before initializing time-axis charts

**Next Steps (Phase 2 - URL Routing Switchover):**
- Feature flags for gradual rollout (10% → 50% → 100%)
- Remove old template versions after 2-week monitoring period
- Comprehensive regression testing
- User feedback collection

**Related Documentation:**
- Frontend README: dojo/frontend/README.md
- Frontend Quick Start: dojo/frontend/QUICK_START.md
- Task Tracker: sessions/tasks/h-comprehensive-ui-modernization.md
- Phase 1 Tracker: sessions/tasks/h-phase1-url-routing-switchover.md

### Common UI Patterns (Modern Templates)

**Pattern: Navigation Active State (Server-Side)**

**Problem:** JavaScript-based URL matching for active navigation states is unreliable and doesn't work for server-rendered pages.

**Solution:** Use Django template logic with `request.resolver_match.url_name`

```django
<!-- In base_modern.html sidebar navigation -->
<a href="{% url 'dashboard_modern' %}"
   class="sidebar-nav-item {% if request.resolver_match.url_name == 'dashboard_modern' %}active{% endif %}">
    Dashboard
</a>
<a href="{% url 'finding' %}"
   class="sidebar-nav-item {% if request.resolver_match.url_name == 'finding' %}active{% endif %}">
    Findings
</a>
```

**Critical:** URL names must match exactly in `urls.py` - e.g., `name='engagement'` not `name='engagements'`

**Pattern: Flexbox Card Layout (Prevent Icon Overflow)**

**Problem:** Using `justify-between` causes icons to wrap to next line on narrow viewports.

**Solution:** Use `gap-4` with explicit flex alignment

```html
<!-- Before (causes overflow) -->
<div class="flex items-center justify-between">
    <div class="flex items-center gap-3">
        <icon>...</icon>
        <div>
            <h3>Title</h3>
            <p>Description</p>
        </div>
    </div>
    <span class="text-2xl">123</span>
</div>

<!-- After (prevents overflow) -->
<div class="flex items-center gap-4">
    <icon>...</icon>
    <div class="flex-1">
        <h3>Title</h3>
        <p>Description</p>
    </div>
    <span class="text-2xl">123</span>
</div>
```

**Pattern: JSON Data Passing to Alpine.js**

**Problem:** Inline JSON in `x-data` attribute causes parsing errors with complex data structures.

**Solution:** Use separate `<script type="application/json">` tag

```django
<!-- Correct approach -->
<script id="findings-data" type="application/json">
{{ findings_json|safe }}
</script>

<div x-data="dataTable({
    data: JSON.parse(document.getElementById('findings-data').textContent),
    columns: [...]
})">
```

**Pattern: Configure Modal (Vanilla DOM Manipulation)**

**Problem:** Bootstrap modal API conflicts with Alpine.js reactivity.

**Solution:** Use vanilla JavaScript DOM manipulation for modal show/hide

```javascript
// In github_insights_dashboard.js
function showConfigureModal() {
    const modal = document.getElementById('configureModal');
    modal.style.display = 'block';
    modal.classList.add('show');
    document.body.classList.add('modal-open');
}

function hideConfigureModal() {
    const modal = document.getElementById('configureModal');
    modal.style.display = 'none';
    modal.classList.remove('show');
    document.body.classList.remove('modal-open');
}
```

**Pattern: DataTable Color Scheme Uniformity**

**Principle:** All DataTables across modern templates should use consistent violet accent.

**Implementation:**
```css
/* In dataTable.css */
:root {
    --dd-table-accent: #8B5CF6;          /* Violet primary */
    --dd-table-accent-hover: #7C3AED;    /* Violet hover */
    --dd-table-bg: #1c2128;              /* Soft dark, not pure black */
    --dd-table-card-bg: #1c2128;
}
```

**Applied to:**
- Checkbox accent color
- Sort indicators
- Hover states
- Border highlights
- Filter pills
- Pagination active state

**Pattern: Glass Morphism with Safari Support**

**Best Practice:** Always include `-webkit-` prefix for Safari 17+ compatibility

```css
.config-panel {
    background: rgba(28, 33, 40, 0.6);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);  /* Required for Safari */
    border: 1px solid rgba(255, 255, 255, 0.1);
}
```

**Pattern: Table Design System (2025 Best Practices)**

**Avoid:** Pure black backgrounds (`#000000`)
**Use:** Soft dark backgrounds (`#1c2128`) for better readability and modern aesthetics

**Rationale:**
- Pure black creates harsh contrast with white text
- Soft dark (#1c2128) reduces eye strain
- Aligns with 2025 UI/UX trends (GitHub, Linear, Vercel design systems)
- Better visual hierarchy with subtle gradients

**Pattern: DataTable Virtual Scrolling - Row Parity Computation**

**Problem:** CSS `:nth-child(even)` selector breaks with virtual scrolling because it counts DOM position (1-20) rather than data index (100-120).

**Solution:** Use Alpine.js computed class binding based on actual data index

```html
<!-- In template with virtual scrolling -->
<template x-for="(row, index) in visibleData" :key="row.id">
    <tr class="dd-table-row"
        :class="{
            'selected': isSelected(row.id),
            'expanded': isExpanded(row.id),
            'even-row': (startIndex + index) % 2 === 1
        }">
        <!-- Row content -->
    </tr>
</template>
```

```css
/* In dataTable.css */
.dd-table-row.even-row {
    background: var(--dd-table-row-alt);
}
```

**Technical Details:**
- Virtual scrolling renders only visible rows (e.g., rows 100-120 of 1000)
- DOM positions reset for each render (1-20), but data indices remain (100-120)
- Computing `(startIndex + index) % 2 === 1` maintains consistent alternating row colors
- `:nth-child()` CSS selectors DO NOT work with virtual scrolling - always use computed classes

**Files Affected:**
- `dojo/static/dojo/css/components/dataTable.css:229` - Removed `:nth-child(even)` rule
- `dojo/templates/dojo/findings_list_modern.html:297` - Added `:class` binding
- `dojo/templates/dojo/engagements_modern.html:294` - Added `:class` binding
- `dojo/templates/dojo/product_modern.html:344` - Added `:class` binding

## Development Guidelines

### Code Standards
- **Python Version:** Python 3.13 compliant (target-version in ruff.toml)
- **Line Length:** 120 characters
- **Linting:** Ruff with extensive rule set (see ruff.toml)
- **Code Style:** PEP8 compliance required
- **Tests:** All changes must pass existing tests in `tests/` and `unittests/`

### Branch Strategy
- **Base PRs against:** `dev` or `bugfix` branch (NOT `master`)
- **Master branch:** Production releases only

### Testing Requirements
- Unit tests in `unittests/` directory
- Parser tests require sample scan files in `unittests/scans/<tool_name>/`
- Integration tests via `./run-integration-tests.sh`
- Test fixtures in `dojo/fixtures/`
- Django TestCase with custom `DjangoTestCase` base class (37KB in unittests/dojo_test_case.py)

### Writing New Parsers
See official docs: https://docs.defectdojo.com/en/open_source/contributing/how-to-write-a-parser/

**Quick Reference:**
1. Create `dojo/tools/<tool_name>/parser.py`
2. Implement required methods: `get_scan_types()`, `get_findings()`
3. Add sample scan files to `unittests/scans/<tool_name>/`
4. Write tests in `unittests/tools/test_<tool_name>_parser.py`
5. Update `dojo/tools/__init__.py` if needed

### Pull Request Guidelines
- Get **pre-approval** for enhancements via GitHub issue first
- Include operating system, version, and install type in bug reports
- All integration test scripts must pass
- Code must conform to PEP8 and pass Ruff checks
- Don't resolve reviewer comments without discussion
- Keep changes within the scope of the PR

**Acceptable Changes:**
- New parser for unsupported tool
- Bug fix for existing parser or core feature
- Security vulnerability fixes
- Test improvements

**Pre-approval Required:**
- New fields or data models
- UI changes beyond minor improvements
- New API routes or third-party integrations

### Database Migrations
**IMPORTANT:** Database changes require migrations and proper testing.

```bash
# Generate migration after model changes
docker compose exec uwsgi bash -c "python manage.py makemigrations"

# Review generated migration in dojo/db_migrations/
# Commit migration file to git

# Apply migration
docker compose exec uwsgi bash -c "python manage.py migrate"
```

**Risk Warning:** Downstream forks must carefully manage migrations to avoid conflicts with upstream. Requires knowledge of Django Migrations: https://docs.djangoproject.com/en/5.0/topics/migrations/

### Docker Services Architecture
**Container Services** (docker-compose.yml):
1. **nginx** - Static files, reverse proxy (Alpine-based)
2. **uwsgi** - Django application server
3. **celeryworker** - Background tasks
4. **celerybeat** - Scheduled tasks (cron)
5. **initializer** - DB setup and migrations (runs once)
6. **postgres** - Database
7. **valkey** - Message broker and cache (Redis-compatible)

**Dev Mode:**
```bash
# Set environment to dev
./docker/setEnv.sh dev

# Use dev override
docker compose -f docker-compose.yml -f docker-compose.override.dev.yml up
```

## Common Patterns

### Locality of Behavior
- Keep related code together - queries near the domain logic
- Helper functions in module-specific helper.py files
- Avoid over-abstraction - prefer simple function calls

### Security Considerations
DefectDojo is a security-focused application. When making changes:
- Be vigilant about SQL injection, XSS, CSRF, command injection
- Use Django's built-in protections (ORM, template escaping, CSRF middleware)
- Sanitize user input with `bleach`, `defusedxml`
- Validate file uploads carefully (many parsers handle XML/JSON)
- Be cautious with `eval()` - use `asteval` for safe evaluation
- Follow OWASP Top 10 guidelines

### Finding Deduplication
When working with findings:
- Understand deduplication fields: `hash_code`, `unique_id_from_tool`
- Parser-specific deduplication via `get_dedupe_fields()`
- Complex logic in `dojo/finding/helper.py`
- Re-import operations update existing findings using deduplication

### Notification System
Event-based notifications with multiple channels:
- UI alerts (in-app)
- Email (SMTP configuration)
- Webhooks (HTTP callbacks)
- Slack integration
- Jira issue creation/update
- Async delivery via Celery

## Additional Resources

- **Official Docs:** https://docs.defectdojo.com/
- **REST API Docs:** https://docs.defectdojo.com/en/open_source/api-v2-docs/
- **Supported Tools:** https://docs.defectdojo.com/en/connecting_your_tools/parsers/
- **Contributing Guide:** readme-docs/CONTRIBUTING.md
- **Security Policy:** SECURITY.md
- **Community:** OWASP Slack #defectdojo channel

## Authentication & SSO
Multiple authentication methods supported:
- **Token-based:** DRF tokens for API access
- **Session-based:** Django sessions for web UI
- **OAuth2/SAML2:** via social-auth-app-django and djangosaml2
- **LDAP:** Configuration available
- **Remote User:** SSO integration for enterprise

Configuration via `DD_*` environment variables in settings.
