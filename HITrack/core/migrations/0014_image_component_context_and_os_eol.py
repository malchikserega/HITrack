from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_image_lineage_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='image',
            name='os_eol_checked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='image',
            name='os_eol_message',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='image',
            name='os_eol_source',
            field=models.CharField(default='unknown', max_length=32),
        ),
        migrations.AddField(
            model_name='image',
            name='os_eol_status',
            field=models.CharField(default='unknown', max_length=32),
        ),
        migrations.AddIndex(
            model_name='image',
            index=models.Index(fields=['os_eol_status'], name='core_image_os_eol_status_idx'),
        ),
        migrations.CreateModel(
            name='ImageComponentVersionContext',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('cataloger', models.CharField(blank=True, default='', max_length=128)),
                ('metadata_type', models.CharField(blank=True, default='', max_length=128)),
                ('dependency_scope', models.CharField(choices=[('direct', 'Direct'), ('transitive', 'Transitive'), ('unknown', 'Unknown')], default='unknown', max_length=16)),
                ('dependency_depth', models.PositiveIntegerField(blank=True, null=True)),
                ('package_scope', models.CharField(choices=[('runtime', 'Runtime'), ('development', 'Development'), ('build', 'Build'), ('test', 'Test'), ('optional', 'Optional'), ('unknown', 'Unknown')], default='unknown', max_length=16)),
                ('package_arch', models.CharField(blank=True, max_length=64, null=True)),
                ('package_distro', models.CharField(blank=True, max_length=255, null=True)),
                ('package_repo', models.CharField(blank=True, max_length=255, null=True)),
                ('package_channel', models.CharField(blank=True, max_length=255, null=True)),
                ('source_package', models.CharField(blank=True, max_length=255, null=True)),
                ('source_package_version', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('component_version', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='image_contexts', to='core.componentversion')),
                ('image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='component_contexts', to='core.image')),
            ],
            options={
                'unique_together': {('image', 'component_version')},
            },
        ),
        migrations.AddIndex(
            model_name='imagecomponentversioncontext',
            index=models.Index(fields=['image', 'dependency_scope'], name='core_imgctx_image_dep_scope_idx'),
        ),
        migrations.AddIndex(
            model_name='imagecomponentversioncontext',
            index=models.Index(fields=['component_version'], name='core_imgctx_component_version_idx'),
        ),
        migrations.AddIndex(
            model_name='imagecomponentversioncontext',
            index=models.Index(fields=['package_arch'], name='core_imgctx_package_arch_idx'),
        ),
        migrations.AddIndex(
            model_name='imagecomponentversioncontext',
            index=models.Index(fields=['source_package'], name='core_imgctx_source_package_idx'),
        ),
        migrations.AddIndex(
            model_name='imagecomponentversioncontext',
            index=models.Index(fields=['package_scope'], name='core_imgctx_package_scope_idx'),
        ),
    ]
