from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from core.models import ContainerRegistry, Repository
from core.tasks import _select_tags_for_scan, periodic_repository_scan


class RepositoryTagSelectionTests(SimpleTestCase):
    def test_legacy_latest_only_behavior_is_preserved(self):
        selected = _select_tags_for_scan(
            ['29.2', '28.3', 'latest'],
            selection_mode='latest_only',
        )

        self.assertEqual(selected, ['latest'])

    def test_selects_latest_version_from_each_major_line(self):
        selected = _select_tags_for_scan(
            ['28.1', '28.2', '29.1', '29.2', '28.3'],
            selection_mode='latest_per_release_line',
            release_line_depth=1,
            release_lines_limit=2,
        )

        self.assertEqual(selected, ['29.2', '28.3'])

    def test_major_minor_lines_detect_patch_backports(self):
        selected = _select_tags_for_scan(
            ['28.1', '28.1.2', '28.2', '29.1', '29.2'],
            selection_mode='latest_per_release_line',
            release_line_depth=2,
            release_lines_limit=4,
        )

        self.assertEqual(selected, ['29.2', '29.1', '28.2', '28.1.2'])

    def test_prereleases_are_optional_and_latest_alias_is_separate(self):
        stable_only = _select_tags_for_scan(
            ['29.2-rc1', '29.1', '28.3', 'latest'],
            selection_mode='latest_per_release_line',
            release_line_depth=1,
            release_lines_limit=2,
            include_prerelease=False,
            scan_latest_alias=True,
        )
        with_prerelease = _select_tags_for_scan(
            ['29.2-rc1', '29.1', '28.3'],
            selection_mode='latest_per_release_line',
            release_line_depth=1,
            release_lines_limit=2,
            include_prerelease=True,
        )

        self.assertEqual(stable_only, ['29.1', '28.3', 'latest'])
        self.assertEqual(with_prerelease, ['29.2-rc1', '28.3'])


class PeriodicRepositoryScanPolicyTests(TestCase):
    def setUp(self):
        registry = ContainerRegistry.objects.create(
            name='registry',
            provider='acr',
            api_url='https://registry.example.com',
        )
        self.repository = Repository.objects.create(
            name='example/service',
            url='registry.example.com/example/service',
            status=True,
            container_registry=registry,
        )

    @patch('core.tasks.scan_repository_tags.apply_async')
    def test_no_periodic_kwargs_preserve_legacy_latest_only_call(self, apply_async):
        apply_async.return_value = SimpleNamespace(id='legacy-task')

        periodic_repository_scan.run()

        apply_async.assert_called_once_with(
            args=[str(self.repository.uuid)],
            kwargs={'latest_only': True, 'process_existing': True},
        )

    @patch('core.tasks.scan_repository_tags.apply_async')
    def test_release_line_policy_is_forwarded_to_repository_scan(self, apply_async):
        apply_async.return_value = SimpleNamespace(id='release-line-task')

        periodic_repository_scan.run(
            selection_mode='latest_per_release_line',
            release_line_depth=2,
            release_lines_limit=5,
            include_prerelease=False,
            scan_latest_alias=True,
            tag_candidates_limit=750,
            process_existing=False,
        )

        apply_async.assert_called_once_with(
            args=[str(self.repository.uuid)],
            kwargs={
                'latest_only': True,
                'process_existing': False,
                'selection_mode': 'latest_per_release_line',
                'release_line_depth': 2,
                'release_lines_limit': 5,
                'include_prerelease': False,
                'scan_latest_alias': True,
                'tag_candidates_limit': 750,
            },
        )
