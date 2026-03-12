from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_repository_image_fallback_repositories'),
    ]

    operations = [
        migrations.AddField(
            model_name='repository',
            name='repo_key',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
