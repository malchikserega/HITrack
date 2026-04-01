from datetime import date, datetime, timedelta
from typing import Dict
from collections import defaultdict

from django.db.models import Exists, OuterRef
from django.utils import timezone

from core.models import ComponentVersionVulnerability, Image, RepositoryTag, ThreatIntelSnapshot, Vulnerability
from core.utils.vulnerability_sources import VulnerabilityDataCollector


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
        return limited

    return {
        'period_start': summary.get('period_start'),
        'period_end': summary.get('period_end'),
        'observed_this_week': limited_bucket(summary.get('observed_this_week')),
        'kev_added_this_week': limited_bucket(summary.get('kev_added_this_week')),
        'supply_chain_this_week': limited_bucket(summary.get('supply_chain_this_week')),
    }


def _normalize_vulnerability_identifier(identifier: str | None) -> str | None:
    if not identifier:
        return None
    normalized = str(identifier).strip().upper()
    return normalized or None


def _build_hitrack_location_preview(vulnerability_queryset) -> Dict[int, Dict]:
    vulnerability_ids = [vulnerability.pk for vulnerability in vulnerability_queryset]
    if not vulnerability_ids:
        return {}

    repositories_map = defaultdict(set)
    tags_map = defaultdict(set)
    images_map = defaultdict(set)

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

    preview_map = {}
    for vulnerability in vulnerability_queryset:
        repository_names = sorted(repositories_map.get(vulnerability.pk, set()))
        tag_names = sorted(tags_map.get(vulnerability.pk, set()))
        image_names = sorted(images_map.get(vulnerability.pk, set()))
        preview_map[vulnerability.pk] = {
            'repository_count': len(repository_names),
            'repositories': repository_names[:3],
            'tag_count': len(tag_names),
            'tags': tag_names[:3],
            'image_count': len(image_names),
            'images': image_names[:3],
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

    queryset = Vulnerability.objects.filter(
        vulnerability_id__in=normalized_identifiers,
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
                },
            ).get('hitrack_match'),
        }
        for vulnerability in observed_queryset
    ]

    collector = VulnerabilityDataCollector()

    try:
        kev_summary = collector.get_weekly_cisa_kev_entries(week_start, week_end, limit=None)
    except Exception:
        kev_summary = {'count': 0, 'entries': []}

    try:
        supply_chain_summary = collector.get_weekly_supply_chain_advisories(
            week_start,
            week_end,
            limit=None,
        )
    except Exception:
        supply_chain_summary = {'count': 0, 'entries': []}

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

    summary = {
        'period_start': week_start.isoformat(),
        'period_end': week_end.isoformat(),
        'observed_this_week': {
            'count': observed_queryset.count(),
            'relevant_in_hitrack_count': observed_queryset.count(),
            'currently_present_count': observed_queryset.filter(currently_present=True).count(),
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
        return _limit_summary_entries({
            'period_start': latest_snapshot.period_start.isoformat(),
            'period_end': latest_snapshot.period_end.isoformat(),
            'observed_this_week': latest_snapshot.observed_this_week,
            'kev_added_this_week': latest_snapshot.kev_added_this_week,
            'supply_chain_this_week': latest_snapshot.supply_chain_this_week,
        }, limit)

    return build_live_weekly_threat_intel_summary(limit=limit)
