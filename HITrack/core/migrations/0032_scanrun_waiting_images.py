from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0031_schedule_stale_scan_reconciliation'),
    ]

    operations = [
        migrations.AddField(
            model_name='scanrun',
            name='waiting_images',
            field=models.ManyToManyField(blank=True, related_name='waiting_scan_runs', to='core.image'),
        ),
    ]
