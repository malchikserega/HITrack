"""Durable scan bookkeeping.

A ScanRun is keyed by image *content* (digest), so every image name/tag with
the same digest shares one run. Results are still stored per Image row, so:

* the first image to arrive claims the run and is scanned;
* images with the same digest that arrive while it is live join it as
  waiters and receive its results when it succeeds (re-queued if it fails);
* images whose digest was scanned successfully within SCAN_REUSE_HOURS reuse
  that result without scanning (automated scans only).

Liveness is therefore per digest: an image is live when its own digest has a
live run, not only when it owns the run.
"""
import hashlib
import json
from datetime import timedelta

from django.conf import settings
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

CLAIMED = 'claimed'
WAITING = 'waiting'


def scan_idempotency_key(image, scanner_version='', policy_version=''):
    identity = image.digest or image.artifact_reference or image.name
    value = f'{identity}|{scanner_version}|{policy_version}'
    return hashlib.sha256(value.encode()).hexdigest()


def queue_scan(image, *, celery_task_id='', scanner_version='', policy_version='', lease_minutes=DEFAULT_LEASE_MINUTES):
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


def join_or_claim_scan(image, *, celery_task_id='', lease_minutes=DEFAULT_LEASE_MINUTES):
    """Claim the scan of this image's content, or wait on the one already live.

    Returns ``(run, CLAIMED)`` when the caller must scan, or ``(run, WAITING)``
    when another image with the same digest is being scanned right now; the
    image is then recorded as a waiter on that run. The run row lock makes
    this atomic with complete_scan(), so a waiter can never be added after the
    run's waiters were handed out.
    """
    key = scan_idempotency_key(image)
    now = timezone.now()
    lease = now + timedelta(minutes=lease_minutes)
    with transaction.atomic():
        run, created = ScanRun.objects.select_for_update().get_or_create(
            idempotency_key=key,
            defaults={
                'image': image,
                'celery_task_id': celery_task_id,
                'status': 'running',
                'attempt_count': 1,
                'started_at': now,
                'lease_expires_at': lease,
            },
        )
        if created:
            return run, CLAIMED
        is_live = run.status in ACTIVE_RUN_STATUSES and run.lease_expires_at and run.lease_expires_at > now
        # A redelivered message (worker killed mid-scan, acks_late) carries the
        # same task id as the claim it lost: it must take the run over, not
        # wait on itself until the lease expires.
        is_redelivery = bool(celery_task_id) and run.celery_task_id == celery_task_id
        if is_live and not is_redelivery:
            run.waiting_images.add(image)
            return run, WAITING
        run.status = 'running'
        run.attempt_count += 1
        run.started_at = now
        run.lease_expires_at = lease
        run.error_message = ''
        run.finished_at = None
        update_fields = [
            'status', 'attempt_count', 'started_at', 'lease_expires_at',
            'error_message', 'finished_at', 'updated_at',
        ]
        if celery_task_id:
            run.celery_task_id = celery_task_id
            update_fields.append('celery_task_id')
        run.save(update_fields=update_fields)
    return run, CLAIMED


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


def complete_scan(run_id, *, error=''):
    """Finish a run and detach its waiters atomically.

    Returns the waiting image ids; the caller hands them the result (success)
    or re-queues them (failure).
    """
    now = timezone.now()
    with transaction.atomic():
        run = ScanRun.objects.select_for_update().filter(pk=run_id).first()
        if run is None:
            return []
        waiter_ids = list(run.waiting_images.values_list('pk', flat=True))
        if waiter_ids:
            run.waiting_images.clear()
        run.status = 'failed' if error else 'success'
        run.error_message = error
        run.finished_at = now
        run.lease_expires_at = None
        run.save(update_fields=['status', 'error_message', 'finished_at', 'lease_expires_at', 'updated_at'])
    return waiter_ids


def finish_scan(run_id, *, error=''):
    """Backwards-compatible wrapper; returns the detached waiter ids."""
    return complete_scan(run_id, error=error)


