"""Recovery from lost Celery messages and Helm image discovery with placeholders.

Regression coverage for images stuck forever in pending/in_process after the
Redis broker dropped queued scan messages, and for charts whose rendered image
field is `docker.$REPO_HOST/app:tag`.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from core.models import Image, Repository, RepositoryTag, ScanRun
from core.services.scans import (
    IN_PROCESS_GRACE_MINUTES,
    LEASE_EXPIRED_ERROR,
    PENDING_GRACE_MINUTES,
    claim_scan,
    image_scan_is_active,
    live_active_images,
    queue_scan,
    reap_stale_scans,
    renew_scan_lease,
    stale_active_images,
)
from core.utils.helm import (
    _extract_image_refs_from_text,
    _looks_like_image_ref,
    _placeholder_substitutions,
)


def _age(image, minutes):
    Image.objects.filter(pk=image.pk).update(updated_at=timezone.now() - timedelta(minutes=minutes))
    image.refresh_from_db()


def _expire(run):
    ScanRun.objects.filter(pk=run.pk).update(lease_expires_at=timezone.now() - timedelta(minutes=1))


class ScanLivenessTests(TestCase):
    def setUp(self):
        self.image = Image.objects.create(
            name='registry.example/api:1', digest='sha256:abc', scan_status='in_process',
        )

    def test_live_lease_means_active_regardless_of_age(self):
        run, _ = queue_scan(self.image)
        claim_scan(run.pk)
        _age(self.image, IN_PROCESS_GRACE_MINUTES * 10)
        self.assertTrue(image_scan_is_active(self.image))

    def test_in_process_without_lease_is_active_only_within_grace(self):
        self.assertTrue(image_scan_is_active(self.image))
        _age(self.image, IN_PROCESS_GRACE_MINUTES + 1)
        self.assertFalse(image_scan_is_active(self.image))

    def test_expired_lease_is_not_active(self):
        run, _ = queue_scan(self.image)
        claim_scan(run.pk)
        _expire(run)
        _age(self.image, IN_PROCESS_GRACE_MINUTES + 1)
        self.assertFalse(image_scan_is_active(self.image))

    def test_pending_gets_the_longer_backlog_grace(self):
        Image.objects.filter(pk=self.image.pk).update(scan_status='pending')
        _age(self.image, IN_PROCESS_GRACE_MINUTES + 1)
        self.assertTrue(image_scan_is_active(self.image))
        _age(self.image, PENDING_GRACE_MINUTES + 1)
        self.assertFalse(image_scan_is_active(self.image))

    def test_finished_statuses_are_never_active(self):
        for scan_status in ('success', 'error'):
            Image.objects.filter(pk=self.image.pk).update(scan_status=scan_status)
            self.image.refresh_from_db()
            self.assertFalse(image_scan_is_active(self.image))

    def test_live_and_stale_querysets_partition_active_images(self):
        stale = Image.objects.create(name='registry.example/stale:1', scan_status='in_process')
        _age(stale, IN_PROCESS_GRACE_MINUTES + 1)
        done = Image.objects.create(name='registry.example/done:1', scan_status='success')

        all_images = Image.objects.filter(pk__in=[self.image.pk, stale.pk, done.pk])
        self.assertEqual(set(live_active_images(all_images).values_list('pk', flat=True)), {self.image.pk})
        self.assertEqual(set(stale_active_images(all_images).values_list('pk', flat=True)), {stale.pk})


class ReapStaleScansTests(TestCase):
    def test_expired_runs_fail_and_stuck_images_are_released(self):
        stuck = Image.objects.create(name='registry.example/stuck:1', digest='sha256:1', scan_status='in_process')
        run, _ = queue_scan(stuck)
        claim_scan(run.pk)
        _expire(run)
        _age(stuck, IN_PROCESS_GRACE_MINUTES + 1)

        orphan = Image.objects.create(name='registry.example/orphan:1', scan_status='in_process')
        _age(orphan, IN_PROCESS_GRACE_MINUTES + 1)

        fresh = Image.objects.create(name='registry.example/fresh:1', scan_status='pending')
        busy = Image.objects.create(name='registry.example/busy:1', digest='sha256:2', scan_status='in_process')
        busy_run, _ = queue_scan(busy)
        claim_scan(busy_run.pk)
        _age(busy, IN_PROCESS_GRACE_MINUTES + 1)

        reaped_runs, released = reap_stale_scans()

        self.assertEqual(reaped_runs, 1)
        self.assertEqual(set(released), {stuck.pk, orphan.pk})
        run.refresh_from_db()
        self.assertEqual(run.status, 'failed')
        self.assertEqual(run.error_message, LEASE_EXPIRED_ERROR)
        self.assertIsNone(run.lease_expires_at)
        for image, expected in ((stuck, 'error'), (orphan, 'error'), (fresh, 'pending'), (busy, 'in_process')):
            image.refresh_from_db()
            self.assertEqual(image.scan_status, expected, image.name)

    def test_renew_revives_a_reaped_run_when_a_stage_starts(self):
        image = Image.objects.create(name='registry.example/slow:1', digest='sha256:3', scan_status='in_process')
        run, _ = queue_scan(image)
        claim_scan(run.pk)
        _expire(run)
        reap_stale_scans()

        self.assertEqual(renew_scan_lease(run.pk), 1)
        run.refresh_from_db()
        self.assertEqual(run.status, 'running')
        self.assertGreater(run.lease_expires_at, timezone.now())
        self.assertIsNone(run.finished_at)

    def test_renew_never_reopens_a_successful_run(self):
        image = Image.objects.create(name='registry.example/ok:1', digest='sha256:4')
        run, _ = queue_scan(image)
        ScanRun.objects.filter(pk=run.pk).update(status='success', lease_expires_at=None)
        self.assertEqual(renew_scan_lease(run.pk), 0)
        run.refresh_from_db()
        self.assertEqual(run.status, 'success')

    def test_claim_records_celery_task_id(self):
        image = Image.objects.create(name='registry.example/id:1', digest='sha256:5')
        run, _ = queue_scan(image, celery_task_id='queued-id')
        claimed, ok = claim_scan(run.pk, celery_task_id='worker-id')
        self.assertTrue(ok)
        claimed.refresh_from_db()
        self.assertEqual(claimed.celery_task_id, 'worker-id')


class ReconcileStaleScanStatesTaskTests(TestCase):
    def test_task_releases_images_and_resolves_tag_and_repository(self):
        from core.tasks import reconcile_stale_scan_states

        repository = Repository.objects.create(
            name='helm/app', url='helm/app', repository_type='helm', scan_status='in_process',
        )
        tag = RepositoryTag.objects.create(repository=repository, tag='1.0.0', processing_status='in_process')
        image = Image.objects.create(name='registry.example/app:1.0.0', scan_status='in_process')
        image.repository_tags.add(tag)
        _age(image, IN_PROCESS_GRACE_MINUTES + 1)

        result = reconcile_stale_scan_states()

        self.assertEqual(result['released_images'], 1)
        image.refresh_from_db()
        tag.refresh_from_db()
        repository.refresh_from_db()
        self.assertEqual(image.scan_status, 'error')
        self.assertEqual(tag.processing_status, 'error')
        self.assertEqual(repository.scan_status, 'error')

    def test_task_is_a_no_op_when_nothing_is_stale(self):
        from core.tasks import reconcile_stale_scan_states

        Image.objects.create(name='registry.example/app:2', scan_status='in_process')
        result = reconcile_stale_scan_states()
        self.assertEqual((result['reaped_runs'], result['released_images']), (0, 0))


class StaleImageRescanViewTests(APITestCase):
    def setUp(self):
        operator = get_user_model().objects.create_user(username='operator', password='test-password')
        operator.groups.add(Group.objects.create(name='operator'))
        self.client.force_authenticate(operator)

    @patch('core.tasks.generate_sbom_and_create_components.delay')
    def test_rescan_accepts_a_stale_in_process_image(self, delay):
        delay.return_value.id = 'scan-task'
        image = Image.objects.create(name='registry.example/stale:1', scan_status='in_process')
        _age(image, IN_PROCESS_GRACE_MINUTES + 1)

        response = self.client.post(f'/api/images/{image.uuid}/rescan/')

        self.assertEqual(response.status_code, 200, response.data)
        delay.assert_called_once()
        image.refresh_from_db()
        self.assertEqual(image.scan_status, 'pending')

    @patch('core.tasks.generate_sbom_and_create_components.delay')
    def test_rescan_still_refuses_a_live_scan(self, delay):
        image = Image.objects.create(name='registry.example/live:1', digest='sha256:6', scan_status='in_process')
        run, _ = queue_scan(image)
        claim_scan(run.pk)

        response = self.client.post(f'/api/images/{image.uuid}/rescan/')

        self.assertEqual(response.status_code, 409)
        delay.assert_not_called()


class HelmPlaceholderImageTests(SimpleTestCase):
    CHART_URL = (
        'https://registry.example.zone/artifactory/api/helm/helm-stable/'
        'billing-export/billing-export-4.7.165.tgz'
    )

    def test_repo_host_placeholders_resolve_to_chart_registry_host(self):
        rendered = '\n'.join([
            '        image: docker.$REPO_HOST/billing-export:4.7.165',
            '          image: "docker.${REPO_HOST}/storefront:11.2.3850"',
            '        image: docker.registry.example.zone/core-api:21.31.0.99',
        ])
        refs = _extract_image_refs_from_text(rendered, _placeholder_substitutions(self.CHART_URL))
        self.assertEqual(refs, {
            'docker.registry.example.zone/billing-export:4.7.165',
            'docker.registry.example.zone/storefront:11.2.3850',
            'docker.registry.example.zone/core-api:21.31.0.99',
        })

    def test_unresolvable_placeholders_are_dropped_not_guessed(self):
        rendered = 'image: docker.${UNKNOWN_HOST}/app:1\nimage: docker.$REPO_HOST/app:2'
        self.assertEqual(_extract_image_refs_from_text(rendered, {}), set())

    def test_explicit_repo_host_wins_over_non_url_chart_ref(self):
        self.assertEqual(
            _placeholder_substitutions('charts/app:sha256:abc', 'registry.example'),
            {'REPO_HOST': 'registry.example'},
        )
        self.assertEqual(_placeholder_substitutions('charts/app:sha256:abc'), {})

    def test_values_strings_that_merely_contain_a_colon_are_not_images(self):
        for value in (
            '-XX:InitialRAMPercentage=30.0 -XX:MaxRAMPercentage=70.0 -XX:MetaspaceSize=96m',
            'ApiKey NN-XXX-XXX-XXX:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',
            'https://example.invalid:443',
            '/elasticsearch:8.19.14',
            'key: value',
        ):
            self.assertFalse(_looks_like_image_ref(value), value)

    def test_real_image_refs_are_still_recognised(self):
        for value in (
            'docker.registry.example.zone/billing-export:4.7.165',
            'registry:5000/team/app:1.2',
            'postgres:17-alpine',
            'busybox@sha256:' + 'a' * 64,
            '"quoted.example/app:1"',
        ):
            self.assertTrue(_looks_like_image_ref(value), value)
