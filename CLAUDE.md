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
# Build and start services
docker compose build && docker compose up -d

# Get admin credentials
docker compose logs initializer | grep "Admin password:"

# Access at http://localhost:8080
```

### Testing
```bash
# Run specific unit test
./run-unittest.sh --test-case unittests.tools.test_stackhawk_parser.TestStackHawkParser

# Run with verbosity and fail-fast
./run-unittest.sh --test-case <test_path> -v3 --failfast

# Run integration tests
./run-integration-tests.sh
```

### Database Migrations
```bash
docker compose exec uwsgi bash -c "python manage.py makemigrations"
docker compose exec uwsgi bash -c "python manage.py migrate"
```

### Shell Access
```bash
docker compose exec uwsgi bash -c "python manage.py shell"
docker compose exec uwsgi bash
```

### GitHub Integration
```bash
# Validate GitHub setup before sync (pre-flight checks)
docker compose exec uwsgi bash -c "python manage.py validate_github_setup"
docker compose exec uwsgi bash -c "python manage.py validate_github_setup --json"
docker compose exec uwsgi bash -c "python manage.py validate_github_setup --token ghp_xxx --org myorg"

# Sync repository metadata
docker compose exec uwsgi bash -c "python manage.py sync_github_repositories --incremental"

# Sync security alerts and create findings
docker compose exec uwsgi bash -c "python manage.py sync_github_alerts --create-findings"

# Generate insights
docker compose exec uwsgi bash -c "python manage.py generate_insights --category security"

# Build dependency graph
docker compose exec uwsgi bash -c "python manage.py build_dependency_graph"
```

<!-- See detailed docs: dojo/github_collector/README.md -->

### Priority Scoring & Triage
```bash
# Calculate priority scores
docker compose exec uwsgi bash -c "python manage.py calculate_priority_scores"
```

<!-- See detailed docs: dojo/finding/README.md -->

## Architecture Overview

### Monolithic Models with Domain Modules
The codebase uses a **monolithic `dojo/models.py`** (238KB) containing 40+ core models, with feature-specific modules.

**Core Entity Hierarchy:**
- `Product_Type` → `Product` → `Repository` → `Test` → `Finding`
- `Repository` - GitHub repository with 53 enrichment fields
- `GitHubAlert` - Raw GitHub security alerts
- `Engagement` - Time-bound security testing activities

**Key Modules:**
- `dojo/finding/` - Vulnerability management, priority scoring, triage workflow
  <!-- See: dojo/finding/README.md -->
- `dojo/importers/` - Scan file parsing framework
- `dojo/tools/` - 211 security tool parsers
- `dojo/authorization/` - RBAC with roles: Reader, API_Importer, Writer, Maintainer, Owner
- `dojo/api_v2/` - REST API with serializers, permissions, viewsets
- `dojo/github_collector/` - GitHub integration (6 subsystems)
  <!-- See: dojo/github_collector/README.md -->
- `dojo/frontend/` - Modern UI build system
  <!-- See: dojo/frontend/README.md -->

### REST API Architecture
**Base URL:** `/api/v2/`
**Authentication:** Token-based, session-based, OAuth2/SAML2, remote user SSO
**Permissions:** Fine-grained RBAC with 100+ permission types
**Documentation:** OpenAPI/Swagger via drf-spectacular

### Settings & Configuration
Uses **django-split-settings** with environment variable configuration.
**Settings Location:** `dojo/settings/settings.dist.py`
**Environment Variables:** Prefix all configs with `DD_*`

### Async Task Processing
**Celery Configuration:**
- Broker: Valkey/Redis
- Result backend: Django DB or Redis
- Beat scheduler for cron jobs

### Security Tool Integration
**211 supported parsers** in `dojo/tools/<tool_name>/`:
```python
class MyToolParser:
    def get_scan_types(self):
        return ["MyTool Scan"]
    def get_findings(self, file, test):
        # Parse and return Finding objects
