# Generated manually for Artifactory repo-key support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='repositorytag',
            name='image_path',
            field=models.CharField(blank=True, default='', max_length=512),
        ),
        migrations.AlterUniqueTogether(
            name='repositorytag',
            unique_together={('repository', 'tag', 'image_path')},
        ),
    ]
