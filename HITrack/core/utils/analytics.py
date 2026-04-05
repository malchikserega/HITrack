from __future__ import annotations

from collections import defaultdict
from django.db import models, transaction
from django.db.models import (
    Case,
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    Func,
    IntegerField,
    Max,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Cast, Coalesce, Concat, Lower
from django.utils import timezone
from datetime import timedelta


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


def _fix_priority_case(field_name: str = 'fix_status'):
    return Case(
        When(**{field_name: 'available'}, then=Value(3)),
        When(**{field_name: 'not_in_repo'}, then=Value(2)),
        When(**{f'{field_name}__in': ['not_fixed', 'wont_fix']}, then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
    )


def _cvv_severity_weight_case():
    return Case(
        When(vulnerability__severity='CRITICAL', then=Value(40.0)),
        When(vulnerability__severity='HIGH', then=Value(25.0)),
        When(vulnerability__severity='MEDIUM', then=Value(12.0)),
        When(vulnerability__severity='LOW', then=Value(5.0)),
        default=Value(2.0),
        output_field=FloatField(),
    )


def _cvv_weighted_risk_expression():
    return ExpressionWrapper(
        _cvv_severity_weight_case()
        + (Coalesce(F('vulnerability__epss'), Value(0.0), output_field=FloatField()) * Value(20.0))
        + Case(
            When(vulnerability__details__cisa_kev_known_exploited=True, then=Value(20.0)),
            default=Value(0.0),
            output_field=FloatField(),
        )
        + Case(
            When(vulnerability__details__exploit_available=True, then=Value(10.0)),
            default=Value(0.0),
            output_field=FloatField(),
        )
        + Case(
            When(vulnerability__details__cisa_kev_ransomware_use='Known', then=Value(15.0)),
            default=Value(0.0),
            output_field=FloatField(),
        )
        + Value(10.0)
        + Case(
            When(fix_status='available', then=Value(0.0)),
            default=Value(8.0),
            output_field=FloatField(),
        ),
        output_field=FloatField(),
    )


def build_shared_root_cause_queryset(base_queryset=None):
    from ..models import ComponentVersion, ComponentVersionVulnerability

    if base_queryset is None:
        base_queryset = ComponentVersion.objects.all()

    active_linked_image_filter = Q(
        images__scan_status='success',
        images__repository_tags__isnull=False,
    )
    risk_subquery = ComponentVersionVulnerability.objects.filter(
        component_version=OuterRef('pk'),
    ).annotate(
        risk_value=_cvv_weighted_risk_expression(),
    ).values(
        'component_version',
    ).annotate(
        total_risk=Sum('risk_value'),
    ).values('total_risk')[:1]

    return base_queryset.filter(
        componentversionvulnerability__isnull=False,
        images__scan_status='success',
        images__repository_tags__isnull=False,
    ).select_related(
        'component',
    ).annotate(
        affected_images_count=Count('images', filter=active_linked_image_filter, distinct=True),
        affected_repositories_count=Count('images__repository_tags__repository', filter=active_linked_image_filter, distinct=True),
        affected_tags_count=Count('images__repository_tags', filter=active_linked_image_filter, distinct=True),
        affected_releases_count=Count('images__repository_tags__releases__release', filter=active_linked_image_filter, distinct=True),
        vulnerabilities_count=Count('componentversionvulnerability', distinct=True),
        critical_vulnerabilities_count=Count(
            'componentversionvulnerability',
            filter=Q(componentversionvulnerability__vulnerability__severity='CRITICAL'),
            distinct=True,
        ),
        high_vulnerabilities_count=Count(
            'componentversionvulnerability',
            filter=Q(componentversionvulnerability__vulnerability__severity='HIGH'),
            distinct=True,
        ),
        kev_vulnerabilities_count=Count(
            'componentversionvulnerability',
            filter=Q(componentversionvulnerability__vulnerability__details__cisa_kev_known_exploited=True),
            distinct=True,
        ),
        exploit_vulnerabilities_count=Count(
            'componentversionvulnerability',
            filter=Q(componentversionvulnerability__vulnerability__details__exploit_available=True),
            distinct=True,
        ),
        max_fix_priority=Max(_fix_priority_case('componentversionvulnerability__fix_status')),
        fixable_now_count=Count(
            'componentversionvulnerability',
            filter=Q(componentversionvulnerability__fix_status='available'),
            distinct=True,
        ),
        fix_exists_but_not_in_repo_count=Count(
            'componentversionvulnerability',
            filter=Q(componentversionvulnerability__fix_status='not_in_repo'),
            distinct=True,
        ),
        no_fix_count=Count(
            'componentversionvulnerability',
            filter=Q(componentversionvulnerability__fix_status__in=['not_fixed', 'wont_fix']),
            distinct=True,
        ),
        fix_unknown_count=Count(
            'componentversionvulnerability',
            filter=Q(componentversionvulnerability__fix_status__in=['unknown', 'version_unknown'])
            | Q(componentversionvulnerability__fix_status__isnull=True),
            distinct=True,
        ),
        weighted_risk_score=Coalesce(
            Subquery(risk_subquery, output_field=FloatField()),
            Value(0.0),
            output_field=FloatField(),
        ),
        latest_seen_at=Max('images__updated_at', filter=active_linked_image_filter),
    ).filter(
        affected_images_count__gt=0,
    )


def build_base_lineage_image_queryset(base_queryset=None, include_risk_score: bool = True):
    from ..models import ComponentVersion, ComponentVersionVulnerability, Image

    if base_queryset is None:
        base_queryset = Image.objects.all()

    os_distro_hint_subquery = ComponentVersion.objects.filter(
        images=OuterRef('pk'),
        component__type__in=['deb', 'rpm', 'apk'],
        purl__icontains='distro=',
    ).annotate(
        distro_hint=Lower(
            Func(
                F('purl'),
                Value(r'.*[?&]distro=([^&]+).*'),
                Value(r'\1'),
                function='regexp_replace',
                output_field=models.CharField(),
            )
        ),
    ).exclude(
        distro_hint='',
    ).values('distro_hint')[:1]

    image_risk_subquery = ComponentVersionVulnerability.objects.filter(
        component_version__images=OuterRef('pk'),
    ).annotate(
        risk_value=_cvv_weighted_risk_expression(),
    ).values(
        'component_version__images',
    ).annotate(
        total_risk=Sum('risk_value'),
    ).values('total_risk')[:1]

    annotations = {
        'sbom_distro_name': Lower(
            Func(
                F('sbom_data'),
                Value('distro'),
                Value('name'),
                function='jsonb_extract_path_text',
                output_field=models.CharField(),
            )
        ),
        'sbom_distro_version': Func(
            F('sbom_data'),
            Value('distro'),
            Value('version'),
            function='jsonb_extract_path_text',
            output_field=models.CharField(),
        ),
        'package_distro_hint': Subquery(os_distro_hint_subquery, output_field=models.CharField()),
    }
    if include_risk_score:
        annotations['image_risk_score'] = Coalesce(
            Subquery(image_risk_subquery, output_field=FloatField()),
            Value(0.0),
            output_field=FloatField(),
        )

    queryset = base_queryset.filter(
        scan_status='success',
        repository_tags__isnull=False,
    ).annotate(**annotations)

    has_sbom_distro = (
        Q(sbom_distro_name__isnull=False)
        & ~Q(sbom_distro_name='')
    )
    has_sbom_version = (
        Q(sbom_distro_version__isnull=False)
        & ~Q(sbom_distro_version='')
    )
    has_package_distro = (
        Q(package_distro_hint__isnull=False)
        & ~Q(package_distro_hint='')
    )

    return queryset.annotate(
        lineage_label=Case(
            When(
                has_sbom_distro & has_sbom_version,
                then=Concat(F('sbom_distro_name'), Value('-'), F('sbom_distro_version')),
            ),
            When(
                has_sbom_distro,
                then=F('sbom_distro_name'),
            ),
            When(
                has_package_distro,
                then=F('package_distro_hint'),
            ),
            default=Value('unknown'),
            output_field=models.CharField(),
        ),
        lineage_source=Case(
            When(has_sbom_distro, then=Value('sbom_distro')),
            When(has_package_distro, then=Value('package_distro')),
            default=Value('unknown'),
            output_field=models.CharField(),
        ),
    )


def build_base_lineage_snapshot_image_queryset(base_queryset=None):
    return build_base_lineage_image_queryset(
        base_queryset=base_queryset,
        include_risk_score=False,
    ).values(
        'uuid',
        'lineage_label',
        'lineage_source',
        'updated_at',
    )


def serialize_shared_root_cause_summary_rows(component_versions):
    rows = []
    for component_version in component_versions:
        priority = getattr(component_version, 'max_fix_priority', 0) or 0
        rows.append({
            'uuid': str(component_version.uuid),
            'component_uuid': str(component_version.component.uuid),
            'component_name': component_version.component.name,
            'version': component_version.version,
            'component_type': component_version.component.type,
            'purl': component_version.purl,
            'latest_version': component_version.latest_version,
            'affected_repositories_count': getattr(component_version, 'affected_repositories_count', 0) or 0,
            'affected_tags_count': getattr(component_version, 'affected_tags_count', 0) or 0,
            'affected_releases_count': getattr(component_version, 'affected_releases_count', 0) or 0,
            'affected_images_count': getattr(component_version, 'affected_images_count', 0) or 0,
            'vulnerabilities_count': getattr(component_version, 'vulnerabilities_count', 0) or 0,
            'critical_vulnerabilities_count': getattr(component_version, 'critical_vulnerabilities_count', 0) or 0,
            'high_vulnerabilities_count': getattr(component_version, 'high_vulnerabilities_count', 0) or 0,
            'kev_vulnerabilities_count': getattr(component_version, 'kev_vulnerabilities_count', 0) or 0,
            'exploit_vulnerabilities_count': getattr(component_version, 'exploit_vulnerabilities_count', 0) or 0,
            'weighted_risk_score': round(float(getattr(component_version, 'weighted_risk_score', 0.0) or 0.0), 2),
            'max_fix_priority': priority,
            'fixability_category': get_fixability_category_from_priority(priority),
            'fixability_breakdown': {
                'fixable_now': getattr(component_version, 'fixable_now_count', 0) or 0,
                'fix_exists_but_not_in_repo': getattr(component_version, 'fix_exists_but_not_in_repo_count', 0) or 0,
                'no_fix': getattr(component_version, 'no_fix_count', 0) or 0,
                'fix_unknown': getattr(component_version, 'fix_unknown_count', 0) or 0,
            },
            'latest_seen_at': getattr(component_version, 'latest_seen_at', None),
            'repositories_preview': [],
            'vulnerabilities_preview': [],
        })
    return rows


def build_base_lineage_grouped_queryset(lineage_members):
    risk_subquery = Subquery(
        lineage_members.filter(
            lineage_label=OuterRef('lineage_label'),
        ).values('lineage_label').annotate(
            total_risk=Sum('image_risk_score'),
        ).values('total_risk')[:1],
        output_field=models.FloatField(),
    )

    return lineage_members.values('lineage_label', 'lineage_source').annotate(
        affected_images_count=Count('uuid', distinct=True),
        affected_repositories_count=Count('repository_tags__repository', distinct=True),
        affected_tags_count=Count('repository_tags', distinct=True),
        affected_releases_count=Count('repository_tags__releases__release', distinct=True),
        vulnerabilities_count=Count('component_versions__componentversionvulnerability__vulnerability', distinct=True),
        critical_vulnerabilities_count=Count(
            'component_versions__componentversionvulnerability__vulnerability',
            filter=Q(component_versions__componentversionvulnerability__vulnerability__severity='CRITICAL'),
            distinct=True,
        ),
        high_vulnerabilities_count=Count(
            'component_versions__componentversionvulnerability__vulnerability',
            filter=Q(component_versions__componentversionvulnerability__vulnerability__severity='HIGH'),
            distinct=True,
        ),
        kev_vulnerabilities_count=Count(
            'component_versions__componentversionvulnerability__vulnerability',
            filter=Q(component_versions__componentversionvulnerability__vulnerability__details__cisa_kev_known_exploited=True),
            distinct=True,
        ),
        exploit_vulnerabilities_count=Count(
            'component_versions__componentversionvulnerability__vulnerability',
            filter=Q(component_versions__componentversionvulnerability__vulnerability__details__exploit_available=True),
            distinct=True,
        ),
        max_fix_priority=Max(Case(
            When(component_versions__componentversionvulnerability__fix_status='available', then=Value(3)),
            When(component_versions__componentversionvulnerability__fix_status='not_in_repo', then=Value(2)),
            When(component_versions__componentversionvulnerability__fix_status__in=['not_fixed', 'wont_fix'], then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )),
        fixable_now_count=Count(
            'component_versions__componentversionvulnerability',
            filter=Q(component_versions__componentversionvulnerability__fix_status='available'),
            distinct=True,
        ),
        fix_exists_but_not_in_repo_count=Count(
            'component_versions__componentversionvulnerability',
            filter=Q(component_versions__componentversionvulnerability__fix_status='not_in_repo'),
            distinct=True,
        ),
        no_fix_count=Count(
            'component_versions__componentversionvulnerability',
            filter=Q(component_versions__componentversionvulnerability__fix_status__in=['not_fixed', 'wont_fix']),
            distinct=True,
        ),
        fix_unknown_count=Count(
            'component_versions__componentversionvulnerability',
            filter=Q(component_versions__componentversionvulnerability__fix_status__in=['unknown', 'version_unknown'])
            | Q(component_versions__componentversionvulnerability__fix_status__isnull=True),
            distinct=True,
        ),
        weighted_risk_score=Coalesce(risk_subquery, Value(0.0), output_field=models.FloatField()),
        latest_seen_at=Max('updated_at'),
    ).filter(
        affected_images_count__gt=0,
    )


def serialize_base_lineage_root_cause_summary_rows(grouped_rows):
    rows = []
    for row in grouped_rows:
        priority = row.get('max_fix_priority', 0) or 0
        rows.append({
            'key': row['lineage_label'],
            'lineage_label': row['lineage_label'],
            'lineage_source': row.get('lineage_source') or 'unknown',
            'affected_repositories_count': row.get('affected_repositories_count', 0) or 0,
            'affected_tags_count': row.get('affected_tags_count', 0) or 0,
            'affected_releases_count': row.get('affected_releases_count', 0) or 0,
            'affected_images_count': row.get('affected_images_count', 0) or 0,
            'vulnerabilities_count': row.get('vulnerabilities_count', 0) or 0,
            'critical_vulnerabilities_count': row.get('critical_vulnerabilities_count', 0) or 0,
            'high_vulnerabilities_count': row.get('high_vulnerabilities_count', 0) or 0,
            'kev_vulnerabilities_count': row.get('kev_vulnerabilities_count', 0) or 0,
            'exploit_vulnerabilities_count': row.get('exploit_vulnerabilities_count', 0) or 0,
            'weighted_risk_score': round(float(row.get('weighted_risk_score', 0.0) or 0.0), 2),
            'max_fix_priority': priority,
            'fixability_category': get_fixability_category_from_priority(priority),
            'fixability_breakdown': {
                'fixable_now': row.get('fixable_now_count', 0) or 0,
                'fix_exists_but_not_in_repo': row.get('fix_exists_but_not_in_repo_count', 0) or 0,
                'no_fix': row.get('no_fix_count', 0) or 0,
                'fix_unknown': row.get('fix_unknown_count', 0) or 0,
            },
            'latest_seen_at': row.get('latest_seen_at'),
            'repositories_preview': [],
            'components_preview': [],
            'vulnerabilities_preview': [],
        })
    return rows


def get_latest_root_cause_analytics_snapshots():
    from ..models import (
        BaseLineageRootCauseAnalyticsSnapshot,
        SharedRootCauseAnalyticsSnapshot,
    )

    return {
        'shared': SharedRootCauseAnalyticsSnapshot.objects.order_by('-snapshot_date', '-updated_at').first(),
        'base_lineage': BaseLineageRootCauseAnalyticsSnapshot.objects.order_by('-snapshot_date', '-updated_at').first(),
    }


def _bulk_insert_shared_root_cause_rows(snapshot, serialized_rows, batch_size=500):
    from ..models import SharedRootCauseAnalyticsSnapshotRow

    SharedRootCauseAnalyticsSnapshotRow.objects.bulk_create([
        SharedRootCauseAnalyticsSnapshotRow(
            snapshot=snapshot,
            component_version_uuid=row['uuid'],
            component_uuid=row['component_uuid'],
            component_name=row['component_name'],
            version=row['version'],
            component_type=row['component_type'],
            purl=row.get('purl'),
            latest_version=row.get('latest_version'),
            affected_repositories_count=row['affected_repositories_count'],
            affected_tags_count=row['affected_tags_count'],
            affected_releases_count=row['affected_releases_count'],
            affected_images_count=row['affected_images_count'],
            vulnerabilities_count=row['vulnerabilities_count'],
            critical_vulnerabilities_count=row['critical_vulnerabilities_count'],
            high_vulnerabilities_count=row['high_vulnerabilities_count'],
            kev_vulnerabilities_count=row['kev_vulnerabilities_count'],
            exploit_vulnerabilities_count=row['exploit_vulnerabilities_count'],
            weighted_risk_score=row['weighted_risk_score'],
            max_fix_priority=row['max_fix_priority'],
            fixability_category=row['fixability_category'],
            fixable_now_count=row['fixability_breakdown']['fixable_now'],
            fix_exists_but_not_in_repo_count=row['fixability_breakdown']['fix_exists_but_not_in_repo'],
            no_fix_count=row['fixability_breakdown']['no_fix'],
            fix_unknown_count=row['fixability_breakdown']['fix_unknown'],
            latest_seen_at=row.get('latest_seen_at'),
            repositories_preview=row.get('repositories_preview', []),
            components_preview=row.get('components_preview', []),
            vulnerabilities_preview=row.get('vulnerabilities_preview', []),
        )
        for row in serialized_rows
    ], batch_size=batch_size)


def _bulk_insert_base_lineage_root_cause_rows(snapshot, serialized_rows, batch_size=500):
    from ..models import BaseLineageRootCauseAnalyticsSnapshotRow

    BaseLineageRootCauseAnalyticsSnapshotRow.objects.bulk_create([
        BaseLineageRootCauseAnalyticsSnapshotRow(
            snapshot=snapshot,
            key=row['key'],
            lineage_label=row['lineage_label'],
            lineage_source=row['lineage_source'],
            affected_repositories_count=row['affected_repositories_count'],
            affected_tags_count=row['affected_tags_count'],
            affected_releases_count=row['affected_releases_count'],
            affected_images_count=row['affected_images_count'],
            vulnerabilities_count=row['vulnerabilities_count'],
            critical_vulnerabilities_count=row['critical_vulnerabilities_count'],
            high_vulnerabilities_count=row['high_vulnerabilities_count'],
            kev_vulnerabilities_count=row['kev_vulnerabilities_count'],
            exploit_vulnerabilities_count=row['exploit_vulnerabilities_count'],
            weighted_risk_score=row['weighted_risk_score'],
            max_fix_priority=row['max_fix_priority'],
            fixability_category=row['fixability_category'],
            fixable_now_count=row['fixability_breakdown']['fixable_now'],
            fix_exists_but_not_in_repo_count=row['fixability_breakdown']['fix_exists_but_not_in_repo'],
            no_fix_count=row['fixability_breakdown']['no_fix'],
            fix_unknown_count=row['fixability_breakdown']['fix_unknown'],
            latest_seen_at=row.get('latest_seen_at'),
            repositories_preview=row.get('repositories_preview', []),
            components_preview=row.get('components_preview', []),
            vulnerabilities_preview=row.get('vulnerabilities_preview', []),
        )
        for row in serialized_rows
    ], batch_size=batch_size)


def _build_shared_root_cause_preview_maps_for_ids(component_version_uuids):
    from ..models import ComponentVersionVulnerability, Repository

    if not component_version_uuids:
        return {}, {}

    repository_rows = Repository.objects.filter(
        tags__images__component_versions__uuid__in=component_version_uuids,
        tags__images__scan_status='success',
    ).values(
        'tags__images__component_versions__uuid',
        'uuid',
        'name',
    ).annotate(
        affected_images_count=Count(
            'tags__images',
            filter=Q(tags__images__scan_status='success'),
            distinct=True,
        ),
        affected_tags_count=Count(
            'tags',
            filter=Q(tags__images__scan_status='success'),
            distinct=True,
        ),
    ).order_by(
        'tags__images__component_versions__uuid',
        '-affected_images_count',
        'name',
    )

    repositories_preview_map = defaultdict(list)
    for row in repository_rows:
        component_version_uuid = str(row['tags__images__component_versions__uuid'])
        preview_list = repositories_preview_map[component_version_uuid]
        if len(preview_list) >= 5:
            continue
        preview_list.append({
            'repository_uuid': str(row['uuid']),
            'repository_name': row['name'],
            'affected_images_count': row['affected_images_count'] or 0,
            'affected_tags_count': row['affected_tags_count'] or 0,
        })

    vulnerability_rows = ComponentVersionVulnerability.objects.filter(
        component_version__uuid__in=component_version_uuids,
    ).values(
        'component_version__uuid',
        'vulnerability__uuid',
        'vulnerability__vulnerability_id',
        'vulnerability__severity',
        'vulnerability__epss',
        'vulnerability__details__cisa_kev_known_exploited',
        'vulnerability__details__exploit_available',
        'fix_status',
    )

    severity_rank_map = {
        'CRITICAL': 4,
        'HIGH': 3,
        'MEDIUM': 2,
        'LOW': 1,
        'UNKNOWN': 0,
    }
    vulnerabilities_preview_map = defaultdict(list)
    grouped_vulnerability_rows = defaultdict(list)
    for row in vulnerability_rows:
        grouped_vulnerability_rows[str(row['component_version__uuid'])].append(row)

    for component_version_uuid, rows in grouped_vulnerability_rows.items():
        rows.sort(
            key=lambda row: (
                -severity_rank_map.get((row['vulnerability__severity'] or 'UNKNOWN').upper(), 0),
                -(row['vulnerability__epss'] or 0.0),
                row['vulnerability__vulnerability_id'] or '',
            )
        )
        vulnerabilities_preview_map[component_version_uuid] = [
            {
                'uuid': str(row['vulnerability__uuid']),
                'vulnerability_id': row['vulnerability__vulnerability_id'],
                'severity': row['vulnerability__severity'] or 'UNKNOWN',
                'epss': round(float(row['vulnerability__epss'] or 0.0), 3),
                'cisa_kev': bool(row['vulnerability__details__cisa_kev_known_exploited']),
                'exploit_available': bool(row['vulnerability__details__exploit_available']),
                'fix_status': row['fix_status'],
            }
            for row in rows[:5]
        ]

    return repositories_preview_map, vulnerabilities_preview_map


def _populate_shared_root_cause_snapshot_previews(snapshot, batch_size=500):
    from ..models import SharedRootCauseAnalyticsSnapshotRow

    rows = list(snapshot.rows.all())
    if not rows:
        return

    component_version_uuids = [str(row.component_version_uuid) for row in rows]
    repositories_preview_map, vulnerabilities_preview_map = _build_shared_root_cause_preview_maps_for_ids(
        component_version_uuids
    )

    for row in rows:
        component_version_uuid = str(row.component_version_uuid)
        row.repositories_preview = repositories_preview_map.get(component_version_uuid, [])
        row.vulnerabilities_preview = vulnerabilities_preview_map.get(component_version_uuid, [])

    SharedRootCauseAnalyticsSnapshotRow.objects.bulk_update(
        rows,
        ['repositories_preview', 'vulnerabilities_preview'],
        batch_size=batch_size,
    )


def _build_base_lineage_preview_maps_for_labels(lineage_labels):
    if not lineage_labels:
        return {}, {}, {}

    lineage_members = build_base_lineage_image_queryset(include_risk_score=False).filter(
        lineage_label__in=lineage_labels
    )

    repositories_preview_map = defaultdict(list)
    repository_rows = lineage_members.values(
        'lineage_label',
        'repository_tags__repository__uuid',
        'repository_tags__repository__name',
    ).annotate(
        affected_images_count=Count('uuid', distinct=True),
        affected_tags_count=Count('repository_tags', distinct=True),
    ).order_by('lineage_label', '-affected_images_count', 'repository_tags__repository__name')

    for row in repository_rows:
        lineage_label = row['lineage_label']
        preview_list = repositories_preview_map[lineage_label]
        if len(preview_list) >= 5:
            continue
        repository_uuid = row['repository_tags__repository__uuid']
        repository_name = row['repository_tags__repository__name']
        if not repository_uuid or not repository_name:
            continue
        preview_list.append({
            'repository_uuid': str(repository_uuid),
            'repository_name': repository_name,
            'affected_images_count': row['affected_images_count'] or 0,
            'affected_tags_count': row['affected_tags_count'] or 0,
        })

    components_preview_map = defaultdict(list)
    component_rows = lineage_members.values(
        'lineage_label',
        'component_versions__component__uuid',
        'component_versions__component__name',
        'component_versions__version',
        'component_versions__component__type',
    ).annotate(
        affected_images_count=Count('uuid', distinct=True),
        vulnerabilities_count=Count(
            'component_versions__componentversionvulnerability__vulnerability',
            distinct=True,
        ),
    ).order_by(
        'lineage_label',
        '-affected_images_count',
        '-vulnerabilities_count',
        'component_versions__component__name',
        'component_versions__version',
    )

    for row in component_rows:
        lineage_label = row['lineage_label']
        preview_list = components_preview_map[lineage_label]
        if len(preview_list) >= 5:
            continue
        component_uuid = row['component_versions__component__uuid']
        component_name = row['component_versions__component__name']
        component_version = row['component_versions__version']
        if not component_uuid or not component_name or not component_version:
            continue
        preview_list.append({
            'component_uuid': str(component_uuid),
            'component_name': component_name,
            'version': component_version,
            'component_type': row['component_versions__component__type'] or 'unknown',
            'affected_images_count': row['affected_images_count'] or 0,
            'vulnerabilities_count': row['vulnerabilities_count'] or 0,
        })

    severity_rank_map = {
        'CRITICAL': 4,
        'HIGH': 3,
        'MEDIUM': 2,
        'LOW': 1,
        'UNKNOWN': 0,
    }
    vulnerabilities_preview_map = defaultdict(list)
    vulnerability_rows = list(
        lineage_members.values(
            'lineage_label',
            'component_versions__componentversionvulnerability__vulnerability__uuid',
            'component_versions__componentversionvulnerability__vulnerability__vulnerability_id',
            'component_versions__componentversionvulnerability__vulnerability__severity',
            'component_versions__componentversionvulnerability__vulnerability__epss',
            'component_versions__componentversionvulnerability__vulnerability__details__cisa_kev_known_exploited',
            'component_versions__componentversionvulnerability__vulnerability__details__exploit_available',
            'component_versions__componentversionvulnerability__fix_status',
        ).annotate(
            affected_images_count=Count('uuid', distinct=True),
        )
    )
    vulnerability_rows.sort(
        key=lambda row: (
            row['lineage_label'] or '',
            -severity_rank_map.get(
                (row['component_versions__componentversionvulnerability__vulnerability__severity'] or 'UNKNOWN').upper(),
                0,
            ),
            -(row['component_versions__componentversionvulnerability__vulnerability__epss'] or 0.0),
            -(row['affected_images_count'] or 0),
            row['component_versions__componentversionvulnerability__vulnerability__vulnerability_id'] or '',
        )
    )

    for row in vulnerability_rows:
        lineage_label = row['lineage_label']
        preview_list = vulnerabilities_preview_map[lineage_label]
        if len(preview_list) >= 5:
            continue
        vulnerability_uuid = row['component_versions__componentversionvulnerability__vulnerability__uuid']
        vulnerability_id = row['component_versions__componentversionvulnerability__vulnerability__vulnerability_id']
        if not vulnerability_uuid or not vulnerability_id:
            continue
        preview_list.append({
            'uuid': str(vulnerability_uuid),
            'vulnerability_id': vulnerability_id,
            'severity': row['component_versions__componentversionvulnerability__vulnerability__severity'] or 'UNKNOWN',
            'epss': round(float(row['component_versions__componentversionvulnerability__vulnerability__epss'] or 0.0), 3),
            'cisa_kev': bool(row['component_versions__componentversionvulnerability__vulnerability__details__cisa_kev_known_exploited']),
            'exploit_available': bool(row['component_versions__componentversionvulnerability__vulnerability__details__exploit_available']),
            'fix_status': row['component_versions__componentversionvulnerability__fix_status'],
        })

    return repositories_preview_map, components_preview_map, vulnerabilities_preview_map


def _populate_base_lineage_snapshot_previews(snapshot, batch_size=500):
    from ..models import BaseLineageRootCauseAnalyticsSnapshotRow

    rows = list(snapshot.rows.all())
    if not rows:
        return

    lineage_labels = [row.lineage_label for row in rows]
    repositories_preview_map, components_preview_map, vulnerabilities_preview_map = (
        _build_base_lineage_preview_maps_for_labels(lineage_labels)
    )

    for row in rows:
        row.repositories_preview = repositories_preview_map.get(row.lineage_label, [])
        row.components_preview = components_preview_map.get(row.lineage_label, [])
        row.vulnerabilities_preview = vulnerabilities_preview_map.get(row.lineage_label, [])

    BaseLineageRootCauseAnalyticsSnapshotRow.objects.bulk_update(
        rows,
        ['repositories_preview', 'components_preview', 'vulnerabilities_preview'],
        batch_size=batch_size,
    )


def save_shared_root_cause_analytics_snapshot(snapshot_date=None, batch_size: int = 500):
    from ..models import (
        SharedRootCauseAnalyticsSnapshot,
    )

    snapshot_date = snapshot_date or timezone.localdate()
    queryset = build_shared_root_cause_queryset().select_related('component')

    with transaction.atomic():
        snapshot, _ = SharedRootCauseAnalyticsSnapshot.objects.update_or_create(
            snapshot_date=snapshot_date,
            defaults={'total_items': 0},
        )
        snapshot.rows.all().delete()

    buffered = []
    total_items = 0
    for component_version in queryset.iterator(chunk_size=batch_size):
        buffered.append(component_version)
        if len(buffered) >= batch_size:
            serialized_rows = serialize_shared_root_cause_summary_rows(buffered)
            _bulk_insert_shared_root_cause_rows(snapshot, serialized_rows, batch_size=batch_size)
            total_items += len(serialized_rows)
            buffered = []

    if buffered:
        serialized_rows = serialize_shared_root_cause_summary_rows(buffered)
        _bulk_insert_shared_root_cause_rows(snapshot, serialized_rows, batch_size=batch_size)
        total_items += len(serialized_rows)

    _populate_shared_root_cause_snapshot_previews(snapshot, batch_size=batch_size)
    snapshot.total_items = total_items
    snapshot.save(update_fields=['total_items', 'updated_at'])
    return snapshot


def save_base_lineage_root_cause_analytics_snapshot(snapshot_date=None, batch_size: int = 500):
    from ..models import (
        BaseLineageRootCauseAnalyticsSnapshot,
        ComponentVersionVulnerability,
        RepositoryTag,
        RepositoryTagRelease,
    )

    snapshot_date = snapshot_date or timezone.localdate()
    image_queryset = build_base_lineage_snapshot_image_queryset()

    with transaction.atomic():
        snapshot, _ = BaseLineageRootCauseAnalyticsSnapshot.objects.update_or_create(
            snapshot_date=snapshot_date,
            defaults={'total_items': 0},
        )
        snapshot.rows.all().delete()

    lineage_stats = {}

    def get_lineage_bucket(label, source):
        bucket = lineage_stats.get(label)
        if bucket is None:
            bucket = {
                'lineage_label': label,
                'lineage_source': source or 'unknown',
                'image_ids': set(),
                'repository_ids': set(),
                'tag_ids': set(),
                'release_ids': set(),
                'vulnerability_state': {},
                'cvv_fix_priorities': {},
                'repository_preview_state': {},
                'component_preview_state': {},
                'weighted_risk_score': 0.0,
                'latest_seen_at': None,
                'max_fix_priority': 0,
            }
            lineage_stats[label] = bucket
        elif bucket['lineage_source'] == 'unknown' and source and source != 'unknown':
            bucket['lineage_source'] = source
        return bucket

    buffered_images = []
    for image_row in image_queryset.iterator(chunk_size=batch_size):
        buffered_images.append(image_row)
        if len(buffered_images) < batch_size:
            continue

        _accumulate_base_lineage_snapshot_batch(
            buffered_images,
            lineage_stats,
            RepositoryTag,
            RepositoryTagRelease,
            ComponentVersionVulnerability,
            get_lineage_bucket,
        )
        buffered_images = []

    if buffered_images:
        _accumulate_base_lineage_snapshot_batch(
            buffered_images,
            lineage_stats,
            RepositoryTag,
            RepositoryTagRelease,
            ComponentVersionVulnerability,
            get_lineage_bucket,
        )

    serialized_rows = []
    for label, bucket in sorted(
        lineage_stats.items(),
        key=lambda item: (
            -round(float(item[1]['weighted_risk_score'] or 0.0), 2),
            item[0],
        ),
    ):
        vulnerability_state = bucket['vulnerability_state']
        fixability_breakdown = {
            'fixable_now': 0,
            'fix_exists_but_not_in_repo': 0,
            'no_fix': 0,
            'fix_unknown': 0,
        }
        for priority in bucket['cvv_fix_priorities'].values():
            fixability_breakdown[get_fixability_category_from_priority(priority)] += 1

        repositories_preview = sorted(
            bucket['repository_preview_state'].values(),
            key=lambda preview: (
                -len(preview['image_ids']),
                -len(preview['tag_ids']),
                preview['repository_name'],
            ),
        )[:5]
        components_preview = sorted(
            bucket['component_preview_state'].values(),
            key=lambda preview: (
                -len(preview['image_ids']),
                -len(preview['vulnerability_ids']),
                preview['component_name'],
                preview['version'] or '',
            ),
        )[:5]
        vulnerabilities_preview = sorted(
            bucket['vulnerability_state'].items(),
            key=lambda item: (
                -get_severity_rank(item[1]['severity']),
                -(item[1].get('epss') or 0.0),
                -len(item[1].get('image_ids') or ()),
                item[0],
            ),
        )[:5]

        serialized_rows.append({
            'key': label,
            'lineage_label': label,
            'lineage_source': bucket['lineage_source'],
            'affected_repositories_count': len(bucket['repository_ids']),
            'affected_tags_count': len(bucket['tag_ids']),
            'affected_releases_count': len(bucket['release_ids']),
            'affected_images_count': len(bucket['image_ids']),
            'vulnerabilities_count': len(vulnerability_state),
            'critical_vulnerabilities_count': sum(
                1 for state in vulnerability_state.values()
                if state['severity'] == 'CRITICAL'
            ),
            'high_vulnerabilities_count': sum(
                1 for state in vulnerability_state.values()
                if state['severity'] == 'HIGH'
            ),
            'kev_vulnerabilities_count': sum(
                1 for state in vulnerability_state.values()
                if state['kev']
            ),
            'exploit_vulnerabilities_count': sum(
                1 for state in vulnerability_state.values()
                if state['exploit']
            ),
            'weighted_risk_score': round(float(bucket['weighted_risk_score'] or 0.0), 2),
            'max_fix_priority': bucket['max_fix_priority'],
            'fixability_category': get_fixability_category_from_priority(bucket['max_fix_priority']),
            'fixability_breakdown': fixability_breakdown,
            'latest_seen_at': bucket['latest_seen_at'],
            'repositories_preview': [
                {
                    'repository_uuid': preview['repository_uuid'],
                    'repository_name': preview['repository_name'],
                    'affected_images_count': len(preview['image_ids']),
                    'affected_tags_count': len(preview['tag_ids']),
                }
                for preview in repositories_preview
            ],
            'components_preview': [
                {
                    'component_uuid': preview['component_uuid'],
                    'component_name': preview['component_name'],
                    'version': preview['version'],
                    'component_type': preview['component_type'],
                    'affected_images_count': len(preview['image_ids']),
                    'vulnerabilities_count': len(preview['vulnerability_ids']),
                }
                for preview in components_preview
            ],
            'vulnerabilities_preview': [
                {
                    'uuid': state['uuid'],
                    'vulnerability_id': vulnerability_id,
                    'severity': state['severity'],
                    'epss': round(float(state.get('epss') or 0.0), 3),
                    'cisa_kev': state['kev'],
                    'exploit_available': state['exploit'],
                    'fix_status': state.get('fix_status') or 'unknown',
                }
                for vulnerability_id, state in vulnerabilities_preview
            ],
        })

    total_items = len(serialized_rows)
    if serialized_rows:
        _bulk_insert_base_lineage_root_cause_rows(snapshot, serialized_rows, batch_size=batch_size)

    snapshot.total_items = total_items
    snapshot.save(update_fields=['total_items', 'updated_at'])
    return snapshot


def _accumulate_base_lineage_snapshot_batch(
    image_rows,
    lineage_stats,
    RepositoryTag,
    RepositoryTagRelease,
    ComponentVersionVulnerability,
    get_lineage_bucket,
):
    if not image_rows:
        return

    image_ids = [row['uuid'] for row in image_rows]
    image_lineage_map = {}
    tag_lineages = defaultdict(set)

    for image_row in image_rows:
        label = image_row['lineage_label'] or 'unknown'
        source = image_row.get('lineage_source') or 'unknown'
        bucket = get_lineage_bucket(label, source)
        bucket['image_ids'].add(image_row['uuid'])
        latest_seen_at = image_row.get('updated_at')
        if latest_seen_at and (
            bucket['latest_seen_at'] is None or latest_seen_at > bucket['latest_seen_at']
        ):
            bucket['latest_seen_at'] = latest_seen_at
        image_lineage_map[image_row['uuid']] = label

    tag_links = RepositoryTag.objects.filter(
        images__uuid__in=image_ids,
    ).values_list(
        'images__uuid',
        'uuid',
        'repository_id',
        'repository__uuid',
        'repository__name',
    ).distinct()

    for image_id, tag_id, repository_id, repository_uuid, repository_name in tag_links:
        label = image_lineage_map.get(image_id)
        if not label:
            continue
        bucket = lineage_stats[label]
        bucket['tag_ids'].add(tag_id)
        bucket['repository_ids'].add(repository_id)
        tag_lineages[tag_id].add(label)
        repository_state = bucket['repository_preview_state'].get(repository_id)
        if repository_state is None:
            repository_state = {
                'repository_uuid': str(repository_uuid) if repository_uuid else str(repository_id),
                'repository_name': repository_name or 'Unknown repository',
                'image_ids': set(),
                'tag_ids': set(),
            }
            bucket['repository_preview_state'][repository_id] = repository_state
        repository_state['image_ids'].add(image_id)
        repository_state['tag_ids'].add(tag_id)

    if tag_lineages:
        for tag_id, release_id in RepositoryTagRelease.objects.filter(
            repository_tag_id__in=tag_lineages.keys(),
        ).values_list('repository_tag_id', 'release_id'):
            for label in tag_lineages.get(tag_id, ()):
                lineage_stats[label]['release_ids'].add(release_id)

    cvv_rows = ComponentVersionVulnerability.objects.filter(
        component_version__images__uuid__in=image_ids,
    ).values_list(
        'component_version__images__uuid',
        'id',
        'component_version__uuid',
        'component_version__component__uuid',
        'component_version__component__name',
        'component_version__version',
        'component_version__component__type',
        'vulnerability__vulnerability_id',
        'vulnerability__uuid',
        'vulnerability__severity',
        'vulnerability__epss',
        'vulnerability__details__cisa_kev_known_exploited',
        'vulnerability__details__exploit_available',
        'vulnerability__details__cisa_kev_ransomware_use',
        'fix_status',
    )

    for (
        image_id,
        cvv_id,
        component_version_uuid,
        component_uuid,
        component_name,
        component_version,
        component_type,
        vulnerability_id,
        vulnerability_uuid,
        severity,
        epss,
        cisa_kev,
        exploit_available,
        ransomware_use,
        fix_status,
    ) in cvv_rows.iterator():
        label = image_lineage_map.get(image_id)
        if not label:
            continue

        bucket = lineage_stats[label]
        priority = FIXABILITY_PRIORITY.get(str(fix_status or 'unknown'), 0)
        bucket['max_fix_priority'] = max(bucket['max_fix_priority'], priority)
        previous_priority = bucket['cvv_fix_priorities'].get(cvv_id, -1)
        if priority > previous_priority:
            bucket['cvv_fix_priorities'][cvv_id] = priority

        component_state = bucket['component_preview_state'].get(component_version_uuid)
        if component_state is None:
            component_state = {
                'component_uuid': str(component_uuid),
                'component_name': component_name or 'Unknown component',
                'version': component_version,
                'component_type': component_type or 'unknown',
                'image_ids': set(),
                'vulnerability_ids': set(),
            }
            bucket['component_preview_state'][component_version_uuid] = component_state
        component_state['image_ids'].add(image_id)
        if vulnerability_id:
            component_state['vulnerability_ids'].add(vulnerability_id)

        state = bucket['vulnerability_state'].get(vulnerability_id)
        if state is None:
            bucket['vulnerability_state'][vulnerability_id] = {
                'uuid': str(vulnerability_uuid),
                'severity': severity or 'UNKNOWN',
                'epss': float(epss or 0.0),
                'kev': bool(cisa_kev),
                'exploit': bool(exploit_available),
                'fix_status': fix_status or 'unknown',
                'fix_priority': priority,
                'image_ids': {image_id},
            }
        else:
            if get_severity_rank(severity) > get_severity_rank(state['severity']):
                state['severity'] = severity
            state['epss'] = max(float(epss or 0.0), float(state.get('epss') or 0.0))
            state['kev'] = state['kev'] or bool(cisa_kev)
            state['exploit'] = state['exploit'] or bool(exploit_available)
            if priority > state.get('fix_priority', -1):
                state['fix_priority'] = priority
                state['fix_status'] = fix_status or 'unknown'
            state['image_ids'].add(image_id)

        bucket['weighted_risk_score'] += calculate_weighted_risk_score(
            severity=severity,
            epss=epss,
            cisa_kev=bool(cisa_kev),
            exploit_available=bool(exploit_available),
            ransomware=ransomware_use == 'Known',
            currently_present=True,
            not_fixable=priority < 3,
        )


def save_root_cause_analytics_snapshots(snapshot_date=None, batch_size: int = 500):
    snapshot_date = snapshot_date or timezone.localdate()
    return {
        'shared_snapshot': save_shared_root_cause_analytics_snapshot(snapshot_date=snapshot_date, batch_size=batch_size),
        'base_lineage_snapshot': save_base_lineage_root_cause_analytics_snapshot(snapshot_date=snapshot_date, batch_size=batch_size),
    }


def cleanup_old_root_cause_analytics_snapshots(retention_days: int = 30):
    from ..models import (
        BaseLineageRootCauseAnalyticsSnapshot,
        SharedRootCauseAnalyticsSnapshot,
    )

    cutoff_date = timezone.localdate() - timedelta(days=retention_days)
    shared_deleted, _ = SharedRootCauseAnalyticsSnapshot.objects.filter(snapshot_date__lt=cutoff_date).delete()
    lineage_deleted, _ = BaseLineageRootCauseAnalyticsSnapshot.objects.filter(snapshot_date__lt=cutoff_date).delete()
    return {
        'shared_deleted': shared_deleted,
        'base_lineage_deleted': lineage_deleted,
        'total_deleted': shared_deleted + lineage_deleted,
    }


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