```

### GitHub Integration
DefectDojo has seven GitHub integration patterns:
1. **Issue Tracking** - GitHub issue creation/sync
2. **Repository Context Enrichment** - GraphQL-powered metadata collector (47 fields)
3. **Security Alerts Collection** - Dependabot, CodeQL, Secret Scanning
4. **Insights Dashboard** - 31 insights across 6 categories
5. **Product Migration Wizard** - Repository clustering and consolidation
6. **Dependency Graph Analysis** - SBOM-based consumption tracking
7. **Setup Validation** - Pre-flight checks for token scopes, rate limits, and prerequisites

**Validation Features:**
- **Web UI:** "Test Connection" button at `/github/sync/configuration` (6-step validation with real-time feedback)
- **Management Command:** `python manage.py validate_github_setup` (CLI validation with human-readable or JSON output)
- **Exit Codes:** 0=pass, 1=warnings, 2=failures (CI/CD friendly)

<!-- See detailed docs: dojo/github_collector/README.md -->

### Vulnerability Prioritization
Automated vulnerability prioritization based on tier, severity, and risk modifiers:
- **Priority Scoring:** P0-P4 buckets based on tier weight × severity + modifiers
- **Triage Workflow:** State machine with full audit trail
- **Notification Routing:** Priority-based digest batching

<!-- See detailed docs: dojo/finding/README.md -->

### Modern Dashboard UI
Preview feature with Tailwind CSS, Alpine.js, Vite.
- **URLs:** `/dashboard_modern`, `/findings/modern`, `/triage/queue`
- **Design System:** Violet accent (#8B5CF6), soft dark backgrounds (#1c2128)

<!-- See: dojo/frontend/README.md and dojo/frontend/README_PATTERNS.md -->

### Data Persistence Patterns
- **Audit Logging:** django-auditlog
- **History Tracking:** django-pghistory
- **Full-text Search:** django-watson
- **Tags:** django-tagulous
- **Soft Deletes:** Status fields (active, verified, duplicate, false_p, risk_accepted)

### Deduplication System
Complex algorithm for finding duplicate detection:
- Located in `dojo/finding/helper.py`
- Fields: `hash_code`, `unique_id_from_tool`, configurable deduplication keys
- GitHub alerts use: `"github-{type}-{repo_id}-{alert_id}"`

## Development Guidelines

### Code Standards
- **Python Version:** Python 3.13 (target-version in ruff.toml)
- **Line Length:** 120 characters
- **Linting:** Ruff with extensive rule set
- **Tests:** All changes must pass tests in `tests/` and `unittests/`

### Branch Strategy
- **Base PRs against:** `dev` or `bugfix` branch (NOT `master`)
- **Master branch:** Production releases only

### Testing Requirements
- Unit tests in `unittests/` directory
- Parser tests require sample scan files in `unittests/scans/<tool_name>/`
- Integration tests via `./run-integration-tests.sh`

### Writing New Parsers
See official docs: https://docs.defectdojo.com/en/open_source/contributing/how-to-write-a-parser/

### Pull Request Guidelines
- Get **pre-approval** for enhancements via GitHub issue first
- All integration test scripts must pass
- Code must conform to PEP8 and pass Ruff checks

**Acceptable Changes:**
- New parser, bug fix, security fix, test improvements

**Pre-approval Required:**
- New fields/models, UI changes, new API routes

### Database Migrations
```bash
docker compose exec uwsgi bash -c "python manage.py makemigrations"
# Review migration in dojo/db_migrations/
docker compose exec uwsgi bash -c "python manage.py migrate"
```

### Docker Services
1. **nginx** - Static files, reverse proxy
2. **uwsgi** - Django application server
3. **celeryworker** - Background tasks
4. **celerybeat** - Scheduled tasks
5. **postgres** - Database
6. **valkey** - Message broker and cache

## Common Patterns

### Locality of Behavior
- Keep related code together
- Helper functions in module-specific helper.py files
- Avoid over-abstraction

### Security Considerations
- Use Django's built-in protections (ORM, template escaping, CSRF)
- Sanitize user input with `bleach`, `defusedxml`
- Follow OWASP Top 10 guidelines

### Finding Deduplication
- Understand fields: `hash_code`, `unique_id_from_tool`
- Parser-specific deduplication via `get_dedupe_fields()`
- Complex logic in `dojo/finding/helper.py`

### Notification System
Event-based notifications: UI alerts, email, webhooks, Slack, Jira

## Additional Resources

- **Official Docs:** https://docs.defectdojo.com/
- **REST API Docs:** https://docs.defectdojo.com/en/open_source/api-v2-docs/
- **Supported Tools:** https://docs.defectdojo.com/en/connecting_your_tools/parsers/
- **Contributing Guide:** readme-docs/CONTRIBUTING.md
- **Security Policy:** SECURITY.md
- **Community:** OWASP Slack #defectdojo channel

## Module Documentation

Detailed documentation has been moved to module-level READMEs:

| Module | Documentation |
|--------|---------------|
| Finding (Priority/Triage) | `dojo/finding/README.md` |
| GitHub Collector | `dojo/github_collector/README.md` |
| GitHub Insights | `dojo/github_collector/README_INSIGHTS.md` |
| Dependency Graph | `dojo/github_collector/README_DEPENDENCY_GRAPH.md` |
| Security Alerts | `dojo/github_collector/README_ALERTS.md` |
| GraphQL Migration | `dojo/github_collector/README_GRAPHQL.md` |
| Sync UI | `dojo/github_collector/README_SYNC_UI.md` |
| Modern Frontend | `dojo/frontend/README.md` |
| UI Patterns | `dojo/frontend/README_PATTERNS.md` |

## Authentication & SSO

Multiple authentication methods supported:
- **Token-based:** DRF tokens for API access
- **Session-based:** Django sessions for web UI
- **OAuth2/SAML2:** via social-auth-app-django and djangosaml2
- **LDAP:** Configuration available
- **Remote User:** SSO integration for enterprise

Configuration via `DD_*` environment variables in settings.
