from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_containerregistry_fallback_json'),
    ]

    operations = [
        migrations.CreateModel(
            name='ThreatIntelSnapshot',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('snapshot_date', models.DateField(unique=True)),
                ('period_start', models.DateField()),
                ('period_end', models.DateField()),
                ('observed_this_week', models.JSONField(blank=True, default=dict)),
                ('kev_added_this_week', models.JSONField(blank=True, default=dict)),
                ('supply_chain_this_week', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Threat Intel Snapshot',
                'verbose_name_plural': 'Threat Intel Snapshots',
                'ordering': ['-snapshot_date', '-updated_at'],
            },
        ),
        migrations.AddIndex(
            model_name='threatintelsnapshot',
            index=models.Index(fields=['period_start', 'period_end'], name='core_threat_period_idx'),
        ),
    ]
