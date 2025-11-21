# Task: Phase 1 - Direct Modern UI Switchover

**Status**: READY TO START
**Priority**: P0 (Critical)
**Created**: 2025-01-20
**Estimated Duration**: 1 week
**Parent Task**: h-comprehensive-ui-modernization.md
**Phase**: 1 of 10
**Owner**: TBD

---

## Executive Summary

Phase 1 switches all Django views from old Bootstrap 3 templates to modern Tailwind CSS templates for the 12 most critical DefectDojo pages. This is a **direct switchover** with no feature flags or gradual rollout - all users will see the modern UI immediately after deployment.

**Success Definition**:
- All 12 old templates removed from codebase
- All views updated to use modern templates
- Zero 404 errors on existing URLs
- Page load time improved >30%
- Zero data integrity issues
- All tests passing

---

## Objectives

### Primary Objectives
1. Update 12 view functions to render modern templates
2. Remove 12 old Bootstrap 3 templates
3. Validate with automated tests (Playwright + Django unit tests)
4. Deploy to production with zero downtime

### Secondary Objectives
1. Establish testing patterns for future phases
2. Validate Context7 documentation review process
3. Document deployment procedures
4. Gather initial user feedback

---

## Scope

### Templates to Switch (12)

| Old Template | Modern Template | View File | View Function |
|-------------|----------------|-----------|---------------|
| dashboard.html | dashboard_modern.html | dojo/home/views.py | dashboard() |
| findings_list.html | findings_list_modern.html | dojo/finding/views.py | findings_list() |
| view_finding.html | view_finding_modern.html | dojo/finding/views.py | view_finding() |
| product.html | product_modern.html | dojo/product/views.py | product_list() |
| view_product_details.html | view_product_details_modern.html | dojo/product/views.py | view_product_details() |
| engagement.html | engagements_modern.html | dojo/engagement/views.py | engagements() |
| view_eng.html | view_eng_modern.html | dojo/engagement/views.py | view_engagement() |
| view_engagements.html | engagements_modern.html | dojo/engagement/views.py | view_engagements() |
| engagements_all.html | engagements_modern.html | dojo/engagement/views.py | engagements_all() |
| view_test.html | view_test_modern.html | dojo/test/views.py | view_test() |
| calendar.html | test_calendar_modern.html | dojo/test/views.py | test_calendar() |
| login.html | login_modern.html | dojo/user/views.py | login_view() |

**Note**: Modern templates already exist and have been validated with real data.

### Out of Scope
- Feature flags (not needed)
- Gradual rollout (direct switchover)
- Database migrations (not needed)
- API endpoint changes (not needed)

---

## Implementation Plan

### Day 1-2: Architectural Testing & Context7 Review

#### Task 1.1: View Function Updates
**Goal**: Update all 12 view functions to use modern templates

**Files to Update**:
- `dojo/home/views.py` - dashboard()
- `dojo/finding/views.py` - findings_list(), view_finding()
- `dojo/product/views.py` - product_list(), view_product_details()
- `dojo/engagement/views.py` - engagements(), view_engagement(), view_engagements(), engagements_all()
- `dojo/test/views.py` - view_test(), test_calendar()
- `dojo/user/views.py` - login_view()

**Example Change**:
```python
# BEFORE
def dashboard(request):
    # ... existing logic ...
    return render(request, 'dojo/dashboard.html', context)

# AFTER
def dashboard(request):
    # ... existing logic ...
    return render(request, 'dojo/dashboard_modern.html', context)
```

**Checklist**:
- [ ] Update dojo/home/views.py (dashboard)
- [ ] Update dojo/finding/views.py (findings_list, view_finding)
- [ ] Update dojo/product/views.py (product_list, view_product_details)
- [ ] Update dojo/engagement/views.py (4 functions)
- [ ] Update dojo/test/views.py (view_test, test_calendar)
- [ ] Update dojo/user/views.py (login_view)
- [ ] Verify all context variables match modern templates
- [ ] Run Django unit tests: `./run-unittest.sh`

