from django.db import migrations


TASK_NAME = 'HITrack: Reconcile Stale Scan States'
REGISTERED_TASK = 'Reconcile Stale Scan States'


def schedule_stale_scan_reconciliation(apps, schema_editor):
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=15,
        period='minutes',
    )
    PeriodicTask.objects.get_or_create(
        name=TASK_NAME,
        defaults={
            'task': REGISTERED_TASK,
            'interval': schedule,
            'enabled': True,
            'description': (
                'Marks expired or abandoned image scans as failed and reconciles '
                'tag/repository aggregate statuses.'
            ),
        },
    )


def remove_stale_scan_reconciliation(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(name=TASK_NAME, task=REGISTERED_TASK).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0030_clusterimage_core_climg_cluster_src_idx'),
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        migrations.RunPython(
            schedule_stale_scan_reconciliation,
            remove_stale_scan_reconciliation,
        ),
    ]
