{% load i18n %}
{% load display_tags %}
{% if is_escalation %}
{% blocktranslate trimmed with id=finding.id product_name=finding.test.engagement.product.name title=finding.title severity=finding.severity score=finding.priority_score finding_url=url|full_url %}
:rotating_light: *ESCALATED* Finding {{ id }} in {{ product_name }}
*Title:* {{title}}
*Severity:* {{severity}}
*Priority Score:* {{score}}
*Details:* {{ finding_url }}

This finding has been escalated and requires immediate attention.
{% endblocktranslate %}
{% else %}
{% blocktranslate trimmed with id=finding.id product_name=finding.test.engagement.product.name title=finding.title severity=finding.severity bucket=priority_bucket score=finding.priority_score finding_url=url|full_url %}
:red_circle: *{{ bucket }} Priority Alert* - Finding {{ id }} in {{ product_name }}
*Title:* {{title}}
*Severity:* {{severity}}
*Priority Score:* {{score}}
*Details:* {{ finding_url }}

P0/P1 findings require immediate attention.
{% endblocktranslate %}
{% endif %}
{% if system_settings.disclaimer_notifications and system_settings.disclaimer_notifications.strip %}

_{% trans "Disclaimer" %}:_
{{ system_settings.disclaimer_notifications }}
{% endif %}
