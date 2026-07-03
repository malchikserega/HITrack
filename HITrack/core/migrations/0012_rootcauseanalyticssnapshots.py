from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_repositorytagscansnapshot'),
    ]

    operations = [
        migrations.CreateModel(
            name='BaseLineageRootCauseAnalyticsSnapshot',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('snapshot_date', models.DateField(unique=True)),
                ('total_items', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Base Lineage Root Cause Analytics Snapshot',
                'verbose_name_plural': 'Base Lineage Root Cause Analytics Snapshots',
                'ordering': ['-snapshot_date', '-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='SharedRootCauseAnalyticsSnapshot',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('snapshot_date', models.DateField(unique=True)),
                ('total_items', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Shared Root Cause Analytics Snapshot',
                'verbose_name_plural': 'Shared Root Cause Analytics Snapshots',
                'ordering': ['-snapshot_date', '-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='SharedRootCauseAnalyticsSnapshotRow',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('component_version_uuid', models.UUIDField()),
                ('component_uuid', models.UUIDField()),
                ('component_name', models.CharField(max_length=255)),
                ('version', models.CharField(max_length=255)),
                ('component_type', models.CharField(default='unknown', max_length=50)),
                ('purl', models.CharField(blank=True, max_length=512, null=True)),
                ('latest_version', models.CharField(blank=True, max_length=255, null=True)),
                ('affected_repositories_count', models.IntegerField(default=0)),
                ('affected_tags_count', models.IntegerField(default=0)),
                ('affected_releases_count', models.IntegerField(default=0)),
                ('affected_images_count', models.IntegerField(default=0)),
                ('vulnerabilities_count', models.IntegerField(default=0)),
                ('critical_vulnerabilities_count', models.IntegerField(default=0)),
                ('high_vulnerabilities_count', models.IntegerField(default=0)),
                ('kev_vulnerabilities_count', models.IntegerField(default=0)),
                ('exploit_vulnerabilities_count', models.IntegerField(default=0)),
                ('weighted_risk_score', models.FloatField(default=0.0)),
                ('max_fix_priority', models.IntegerField(default=0)),
                ('fixability_category', models.CharField(default='fix_unknown', max_length=64)),
                ('fixable_now_count', models.IntegerField(default=0)),
                ('fix_exists_but_not_in_repo_count', models.IntegerField(default=0)),
                ('no_fix_count', models.IntegerField(default=0)),
                ('fix_unknown_count', models.IntegerField(default=0)),
                ('latest_seen_at', models.DateTimeField(blank=True, null=True)),
                ('repositories_preview', models.JSONField(blank=True, default=list)),
                ('vulnerabilities_preview', models.JSONField(blank=True, default=list)),
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rows', to='core.sharedrootcauseanalyticssnapshot')),
            ],
            options={
                'verbose_name': 'Shared Root Cause Analytics Snapshot Row',
                'verbose_name_plural': 'Shared Root Cause Analytics Snapshot Rows',
                'ordering': ['-weighted_risk_score', 'component_name', 'version'],
                'unique_together': {('snapshot', 'component_version_uuid')},
            },
        ),
        migrations.CreateModel(
            name='BaseLineageRootCauseAnalyticsSnapshotRow',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('key', models.CharField(max_length=255)),
                ('lineage_label', models.CharField(max_length=255)),
                ('lineage_source', models.CharField(default='unknown', max_length=64)),
                ('affected_repositories_count', models.IntegerField(default=0)),
                ('affected_tags_count', models.IntegerField(default=0)),
                ('affected_releases_count', models.IntegerField(default=0)),
                ('affected_images_count', models.IntegerField(default=0)),
                ('vulnerabilities_count', models.IntegerField(default=0)),
                ('critical_vulnerabilities_count', models.IntegerField(default=0)),
                ('high_vulnerabilities_count', models.IntegerField(default=0)),
                ('kev_vulnerabilities_count', models.IntegerField(default=0)),
                ('exploit_vulnerabilities_count', models.IntegerField(default=0)),
                ('weighted_risk_score', models.FloatField(default=0.0)),
                ('max_fix_priority', models.IntegerField(default=0)),
                ('fixability_category', models.CharField(default='fix_unknown', max_length=64)),
                ('fixable_now_count', models.IntegerField(default=0)),
                ('fix_exists_but_not_in_repo_count', models.IntegerField(default=0)),
                ('no_fix_count', models.IntegerField(default=0)),
                ('fix_unknown_count', models.IntegerField(default=0)),
                ('latest_seen_at', models.DateTimeField(blank=True, null=True)),
                ('repositories_preview', models.JSONField(blank=True, default=list)),
                ('components_preview', models.JSONField(blank=True, default=list)),
                ('vulnerabilities_preview', models.JSONField(blank=True, default=list)),
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rows', to='core.baselineagerootcauseanalyticssnapshot')),
            ],
            options={
                'verbose_name': 'Base Lineage Root Cause Analytics Snapshot Row',
                'verbose_name_plural': 'Base Lineage Root Cause Analytics Snapshot Rows',
                'ordering': ['-weighted_risk_score', 'lineage_label'],
                'unique_together': {('snapshot', 'key')},
            },
        ),
        migrations.AddIndex(
            model_name='sharedrootcauseanalyticssnapshotrow',
            index=models.Index(fields=['snapshot', '-weighted_risk_score'], name='core_shared_snapshot_risk_idx'),
        ),
        migrations.AddIndex(
            model_name='sharedrootcauseanalyticssnapshotrow',
            index=models.Index(fields=['snapshot', 'component_type'], name='core_shared_snapshot_type_idx'),
        ),
        migrations.AddIndex(
            model_name='sharedrootcauseanalyticssnapshotrow',
            index=models.Index(fields=['snapshot', 'max_fix_priority'], name='core_shared_snapshot_fix_idx'),
        ),
        migrations.AddIndex(
            model_name='sharedrootcauseanalyticssnapshotrow',
            index=models.Index(fields=['snapshot', 'component_name'], name='core_shared_snapshot_name_idx'),
        ),
        migrations.AddIndex(
            model_name='sharedrootcauseanalyticssnapshotrow',
            index=models.Index(fields=['snapshot', '-affected_repositories_count'], name='core_shared_snapshot_repo_idx'),
        ),
        migrations.AddIndex(
            model_name='baselineagerootcauseanalyticssnapshotrow',
            index=models.Index(fields=['snapshot', '-weighted_risk_score'], name='core_lineage_snapshot_risk_idx'),
        ),
        migrations.AddIndex(
            model_name='baselineagerootcauseanalyticssnapshotrow',
            index=models.Index(fields=['snapshot', 'lineage_label'], name='core_lineage_snapshot_label_idx'),
        ),
        migrations.AddIndex(
            model_name='baselineagerootcauseanalyticssnapshotrow',
            index=models.Index(fields=['snapshot', 'lineage_source'], name='core_lineage_snapshot_source_idx'),
        ),
        migrations.AddIndex(
            model_name='baselineagerootcauseanalyticssnapshotrow',
            index=models.Index(fields=['snapshot', 'max_fix_priority'], name='core_lineage_snapshot_fix_idx'),
        ),
        migrations.AddIndex(
            model_name='baselineagerootcauseanalyticssnapshotrow',
            index=models.Index(fields=['snapshot', '-affected_repositories_count'], name='core_lineage_snapshot_repo_idx'),
        ),
    ]
