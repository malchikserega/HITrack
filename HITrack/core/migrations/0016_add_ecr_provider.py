from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_image_component_context_introducers'),
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
                    ('ecr', 'Amazon Elastic Container Registry'),
                    ('dockerhub', 'Docker Hub'),
                    ('harbor', 'Harbor'),
                ],
                max_length=32,
            ),
        ),
    ]
