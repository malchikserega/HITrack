from datetime import date, datetime, timedelta
from typing import Dict
from collections import defaultdict
import logging

from django.db.models import Exists, OuterRef
from django.db.models.functions import Upper
from django.utils import timezone

from core.models import ComponentVersionVulnerability, Image, RepositoryTag, ThreatIntelSnapshot, Vulnerability
from core.utils.vulnerability_sources import VulnerabilityDataCollector

logger = logging.getLogger(__name__)


def get_current_week_period():
    week_end = timezone.localdate()
    week_start = week_end - timedelta(days=week_end.weekday())
    return week_start, week_end


def _limit_summary_entries(summary: Dict, limit: int | None) -> Dict:
    if limit is None:
        return summary

    def limited_bucket(bucket: Dict | None) -> Dict:
        bucket = bucket or {}
        entries = list(bucket.get('entries') or [])
        limited = {
            'count': bucket.get('count', len(entries)),
            'entries': entries[:limit],
        }
        if 'relevant_in_hitrack_count' in bucket:
            limited['relevant_in_hitrack_count'] = bucket.get('relevant_in_hitrack_count', 0)
        if 'currently_present_count' in bucket:
            limited['currently_present_count'] = bucket.get('currently_present_count', 0)
        if 'collection_status' in bucket:
            limited['collection_status'] = bucket.get('collection_status')
        return limited

    return {
        'period_start': summary.get('period_start'),
        'period_end': summary.get('period_end'),
        'generated_at': summary.get('generated_at'),
        'observed_this_week': limited_bucket(summary.get('observed_this_week')),
        'kev_added_this_week': limited_bucket(summary.get('kev_added_this_week')),
        'supply_chain_this_week': limited_bucket(summary.get('supply_chain_this_week')),
    }


def _normalize_vulnerability_identifier(identifier: str | None) -> str | None:
    if not identifier:
        return None
    normalized = str(identifier).strip().upper()
    return normalized or None


def _parse_match_timestamp(value):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)

    try:
        if isinstance(value, str) and 'T' in value:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        return datetime.fromisoformat(f"{value}T00:00:00+00:00")
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _build_hitrack_location_preview(vulnerability_queryset) -> Dict[int, Dict]:
    vulnerability_ids = [vulnerability.pk for vulnerability in vulnerability_queryset]
    if not vulnerability_ids:
        return {}

    repositories_map = defaultdict(set)
    tags_map = defaultdict(set)
    images_map = defaultdict(set)
    components_map = defaultdict(dict)

    tag_rows = RepositoryTag.objects.filter(
        images__component_versions__componentversionvulnerability__vulnerability_id__in=vulnerability_ids,
    ).values(
        'images__component_versions__componentversionvulnerability__vulnerability_id',
        'repository__name',
        'tag',
    ).distinct()

    for row in tag_rows:
        vulnerability_id = row['images__component_versions__componentversionvulnerability__vulnerability_id']
        repository_name = row.get('repository__name')
        tag_name = row.get('tag')
        if repository_name:
            repositories_map[vulnerability_id].add(repository_name)
        if repository_name or tag_name:
            tag_label = " : ".join(part for part in [repository_name, tag_name] if part)
            if tag_label:
                tags_map[vulnerability_id].add(tag_label)

    image_rows = Image.objects.filter(
        component_versions__componentversionvulnerability__vulnerability_id__in=vulnerability_ids,
        repository_tags__isnull=False,
    ).values(
        'component_versions__componentversionvulnerability__vulnerability_id',
        'name',
    ).distinct()

    for row in image_rows:
        vulnerability_id = row['component_versions__componentversionvulnerability__vulnerability_id']
        image_name = row.get('name')
        if image_name:
            images_map[vulnerability_id].add(image_name)

    component_rows = ComponentVersionVulnerability.objects.filter(
        vulnerability_id__in=vulnerability_ids,
        component_version__images__repository_tags__isnull=False,
    ).values(
        'vulnerability_id',
        'component_version__uuid',
        'component_version__component__name',
        'component_version__component__type',
        'component_version__version',
        'component_version__purl',
        'component_version__images__name',
    ).distinct()

    for row in component_rows:
        vulnerability_id = row['vulnerability_id']
        component_version_uuid = str(row['component_version__uuid'])
        component = components_map[vulnerability_id].setdefault(component_version_uuid, {
            'component_version_uuid': component_version_uuid,
            'name': row.get('component_version__component__name') or 'Unknown package',
            'version': row.get('component_version__version') or 'Unknown version',
            'ecosystem': row.get('component_version__component__type') or 'unknown',
            'purl': row.get('component_version__purl'),
            'images': set(),
        })
        image_name = row.get('component_version__images__name')
        if image_name:
            component['images'].add(image_name)

    preview_map = {}
    for vulnerability in vulnerability_queryset:
        repository_names = sorted(repositories_map.get(vulnerability.pk, set()))
        tag_names = sorted(tags_map.get(vulnerability.pk, set()))
        image_names = sorted(images_map.get(vulnerability.pk, set()))
        component_matches = []
        for component in components_map.get(vulnerability.pk, {}).values():
            component_image_names = sorted(component.pop('images'))
            component_matches.append({
                **component,
                'image_count': len(component_image_names),
                'images': component_image_names[:3],
            })
        component_matches.sort(key=lambda item: (
            str(item['ecosystem']).casefold(),
            str(item['name']).casefold(),
            str(item['version']).casefold(),
        ))
        preview_map[vulnerability.pk] = {
            'repository_count': len(repository_names),
            'repositories': repository_names[:3],
            'tag_count': len(tag_names),
            'tags': tag_names[:3],
            'image_count': len(image_names),
            'images': image_names[:3],
            'component_count': len(component_matches),
            'components': component_matches[:10],
        }

    return preview_map


