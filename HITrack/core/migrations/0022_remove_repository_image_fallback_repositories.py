from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_image_vulnerability_summary'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='repository',
            name='image_fallback_repositories',
        ),
    ]
