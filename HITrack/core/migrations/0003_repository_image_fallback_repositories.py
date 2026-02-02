# Generated manually for Helm image fallback repositories

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_repositorytag_image_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='repository',
            name='image_fallback_repositories',
            field=models.ManyToManyField(
                blank=True,
                help_text='Docker repositories to use when resolving Helm chart image refs fails.',
                related_name='helm_repos_using_as_fallback',
                to='core.repository'
            ),
        ),
    ]
