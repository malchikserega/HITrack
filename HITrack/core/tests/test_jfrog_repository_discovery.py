from unittest.mock import patch

from django.test import TestCase

from core.models import ContainerRegistry, Repository
from core.services.jfrog_discovery import sync_jfrog_registry_repositories
from core.tasks import sync_jfrog_repositories, sync_single_jfrog_registry


class JFrogRegistryDiscoveryServiceTests(TestCase):
    def setUp(self):
        self.registry = ContainerRegistry.objects.create(
            name='artifactory-one',
            provider='jfrog',
            api_url='https://jfrog.example.test/artifactory',
            login='registry-user',
            password='registry-password',
        )

    @patch('core.services.jfrog_discovery.get_repo_images')
    @patch('core.services.jfrog_discovery.get_catalog')
    @patch('core.services.jfrog_discovery.get_repositories_rest')
    @patch('core.services.jfrog_discovery.get_bearer_token', return_value='basic-token')
    def test_discovers_paginated_docker_projects_and_helm_charts(
        self,
        get_token,
        get_repo_keys,
        get_catalog,
        get_repo_images,
    ):
        get_repo_keys.side_effect = lambda _url, _token, package_type: (
            [('docker-local', 'https://jfrog.example.test/artifactory/docker-local')]
            if package_type == 'docker'
            else [('helm-local', 'https://jfrog.example.test/artifactory/helm-local')]
        )
        get_catalog.side_effect = [
            (['apps/orders'], 'apps/orders'),
            (['apps/payments'], None),
        ]
        get_repo_images.return_value = [
            (
                'helm-local/platform-chart',
                'https://jfrog.example.test/artifactory/helm-local/platform-chart',
                'helm',
                'helm-local',
            ),
        ]

        result = sync_jfrog_registry_repositories(self.registry)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['repo_keys_discovered'], 2)
        self.assertEqual(result['projects_discovered'], 3)
        self.assertEqual(result['created'], 3)
        self.assertEqual(
            set(Repository.objects.values_list('name', 'repo_key', 'repository_type')),
            {
                ('docker-local/apps/orders', 'docker-local', 'docker'),
                ('docker-local/apps/payments', 'docker-local', 'docker'),
                ('helm-local/platform-chart', 'helm-local', 'helm'),
            },
        )
        self.assertEqual(Repository.objects.filter(status=True).count(), 3)
        self.registry.refresh_from_db()
        self.assertIsNotNone(self.registry.last_sync)
        get_token.assert_called_once_with(self.registry)
        self.assertEqual(get_catalog.call_count, 2)

    @patch('core.services.jfrog_discovery.get_repo_images', return_value=[])
    @patch('core.services.jfrog_discovery.get_catalog')
    @patch('core.services.jfrog_discovery.get_repositories_rest')
    @patch('core.services.jfrog_discovery.get_bearer_token', return_value='basic-token')
    def test_second_sync_is_idempotent_and_preserves_disabled_status(
        self,
        _get_token,
        get_repo_keys,
        get_catalog,
        _get_repo_images,
    ):
        get_repo_keys.side_effect = lambda _url, _token, package_type: (
            [('docker-local', 'unused')] if package_type == 'docker' else []
        )
        get_catalog.return_value = (['orders'], None)
        first = sync_jfrog_registry_repositories(self.registry)
        repository = Repository.objects.get(name='docker-local/orders')
        repository.status = False
        repository.save(update_fields=['status'])

        second = sync_jfrog_registry_repositories(self.registry)

        self.assertEqual(first['created'], 1)
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['existing'], 1)
        self.assertEqual(Repository.objects.count(), 1)
        repository.refresh_from_db()
        self.assertFalse(repository.status)

    @patch('core.services.jfrog_discovery.get_repo_images', return_value=[])
    @patch('core.services.jfrog_discovery.get_catalog')
    @patch('core.services.jfrog_discovery.get_repositories_rest')
    @patch('core.services.jfrog_discovery.get_bearer_token', return_value='basic-token')
    def test_repo_key_failure_is_partial_and_does_not_advance_last_sync(
        self,
        _get_token,
        get_repo_keys,
        get_catalog,
        _get_repo_images,
    ):
        get_repo_keys.side_effect = lambda _url, _token, package_type: (
            [('working-local', 'unused'), ('broken-local', 'unused')]
            if package_type == 'docker'
            else []
        )

        def catalog(_registry, repo_key, **_kwargs):
            if repo_key == 'broken-local':
                raise RuntimeError('catalog unavailable')
            return ['orders'], None

        get_catalog.side_effect = catalog

        result = sync_jfrog_registry_repositories(self.registry)

        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['repo_keys_succeeded'], 1)
        self.assertEqual(result['errors'][0]['repo_key'], 'broken-local')
        self.registry.refresh_from_db()
        self.assertIsNone(self.registry.last_sync)
        self.assertTrue(Repository.objects.filter(name='working-local/orders').exists())

    @patch('core.services.jfrog_discovery.get_repo_images', return_value=[])
    @patch('core.services.jfrog_discovery.get_catalog', return_value=(['orders'], None))
    @patch('core.services.jfrog_discovery.get_repositories_rest')
    @patch('core.services.jfrog_discovery.get_bearer_token', return_value='basic-token')
    def test_new_repositories_can_be_created_inactive(
        self,
        _get_token,
        get_repo_keys,
        _get_catalog,
        _get_repo_images,
    ):
        get_repo_keys.side_effect = lambda _url, _token, package_type: (
            [('docker-local', 'unused')] if package_type == 'docker' else []
        )

        sync_jfrog_registry_repositories(self.registry, activate_new=False)

        self.assertFalse(Repository.objects.get().status)


