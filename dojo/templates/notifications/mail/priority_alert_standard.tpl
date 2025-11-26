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
                {% blocktranslate trimmed %}
                    A P2 (Medium Priority) security finding has been identified.
                {% endblocktranslate %}
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
                    <td style="padding: 8px; border: 1px solid #ddd;">P2</td>
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
                {% blocktranslate trimmed %}
                    P2 findings should be reviewed and triaged within a reasonable timeframe.
                {% endblocktranslate %}
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
