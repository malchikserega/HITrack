from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_containerregistry_image_fallback_repositories'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='containerregistry',
            name='image_fallback_repositories',
        ),
        migrations.AddField(
            model_name='containerregistry',
            name='image_fallback_repositories',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    'Fallback Docker repos for Helm image resolution. '
                    'Each entry: {"url": "...", "name": "...", "registry_uuid": "..."}'
                ),
            ),
        ),
    ]
