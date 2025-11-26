{% load i18n %}
{% load display_tags %}
{% blocktranslate trimmed with id=finding.id title=finding.title severity=finding.severity %}
P2 Priority: {{ severity }} Finding #{{ id }} - {{ title }}
{% endblocktranslate %}
