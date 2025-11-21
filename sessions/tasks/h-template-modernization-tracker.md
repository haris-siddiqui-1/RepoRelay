# DefectDojo Template Modernization Progress Tracker

**Status**: IN PROGRESS
**Created**: 2025-01-20
**Master Plan**: h-comprehensive-ui-modernization.md
**Current Phase**: Phase 1 (URL Routing Switchover)

---

## Progress Summary

| Metric | Count | Percentage |
|--------|-------|------------|
| **Total Templates** | 242 | 100% |
| **Completed** | 11 | 4.5% |
| **Remaining** | 231 | 95.5% |
| **Current Phase** | 1 of 10 | 10% |

---

## Phase 0 - Foundation (COMPLETED ✅)

**Status**: ✅ COMPLETE
**Completed**: 2025-01 (Week 0)
**Templates**: 11/11

### Completed Templates
- [x] base_modern.html
- [x] dashboard_modern.html
- [x] login_modern.html
- [x] findings_list_modern.html
- [x] view_finding_modern.html
- [x] product_modern.html
- [x] view_product_details_modern.html
- [x] engagements_modern.html
- [x] view_eng_modern.html
- [x] test_calendar_modern.html
- [x] view_test_modern.html

---

## Phase 1 - URL Routing Switchover (IN PROGRESS 🔄)

**Status**: 🔄 IN PROGRESS
**Task File**: h-phase1-url-routing-switchover.md
**Timeline**: Week 1 (1 week)
**Templates**: 0/12 (routing changes only)

### Templates to Route (Old → Modern)
- [ ] dashboard.html → dashboard_modern.html
- [ ] findings_list.html → findings_list_modern.html
- [ ] view_finding.html → view_finding_modern.html
- [ ] product.html → product_modern.html
- [ ] view_product_details.html → view_product_details_modern.html
- [ ] engagement.html → engagements_modern.html
- [ ] view_eng.html → view_eng_modern.html
- [ ] view_engagements.html → engagements_modern.html (consolidate)
- [ ] engagements_all.html → engagements_modern.html (consolidate)
- [ ] view_test.html → view_test_modern.html
- [ ] calendar.html → test_calendar_modern.html
- [ ] login.html → login_modern.html

**Actions**: Update view functions, remove old templates

---

## Priority 2 - Finding Management (12 templates)

**Timeline**: Weeks 3-4 (2 weeks)
**Risk**: HIGH (data integrity, deduplication)

### Finding CRUD (5)
- [ ] add_findings.html → add_findings_modern.html (HIGH RISK)
- [ ] add_findings_as_accepted.html → add_findings_as_accepted_modern.html (HIGH RISK)
- [ ] ad_hoc_findings.html → ad_hoc_findings_modern.html
- [ ] edit_finding.html → edit_finding_modern.html (HIGH RISK)
- [ ] close_finding.html → close_finding_modern.html

### Finding Groups (3)
- [ ] finding_groups_list.html → finding_groups_list_modern.html
- [ ] view_finding_group.html → view_finding_group_modern.html
- [ ] delete_finding_group.html → delete_finding_group_modern.html

### Advanced Operations (4)
- [ ] merge_findings.html → merge_findings_modern.html (HIGH RISK)
- [ ] promote_to_finding.html → promote_to_finding_modern.html
- [ ] review_finding.html → review_finding_modern.html
- [ ] clear_finding_review.html → clear_finding_review_modern.html

---

## Priority 3 - Product & Engagement Operations (23 templates)

**Timeline**: Weeks 5-6 (2 weeks)
**Risk**: MEDIUM (RBAC, cascade deletes)

### Product CRUD (3)
- [ ] new_product.html → new_product_modern.html
- [ ] edit_product.html → edit_product_modern.html
- [ ] delete_product.html → delete_product_modern.html

### Product Details (2)
- [ ] product_components.html → product_components_modern.html
- [ ] product_cross_repo_duplicates.html → product_cross_repo_duplicates_modern.html

### Product Members (4)
- [ ] new_product_member.html → new_product_member_modern.html
- [ ] new_product_member_user.html → new_product_member_user_modern.html
- [ ] edit_product_member.html → edit_product_member_modern.html
- [ ] delete_product_member.html → delete_product_member_modern.html