def _build_vulnerability_presence_map(identifiers) -> Dict[str, Dict]:
    normalized_identifiers = {
        normalized
        for normalized in (_normalize_vulnerability_identifier(identifier) for identifier in identifiers)
        if normalized
    }
    if not normalized_identifiers:
        return {}

    queryset = Vulnerability.objects.annotate(
        normalized_vulnerability_id=Upper('vulnerability_id'),
    ).filter(
        normalized_vulnerability_id__in=normalized_identifiers,
    ).annotate(
        currently_present=Exists(
            ComponentVersionVulnerability.objects.filter(
                vulnerability=OuterRef('pk'),
                component_version__images__repository_tags__isnull=False,
            )
        )
    ).only('uuid', 'vulnerability_id')
    vulnerabilities = list(queryset)
    location_preview_map = _build_hitrack_location_preview(vulnerabilities)

    return {
        vulnerability.vulnerability_id.upper(): {
            'uuid': str(vulnerability.uuid),
            'vulnerability_id': vulnerability.vulnerability_id,
            'currently_present': bool(vulnerability.currently_present),
            'hitrack_match': location_preview_map.get(vulnerability.pk, {
                'repository_count': 0,
                'repositories': [],
                'tag_count': 0,
                'tags': [],
                'image_count': 0,
                'images': [],
                'component_count': 0,
                'components': [],
            }),
        }
        for vulnerability in vulnerabilities
    }


def _normalize_identifier_candidates(identifier_candidates):
    normalized_candidates = []

    for candidate in identifier_candidates or []:
        match_type = 'Identifier'
        identifier = candidate
        if isinstance(candidate, dict):
            identifier = candidate.get('identifier')
            match_type = candidate.get('match_type') or match_type

        normalized_identifier = _normalize_vulnerability_identifier(identifier)
        if not normalized_identifier:
            continue

        normalized_candidates.append({
            'identifier': normalized_identifier,
            'match_type': match_type,
        })

    return normalized_candidates


