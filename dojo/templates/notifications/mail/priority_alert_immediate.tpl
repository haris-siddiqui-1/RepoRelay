{% load i18n %}
{% load navigation_tags %}
{% load display_tags %}
{% url 'view_finding' finding.id as finding_url %}
<html>
    <body>
        {% autoescape on %}
            <p>
                {% trans "Hello" %} {{ user.get_full_name }},
            </p>
            <br/>
            <br/>
            <p>
                {% if is_escalation %}
                    {% blocktranslate trimmed %}
                        A security finding has been ESCALATED and requires immediate attention.
                    {% endblocktranslate %}
                {% else %}
                    {% blocktranslate trimmed with bucket=priority_bucket %}
                        A {{ bucket }} priority security finding has been identified and requires immediate attention.
                    {% endblocktranslate %}
                {% endif %}
            </p>
            <br/>
            <table style="border-collapse: collapse; width: 100%;">
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>{% trans "Title" %}</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;"><a href="{{finding_url|full_url}}">{{finding.title}}</a></td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>{% trans "Severity" %}</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{finding.severity}}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>{% trans "Priority Bucket" %}</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{priority_bucket}}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>{% trans "Priority Score" %}</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{finding.priority_score}}</td>
                </tr>
                {% if finding.cve %}
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>{% trans "CVE" %}</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{finding.cve}}</td>
                </tr>
                {% endif %}
                <tr>
                    <td style="padding: 8px; border: 1px solid #ddd;"><strong>{% trans "Product" %}</strong></td>
                    <td style="padding: 8px; border: 1px solid #ddd;">{{finding.test.engagement.product.name}}</td>
                </tr>
            </table>
            <br/>
            <p>
                {% if is_escalation %}
                    {% blocktranslate trimmed %}
                        This finding was escalated by the triage team. Please review and take appropriate action immediately.
                    {% endblocktranslate %}
                {% else %}
                    {% blocktranslate trimmed %}
                        P0/P1 findings require immediate attention. Please review and triage this finding as soon as possible.
                    {% endblocktranslate %}
                {% endif %}
            </p>
            <br/></br>
            {% trans "Kind regards" %},
            </br></br>
            {% if system_settings.team_name %}
                {{ system_settings.team_name }}
            {% else %}
                Defect Dojo
            {% endif %}
            <br/><br/>
            <p>
                {% url 'notifications' as notification_url %}
                {% trans "You can manage your notification settings here" %}: <a href="{{ notification_url|full_url }}">{{ notification_url|full_url }}</a>
            </p>
            {% if system_settings.disclaimer_notifications and system_settings.disclaimer_notifications.strip %}
                <br/>
                <div style="background-color:#DADCE2; border:1px #003333; padding:.8em; ">
                    <span style="font-size:16pt;  font-family: 'Cambria','times new roman','garamond',serif; color:#ff0000;">{% trans "Disclaimer" %}</span><br/>
                    <p style="font-size:11pt; line-height:10pt; font-family: 'Cambria','times roman',serif;">{{ system_settings.disclaimer_notifications }}</p>
                </div>
            {% endif %}
        {% endautoescape %}
    </body>
</html>
