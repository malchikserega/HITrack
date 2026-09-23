import hashlib
import json
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from core.models import ScanArtifact, ScanRun


def scan_idempotency_key(image, scanner_version='', policy_version=''):
    identity = image.digest or image.artifact_reference or image.name
    value = f'{identity}|{scanner_version}|{policy_version}'
    return hashlib.sha256(value.encode()).hexdigest()


def queue_scan(image, *, celery_task_id='', scanner_version='', policy_version='', lease_minutes=90):
    """Create one durable run for a scan identity, or return the existing active one."""
    key = scan_idempotency_key(image, scanner_version, policy_version)
    now = timezone.now()
    with transaction.atomic():
        run, created = ScanRun.objects.select_for_update().get_or_create(
            idempotency_key=key,
            defaults={
                'image': image,
                'scanner_version': scanner_version,
                'policy_version': policy_version,
                'celery_task_id': celery_task_id,
                'lease_expires_at': now + timedelta(minutes=lease_minutes),
            },
        )
        if not created and run.status in {'queued', 'running'} and run.lease_expires_at and run.lease_expires_at > now:
            return run, False
        if not created:
            run.status = 'queued'
            run.celery_task_id = celery_task_id
            run.lease_expires_at = now + timedelta(minutes=lease_minutes)
            run.error_message = ''
            run.finished_at = None
            run.save(update_fields=['status', 'celery_task_id', 'lease_expires_at', 'error_message', 'finished_at', 'updated_at'])
    return run, True


def claim_scan(run_id, *, lease_minutes=90):
    now = timezone.now()
    with transaction.atomic():
        run = ScanRun.objects.select_for_update().get(pk=run_id)
        if run.status == 'success':
            return run, False
        if run.status == 'running' and run.lease_expires_at and run.lease_expires_at > now:
            return run, False
        run.status = 'running'
        run.attempt_count += 1
        run.started_at = run.started_at or now
        run.lease_expires_at = now + timedelta(minutes=lease_minutes)
        run.save(update_fields=['status', 'attempt_count', 'started_at', 'lease_expires_at', 'updated_at'])
    return run, True


def finish_scan(run_id, *, error=''):
    status = 'failed' if error else 'success'
    ScanRun.objects.filter(pk=run_id).update(
        status=status, error_message=error, finished_at=timezone.now(), lease_expires_at=None,
    )


def store_raw_artifact(image, kind, payload, *, scan_run=None, scanner_version=''):
    """Store scanner JSON via Django storage (filesystem today, S3/MinIO when configured)."""
    encoded = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
    checksum = hashlib.sha256(encoded).hexdigest()
    key = f'scan-artifacts/{image.uuid}/{kind}/{checksum}.json'
    if not default_storage.exists(key):
        default_storage.save(key, ContentFile(encoded))
    return ScanArtifact.objects.get_or_create(
        image=image, kind=kind, checksum=checksum,
        defaults={'scan_run': scan_run, 'storage_key': key, 'size_bytes': len(encoded), 'scanner_version': scanner_version},
    )[0]