def _augment_entries_with_hitrack_presence(entries, identifier_resolver, total_count: int | None = None) -> Dict:
    candidate_ids = []
    resolved_entry_ids = []
    for entry in entries:
        resolved_identifiers = _normalize_identifier_candidates(identifier_resolver(entry))
        resolved_entry_ids.append(resolved_identifiers)
        candidate_ids.extend(identifier['identifier'] for identifier in resolved_identifiers)

    presence_map = _build_vulnerability_presence_map(candidate_ids)
    relevant_count = 0
    currently_present_count = 0
    augmented_entries = []

    for entry, resolved_ids in zip(entries, resolved_entry_ids):
        matched_record = None
        matched_identifier = None
        matched_by = None
        for resolved_id in resolved_ids:
            matched_record = presence_map.get(resolved_id['identifier'])
            if matched_record:
                matched_identifier = resolved_id['identifier']
                matched_by = resolved_id['match_type']
                break

        if matched_record:
            relevant_count += 1
            if matched_record['currently_present']:
                currently_present_count += 1

        augmented_entries.append({
            **entry,
            'relevant_in_hitrack': bool(matched_record),
            'currently_present': bool(matched_record and matched_record['currently_present']),
            'match_status': (
                'confirmed_present' if matched_record and matched_record['currently_present']
                else 'historical' if matched_record
                else 'not_confirmed'
            ),
            'target_type': 'vulnerability' if matched_record else None,
            'target_uuid': matched_record['uuid'] if matched_record else None,
            'matched_identifier': matched_identifier,
            'matched_by': matched_by,
            'matched_vulnerability_id': matched_record['vulnerability_id'] if matched_record else None,
            'hitrack_match': matched_record['hitrack_match'] if matched_record else None,
        })

    return {
        'count': total_count if total_count is not None else len(augmented_entries),
        'entries': augmented_entries,
        'relevant_in_hitrack_count': relevant_count,
        'currently_present_count': currently_present_count,
    }


def _refresh_summary_hitrack_presence(summary: Dict) -> Dict:
    """Refresh inventory evidence without re-querying external feed providers."""
    observed_bucket = summary.get('observed_this_week') or {}
    observed_entries = list(observed_bucket.get('entries') or [])
    observed_map = _build_vulnerability_presence_map(
        entry.get('vulnerability_id') for entry in observed_entries
    )
    refreshed_observed_entries = []
    for entry in observed_entries:
        identifier = _normalize_vulnerability_identifier(entry.get('vulnerability_id'))
        matched_record = observed_map.get(identifier) if identifier else None
        refreshed_observed_entries.append({
            **entry,
            'relevant_in_hitrack': bool(matched_record),
            'currently_present': bool(matched_record and matched_record['currently_present']),
            'match_status': (
                'confirmed_present' if matched_record and matched_record['currently_present']
                else 'historical' if matched_record
                else 'not_confirmed'
            ),
            'target_type': 'vulnerability' if matched_record else None,
            'target_uuid': matched_record['uuid'] if matched_record else None,
            'matched_identifier': identifier if matched_record else None,
            'matched_by': 'Vulnerability ID' if matched_record else None,
            'matched_vulnerability_id': matched_record['vulnerability_id'] if matched_record else None,
            'hitrack_match': matched_record['hitrack_match'] if matched_record else None,
        })

    refreshed_observed = {
        **observed_bucket,
        'entries': refreshed_observed_entries,
        'relevant_in_hitrack_count': sum(
            1 for entry in refreshed_observed_entries if entry.get('relevant_in_hitrack')
        ),
        'currently_present_count': sum(
            1 for entry in refreshed_observed_entries if entry.get('currently_present')
        ),
    }

    kev_bucket = summary.get('kev_added_this_week') or {}
    refreshed_kev = {
        **kev_bucket,
        **_augment_entries_with_hitrack_presence(
            kev_bucket.get('entries') or [],
            lambda entry: [{'identifier': entry.get('vulnerability_id'), 'match_type': 'CVE ID'}],
            total_count=kev_bucket.get('count'),
        ),
    }

    supply_bucket = summary.get('supply_chain_this_week') or {}
    refreshed_supply_chain = {
        **supply_bucket,
        **_augment_entries_with_hitrack_presence(
            supply_bucket.get('entries') or [],
            lambda entry: [
                {'identifier': entry.get('ghsa_id'), 'match_type': 'GHSA ID'},
                {'identifier': entry.get('cve_id'), 'match_type': 'CVE ID'},
                {'identifier': entry.get('osv_id'), 'match_type': 'OSV ID'},
                *[
                    {'identifier': alias, 'match_type': 'Alias'}
                    for alias in (entry.get('aliases') or [])
                ],
                {'identifier': entry.get('advisory_id'), 'match_type': 'Advisory ID'},
            ],
            total_count=supply_bucket.get('count'),
        ),
    }

    return {
        **summary,
        'observed_this_week': refreshed_observed,
        'kev_added_this_week': refreshed_kev,
        'supply_chain_this_week': refreshed_supply_chain,
    }


