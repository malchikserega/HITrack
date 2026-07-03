from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_rootcauseanalyticssnapshots"),
    ]

    operations = [
        migrations.AddField(
            model_name="image",
            name="lineage_label",
            field=models.CharField(default="unknown", max_length=255),
        ),
        migrations.AddField(
            model_name="image",
            name="lineage_source",
            field=models.CharField(default="unknown", max_length=64),
        ),
        migrations.AddField(
            model_name="image",
            name="lineage_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="image",
            name="os_distro_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="image",
            name="os_distro_version",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddIndex(
            model_name="image",
            index=models.Index(
                fields=["scan_status", "lineage_label", "lineage_source"],
                name="core_image_scan_lineage_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="image",
            index=models.Index(
                fields=["lineage_label", "lineage_source"],
                name="core_image_lineage_idx",
            ),
        ),
    ]
