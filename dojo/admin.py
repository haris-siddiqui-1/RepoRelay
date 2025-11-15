from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from polymorphic.admin import PolymorphicChildModelAdmin, PolymorphicParentModelAdmin

from dojo.models import (
    Answer,
    Answered_Survey,
    Choice,
    ChoiceAnswer,
    ChoiceQuestion,
    Engagement_Survey,
    GitHubAlert,
    GitHubAlertSync,
    Question,
    Repository,
    TextAnswer,
    TextQuestion,
)

# Conditionally unregister LogEntry from auditlog if it's registered
try:
    from auditlog.models import LogEntry
    admin.site.unregister(LogEntry)
except (ImportError, NotRegistered):
    # auditlog not available or LogEntry not registered
    pass

# ==============================
# Defect Dojo Engaegment Surveys
# ==============================


class QuestionChildAdmin(PolymorphicChildModelAdmin):

    """Base admin class for all child models of Question"""

    base_model = Question


class TextQuestionAdmin(QuestionChildAdmin):

    """ModelAdmin for a TextQuestion"""


class ChoiceQuestionAdmin(QuestionChildAdmin):

    """ModelAdmin for a ChoiceQuestion"""


class QuestionParentAdmin(PolymorphicParentModelAdmin):

    """Question parent model admin"""

    base_model = Question
    child_models = (
        TextQuestion,
        ChoiceQuestion,
    )


admin.site.register(TextQuestion, TextQuestionAdmin)
admin.site.register(ChoiceQuestion, ChoiceQuestionAdmin)
admin.site.register(Question, QuestionParentAdmin)
admin.site.register(Choice)


class AnswerChildAdmin(PolymorphicChildModelAdmin):

    """Base admin class for all child Answer models"""

    base_model = Answer


class TextAnswerAdmin(AnswerChildAdmin):

    """ModelAdmin for TextAnswer"""


class ChoiceAnswerAdmin(AnswerChildAdmin):

    """ModelAdmin for ChoiceAnswer"""


class AnswerParentAdmin(PolymorphicParentModelAdmin):

    """The parent model admin for answer"""

    list_display = (
        "answered_survey",
        "question",
    )

    base_model = Answer
    child_models = (
        TextAnswer,
        ChoiceAnswer,
    )


admin.site.register(TextAnswer, TextAnswerAdmin)
admin.site.register(ChoiceAnswer, ChoiceAnswerAdmin)
admin.site.register(Answer, AnswerParentAdmin)
admin.site.register(Engagement_Survey)
admin.site.register(Answered_Survey)


# ==============================
# Repository Model
# ==============================


class RepositoryAdmin(admin.ModelAdmin):
    """ModelAdmin for Repository"""

    list_display = (
        'name',
        'github_repo_id',
        'product',
        'tier',
        'total_alert_count',
        'last_alert_sync',
    )

    list_filter = (
        'tier',
        'has_ci_cd',
        'has_tests',
        'has_security_scanning',
        'last_alert_sync',
    )

    search_fields = (
        'name',
        'github_url',
        'product__name',
    )

    readonly_fields = (
        'created',
        'updated',
        'cached_finding_counts',
    )

    fieldsets = (
        ('Core Information', {
            'fields': (
                'name',
                'github_repo_id',
                'github_url',
                'product',
                'related_products',
                'tier',
            )
        }),
        ('Activity Tracking', {
            'fields': (
                'last_commit_date',
                'active_contributors_90d',
                'days_since_last_commit',
            )
        }),
        ('Metadata', {
            'fields': (
                'readme_summary',
                'readme_length',
                'primary_language',
                'primary_framework',
            )
        }),
        ('Ownership', {
            'fields': (
                'codeowners_content',
                'ownership_confidence',
            )
        }),
        ('Deployment Signals', {
            'fields': (
                'has_dockerfile',
                'has_kubernetes_config',
                'has_ci_cd',
                'has_terraform',
                'has_deployment_scripts',
                'has_procfile',
            )
        }),
        ('Production Readiness', {
            'fields': (
                'has_environments',
                'has_releases',
                'has_branch_protection',
                'has_monitoring_config',
                'has_ssl_config',
                'has_database_migrations',
            )
        }),
        ('Development Activity', {
            'fields': (
                'recent_commits_30d',
                'active_prs_30d',
                'multiple_contributors',
                'has_dependabot_activity',
                'recent_releases_90d',
                'consistent_commit_pattern',
            )
        }),
        ('Code Organization', {
            'fields': (
                'has_tests',
                'has_documentation',
                'has_api_specs',
                'has_codeowners',
                'has_security_md',
                'is_monorepo',
            )
        }),
        ('Security Maturity', {
            'fields': (
                'has_security_scanning',
                'has_secret_scanning',
                'has_dependency_scanning',
                'has_gitleaks_config',
                'has_sast_config',
            )
        }),
        ('GitHub Alerts', {
            'fields': (
                'last_alert_sync',
                'dependabot_alert_count',
                'codeql_alert_count',
                'secret_scanning_alert_count',
            )
        }),
        ('System Fields', {
            'fields': (
                'cached_finding_counts',
                'created',
                'updated',
            )
        }),
    )