def build_live_weekly_threat_intel_summary(limit: int | None = 5) -> Dict:
    current_timezone = timezone.get_current_timezone()
    week_start, week_end = get_current_week_period()
    week_start_datetime = timezone.make_aware(
        datetime.combine(week_start, datetime.min.time()),
        current_timezone,
    )
    week_end_datetime = timezone.make_aware(
        datetime.combine(week_end + timedelta(days=1), datetime.min.time()),
        current_timezone,
    )

    observed_queryset = Vulnerability.objects.filter(
        created_at__gte=week_start_datetime,
        created_at__lt=week_end_datetime,
    ).annotate(
        currently_present=Exists(
            ComponentVersionVulnerability.objects.filter(
                vulnerability=OuterRef('pk'),
                component_version__images__repository_tags__isnull=False,
            )
        )
    ).select_related('details').only(
        'uuid',
        'vulnerability_id',
        'severity',
        'vulnerability_type',
        'created_at',
        'epss',
        'details__cisa_kev_known_exploited',
        'details__exploit_available',
    ).order_by('-created_at')

    observed_presence_map = _build_vulnerability_presence_map(
        vulnerability.vulnerability_id for vulnerability in observed_queryset
    )

    observed_entries = [
        {
            'uuid': str(vulnerability.uuid),
            'vulnerability_id': vulnerability.vulnerability_id,
            'severity': vulnerability.severity,
            'type': vulnerability.vulnerability_type,
            'created_at': vulnerability.created_at.isoformat(),
            'epss': round(vulnerability.epss or 0, 3),
            'relevant_in_hitrack': True,
            'currently_present': bool(vulnerability.currently_present),
            'match_status': 'confirmed_present' if vulnerability.currently_present else 'historical',
            'target_type': 'vulnerability',
            'target_uuid': str(vulnerability.uuid),
            'cisa_kev': bool(getattr(vulnerability.details, 'cisa_kev_known_exploited', False))
            if getattr(vulnerability, 'details', None) else False,
            'exploit_available': bool(getattr(vulnerability.details, 'exploit_available', False))
            if getattr(vulnerability, 'details', None) else False,
            'matched_identifier': vulnerability.vulnerability_id,
            'matched_by': 'Vulnerability ID',
            'matched_vulnerability_id': vulnerability.vulnerability_id,
            'hitrack_match': observed_presence_map.get(
                vulnerability.vulnerability_id.upper(),
                {
                    'repository_count': 0,
                    'repositories': [],
                    'tag_count': 0,
                    'tags': [],
                    'image_count': 0,
                    'images': [],
                    'component_count': 0,
                    'components': [],
                },
            ).get('hitrack_match'),
        }
        for vulnerability in observed_queryset
    ]

    collector = VulnerabilityDataCollector()

    kev_collection_status = 'available'
    try:
        kev_summary = collector.get_weekly_cisa_kev_entries(week_start, week_end, limit=None)
    except Exception:
        logger.exception('Unable to collect the weekly CISA KEV feed')
        kev_collection_status = 'unavailable'
        kev_summary = {'count': 0, 'entries': []}

    supply_chain_collection_status = 'available'
    try:
        supply_chain_summary = collector.get_weekly_supply_chain_advisories(
            week_start,
            week_end,
            limit=None,
        )
    except Exception:
        logger.exception('Unable to collect the weekly supply-chain advisory feed')
        supply_chain_collection_status = 'unavailable'
        supply_chain_summary = {'count': 0, 'entries': []}

    supply_chain_metadata = {
        key: supply_chain_summary.get(key)
        for key in ('truncated', 'candidate_ids_considered', 'candidate_ids_available')
        if key in supply_chain_summary
    }

    kev_summary = _augment_entries_with_hitrack_presence(
        kev_summary.get('entries', []),
        lambda entry: [
            {
                'identifier': entry.get('vulnerability_id'),
                'match_type': 'CVE ID',
            }
        ],
        total_count=kev_summary.get('count'),
    )
    kev_summary['collection_status'] = kev_collection_status
    supply_chain_summary = _augment_entries_with_hitrack_presence(
        supply_chain_summary.get('entries', []),
        lambda entry: [
            {
                'identifier': entry.get('ghsa_id'),
                'match_type': 'GHSA ID',
            },
            {
                'identifier': entry.get('cve_id'),
                'match_type': 'CVE ID',
            },
            {
                'identifier': entry.get('osv_id'),
                'match_type': 'OSV ID',
            },
            *[
                {
                    'identifier': alias,
                    'match_type': 'Alias',
                }
                for alias in (entry.get('aliases') or [])
            ],
            {
                'identifier': entry.get('advisory_id'),
                'match_type': 'Advisory ID',
            },
        ],
        total_count=supply_chain_summary.get('count'),
    )
    supply_chain_summary.update(supply_chain_metadata)
    if supply_chain_collection_status == 'available' and supply_chain_metadata.get('truncated'):
        supply_chain_collection_status = 'partial'
    supply_chain_summary['collection_status'] = supply_chain_collection_status

    summary = {
        'period_start': week_start.isoformat(),
        'period_end': week_end.isoformat(),
        'generated_at': timezone.now().isoformat(),
        'observed_this_week': {
            'count': observed_queryset.count(),
            'relevant_in_hitrack_count': observed_queryset.count(),
            'currently_present_count': observed_queryset.filter(currently_present=True).count(),
            'collection_status': 'available',
            'entries': observed_entries,
        },
        'kev_added_this_week': kev_summary,
        'supply_chain_this_week': supply_chain_summary,
    }

    return _limit_summary_entries(summary, limit)


