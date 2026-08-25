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

    def test_dotnet_ecosystem_is_inferred_from_nuget_purl(self):
        component = Component.objects.create(name='Newtonsoft.Json', type='unknown')
        version = ComponentVersion.objects.create(
            component=component,
            version='12.0.1',
            purl='pkg:nuget/Newtonsoft.Json@12.0.1',
        )
        version.images.add(self.image)
        ComponentVersionVulnerability.objects.create(
            component_version=version, vulnerability=self.high, fixable=True,
        )

        dotnet = next(
            row for row in ImageSerializer(self.image).data['vulnerability_breakdown']
            if row['key'] == 'dotnet'
        )
        self.assertEqual(dotnet['label'], '.NET / NuGet')
        self.assertEqual(dotnet['vulnerable_components_count'], 1)

    def test_legacy_stored_summary_without_breakdown_is_rebuilt_from_grype(self):
        grype_data = {
            'matches': [{
                'artifact': {
                    'id': 'nuget-package', 'name': 'Example.Package', 'version': '1.0',
                    'type': 'unknown', 'purl': 'pkg:nuget/Example.Package@1.0',
                },
                'vulnerability': {'id': 'CVE-2025-9999', 'severity': 'HIGH'},
            }],
        }
        self.image.grype_data = grype_data
        self.image.vulnerability_summary = {'schema_version': 1, 'findings': 1}
        self.image.save(update_fields=['grype_data', 'vulnerability_summary'])

        data = ImageSerializer(self.image).data
        self.assertEqual(data['vulnerability_breakdown'][0]['key'], 'dotnet')


class GrypeEcosystemSummaryTests(TestCase):
    def test_common_language_ecosystems_and_schema_version(self):
        matches = []
        for package_type, purl in [
            ('dotnet', 'pkg:nuget/A@1'), ('unknown', 'pkg:pypi/B@1'),
            ('java-archive', 'pkg:maven/org.example/C@1'), ('go-module', 'pkg:golang/D@1'),
        ]:
            matches.append({
                'artifact': {'name': purl, 'version': '1', 'type': package_type, 'purl': purl},
                'vulnerability': {'id': f'CVE-{len(matches)}', 'severity': 'HIGH'},
            })
        summary = build_grype_vulnerability_summary({'matches': matches})
        self.assertEqual(summary['schema_version'], 2)
        self.assertEqual(
            {row['key'] for row in summary['vulnerability_breakdown']},
            {'dotnet', 'python', 'java', 'go'},
        )