### Product Groups (4)
- [ ] new_product_group.html → new_product_group_modern.html
- [ ] new_product_group_group.html → new_product_group_group_modern.html
- [ ] edit_product_group.html → edit_product_group_modern.html
- [ ] delete_product_group.html → delete_product_group_modern.html

### Product Type (2)
- [ ] product_type.html → product_type_modern.html
- [ ] view_product_type.html → view_product_type_modern.html

### Engagement Operations (8)
- [ ] new_eng.html → new_eng_modern.html
- [ ] delete_engagement.html → delete_engagement_modern.html
- [ ] view_objects_eng.html → view_objects_eng_modern.html
- [ ] engagement_pdf_report.html → engagement_pdf_report_modern.html
- [ ] finding_related_actions.html → finding_related_actions_modern.html
- [ ] finding_related_list.html → finding_related_list_modern.html
- [ ] finding_related_row.html → finding_related_row_modern.html
- [ ] add_related.html → add_related_modern.html

---

## Priority 4 - Tool Integration & Configuration (35 templates)

**Timeline**: Weeks 7-8 (2 weeks)
**Risk**: HIGH (scan imports, credentials)

### Scan Import & Test Management (6)
- [ ] import_scan_results.html → import_scan_results_modern.html (HIGH RISK)
- [ ] add_tests.html → add_tests_modern.html
- [ ] edit_test.html → edit_test_modern.html
- [ ] delete_test.html → delete_test_modern.html
- [ ] test_type.html → test_type_modern.html
- [ ] new_test_type.html → new_test_type_modern.html

### Tool Type Configuration (3)
- [ ] tool_type.html → tool_type_modern.html
- [ ] new_tool_type.html → new_tool_type_modern.html
- [ ] edit_tool_type.html → edit_tool_type_modern.html

### Tool Configuration (3)
- [ ] tool_config.html → tool_config_modern.html
- [ ] new_tool_config.html → new_tool_config_modern.html
- [ ] edit_tool_config.html → edit_tool_config_modern.html

### Tool Product Configuration (3)
- [ ] new_tool_product.html → new_tool_product_modern.html
- [ ] edit_tool_product.html → edit_tool_product_modern.html
- [ ] delete_tool_product.html → delete_tool_product_modern.html

### GitHub Integration (3)
- [ ] github.html → github_modern.html
- [ ] new_github.html → new_github_modern.html
- [ ] delete_github.html → delete_github_modern.html

### JIRA Integration (4)
- [ ] jira.html → jira_modern.html
- [ ] new_jira.html → new_jira_modern.html
- [ ] new_jira_advanced.html → new_jira_advanced_modern.html
- [ ] edit_jira.html → edit_jira_modern.html

### Product API Scan Configuration (4)
- [ ] add_product_api_scan_configuration.html → add_product_api_scan_configuration_modern.html
- [ ] edit_product_api_scan_configuration.html → edit_product_api_scan_configuration_modern.html
- [ ] delete_product_api_scan_configuration.html → delete_product_api_scan_configuration_modern.html
- [ ] view_product_api_scan_configurations.html → view_product_api_scan_configurations_modern.html

### Credentials Management (10)
- [ ] new_cred.html → new_cred_modern.html (SECURITY CRITICAL)
- [ ] edit_cred.html → edit_cred_modern.html (SECURITY CRITICAL)
- [ ] view_cred.html → view_cred_modern.html
- [ ] view_cred_details.html → view_cred_details_modern.html
- [ ] new_cred_product.html → new_cred_product_modern.html
- [ ] view_cred_prod.html → view_cred_prod_modern.html
- [ ] new_cred_mapping.html → new_cred_mapping_modern.html
- [ ] view_cred_all_details.html → view_cred_all_details_modern.html
- [ ] edit_cred_all.html → edit_cred_all_modern.html
- [ ] delete_cred_all.html → delete_cred_all_modern.html

---

## Priority 5 - Reports & Metrics (27 templates)

**Timeline**: Weeks 9-10 (2 weeks)
**Risk**: MEDIUM (performance, PDF generation)

### Dashboard & Metrics (6)
- [ ] dashboard-metrics.html → dashboard_metrics_modern.html
- [ ] metrics.html → metrics_modern.html
- [ ] simple_metrics.html → simple_metrics_modern.html
- [ ] engineer_metrics.html → engineer_metrics_modern.html
- [ ] product_metrics.html → product_metrics_modern.html
- [ ] pt_counts.html → pt_counts_modern.html