**Deliverable**: Updated view functions (Git branch: feature/phase1-modern-ui-switchover)

#### Task 1.2: Context7 Documentation Validation
**Goal**: Validate implementations against official framework docs

**Context7 Queries**:

**Django Validation**:
```python
# Query 1: Template rendering best practices
mcp_call("context7", "resolve-library-id", {"libraryName": "django"})
mcp_call("context7", "get-library-docs", {
    "context7CompatibleLibraryID": "/django/django",
    "topic": "template rendering render function"
})

# Query 2: CSRF protection
mcp_call("context7", "get-library-docs", {
    "context7CompatibleLibraryID": "/django/django",
    "topic": "csrf protection templates"
})
```

**Alpine.js Validation**:
```python
# Query 1: Component registration
mcp_call("context7", "resolve-library-id", {"libraryName": "alpinejs"})
mcp_call("context7", "get-library-docs", {
    "context7CompatibleLibraryID": "/alpinejs/alpine",
    "topic": "component registration Alpine.data"
})

# Query 2: Virtual scrolling patterns
mcp_call("context7", "get-library-docs", {
    "context7CompatibleLibraryID": "/alpinejs/alpine",
    "topic": "performance large lists"
})
```

**Tailwind CSS Validation**:
```python
# Query 1: Dark mode implementation
mcp_call("context7", "resolve-library-id", {"libraryName": "tailwindcss"})
mcp_call("context7", "get-library-docs", {
    "context7CompatibleLibraryID": "/tailwindlabs/tailwindcss",
    "topic": "dark mode configuration"
})
```

**Validation Checklist**:
- [ ] All render() calls use correct template path
- [ ] All forms have {% csrf_token %}
- [ ] All static files use {% load static %}
- [ ] Alpine.js components properly registered
- [ ] DataTable component used correctly
- [ ] Tailwind dark mode classes correct
- [ ] No deprecated Django template tags

**Deliverable**: Context7 validation report (Markdown)

#### Task 1.3: Security Review
**Goal**: Ensure no security vulnerabilities

**Security Checklist**:
- [ ] All forms have CSRF tokens
- [ ] No {{ var|safe }} without justification
- [ ] No JavaScript eval() or Function()
- [ ] No inline event handlers (onclick, onload)
- [ ] JSON data properly escaped
- [ ] URL parameters validated in views
- [ ] Permission decorators enforced (@user_has_permission)
- [ ] No secrets in templates

**Tools**:
```bash
# Django security check
python manage.py check --deploy

# Python security linter
bandit -r dojo/

# JavaScript linter
cd dojo/frontend && npm run lint
```

**Deliverable**: Security audit report

### Day 3-4: Playwright UI Testing

#### Task 2.1: Write Playwright Test Suite
**Goal**: Comprehensive automated UI tests for all 12 pages

**Test File**: `tests/ui/phase1_modern_ui.spec.js`

**Test Coverage**:
1. **Dashboard** (2 tests)
   - Page loads correctly
   - Metrics cards and charts render

2. **Findings List** (4 tests)
   - Page loads with DataTable
   - Search functionality works
   - Sorting works (Severity column)
   - Bulk selection works

3. **Finding Detail** (1 test)
   - Page loads with sidebar and cards

4. **Products List** (2 tests)
   - Grid view loads
   - Grid/list toggle works

5. **Product Detail** (1 test)
   - Page loads with metrics

6. **Engagements List** (1 test)
   - Page loads with DataTable

7. **Engagement Detail** (1 test)
   - Page loads with test list

8. **Test Detail** (1 test)
   - Page loads with findings

9. **Test Calendar** (1 test)
   - FullCalendar renders

10. **Login** (1 test)
    - Login form works

11. **Navigation Flow** (1 test)
    - Navigate through all pages

12. **Responsive Design** (2 tests)
    - Mobile (375px)
    - Tablet (768px)

13. **Performance** (1 test)
    - All pages load <2s

