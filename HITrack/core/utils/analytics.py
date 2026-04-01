from __future__ import annotations

from django.db import models
from django.db.models import Case, Count, IntegerField, Max, Q, Value, When
from django.utils import timezone


SEVERITY_RANKS = {
    'UNKNOWN': 0,
    'LOW': 1,
    'MEDIUM': 2,
    'HIGH': 3,
    'CRITICAL': 4,
}

SEVERITY_WEIGHTS = {
    'UNKNOWN': 2.0,
    'LOW': 5.0,
    'MEDIUM': 12.0,
    'HIGH': 25.0,
    'CRITICAL': 40.0,
}

FIXABILITY_PRIORITY = {
    'unknown': 0,
    'version_unknown': 0,
    'not_fixed': 1,
    'wont_fix': 1,
    'not_in_repo': 2,
    'available': 3,
}


def get_severity_rank(severity: str | None) -> int:
    return SEVERITY_RANKS.get(str(severity or 'UNKNOWN').upper(), 0)


def get_severity_weight(severity: str | None) -> float:
    return SEVERITY_WEIGHTS.get(str(severity or 'UNKNOWN').upper(), 2.0)


def get_fixability_category_from_priority(priority: int) -> str:
    if priority >= 3:
        return 'fixable_now'
    if priority == 2:
        return 'fix_exists_but_not_in_repo'
    if priority == 1:
        return 'no_fix'
    return 'fix_unknown'


def calculate_weighted_risk_score(
    severity: str | None,
    epss: float | int | None = None,
    cisa_kev: bool = False,
    exploit_available: bool = False,
    ransomware: bool = False,
    currently_present: bool = False,
    not_fixable: bool = False,
) -> float:
    score = get_severity_weight(severity)
    epss_value = float(epss or 0.0)
    if epss_value < 0:
        epss_value = 0.0
    if epss_value > 1:
        epss_value = 1.0

    score += epss_value * 20.0
    if cisa_kev:
        score += 20.0
    if exploit_available:
        score += 10.0
    if ransomware:
        score += 15.0
    if currently_present:
        score += 10.0
    if not_fixable:
        score += 8.0
    return round(score, 2)