### Report Builder & Outputs (14)
- [ ] report_builder.html → report_builder_modern.html
- [ ] report_widget.html → report_widget_modern.html
- [ ] report_cover_page.html → report_cover_page_modern.html
- [ ] report_endpoints.html → report_endpoints_modern.html
- [ ] report_findings.html → report_findings_modern.html
- [ ] report_filter_snippet.html → report_filter_snippet_modern.html
- [ ] product_pdf_report.html → product_pdf_report_modern.html
- [ ] finding_pdf_report.html → finding_pdf_report_modern.html
- [ ] endpoint_pdf_report.html → endpoint_pdf_report_modern.html
- [ ] test_pdf_report.html → test_pdf_report_modern.html
- [ ] product_endpoint_pdf_report.html → product_endpoint_pdf_report_modern.html
- [ ] product_type_pdf_report.html → product_type_pdf_report_modern.html
- [ ] request_report.html → request_report_modern.html
- [ ] request_endpoint_report.html → request_endpoint_report_modern.html

### Custom HTML Reports (7)
- [ ] custom_html_report.html → custom_html_report_modern.html
- [ ] custom_html_report_cover_page.html → custom_html_report_cover_page_modern.html
- [ ] custom_html_report_endpoint_list.html → custom_html_report_endpoint_list_modern.html
- [ ] custom_html_report_finding_list.html → custom_html_report_finding_list_modern.html
- [ ] custom_html_report_wysiwyg_content.html → custom_html_report_wysiwyg_content_modern.html
- [ ] custom_html_toc.html → custom_html_toc_modern.html

---

## Priority 6 - User & Access Management (25 templates)

**Timeline**: Weeks 11-12 (2 weeks)
**Risk**: HIGH (RBAC, authentication)

### User Management (5)
- [ ] add_user.html → add_user_modern.html
- [ ] delete_user.html → delete_user_modern.html
- [ ] view_user.html → view_user_modern.html
- [ ] users.html → users_modern.html
- [ ] profile.html → profile_modern.html

### Authentication (2)
- [ ] change_pwd.html → change_pwd_modern.html
- [ ] api_v2_key.html → api_v2_key_modern.html

### Group Management (10)
- [ ] groups.html → groups_modern.html
- [ ] add_group.html → add_group_modern.html
- [ ] delete_group.html → delete_group_modern.html
- [ ] view_group.html → view_group_modern.html
- [ ] new_group_member.html → new_group_member_modern.html
- [ ] new_group_member_user.html → new_group_member_user_modern.html
- [ ] delete_group_member.html → delete_group_member_modern.html
- [ ] edit_group_member.html → edit_group_member_modern.html
- [ ] edit_product_group.html → edit_product_group_modern.html
- [ ] delete_product_group.html → delete_product_group_modern.html

### Product Type Access (8)
- [ ] new_product_type.html → new_product_type_modern.html
- [ ] edit_product_type.html → edit_product_type_modern.html
- [ ] delete_product_type.html → delete_product_type_modern.html
- [ ] new_product_type_member.html → new_product_type_member_modern.html
- [ ] new_product_type_member_user.html → new_product_type_member_user_modern.html
- [ ] edit_product_type_member.html → edit_product_type_member_modern.html
- [ ] delete_product_type_member.html → delete_product_type_member_modern.html
- [ ] new_product_type_group.html → new_product_type_group_modern.html

---

## Priority 7 - Endpoint Management (9 templates)

**Timeline**: Weeks 13-14 (2 weeks)
**Risk**: MEDIUM (relationships to findings)

### Endpoint CRUD (5)
- [ ] endpoints.html → endpoints_modern.html
- [ ] view_endpoint.html → view_endpoint_modern.html
- [ ] add_endpoint.html → add_endpoint_modern.html
- [ ] edit_endpoint.html → edit_endpoint_modern.html
- [ ] delete_endpoint.html → delete_endpoint_modern.html

### Endpoint Metadata (3)
- [ ] endpoint_meta_importer.html → endpoint_meta_importer_modern.html
- [ ] add_endpoint_meta_data.html → add_endpoint_meta_data_modern.html
- [ ] edit_endpoint_meta_data.html → edit_endpoint_meta_data_modern.html

