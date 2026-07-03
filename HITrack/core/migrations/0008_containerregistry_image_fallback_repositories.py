from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_componentversionvulnerability_fix_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='containerregistry',
            name='image_fallback_repositories',
            field=models.ManyToManyField(
                blank=True,
                help_text='Docker repositories to try when resolving Helm chart image refs for any repo in this registry.',
                related_name='registries_using_as_fallback',
                to='core.repository',
            ),
        ),
    ]
