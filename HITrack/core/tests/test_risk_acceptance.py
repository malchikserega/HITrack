from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import AuditEvent, RiskAcceptance, Vulnerability


class RiskAcceptanceApiTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(username='security-admin', password='test-password')
        self.admin.groups.add(Group.objects.create(name='admin'))
        self.operator = get_user_model().objects.create_user(username='operator', password='test-password')
        self.operator.groups.add(Group.objects.create(name='operator'))
        self.vulnerability = Vulnerability.objects.create(
            vulnerability_id='CVE-2026-10001', severity='HIGH', epss=0.72,
        )
        self.url = f'/api/vulnerabilities/{self.vulnerability.uuid}'
        self.client = APIClient()

    def test_admin_can_accept_and_revoke_with_audited_reason(self):
        self.client.force_authenticate(self.admin)
        expires_at = timezone.now() + timedelta(days=30)
        created = self.client.post(f'{self.url}/accept-risk/', {
            'reason': 'Compensating control blocks the vulnerable code path.',
            'expires_at': expires_at.isoformat(),
        }, format='json')
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data['status'], 'active')
        self.assertEqual(created.data['created_by_username'], self.admin.username)
        self.assertTrue(AuditEvent.objects.filter(action='risk_acceptance.created').exists())

        detail = self.client.get(f'{self.url}/?include_analytics=0')
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.data['is_suppressed'])
        self.assertIn('Compensating control', detail.data['suppression_reason'])

        duplicate = self.client.post(f'{self.url}/accept-risk/', {
            'reason': 'A second concurrent decision must not be accepted.',
            'expires_at': expires_at.isoformat(),
        }, format='json')
        self.assertEqual(duplicate.status_code, 409)

        revoked = self.client.post(f'{self.url}/revoke-risk-acceptance/', format='json')
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(revoked.data['status'], 'revoked')
        self.assertTrue(AuditEvent.objects.filter(action='risk_acceptance.revoked').exists())

    def test_operator_cannot_accept_risk(self):
        self.client.force_authenticate(self.operator)
        response = self.client.post(f'{self.url}/accept-risk/', {
            'reason': 'Operator should not be allowed to make this decision.',
            'expires_at': (timezone.now() + timedelta(days=30)).isoformat(),
        }, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(RiskAcceptance.objects.exists())

    def test_acceptance_is_time_bounded(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(f'{self.url}/accept-risk/', {
            'reason': 'An excessively long exception should be rejected.',
            'expires_at': (timezone.now() + timedelta(days=366)).isoformat(),
        }, format='json')
        self.assertEqual(response.status_code, 400)