### Endpoint Migration (1)
- [ ] migrate_endpoints.html → migrate_endpoints_modern.html

---

## Priority 8 - Risk & Compliance (14 templates)

**Timeline**: Weeks 15-16 (2 weeks)
**Risk**: HIGH (audit trail, compliance requirements)

### Risk Acceptance (3)
- [ ] add_risk_acceptance.html → add_risk_acceptance_modern.html (HIGH RISK)
- [ ] view_risk_acceptance.html → view_risk_acceptance_modern.html
- [ ] remediation_date.html → remediation_date_modern.html

### Regulations & SLA (7)
- [ ] regulations.html → regulations_modern.html
- [ ] regulations_config.html → regulations_config_modern.html
- [ ] new_regulation.html → new_regulation_modern.html
- [ ] edit_regulation.html → edit_regulation_modern.html
- [ ] sla_config.html → sla_config_modern.html
- [ ] new_sla_config.html → new_sla_config_modern.html
- [ ] edit_sla_config.html → edit_sla_config_modern.html

### Compliance Tools (4)
- [ ] benchmark.html → benchmark_modern.html
- [ ] delete_benchmark.html → delete_benchmark_modern.html
- [ ] checklist.html → checklist_modern.html
- [ ] up_threat.html → up_threat_modern.html

---

## Priority 9 - System Settings & Specialized Features (45 templates)

**Timeline**: Weeks 17-18 (2 weeks)
**Risk**: MEDIUM (configuration changes)

### System Settings (3)
- [ ] system_settings.html → system_settings_modern.html
- [ ] edit_presets.html → edit_presets_modern.html
- [ ] view_presets.html → view_presets_modern.html

### Note Types (5)
- [ ] note_type.html → note_type_modern.html
- [ ] add_note_type.html → add_note_type_modern.html
- [ ] edit_note_type.html → edit_note_type_modern.html
- [ ] enable_note_type.html → enable_note_type_modern.html
- [ ] disable_note_type.html → disable_note_type_modern.html

### Notifications (7)
- [ ] alerts.html → alerts_modern.html
- [ ] delete_alerts.html → delete_alerts_modern.html
- [ ] notifications.html → notifications_modern.html
- [ ] add_notification_webhook.html → add_notification_webhook_modern.html
- [ ] edit_notification_webhook.html → edit_notification_webhook_modern.html
- [ ] delete_notification_webhook.html → delete_notification_webhook_modern.html
- [ ] view_notification_webhooks.html → view_notification_webhooks_modern.html

### Announcements (3)
- [ ] announcement.html → announcement_modern.html
- [ ] dismiss_announcement.html → dismiss_announcement_modern.html
- [ ] banner.html → banner_modern.html

### Technology & Dev Environment (7)
- [ ] components.html → components_modern.html
- [ ] new_tech.html → new_tech_modern.html
- [ ] edit_technology.html → edit_technology_modern.html
- [ ] delete_technology.html → delete_technology_modern.html
- [ ] dev_env.html → dev_env_modern.html
- [ ] new_dev_env.html → new_dev_env_modern.html
- [ ] edit_dev_env.html → edit_dev_env_modern.html

### GitHub Insights (2)
- [ ] github_insights_dashboard.html → review for modernization (may already be modern)
- [ ] repository_dashboard.html → repository_dashboard_modern.html

### Product Repository (1)
- [ ] product_repository.html → product_repository_modern.html

### Templates & Finding Templates (3)
- [ ] templates.html → templates_modern.html
- [ ] add_template.html → add_template_modern.html
- [ ] apply_finding_template.html → apply_finding_template_modern.html

### Notes & History (3)
- [ ] edit_note.html → edit_note_modern.html
- [ ] view_note_history.html → view_note_history_modern.html
- [ ] action_history.html → action_history_modern.html

### Metadata Management (2)
- [ ] add_product_meta_data.html → add_product_meta_data_modern.html
- [ ] edit_product_meta_data.html → edit_product_meta_data_modern.html

### File Management (2)
- [ ] manage_files.html → manage_files_modern.html
- [ ] manage_images.html → manage_images_modern.html

### Search (1)
- [ ] simple_search.html → simple_search_modern.html

