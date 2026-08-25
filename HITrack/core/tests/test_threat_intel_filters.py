from django.test import SimpleTestCase, TestCase

from core.views import _filter_weekly_threat_intel_rows
from core.models import (
    Component, ComponentVersion, ComponentVersionVulnerability, Image,
    Repository, RepositoryTag, Vulnerability,
)
from core.utils.threat_intel import (
    _build_vulnerability_presence_map,
    _refresh_summary_hitrack_presence,
)
from core.utils.vulnerability_sources import VulnerabilityDataCollector


class WeeklyThreatIntelFilterTests(SimpleTestCase):
    rows = [
        {'identifier': 'GHSA-dotnet', 'title': 'NuGet issue', 'context': 'NUGET · Package.A', 'ecosystem': 'NuGet',
         'severity': 'HIGH', 'tags': ['Fix Available'], 'source_labels': ['GitHub'],
         'currently_present': True, 'relevant_in_hitrack': True},
        {'identifier': 'OSV-malware', 'title': 'npm malware', 'context': 'NPM · bad-package', 'ecosystem': 'npm',
         'severity': 'MALWARE', 'tags': ['Malware', 'No Fix'], 'source_labels': ['OSV'],
         'currently_present': False, 'relevant_in_hitrack': False},
    ]

    def test_combines_signal_presence_and_ecosystem_filters(self):
        result = _filter_weekly_threat_intel_rows(
            self.rows, signal='high', presence='present', ecosystem='nuget',
        )
        self.assertEqual([row['identifier'] for row in result], ['GHSA-dotnet'])

    def test_search_and_unmatched_filters(self):
        result = _filter_weekly_threat_intel_rows(
            self.rows, presence='unmatched', search='bad-package',
        )
        self.assertEqual([row['identifier'] for row in result], ['OSV-malware'])

    def test_ecosystem_aliases_and_component_search(self):
        rows = [{
            **self.rows[0],
            'ecosystem': 'crates.io',
            'affected_components': [{
                'name': 'serde_json', 'version': '1.0.1',
                'ecosystem': 'rust', 'purl': 'pkg:cargo/serde_json@1.0.1',
            }],
        }]
        result = _filter_weekly_threat_intel_rows(
            rows, ecosystem='rust', search='serde_json 1.0.1',
        )
        self.assertEqual(len(result), 1)

    def test_osv_candidate_cap_is_shared_fairly_across_ecosystems(self):
        candidates = VulnerabilityDataCollector._fair_sample_osv_candidates([
            ('npm', ['NPM-1', 'NPM-2', 'NPM-3']),
            ('PyPI', ['PYPI-1', 'PYPI-2', 'PYPI-3']),
            ('NuGet', ['NUGET-1', 'NUGET-2', 'NUGET-3']),
        ], total_cap=6)
        self.assertEqual(candidates, [
            'NPM-1', 'PYPI-1', 'NUGET-1',
            'NPM-2', 'PYPI-2', 'NUGET-2',
        ])


class WeeklyThreatIntelPresenceTests(TestCase):
    def test_presence_match_is_case_insensitive_and_returns_exact_components(self):
        repository = Repository.objects.create(name='payments', repository_type='docker')
        tag = RepositoryTag.objects.create(repository=repository, tag='production')
        image = Image.objects.create(name='registry.example/payments:production', scan_status='success')
        image.repository_tags.add(tag)
        component = Component.objects.create(name='Newtonsoft.Json', type='dotnet')
        component_version = ComponentVersion.objects.create(
            component=component,
            version='13.0.1',
            purl='pkg:nuget/Newtonsoft.Json@13.0.1',
        )
        component_version.images.add(image)
        vulnerability = Vulnerability.objects.create(
            vulnerability_id='GHSA-5CRP-9R3C-P9VR', severity='HIGH',
        )
        ComponentVersionVulnerability.objects.create(
            component_version=component_version,
            vulnerability=vulnerability,
        )

        result = _build_vulnerability_presence_map(['ghsa-5crp-9r3c-p9vr'])

        match = result['GHSA-5CRP-9R3C-P9VR']
        self.assertTrue(match['currently_present'])
        self.assertEqual(match['hitrack_match']['component_count'], 1)
        self.assertEqual(match['hitrack_match']['components'][0], {
            'component_version_uuid': str(component_version.uuid),
            'name': 'Newtonsoft.Json',
            'version': '13.0.1',
            'ecosystem': 'dotnet',
            'purl': 'pkg:nuget/Newtonsoft.Json@13.0.1',
            'image_count': 1,
            'images': ['registry.example/payments:production'],
        })

        stale_summary = {
            'observed_this_week': {'count': 0, 'entries': []},
            'kev_added_this_week': {'count': 1, 'entries': [{
                'vulnerability_id': 'ghsa-5crp-9r3c-p9vr',
                'currently_present': False,
            }]},
            'supply_chain_this_week': {'count': 0, 'entries': []},
        }
        refreshed = _refresh_summary_hitrack_presence(stale_summary)
        refreshed_entry = refreshed['kev_added_this_week']['entries'][0]
        self.assertTrue(refreshed_entry['currently_present'])
        self.assertEqual(refreshed_entry['match_status'], 'confirmed_present')
        self.assertEqual(
            refreshed_entry['hitrack_match']['components'][0]['name'],
            'Newtonsoft.Json',
        )
