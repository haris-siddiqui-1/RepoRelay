{% load i18n %}{% load display_tags %}{% url 'view_finding' finding.id as finding_url %}
{
    "type": "message",
    "attachments": [
        {
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type": "ColumnSet",
                        "columns": [
                            {
                                "type": "Column",
                                "width": "auto",
                                "items": [
                                    {
                                        "type": "Image",
                                        "url": "https://raw.githubusercontent.com/DefectDojo/django-DefectDojo/master/dojo/static/dojo/img/chop.png",
                                        "size": "Small"
                                    }
                                ]
                            },
                            {
                                "type": "Column",
                                "width": "stretch",
                                "items": [
                                    {
                                        "type": "TextBlock",
                                        "text": "DefectDojo",
                                        "weight": "Bolder",
                                        "size": "Medium"
                                    },
                                    {
                                        "type": "TextBlock",
                                        "text": "{% if is_escalation %}{% trans 'ESCALATED Finding' %}{% else %}{{ priority_bucket }} {% trans 'Priority Alert' %}{% endif %}",
                                        "weight": "Bolder",
                                        "size": "Large",
                                        "color": "Attention"
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        "type": "TextBlock",
                        "text": "{% if is_escalation %}{% blocktranslate with title=finding.title %}Finding [{{ title }}]({{ finding_url|full_url }}) has been ESCALATED and requires immediate attention.{% endblocktranslate %}{% else %}{% blocktranslate with title=finding.title bucket=priority_bucket %}{{ bucket }} priority finding [{{ title }}]({{ finding_url|full_url }}) requires immediate attention.{% endblocktranslate %}{% endif %}",
                        "wrap": true,
                        "spacing": "Medium"
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {
                                "title": "{% trans 'Product' %}:",
                                "value": "{{ finding.test.engagement.product.name }}"
                            },
                            {
                                "title": "{% trans 'Finding' %}:",
                                "value": "{{ finding.title }}"
                            },
                            {
                                "title": "{% trans 'Severity' %}:",
                                "value": "{{ finding.severity }}"
                            },
                            {
                                "title": "{% trans 'Priority Score' %}:",
                                "value": "{{ finding.priority_score }}"
                            },
                            {
                                "title": "{% trans 'Priority Bucket' %}:",
                                "value": "{{ priority_bucket }}"
                            }
                        ],
                        "spacing": "Medium"
                    }{% if system_settings.disclaimer_notifications and system_settings.disclaimer_notifications.strip %},
                    {
                        "type": "Container",
                        "style": "attention",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "{% trans 'Disclaimer' %}",
                                "weight": "Bolder"
                            },
                            {
                                "type": "TextBlock",
                                "text": "{{ system_settings.disclaimer_notifications }}",
                                "wrap": true
                            }
                        ],
                        "spacing": "Medium"
                    }{% endif %}
                ],
                "actions": [
                    {
                        "type": "Action.OpenUrl",
                        "title": "{% trans 'View Finding' %}",
                        "url": "{{ finding_url|full_url }}"
                    }
                ]
            }
        }
    ]
}
