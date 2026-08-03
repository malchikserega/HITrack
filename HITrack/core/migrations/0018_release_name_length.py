from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0017_scan_runs_artifacts_audit_and_component_identity')]

    operations = [
        migrations.AlterField(
            model_name='release', name='name',
            field=models.CharField(max_length=128, unique=True),
        ),
    ]
