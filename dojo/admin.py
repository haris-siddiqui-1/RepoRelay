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
