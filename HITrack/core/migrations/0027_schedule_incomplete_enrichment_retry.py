import json

from django.db import migrations


TASK_NAME = 'HITrack: Retry Incomplete Vulnerability Enrichment'
REGISTERED_TASK = 'Retry Incomplete Vulnerability Enrichment'


def schedule_incomplete_enrichment_retry(apps, schema_editor):
    CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute='45',
        hour='3',
        day_of_week='*',
        day_of_month='*',
        month_of_year='*',
        timezone='UTC',
    )
    PeriodicTask.objects.get_or_create(
        name=TASK_NAME,
        defaults={
            'task': REGISTERED_TASK,
            'crontab': schedule,
            'kwargs': json.dumps({}),
            'enabled': True,
            'description': (
                'Daily bounded retry for CVE/GHSA records whose external '
                'enrichment is partial or failed.'
            ),
        },
    )


def remove_incomplete_enrichment_retry(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(name=TASK_NAME, task=REGISTERED_TASK).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0026_add_ecr_registry_provider'),
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        migrations.RunPython(
            schedule_incomplete_enrichment_retry,
            remove_incomplete_enrichment_retry,
        ),
    ]
