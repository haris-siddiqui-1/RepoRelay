{% load i18n %}
{% load display_tags %}
{% if is_escalation %}
{% blocktranslate trimmed with id=finding.id title=finding.title severity=finding.severity %}
ESCALATED: {{ severity }} Finding #{{ id }} - {{ title }}
{% endblocktranslate %}
{% else %}
{% blocktranslate trimmed with bucket=priority_bucket id=finding.id title=finding.title severity=finding.severity %}
{{ bucket }} Priority: {{ severity }} Finding #{{ id }} - {{ title }}
{% endblocktranslate %}
{% endif %}