def scan_reuse_window():
    hours = getattr(settings, 'SCAN_REUSE_HOURS', 24)
    return timedelta(hours=hours) if hours and hours > 0 else None


def find_reusable_scan_source(image, *, now=None):
    """Return an image whose results can stand in for ``image`` without scanning.

    Requires a digest (identical content), a successful run for that digest
    inside the reuse window, and another image of that digest holding results.
    """
    from core.models import Image

    window = scan_reuse_window()
    if window is None or not image.digest:
        return None
    now = now or timezone.now()
    fresh_run = ScanRun.objects.filter(
        idempotency_key=scan_idempotency_key(image),
        status='success',
        finished_at__gte=now - window,
    ).exists()
    if not fresh_run:
        return None
    return Image.objects.filter(
        digest=image.digest,
        scan_status='success',
        sbom_data__isnull=False,
        grype_data__isnull=False,
    ).exclude(pk=image.pk).order_by('-updated_at').first()


def _live_image_ids(now):
    """Ids of images whose scan is live: run owner, recorded waiter, or same digest."""
    from core.models import Image

    live_runs = ScanRun.objects.filter(status__in=ACTIVE_RUN_STATUSES, lease_expires_at__gt=now)
    live_digests = live_runs.exclude(image__digest__isnull=True).exclude(image__digest='').values('image__digest')
    return Image.objects.filter(
        Q(uuid__in=live_runs.values('image_id'))
        | Q(uuid__in=live_runs.filter(waiting_images__isnull=False).values('waiting_images'))
        | Q(digest__in=live_digests)
    ).values('uuid')


def image_scan_is_active(image, *, now=None):
    """True only if a pending/in_process image is really being worked on.

    Image.scan_status alone is not trustworthy: Celery messages live only in the
    broker, and if the broker loses them the status is never cleared.
    """
    from core.models import Image

    if image.scan_status not in ACTIVE_IMAGE_STATUSES:
        return False
    now = now or timezone.now()
    if Image.objects.filter(pk=image.pk, uuid__in=_live_image_ids(now)).exists():
        return True
    grace = PENDING_GRACE_MINUTES if image.scan_status == 'pending' else IN_PROCESS_GRACE_MINUTES
    return bool(image.updated_at and image.updated_at > now - timedelta(minutes=grace))


def stale_active_images(queryset, *, now=None):
    """Narrow an Image queryset to pending/in_process images that are NOT live."""
    now = now or timezone.now()
    return queryset.filter(scan_status__in=ACTIVE_IMAGE_STATUSES).exclude(
        uuid__in=_live_image_ids(now),
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

    Waiters of an expired run are released together with it. Returns
    ``(reaped_run_count, released_image_ids)``.
    """
    from core.models import Image

    now = now or timezone.now()
    with transaction.atomic():
        expired = ScanRun.objects.select_for_update().filter(
            status__in=ACTIVE_RUN_STATUSES, lease_expires_at__lte=now,
        )
        expired_ids = list(expired.values_list('pk', flat=True))
        waiter_links = ScanRun.waiting_images.through.objects.filter(scanrun_id__in=expired_ids)
        orphaned_waiter_ids = set(waiter_links.values_list('image_id', flat=True))
        waiter_links.delete()
        reaped_runs = ScanRun.objects.filter(pk__in=expired_ids).update(
            status='failed', error_message=LEASE_EXPIRED_ERROR,
            finished_at=now, lease_expires_at=None, updated_at=now,
        )

    released_ids = set(stale_active_images(Image.objects.all(), now=now).values_list('uuid', flat=True))
    if orphaned_waiter_ids:
        released_ids.update(
            Image.objects.filter(pk__in=orphaned_waiter_ids, scan_status__in=ACTIVE_IMAGE_STATUSES)
            .exclude(uuid__in=_live_image_ids(now))
            .values_list('uuid', flat=True)
        )
    released_ids = list(released_ids)
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