admin.site.register(Repository, RepositoryAdmin)


# ==============================
# GitHub Alert Models
# ==============================


class GitHubAlertAdmin(admin.ModelAdmin):
    """ModelAdmin for GitHubAlert"""

    list_display = (
        'id',
        'repository',
        'alert_type',
        'state',
        'severity',
        'title_truncated',
        'created_at',
        'finding_link',
    )

    list_filter = (
        'alert_type',
        'state',
        'severity',
        'repository',
        'created_at',
    )

    search_fields = (
        'title',
        'github_alert_id',
        'cve',
        'package_name',
        'rule_id',
        'secret_type',
    )

    readonly_fields = (
        'synced_at',
        'created',
    )

    fieldsets = (
        ('Alert Information', {
            'fields': (
                'repository',
                'alert_type',
                'github_alert_id',
                'state',
                'severity',
                'title',
                'description',
                'html_url',
            )
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
                'dismissed_at',
                'fixed_at',
            )
        }),
        ('Dependabot Fields', {
            'fields': (
                'cve',
                'package_name',
                'package_ecosystem',
                'vulnerable_version',
                'patched_version',
            ),
            'classes': ('collapse',),
        }),
        ('CodeQL Fields', {
            'fields': (
                'cwe',
                'rule_id',
                'file_path',
                'start_line',
                'end_line',
            ),
            'classes': ('collapse',),
        }),
        ('Secret Scanning Fields', {
            'fields': (
                'secret_type',
            ),
            'classes': ('collapse',),
        }),
        ('DefectDojo Integration', {
            'fields': (
                'finding',
            )
        }),
        ('Raw Data', {
            'fields': (
                'raw_data',
            ),
            'classes': ('collapse',),
        }),
        ('System Fields', {
            'fields': (
                'synced_at',
                'created',
            )
        }),
    )

    def title_truncated(self, obj):
        """Return truncated title for list display."""
        return obj.title[:75] + '...' if len(obj.title) > 75 else obj.title
    title_truncated.short_description = 'Title'

    def finding_link(self, obj):
        """Return link to associated Finding if exists."""
        if obj.finding:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:dojo_finding_change', args=[obj.finding.id])
            return format_html('<a href="{}">Finding #{}</a>', url, obj.finding.id)
        return '-'
    finding_link.short_description = 'Finding'
    finding_link.allow_tags = True


class GitHubAlertSyncAdmin(admin.ModelAdmin):
    """ModelAdmin for GitHubAlertSync"""

    list_display = (
        'repository',
        'dependabot_last_sync',
        'codeql_last_sync',
        'secret_scanning_last_sync',
        'full_sync_completed',
        'sync_enabled',
    )

    list_filter = (
        'sync_enabled',
        'full_sync_completed',
        'dependabot_last_sync',
    )

    search_fields = (
        'repository__name',
    )

    readonly_fields = (
        'last_sync_error_at',
        'last_rate_limit_hit',
        'created',
        'updated',
    )

    fieldsets = (
        ('Repository', {
            'fields': (
                'repository',
                'sync_enabled',
                'full_sync_completed',
            )
        }),
        ('Last Sync Times', {
            'fields': (
                'dependabot_last_sync',
                'codeql_last_sync',
                'secret_scanning_last_sync',
            )
        }),
        ('Alert Counts', {
            'fields': (
                'dependabot_alerts_fetched',
                'codeql_alerts_fetched',
                'secret_scanning_alerts_fetched',
            )
        }),
        ('Error Tracking', {
            'fields': (
                'last_sync_error',
                'last_sync_error_at',
                'last_rate_limit_hit',
            )
        }),
        ('System Fields', {
            'fields': (
                'created',
                'updated',
            )
        }),
    )


admin.site.register(GitHubAlert, GitHubAlertAdmin)
admin.site.register(GitHubAlertSync, GitHubAlertSyncAdmin)
