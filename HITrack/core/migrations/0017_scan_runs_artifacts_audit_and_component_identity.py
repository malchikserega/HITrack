import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_component_identity(apps, schema_editor):
    Component = apps.get_model('core', 'Component')
    ComponentVersion = apps.get_model('core', 'ComponentVersion')
    # Prefer an existing PURL; a stable legacy key keeps rows without one distinct.
    for component in Component.objects.iterator():
        purl = ComponentVersion.objects.filter(component_id=component.pk, purl__isnull=False).exclude(purl='').values_list('purl', flat=True).first()
        if purl and purl.startswith('pkg:'):
            base = purl.split('?', 1)[0].split('#', 1)[0]
            identity = base.rpartition('@')[0] if '@' in base else base
        else:
            identity = f'legacy:{component.type or "unknown"}:{component.name.casefold()}'
        Component.objects.filter(pk=component.pk).update(identity=identity)


class Migration(migrations.Migration):
    dependencies = [('core', '0016_fix_delete_old_tags_periodic_task_name')]

    operations = [
        migrations.AddField(
            model_name='component', name='identity',
            field=models.CharField(blank=True, db_index=True, default='', max_length=512),
        ),
        migrations.RunPython(backfill_component_identity, migrations.RunPython.noop),
        migrations.CreateModel(
            name='ScanRun',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('idempotency_key', models.CharField(max_length=255, unique=True)),
                ('scanner_version', models.CharField(blank=True, default='', max_length=128)),
                ('policy_version', models.CharField(blank=True, default='', max_length=128)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('running', 'Running'), ('success', 'Success'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='queued', max_length=16)),
                ('celery_task_id', models.CharField(blank=True, default='', max_length=255)),
                ('attempt_count', models.PositiveIntegerField(default=0)),
                ('lease_expires_at', models.DateTimeField(blank=True, null=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('error_message', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scan_runs', to='core.image')),
            ],
        ),
        migrations.CreateModel(
            name='AuditEvent',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(max_length=128)),
                ('target_type', models.CharField(blank=True, default='', max_length=128)),
                ('target_id', models.CharField(blank=True, default='', max_length=128)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='hitrack_audit_events', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ScanArtifact',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[('sbom', 'SBOM'), ('grype', 'Grype')], max_length=16)),
                ('storage_key', models.CharField(max_length=1024)),
                ('checksum', models.CharField(blank=True, default='', max_length=128)),
                ('size_bytes', models.BigIntegerField(default=0)),
                ('scanner_version', models.CharField(blank=True, default='', max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scan_artifacts', to='core.image')),
                ('scan_run', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='artifacts', to='core.scanrun')),
            ],
        ),
        migrations.AddIndex(model_name='scanrun', index=models.Index(fields=['image', 'status', '-created_at'], name='core_scanrun_image_status_idx')),
        migrations.AddIndex(model_name='scanrun', index=models.Index(fields=['status', 'lease_expires_at'], name='core_scanrun_status_lease_idx')),
        migrations.AddIndex(model_name='auditevent', index=models.Index(fields=['actor', '-created_at'], name='core_audit_actor_date_idx')),
        migrations.AddIndex(model_name='auditevent', index=models.Index(fields=['action', '-created_at'], name='core_audit_action_date_idx')),
        migrations.AddIndex(model_name='scanartifact', index=models.Index(fields=['image', 'kind', '-created_at'], name='core_artifact_image_kind_idx')),
        migrations.AddConstraint(model_name='scanartifact', constraint=models.UniqueConstraint(fields=('image', 'kind', 'checksum'), name='unique_image_artifact_checksum')),
    ]