**Example Test**:
```javascript
const { test, expect } = require('@playwright/test');

test.describe('Phase 1: Modern UI Switchover', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:8080/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', process.env.DD_ADMIN_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForNavigation();
  });

  test('dashboard loads with modern UI', async ({ page }) => {
    await page.goto('http://localhost:8080/dashboard');

    // Verify modern template elements
    await expect(page.locator('h1')).toContainText('Dashboard');
    await expect(page.locator('.enterprise-card')).toBeVisible();
    await expect(page.locator('canvas')).toBeVisible(); // Chart.js

    // Verify no console errors
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    await page.reload();
    expect(errors).toHaveLength(0);

    // Screenshot
    await page.screenshot({ path: 'screenshots/dashboard-modern.png' });
  });

  test('findings list search and sort work', async ({ page }) => {
    await page.goto('http://localhost:8080/finding');

    // Test search
    await page.fill('input[placeholder*="Search"]', 'SQL');
    await page.waitForTimeout(500);
    const searchResults = await page.locator('tbody tr').count();
    expect(searchResults).toBeGreaterThan(0);

    // Test sorting
    await page.click('th:has-text("Severity")');
    await page.waitForTimeout(300);
    const firstSeverity = await page.locator('tbody tr:first-child .dd-severity-badge').textContent();
    expect(['Critical', 'High']).toContain(firstSeverity.trim());

    await page.screenshot({ path: 'screenshots/findings-modern.png' });
  });

  test('navigation flow works', async ({ page }) => {
    // Dashboard → Findings → Finding Detail → Product → Engagement → Test
    await page.goto('http://localhost:8080/dashboard');
    await page.click('a[href*="/finding"]');
    await expect(page).toHaveURL(/\/finding/);

    await page.click('tbody tr:first-child td:nth-child(3)'); // Click title
    await expect(page).toHaveURL(/\/finding\/\d+/);

    await page.click('a[href*="/product/"]');
    await expect(page).toHaveURL(/\/product\/\d+/);

    await page.click('a[href*="/engagement/"]');
    await expect(page).toHaveURL(/\/engagement\/\d+/);

    await page.click('a[href*="/test/"]');
    await expect(page).toHaveURL(/\/test\/\d+/);
  });

  test('performance - pages load under 2 seconds', async ({ page }) => {
    const pages = ['/dashboard', '/finding', '/product', '/engagement'];

    for (const path of pages) {
      const startTime = Date.now();
      await page.goto(`http://localhost:8080${path}`);
      const loadTime = Date.now() - startTime;

      console.log(`${path} load time: ${loadTime}ms`);
      expect(loadTime).toBeLessThan(2000);
    }
  });
});
```

**Checklist**:
- [ ] Install Playwright: `npm install -D @playwright/test`
- [ ] Create playwright.config.js
- [ ] Write 20+ test cases
- [ ] Test all 12 pages
- [ ] Test navigation flow
- [ ] Test responsive design
- [ ] Test performance
- [ ] All tests pass: `npx playwright test`

**Deliverable**: Playwright test suite with HTML report

#### Task 2.2: Run Playwright Tests Locally
**Goal**: Verify all tests pass before deployment

**Commands**:
```bash
# Install browsers
npx playwright install

# Run tests (headless)
npx playwright test

# Run tests with UI
npx playwright test --headed

# Generate HTML report
npx playwright test --reporter=html
npx playwright show-report

