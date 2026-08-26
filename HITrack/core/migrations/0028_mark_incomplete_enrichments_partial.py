from django.db import migrations
from django.db.models import Q


def mark_incomplete_enrichments_partial(apps, schema_editor):
    VulnerabilityDetails = apps.get_model('core', 'VulnerabilityDetails')
    VulnerabilityDetails.objects.filter(
        enrichment_status='success',
    ).filter(
        Q(cve_details_score__isnull=True)
        | Q(
            vulnerability__vulnerability_id__istartswith='CVE-',
            epss_score__isnull=True,
        )
    ).update(enrichment_status='partial')


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0027_schedule_incomplete_enrichment_retry'),
    ]

    operations = [
        migrations.RunPython(mark_incomplete_enrichments_partial, migrations.RunPython.noop),
    ]
