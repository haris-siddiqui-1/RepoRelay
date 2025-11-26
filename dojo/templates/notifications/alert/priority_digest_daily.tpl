{% load i18n %}
{% load display_tags %}
{% blocktranslate trimmed with count=findings|length %}
Daily P3 Findings Digest: {{ count }} finding(s) require attention
{% endblocktranslate %}
