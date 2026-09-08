import django.db.models.deletion
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0028_mark_incomplete_enrichments_partial')]

    operations = [
        migrations.AddField(
            model_name='image',
            name='container_registry',
            field=models.ForeignKey(
                blank=True,
                help_text='Registry credentials used when this image is scanned without a repository tag.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='standalone_images',
                to='core.containerregistry',
            ),
        ),
        migrations.CreateModel(
            name='Cluster',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=128, unique=True)),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='ClusterImage',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('source_reference', models.CharField(max_length=255)),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('cluster', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='image_links', to='core.cluster')),
                ('image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cluster_links', to='core.image')),
            ],
            options={'ordering': ['source_reference'], 'unique_together': {('cluster', 'image')}},
        ),
        migrations.AddField(
            model_name='cluster',
            name='images',
            field=models.ManyToManyField(blank=True, related_name='clusters', through='core.ClusterImage', to='core.image'),
        ),
    ]
