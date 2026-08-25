import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0022_remove_repository_image_fallback_repositories'),
    ]

    operations = [
        migrations.CreateModel(
            name='RiskAcceptance',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reason', models.TextField()),
                ('status', models.CharField(choices=[('active', 'Active'), ('expired', 'Expired'), ('revoked', 'Revoked')], default='active', max_length=16)),
                ('expires_at', models.DateTimeField()),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_risk_acceptances', to=settings.AUTH_USER_MODEL)),
                ('revoked_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='revoked_risk_acceptances', to=settings.AUTH_USER_MODEL)),
                ('vulnerability', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='risk_acceptances', to='core.vulnerability')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['status', 'expires_at'], name='core_risk_status_expiry_idx'),
                    models.Index(fields=['vulnerability', '-created_at'], name='core_risk_vuln_created_idx'),
                ],
                'constraints': [models.UniqueConstraint(condition=models.Q(status='active'), fields=('vulnerability',), name='unique_active_risk_acceptance')],
            },
        ),
    ]