def save_weekly_threat_intel_snapshot(snapshot_date=None, limit: int | None = None) -> ThreatIntelSnapshot:
    snapshot_date = snapshot_date or timezone.localdate()
    summary = build_live_weekly_threat_intel_summary(limit=limit)
    period_start = summary['period_start']
    period_end = summary['period_end']

    if isinstance(period_start, str):
        period_start = date.fromisoformat(period_start)
    if isinstance(period_end, str):
        period_end = date.fromisoformat(period_end)

    snapshot, _ = ThreatIntelSnapshot.objects.update_or_create(
        snapshot_date=snapshot_date,
        defaults={
            'period_start': period_start,
            'period_end': period_end,
            'observed_this_week': summary['observed_this_week'],
            'kev_added_this_week': summary['kev_added_this_week'],
            'supply_chain_this_week': summary['supply_chain_this_week'],
        },
    )
    return snapshot


def cleanup_old_threat_intel_snapshots(retention_days: int = 90) -> int:
    cutoff_date = timezone.localdate() - timedelta(days=retention_days)
    deleted_count, _ = ThreatIntelSnapshot.objects.filter(snapshot_date__lt=cutoff_date).delete()
    return deleted_count


def get_dashboard_weekly_threat_intel(limit: int | None = 5) -> Dict:
    week_start, _ = get_current_week_period()
    latest_snapshot = ThreatIntelSnapshot.objects.filter(
        snapshot_date__gte=week_start,
    ).order_by('-snapshot_date', '-updated_at').first()

    if latest_snapshot:
        refreshed_summary = _refresh_summary_hitrack_presence({
            'period_start': latest_snapshot.period_start.isoformat(),
            'period_end': latest_snapshot.period_end.isoformat(),
            'generated_at': latest_snapshot.updated_at.isoformat(),
            'observed_this_week': latest_snapshot.observed_this_week,
            'kev_added_this_week': latest_snapshot.kev_added_this_week,
            'supply_chain_this_week': latest_snapshot.supply_chain_this_week,
        })
        return _limit_summary_entries(refreshed_summary, limit)

    return build_live_weekly_threat_intel_summary(limit=limit)


def _entry_matches_vulnerability(entry: Dict, vulnerability: Vulnerability) -> bool:
    vulnerability_uuid = str(vulnerability.uuid)
    vulnerability_id = _normalize_vulnerability_identifier(vulnerability.vulnerability_id)
    if not vulnerability_id:
        return False

    if entry.get('target_uuid') == vulnerability_uuid:
        return True

    candidate_identifiers = [
        entry.get('matched_vulnerability_id'),
        entry.get('vulnerability_id'),
        entry.get('matched_identifier'),
        entry.get('ghsa_id'),
        entry.get('cve_id'),
        entry.get('osv_id'),
        entry.get('advisory_id'),
        *(entry.get('aliases') or []),
    ]
    normalized_candidates = {
        normalized
        for normalized in (
            _normalize_vulnerability_identifier(identifier)
            for identifier in candidate_identifiers
        )
        if normalized
    }
    return vulnerability_id in normalized_candidates


