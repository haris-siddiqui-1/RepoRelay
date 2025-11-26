# Generated migration for Notifications priority notification fields
# Phase 5 - Vulnerability Prioritization Strategy

from django.db import migrations
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('dojo', '0264_priority_digest_queue'),
    ]

    operations = [
        migrations.AddField(
            model_name='notifications',
            name='priority_alert_immediate',
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ('alert', 'alert'),
                    ('mail', 'mail'),
                    ('slack', 'slack'),
                    ('msteams', 'msteams'),
                    ('webhooks', 'webhooks')
                ],
                default='alert',
                help_text='Get notified immediately for P0/P1 critical priority findings',
                max_length=54,
                verbose_name='Priority Alert (Immediate)'
            ),
        ),
        migrations.AddField(
            model_name='notifications',
            name='priority_alert_standard',
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ('alert', 'alert'),
                    ('mail', 'mail'),
                    ('slack', 'slack'),
                    ('msteams', 'msteams'),
                    ('webhooks', 'webhooks')
                ],
                default='alert',
                help_text='Get notified for P2 medium priority findings (1-hour delay)',
                max_length=54,
                verbose_name='Priority Alert (Standard)'
            ),
        ),
        migrations.AddField(
            model_name='notifications',
            name='priority_digest_daily',
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ('alert', 'alert'),
                    ('mail', 'mail'),
                    ('slack', 'slack'),
                    ('msteams', 'msteams'),
                    ('webhooks', 'webhooks')
                ],
                default='alert',
                help_text='Get daily digest of P3 low priority findings',
                max_length=54,
                verbose_name='Priority Digest (Daily)'
            ),
        ),
        migrations.AddField(
            model_name='notifications',
            name='priority_digest_weekly',
            field=multiselectfield.db.fields.MultiSelectField(
                blank=True,
                choices=[
                    ('alert', 'alert'),
                    ('mail', 'mail'),
                    ('slack', 'slack'),
                    ('msteams', 'msteams'),
                    ('webhooks', 'webhooks')
                ],
                default=[],
                help_text='Get weekly digest of P4 minimal priority findings (optional)',
                max_length=54,
                verbose_name='Priority Digest (Weekly)'
            ),
        ),
    ]
