import hashlib
import json
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import ScanArtifact, ScanRun

ACTIVE_RUN_STATUSES = ('queued', 'running')
ACTIVE_IMAGE_STATUSES = ('pending', 'in_process')
DEFAULT_LEASE_MINUTES = 90
# How long an in_process image without a live ScanRun lease is trusted. Covers
# the window between "status set" and "run claimed" inside one task.
IN_PROCESS_GRACE_MINUTES = 120
# Pending images have no ScanRun until a scan worker picks the message up, so
# they may legitimately wait behind a long scan backlog.
PENDING_GRACE_MINUTES = 360
LEASE_EXPIRED_ERROR = 'lease expired: Celery message lost or worker died before finishing'


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


def claim_scan(run_id, *, celery_task_id='', lease_minutes=DEFAULT_LEASE_MINUTES):
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
        update_fields = ['status', 'attempt_count', 'started_at', 'lease_expires_at', 'updated_at']
        if celery_task_id:
            run.celery_task_id = celery_task_id
            update_fields.append('celery_task_id')
        run.save(update_fields=update_fields)
    return run, True


def renew_scan_lease(run_id, *, lease_minutes=DEFAULT_LEASE_MINUTES):
    """Extend the lease when a follow-up pipeline stage (parse/grype) starts.

    A run the reaper already failed for lease expiry is revived: the stage is
    demonstrably executing, so the run is live again.
    """
    now = timezone.now()
    return ScanRun.objects.filter(pk=run_id).exclude(status='success').update(
        status='running',
        lease_expires_at=now + timedelta(minutes=lease_minutes),
        finished_at=None,
        updated_at=now,
    )


def finish_scan(run_id, *, error=''):
    status = 'failed' if error else 'success'
    ScanRun.objects.filter(pk=run_id).update(
        status=status, error_message=error, finished_at=timezone.now(), lease_expires_at=None,
    )


def _live_run_image_ids(now):
    return ScanRun.objects.filter(
        status__in=ACTIVE_RUN_STATUSES, lease_expires_at__gt=now,
    ).values('image_id')


def image_scan_is_active(image, *, now=None):
    """True only if a pending/in_process image is really being worked on.

    Image.scan_status alone is not trustworthy: Celery messages live only in the
    broker, and if the broker loses them the status is never cleared.
    """
    if image.scan_status not in ACTIVE_IMAGE_STATUSES:
        return False
    now = now or timezone.now()
    if ScanRun.objects.filter(
        image=image, status__in=ACTIVE_RUN_STATUSES, lease_expires_at__gt=now,
    ).exists():
        return True
    grace = PENDING_GRACE_MINUTES if image.scan_status == 'pending' else IN_PROCESS_GRACE_MINUTES
    return bool(image.updated_at and image.updated_at > now - timedelta(minutes=grace))


def stale_active_images(queryset, *, now=None):
    """Narrow an Image queryset to pending/in_process images that are NOT live."""
    now = now or timezone.now()
    return queryset.filter(scan_status__in=ACTIVE_IMAGE_STATUSES).exclude(
        uuid__in=_live_run_image_ids(now),
    ).filter(
        Q(scan_status='pending', updated_at__lt=now - timedelta(minutes=PENDING_GRACE_MINUTES))
        | Q(scan_status='in_process', updated_at__lt=now - timedelta(minutes=IN_PROCESS_GRACE_MINUTES))
    )


def live_active_images(queryset, *, now=None):
    """Narrow an Image queryset to pending/in_process images that ARE live."""
    now = now or timezone.now()
    stale_ids = stale_active_images(queryset, now=now).values('uuid')
    return queryset.filter(scan_status__in=ACTIVE_IMAGE_STATUSES).exclude(uuid__in=stale_ids)


def reap_stale_scans(*, now=None):
    """Fail expired runs and release images whose scan will never finish.

    Returns (reaped_run_count, released_image_ids).
    """
    from core.models import Image

    now = now or timezone.now()
    reaped_runs = ScanRun.objects.filter(
        status__in=ACTIVE_RUN_STATUSES, lease_expires_at__lte=now,
    ).update(
        status='failed', error_message=LEASE_EXPIRED_ERROR,
        finished_at=now, lease_expires_at=None, updated_at=now,
    )
    stale = stale_active_images(Image.objects.all(), now=now)
    released_ids = list(stale.values_list('uuid', flat=True))
    if released_ids:
        Image.objects.filter(uuid__in=released_ids).update(scan_status='error', updated_at=now)
    return reaped_runs, released_ids


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