def _fix_priority_case():
    return Case(
        When(fix_status='available', then=Value(3)),
        When(fix_status='not_in_repo', then=Value(2)),
        When(fix_status__in=['not_fixed', 'wont_fix'], then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )


def _build_state_from_cvv_queryset(cvv_queryset):
    grouped_rows = cvv_queryset.values(
        'vulnerability__uuid',
        'vulnerability__vulnerability_id',
        'vulnerability__severity',
        'vulnerability__epss',
        'vulnerability__details__cisa_kev_known_exploited',
        'vulnerability__details__exploit_available',
        'vulnerability__details__cisa_kev_ransomware_use',
    ).annotate(
        max_fix_priority=Max(_fix_priority_case()),
    )

    vulnerability_state = {}
    fixability_breakdown = {
        'fixable_now': 0,
        'fix_exists_but_not_in_repo': 0,
        'no_fix': 0,
        'fix_unknown': 0,
    }
    weighted_risk_score = 0.0

    for row in grouped_rows:
        vulnerability_id = row['vulnerability__vulnerability_id']
        severity = row['vulnerability__severity'] or 'UNKNOWN'
        cisa_kev = bool(row['vulnerability__details__cisa_kev_known_exploited'])
        exploit_available = bool(row['vulnerability__details__exploit_available'])
        ransomware = row['vulnerability__details__cisa_kev_ransomware_use'] == 'Known'
        priority = row['max_fix_priority'] or 0
        fixability_category = get_fixability_category_from_priority(priority)
        risk_score = calculate_weighted_risk_score(
            severity=severity,
            epss=row['vulnerability__epss'],
            cisa_kev=cisa_kev,
            exploit_available=exploit_available,
            ransomware=ransomware,
            currently_present=True,
            not_fixable=fixability_category != 'fixable_now',
        )

        vulnerability_state[vulnerability_id] = {
            'uuid': str(row['vulnerability__uuid']),
            'severity': severity,
            'kev': cisa_kev,
            'risk_score': risk_score,
            'fixability_category': fixability_category,
        }
        fixability_breakdown[fixability_category] += 1
        weighted_risk_score += risk_score

    return {
        'vulnerability_state': vulnerability_state,
        'fixability_breakdown': fixability_breakdown,
        'unique_vulnerabilities_count': len(vulnerability_state),
        'weighted_risk_score': round(weighted_risk_score, 2),
    }


def compare_vulnerability_states(previous_state: dict | None, current_state: dict | None) -> dict:
    previous_state = previous_state or {}
    current_state = current_state or {}

    previous_ids = set(previous_state.keys())
    current_ids = set(current_state.keys())

    new_ids = sorted(current_ids - previous_ids)
    fixed_ids = sorted(previous_ids - current_ids)

    severity_increased_ids = []
    new_kev_relevant_ids = []
    for vulnerability_id in sorted(current_ids & previous_ids):
        previous_entry = previous_state.get(vulnerability_id) or {}
        current_entry = current_state.get(vulnerability_id) or {}
        if get_severity_rank(current_entry.get('severity')) > get_severity_rank(previous_entry.get('severity')):
            severity_increased_ids.append(vulnerability_id)
        if bool(current_entry.get('kev')) and not bool(previous_entry.get('kev')):
            new_kev_relevant_ids.append(vulnerability_id)

    has_changes = bool(new_ids or fixed_ids or severity_increased_ids or new_kev_relevant_ids)
    return {
        'previous_unique_vulnerabilities_count': len(previous_ids),
        'current_unique_vulnerabilities_count': len(current_ids),
        'new_vulnerabilities_count': len(new_ids),
        'fixed_vulnerabilities_count': len(fixed_ids),
        'severity_increased_count': len(severity_increased_ids),
        'new_kev_relevant_count': len(new_kev_relevant_ids),
        'has_changes': has_changes,
        'delta_summary': {
            'has_changes': has_changes,
            'new_vulnerabilities': new_ids[:10],
            'fixed_vulnerabilities': fixed_ids[:10],
            'severity_increased': severity_increased_ids[:10],
            'new_kev_relevant': new_kev_relevant_ids[:10],
        },
    }


def build_repository_tag_scan_summary(repository_tag):
    from ..models import ComponentVersionVulnerability

    current_cvv = ComponentVersionVulnerability.objects.filter(
        component_version__images__repository_tags=repository_tag,
        component_version__images__scan_status='success',
    )
    state = _build_state_from_cvv_queryset(current_cvv)
    total_images = repository_tag.images.count()
    successful_images = repository_tag.images.filter(scan_status='success').count()

    return {
        'processing_status': repository_tag.processing_status,
        'total_images': total_images,
        'successful_images': successful_images,
        **state,
    }


def build_repository_exposure_summary(repository):
    from ..models import ComponentVersionVulnerability, Image

    current_cvv = ComponentVersionVulnerability.objects.filter(
        component_version__images__repository_tags__repository=repository,
        component_version__images__scan_status='success',
    )
    state = _build_state_from_cvv_queryset(current_cvv)
    active_images_count = Image.objects.filter(
        repository_tags__repository=repository,
        scan_status='success',
    ).distinct().count()

    return {
        'active_images_count': active_images_count,
        'current_unique_vulnerabilities_count': state['unique_vulnerabilities_count'],
        'weighted_risk_score': state['weighted_risk_score'],
    }


def build_vulnerability_exposure_rollup(vulnerability):
    from ..models import Image, Release, Repository, RepositoryTag

    return {
        'affected_repositories_count': Repository.objects.filter(
            tags__images__component_versions__componentversionvulnerability__vulnerability=vulnerability,
        ).distinct().count(),
        'affected_tags_count': RepositoryTag.objects.filter(
            images__component_versions__componentversionvulnerability__vulnerability=vulnerability,
        ).distinct().count(),
        'affected_releases_count': Release.objects.filter(
            repository_tags__repository_tag__images__component_versions__componentversionvulnerability__vulnerability=vulnerability,
        ).distinct().count(),
        'affected_images_count': Image.objects.filter(
            component_versions__componentversionvulnerability__vulnerability=vulnerability,
        ).distinct().count(),
        'active_images_count': Image.objects.filter(
            component_versions__componentversionvulnerability__vulnerability=vulnerability,
            scan_status='success',
        ).distinct().count(),
    }


def build_vulnerability_detail_analytics(vulnerability):
    from ..models import ComponentVersionVulnerability

    exposure = build_vulnerability_exposure_rollup(vulnerability)
    try:
        details = vulnerability.details
    except Exception:
        details = None
    current_cvv = ComponentVersionVulnerability.objects.filter(
        vulnerability=vulnerability,
        component_version__images__scan_status='success',
    )
    grouped = current_cvv.aggregate(max_fix_priority=Max(_fix_priority_case()))
    max_fix_priority = grouped.get('max_fix_priority') or 0
    fixability_category = get_fixability_category_from_priority(max_fix_priority)
    weighted_risk_score = calculate_weighted_risk_score(
        severity=vulnerability.severity,
        epss=vulnerability.epss,
        cisa_kev=bool(getattr(details, 'cisa_kev_known_exploited', False)),
        exploit_available=bool(getattr(details, 'exploit_available', False)),
        ransomware=getattr(details, 'cisa_kev_ransomware_use', None) == 'Known',
        currently_present=exposure['active_images_count'] > 0,
        not_fixable=exposure['active_images_count'] > 0 and fixability_category != 'fixable_now',
    )
    return {
        **exposure,
        'currently_present': exposure['active_images_count'] > 0,
        'weighted_risk_score': weighted_risk_score,
        'fixability_category': fixability_category,
    }


def build_release_exposure_summary(release):
    from ..models import ComponentVersionVulnerability, Image, RepositoryTag

    current_cvv = ComponentVersionVulnerability.objects.filter(
        component_version__images__repository_tags__releases__release=release,
        component_version__images__scan_status='success',
    )
    state = _build_state_from_cvv_queryset(current_cvv)
    active_images_count = Image.objects.filter(
        repository_tags__releases__release=release,
        scan_status='success',
    ).distinct().count()
    active_tags_count = RepositoryTag.objects.filter(
        releases__release=release,
        images__scan_status='success',
    ).distinct().count()
    return {
        'active_images_count': active_images_count,
        'active_tags_count': active_tags_count,
        'current_unique_vulnerabilities_count': state['unique_vulnerabilities_count'],
        'weighted_risk_score': state['weighted_risk_score'],
        'fixability_breakdown': state['fixability_breakdown'],
        'vulnerability_state': state['vulnerability_state'],
    }


def build_release_delta_summary(release):
    from ..models import Release

    current_summary = build_release_exposure_summary(release)
    previous_release = Release.objects.filter(
        created_at__lt=release.created_at,
    ).order_by('-created_at').first()

    if not previous_release:
        return {
            'current': current_summary,
            'previous_release': None,
            'delta': {
                'previous_unique_vulnerabilities_count': 0,
                'current_unique_vulnerabilities_count': current_summary['current_unique_vulnerabilities_count'],
                'new_vulnerabilities_count': current_summary['current_unique_vulnerabilities_count'],
                'fixed_vulnerabilities_count': 0,
                'severity_increased_count': 0,
                'new_kev_relevant_count': 0,
                'risk_score_delta': current_summary['weighted_risk_score'],
                'has_changes': current_summary['current_unique_vulnerabilities_count'] > 0,
                'delta_summary': {
                    'has_changes': current_summary['current_unique_vulnerabilities_count'] > 0,
                    'new_vulnerabilities': sorted(current_summary['vulnerability_state'].keys())[:10],
                    'fixed_vulnerabilities': [],
                    'severity_increased': [],
                    'new_kev_relevant': [],
                },
            },
        }

    previous_summary = build_release_exposure_summary(previous_release)
    delta = compare_vulnerability_states(
        previous_summary['vulnerability_state'],
        current_summary['vulnerability_state'],
    )
    delta['risk_score_delta'] = round(
        current_summary['weighted_risk_score'] - previous_summary['weighted_risk_score'],
        2,
    )
    return {
        'current': current_summary,
        'previous_release': {
            'uuid': str(previous_release.uuid),
            'name': previous_release.name,
            'created_at': previous_release.created_at,
            'weighted_risk_score': previous_summary['weighted_risk_score'],
            'current_unique_vulnerabilities_count': previous_summary['current_unique_vulnerabilities_count'],
        },
        'delta': delta,
    }


def build_dashboard_fixability_analytics():
    from ..models import ComponentVersionVulnerability

    grouped_rows = ComponentVersionVulnerability.objects.filter(
        component_version__images__scan_status='success',
    ).values(
        'vulnerability__uuid',
        'vulnerability__severity',
        'vulnerability__created_at',
    ).annotate(
        max_fix_priority=Max(_fix_priority_case()),
    )

    breakdown = {
        'fixable_now': 0,
        'fix_exists_but_not_in_repo': 0,
        'no_fix': 0,
        'fix_unknown': 0,
    }
    age_bucket_counts = {
        '0-7 days': 0,
        '8-30 days': 0,
        '31-90 days': 0,
        '90+ days': 0,
    }
    now = timezone.now()

    for row in grouped_rows:
        category = get_fixability_category_from_priority(row['max_fix_priority'] or 0)
        breakdown[category] += 1

        if category != 'fixable_now' or row['vulnerability__severity'] not in {'CRITICAL', 'HIGH'}:
            continue

        created_at = row['vulnerability__created_at']
        age_days = max((now - created_at).days, 0)
        if age_days <= 7:
            age_bucket_counts['0-7 days'] += 1
        elif age_days <= 30:
            age_bucket_counts['8-30 days'] += 1
        elif age_days <= 90:
            age_bucket_counts['31-90 days'] += 1
        else:
            age_bucket_counts['90+ days'] += 1

    return {
        'breakdown': breakdown,
        'critical_high_fixable_age_buckets': [
            {'label': label, 'count': count}
            for label, count in age_bucket_counts.items()
        ],
    }


def _aggregate_asset_rows(rows, asset_type: str, name_builder):
    assets = {}
    for row in rows:
        asset_uuid = str(row['asset_uuid'])
        asset = assets.setdefault(
            asset_uuid,
            {
                'uuid': asset_uuid,
                'name': name_builder(row),
                'asset_type': asset_type,
                'weighted_risk_score': 0.0,
                'unique_vulnerabilities': 0,
                'critical_vulnerabilities': 0,
                'kev_vulnerabilities': 0,
            },
        )
        fixability_category = get_fixability_category_from_priority(row['max_fix_priority'] or 0)
        risk_score = calculate_weighted_risk_score(
            severity=row['vulnerability__severity'],
            epss=row['vulnerability__epss'],
            cisa_kev=bool(row['vulnerability__details__cisa_kev_known_exploited']),
            exploit_available=bool(row['vulnerability__details__exploit_available']),
            ransomware=row['vulnerability__details__cisa_kev_ransomware_use'] == 'Known',
            currently_present=True,
            not_fixable=fixability_category != 'fixable_now',
        )
        asset['weighted_risk_score'] += risk_score
        asset['unique_vulnerabilities'] += 1
        if row['vulnerability__severity'] == 'CRITICAL':
            asset['critical_vulnerabilities'] += 1
        if row['vulnerability__details__cisa_kev_known_exploited']:
            asset['kev_vulnerabilities'] += 1

    ranked_assets = list(assets.values())
    for asset in ranked_assets:
        asset['weighted_risk_score'] = round(asset['weighted_risk_score'], 2)
    ranked_assets.sort(
        key=lambda asset: (
            -asset['weighted_risk_score'],
            -asset['critical_vulnerabilities'],
            -asset['unique_vulnerabilities'],
            asset['name'],
        )
    )
    return ranked_assets


def build_dashboard_risk_rankings(limit: int = 5):
    from ..models import ComponentVersionVulnerability

    base_queryset = ComponentVersionVulnerability.objects.filter(
        component_version__images__scan_status='success',
    )

    vulnerability_rows = base_queryset.values(
        'vulnerability__uuid',
        'vulnerability__vulnerability_id',
        'vulnerability__severity',
        'vulnerability__epss',
        'vulnerability__details__cisa_kev_known_exploited',
        'vulnerability__details__exploit_available',
        'vulnerability__details__cisa_kev_ransomware_use',
    ).annotate(
        max_fix_priority=Max(_fix_priority_case()),
        active_images_count=Count('component_version__images', distinct=True),
    )

    vulnerability_rankings = []
    for row in vulnerability_rows:
        fixability_category = get_fixability_category_from_priority(row['max_fix_priority'] or 0)
        vulnerability_rankings.append({
            'uuid': str(row['vulnerability__uuid']),
            'name': row['vulnerability__vulnerability_id'],
            'asset_type': 'vulnerability',
            'weighted_risk_score': calculate_weighted_risk_score(
                severity=row['vulnerability__severity'],
                epss=row['vulnerability__epss'],
                cisa_kev=bool(row['vulnerability__details__cisa_kev_known_exploited']),
                exploit_available=bool(row['vulnerability__details__exploit_available']),
                ransomware=row['vulnerability__details__cisa_kev_ransomware_use'] == 'Known',
                currently_present=(row['active_images_count'] or 0) > 0,
                not_fixable=fixability_category != 'fixable_now',
            ),
            'severity': row['vulnerability__severity'],
            'currently_present': (row['active_images_count'] or 0) > 0,
        })
    vulnerability_rankings.sort(
        key=lambda item: (-item['weighted_risk_score'], -get_severity_rank(item['severity']), item['name'])
    )

    repository_rows = base_queryset.annotate(
        asset_uuid=models.F('component_version__images__repository_tags__repository__uuid'),
        repository_name=models.F('component_version__images__repository_tags__repository__name'),
        vulnerability_severity=models.F('vulnerability__severity'),
        vulnerability_epss=models.F('vulnerability__epss'),
        vulnerability_kev=models.F('vulnerability__details__cisa_kev_known_exploited'),
        vulnerability_exploit=models.F('vulnerability__details__exploit_available'),
        vulnerability_ransomware=models.F('vulnerability__details__cisa_kev_ransomware_use'),
    ).exclude(
        asset_uuid__isnull=True,
    ).values(
        'asset_uuid',
        'repository_name',
        'vulnerability__uuid',
        'vulnerability_severity',
        'vulnerability_epss',
        'vulnerability_kev',
        'vulnerability_exploit',
        'vulnerability_ransomware',
    ).annotate(
        max_fix_priority=Max(_fix_priority_case()),
    )

    tag_rows = base_queryset.annotate(
        asset_uuid=models.F('component_version__images__repository_tags__uuid'),
        repository_name=models.F('component_version__images__repository_tags__repository__name'),
        tag_name=models.F('component_version__images__repository_tags__tag'),
        vulnerability_severity=models.F('vulnerability__severity'),
        vulnerability_epss=models.F('vulnerability__epss'),
        vulnerability_kev=models.F('vulnerability__details__cisa_kev_known_exploited'),
        vulnerability_exploit=models.F('vulnerability__details__exploit_available'),
        vulnerability_ransomware=models.F('vulnerability__details__cisa_kev_ransomware_use'),
    ).exclude(
        asset_uuid__isnull=True,
    ).values(
        'asset_uuid',
        'repository_name',
        'tag_name',
        'vulnerability__uuid',
        'vulnerability_severity',
        'vulnerability_epss',
        'vulnerability_kev',
        'vulnerability_exploit',
        'vulnerability_ransomware',
    ).annotate(
        max_fix_priority=Max(_fix_priority_case()),
    )

    image_rows = base_queryset.annotate(
        asset_uuid=models.F('component_version__images__uuid'),
        image_name=models.F('component_version__images__name'),
        vulnerability_severity=models.F('vulnerability__severity'),
        vulnerability_epss=models.F('vulnerability__epss'),
        vulnerability_kev=models.F('vulnerability__details__cisa_kev_known_exploited'),
        vulnerability_exploit=models.F('vulnerability__details__exploit_available'),
        vulnerability_ransomware=models.F('vulnerability__details__cisa_kev_ransomware_use'),
    ).exclude(
        asset_uuid__isnull=True,
    ).values(
        'asset_uuid',
        'image_name',
        'vulnerability__uuid',
        'vulnerability_severity',
        'vulnerability_epss',
        'vulnerability_kev',
        'vulnerability_exploit',
        'vulnerability_ransomware',
    ).annotate(
        max_fix_priority=Max(_fix_priority_case()),
    )

    release_rows = base_queryset.annotate(
        asset_uuid=models.F('component_version__images__repository_tags__releases__release__uuid'),
        release_name=models.F('component_version__images__repository_tags__releases__release__name'),
        vulnerability_severity=models.F('vulnerability__severity'),
        vulnerability_epss=models.F('vulnerability__epss'),
        vulnerability_kev=models.F('vulnerability__details__cisa_kev_known_exploited'),
        vulnerability_exploit=models.F('vulnerability__details__exploit_available'),
        vulnerability_ransomware=models.F('vulnerability__details__cisa_kev_ransomware_use'),
    ).exclude(
        asset_uuid__isnull=True,
    ).values(
        'asset_uuid',
        'release_name',
        'vulnerability__uuid',
        'vulnerability_severity',
        'vulnerability_epss',
        'vulnerability_kev',
        'vulnerability_exploit',
        'vulnerability_ransomware',
    ).annotate(
        max_fix_priority=Max(_fix_priority_case()),
    )

    def normalize_asset_rows(raw_rows):
        normalized = []
        for row in raw_rows:
            normalized.append({
                'asset_uuid': row['asset_uuid'],
                'max_fix_priority': row['max_fix_priority'],
                'vulnerability__severity': row.get('vulnerability_severity'),
                'vulnerability__epss': row.get('vulnerability_epss'),
                'vulnerability__details__cisa_kev_known_exploited': row.get('vulnerability_kev'),
                'vulnerability__details__exploit_available': row.get('vulnerability_exploit'),
                'vulnerability__details__cisa_kev_ransomware_use': row.get('vulnerability_ransomware'),
                **row,
            })
        return normalized

    repositories = _aggregate_asset_rows(
        normalize_asset_rows(repository_rows),
        'repository',
        lambda row: row['repository_name'],
    )[:limit]
    tags = _aggregate_asset_rows(
        normalize_asset_rows(tag_rows),
        'repository_tag',
        lambda row: f"{row['repository_name']}:{row['tag_name']}",
    )[:limit]
    images = _aggregate_asset_rows(
        normalize_asset_rows(image_rows),
        'image',
        lambda row: row['image_name'],
    )[:limit]
    releases = _aggregate_asset_rows(
        normalize_asset_rows(release_rows),
        'release',
        lambda row: row['release_name'],
    )[:limit]

    return {
        'vulnerabilities': vulnerability_rankings[:limit],
        'repositories': repositories,
        'tags': tags,
        'images': images,
        'releases': releases,
    }


def build_recent_scan_deltas(limit: int = 10):
    from ..models import RepositoryTagScanSnapshot

    snapshots = RepositoryTagScanSnapshot.objects.filter(
        has_changes=True,
    ).select_related(
        'repository_tag__repository',
    ).order_by('-created_at')[:limit]

    results = []
    for snapshot in snapshots:
        results.append({
            'uuid': str(snapshot.uuid),
            'repository_name': snapshot.repository_tag.repository.name,
            'repository_uuid': str(snapshot.repository_tag.repository.uuid),
            'tag': snapshot.repository_tag.tag,
            'tag_uuid': str(snapshot.repository_tag.uuid),
            'timestamp': snapshot.created_at.isoformat(),
            'new_vulnerabilities_count': snapshot.new_vulnerabilities_count,
            'fixed_vulnerabilities_count': snapshot.fixed_vulnerabilities_count,
            'severity_increased_count': snapshot.severity_increased_count,
            'new_kev_relevant_count': snapshot.new_kev_relevant_count,
            'weighted_risk_score': snapshot.weighted_risk_score,
            'risk_score_delta': snapshot.risk_score_delta,
            'delta_summary': snapshot.delta_summary or {},
        })
    return results
