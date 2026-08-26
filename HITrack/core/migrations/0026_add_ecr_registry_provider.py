from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0025_schedule_vulnerability_feed_refresh'),
    ]

    operations = [
        migrations.AlterField(
            model_name='containerregistry',
            name='provider',
            field=models.CharField(
                choices=[
                    ('acr', 'Azure Container Registry'),
                    ('gcr', 'Google Container Registry'),
                    ('jfrog', 'JFrog Artifactory'),
                    ('dockerhub', 'Docker Hub'),
                    ('harbor', 'Harbor'),
                    ('ecr', 'Amazon Elastic Container Registry'),
                ],
                max_length=32,
            ),
        ),
    ]
