from collections import defaultdict
from datetime import timedelta

from django.db.models import BooleanField, Case, Count, Max, OuterRef, Q, Subquery, Value, When
from django.utils import timezone
from packaging.version import InvalidVersion, Version

from core.models import (
    ComponentVersionVulnerability,
    Image,
    RiskAcceptance,
    ScanRun,
)


ECOSYSTEM_QUERY_ALIASES = {
    'dotnet': ({'dotnet', 'nuget'}, 'nuget'),
    'python': ({'python', 'pip', 'pypi', 'python-wheel', 'python-egg'}, 'pypi'),
    'npm': ({'npm', 'javascript', 'yarn', 'pnpm'}, 'npm'),
    'java': ({'java', 'java-archive', 'maven', 'gradle', 'jenkins-plugin'}, 'maven'),
    'go': ({'go', 'go-module', 'golang'}, 'golang'),
    'ruby': ({'ruby', 'gem'}, 'gem'),
    'rust': ({'rust', 'cargo', 'rust-crate'}, 'cargo'),
    'php': ({'php-composer', 'composer'}, 'composer'),
    'os': ({'deb', 'rpm', 'apk', 'alpm'}, None),
}


def _ecosystem_query(value):
    normalized = str(value or 'all').strip().lower()
    aliases = ECOSYSTEM_QUERY_ALIASES.get(normalized)
    if not aliases:
        return Q(component_version__component__type__iexact=normalized)
    component_types, purl_type = aliases
    query = Q(component_version__component__type__in=component_types)
    if purl_type:
        query |= Q(component_version__purl__istartswith=f'pkg:{purl_type}/')
    return query


def _active_suppressed_ids():
    return RiskAcceptance.objects.filter(
        status='active',
        expires_at__gt=timezone.now(),
    ).values('vulnerability_id')


def _pick_recommended_version(versions):
    normalized = sorted({str(value).strip() for value in versions if str(value).strip()})
    if not normalized:
        return None
    try:
        return str(max((Version(value) for value in normalized)))
    except InvalidVersion:
        return normalized[-1]


def _component_risk_rows(*, fixable_only=False, include_suppressed=False, limit=50, search='', ecosystem='all'):
    queryset = ComponentVersionVulnerability.objects.filter(
        component_version__images__isnull=False,
    )
    if fixable_only:
        queryset = queryset.filter(fixable=True)
    if not include_suppressed:
        queryset = queryset.exclude(vulnerability_id__in=_active_suppressed_ids())
    if search:
        queryset = queryset.filter(
            Q(component_version__component__name__icontains=search)
            | Q(component_version__purl__icontains=search)
        )
    if ecosystem not in {'', 'all'}:
        queryset = queryset.filter(_ecosystem_query(ecosystem))

    grouped = queryset.values(
        'component_version_id',
        'component_version__component_id',
        'component_version__component__name',
        'component_version__component__type',
        'component_version__version',
        'component_version__latest_version',
        'component_version__purl',
    ).annotate(
        vulnerabilities_count=Count('vulnerability_id', distinct=True),
        critical_count=Count('vulnerability_id', filter=Q(vulnerability__severity='CRITICAL'), distinct=True),
        high_count=Count('vulnerability_id', filter=Q(vulnerability__severity='HIGH'), distinct=True),
        medium_count=Count('vulnerability_id', filter=Q(vulnerability__severity='MEDIUM'), distinct=True),
        fixable_count=Count('vulnerability_id', filter=Q(fixable=True), distinct=True),
        kev_count=Count(
            'vulnerability_id',
            filter=Q(vulnerability__details__cisa_kev_known_exploited=True),
            distinct=True,
        ),
        exploit_count=Count(
            'vulnerability_id',
            filter=Q(vulnerability__details__exploit_available=True),
            distinct=True,
        ),
        max_epss=Max('vulnerability__epss'),
        affected_images_count=Count('component_version__images', distinct=True),
        affected_tags_count=Count('component_version__images__repository_tags', distinct=True),
        affected_repositories_count=Count(
            'component_version__images__repository_tags__repository', distinct=True,
        ),
        affected_releases_count=Count(
            'component_version__images__repository_tags__releases__release', distinct=True,
        ),
    )

    candidates = list(grouped.order_by(
        '-critical_count', '-kev_count', '-high_count', '-affected_images_count'
    )[:max(limit * 4, 100)])
    for row in candidates:
        row['risk_score'] = round(
            row['critical_count'] * 40
            + row['high_count'] * 16
            + row['medium_count'] * 5
            + row['kev_count'] * 35
            + row['exploit_count'] * 20
            + min(row['affected_images_count'], 25) * 2
            + min(float(row['max_epss'] or 0) * 20, 20),
            1,
        )
        row['no_fix_count'] = max(row['vulnerabilities_count'] - row['fixable_count'], 0)
        row['component_version_uuid'] = str(row.pop('component_version_id'))
        row['component_uuid'] = str(row.pop('component_version__component_id'))
        row['component_name'] = row.pop('component_version__component__name')
        row['component_type'] = row.pop('component_version__component__type')
        row['current_version'] = row.pop('component_version__version')
        row['latest_version'] = row.pop('component_version__latest_version')
        row['purl'] = row.pop('component_version__purl')

    candidates.sort(key=lambda row: (-row['risk_score'], row['component_name']))
    selected = candidates[:limit]

    if fixable_only and selected:
        versions_by_component = defaultdict(set)
        selected_ids = [row['component_version_uuid'] for row in selected]
        for component_version_id, versions in ComponentVersionVulnerability.objects.filter(
            component_version_id__in=selected_ids,
            fixable=True,
        ).values_list('component_version_id', 'fix_versions'):
            versions_by_component[str(component_version_id)].update(versions or [])
        for row in selected:
            known_versions = sorted(versions_by_component[row['component_version_uuid']])
            row['known_fix_versions'] = known_versions[:10]
            row['recommended_version'] = (
                _pick_recommended_version(known_versions) or row['latest_version']
            )
    return selected


