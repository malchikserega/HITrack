from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_image_component_context_and_os_eol'),
    ]

    operations = [
        migrations.AddField(
            model_name='imagecomponentversioncontext',
            name='direct_introducer_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='imagecomponentversioncontext',
            name='direct_introducer_version',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='imagecomponentversioncontext',
            name='immediate_parent_name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='imagecomponentversioncontext',
            name='immediate_parent_version',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
