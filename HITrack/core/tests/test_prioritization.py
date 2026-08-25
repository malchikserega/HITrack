from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import (
    Component, ComponentVersion, ComponentVersionVulnerability, Image,
    RiskAcceptance, ScanRun, Vulnerability,
)
from core.utils.prioritization import build_prioritization_payload


class PrioritizationAnalyticsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='admin')
        image = Image.objects.create(
            name='registry.example/app:1', scan_status='success',
            sbom_data={'artifacts': []}, grype_data={'matches': []},
        )
        # Legacy/ambiguous component types must still be classified from PURL.
        component = Component.objects.create(name='Newtonsoft.Json', type='unknown')
        version = ComponentVersion.objects.create(
            component=component, version='12.0.1', purl='pkg:nuget/Newtonsoft.Json@12.0.1',
        )
        version.images.add(image)
        self.vulnerability = Vulnerability.objects.create(
            vulnerability_id='CVE-2026-20001', severity='CRITICAL', epss=0.9,
        )
        ComponentVersionVulnerability.objects.create(
            component_version=version,
            vulnerability=self.vulnerability,
            fixable=True,
            fix_status='fixed',
            fix_versions=['13.0.1', '13.0.3'],
        )
        ScanRun.objects.create(
            image=image,
            idempotency_key='test-successful-scan',
            status='success',
            finished_at=timezone.now() - timedelta(days=2),
        )

    def test_prioritizes_fixable_dotnet_package_and_coverage(self):
        payload = build_prioritization_payload(ecosystem='dotnet')
        opportunity = payload['remediation_opportunities'][0]
        self.assertEqual(opportunity['component_type'], 'unknown')
        self.assertEqual(opportunity['recommended_version'], '13.0.3')
        self.assertGreater(opportunity['risk_score'], 0)
        self.assertEqual(payload['scan_freshness']['fully_analyzed_percentage'], 100.0)
        self.assertEqual(payload['scan_freshness']['freshness_buckets']['fresh'], 1)

    def test_active_acceptance_is_excluded_by_default(self):
        RiskAcceptance.objects.create(
            vulnerability=self.vulnerability,
            reason='Accepted temporarily with a compensating runtime control.',
            expires_at=timezone.now() + timedelta(days=30),
            created_by=self.user,
        )
        excluded = build_prioritization_payload(ecosystem='dotnet')
        included = build_prioritization_payload(ecosystem='dotnet', include_suppressed=True)
        self.assertEqual(excluded['remediation_opportunities'], [])
        self.assertEqual(excluded['active_suppressions_count'], 1)
        self.assertEqual(len(included['remediation_opportunities']), 1)
