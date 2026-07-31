from django.db import migrations

# Celery tasks in core.tasks are registered under human-readable names (see the
# `name="..."` kwarg on each @celery_app.task decorator), not their Python
# dotted path. Periodic tasks created through the admin using the dotted path
# (e.g. "core.tasks.delete_old_repository_tags") are never picked up by any
# worker: Celery routes strictly on the registered task name, so beat sends a
# task type no worker recognizes and it gets silently discarded.
# Maps the dotted path someone might type in the admin to the actual
# registered Celery task name.
DOTTED_PATH_TO_REGISTERED_NAME = {
    'core.tasks.periodic_repository_scan': 'Periodic Repository Scan',
    'core.tasks.scan_repository': 'Scan Repository',
    'core.tasks.scan_repository_tags': 'Scan Repository Tags',
    'core.tasks.process_all_tags': 'Process All Tags',
    'core.tasks.parse_sbom_and_create_components': 'Parse SBOM and Create Components',
    'core.tasks.generate_sbom_and_create_components': 'Generate SBOM and Create Components',
    'core.tasks.update_components_latest_versions': 'Update Components Latest Versions',
    'core.tasks.process_grype_scan_results': 'Process Grype Scan Results',
    'core.tasks.scan_image_with_grype': 'Scan Image with Grype',
    'core.tasks.rescan_all_images_with_sbom': 'Rescan All Images with SBOM',
    'core.tasks.monitor_mass_rescan_progress': 'Monitor Mass Rescan Progress',
    'core.tasks.process_single_tag': 'Process Single Tag',
    'core.tasks.deduplicate_images_by_identity': 'Deduplicate Images by Identity',
    'core.tasks.backfill_image_lineage_fields': 'Backfill Image Lineage Fields',
    'core.tasks.backfill_image_sbom_security_metadata': 'Backfill Image SBOM Security Metadata',
    'core.tasks.delete_old_repository_tags': 'Delete Old Repository Tags',
    'core.tasks.update_vulnerability_details': 'Update Vulnerability Details',
    'core.tasks.update_all_vulnerability_details': 'Update All Vulnerability Details',
    'core.tasks.update_critical_vulnerability_details': 'Update Critical Vulnerability Details',
    'core.tasks.cleanup_old_vulnerability_data': 'Cleanup Old Vulnerability Data',
    'core.tasks.update_vulnerability_details_bulk': 'Update Vulnerability Details (Bulk)',
    'core.tasks.update_critical_vulnerabilities_bulk': 'Update Critical Vulnerabilities (Bulk)',
    'core.tasks.monitor_task_status': 'Monitor Task Status',
    'core.tasks.monitor_bulk_update_progress': 'Monitor Bulk Update Progress',
    'core.tasks.update_cisa_kev_vulnerabilities': 'Update CISA KEV Vulnerabilities',
    'core.tasks.test_task': 'Test Task',
    'core.tasks.test_failing_task': 'Test Failing Task',
    'core.tasks.performance_monitor': 'Performance Monitor',
    'core.tasks.update_all_components_latest_versions': 'Update All Components Latest Versions',
    'core.tasks.update_deb_components_latest_versions': 'Update Deb Components Latest Versions',
    'core.tasks.recalculate_vulnerability_fix_availability': 'Recalculate Vulnerability Fix Availability',
    'core.tasks.cleanup_threat_intel_snapshots': 'Cleanup Threat Intel Snapshots',
    'core.tasks.collect_weekly_threat_intel_snapshot': 'Collect Weekly Threat Intel Snapshot',
    'core.tasks.cleanup_root_cause_analytics_snapshots': 'Cleanup Root Cause Analytics Snapshots',
    'core.tasks.collect_root_cause_analytics_snapshot': 'Collect Root Cause Analytics Snapshot',
}


def fix_task_names(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    for dotted_path, registered_name in DOTTED_PATH_TO_REGISTERED_NAME.items():
        PeriodicTask.objects.filter(task=dotted_path).update(task=registered_name)


def revert_task_names(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    for dotted_path, registered_name in DOTTED_PATH_TO_REGISTERED_NAME.items():
        PeriodicTask.objects.filter(task=registered_name).update(task=dotted_path)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_image_component_context_introducers'),
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        migrations.RunPython(fix_task_names, revert_task_names),
    ]
