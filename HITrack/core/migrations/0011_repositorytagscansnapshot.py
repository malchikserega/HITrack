from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_threatintelsnapshot'),
    ]

    operations = [
        migrations.CreateModel(
            name='RepositoryTagScanSnapshot',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('processing_status', models.CharField(default='success', max_length=32)),
                ('total_images', models.IntegerField(default=0)),
                ('successful_images', models.IntegerField(default=0)),
                ('unique_vulnerabilities_count', models.IntegerField(default=0)),
                ('weighted_risk_score', models.FloatField(default=0.0)),
                ('previous_unique_vulnerabilities_count', models.IntegerField(default=0)),
                ('new_vulnerabilities_count', models.IntegerField(default=0)),
                ('fixed_vulnerabilities_count', models.IntegerField(default=0)),
                ('severity_increased_count', models.IntegerField(default=0)),
                ('new_kev_relevant_count', models.IntegerField(default=0)),
                ('risk_score_delta', models.FloatField(default=0.0)),
                ('has_changes', models.BooleanField(default=False)),
                ('fixability_breakdown', models.JSONField(blank=True, default=dict)),
                ('vulnerability_state', models.JSONField(blank=True, default=dict)),
                ('delta_summary', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('repository_tag', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scan_snapshots', to='core.repositorytag')),
            ],
            options={
                'verbose_name': 'Repository Tag Scan Snapshot',
                'verbose_name_plural': 'Repository Tag Scan Snapshots',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='repositorytagscansnapshot',
            index=models.Index(fields=['repository_tag', '-created_at'], name='core_repos_repository_778569_idx'),
        ),
        migrations.AddIndex(
            model_name='repositorytagscansnapshot',
            index=models.Index(fields=['has_changes', '-created_at'], name='core_repos_has_cha_5c280e_idx'),
        ),
    ]