# Run specific test
npx playwright test tests/ui/phase1_modern_ui.spec.js
```

**Checklist**:
- [ ] All tests pass in headless mode
- [ ] Screenshots captured
- [ ] HTML report generated
- [ ] No console errors
- [ ] Performance targets met (<2s)

**Deliverable**: Playwright HTML report + 12 screenshots

### Day 5: Remove Old Templates

#### Task 3.1: Remove Old Templates from Codebase
**Goal**: Clean up by removing 12 old Bootstrap 3 templates

**Templates to Remove**:
```bash
rm dojo/templates/dojo/dashboard.html
rm dojo/templates/dojo/findings_list.html
rm dojo/templates/dojo/view_finding.html
rm dojo/templates/dojo/product.html
rm dojo/templates/dojo/view_product_details.html
rm dojo/templates/dojo/engagement.html
rm dojo/templates/dojo/view_eng.html
rm dojo/templates/dojo/view_engagements.html
rm dojo/templates/dojo/engagements_all.html
rm dojo/templates/dojo/view_test.html
rm dojo/templates/dojo/calendar.html
rm dojo/templates/dojo/login.html
```

**Checklist**:
- [ ] Remove all 12 old templates
- [ ] Verify no other files reference old templates (grep search)
- [ ] Run Django unit tests: `./run-unittest.sh`
- [ ] Run Playwright tests: `npx playwright test`
- [ ] Commit changes: `git commit -m "feat: Switch to modern UI for core pages"`

**Deliverable**: Git commit removing old templates

#### Task 3.2: Update Documentation
**Goal**: Document the modern UI patterns

**Files to Update**:
- `CLAUDE.md` - Add modern UI section
- `dojo/frontend/README.md` - Update with Phase 1 completion

**CLAUDE.md Addition**:
```markdown
### Modern UI (January 2025)