def build_remediation_opportunities(**kwargs):
    return _component_risk_rows(fixable_only=True, **kwargs)


def build_high_impact_packages(**kwargs):
    return _component_risk_rows(fixable_only=False, **kwargs)


def build_scan_freshness(*, stale_days=30, limit=20):
    stale_days = min(max(int(stale_days), 1), 365)
    now = timezone.now()
    stale_cutoff = now - timedelta(days=stale_days)
    recent_cutoff = now - timedelta(days=7)
    latest_success = ScanRun.objects.filter(
        image=OuterRef('pk'), status='success', finished_at__isnull=False,
    ).order_by('-finished_at', '-updated_at')

    images = list(Image.objects.annotate(
        last_successful_scan=Subquery(latest_success.values('finished_at')[:1]),
        has_sbom=Case(
            When(sbom_data__isnull=False, then=Value(True)),
            default=Value(False), output_field=BooleanField(),
        ),
        has_grype=Case(
            When(grype_data__isnull=False, then=Value(True)),
            default=Value(False), output_field=BooleanField(),
        ),
    ).values(
        'uuid', 'name', 'scan_status', 'has_sbom', 'has_grype',
        'last_successful_scan', 'updated_at',
    ))

    buckets = {'fresh': 0, 'aging': 0, 'stale': 0, 'never_scanned': 0}
    stale_images = []
    sbom_count = grype_count = fully_analyzed = 0
    for image in images:
        has_sbom = image['has_sbom']
        has_grype = image['has_grype']
        sbom_count += int(has_sbom)
        grype_count += int(has_grype)
        fully_analyzed += int(has_sbom and has_grype)
        scanned_at = image['last_successful_scan'] or (image['updated_at'] if has_grype else None)
        if not scanned_at:
            bucket = 'never_scanned'
        elif scanned_at < stale_cutoff:
            bucket = 'stale'
        elif scanned_at < recent_cutoff:
            bucket = 'aging'
        else:
            bucket = 'fresh'
        buckets[bucket] += 1
        if bucket in {'stale', 'never_scanned'}:
            stale_images.append({
                'uuid': str(image['uuid']),
                'name': image['name'],
                'scan_status': image['scan_status'],
                'freshness': bucket,
                'last_successful_scan': scanned_at,
                'has_sbom': has_sbom,
                'has_grype': has_grype,
            })

    stale_images.sort(key=lambda row: (row['last_successful_scan'] is not None, row['last_successful_scan'] or now))
    total = len(images)
    return {
        'total_images': total,
        'sbom_coverage_count': sbom_count,
        'grype_coverage_count': grype_count,
        'fully_analyzed_count': fully_analyzed,
        'fully_analyzed_percentage': round((fully_analyzed / total * 100) if total else 0, 1),
        'stale_after_days': stale_days,
        'freshness_buckets': buckets,
        'attention_images': stale_images[:limit],
    }


def build_prioritization_payload(*, limit=50, stale_days=30, search='', ecosystem='all', include_suppressed=False):
    active_suppressions = RiskAcceptance.objects.filter(
        status='active', expires_at__gt=timezone.now(),
    ).count()
    return {
        'generated_at': timezone.now(),
        'active_suppressions_count': active_suppressions,
        'remediation_opportunities': build_remediation_opportunities(
            limit=limit, search=search, ecosystem=ecosystem,
            include_suppressed=include_suppressed,
        ),
        'high_impact_packages': build_high_impact_packages(
            limit=limit, search=search, ecosystem=ecosystem,
            include_suppressed=include_suppressed,
        ),
        'scan_freshness': build_scan_freshness(stale_days=stale_days, limit=limit),
    }
