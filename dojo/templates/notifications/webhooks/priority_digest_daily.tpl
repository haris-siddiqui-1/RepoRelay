{% load display_tags %}
{% load as_json %}
---
description: {{ description | as_json_no_html_esc }}
title: {{ title | as_json_no_html_esc }}
{% include 'notifications/webhooks/subtemplates/user.tpl' %}
{% if url %}
url_ui:  {{ url | full_url | as_json_no_html_esc }}
{% endif %}
digest_type: "daily"
priority_bucket: "P3"
findings_count: {{ findings|length }}
severity_counts:
{% for severity, count in severity_counts.items %}
  {{ severity }}: {{ count }}
{% endfor %}
{% if system_settings.disclaimer_notifications and system_settings.disclaimer_notifications.strip %}
disclaimer:  {{ system_settings.disclaimer_notifications | as_json_no_html_esc }}
{% endif %}
