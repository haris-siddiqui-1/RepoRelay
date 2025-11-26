{% load i18n %}
{% load display_tags %}
{% blocktranslate trimmed with count=findings|length %}
:calendar: *Weekly P4 Findings Digest* - {{ count }} finding(s)
{% endblocktranslate %}

*{% trans "Summary by Severity" %}:*
{% for severity, count in severity_counts.items %}
• {{ severity }}: {{ count }}
{% endfor %}

*{% trans "Findings by Product" %}:*
{% for product_name, product_findings in findings_by_product.items %}
*{{ product_name }}* ({{ product_findings|length }}):
{% for finding in product_findings|slice:":5" %}
{% url 'view_finding' finding.id as finding_url %}
  - {{ finding.severity }} | {{ finding.title|truncatewords:8 }} | <{{ finding_url|full_url }}|View>
{% endfor %}
{% if product_findings|length > 5 %}
  _...and {{ product_findings|length|add:"-5" }} more_
{% endif %}
{% endfor %}

{% url 'finding' as findings_url %}
P4 findings are informational. <{{ findings_url|full_url }}|{% trans "View all findings" %}>
{% if system_settings.disclaimer_notifications and system_settings.disclaimer_notifications.strip %}

_{% trans "Disclaimer" %}:_
{{ system_settings.disclaimer_notifications }}
{% endif %}
