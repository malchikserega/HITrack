from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_repository_repo_key'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='repository',
            index=models.Index(fields=['scan_status'], name='core_reposi_scan_st_idx'),
        ),
        migrations.AddIndex(
            model_name='repository',
            index=models.Index(fields=['repository_type'], name='core_reposi_repo_ty_idx'),
        ),
        migrations.AddIndex(
            model_name='repositorytag',
            index=models.Index(fields=['processing_status'], name='core_repota_process_idx'),
        ),
        migrations.AddIndex(
            model_name='image',
            index=models.Index(fields=['scan_status'], name='core_image_scan_st_idx'),
        ),
        migrations.AddIndex(
            model_name='vulnerability',
            index=models.Index(fields=['severity'], name='core_vulner_severit_idx'),
        ),
        migrations.AddIndex(
            model_name='componentversionvulnerability',
            index=models.Index(fields=['vulnerability', 'component_version'], name='core_cvv_vuln_cv_idx'),
        ),
    ]
