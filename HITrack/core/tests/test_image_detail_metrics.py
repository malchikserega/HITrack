from django.test import TestCase

from core.models import (
    Component,
    ComponentVersion,
    ComponentVersionVulnerability,
    Image,
    Vulnerability,
)
from core.serializers import ImageSerializer
from core.utils.image_vulnerability_summary import build_grype_vulnerability_summary
from core.views import _build_optimized_image_list_queryset, _hydrate_image_list_page_metrics


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
        self.assertEqual(sum(data['severity_counts'].values()), data['findings'])
        self.assertEqual(sum(data['unique_severity_counts'].values()), data['unique_findings'])

    def test_fully_fixable_summary_excludes_partially_fixable_components(self):
        data = ImageSerializer(self.image).data

        self.assertEqual(data['fully_fixable_components_count'], 1)
        self.assertEqual(data['fully_fixable_findings'], 2)
        self.assertEqual(data['fully_fixable_unique_findings'], 2)
        self.assertEqual(data['fully_fixable_severity_counts']['CRITICAL'], 1)
        self.assertEqual(data['fully_fixable_severity_counts']['HIGH'], 1)
        self.assertEqual(data['fully_fixable_severity_counts']['MEDIUM'], 0)
        self.assertEqual(
            sum(data['fully_fixable_severity_counts'].values()),
            data['fully_fixable_findings'],
        )
        self.assertEqual(
            sum(data['fully_fixable_unique_severity_counts'].values()),
            data['fully_fixable_unique_findings'],
        )

        # The legacy individually-fixable metric stays available and correctly
        # includes the fixable CVE from the partially-fixable component.
        self.assertEqual(data['fixable_findings'], 3)
        self.assertEqual(data['fixable_unique_findings'], 2)

    def test_negligible_and_unrecognized_severities_are_not_lost_from_chart_counts(self):
        component = Component.objects.create(name='component-c', type='deb')
        version = ComponentVersion.objects.create(component=component, version='3.0')
        version.images.add(self.image)
        negligible = Vulnerability.objects.create(
            vulnerability_id='CVE-2024-0004', severity='NEGLIGIBLE',
        )
        legacy_info = Vulnerability.objects.create(
            vulnerability_id='CVE-2024-0005', severity='INFO',
        )
        ComponentVersionVulnerability.objects.create(
            component_version=version, vulnerability=negligible, fixable=True,
        )
        ComponentVersionVulnerability.objects.create(
            component_version=version, vulnerability=legacy_info, fixable=True,
        )

        data = ImageSerializer(self.image).data

        self.assertEqual(data['severity_counts']['NEGLIGIBLE'], 1)
        self.assertEqual(data['severity_counts']['UNKNOWN'], 1)
        self.assertEqual(sum(data['severity_counts'].values()), data['findings'])

    def test_vulnerabilities_are_grouped_by_package_ecosystem(self):
        python_component = Component.objects.create(name='requests', type='python')
        python_version = ComponentVersion.objects.create(
            component=python_component,
            version='2.32.0',
        )
        python_version.images.add(self.image)
        ComponentVersionVulnerability.objects.create(
            component_version=python_version,
            vulnerability=self.high,
            fixable=False,
        )

        data = ImageSerializer(self.image).data
        breakdown = {item['key']: item for item in data['vulnerability_breakdown']}

        self.assertEqual(set(breakdown), {'os', 'python'})
        self.assertEqual(breakdown['os']['findings'], 4)
        self.assertEqual(breakdown['os']['unique_findings'], 3)
        self.assertEqual(breakdown['os']['vulnerable_components_count'], 2)
        self.assertEqual(breakdown['python']['findings'], 1)
        self.assertEqual(breakdown['python']['unique_findings'], 1)
        self.assertEqual(breakdown['python']['severity_counts']['HIGH'], 1)
        self.assertEqual(breakdown['python']['fully_fixable_findings'], 0)
        self.assertEqual(
            sum(item['findings'] for item in data['vulnerability_breakdown']),
            data['findings'],
        )

    def test_ecosystem_breakdown_does_not_add_queries(self):
        image = Image.objects.get(pk=self.image.pk)

        with self.assertNumQueries(2):
            summary = ImageSerializer()._get_summary(image)

        self.assertEqual(summary['findings'], 4)
        self.assertEqual(summary['vulnerability_breakdown'][0]['key'], 'os')

    def test_raw_grype_matches_are_authoritative_for_image_counts(self):
        self.image.grype_data = {
            'matches': [
                {
                    'artifact': {
                        'id': 'python-artifact',
                        'name': 'requests',
                        'version': '2.31.0',
                        'type': 'python',
                    },
                    'vulnerability': {
                        'id': 'CVE-2024-9999',
                        'severity': 'High',
                        'fix': {'state': 'fixed', 'versions': ['2.32.0']},
                    },
                },
            ],
        }
        self.image.save(update_fields=['grype_data'])

        data = ImageSerializer(self.image).data

        # The image has four legacy/global CVV links, but only its own raw
        # Grype match must contribute to image-detail counters.
        self.assertEqual(data['findings'], 1)
        self.assertEqual(data['unique_findings'], 1)
        self.assertEqual(data['severity_counts']['HIGH'], 1)
        self.assertEqual(data['vulnerability_breakdown'][0]['key'], 'python')

    def test_image_list_uses_the_same_scoped_summary_as_detail(self):
        grype_data = {
            'matches': [
                {
                    'artifact': {'id': 'one', 'type': 'python'},
                    'vulnerability': {'id': 'CVE-2024-9999', 'severity': 'High'},
                },
            ],
        }
        self.image.vulnerability_summary = build_grype_vulnerability_summary(grype_data)
        self.image.save(update_fields=['vulnerability_summary'])

        lightweight_image = Image.objects.get(pk=self.image.pk)
        _hydrate_image_list_page_metrics([lightweight_image])
        self.assertEqual(lightweight_image.findings_count, 1)
        self.assertEqual(lightweight_image.unique_findings_count, 1)

        optimized_image = _build_optimized_image_list_queryset(
            Image.objects.filter(pk=self.image.pk)
        ).get()
        self.assertEqual(optimized_image.findings_count, 1)
        self.assertEqual(optimized_image.unique_findings_count, 1)
