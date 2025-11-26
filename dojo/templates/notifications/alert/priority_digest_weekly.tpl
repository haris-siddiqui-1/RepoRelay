{% load i18n %}
{% load display_tags %}
{% blocktranslate trimmed with count=findings|length %}
Weekly P4 Findings Digest: {{ count }} finding(s) identified this week
{% endblocktranslate %}
