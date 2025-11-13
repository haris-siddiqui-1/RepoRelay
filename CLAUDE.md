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
**Frontend:** Bootstrap 3.4.1, jQuery 3.7.1, DataTables
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

## Architecture Overview

### Monolithic Models with Domain Modules
The codebase uses a **monolithic `dojo/models.py`** (238KB) containing 40+ core models, with feature-specific modules that extend functionality:

**Core Entity Hierarchy:**
- `Product_Type` → `Product` → `Test` → `Finding`
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
- `dojo/github_collector/` - Repository metadata enrichment with GraphQL API integration (see dojo/github_collector/README_GRAPHQL.md)

### REST API Architecture
**Base URL:** `/api/v2/`

**Design Pattern:** ViewSet-based with DRF
**Authentication:** Token-based, session-based, OAuth2/SAML2, remote user SSO
**Permissions:** Fine-grained RBAC with 100+ permission types (dojo/authorization/roles_permissions.py)
**Documentation:** OpenAPI/Swagger via drf-spectacular

**Key Endpoints:**
- `/products/`, `/engagements/`, `/tests/`, `/findings/`
- `/scan-imports/`, `/re-scan-imports/` - Bulk vulnerability import/update
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

DefectDojo has two GitHub integration patterns:

1. **Issue Tracking** (`dojo/github.py`) - Traditional GitHub issue creation/sync for findings
   - Uses PyGithub REST API
   - Creates/updates GitHub issues for security findings
   - Associated with GITHUB_PKey and GITHUB_Issue models

2. **Repository Context Enrichment** (`dojo/github_collector/`) - NEW GraphQL-powered collector
   - Syncs repository metadata to Product records
   - Detects 36 binary signals (deployment indicators, security posture, activity metrics)
   - Classifies repository tier/criticality
   - **GraphQL API v4 for bulk operations** (15-20x faster incremental syncs)
   - Automatic REST fallback for reliability
   - Management command: `python manage.py sync_github_repositories`
   - See detailed documentation: dojo/github_collector/README_GRAPHQL.md

**GraphQL Migration (January 2025):**
The repository collector now uses GitHub GraphQL API v4 for bulk organization syncs, reducing API calls by 94% and enabling sub-5-minute daily incremental syncs. REST API remains as fallback and for individual repository updates.

**Key Features:**
- Incremental sync: Only fetch repositories updated since last sync
- Query cost: ~40 points per repo (vs 18 REST calls)
- Rate limit monitoring: 5,000 points/hour quota
- Product model enrichment: 36 signal fields + tier classification + ownership data

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
