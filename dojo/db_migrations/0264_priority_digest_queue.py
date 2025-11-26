# Generated migration for PriorityDigestQueue model
# Phase 5 - Vulnerability Prioritization Strategy

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dojo', '0263_repository_consumption_signals'),
    ]

    operations = [
        migrations.CreateModel(
            name='PriorityDigestQueue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('digest_type', models.CharField(
                    choices=[
                        ('standard', 'Standard (P2)'),
                        ('daily', 'Daily Digest (P3)'),
                        ('weekly', 'Weekly Digest (P4)')
                    ],
                    db_index=True,
                    help_text='Type of digest this finding is queued for',
                    max_length=20,
                    verbose_name='Digest Type'
                )),
                ('queued_at', models.DateTimeField(
                    auto_now_add=True,
                    db_index=True,
                    help_text='When the finding was added to the digest queue',
                    verbose_name='Queued At'
                )),
                ('sent_at', models.DateTimeField(
                    blank=True,
                    db_index=True,
                    help_text='When the digest containing this finding was sent (null if pending)',
                    null=True,
                    verbose_name='Sent At'
                )),
                ('finding', models.ForeignKey(
                    help_text='Finding queued for digest notification',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='digest_queue_entries',
                    to='dojo.finding',
                    verbose_name='Finding'
                )),
            ],
            options={
                'verbose_name': 'Priority Digest Queue',
                'verbose_name_plural': 'Priority Digest Queue',
                'ordering': ['-queued_at'],
            },
        ),
        migrations.AddIndex(
            model_name='prioritydigestqueue',
            index=models.Index(fields=['digest_type', 'sent_at'], name='dojo_priori_digest__5d8b4e_idx'),
        ),
        migrations.AddConstraint(
            model_name='prioritydigestqueue',
            constraint=models.UniqueConstraint(
                condition=models.Q(sent_at__isnull=True),
                fields=['finding', 'digest_type'],
                name='unique_pending_digest_entry'
            ),
        ),
    ]