### Generic Operations (4)
- [ ] copy_object.html → copy_object_modern.html
- [ ] delete_object.html → delete_object_modern.html
- [ ] edit_object.html → edit_object_modern.html
- [ ] new_object.html → new_object_modern.html

### Utility (2)
- [ ] support.html → support_modern.html
- [ ] datatable_demo.html → datatable_demo_modern.html

---

## Priority 10 - UI Components & Final Cleanup (25 templates)

**Timeline**: Weeks 19-20 (2 weeks)
**Risk**: LOW (reusable components)

### Breadcrumbs (5)
- [ ] breadcrumbs/custom_breadcrumb.html → breadcrumbs/custom_breadcrumb_modern.html
- [ ] breadcrumbs/endpoint_breadcrumb.html → breadcrumbs/endpoint_breadcrumb_modern.html
- [ ] breadcrumbs/engagement_breadcrumb.html → breadcrumbs/engagement_breadcrumb_modern.html
- [ ] breadcrumbs/finding_breadcrumb.html → breadcrumbs/finding_breadcrumb_modern.html
- [ ] breadcrumbs/settings_breadcrumb.html → breadcrumbs/settings_breadcrumb_modern.html

### Snippets (10)
- [ ] snippets/comments.html → snippets/comments_modern.html
- [ ] snippets/endpoints.html → snippets/endpoints_modern.html
- [ ] snippets/engagement_list.html → snippets/engagement_list_modern.html
- [ ] snippets/file_images.html → snippets/file_images_modern.html
- [ ] snippets/risk_acceptance_actions_snippet.html → snippets/risk_acceptance_actions_snippet_modern.html
- [ ] snippets/risk_acceptance_actions_snippet_js.html → snippets/risk_acceptance_actions_snippet_js_modern.html
- [ ] snippets/selectpicker_in_dropdown.html → snippets/selectpicker_in_dropdown_modern.html
- [ ] snippets/sonarqube_history.html → snippets/sonarqube_history_modern.html
- [ ] snippets/tags.html → snippets/tags_modern.html
- [ ] paging_snippet.html → paging_snippet_modern.html

### Form Components (5)
- [ ] form_fields.html → form_fields_modern.html
- [ ] filter_snippet.html → filter_snippet_modern.html
- [ ] filter_js_snippet.html → filter_js_snippet_modern.html
- [ ] apply_finding_template_form_fields.html → apply_finding_template_form_fields_modern.html
- [ ] view_objects.html → view_objects_modern.html

### Other Review/Actions (5)
- [ ] defect_finding_review.html → defect_finding_review_modern.html
- [ ] finding_groups_list_snippet.html → finding_groups_list_snippet_modern.html
- [ ] findings_list_snippet.html → findings_list_snippet_modern.html
- [ ] view_engineer.html → view_engineer_modern.html
- [ ] view_tool_product_all.html → view_tool_product_all_modern.html

---

## Testing Pattern (Apply to Each Phase)

1. **Architectural Review**: Review views, URL patterns, data models
2. **Context7 Validation**: Query Django/Alpine.js/Tailwind docs
3. **Security Review**: Check CSRF, XSS, permission decorators
4. **Playwright Tests**: Write 20+ UI tests per phase
5. **Staging Deployment**: Deploy and manual test
6. **Production Deployment**: Deploy with monitoring

---

## Risk Levels

- **HIGH RISK**: Data integrity, security, deduplication, audit trail
- **MEDIUM RISK**: RBAC, relationships, cascade deletes, performance
- **LOW RISK**: Read-only views, simple forms, snippets

---

## Rollback Procedure (Same for All Phases)

```bash
# Quick rollback
git revert HEAD
cd dojo/frontend && npm run build && cd ../..
docker compose exec uwsgi bash -c "python manage.py collectstatic --noinput"
docker compose exec uwsgi bash -c "kill -HUP 1"

# Database rollback (if corruption)
docker compose stop uwsgi
docker compose exec postgres psql -U defectdojo defectdojo < backup_prod_YYYYMMDD.sql
docker compose up -d
```

---

## Documentation Updates

- Update this tracker after each template completion
- Update CLAUDE.md after each phase completion
- Create phase-specific task file only if complexity warrants it
- Update h-comprehensive-ui-modernization.md with lessons learned

---

**Last Updated**: 2025-01-20
**Next Update**: After Phase 1 completion