def _build_vulnerability_threat_intel_match(summary: Dict, vulnerability: Vulnerability) -> Dict:
    entry_groups = [
        ('observed', 'Observed In HITrack', (summary.get('observed_this_week') or {}).get('entries', [])),
        ('kev', 'New KEV This Week', (summary.get('kev_added_this_week') or {}).get('entries', [])),
        ('supply_chain', 'Supply-Chain Advisories', (summary.get('supply_chain_this_week') or {}).get('entries', [])),
    ]

    matched_entries = []
    for intel_type, label, entries in entry_groups:
        for entry in entries:
            if not _entry_matches_vulnerability(entry, vulnerability):
                continue
            matched_entries.append({
                'intel_type': intel_type,
                'label': label,
                'identifier': entry.get('advisory_id')
                or entry.get('osv_id')
                or entry.get('vulnerability_id')
                or entry.get('matched_identifier')
                or vulnerability.vulnerability_id,
                'title': entry.get('title') or entry.get('vulnerability_id') or vulnerability.vulnerability_id,
                'timestamp': entry.get('published_at') or entry.get('date_added') or entry.get('created_at'),
                'source_labels': entry.get('source_labels') or [],
                'tags': entry.get('tags') or [],
                'matched_by': entry.get('matched_by'),
                'matched_identifier': entry.get('matched_identifier'),
                'matched_vulnerability_id': entry.get('matched_vulnerability_id'),
                'currently_present': bool(entry.get('currently_present')),
                'relevant_in_hitrack': bool(entry.get('relevant_in_hitrack', True)),
                'hitrack_match': entry.get('hitrack_match') or {
                    'repository_count': 0,
                    'repositories': [],
                    'tag_count': 0,
                    'tags': [],
                    'image_count': 0,
                    'images': [],
                    'component_count': 0,
                    'components': [],
                },
            })

    matched_entries.sort(
        key=lambda item: _parse_match_timestamp(item.get('timestamp')),
        reverse=True,
    )

    return {
        'matched_this_week': bool(matched_entries),
        'period_start': summary.get('period_start'),
        'period_end': summary.get('period_end'),
        'has_external_matches': any(entry['intel_type'] != 'observed' for entry in matched_entries),
        'entries': matched_entries[:5],
    }


def get_vulnerability_weekly_threat_intel_match(vulnerability: Vulnerability) -> Dict:
    week_start, week_end = get_current_week_period()
    latest_snapshot = ThreatIntelSnapshot.objects.filter(
        snapshot_date__gte=week_start,
    ).order_by('-snapshot_date', '-updated_at').first()

    if latest_snapshot:
        return _build_vulnerability_threat_intel_match({
            'period_start': latest_snapshot.period_start.isoformat(),
            'period_end': latest_snapshot.period_end.isoformat(),
            'observed_this_week': latest_snapshot.observed_this_week,
            'kev_added_this_week': latest_snapshot.kev_added_this_week,
            'supply_chain_this_week': latest_snapshot.supply_chain_this_week,
        }, vulnerability)

    created_date = timezone.localtime(vulnerability.created_at).date() if vulnerability.created_at else None
    if created_date and week_start <= created_date <= week_end:
        return {
            'matched_this_week': True,
            'period_start': week_start.isoformat(),
            'period_end': week_end.isoformat(),
            'has_external_matches': False,
            'entries': [{
                'intel_type': 'observed',
                'label': 'Observed In HITrack',
                'identifier': vulnerability.vulnerability_id,
                'title': vulnerability.vulnerability_id,
                'timestamp': vulnerability.created_at.isoformat() if vulnerability.created_at else None,
                'source_labels': ['HITrack'],
                'tags': [vulnerability.vulnerability_type],
                'matched_by': 'Vulnerability ID',
                'matched_identifier': vulnerability.vulnerability_id,
                'matched_vulnerability_id': vulnerability.vulnerability_id,
                'currently_present': False,
                'relevant_in_hitrack': True,
                'hitrack_match': {
                    'repository_count': 0,
                    'repositories': [],
                    'tag_count': 0,
                    'tags': [],
                    'image_count': 0,
                    'images': [],
                    'component_count': 0,
                    'components': [],
                },
            }],
        }

    return {
        'matched_this_week': False,
        'period_start': week_start.isoformat(),
        'period_end': week_end.isoformat(),
        'has_external_matches': False,
        'entries': [],
    }
