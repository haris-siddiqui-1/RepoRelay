{% load display_tags %}
{% load as_json %}
---
description: {{ description | as_json_no_html_esc }}
title: {{ title | as_json_no_html_esc }}
{% include 'notifications/webhooks/subtemplates/user.tpl' %}
{% if url %}
url_ui:  {{ url | full_url | as_json_no_html_esc }}
{% endif %}
priority_bucket: {{ priority_bucket | as_json_no_html_esc }}
{% if finding %}
finding_id: {{ finding.id }}
finding_severity: {{ finding.severity | as_json_no_html_esc }}
finding_priority_score: {{ finding.priority_score }}
{% if finding.cve %}
finding_cve: {{ finding.cve | as_json_no_html_esc }}
{% endif %}
{% endif %}
{% if is_escalation %}
is_escalation: true
{% endif %}
{% if system_settings.disclaimer_notifications and system_settings.disclaimer_notifications.strip %}
disclaimer:  {{ system_settings.disclaimer_notifications | as_json_no_html_esc }}
{% endif %}