class SyncJFrogRepositoriesTaskTests(TestCase):
    def setUp(self):
        self.jfrog_one = ContainerRegistry.objects.create(
            name='jfrog-one',
            provider='jfrog',
            api_url='https://one.example.test/artifactory',
        )
        self.jfrog_two = ContainerRegistry.objects.create(
            name='jfrog-two',
            provider='jfrog',
            api_url='https://two.example.test/artifactory',
        )
        ContainerRegistry.objects.create(
            name='acr-one',
            provider='acr',
            api_url='https://acr.example.test',
        )

    @patch('core.tasks.sync_single_jfrog_registry.apply_async')
    def test_task_queues_each_jfrog_registry_and_not_acr(
        self,
        apply_async,
    ):
        apply_async.side_effect = lambda args, kwargs: type(
            'AsyncResult',
            (),
            {'id': f'task-{args[0]}'},
        )()

        result = sync_jfrog_repositories.run()

        self.assertEqual(apply_async.call_count, 2)
        self.assertEqual(
            {call.kwargs['args'][0] for call in apply_async.call_args_list},
            {str(self.jfrog_one.uuid), str(self.jfrog_two.uuid)},
        )
        self.assertEqual(result['status'], 'queued')
        self.assertEqual(result['summary']['registry_syncs_queued'], 2)
        self.assertEqual(
            apply_async.call_args.kwargs['kwargs']['catalog_page_size'],
            500,
        )

    @patch('core.tasks.sync_single_jfrog_registry.apply_async')
    def test_queue_failure_for_one_registry_does_not_block_the_other(
        self,
        apply_async,
    ):
        successful_result = type('AsyncResult', (), {'id': 'second-task'})()
        apply_async.side_effect = [RuntimeError('broker publish failed'), successful_result]

        result = sync_jfrog_repositories.run()

        self.assertEqual(apply_async.call_count, 2)
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['summary']['registry_syncs_queued'], 1)
        self.assertEqual(result['summary']['registry_syncs_failed_to_queue'], 1)

    @patch('core.tasks.sync_single_jfrog_registry.apply_async')
    def test_invalid_discovery_options_fail_before_queueing(self, apply_async):
        with self.assertRaisesRegex(ValueError, 'at least one'):
            sync_jfrog_repositories.run(include_docker=False, include_helm=False)

        apply_async.assert_not_called()

    @patch('core.tasks.cache.get', return_value='another-task')
    @patch('core.tasks.cache.add', return_value=False)
    @patch('core.services.jfrog_discovery.sync_jfrog_registry_repositories')
    def test_overlapping_registry_sync_is_skipped(
        self,
        sync_registry,
        _cache_add,
        _cache_get,
    ):
        result = sync_single_jfrog_registry.run(registry_uuid=str(self.jfrog_one.uuid))

        sync_registry.assert_not_called()
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'sync_already_in_process')

    @patch('core.tasks.time.time_ns', return_value=123)
    @patch('core.tasks.cache.delete')
    @patch('core.tasks.cache.get', return_value='worker-123')
    @patch('core.tasks.cache.add', return_value=True)
    @patch('core.services.jfrog_discovery.sync_jfrog_registry_repositories')
    def test_single_registry_task_returns_result_and_releases_lock(
        self,
        sync_registry,
        _cache_add,
        _cache_get,
        cache_delete,
        _time_ns,
    ):
        sync_registry.return_value = {
            'registry': self.jfrog_one.name,
            'registry_uuid': str(self.jfrog_one.uuid),
            'status': 'success',
            'projects_discovered': 2,
            'created': 2,
            'errors': [],
        }

        result = sync_single_jfrog_registry.run(
            registry_uuid=str(self.jfrog_one.uuid),
        )

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['task_name'], 'Sync Single JFrog Registry')
        cache_delete.assert_called_once()
