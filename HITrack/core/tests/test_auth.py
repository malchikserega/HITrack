from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch
from core.models import ContainerRegistry


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='operator-user', password='safe-test-password', email='operator@example.com',
        )
        self.user.groups.add(Group.objects.create(name='operator'))
        self.client = APIClient()

    def test_login_me_logout_and_refresh_cookie_revocation(self):
        login = self.client.post('/api/auth/token/', {
            'username': self.user.username, 'password': 'safe-test-password',
        }, format='json')
        self.assertEqual(login.status_code, 200)
        self.assertIn('access', login.data)
        self.assertNotIn('refresh', login.data)
        self.assertIn('hitrack_refresh', login.cookies)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        me = self.client.get('/api/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.data['can_write'])
        self.assertFalse(me.data['is_admin'])

        # Logout must still reach the cookie-clearing endpoint when the access
        # token is already expired or otherwise invalid.
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-access-token')
        logout = self.client.post('/api/auth/logout/')
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(logout.cookies['hitrack_refresh'].value, '')
        refresh = self.client.post('/api/auth/token/refresh/', format='json')
        self.assertEqual(refresh.status_code, 401)

    def test_logout_is_idempotent_without_a_session(self):
        response = self.client.post('/api/auth/logout/')
        self.assertEqual(response.status_code, 204)

    def test_refresh_requires_cookie_and_rotates_refresh_cookie(self):
        missing = self.client.post('/api/auth/token/refresh/', format='json')
        self.assertEqual(missing.status_code, 401)

        login = self.client.post('/api/auth/token/', {
            'username': self.user.username, 'password': 'safe-test-password',
        }, format='json')
        refreshed = self.client.post('/api/auth/token/refresh/', format='json')
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn('access', refreshed.data)
        self.assertNotIn('refresh', refreshed.data)
        self.assertTrue(self.client.cookies['hitrack_refresh']['httponly'])

    @patch('core.auth.cache.get', return_value='ok')
    @patch('core.auth.cache.set')
    def test_health_is_public_and_checks_dependencies(self, _cache_set, _cache_get):
        self.client.credentials()
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {
            'status': 'ok', 'checks': {'database': True, 'cache': True},
        })

    def test_viewer_cannot_change_registry_policy(self):
        viewer = get_user_model().objects.create_user(username='viewer', password='test-password')
        registry = ContainerRegistry.objects.create(name='test-registry', provider='acr')
        self.client.force_authenticate(viewer)
        response = self.client.patch(
            f'/api/registries/{registry.uuid}/',
            {'image_fallback_repositories': []},
            format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_read_current_user_or_registries(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.assertEqual(self.client.get('/api/registries/').status_code, 401)

    def test_security_admin_can_change_registry_policy(self):
        admin = get_user_model().objects.create_user(username='admin-user', password='test-password')
        admin.groups.add(Group.objects.create(name='admin'))
        registry = ContainerRegistry.objects.create(name='admin-registry', provider='acr')
        self.client.force_authenticate(admin)
        response = self.client.patch(
            f'/api/registries/{registry.uuid}/',
            {'image_fallback_repositories': []},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