DefectDojo uses a modern enterprise design system:
- **CSS Framework**: Tailwind CSS 3.4.0
- **JavaScript**: Alpine.js 3.13.3
- **Build Tool**: Vite 5.0.10
- **Charts**: Chart.js 4.4.1
- **Theme**: Dark-mode-first (#0f1419 background, #8B5CF6 accent)

**Modern Templates** (Phase 1 - Completed):
- Dashboard: dashboard_modern.html
- Findings: findings_list_modern.html, view_finding_modern.html
- Products: product_modern.html, view_product_details_modern.html
- Engagements: engagements_modern.html, view_eng_modern.html
- Tests: view_test_modern.html, test_calendar_modern.html
- Login: login_modern.html

**DataTable Component**: All list views use the reusable DataTable Alpine.js component with virtual scrolling, sorting, filtering, and bulk actions.

**Build Process**:
```bash
cd dojo/frontend
npm run build
docker compose exec uwsgi bash -c "python manage.py collectstatic --noinput"
```
```

**Checklist**:
- [ ] Update CLAUDE.md
- [ ] Update dojo/frontend/README.md
- [ ] Commit: `git commit -m "docs: Update documentation for Phase 1 modern UI"`

**Deliverable**: Updated documentation

### Day 6-7: Deployment

#### Task 4.1: Staging Deployment
**Goal**: Deploy to staging and validate

**Pre-Deployment Checklist**:
- [ ] All unit tests pass: `./run-unittest.sh`
- [ ] All integration tests pass: `./run-integration-tests.sh`
- [ ] All Playwright tests pass: `npx playwright test`
- [ ] Code reviewed and approved
- [ ] Database backup created (staging)

**Deployment Steps**:
```bash
# 1. Backup staging database
docker compose exec postgres pg_dump -U defectdojo defectdojo > backup_staging_$(date +%Y%m%d_%H%M%S).sql

# 2. Pull latest code
git checkout feature/phase1-modern-ui-switchover
git pull origin feature/phase1-modern-ui-switchover

# 3. Build frontend
cd dojo/frontend
npm install
npm run build
cd ../..

# 4. Collect static files
docker compose exec uwsgi bash -c "python manage.py collectstatic --noinput"

# 5. Restart services (zero-downtime)
docker compose exec uwsgi bash -c "kill -HUP 1"
docker compose restart nginx

# 6. Clear cache
docker compose exec uwsgi bash -c "python manage.py shell -c \"from django.core.cache import cache; cache.clear()\""

# 7. Health check
curl http://staging.defectdojo.local/health
```

**Post-Deployment Validation**:
- [ ] Health check returns 200
- [ ] Login works
- [ ] Dashboard loads (modern UI)
- [ ] Findings list loads (modern UI)
- [ ] Products list loads (modern UI)
- [ ] Navigation works across all pages
- [ ] No 500 errors in logs
- [ ] Static assets load from nginx

**Deliverable**: Staging deployment confirmation

#### Task 4.2: Staging Manual Testing
**Goal**: Manual validation in staging

**Test Scenarios**:

1. **Dashboard**
   - [ ] Metrics cards display correct numbers
   - [ ] Charts render (Chart.js)
   - [ ] Links work (Findings, Products, Engagements)

2. **Findings List**
   - [ ] DataTable displays 25 findings
   - [ ] Search works (type "SQL")
   - [ ] Sort works (click Severity column)
   - [ ] Bulk select works (select 3 findings)
   - [ ] Pagination info correct

3. **Finding Detail**
   - [ ] Sidebar shows metadata
   - [ ] Cards display correctly
   - [ ] Back to Findings link works

4. **Products List**
   - [ ] Grid view shows product cards
   - [ ] List toggle switches to DataTable
   - [ ] Search works

5. **Product Detail**
   - [ ] Metrics cards display
   - [ ] Engagement list shows
   - [ ] Recent findings displayed

6. **Engagements List**
   - [ ] DataTable shows engagements
   - [ ] Search works

7. **Engagement Detail**
   - [ ] Test list displays
   - [ ] Sidebar shows details

8. **Test Detail**
   - [ ] Test information card
   - [ ] Findings list shows
   - [ ] Statistics correct

9. **Test Calendar**
   - [ ] FullCalendar renders
   - [ ] Tests display on calendar
   - [ ] Filter by lead works

10. **Login**
    - [ ] Login form works
    - [ ] Redirects to dashboard after login

11. **Navigation Flow**
    - [ ] Dashboard → Findings → Finding Detail → Product → Engagement → Test
    - [ ] All links work
    - [ ] Breadcrumbs correct

12. **Responsive Design**
    - [ ] Test on mobile (375px)
    - [ ] Test on tablet (768px)
    - [ ] Test on desktop (1920px)

**Deliverable**: Staging validation report (pass/fail)

#### Task 4.3: Production Deployment
**Goal**: Deploy to production

**Pre-Deployment Checklist**:
- [ ] All staging tests passed
- [ ] Stakeholders approved
- [ ] Database backup created (production)
- [ ] Rollback procedure reviewed
- [ ] Monitoring dashboards ready

**Deployment Steps**:
```bash
# 1. Backup production database
docker compose exec postgres pg_dump -U defectdojo defectdojo > backup_prod_$(date +%Y%m%d_%H%M%S).sql

# 2. Merge to main
git checkout main
git merge feature/phase1-modern-ui-switchover
git push origin main

# 3. Build frontend (on production server)
cd dojo/frontend
npm install
npm run build
cd ../..

# 4. Collect static files
docker compose exec uwsgi bash -c "python manage.py collectstatic --noinput"

# 5. Restart services (zero-downtime)
docker compose exec uwsgi bash -c "kill -HUP 1"
docker compose restart nginx

# 6. Clear cache
docker compose exec uwsgi bash -c "python manage.py shell -c \"from django.core.cache import cache; cache.clear()\""

# 7. Health check
curl https://defectdojo.prod/health
```

**Post-Deployment Monitoring** (0-24 hours):
- [ ] Error rate <0.5% (Django logs)
- [ ] Page load time <2s (Chrome DevTools)
- [ ] No 404 errors (nginx logs)
- [ ] User complaints <5 (Slack, email)
- [ ] Database queries stable (no N+1)

**Monitoring Commands**:
```bash
# Watch Django logs
docker compose logs -f uwsgi | grep ERROR

# Watch nginx logs
docker compose logs -f nginx | grep "404\|500"

# Check memory usage
docker stats

# Check database connections
docker compose exec postgres psql -U defectdojo -c "SELECT count(*) FROM pg_stat_activity;"
```

**Deliverable**: Production deployment confirmation

---

## Rollback Procedures

### Immediate Rollback (0-2 hours)
**Trigger**: Critical bugs, error rate >5%, page load >5s

**Steps**:
```bash
# 1. Revert git commit
git revert HEAD
git push origin main

# 2. Rebuild frontend
cd dojo/frontend && npm run build && cd ../..
docker compose exec uwsgi bash -c "python manage.py collectstatic --noinput"

# 3. Restart services
docker compose exec uwsgi bash -c "kill -HUP 1"
docker compose restart nginx

# 4. Clear cache
docker compose exec uwsgi bash -c "python manage.py shell -c \"from django.core.cache import cache; cache.clear()\""

# 5. Notify stakeholders
# Post in Slack #incidents channel
```

**Decision Maker**: Engineering Lead or on-call engineer

### Database Rollback (if corruption)
**Trigger**: Data loss, database errors

**Steps**:
```bash
# 1. Stop services
docker compose stop uwsgi

# 2. Restore database
docker compose exec postgres psql -U defectdojo -c "DROP DATABASE defectdojo;"
docker compose exec postgres psql -U defectdojo -c "CREATE DATABASE defectdojo;"
docker compose exec postgres psql -U defectdojo defectdojo < backup_prod_YYYYMMDD_HHMMSS.sql

# 3. Restart services
docker compose up -d

# 4. Verify data
# Login and check dashboard, findings, products
```

**Decision Maker**: CTO or Engineering Director

---

## Success Metrics

### Technical Metrics
- ✅ **Zero 404 Errors**: No broken URLs
- ✅ **Page Load Time**: <2s for all 12 pages
- ✅ **Error Rate**: <0.5%
- ✅ **Test Coverage**: 20+ Playwright tests passing
- ✅ **Zero Regressions**: All functionality works

### User Metrics
- ✅ **User Complaints**: <5 in first week
- ✅ **Support Tickets**: <3 UI-related tickets

### Business Metrics
- ✅ **Zero Downtime**: Zero-downtime deployment achieved
- ✅ **Timeline**: Phase 1 completed within 1 week

---

## Deliverables Checklist

### Code Changes
- [ ] Updated view functions (12 functions)
- [ ] Removed old templates (12 files)
- [ ] Playwright test suite (tests/ui/phase1_modern_ui.spec.js)
- [ ] Updated documentation (CLAUDE.md, README.md)

### Testing
- [ ] Context7 validation report
- [ ] Security audit report
- [ ] Playwright HTML report + screenshots
- [ ] Staging validation report

### Deployment
- [ ] Staging deployment confirmation
- [ ] Production deployment confirmation
- [ ] Post-deployment monitoring report

---

## Risk Register

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| User confusion with new UI | Medium | Medium | In-app feedback form, support documentation |
| Performance degradation | High | Low | Performance testing, monitoring |
| Data loss during deployment | Critical | Very Low | Database backups |
| Missing context variables | Medium | Low | Thorough testing in staging |
| Broken external integrations | Low | Very Low | No API changes |

---

## Communication Plan

### Internal
- **Daily Standup**: Progress updates during implementation week
- **Slack**: #ui-modernization channel
- **Post-Deployment**: Email to stakeholders

### User
- **Pre-Deployment**: In-app banner 2 days before deployment
- **Post-Deployment**: Changelog with UI screenshots
- **Always**: Feedback form on every page

### Documentation
- Update CLAUDE.md with modern UI section
- Update README.md with Phase 1 completion status

---

## Next Steps After Phase 1

1. **Retrospective**: What went well, what didn't, lessons learned
2. **User Feedback**: Gather feedback for 1 week post-deployment
3. **Phase 2 Planning**: Finding Management Operations (12 CRUD forms)
4. **Update Timeline**: Adjust remaining phases if needed

---

## Notes

- No feature flags = simpler implementation
- Direct switchover = faster deployment
- Modern templates already validated with real data
- Playwright provides confidence in automated testing
- Context7 ensures framework best practices
- Zero-downtime deployment with uWSGI reload

---

**End of Phase 1 Task Specification**
