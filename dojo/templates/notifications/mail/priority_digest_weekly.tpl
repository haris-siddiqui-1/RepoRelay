{% load i18n %}
{% load navigation_tags %}
{% load display_tags %}
<html>
    <body>
        {% autoescape on %}
            <p>
                {% trans "Hello" %} {{ user.get_full_name }},
            </p>
            <br/>
            <br/>
            <p>
                {% blocktranslate trimmed with count=findings|length %}
                    This is your weekly digest of P4 (Minimal Priority) security findings. {{ count }} finding(s) were identified this week.
                {% endblocktranslate %}
            </p>
            <br/>
            <h3>{% trans "Summary by Severity" %}</h3>
            <ul>
            {% for severity, count in severity_counts.items %}
                <li>{{ severity }}: {{ count }}</li>
            {% endfor %}
            </ul>
            <br/>
            <h3>{% trans "Findings by Product" %}</h3>
            {% for product_name, product_findings in findings_by_product.items %}
                <h4>{{ product_name }} ({{ product_findings|length }})</h4>
                <table style="border-collapse: collapse; width: 100%; margin-bottom: 16px;">
                    <tr style="background-color: #f2f2f2;">
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">{% trans "Title" %}</th>
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">{% trans "Severity" %}</th>
                        <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">{% trans "Score" %}</th>
                    </tr>
                    {% for finding in product_findings %}
                    <tr>
                        {% url 'view_finding' finding.id as finding_url %}
                        <td style="padding: 8px; border: 1px solid #ddd;"><a href="{{finding_url|full_url}}">{{finding.title|truncatewords:10}}</a></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{{finding.severity}}</td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{{finding.priority_score}}</td>
                    </tr>
                    {% endfor %}
                </table>
            {% endfor %}
            <br/>
            <p>
                {% url 'finding' as findings_url %}
                {% blocktranslate trimmed %}
                    P4 findings are informational and typically require no immediate action. Review them when time permits.
                {% endblocktranslate %}
                <br/>
                <a href="{{ findings_url|full_url }}">View all findings</a>
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
