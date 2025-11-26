{% load i18n %}
{% load display_tags %}
{% blocktranslate trimmed with id=finding.id product_name=finding.test.engagement.product.name title=finding.title severity=finding.severity score=finding.priority_score finding_url=url|full_url %}
:large_yellow_circle: *P2 Priority Finding* - {{ id }} in {{ product_name }}
*Title:* {{title}}
*Severity:* {{severity}}
*Priority Score:* {{score}}
*Details:* {{ finding_url }}

P2 findings should be reviewed and triaged.
{% endblocktranslate %}
{% if system_settings.disclaimer_notifications and system_settings.disclaimer_notifications.strip %}

_{% trans "Disclaimer" %}:_
{{ system_settings.disclaimer_notifications }}
{% endif %}
