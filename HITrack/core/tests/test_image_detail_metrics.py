from django.test import TestCase

from core.models import (
    Component,
    ComponentVersion,
    ComponentVersionVulnerability,
    Image,
    Vulnerability,
)
from core.serializers import ImageSerializer


class ImageDetailMetricsTests(TestCase):
    def setUp(self):
        self.image = Image.objects.create(name='registry.example.com/service:1.0.0')
        self.critical = Vulnerability.objects.create(
            vulnerability_id='CVE-2024-0001', severity='CRITICAL',
        )
        self.high = Vulnerability.objects.create(
            vulnerability_id='CVE-2024-0002', severity='HIGH',
        )
        self.medium = Vulnerability.objects.create(
            vulnerability_id='CVE-2024-0003', severity='MEDIUM',
        )

        # component_a is fully fixable: every detected vulnerability has a fix.
        component_a = Component.objects.create(name='component-a', type='deb')
        version_a = ComponentVersion.objects.create(component=component_a, version='1.0')
        version_a.images.add(self.image)
        ComponentVersionVulnerability.objects.create(
            component_version=version_a, vulnerability=self.critical, fixable=True,
        )
        ComponentVersionVulnerability.objects.create(
            component_version=version_a, vulnerability=self.high, fixable=True,
        )

        # component_b has one fixable and one unfixable finding, so none of its
        # vulnerabilities belong in the "fully fixable components" summary.
        component_b = Component.objects.create(name='component-b', type='deb')
        version_b = ComponentVersion.objects.create(component=component_b, version='2.0')
        version_b.images.add(self.image)
        ComponentVersionVulnerability.objects.create(
            component_version=version_b, vulnerability=self.critical, fixable=True,
        )
        ComponentVersionVulnerability.objects.create(
            component_version=version_b, vulnerability=self.medium, fixable=False,
        )

    def test_unique_vulnerabilities_are_deduplicated_across_components(self):
        data = ImageSerializer(self.image).data

        self.assertEqual(data['findings'], 4)
        self.assertEqual(data['unique_findings'], 3)
        self.assertEqual(data['severity_counts']['CRITICAL'], 2)
        self.assertEqual(data['unique_severity_counts']['CRITICAL'], 1)

    def test_fully_fixable_summary_excludes_partially_fixable_components(self):
        data = ImageSerializer(self.image).data

        self.assertEqual(data['fully_fixable_components_count'], 1)
        self.assertEqual(data['fully_fixable_findings'], 2)
        self.assertEqual(data['fully_fixable_unique_findings'], 2)
        self.assertEqual(data['fully_fixable_severity_counts']['CRITICAL'], 1)
        self.assertEqual(data['fully_fixable_severity_counts']['HIGH'], 1)
        self.assertEqual(data['fully_fixable_severity_counts']['MEDIUM'], 0)

        # The legacy individually-fixable metric stays available and correctly
        # includes the fixable CVE from the partially-fixable component.
        self.assertEqual(data['fixable_findings'], 3)
        self.assertEqual(data['fixable_unique_findings'], 2)
