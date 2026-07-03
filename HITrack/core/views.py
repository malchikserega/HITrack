from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.generics import ListAPIView, GenericAPIView
from django_filters.rest_framework import DjangoFilterBackend
from .models import Repository, RepositoryTag, Image, Component, ComponentVersion, Vulnerability, ContainerRegistry, ComponentVersionVulnerability, Release, RepositoryTagRelease, VulnerabilityDetails, ComponentLocation, ImageComponentVersionContext
from .serializers import (
    RepositorySerializer, RepositoryDetailSerializer, RepositoryTagSerializer, ImageSerializer, ImageListSerializer,
    ComponentSerializer, ComponentVersionSerializer, VulnerabilitySerializer, VulnerabilityShortSerializer, ComponentListSerializer,
    ComponentDetailOptimizedSerializer, ComponentVersionOptimizedSerializer, ComponentVersionDetailOptimizedSerializer, ComponentVersionUltraOptimizedSerializer,
    RepositoryListSerializer, RepositoryTagListSerializer, ComponentVersionListSerializer,
    HasACRRegistryResponseSerializer, ListACRRegistriesResponseSerializer,
    StatsResponseSerializer, JobAddRepositoriesRequestSerializer,
    JobAddRepositoriesResponseSerializer, ImageDropdownSerializer,
    ReleaseSerializer, RepositoryTagReleaseSerializer, ReleaseAssignmentSerializer,
    VulnerabilityListSerializer, VulnerabilityDetailsSerializer, VulnerabilityDetailSerializer, VulnerabilityRiskPrioritizationSerializer, VulnerabilityBaseDetailSerializer,
    TaskResultSerializer, TaskResultListSerializer, PeriodicTaskSerializer, TaskStatisticsSerializer,
    ComponentLocationSerializer, VulnerabilityAffectedImageSerializer,
    ImageComparisonGroupSerializer, SharedRootCauseSerializer, SharedRootCausePreviewSerializer,
    BaseLineageRootCauseSerializer, BaseLineageRootCausePreviewSerializer,
    RootCauseRepositoryPreviewSerializer, RootCauseVulnerabilityPreviewSerializer,
    BaseLineageComponentPreviewSerializer,
)
from django.db import models
from .pagination import CustomPageNumberPagination
from django.db.models import Q, Count, Prefetch, Case, When, Value, BooleanField, IntegerField, F, CharField, TextField, Func, Max, OuterRef, Subquery, Sum
from django.db.models.query import prefetch_related_objects
from django.db.models.functions import Cast, Concat, TruncDate, Coalesce
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from datetime import timedelta, datetime
from io import BytesIO
from collections import defaultdict
from rest_framework.views import APIView
from django.http import HttpResponse
from openpyxl import Workbook
from django.shortcuts import get_object_or_404, render
import re
import logging
from django.conf import settings
from .utils.status import resolve_repository_tag_processing_status
from .utils.threat_intel import get_dashboard_weekly_threat_intel
from .utils.analytics import (
    build_dashboard_fixability_analytics,
    build_base_lineage_grouped_queryset,
    build_base_lineage_image_queryset,
    build_dashboard_risk_rankings,
    build_shared_root_cause_queryset,
    build_recent_scan_deltas,
    build_release_delta_summary,
    get_latest_root_cause_analytics_snapshots,
    serialize_base_lineage_root_cause_summary_rows,
    serialize_shared_root_cause_summary_rows,
    build_vulnerability_detail_analytics,
    get_fixability_category_from_priority,
)

logger = logging.getLogger(__name__)

# Create your views here.

REPOSITORY_TAG_LIST_ONLY_FIELDS = (
    'uuid',
    'tag',
    'image_path',
    'processing_status',
    'created_at',
    'updated_at',
    'repository_id',
)

REPOSITORY_TAG_ORDERING_MAP = {
    'created_at': 'created_at',
    '-created_at': '-created_at',
    'updated_at': 'updated_at',
    '-updated_at': '-updated_at',
    'tag': 'tag',
    '-tag': '-tag',
}

IMAGE_LIST_ORDERING_MAP = {
    'name': 'name',
    '-name': '-name',
    'lineage_label': 'lineage_label',
    '-lineage_label': '-lineage_label',
    'os_eol_status': 'os_eol_status',
    '-os_eol_status': '-os_eol_status',
    'digest': 'digest',
    '-digest': '-digest',
    'created_at': 'created_at',
    '-created_at': '-created_at',
    'updated_at': 'updated_at',
    '-updated_at': '-updated_at',
    'findings': 'findings_count',
    '-findings': '-findings_count',
    'findings_count': 'findings_count',
    '-findings_count': '-findings_count',
    'components_count': 'components_count',
    '-components_count': '-components_count',
    'unique_findings': 'unique_findings_count',
    '-unique_findings': '-unique_findings_count',
    'unique_findings_count': 'unique_findings_count',
    '-unique_findings_count': '-unique_findings_count',
}

IMAGE_LIST_METRIC_ORDERING_FIELDS = {
    'findings',
    'findings_count',
    'unique_findings',
    'unique_findings_count',
    'components_count',
}

IMAGE_COMPONENT_VERSION_ORDERING_MAP = {
    'version': 'version',
    '-version': '-version',
    'name': 'component__name',
    '-name': '-component__name',
    'type': 'component__type',
    '-type': '-component__type',
    'vulnerabilities_count': 'vulnerabilities_count',
    '-vulnerabilities_count': '-vulnerabilities_count',
    'used_count': 'images_count',
    '-used_count': '-images_count',
    'images_count': 'images_count',
    '-images_count': '-images_count',
    'created_at': 'created_at',
    '-created_at': '-created_at',
    'updated_at': 'updated_at',
    '-updated_at': '-updated_at',
}

IMAGE_COMPONENT_VERSION_METRIC_ORDERING_FIELDS = {
    'vulnerabilities_count',
    'used_count',
    'images_count',
}

VULNERABILITY_IMAGE_ORDERING_MAP = {
    'name': 'name',
    '-name': '-name',
    'scan_status': 'scan_status',
    '-scan_status': '-scan_status',
}

IMAGE_COMPARISON_ORDERING_MAP = {
    'logical_name': 'logical_name',
    '-logical_name': '-logical_name',
    'variant_count': 'variant_count',
    '-variant_count': '-variant_count',
    'registry_count': 'registry_count',
    '-registry_count': '-registry_count',
    'distinct_digests': 'distinct_digests',
    '-distinct_digests': '-distinct_digests',
    'max_findings': 'max_findings',
    '-max_findings': '-max_findings',
    'max_unique_findings': 'max_unique_findings',
    '-max_unique_findings': '-max_unique_findings',
    'max_components_count': 'max_components_count',
    '-max_components_count': '-max_components_count',
    'latest_updated_at': 'latest_updated_at',
    '-latest_updated_at': '-latest_updated_at',
}

ROOT_CAUSE_ORDERING_MAP = {
    'component_name': 'component__name',
    '-component_name': '-component__name',
    'version': 'version',
    '-version': '-version',
    'component_type': 'component__type',
    '-component_type': '-component__type',
    'affected_repositories_count': 'affected_repositories_count',
    '-affected_repositories_count': '-affected_repositories_count',
    'affected_images_count': 'affected_images_count',
    '-affected_images_count': '-affected_images_count',
    'vulnerabilities_count': 'vulnerabilities_count',
    '-vulnerabilities_count': '-vulnerabilities_count',
    'critical_vulnerabilities_count': 'critical_vulnerabilities_count',
    '-critical_vulnerabilities_count': '-critical_vulnerabilities_count',
    'kev_vulnerabilities_count': 'kev_vulnerabilities_count',
    '-kev_vulnerabilities_count': '-kev_vulnerabilities_count',
    'weighted_risk_score': 'weighted_risk_score',
    '-weighted_risk_score': '-weighted_risk_score',
    'latest_seen_at': 'latest_seen_at',
    '-latest_seen_at': '-latest_seen_at',
}

ROOT_CAUSE_SNAPSHOT_ORDERING_MAP = {
    'component_name': 'component_name',
    '-component_name': '-component_name',
    'version': 'version',
    '-version': '-version',
    'component_type': 'component_type',
    '-component_type': '-component_type',
    'affected_repositories_count': 'affected_repositories_count',
    '-affected_repositories_count': '-affected_repositories_count',
    'affected_images_count': 'affected_images_count',
    '-affected_images_count': '-affected_images_count',
    'vulnerabilities_count': 'vulnerabilities_count',
    '-vulnerabilities_count': '-vulnerabilities_count',
    'critical_vulnerabilities_count': 'critical_vulnerabilities_count',
    '-critical_vulnerabilities_count': '-critical_vulnerabilities_count',
    'kev_vulnerabilities_count': 'kev_vulnerabilities_count',
    '-kev_vulnerabilities_count': '-kev_vulnerabilities_count',
    'weighted_risk_score': 'weighted_risk_score',
    '-weighted_risk_score': '-weighted_risk_score',
    'latest_seen_at': 'latest_seen_at',
    '-latest_seen_at': '-latest_seen_at',
}

BASE_LINEAGE_ORDERING_MAP = {
    'lineage_label': 'lineage_label',
    '-lineage_label': '-lineage_label',
    'affected_repositories_count': 'affected_repositories_count',
    '-affected_repositories_count': '-affected_repositories_count',
    'affected_images_count': 'affected_images_count',
    '-affected_images_count': '-affected_images_count',
    'vulnerabilities_count': 'vulnerabilities_count',
    '-vulnerabilities_count': '-vulnerabilities_count',
    'critical_vulnerabilities_count': 'critical_vulnerabilities_count',
    '-critical_vulnerabilities_count': '-critical_vulnerabilities_count',
    'kev_vulnerabilities_count': 'kev_vulnerabilities_count',
    '-kev_vulnerabilities_count': '-kev_vulnerabilities_count',
    'weighted_risk_score': 'weighted_risk_score',
    '-weighted_risk_score': '-weighted_risk_score',
    'latest_seen_at': 'latest_seen_at',
    '-latest_seen_at': '-latest_seen_at',
}

BASE_LINEAGE_SNAPSHOT_ORDERING_MAP = {
    'lineage_label': 'lineage_label',
    '-lineage_label': '-lineage_label',
    'affected_repositories_count': 'affected_repositories_count',
    '-affected_repositories_count': '-affected_repositories_count',
    'affected_images_count': 'affected_images_count',
    '-affected_images_count': '-affected_images_count',
    'vulnerabilities_count': 'vulnerabilities_count',
    '-vulnerabilities_count': '-vulnerabilities_count',
    'critical_vulnerabilities_count': 'critical_vulnerabilities_count',
    '-critical_vulnerabilities_count': '-critical_vulnerabilities_count',
    'kev_vulnerabilities_count': 'kev_vulnerabilities_count',
    '-kev_vulnerabilities_count': '-kev_vulnerabilities_count',
    'weighted_risk_score': 'weighted_risk_score',
    '-weighted_risk_score': '-weighted_risk_score',
    'latest_seen_at': 'latest_seen_at',
    '-latest_seen_at': '-latest_seen_at',
}


def _normalize_recent_activity_types(raw_types):
    normalized = []
    for raw_type in raw_types:
        if raw_type is None:
            continue
        for item in str(raw_type).split(','):
            value = item.strip().lower()
            if value in {'scan', 'vulnerability'} and value not in normalized:
                normalized.append(value)
    return normalized


def _build_recent_activity_queryset(since_timestamp, activity_types=None):
    selected_types = _normalize_recent_activity_types(activity_types or ['scan', 'vulnerability'])

    recent_scans = Repository.objects.filter(
        updated_at__gte=since_timestamp
    ).annotate(
        activity_type=Value('scan', output_field=CharField()),
        title=Concat(
            Value('Repository "'),
            F('name'),
            Value('" scanned'),
            output_field=TextField(),
        ),
        timestamp=F('updated_at'),
        activity_severity=Value(None, output_field=CharField()),
        activity_status=F('scan_status'),
        target_type=Value('repository', output_field=CharField()),
        target_uuid=Cast('uuid', output_field=CharField()),
    ).values(
        'activity_type',
        'title',
        'timestamp',
        'activity_severity',
        'activity_status',
        'target_type',
        'target_uuid',
    )

    recent_vulnerabilities = Vulnerability.objects.filter(
        created_at__gte=since_timestamp
    ).annotate(
        activity_type=Value('vulnerability', output_field=CharField()),
        title=Concat(
            Value('New vulnerability: '),
            F('vulnerability_id'),
            output_field=TextField(),
        ),
        timestamp=F('created_at'),
        activity_severity=F('severity'),
        activity_status=Value(None, output_field=CharField()),
        target_type=Value('vulnerability', output_field=CharField()),
        target_uuid=Cast('uuid', output_field=CharField()),
    ).values(
        'activity_type',
        'title',
        'timestamp',
        'activity_severity',
        'activity_status',
        'target_type',
        'target_uuid',
    )

    querysets = []
    if 'scan' in selected_types:
        querysets.append(recent_scans)
    if 'vulnerability' in selected_types:
        querysets.append(recent_vulnerabilities)

    if not querysets:
        return recent_scans.none()
    if len(querysets) == 1:
        return querysets[0].order_by('-timestamp')
    return querysets[0].union(*querysets[1:]).order_by('-timestamp')


def _parse_threat_intel_timestamp(value):
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)

    try:
        if isinstance(value, str) and 'T' in value:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        return datetime.fromisoformat(f"{value}T00:00:00+00:00")
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _build_weekly_threat_intel_rows(summary, intel_type='all'):
    rows = []
    selected_type = (intel_type or 'all').strip().lower()

    if selected_type in {'all', 'observed'}:
        for entry in (summary.get('observed_this_week') or {}).get('entries', []):
            context_parts = [entry.get('type') or 'Observed in HITrack']
            if entry.get('cisa_kev'):
                context_parts.append('KEV')
            elif entry.get('exploit_available'):
                context_parts.append('Exploit available')
            if entry.get('epss'):
                context_parts.append(f"EPSS {entry['epss']}")

            rows.append({
                'id': f"observed:{entry.get('uuid') or entry.get('vulnerability_id')}",
                'type': 'observed',
                'identifier': entry.get('vulnerability_id'),
                'title': entry.get('vulnerability_id'),
                'context': " · ".join(part for part in context_parts if part),
                'timestamp': entry.get('created_at'),
                'severity': entry.get('severity'),
                'target_type': entry.get('target_type') or 'vulnerability',
                'target_uuid': entry.get('target_uuid') or entry.get('uuid'),
                'external_url': None,
                'relevant_in_hitrack': bool(entry.get('relevant_in_hitrack', True)),
                'currently_present': bool(entry.get('currently_present')),
                'source_labels': ['HITrack'],
                'tags': [
                    tag for tag in [
                        entry.get('type'),
                        'KEV' if entry.get('cisa_kev') else None,
                        'Exploit available' if entry.get('exploit_available') else None,
                    ] if tag
                ],
                'matched_identifier': entry.get('matched_identifier'),
                'matched_by': entry.get('matched_by'),
                'matched_vulnerability_id': entry.get('matched_vulnerability_id'),
                'hitrack_match': entry.get('hitrack_match'),
            })

    if selected_type in {'all', 'kev'}:
        for entry in (summary.get('kev_added_this_week') or {}).get('entries', []):
            context_parts = [part for part in [entry.get('vendor'), entry.get('product')] if part]
            if entry.get('ransomware_use') == 'Known':
                context_parts.append('Ransomware')

            rows.append({
                'id': f"kev:{entry.get('vulnerability_id')}",
                'type': 'kev',
                'identifier': entry.get('vulnerability_id'),
                'title': entry.get('title') or entry.get('vulnerability_id'),
                'context': " · ".join(context_parts) or 'CISA KEV',
                'timestamp': entry.get('date_added'),
                'severity': 'KEV',
                'target_type': entry.get('target_type'),
                'target_uuid': entry.get('target_uuid'),
                'external_url': entry.get('url'),
                'relevant_in_hitrack': bool(entry.get('relevant_in_hitrack')),
                'currently_present': bool(entry.get('currently_present')),
                'source_labels': ['CISA KEV'],
                'tags': [
                    tag for tag in [
                        'CISA KEV',
                        'Ransomware' if entry.get('ransomware_use') == 'Known' else None,
                    ] if tag
                ],
                'matched_identifier': entry.get('matched_identifier'),
                'matched_by': entry.get('matched_by'),
                'matched_vulnerability_id': entry.get('matched_vulnerability_id'),
                'hitrack_match': entry.get('hitrack_match'),
            })

    if selected_type in {'all', 'supply_chain'}:
        for entry in (summary.get('supply_chain_this_week') or {}).get('entries', []):
            packages = entry.get('packages') or []
            context_parts = [str(entry.get('ecosystem') or '').upper()]
            if packages:
                context_parts.append(", ".join(packages[:3]))
            elif entry.get('title'):
                context_parts.append(entry.get('title'))

            rows.append({
                'id': f"supply_chain:{entry.get('advisory_id') or entry.get('url')}",
                'type': 'supply_chain',
                'identifier': entry.get('advisory_id') or entry.get('osv_id') or 'Advisory',
                'title': entry.get('title') or entry.get('advisory_id') or entry.get('osv_id') or 'Supply-chain advisory',
                'context': " · ".join(part for part in context_parts if part) or ", ".join(entry.get('source_labels') or []) or 'Supply-chain advisory',
                'timestamp': entry.get('published_at'),
                'severity': entry.get('severity') or ('MALWARE' if entry.get('type') == 'malware' else None),
                'target_type': entry.get('target_type'),
                'target_uuid': entry.get('target_uuid'),
                'external_url': entry.get('url'),
                'relevant_in_hitrack': bool(entry.get('relevant_in_hitrack')),
                'currently_present': bool(entry.get('currently_present')),
                'source_labels': entry.get('source_labels') or [],
                'tags': entry.get('tags') or [],
                'matched_identifier': entry.get('matched_identifier'),
                'matched_by': entry.get('matched_by'),
                'matched_vulnerability_id': entry.get('matched_vulnerability_id'),
                'hitrack_match': entry.get('hitrack_match'),
            })

    rows.sort(key=lambda item: _parse_threat_intel_timestamp(item.get('timestamp')), reverse=True)
    return rows


def _build_vulnerability_trend_series(days=30):
    current_timezone = timezone.get_current_timezone()
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=days - 1)
    start_datetime = timezone.make_aware(
        datetime.combine(start_date, datetime.min.time()),
        current_timezone,
    )
    end_datetime = timezone.make_aware(
        datetime.combine(end_date + timedelta(days=1), datetime.min.time()),
        current_timezone,
    )

    vulnerability_counts = {
        item['trend_date']: item['count']
        for item in Vulnerability.objects.filter(
            created_at__gte=start_datetime,
            created_at__lt=end_datetime,
        ).annotate(
            trend_date=TruncDate('created_at', tzinfo=current_timezone)
        ).values('trend_date').annotate(
            count=Count('uuid')
        ).order_by('trend_date')
    }

    return [
        {
            'created_at__date': (start_date + timedelta(days=offset)).isoformat(),
            'count': vulnerability_counts.get(start_date + timedelta(days=offset), 0),
        }
        for offset in range(days)
    ]


def _build_dashboard_overview_payload():
    from django.db.models import Count, Q

    total_repositories = Repository.objects.count()
    total_images = Image.objects.count()

    security_metrics = Vulnerability.objects.aggregate(
        critical_count=Count('uuid', filter=Q(severity='CRITICAL')),
        total_count=Count('uuid')
    )

    fixable_vulns = ComponentVersionVulnerability.objects.filter(
        fixable=True
    ).values('vulnerability').distinct().count()

    total_vulns = security_metrics['total_count']
    fixable_percentage = (fixable_vulns / total_vulns * 100) if total_vulns > 0 else 0
    cisa_kev_vulns = Vulnerability.objects.filter(details__cisa_kev_known_exploited=True).count()
    exploit_available_vulns = Vulnerability.objects.filter(details__exploit_available=True).count()
    ransomware_vulns = Vulnerability.objects.filter(details__cisa_kev_ransomware_use='Known').count()
    vulns_with_details = Vulnerability.objects.filter(details__isnull=False).count()

    cisa_kev_percentage = (cisa_kev_vulns / total_vulns * 100) if total_vulns > 0 else 0
    exploit_percentage = (exploit_available_vulns / total_vulns * 100) if total_vulns > 0 else 0
    ransomware_percentage = (ransomware_vulns / total_vulns * 100) if total_vulns > 0 else 0
    details_percentage = (vulns_with_details / total_vulns * 100) if total_vulns > 0 else 0

    return {
        'basic_stats': {
            'repositories': total_repositories,
            'images': total_images,
        },
        'security_metrics': {
            'critical_vulnerabilities': security_metrics['critical_count'],
            'fixable_vulnerabilities': fixable_vulns,
            'fixable_percentage': round(fixable_percentage, 1),
            'cisa_kev_vulnerabilities': cisa_kev_vulns,
            'cisa_kev_percentage': round(cisa_kev_percentage, 1),
            'exploit_available_vulnerabilities': exploit_available_vulns,
            'exploit_percentage': round(exploit_percentage, 1),
            'ransomware_vulnerabilities': ransomware_vulns,
            'ransomware_percentage': round(ransomware_percentage, 1),
            'vulnerabilities_with_details': vulns_with_details,
            'details_percentage': round(details_percentage, 1),
        },
    }


def _build_dashboard_visualizations_payload():
    from django.db.models import Count

    severity_distribution = Vulnerability.objects.values('severity').annotate(
        count=Count('uuid')
    ).order_by('severity')

    return {
        'severity_distribution': list(severity_distribution),
        'vulnerability_trends': _build_vulnerability_trend_series(days=30),
    }


def _build_dashboard_top_lists_payload():
    from django.db.models import Count

    top_vulnerable_components = ComponentVersion.objects.select_related('component').annotate(
        vuln_count=Count('vulnerabilities')
    ).filter(vuln_count__gt=0).order_by('-vuln_count')[:10]

    top_vulnerabilities_by_epss = Vulnerability.objects.filter(
        epss__isnull=False
    ).only('uuid', 'vulnerability_id', 'severity', 'epss', 'description').order_by('-epss')[:10]

    return {
        'top_vulnerable_components': [
            {
                'name': cv.component.name,
                'version': cv.version,
                'vulnerability_count': cv.vuln_count,
            }
            for cv in top_vulnerable_components
        ],
        'top_vulnerabilities_by_epss': [
            {
                'uuid': str(vuln.uuid),
                'vulnerability_id': vuln.vulnerability_id,
                'severity': vuln.severity,
                'epss': round(vuln.epss, 3),
                'description': (
                    f"{vuln.description[:100]}..."
                    if vuln.description and len(vuln.description) > 100
                    else vuln.description
                ),
            }
            for vuln in top_vulnerabilities_by_epss
        ],
    }


def _build_dashboard_activity_payload():
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_activities = list(_build_recent_activity_queryset(thirty_days_ago)[:10])
    for activity in recent_activities:
        activity['type'] = activity.pop('activity_type')
        activity['severity'] = activity.pop('activity_severity')
        activity['status'] = activity.pop('activity_status')

    return {
        'recent_activities': recent_activities[:10],
    }


def _build_dashboard_threat_intel_payload():
    return {
        'weekly_threat_intel': get_dashboard_weekly_threat_intel(limit=5),
    }


def _build_dashboard_analytics_payload():
    return {
        'risk_rankings': build_dashboard_risk_rankings(limit=5),
        'fixability_analytics': build_dashboard_fixability_analytics(),
        'recent_scan_deltas': build_recent_scan_deltas(limit=10),
    }


def _build_dashboard_root_causes_payload():
    from .models import SharedRootCauseAnalyticsSnapshotRow

    latest_snapshots = get_latest_root_cause_analytics_snapshots()
    latest_snapshot = latest_snapshots.get('shared')
    if latest_snapshot:
        queryset = _apply_root_cause_ordering(
            SharedRootCauseAnalyticsSnapshotRow.objects.filter(
                snapshot=latest_snapshot,
                affected_repositories_count__gt=1,
            ).defer('repositories_preview', 'vulnerabilities_preview'),
            '-weighted_risk_score',
            ordering_map=ROOT_CAUSE_SNAPSHOT_ORDERING_MAP,
        )[:5]
        return {
            'shared_root_causes': SharedRootCauseSerializer(queryset, many=True).data,
            'root_cause_snapshot_generated_at': latest_snapshot.updated_at.isoformat(),
        }

    queryset = _apply_root_cause_ordering(
        build_shared_root_cause_queryset().filter(
            affected_repositories_count__gt=1,
        ),
        '-weighted_risk_score',
    )[:5]
    return {
        'shared_root_causes': _serialize_root_causes(list(queryset), include_previews=True),
    }


def _build_dashboard_base_lineage_root_causes_payload():
    from .models import BaseLineageRootCauseAnalyticsSnapshotRow

    latest_snapshots = get_latest_root_cause_analytics_snapshots()
    latest_snapshot = latest_snapshots.get('base_lineage')
    if latest_snapshot:
        queryset = _apply_base_lineage_ordering(
            BaseLineageRootCauseAnalyticsSnapshotRow.objects.filter(
                snapshot=latest_snapshot,
                lineage_label__isnull=False,
            ).exclude(
                lineage_label='unknown',
            ).filter(
                affected_images_count__gt=0,
                affected_repositories_count__gt=1,
            ).defer('repositories_preview', 'components_preview', 'vulnerabilities_preview'),
            '-weighted_risk_score',
            ordering_map=BASE_LINEAGE_SNAPSHOT_ORDERING_MAP,
        )[:5]
        return {
            'base_lineage_root_causes': BaseLineageRootCauseSerializer(queryset, many=True).data,
            'base_lineage_snapshot_generated_at': latest_snapshot.updated_at.isoformat(),
        }

    lineage_members = build_base_lineage_image_queryset().exclude(lineage_label='unknown')
    grouped_queryset = build_base_lineage_grouped_queryset(lineage_members).filter(
        affected_images_count__gt=0,
        affected_repositories_count__gt=1,
    )
    grouped_queryset = _apply_base_lineage_ordering(grouped_queryset, '-weighted_risk_score')[:5]
    grouped_rows = list(grouped_queryset)
    labels = [row['lineage_label'] for row in grouped_rows]
    page_members = lineage_members.filter(lineage_label__in=labels)
    return {
        'base_lineage_root_causes': _serialize_base_lineage_root_causes(
            grouped_rows,
            page_members,
            include_previews=True,
        ),
    }


def _annotate_image_comparison_fields(queryset):
    image_basename = Func(
        F('name'),
        Value(r'^.*/'),
        Value(''),
        function='regexp_replace',
        output_field=CharField(),
    )
    return queryset.annotate(
        logical_name=Func(
            Func(
                image_basename,
                Value(r'@.*$'),
                Value(''),
                function='regexp_replace',
                output_field=CharField(),
            ),
            Value(r':[^:]+$'),
            Value(''),
            function='regexp_replace',
            output_field=CharField(),
        ),
        registry_host=Func(
            F('name'),
            Value(r'/.*$'),
            Value(''),
            function='regexp_replace',
            output_field=CharField(),
        ),
        repository_path=Func(
            Func(
                F('name'),
                Value(r'^[^/]*/'),
                Value(''),
                function='regexp_replace',
                output_field=CharField(),
            ),
            Value(r':[^:]+$'),
            Value(''),
            function='regexp_replace',
            output_field=CharField(),
        ),
    )


def _apply_image_comparison_ordering(queryset, ordering, default='-variant_count'):
    requested = []
    for field in (ordering or default).split(','):
        field = field.strip()
        if not field:
            continue
        resolved = IMAGE_COMPARISON_ORDERING_MAP.get(field)
        if resolved:
            requested.append(resolved)
    if not requested:
        requested = [IMAGE_COMPARISON_ORDERING_MAP[default]]
    return queryset.order_by(*requested)


def _apply_root_cause_ordering(queryset, ordering, default='-weighted_risk_score', ordering_map=None):
    ordering_map = ordering_map or ROOT_CAUSE_ORDERING_MAP
    requested = []
    for field in (ordering or default).split(','):
        field = field.strip()
        if not field:
            continue
        resolved = ordering_map.get(field)
        if resolved:
            requested.append(resolved)
    if not requested:
        requested = [ordering_map[default]]
    if ordering_map is ROOT_CAUSE_SNAPSHOT_ORDERING_MAP:
        return queryset.order_by(*requested, 'component_name', 'version')
    return queryset.order_by(*requested, 'component__name', 'version')


def _apply_base_lineage_ordering(queryset, ordering, default='-weighted_risk_score', ordering_map=None):
    ordering_map = ordering_map or BASE_LINEAGE_ORDERING_MAP
    requested = []
    for field in (ordering or default).split(','):
        field = field.strip()
        if not field:
            continue
        resolved = ordering_map.get(field)
        if resolved:
            requested.append(resolved)
    if not requested:
        requested = [ordering_map[default]]
    return queryset.order_by(*requested, 'lineage_label')


def _build_root_cause_preview_maps(component_versions):
    component_version_ids = [component_version.pk for component_version in component_versions]
    if not component_version_ids:
        return {}, {}

    repository_rows = Repository.objects.filter(
        tags__images__component_versions__pk__in=component_version_ids,
        tags__images__scan_status='success',
    ).values(
        'tags__images__component_versions__pk',
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
        'tags__images__component_versions__pk',
        '-affected_images_count',
        'name',
    )

    repositories_preview_map = defaultdict(list)
    for row in repository_rows:
        component_version_id = row['tags__images__component_versions__pk']
        preview_list = repositories_preview_map[component_version_id]
        if len(preview_list) >= 5:
            continue
        preview_list.append({
            'repository_uuid': str(row['uuid']),
            'repository_name': row['name'],
            'affected_images_count': row['affected_images_count'] or 0,
            'affected_tags_count': row['affected_tags_count'] or 0,
        })

    vulnerability_rows = ComponentVersionVulnerability.objects.filter(
        component_version__pk__in=component_version_ids,
    ).values(
        'component_version__pk',
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
        grouped_vulnerability_rows[row['component_version__pk']].append(row)

    for component_version_id, rows in grouped_vulnerability_rows.items():
        rows.sort(
            key=lambda row: (
                -severity_rank_map.get((row['vulnerability__severity'] or 'UNKNOWN').upper(), 0),
                -(row['vulnerability__epss'] or 0.0),
                row['vulnerability__vulnerability_id'] or '',
            )
        )
        vulnerabilities_preview_map[component_version_id] = [
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


def _serialize_root_causes(component_versions, include_previews=False):
    repositories_preview_map = {}
    vulnerabilities_preview_map = {}
    if include_previews:
        repositories_preview_map, vulnerabilities_preview_map = _build_root_cause_preview_maps(component_versions)
    rows = []
    for component_version in component_versions:
        fixability_category = get_fixability_category_from_priority(
            getattr(component_version, 'max_fix_priority', 0) or 0
        )
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
            'fixability_category': fixability_category,
            'fixability_breakdown': {
                'fixable_now': getattr(component_version, 'fixable_now_count', 0) or 0,
                'fix_exists_but_not_in_repo': getattr(component_version, 'fix_exists_but_not_in_repo_count', 0) or 0,
                'no_fix': getattr(component_version, 'no_fix_count', 0) or 0,
                'fix_unknown': getattr(component_version, 'fix_unknown_count', 0) or 0,
            },
            'latest_seen_at': getattr(component_version, 'latest_seen_at', None),
            'repositories_preview': repositories_preview_map.get(component_version.pk, []),
            'vulnerabilities_preview': vulnerabilities_preview_map.get(component_version.pk, []),
        })
    return rows


def _build_shared_root_cause_preview_payload(component_version):
    repositories_preview_map, vulnerabilities_preview_map = _build_root_cause_preview_maps([component_version])
    return {
        'repositories_preview': repositories_preview_map.get(component_version.pk, []),
        'vulnerabilities_preview': vulnerabilities_preview_map.get(component_version.pk, []),
    }


def _build_base_lineage_preview_maps(lineage_members):
    image_ids = [image.pk for image in lineage_members]
    if not image_ids:
        return {}, {}, {}

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


def _serialize_base_lineage_root_causes(grouped_rows, lineage_members=None, include_previews=False):
    repositories_preview_map = {}
    components_preview_map = {}
    vulnerabilities_preview_map = {}
    if include_previews and lineage_members is not None:
        repositories_preview_map, components_preview_map, vulnerabilities_preview_map = _build_base_lineage_preview_maps(lineage_members)

    rows = []
    for row in grouped_rows:
        fixability_category = get_fixability_category_from_priority(
            row.get('max_fix_priority', 0) or 0
        )
        lineage_label = row['lineage_label']
        rows.append({
            'key': lineage_label,
            'lineage_label': lineage_label,
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
            'fixability_category': fixability_category,
            'fixability_breakdown': {
                'fixable_now': row.get('fixable_now_count', 0) or 0,
                'fix_exists_but_not_in_repo': row.get('fix_exists_but_not_in_repo_count', 0) or 0,
                'no_fix': row.get('no_fix_count', 0) or 0,
                'fix_unknown': row.get('fix_unknown_count', 0) or 0,
            },
            'latest_seen_at': row.get('latest_seen_at'),
            'repositories_preview': repositories_preview_map.get(lineage_label, []),
            'components_preview': components_preview_map.get(lineage_label, []),
            'vulnerabilities_preview': vulnerabilities_preview_map.get(lineage_label, []),
        })
    return rows


def _build_base_lineage_preview_payload(lineage_label, lineage_members):
    repositories_preview_map, components_preview_map, vulnerabilities_preview_map = _build_base_lineage_preview_maps(lineage_members)
    return {
        'repositories_preview': repositories_preview_map.get(lineage_label, []),
        'components_preview': components_preview_map.get(lineage_label, []),
        'vulnerabilities_preview': vulnerabilities_preview_map.get(lineage_label, []),
    }


def _parse_bounded_integer(value, default, minimum=0, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default

    if parsed < minimum:
        parsed = minimum
    if maximum is not None and parsed > maximum:
        parsed = maximum
    return parsed


def _paginate_section_results(results, offset, limit, has_more=False):
    paged_results = results[:limit]
    return {
        'offset': offset,
        'limit': limit,
        'next_offset': offset + limit if has_more else None,
        'has_more': has_more,
        'results': paged_results,
    }


def _build_base_lineage_repositories_section_payload(lineage_members, offset=0, limit=20):
    rows = list(
        lineage_members
        .filter(repository_tags__repository__uuid__isnull=False)
        .values(
            repository_uuid=F('repository_tags__repository__uuid'),
            repository_name=F('repository_tags__repository__name'),
        )
        .annotate(
            affected_images_count=Count('pk', distinct=True),
            affected_tags_count=Count('repository_tags', distinct=True),
        )
        .order_by('-affected_images_count', '-affected_tags_count', 'repository_name')[offset:offset + limit + 1]
    )
    serialized = RootCauseRepositoryPreviewSerializer(rows[:limit], many=True).data
    return _paginate_section_results(serialized, offset, limit, has_more=len(rows) > limit)


def _build_base_lineage_components_section_payload(lineage_members, offset=0, limit=20):
    rows = list(
        lineage_members
        .filter(
            component_versions__component__uuid__isnull=False,
            component_versions__version__isnull=False,
        )
        .values(
            component_uuid=F('component_versions__component__uuid'),
            component_name=F('component_versions__component__name'),
            version=F('component_versions__version'),
            component_type=F('component_versions__component__type'),
        )
        .annotate(
            affected_images_count=Count('pk', distinct=True),
            vulnerabilities_count=Count(
                'component_versions__componentversionvulnerability__vulnerability',
                distinct=True,
            ),
        )
        .order_by(
            '-affected_images_count',
            '-vulnerabilities_count',
            'component_name',
            'version',
        )[offset:offset + limit + 1]
    )
    serialized = BaseLineageComponentPreviewSerializer(rows[:limit], many=True).data
    return _paginate_section_results(serialized, offset, limit, has_more=len(rows) > limit)


def _build_base_lineage_vulnerabilities_section_payload(lineage_members, offset=0, limit=20):
    severity_rank = Case(
        When(
            component_versions__componentversionvulnerability__vulnerability__severity__iexact='CRITICAL',
            then=Value(4),
        ),
        When(
            component_versions__componentversionvulnerability__vulnerability__severity__iexact='HIGH',
            then=Value(3),
        ),
        When(
            component_versions__componentversionvulnerability__vulnerability__severity__iexact='MEDIUM',
            then=Value(2),
        ),
        When(
            component_versions__componentversionvulnerability__vulnerability__severity__iexact='LOW',
            then=Value(1),
        ),
        default=Value(0),
        output_field=IntegerField(),
    )
    rows = list(
        lineage_members
        .filter(component_versions__componentversionvulnerability__vulnerability__uuid__isnull=False)
        .values(
            vulnerability_uuid=F('component_versions__componentversionvulnerability__vulnerability__uuid'),
            vulnerability_id=F('component_versions__componentversionvulnerability__vulnerability__vulnerability_id'),
            severity=F('component_versions__componentversionvulnerability__vulnerability__severity'),
            epss=F('component_versions__componentversionvulnerability__vulnerability__epss'),
        )
        .annotate(
            affected_images_count=Count('pk', distinct=True),
            cisa_kev_int=Max(
                Case(
                    When(
                        component_versions__componentversionvulnerability__vulnerability__details__cisa_kev_known_exploited=True,
                        then=Value(1),
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            exploit_available_int=Max(
                Case(
                    When(
                        component_versions__componentversionvulnerability__vulnerability__details__exploit_available=True,
                        then=Value(1),
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ),
            severity_rank=severity_rank,
        )
        .order_by('-severity_rank', '-epss', '-affected_images_count', 'vulnerability_id')[offset:offset + limit + 1]
    )

    payload = [
        {
            'uuid': str(row['vulnerability_uuid']),
            'vulnerability_id': row['vulnerability_id'],
            'severity': row['severity'] or 'UNKNOWN',
            'epss': round(float(row['epss'] or 0.0), 3),
            'cisa_kev': bool(row['cisa_kev_int']),
            'exploit_available': bool(row['exploit_available_int']),
            'fix_status': None,
        }
        for row in rows[:limit]
        if row.get('vulnerability_uuid') and row.get('vulnerability_id')
    ]
    serialized = RootCauseVulnerabilityPreviewSerializer(payload, many=True).data
    return _paginate_section_results(serialized, offset, limit, has_more=len(rows) > limit)


def _build_base_lineage_section_payload(lineage_members, section, offset=0, limit=20):
    if section == 'repositories':
        return _build_base_lineage_repositories_section_payload(lineage_members, offset=offset, limit=limit)
    if section == 'components':
        return _build_base_lineage_components_section_payload(lineage_members, offset=offset, limit=limit)
    if section == 'vulnerabilities':
        return _build_base_lineage_vulnerabilities_section_payload(lineage_members, offset=offset, limit=limit)
    raise ValueError(f'Unsupported base lineage section: {section}')


def _build_targeted_base_lineage_members_queryset(lineage_label, lineage_source=None, include_unknown=False):
    base_queryset = build_base_lineage_image_queryset(
        base_queryset=Image.objects.filter(
            scan_status='success',
            repository_tags__isnull=False,
        ),
        include_risk_score=False,
    )

    if lineage_label == 'unknown':
        if not include_unknown:
            return base_queryset.none()
        return base_queryset.filter(lineage_label='unknown')

    filters = Q(lineage_label=lineage_label)
    if lineage_source:
        filters &= Q(lineage_source=lineage_source)

    return base_queryset.filter(filters)


def _build_optimized_image_list_queryset(queryset):
    """Annotate lightweight image summary fields without loading large JSON blobs."""
    return queryset.annotate(
        findings_count=Count(
            'component_versions__componentversionvulnerability',
            distinct=False
        ),
        unique_findings_count=Count(
            'component_versions__componentversionvulnerability__vulnerability',
            distinct=True
        ),
        components_count=Count(
            'component_versions',
            distinct=True
        ),
        has_sbom=Case(
            When(sbom_data__isnull=False, then=True),
            default=False,
            output_field=BooleanField()
        ),
        has_grype=Case(
            When(grype_data__isnull=False, then=True),
            default=False,
            output_field=BooleanField()
        )
    ).prefetch_related(
        'repository_tags__repository'
    ).defer('sbom_data', 'grype_data')


def _image_list_needs_metric_ordering(ordering):
    for field in (ordering or '').split(','):
        field = field.strip().lstrip('-')
        if field in IMAGE_LIST_METRIC_ORDERING_FIELDS:
            return True
    return False


def _build_lightweight_image_list_queryset(queryset):
    """Image list base queryset without global component/vulnerability joins."""
    return queryset.only(
        'uuid',
        'name',
        'digest',
        'scan_status',
        'lineage_label',
        'lineage_source',
        'os_distro_name',
        'os_distro_version',
        'os_eol_status',
        'os_eol_source',
        'os_eol_message',
        'os_eol_checked_at',
        'created_at',
        'updated_at',
    ).annotate(
        has_sbom=Case(
            When(sbom_data__isnull=False, then=True),
            default=False,
            output_field=BooleanField()
        ),
        has_grype=Case(
            When(grype_data__isnull=False, then=True),
            default=False,
            output_field=BooleanField()
        )
    ).defer('sbom_data', 'grype_data')


def _hydrate_image_list_page_metrics(images):
    """Attach image list counts and first tag info after pagination."""
    image_ids = [image.pk for image in images]
    if not image_ids:
        return

    through_model = ComponentVersion.images.through
    component_count_map = {
        row['image_id']: row['total']
        for row in through_model.objects.filter(image_id__in=image_ids)
        .values('image_id')
        .annotate(total=Count('componentversion_id', distinct=True))
    }

    vulnerability_count_rows = (
        ComponentVersionVulnerability.objects
        .filter(component_version__images__pk__in=image_ids)
        .values('component_version__images__pk')
        .annotate(
            findings_count=Count('pk'),
            unique_findings_count=Count('vulnerability', distinct=True),
        )
    )
    findings_map = {
        row['component_version__images__pk']: row
        for row in vulnerability_count_rows
    }

    for image in images:
        image.components_count = component_count_map.get(image.pk, 0)
        counts = findings_map.get(image.pk, {})
        image.findings_count = counts.get('findings_count', 0)
        image.unique_findings_count = counts.get('unique_findings_count', 0)

    prefetch_related_objects(
        images,
        Prefetch(
            'repository_tags',
            queryset=RepositoryTag.objects.select_related('repository').only(
                'uuid',
                'tag',
                'repository__uuid',
                'repository__name',
                'repository__repository_type',
            ).order_by('repository__name', 'tag'),
        ),
    )


def _build_image_dropdown_queryset(queryset):
    return queryset.only('uuid', 'name').annotate(
        has_sbom=Case(
            When(sbom_data__isnull=False, then=True),
            default=False,
            output_field=BooleanField()
        )
    ).defer('sbom_data', 'grype_data')


def _component_version_list_needs_metric_ordering(ordering):
    for field in (ordering or '').split(','):
        field = field.strip().lstrip('-')
        if field in IMAGE_COMPONENT_VERSION_METRIC_ORDERING_FIELDS:
            return True
    return False


def _apply_image_component_version_ordering(queryset, ordering, default='component__name,version,created_at'):
    requested = []
    for field in (ordering or default).split(','):
        field = field.strip()
        if not field:
            continue
        resolved = IMAGE_COMPONENT_VERSION_ORDERING_MAP.get(field)
        if resolved:
            requested.append(resolved)
    if not requested:
        requested = [
            IMAGE_COMPONENT_VERSION_ORDERING_MAP[field]
            for field in default.split(',')
            if field in IMAGE_COMPONENT_VERSION_ORDERING_MAP
        ]
    return queryset.order_by(*requested)


def _build_lightweight_image_component_versions_queryset(image_uuid):
    return (
        ComponentVersion.objects
        .filter(images__uuid=image_uuid)
        .select_related('component')
        .only(
            'uuid',
            'version',
            'created_at',
            'updated_at',
            'component__uuid',
            'component__name',
            'component__type',
        )
        .distinct()
    )


def _build_metric_sorted_image_component_versions_queryset(image_uuid):
    through_model = ComponentVersion.images.through
    used_count_subquery = (
        through_model.objects
        .filter(componentversion_id=OuterRef('pk'))
        .values('componentversion_id')
        .annotate(total=Count('image_id', distinct=True))
        .values('total')[:1]
    )
    vulnerability_count_subquery = (
        ComponentVersionVulnerability.objects
        .filter(component_version_id=OuterRef('pk'))
        .values('component_version_id')
        .annotate(total=Count('vulnerability_id', distinct=True))
        .values('total')[:1]
    )
    return _build_lightweight_image_component_versions_queryset(image_uuid).annotate(
        vulnerabilities_count=Coalesce(
            Subquery(vulnerability_count_subquery, output_field=IntegerField()),
            Value(0),
        ),
        images_count=Coalesce(
            Subquery(used_count_subquery, output_field=IntegerField()),
            Value(0),
        ),
    )


def _hydrate_image_component_versions_page(component_versions, image_uuid):
    component_version_ids = [component_version.pk for component_version in component_versions]
    if not component_version_ids:
        return

    through_model = ComponentVersion.images.through
    used_count_map = {
        row['componentversion_id']: row['total']
        for row in through_model.objects.filter(componentversion_id__in=component_version_ids)
        .values('componentversion_id')
        .annotate(total=Count('image_id', distinct=True))
    }
    vulnerability_count_map = {
        row['component_version_id']: row['total']
        for row in ComponentVersionVulnerability.objects.filter(component_version_id__in=component_version_ids)
        .values('component_version_id')
        .annotate(total=Count('vulnerability_id', distinct=True))
    }
    context_map = {
        context.component_version_id: context
        for context in ImageComponentVersionContext.objects.filter(
            image_id=image_uuid,
            component_version_id__in=component_version_ids,
        )
    }

    context_fields = (
        'dependency_scope',
        'dependency_depth',
        'immediate_parent_name',
        'immediate_parent_version',
        'direct_introducer_name',
        'direct_introducer_version',
        'package_scope',
        'package_arch',
        'package_distro',
        'package_repo',
        'package_channel',
        'source_package',
        'source_package_version',
        'cataloger',
        'metadata_type',
    )

    for component_version in component_versions:
        component_version.vulnerabilities_count = vulnerability_count_map.get(component_version.pk, 0)
        component_version.images_count = used_count_map.get(component_version.pk, 0)
        context = context_map.get(component_version.pk)
        for field in context_fields:
            setattr(component_version, field, getattr(context, field, None) if context else None)


def _build_image_comparison_base_queryset(queryset):
    return _annotate_image_comparison_fields(
        queryset.only(
            'uuid',
            'name',
            'digest',
            'scan_status',
            'updated_at',
        )
    )


def _build_image_comparison_member_queryset(queryset):
    return _annotate_image_comparison_fields(
        _build_optimized_image_list_queryset(queryset)
    )


def _build_vulnerability_image_queryset(queryset, vulnerability):
    repository_tag_prefetch = Prefetch(
        'repository_tags',
        queryset=RepositoryTag.objects.select_related('repository').only(
            'uuid',
            'tag',
            'repository__uuid',
            'repository__name',
            'repository__repository_type',
        ).order_by('repository__name', 'tag'),
    )

    return queryset.annotate(
        has_sbom=Case(
            When(sbom_data__isnull=False, then=True),
            default=False,
            output_field=BooleanField()
        ),
        has_grype=Case(
            When(grype_data__isnull=False, then=True),
            default=False,
            output_field=BooleanField()
        )
    ).prefetch_related(
        repository_tag_prefetch
    ).only(
        'uuid',
        'name',
        'digest',
        'scan_status',
    ).defer('sbom_data', 'grype_data')


def _with_repository_scan_status_annotations(queryset):
    return queryset.annotate(
        tag_count=Count('tags', distinct=True),
        active_tag_count=Count(
            'tags',
            filter=Q(tags__processing_status__in=['pending', 'in_process']),
            distinct=True,
        ),
        active_image_count=Count(
            'tags__images',
            filter=Q(tags__images__scan_status__in=['pending', 'in_process']),
            distinct=True,
        ),
    )


def _build_repository_tag_image_queryset(queryset):
    """Lightweight image queryset for nested tag detail responses."""
    return queryset.annotate(
        findings_count=Count(
            'component_versions__componentversionvulnerability',
            distinct=False
        ),
        components_count=Count(
            'component_versions',
            distinct=True
        )
    ).only(
        'uuid',
        'name',
        'scan_status',
        'created_at',
        'updated_at',
    )


def _build_repository_tag_detail_queryset(queryset):
    return queryset.select_related('repository').annotate(
        total_unique_vulnerabilities=Count(
            'images__component_versions__componentversionvulnerability__vulnerability',
            distinct=True,
        ),
        total_findings=Count(
            'images__component_versions__componentversionvulnerability',
            distinct=False,
        ),
        total_components=Count(
            'images__component_versions',
            distinct=False,
        ),
    ).prefetch_related(
        Prefetch('images', queryset=_build_repository_tag_image_queryset(Image.objects.all())),
        'releases__release',
    )


def _apply_image_list_ordering(queryset, ordering, default='-updated_at'):
    requested = []
    for field in (ordering or default).split(','):
        field = field.strip()
        if not field:
            continue
        resolved = IMAGE_LIST_ORDERING_MAP.get(field)
        if resolved:
            requested.append(resolved)
    if not requested:
        requested = [IMAGE_LIST_ORDERING_MAP[default]]
    return queryset.order_by(*requested)


def _repository_tag_version_key(tag_value):
    parts = []
    remaining = tag_value or ''
    while remaining:
        match = re.match(r'^(\d+)', remaining)
        if not match:
            break
        parts.append(int(match.group(1)))
        remaining = remaining[len(match.group(1)):]
        while remaining and not remaining[0].isdigit():
            remaining = remaining[1:]
    while len(parts) < 4:
        parts.append(0)
    return (*parts[:4], (tag_value or '').lower())


def _apply_repository_tag_ordering(queryset, ordering, default='-updated_at'):
    fields = [field.strip() for field in (ordering or default).split(',') if field.strip()]
    if not fields:
        fields = [default]

    if len(fields) == 1 and fields[0].lstrip('-') == 'tag':
        tags = list(queryset)
        tags.sort(
            key=lambda tag: _repository_tag_version_key(tag.tag),
            reverse=fields[0].startswith('-')
        )
        return tags

    requested = []
    for field in fields:
        resolved = REPOSITORY_TAG_ORDERING_MAP.get(field)
        if resolved:
            requested.append(resolved)
    if not requested:
        requested = [REPOSITORY_TAG_ORDERING_MAP[default]]
    return queryset.order_by(*requested)


def _attach_repository_tag_summary_data(tags):
    """Hydrate page-level tag summary data with a handful of bulk queries."""
    tag_ids = [tag.pk for tag in tags]
    if not tag_ids:
        return

    findings_counts = {
        row['component_version__images__repository_tags__pk']: row['total']
        for row in ComponentVersionVulnerability.objects.filter(
            component_version__images__repository_tags__pk__in=tag_ids
        ).values('component_version__images__repository_tags__pk').annotate(
            total=Count('pk')
        )
    }

    component_counts = {
        row['repository_tags__pk']: row['total']
        for row in Image.objects.filter(
            repository_tags__pk__in=tag_ids
        ).values('repository_tags__pk').annotate(
            total=Count('component_versions')
        )
    }

    unique_vulnerability_counts = {
        row['component_version__images__repository_tags__pk']: row['total']
        for row in ComponentVersionVulnerability.objects.filter(
            component_version__images__repository_tags__pk__in=tag_ids
        ).values('component_version__images__repository_tags__pk').annotate(
            total=Count('vulnerability', distinct=True)
        )
    }

    image_names_map = defaultdict(list)
    image_names_seen = defaultdict(set)
    image_name_rows = Image.objects.filter(
        repository_tags__pk__in=tag_ids
    ).values(
        'repository_tags__pk',
        'name',
    ).order_by(
        'repository_tags__pk',
        'name',
    ).distinct()
    for row in image_name_rows:
        tag_pk = row['repository_tags__pk']
        image_name = row['name']
        if image_name and image_name not in image_names_seen[tag_pk]:
            image_names_seen[tag_pk].add(image_name)
            image_names_map[tag_pk].append(image_name)

    releases_map = defaultdict(list)
    for link in RepositoryTagRelease.objects.filter(
        repository_tag_id__in=tag_ids
    ).select_related('release').order_by('-added_at'):
        releases_map[link.repository_tag_id].append({
            'uuid': link.release.uuid,
            'name': link.release.name,
            'description': link.release.description,
            'added_at': link.added_at,
        })

    status_counts_map = defaultdict(dict)
    for row in Image.objects.filter(
        repository_tags__pk__in=tag_ids
    ).values(
        'repository_tags__pk',
        'scan_status',
    ).annotate(
        total=Count('pk', distinct=True)
    ):
        status_counts_map[row['repository_tags__pk']][row['scan_status'] or 'none'] = row['total']

    for tag in tags:
        tag_status_counts = status_counts_map.get(tag.pk, {})
        tag.total_findings = findings_counts.get(tag.pk, 0)
        tag.total_components = component_counts.get(tag.pk, 0)
        tag.total_unique_vulnerabilities = unique_vulnerability_counts.get(tag.pk, 0)
        tag.image_names_data = image_names_map.get(tag.pk, [])
        tag.release_data = releases_map.get(tag.pk, [])
        tag.total_images_count = sum(tag_status_counts.values())
        tag.pending_images_count = tag_status_counts.get('pending', 0)
        tag.in_process_images_count = tag_status_counts.get('in_process', 0)
        tag.error_images_count = tag_status_counts.get('error', 0)
        tag.success_images_count = tag_status_counts.get('success', 0)


def _build_release_repository_tag_payload(tags):
    serialized_tags = []
    summary = {
        'total_tags': 0,
        'success_tags': 0,
        'pending_tags': 0,
        'in_process_tags': 0,
        'error_tags': 0,
        'unscanned_tags': 0,
        'total_images': 0,
        'success_images': 0,
        'pending_images': 0,
        'in_process_images': 0,
        'error_images': 0,
    }

    for tag in tags:
        total_images = getattr(tag, 'total_images_count', 0) or 0
        pending_images = getattr(tag, 'pending_images_count', 0) or 0
        in_process_images = getattr(tag, 'in_process_images_count', 0) or 0
        error_images = getattr(tag, 'error_images_count', 0) or 0
        success_images = getattr(tag, 'success_images_count', 0) or 0
        effective_status = resolve_repository_tag_processing_status(
            getattr(tag, 'processing_status', 'none'),
            total_images,
            pending_images,
            in_process_images,
            error_images,
            success_images,
        )

        summary['total_tags'] += 1
        summary['total_images'] += total_images
        summary['success_images'] += success_images
        summary['pending_images'] += pending_images
        summary['in_process_images'] += in_process_images
        summary['error_images'] += error_images

        if effective_status == 'success':
            summary['success_tags'] += 1
        elif effective_status == 'pending':
            summary['pending_tags'] += 1
        elif effective_status == 'in_process':
            summary['in_process_tags'] += 1
        elif effective_status == 'error':
            summary['error_tags'] += 1
        else:
            summary['unscanned_tags'] += 1

        serialized_tags.append({
            'uuid': str(tag.uuid),
            'tag': tag.tag,
            'image_path': tag.image_path,
            'processing_status': effective_status,
            'findings': getattr(tag, 'total_findings', 0) or 0,
            'components': getattr(tag, 'total_components', 0) or 0,
            'vulnerabilities_count': getattr(tag, 'total_unique_vulnerabilities', 0) or 0,
            'total_images': total_images,
            'success_images': success_images,
            'pending_images': pending_images,
            'in_process_images': in_process_images,
            'error_images': error_images,
            'image_names': getattr(tag, 'image_names_data', []) or [],
            'created_at': tag.created_at,
            'updated_at': tag.updated_at,
            'repository': {
                'uuid': str(tag.repository.uuid),
                'name': tag.repository.name,
                'url': tag.repository.url,
                'repository_type': tag.repository.repository_type,
            },
        })

    summary['all_tags_scanned'] = (
        summary['total_tags'] > 0 and summary['success_tags'] == summary['total_tags']
    )

    return serialized_tags, summary

class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']  # Default ordering
    lookup_field = 'uuid'
    pagination_class = CustomPageNumberPagination

class RepositoryViewSet(BaseViewSet):
    queryset = Repository.objects.all()
    filterset_fields = ['name', 'repository_type']
    search_fields = ['name', 'url']
    ordering_fields = ['name', 'url', 'tag_count', 'created_at', 'updated_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return RepositoryListSerializer
        elif self.action == 'retrieve':
            return RepositoryDetailSerializer
        return RepositorySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list':
            qs = _with_repository_scan_status_annotations(qs)
        elif self.action == 'retrieve':
            qs = _with_repository_scan_status_annotations(
                qs.prefetch_related('image_fallback_repositories')
            )
        return qs

    def partial_update(self, request, *args, **kwargs):
        """Allow updating image_fallback_repository_uuids (for Helm repos)."""
        instance = self.get_object()
        uuids = request.data.get('image_fallback_repository_uuids')
        if uuids is not None:
            if not isinstance(uuids, list):
                return Response(
                    {'image_fallback_repository_uuids': 'Must be a list of repository UUIDs.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            valid = Repository.objects.filter(uuid__in=uuids, repository_type='docker').values_list('uuid', flat=True)
            instance.image_fallback_repositories.set(valid)
        return super().partial_update(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def names(self, request):
        """Lightweight endpoint returning only uuid and name for dropdowns."""
        qs = self.get_queryset()
        repo_type = request.query_params.get('repository_type')
        if repo_type:
            qs = qs.filter(repository_type=repo_type)
        return Response(list(qs.values('uuid', 'name').order_by('name')))

    @action(detail=True, methods=['get'])
    def tags(self, request, uuid=None):
        repository = self.get_object()
        tags = list(_build_repository_tag_detail_queryset(repository.tags.all()))
        _attach_repository_tag_summary_data(tags)
        serializer = RepositoryTagSerializer(tags, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def create_tag(self, request, uuid=None):
        """
        Create a new tag for the repository.
        """
        repository = self.get_object()
        tag_name = request.data.get('tag')
        description = request.data.get('description', '')
        
        print(f"Creating tag: repository={repository.name}, tag={tag_name}, description={description}")
        print(f"Request data: {request.data}")
        
        if not tag_name:
            return Response(
                {'error': 'Tag name is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if tag already exists
        if repository.tags.filter(tag=tag_name).exists():
            return Response(
                {'error': 'Tag already exists'}, 
                status=status.HTTP_409_CONFLICT
            )
        
        try:
            # Create new tag
            tag = RepositoryTag.objects.create(
                repository=repository,
                tag=tag_name
            )
            
            serializer = RepositoryTagSerializer(tag)
            return Response(
                serializer.data, 
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to create tag: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def create_release_with_tags(self, request):
        """
        Create a new release and link it with repository tags.
        """
        release_name = request.data.get('release_name')
        release_description = request.data.get('release_description', '')
        tag_uuids = request.data.get('tag_uuids', [])
        
        print(f"Creating release: name={release_name}, description={release_description}")
        print(f"Tag UUIDs: {tag_uuids}")
        
        if not release_name:
            return Response(
                {'error': 'Release name is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not tag_uuids:
            return Response(
                {'error': 'At least one tag UUID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Check if release name already exists (case-insensitive)
            if Release.objects.filter(name__iexact=release_name).exists():
                return Response(
                    {'release_name': ['Release with this name already exists.']}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create new release
            release = Release.objects.create(
                name=release_name,
                description=release_description
            )
            
            # Get repository tags and create links
            repository_tags = RepositoryTag.objects.filter(uuid__in=tag_uuids)
            created_links = []
            
            for tag in repository_tags:
                # Check if link already exists
                if not RepositoryTagRelease.objects.filter(
                    repository_tag=tag, 
                    release=release
                ).exists():
                    link = RepositoryTagRelease.objects.create(
                        repository_tag=tag,
                        release=release
                    )
                    created_links.append(link)
            
            # Return success response
            return Response({
                'release_uuid': str(release.uuid),
                'release_name': release.name,
                'tags_linked': len(created_links),
                'total_tags': len(tag_uuids)
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to create release: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def check_helm_releases(self, request):
        """
        Check multiple Helm releases against the database.
        Expects a list of objects with 'name' and 'app_version' fields.
        """
        releases_data = request.data.get('releases', [])
        
        if not releases_data:
            return Response(
                {'error': 'Releases data is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            results = []
            
            # Get all repositories and tags in one query
            all_repositories = Repository.objects.all()
            all_tags = RepositoryTag.objects.select_related('repository').all()
            
            # Create lookup dictionaries for faster access
            repos_by_name = {repo.name: repo for repo in all_repositories}
            tags_by_repo_and_version = {}
            
            for tag in all_tags:
                key = f"{tag.repository.uuid}_{tag.tag}"
                tags_by_repo_and_version[key] = tag
            
            for release in releases_data:
                name = release.get('name')
                app_version = release.get('app_version')
                
                if not name or not app_version:
                    results.append({
                        'name': name,
                        'app_version': app_version,
                        'repository_status': 'Error',
                        'tag_status': 'Error',
                        'error': 'Missing name or app_version'
                    })
                    continue
                
                # Check if repository exists
                repository = repos_by_name.get(name)
                repository_status = 'Found' if repository else 'Not Found'
                
                # Check if tag exists (only if repository exists)
                tag_status = 'Not Found'
                tag_uuid = None
                if repository:
                    tag_key = f"{repository.uuid}_{app_version}"
                    tag = tags_by_repo_and_version.get(tag_key)
                    if tag:
                        tag_status = 'Found'
                        tag_uuid = str(tag.uuid)
                
                results.append({
                    'name': name,
                    'app_version': app_version,
                    'repository_status': repository_status,
                    'tag_status': tag_status,
                    'repository_uuid': str(repository.uuid) if repository else None,
                    'tag_uuid': tag_uuid
                })
            
            return Response({
                'results': results,
                'total_checked': len(results),
                'repositories_found': len([r for r in results if r['repository_status'] == 'Found']),
                'tags_found': len([r for r in results if r['tag_status'] == 'Found'])
            })
            
        except Exception as e:
            return Response(
                {'error': f'Failed to check releases: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def get_acr_repos(self, request):
        """
        Get repositories from container registry (ACR or Artifactory) with pagination.
        Uses registry's native pagination. Pass provider='acr' or provider='jfrog'.

        For JFrog, pass repo_key + package_type to list individual images/charts
        inside a repo key (step 2 of the two-phase discovery).
        """
        from .models import ContainerRegistry
        from .utils.registry import get_repositories, get_repo_images

        registry_uuid = request.query_params.get('registry_uuid')
        provider = request.query_params.get('provider', 'acr')
        page_size = int(request.query_params.get('page_size', 100))
        last_repo = request.query_params.get('last')
        repo_key = request.query_params.get('repo_key')
        package_type = request.query_params.get('package_type', 'docker')
        
        try:
            if registry_uuid:
                registry = ContainerRegistry.objects.get(uuid=registry_uuid)
            else:
                registry = ContainerRegistry.objects.get(provider=provider)
            if not registry.api_url:
                return Response(
                    {"error": "Registry has no API URL configured"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # JFrog step 2: list images/charts inside a specific repo key
            if repo_key and registry.provider == 'jfrog':
                images = get_repo_images(registry, repo_key, package_type=package_type)
                return Response({
                    "repositories": [
                        {
                            "name": img[0],
                            "url": img[1],
                            "package_type": img[2],
                            "repo_key": img[3],
                        }
                        for img in images
                    ],
                    "pagination": {"next_page": None, "page_size": len(images)}
                })

            # Default: list repo keys (JFrog) or repos (ACR)
            repos, next_page = get_repositories(
                registry,
                page_size=page_size,
                last_repo=last_repo
            )
            return Response({
                "repositories": [
                    {
                        "name": repo[0],
                        "url": repo[1],
                        **({"package_type": repo[2]} if len(repo) >= 3 else {})
                    }
                    for repo in repos
                ],
                "pagination": {
                    "next_page": next_page,
                    "page_size": page_size
                }
            })
        except ContainerRegistry.DoesNotExist:
            return Response(
                {"error": "Registry not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            import traceback
            logger.exception("get_acr_repos failed: %s", e)
            return Response(
                {"error": str(e), "detail": traceback.format_exc() if settings.DEBUG else None},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def scan_tags(self, request, uuid=None):
        repository = self.get_object()
        if repository.scan_status == 'in_process':
            return Response(
                {'error': 'Repository is already being scanned'},
                status=status.HTTP_409_CONFLICT
            )
        latest_only = request.data.get('latest_only', False) if request.data else False
        if isinstance(latest_only, str):
            latest_only = latest_only.lower() in ('true', '1', 'yes')
        repository.scan_status = 'pending'
        repository.save()

        try:
            from .tasks import scan_repository_tags
            scan_repository_tags.apply_async(
                args=[str(repository.uuid)],
                kwargs={'latest_only': latest_only},
                task_name="Scan Repository Tags"
            )
            return Response({
                'status': 'success',
                'message': 'Repository tags scan scheduled successfully',
                'latest_only': latest_only,
            })
        except Exception as e:
            repository.scan_status = 'error'
            repository.save()
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='paginated-tags')
    def paginated_tags(self, request, uuid=None):
        """
        Returns paginated, searchable, and sortable list of tags for a repository.
        Optimized to paginate first and hydrate page-level summary data in bulk.
        """
        repository = self.get_object()
        tags = repository.tags.only(*REPOSITORY_TAG_LIST_ONLY_FIELDS)

        search = request.query_params.get('search')
        if search:
            tags = tags.filter(Q(tag__icontains=search))

        tags = _apply_repository_tag_ordering(
            tags,
            request.query_params.get('ordering', '-created_at'),
            default='-created_at',
        )

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(tags, request)
        page = list(page) if page is not None else list(tags[:paginator.page_size])
        _attach_repository_tag_summary_data(page)
        
        serializer = RepositoryTagListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=['get'], url_path='tags-graph')
    def tags_graph(self, request, uuid=None):
        """
        Returns the latest 30 tags for repository for use in charts (fields: uuid, tag, findings, components, created_at)
        Tags are sorted by semantic version (numeric part) and then by suffix, returning the most recent 30 tags.
        Optimized to fetch summary data only for the 30 tags shown in the chart.
        """
        repository = self.get_object()
        sorted_tags = sorted(
            list(repository.tags.only(*REPOSITORY_TAG_LIST_ONLY_FIELDS)),
            key=lambda tag: _repository_tag_version_key(tag.tag)
        )[-30:]
        _attach_repository_tag_summary_data(sorted_tags)
        
        serializer = RepositoryTagListSerializer(sorted_tags, many=True)
        return Response(serializer.data)

class RepositoryTagViewSet(BaseViewSet):
    queryset = RepositoryTag.objects.all()
    serializer_class = RepositoryTagSerializer
    filterset_fields = ['repository', 'tag']
    search_fields = ['tag', 'repository__name']
    ordering_fields = ['tag', 'created_at', 'updated_at']
    lookup_field = 'uuid'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'retrieve':
            qs = _build_repository_tag_detail_queryset(qs)
        return qs

    def _check_time_restriction(self, tag):
        """Check if 5 minutes have passed since last update"""
        if tag.updated_at:
            time_diff = timezone.now() - tag.updated_at
            if time_diff < timedelta(minutes=5):
                remaining_seconds = int((timedelta(minutes=5) - time_diff).total_seconds())
                return False, f"Please wait {remaining_seconds} seconds before trying again"
        return True, None

    @action(detail=True, methods=['get'])
    def images(self, request, uuid=None):
        tag = self.get_object()
        images = _build_optimized_image_list_queryset(tag.images.all())

        search = request.query_params.get('search')
        if search:
            images = images.filter(name__icontains=search)

        images = _apply_image_list_ordering(
            images,
            request.query_params.get('ordering', '-updated_at'),
        )
            
        page = self.paginate_queryset(images)
        if page is not None:
            serializer = ImageListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ImageListSerializer(images, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def process(self, request, uuid=None):
        tag = self.get_object()
        if tag.processing_status in ['in_process', 'pending'] or tag.images.filter(
            scan_status__in=['in_process', 'pending']
        ).exists():
            return Response(
                {'error': 'Tag is already queued for processing'}, 
                status=status.HTTP_409_CONFLICT
            )
        
        tag.processing_status = 'pending'
        tag.save()
        
        try:
            from .tasks import process_single_tag
            process_single_tag.apply_async(args=[str(tag.uuid)], task_name="Process Single Tag")
            return Response({
                'status': 'success',
                'message': 'Tag processing scheduled successfully'
            })
        except Exception as e:
            tag.processing_status = 'error'
            tag.save()
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='rescan-images')
    def rescan_images(self, request, uuid=None):
        tag = self.get_object()
        images = tag.images.all()
        # Check if any image is already being scanned or queued
        if images.filter(scan_status__in=['in_process', 'pending']).exists():
            return Response(
                {'error': 'At least one image is already being scanned or queued for scanning'},
                status=status.HTTP_409_CONFLICT
            )
        started = 0
        from .tasks import generate_sbom_and_create_components
        for image in images:
            if image.scan_status != 'in_process':
                image.scan_status = 'pending'
                image.save()
                repo_tag = image.repository_tags.first()
                art_type = repo_tag.repository.repository_type if repo_tag else 'docker'
                generate_sbom_and_create_components.apply_async(
                    kwargs={
                        'image_uuid': str(image.uuid),
                        'art_type': art_type
                    },
                    task_name="Generate SBOM and Create Components"
                )
                started += 1
        if started:
            tag.processing_status = 'in_process'
            tag.save(update_fields=['processing_status', 'updated_at'])
        return Response({
            'status': 'success',
            'message': f'Rescan started for {started} images',
            'count': started
        })

    @action(detail=True, methods=['post'], url_path='reanalyze-sbom')
    def reanalyze_sbom(self, request, uuid=None):
        """
        Re-analyze SBOM for all images in this tag that have SBOM data.
        This will re-run Grype scan on existing SBOM data.
        Skips images that are already being scanned, but continues with others.
        """
        tag = self.get_object()
        images = tag.images.filter(
            sbom_data__isnull=False
        ).exclude(sbom_data={})
        
        if not images.exists():
            return Response(
                {'error': 'No images with SBOM data found for this tag'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Separate images into those that can be scanned and those that are already in process
        available_images = images.exclude(scan_status__in=['in_process', 'pending'])
        skipped_images = images.filter(scan_status__in=['in_process', 'pending'])
        
        if not available_images.exists():
            return Response(
                {
                    'error': 'All images are already being scanned or queued for scanning',
                    'skipped_count': skipped_images.count(),
                    'total_images_with_sbom': images.count()
                },
                status=status.HTTP_409_CONFLICT
            )
        
        started = 0
        from .tasks import scan_image_with_grype
        for image in available_images:
            # Set status to pending to prevent duplicate scans
            image.scan_status = 'pending'
            image.save()
            scan_image_with_grype.delay(str(image.uuid))
            started += 1

        if started:
            tag.processing_status = 'in_process'
            tag.save(update_fields=['processing_status', 'updated_at'])
        
        message = f'Reanalysis started for {started} images with SBOM data'
        if skipped_images.exists():
            message += f' ({skipped_images.count()} images skipped - already in process)'
        
        return Response({
            'status': 'success',
            'message': message,
            'count': started,
            'skipped_count': skipped_images.count(),
            'total_images_with_sbom': images.count()
        })

    @action(detail=True, methods=['post'])
    def add_to_release(self, request, uuid=None):
        """Add repository tag to release"""
        repository_tag = self.get_object()
        serializer = ReleaseAssignmentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            release_id = serializer.validated_data['release_id']
            release = Release.objects.get(uuid=release_id)
            
            # Check if assignment already exists
            assignment, created = RepositoryTagRelease.objects.get_or_create(
                repository_tag=repository_tag,
                release=release
            )
            
            if created:
                return Response({
                    'message': f'Repository tag added to release "{release.name}"',
                    'release': ReleaseSerializer(release).data
                })
            else:
                return Response({
                    'message': f'Repository tag already assigned to release "{release.name}"',
                    'release': ReleaseSerializer(release).data
                })
                
        except Release.DoesNotExist:
            return Response(
                {'error': 'Release not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['delete'])
    def remove_from_release(self, request, uuid=None):
        """Remove repository tag from release"""
        repository_tag = self.get_object()
        serializer = ReleaseAssignmentSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            release_id = serializer.validated_data['release_id']
            assignment = RepositoryTagRelease.objects.filter(
                repository_tag=repository_tag,
                release_id=release_id
            ).first()
            
            if assignment:
                release_name = assignment.release.name
                assignment.delete()
                return Response({
                    'message': f'Repository tag removed from release "{release_name}"'
                })
            else:
                return Response({
                    'message': 'Repository tag not assigned to this release'
                })
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ImageViewSet(BaseViewSet):
    queryset = Image.objects.all()
    filterset_fields = ['repository_tags', 'component_versions']
    search_fields = ['name', 'lineage_label', 'os_distro_name', 'os_distro_version', 'os_eol_status']
    ordering_fields = ['name', 'lineage_label', 'os_eol_status', 'digest', 'created_at', 'updated_at', 'findings_count', 'unique_findings_count', 'components_count']
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    def get_serializer_class(self):
        if self.action == 'list' and self.request and self.request.query_params.get('dropdown') == '1':
            return ImageDropdownSerializer
        if self.action == 'list':
            return ImageListSerializer
        return ImageSerializer

    def get_queryset(self):
        # Always apply search and filters, even for dropdown
        queryset = super().get_queryset()
        
        # Optimize for list action - prevent N+1 queries and memory issues
        if self.action == 'list':
            if self.request and self.request.query_params.get('dropdown') == '1':
                queryset = _build_image_dropdown_queryset(queryset)
            elif self.request and _image_list_needs_metric_ordering(self.request.query_params.get('ordering')):
                queryset = _build_optimized_image_list_queryset(queryset)
            else:
                queryset = _build_lightweight_image_list_queryset(queryset)
        elif self.action == 'retrieve':
            queryset = queryset.annotate(
                components_count=Count('component_versions', distinct=True),
                has_sbom=Case(
                    When(sbom_data__isnull=False, then=True),
                    default=False,
                    output_field=BooleanField()
                ),
                has_grype=Case(
                    When(grype_data__isnull=False, then=True),
                    default=False,
                    output_field=BooleanField()
                )
            ).prefetch_related(
                'repository_tags__repository'
            ).defer('sbom_data', 'grype_data')
        
        return queryset

    def list(self, request, *args, **kwargs):
        if request.query_params.get('dropdown') == '1':
            return super().list(request, *args, **kwargs)

        metric_ordering = _image_list_needs_metric_ordering(request.query_params.get('ordering'))
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            items = list(page)
            if not metric_ordering:
                _hydrate_image_list_page_metrics(items)
            serializer = self.get_serializer(items, many=True)
            return self.get_paginated_response(serializer.data)

        items = list(queryset)
        if not metric_ordering:
            _hydrate_image_list_page_metrics(items)
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='comparisons')
    def comparisons(self, request):
        base_queryset = _build_image_comparison_base_queryset(super().get_queryset())

        search = (request.query_params.get('search') or '').strip()
        if search:
            base_queryset = base_queryset.filter(
                Q(logical_name__icontains=search) |
                Q(name__icontains=search) |
                Q(registry_host__icontains=search) |
                Q(repository_path__icontains=search)
            )

        duplicates_only_param = request.query_params.get('duplicates_only', 'true')
        duplicates_only = str(duplicates_only_param).lower() not in {'false', '0', 'no'}
        requested_ordering = request.query_params.get('ordering', '-variant_count')
        expensive_sort_fields = {'max_findings', '-max_findings', 'max_unique_findings', '-max_unique_findings', 'max_components_count', '-max_components_count'}
        needs_global_metric_sort = any(
            field.strip() in expensive_sort_fields
            for field in requested_ordering.split(',')
            if field.strip()
        )

        grouped_queryset = base_queryset.values('logical_name').annotate(
            variant_count=Count('uuid'),
            registry_count=Count('registry_host', distinct=True),
            distinct_digests=Count('digest', distinct=True),
            latest_updated_at=Max('updated_at'),
            success_count=Count('uuid', filter=Q(scan_status='success')),
            error_count=Count('uuid', filter=Q(scan_status='error')),
            in_process_count=Count('uuid', filter=Q(scan_status='in_process')),
            pending_count=Count('uuid', filter=Q(scan_status='pending')),
            none_count=Count('uuid', filter=Q(scan_status='none')),
        )

        if needs_global_metric_sort:
            metric_queryset = _build_image_comparison_member_queryset(super().get_queryset())
            if search:
                metric_queryset = metric_queryset.filter(
                    Q(logical_name__icontains=search) |
                    Q(name__icontains=search) |
                    Q(registry_host__icontains=search) |
                    Q(repository_path__icontains=search)
                )

            findings_subquery = Subquery(
                metric_queryset.filter(logical_name=OuterRef('logical_name'))
                .order_by('-findings_count')
                .values('findings_count')[:1],
                output_field=IntegerField(),
            )
            unique_findings_subquery = Subquery(
                metric_queryset.filter(logical_name=OuterRef('logical_name'))
                .order_by('-unique_findings_count')
                .values('unique_findings_count')[:1],
                output_field=IntegerField(),
            )
            components_subquery = Subquery(
                metric_queryset.filter(logical_name=OuterRef('logical_name'))
                .order_by('-components_count')
                .values('components_count')[:1],
                output_field=IntegerField(),
            )
            grouped_queryset = grouped_queryset.annotate(
                max_findings=Coalesce(findings_subquery, Value(0)),
                max_unique_findings=Coalesce(unique_findings_subquery, Value(0)),
                max_components_count=Coalesce(components_subquery, Value(0)),
            )
        else:
            grouped_queryset = grouped_queryset.annotate(
                max_findings=Value(0, output_field=IntegerField()),
                max_unique_findings=Value(0, output_field=IntegerField()),
                max_components_count=Value(0, output_field=IntegerField()),
            )

        if duplicates_only:
            grouped_queryset = grouped_queryset.filter(variant_count__gt=1)

        grouped_queryset = _apply_image_comparison_ordering(
            grouped_queryset,
            requested_ordering,
        )

        page = self.paginate_queryset(grouped_queryset)
        grouped_rows = list(page) if page is not None else list(grouped_queryset)
        logical_names = [row['logical_name'] for row in grouped_rows]

        comparison_members = _apply_image_list_ordering(
            _build_image_comparison_member_queryset(
                super().get_queryset()
            ).filter(logical_name__in=logical_names),
            request.query_params.get('member_ordering', 'name'),
            default='name',
        )

        members_by_logical_name = defaultdict(list)
        for image in comparison_members:
            members_by_logical_name[getattr(image, 'logical_name', image.name)].append(image)

        serialized_groups = []
        for row in grouped_rows:
            variants = members_by_logical_name.get(row['logical_name'], [])
            max_findings = max((getattr(image, 'findings_count', 0) or 0) for image in variants) if variants else (row['max_findings'] or 0)
            max_unique_findings = max((getattr(image, 'unique_findings_count', 0) or 0) for image in variants) if variants else (row['max_unique_findings'] or 0)
            max_components_count = max((getattr(image, 'components_count', 0) or 0) for image in variants) if variants else (row['max_components_count'] or 0)
            serialized_groups.append({
                'logical_name': row['logical_name'],
                'variant_count': row['variant_count'],
                'registry_count': row['registry_count'],
                'distinct_digests': row['distinct_digests'],
                'different_digests': (row['distinct_digests'] or 0) > 1,
                'max_findings': max_findings,
                'max_unique_findings': max_unique_findings,
                'max_components_count': max_components_count,
                'latest_updated_at': row['latest_updated_at'],
                'status_breakdown': {
                    'success': row['success_count'] or 0,
                    'error': row['error_count'] or 0,
                    'in_process': row['in_process_count'] or 0,
                    'pending': row['pending_count'] or 0,
                    'none': row['none_count'] or 0,
                },
                'variants': variants,
            })

        serializer = ImageComparisonGroupSerializer(serialized_groups, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_latest_versions(self, request, uuid=None):
        """
        Update latest versions for all components in this image.
        This will check all package registries for the latest available versions.
        """
        image = self.get_object()
        try:
            from .tasks import update_components_latest_versions
            update_components_latest_versions.delay(str(image.uuid))
            return Response({
                'status': 'success',
                'message': 'Latest versions update scheduled successfully'
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='vulnerabilities')
    def vulnerabilities(self, request, uuid=None):
        """
        Paginated list of vulnerabilities for a given image, with search and ordering support.
        """
        # Temporarily disable search filter for this action
        original_filter_backends = self.filter_backends
        self.filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
        
        try:
            image = self.get_object()
        except Exception:
            self.filter_backends = original_filter_backends
            return Response({'error': 'Image not found'}, status=404)
        
        # Restore original filter_backends
        self.filter_backends = original_filter_backends
        
        # Get all vulnerabilities linked to this image through component versions
        vulnerabilities = Vulnerability.objects.filter(
            component_versions__images=image
        ).select_related('details').annotate(
            image_fixable=Count(
                'componentversionvulnerability',
                filter=Q(
                    componentversionvulnerability__component_version__images=image,
                    componentversionvulnerability__fixable=True,
                ),
                distinct=True,
            )
        ).distinct()

        # Search
        search = request.query_params.get('search')
        if search:
            vulnerabilities = vulnerabilities.filter(
                vulnerability_id__icontains=search
            )

        # Ordering
        ordering = request.query_params.get('ordering')
        if ordering:
            # Support ordering by vulnerability fields
            ordering_map = {
                'vulnerability_id': 'vulnerability_id',
                '-vulnerability_id': '-vulnerability_id',
                'vulnerability_type': 'vulnerability_type',
                '-vulnerability_type': '-vulnerability_type',
                'severity': 'severity',
                '-severity': '-severity',
                'epss': 'epss',
                '-epss': '-epss',
                'fixable': 'image_fixable',
                '-fixable': '-image_fixable',
                'created_at': 'created_at',
                '-created_at': '-created_at',
                'updated_at': 'updated_at',
                '-updated_at': '-updated_at',
            }
            ordering_field = ordering_map.get(ordering, ordering)
            if ordering in ['severity', '-severity']:
                vulnerabilities = vulnerabilities.annotate(
                    _severity_order=Case(
                        When(severity='CRITICAL', then=Value(4)),
                        When(severity='HIGH', then=Value(3)),
                        When(severity='MEDIUM', then=Value(2)),
                        When(severity='LOW', then=Value(1)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ).order_by('-_severity_order' if ordering == '-severity' else '_severity_order', 'vulnerability_id')
            else:
                vulnerabilities = vulnerabilities.order_by(ordering_field, 'vulnerability_id')
        else:
            vulnerabilities = vulnerabilities.order_by('-created_at')

        # Pagination
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(vulnerabilities, request)
        
        # Bulk-fetch fix info for all vulns on this page in one query
        page_vuln_ids = [v.pk for v in page]
        cvv_qs = ComponentVersionVulnerability.objects.filter(
            vulnerability__pk__in=page_vuln_ids,
            component_version__images=image
        ).values('vulnerability__pk', 'fixable', 'fix', 'fix_status', 'fix_state', 'fix_versions')
        fix_map = {}
        for row in cvv_qs.order_by('vulnerability__pk', '-fixable', 'fix'):
            fix_map.setdefault(row['vulnerability__pk'], row)

        vuln_data = []
        for vuln in page:
            vuln_dict = VulnerabilitySerializer(vuln).data
            cvv_row = fix_map.get(vuln.pk)
            if cvv_row:
                vuln_dict['fixable'] = cvv_row['fixable']
                vuln_dict['fix'] = cvv_row['fix']
                vuln_dict['fix_status'] = cvv_row['fix_status']
                vuln_dict['fix_state'] = cvv_row['fix_state']
                vuln_dict['fix_versions'] = cvv_row['fix_versions']
            else:
                vuln_dict['fixable'] = False
                vuln_dict['fix'] = ''
                vuln_dict['fix_status'] = 'unknown'
                vuln_dict['fix_state'] = ''
                vuln_dict['fix_versions'] = []
            vuln_data.append(vuln_dict)
        
        return paginator.get_paginated_response(vuln_data)

    @action(detail=True, methods=['post'])
    def rescan(self, request, uuid=None):
        image = self.get_object()
        if image.scan_status in ['in_process', 'pending']:
            return Response(
                {'error': 'Image is already being scanned or queued for scanning'}, 
                status=status.HTTP_409_CONFLICT
            )
        image.scan_status = 'pending'
        image.save()
        try:
            repo_tag = image.repository_tags.first()
            if repo_tag:
                art_type = repo_tag.repository.repository_type
            else:
                art_type = 'docker'  # fallback default
            from .tasks import generate_sbom_and_create_components
            generate_sbom_and_create_components.delay(
                image_uuid=str(image.uuid),
                art_type=art_type
            )
            return Response({
                'status': 'success',
                'message': 'SBOM generation scheduled successfully'
            })
        except Exception as e:
            image.scan_status = 'error'
            image.save()
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def sbom(self, request, uuid=None):
        image = self.get_object()
        if image.sbom_data:
            return Response(image.sbom_data)
        return Response({'error': 'No SBOM data available.'}, status=404)

    @action(detail=True, methods=['get'])
    def grype(self, request, uuid=None):
        image = self.get_object()
        if image.grype_data:
            return Response(image.grype_data)
        return Response({'error': 'No Grype data available.'}, status=404)

    @action(detail=True, methods=['get'], url_path='components')
    def components(self, request, uuid=None):
        """
        Paginated list of component versions for a given image, with search and ordering support.
        """
        image = self.get_object()
        # Get all component versions linked to this image, with their components
        component_versions = image.component_versions.select_related('component').annotate(
            vulnerabilities_count=Count('vulnerabilities', distinct=True),
            images_count=Count('images', distinct=True),
        ).all()

        # Search
        search = request.query_params.get('search')
        if search:
            component_versions = component_versions.filter(
                Q(version__icontains=search) |
                Q(component__name__icontains=search) |
                Q(component__type__icontains=search)
            )

        # Ordering
        ordering = request.query_params.get('ordering')
        if ordering:
            # Support ordering by version, component name, or type
            ordering_map = {
                'version': 'version',
                '-version': '-version',
                'name': 'component__name',
                '-name': '-component__name',
                'type': 'component__type',
                '-type': '-component__type',
                'vulnerabilities_count': 'vulnerabilities_count',
                '-vulnerabilities_count': '-vulnerabilities_count',
                'used_count': 'images_count',
                '-used_count': '-images_count',
                'created_at': 'created_at',
                '-created_at': '-created_at',
                'updated_at': 'updated_at',
                '-updated_at': '-updated_at',
            }
            ordering_field = ordering_map.get(ordering, ordering)
            component_versions = component_versions.order_by(ordering_field)
        else:
            component_versions = component_versions.order_by('-created_at')

        # Pagination
        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(component_versions, request)
        items = list(page) if page is not None else list(component_versions[:paginator.page_size])
        prefetch_related_objects(
            items,
            'images',
            Prefetch(
                'componentversionvulnerability_set',
                queryset=ComponentVersionVulnerability.objects.select_related('vulnerability'),
            ),
            Prefetch(
                'locations',
                queryset=ComponentLocation.objects.select_related('image'),
            ),
        )
        serializer = ComponentVersionSerializer(items, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='rescan-grype')
    def rescan_grype(self, request, uuid=None):
        """
        Re-analyze SBOM for this image using Grype.
        """
        image = self.get_object()
        if not image.sbom_data:
            return Response({'error': 'No SBOM data available for this image.'}, status=400)
        if image.scan_status in ['in_process', 'pending']:
            return Response(
                {'error': 'Image is already being scanned or queued for scanning'},
                status=status.HTTP_409_CONFLICT
            )
        try:
            image.scan_status = 'pending'
            image.save(update_fields=['scan_status', 'updated_at'])
            from .tasks import scan_image_with_grype
            scan_image_with_grype.delay(str(image.uuid))
            return Response({'status': 'success', 'message': 'Grype scan scheduled successfully'})
        except Exception as e:
            image.scan_status = 'error'
            image.save(update_fields=['scan_status', 'updated_at'])
            return Response({'error': str(e)}, status=500)

    @action(detail=True, methods=['get'], url_path='component-locations')
    def component_locations(self, request, uuid=None):
        """
        Get detailed location information for all components in an image.
        """
        image = self.get_object()
        
        # Get all component locations for this image
        locations = ComponentLocation.objects.filter(
            image=image
        ).select_related('component_version', 'component_version__component')
        
        # Group by component version
        component_locations = {}
        for location in locations:
            component_version = location.component_version
            component_key = f"{component_version.component.name}:{component_version.version}"
            
            if component_key not in component_locations:
                component_locations[component_key] = {
                    'component_name': component_version.component.name,
                    'component_version': component_version.version,
                    'component_type': component_version.component.type,
                    'purl': component_version.purl,
                    'cpes': component_version.cpes,
                    'locations': []
                }
            
            component_locations[component_key]['locations'].append({
                'path': location.path,
                'layer_id': location.layer_id,
                'access_path': location.access_path,
                'evidence_type': location.evidence_type,
                'annotations': location.annotations
            })
        
        return Response({
            'image_uuid': str(image.uuid),
            'image_name': image.name,
            'component_locations': list(component_locations.values())
        })

class ComponentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Component.objects.all()
    filterset_fields = ['name', 'type']
    search_fields = ['name', 'type']
    ordering_fields = ['name', 'type', 'created_at', 'updated_at']
    pagination_class = CustomPageNumberPagination
    lookup_field = 'uuid'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'retrieve':
            qs = qs.annotate(
                _total_images=Count('versions__images', distinct=True),
                _versions_count=Count('versions', distinct=True)
            )
        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return ComponentListSerializer
        elif self.action == 'retrieve':
            return ComponentDetailOptimizedSerializer
        return ComponentSerializer

    @action(detail=True, methods=['get'])
    def versions(self, request, uuid=None):
        component = self.get_object()
        versions = component.versions.annotate(
            vulnerabilities_count=Count('vulnerabilities', distinct=True),
            images_count=Count('images', distinct=True)
        ).all().order_by('-version')
        page = self.paginate_queryset(versions)
        if page is not None:
            serializer = ComponentVersionOptimizedSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = ComponentVersionOptimizedSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def locations(self, request, uuid=None):
        """
        Get location information for all versions of this component.
        """
        component = self.get_object()
        
        locations = ComponentLocation.objects.filter(
            component_version__component=component
        ).select_related('component_version', 'image').order_by('path', 'created_at')

        page = self.paginate_queryset(locations)
        items = page if page is not None else locations

        location_data = []
        for location in items:
            location_data.append({
                'component_version': {
                    'uuid': str(location.component_version.uuid),
                    'version': location.component_version.version,
                    'purl': location.component_version.purl,
                    'cpes': location.component_version.cpes
                },
                'image': {
                    'uuid': str(location.image.uuid),
                    'name': location.image.name
                },
                'path': location.path,
                'layer_id': location.layer_id,
                'access_path': location.access_path,
                'evidence_type': location.evidence_type,
                'annotations': location.annotations
            })

        payload = {
            'component_uuid': str(component.uuid),
            'component_name': component.name,
            'component_type': component.type,
            'locations': location_data
        }
        if page is not None:
            return self.get_paginated_response(payload)
        return Response(payload)

    @action(detail=True, methods=['get'])
    def vulnerabilities(self, request, uuid=None):
        """
        Get all vulnerabilities for this component across all versions.
        """
        component = self.get_object()
        
        vulnerabilities = Vulnerability.objects.filter(
            component_versions__component=component
        ).select_related('details').distinct().order_by('-created_at')

        page = self.paginate_queryset(vulnerabilities)
        if page is not None:
            serializer = VulnerabilitySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = VulnerabilitySerializer(vulnerabilities, many=True)
        return Response(serializer.data)

class ComponentVersionViewSet(BaseViewSet):
    queryset = ComponentVersion.objects.all()
    serializer_class = ComponentVersionSerializer
    filterset_fields = ['component', 'images', 'vulnerabilities']
    search_fields = ['version', 'component__name']
    ordering_fields = ['version', 'created_at', 'updated_at', 'vulnerabilities_count', 'used_count', 'images_count']

    def get_queryset(self):
        qs = super().get_queryset()
        image_filter = self.request.query_params.get('images')
        if self.action == 'retrieve':
            qs = qs.select_related('component').annotate(
                vulnerabilities_count=Count('vulnerabilities', distinct=True),
                images_count=Count('images', distinct=True),
                locations_count=Count('locations', distinct=True)
            )
        elif self.action == 'list':
            qs = qs.select_related('component').annotate(
                vulnerabilities_count=Count('vulnerabilities', distinct=True),
                images_count=Count('images', distinct=True)
            )
            if image_filter:
                context_queryset = ImageComponentVersionContext.objects.filter(
                    image_id=image_filter,
                    component_version=OuterRef('pk'),
                )
                qs = qs.annotate(
                    dependency_scope=Subquery(context_queryset.values('dependency_scope')[:1]),
                    dependency_depth=Subquery(
                        context_queryset.values('dependency_depth')[:1],
                        output_field=IntegerField(),
                    ),
                    immediate_parent_name=Subquery(context_queryset.values('immediate_parent_name')[:1]),
                    immediate_parent_version=Subquery(context_queryset.values('immediate_parent_version')[:1]),
                    direct_introducer_name=Subquery(context_queryset.values('direct_introducer_name')[:1]),
                    direct_introducer_version=Subquery(context_queryset.values('direct_introducer_version')[:1]),
                    package_scope=Subquery(context_queryset.values('package_scope')[:1]),
                    package_arch=Subquery(context_queryset.values('package_arch')[:1]),
                    package_distro=Subquery(context_queryset.values('package_distro')[:1]),
                    package_repo=Subquery(context_queryset.values('package_repo')[:1]),
                    package_channel=Subquery(context_queryset.values('package_channel')[:1]),
                    source_package=Subquery(context_queryset.values('source_package')[:1]),
                    source_package_version=Subquery(context_queryset.values('source_package_version')[:1]),
                    cataloger=Subquery(context_queryset.values('cataloger')[:1]),
                    metadata_type=Subquery(context_queryset.values('metadata_type')[:1]),
                )
        else:
            qs = qs.annotate(vulnerabilities_count=Count('vulnerabilities', distinct=True))
        return qs.order_by('component__name', 'version', 'created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return ComponentVersionListSerializer
        elif self.action == 'retrieve':
            return ComponentVersionUltraOptimizedSerializer
        return ComponentVersionSerializer

    def list(self, request, *args, **kwargs):
        image_uuid = request.query_params.get('images')
        if not image_uuid:
            return super().list(request, *args, **kwargs)

        ordering = request.query_params.get('ordering')
        metric_ordering = _component_version_list_needs_metric_ordering(ordering)
        queryset = (
            _build_metric_sorted_image_component_versions_queryset(image_uuid)
            if metric_ordering
            else _build_lightweight_image_component_versions_queryset(image_uuid)
        )

        component_filter = request.query_params.get('component')
        if component_filter:
            queryset = queryset.filter(component_id=component_filter)

        vulnerability_filter = request.query_params.get('vulnerabilities')
        if vulnerability_filter:
            queryset = queryset.filter(vulnerabilities__uuid=vulnerability_filter)

        search = (request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(version__icontains=search)
                | Q(component__name__icontains=search)
                | Q(component__type__icontains=search)
            )

        queryset = _apply_image_component_version_ordering(queryset, ordering)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(queryset, request)
        items = list(page) if page is not None else list(queryset[:paginator.page_size])
        _hydrate_image_component_versions_page(items, image_uuid)

        serializer = ComponentVersionListSerializer(items, many=True)
        if page is not None:
            return paginator.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def images(self, request, uuid=None):
        """Get images for this component version - lightweight endpoint"""
        version = self.get_object()
        images = version.images.all().values('uuid', 'name', 'digest')[:50]  # Limit to 50 images
        
        return Response({
            'version_uuid': str(version.uuid),
            'images': list(images),
            'total_count': version.images.count()
        })

    @action(detail=True, methods=['get'])
    def vulnerabilities(self, request, uuid=None):
        """Get vulnerabilities for this component version with pagination"""
        version = self.get_object()
        vulnerabilities_qs = version.vulnerabilities.all()
        
        # Add pagination
        page = self.paginate_queryset(vulnerabilities_qs)
        if page is not None:
            serializer = VulnerabilityShortSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Fallback for non-paginated response (limit to 100)
        vulnerabilities_qs = vulnerabilities_qs[:100]
        serializer = VulnerabilityShortSerializer(vulnerabilities_qs, many=True)
        return Response({
            'results': serializer.data,
            'total_count': version.vulnerabilities.count()
        })

    @action(detail=True, methods=['get'])
    def locations(self, request, uuid=None):
        """
        Get location information for this specific component version.
        Supports optional 'image' query parameter to filter by specific image.
        """
        version = self.get_object()
        
        # Get all component locations for this version with pagination
        locations_qs = ComponentLocation.objects.filter(
            component_version=version
        ).select_related('image')
        
        # Filter by image if specified
        image_uuid = request.query_params.get('image')
        if image_uuid:
            locations_qs = locations_qs.filter(image__uuid=image_uuid)
        
        # Order the queryset to avoid pagination warnings
        locations_qs = locations_qs.order_by('path', 'created_at')
        
        # Add pagination
        page = self.paginate_queryset(locations_qs)
        if page is not None:
            # Format location data for paginated response
            location_data = []
            for location in page:
                location_data.append({
                    'image': {
                        'uuid': str(location.image.uuid),
                        'name': location.image.name
                    },
                    'path': location.path,
                    'layer_id': location.layer_id,
                    'access_path': location.access_path,
                    'evidence_type': location.evidence_type,
                    'annotations': location.annotations
                })
            
            return self.get_paginated_response({
                'version_uuid': str(version.uuid),
                'version': version.version,
                'component_name': version.component.name,
                'filtered_by_image': image_uuid,
                'locations': location_data
            })
        
        # Fallback for non-paginated response (limit to 100)
        locations_qs = locations_qs[:100]
        location_data = []
        for location in locations_qs:
            location_data.append({
                'image': {
                    'uuid': str(location.image.uuid),
                    'name': location.image.name
                },
                'path': location.path,
                'layer_id': location.layer_id,
                'access_path': location.access_path,
                'evidence_type': location.evidence_type,
                'annotations': location.annotations
            })
        
        return Response({
            'version_uuid': str(version.uuid),
            'version': version.version,
            'component_name': version.component.name,
            'filtered_by_image': image_uuid,
            'locations': location_data,
            'total_count': locations_qs.count()
        })

class ReleaseViewSet(BaseViewSet):
    """
    API endpoint for managing releases.
    
    list:
    Return a list of all releases.
    
    retrieve:
    Return the details of a specific release.
    
    create:
    Create a new release.
    
    update:
    Update an existing release.
    
    partial_update:
    Partially update an existing release.
    
    destroy:
    Delete a release.
    """
    queryset = Release.objects.all()
    serializer_class = ReleaseSerializer
    search_fields = ['name', 'description']
    ordering_fields = [
        'name',
        'description',
        'created_at',
        'tag_count',
        'critical_vulnerabilities',
        'high_vulnerabilities',
    ]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in {'list', 'retrieve'}:
            queryset = queryset.annotate(
                repository_tags_count=Count('repository_tags', distinct=True),
            )
        return queryset

    def _get_with_stats_queryset(self):
        return Release.objects.annotate(
            tag_count=Count('repository_tags', distinct=True),
            critical_vulnerabilities=Count(
                'repository_tags__repository_tag__images__component_versions__componentversionvulnerability__vulnerability',
                filter=Q(
                    repository_tags__repository_tag__images__component_versions__componentversionvulnerability__vulnerability__severity='CRITICAL'
                ),
                distinct=True,
            ),
            high_vulnerabilities=Count(
                'repository_tags__repository_tag__images__component_versions__componentversionvulnerability__vulnerability',
                filter=Q(
                    repository_tags__repository_tag__images__component_versions__componentversionvulnerability__vulnerability__severity='HIGH'
                ),
                distinct=True,
            ),
        )
    
    @action(detail=False, methods=['get'])
    def with_stats(self, request):
        """Get all releases with repository tag counts and vulnerability stats"""
        releases = self.filter_queryset(self._get_with_stats_queryset())

        def serialize_release(release):
            return {
                'uuid': str(release.uuid),
                'name': release.name,
                'description': release.description,
                'tag_count': getattr(release, 'tag_count', 0) or 0,
                'critical_vulnerabilities': getattr(release, 'critical_vulnerabilities', 0) or 0,
                'high_vulnerabilities': getattr(release, 'high_vulnerabilities', 0) or 0,
                'created_at': release.created_at,
            }

        page = self.paginate_queryset(releases)
        if page is not None:
            return self.get_paginated_response([serialize_release(release) for release in page])

        return Response([serialize_release(release) for release in releases])

    @method_decorator(cache_page(300))
    @action(detail=False, methods=['get'])
    def names(self, request):
        """Get only release names and UUIDs for validation purposes"""
        releases = Release.objects.values('uuid', 'name').order_by('name')
        return Response(list(releases))

    @action(detail=True, methods=['get'])
    def contents(self, request, uuid=None):
        """Return all repository tags included in the release with scan status summary."""
        release = self.get_object()
        tags = list(
            RepositoryTag.objects.filter(releases__release=release)
            .select_related('repository')
            .order_by('repository__name', '-updated_at', 'tag')
        )
        _attach_repository_tag_summary_data(tags)
        serialized_tags, summary = _build_release_repository_tag_payload(tags)
        analytics = build_release_delta_summary(release)

        return Response({
            'release': {
                'uuid': str(release.uuid),
                'name': release.name,
                'description': release.description,
                'created_at': release.created_at,
            },
            'summary': summary,
            'analytics': analytics['current'],
            'delta_from_previous_release': {
                'previous_release': analytics['previous_release'],
                **analytics['delta'],
            },
            'tags': serialized_tags,
        })

    @action(detail=True, methods=['post'], url_path='scan-unscanned')
    def scan_unscanned(self, request, uuid=None):
        """Queue processing only for release tags that are not fully scanned yet."""
        from .tasks import process_single_tag

        release = self.get_object()
        tags = list(
            RepositoryTag.objects.filter(releases__release=release)
            .select_related('repository')
            .order_by('repository__name', 'tag')
        )
        _attach_repository_tag_summary_data(tags)

        queued_tag_uuids = []
        already_running_tag_uuids = []
        skipped_success_tag_uuids = []

        for tag in tags:
            total_images = getattr(tag, 'total_images_count', 0) or 0
            pending_images = getattr(tag, 'pending_images_count', 0) or 0
            in_process_images = getattr(tag, 'in_process_images_count', 0) or 0
            error_images = getattr(tag, 'error_images_count', 0) or 0
            success_images = getattr(tag, 'success_images_count', 0) or 0
            effective_status = resolve_repository_tag_processing_status(
                getattr(tag, 'processing_status', 'none'),
                total_images,
                pending_images,
                in_process_images,
                error_images,
                success_images,
            )

            if effective_status == 'success':
                skipped_success_tag_uuids.append(str(tag.uuid))
                continue
            if effective_status in ['pending', 'in_process']:
                already_running_tag_uuids.append(str(tag.uuid))
                continue

            tag.processing_status = 'pending'
            tag.save(update_fields=['processing_status', 'updated_at'])
            process_single_tag.apply_async(args=[str(tag.uuid)], task_name="Process Single Tag")
            queued_tag_uuids.append(str(tag.uuid))

        return Response({
            'status': 'success',
            'message': (
                f'Queued {len(queued_tag_uuids)} release tag(s) for scanning; '
                f'{len(already_running_tag_uuids)} already running, '
                f'{len(skipped_success_tag_uuids)} already complete'
            ),
            'summary': {
                'total_tags_seen': len(tags),
                'queued_tags': len(queued_tag_uuids),
                'already_running_tags': len(already_running_tag_uuids),
                'already_scanned_tags': len(skipped_success_tag_uuids),
            },
            'queued_tag_uuids': queued_tag_uuids,
            'already_running_tag_uuids': already_running_tag_uuids,
            'already_scanned_tag_uuids': skipped_success_tag_uuids,
        })


class VulnerabilityViewSet(BaseViewSet):
    """
    API endpoint for managing vulnerabilities.
    
    list:
    Return a list of all vulnerabilities.
    
    retrieve:
    Return the details of a specific vulnerability.
    
    create:
    Create a new vulnerability.
    
    update:
    Update an existing vulnerability.
    
    partial_update:
    Partially update an existing vulnerability.
    
    destroy:
    Delete a vulnerability.
    
    severity_stats:
    Return statistics about vulnerabilities grouped by severity.
    
    update_details:
    Update detailed information for a vulnerability from external sources.
    
    exploit_stats:
    Return statistics about vulnerabilities with exploit information.
    """
    queryset = Vulnerability.objects.all()
    serializer_class = VulnerabilitySerializer
    filterset_fields = ['severity', 'vulnerability_type']
    search_fields = ['vulnerability_id']
    ordering_fields = [
        'vulnerability_id',
        'vulnerability_type',
        'severity',
        'epss',
        'created_at',
        'updated_at',
        'cisa_kev',
        'exploit_available',
        'has_details',
    ]

    def get_queryset(self):
        queryset = Vulnerability.objects.select_related('details').all()

        # Add filters for exploit information
        exploit_available = self.request.query_params.get('exploit_available', None)
        if exploit_available is not None:
            exploit_available = exploit_available.lower() == 'true'
            if exploit_available:
                queryset = queryset.filter(details__exploit_available=True)
            else:
                queryset = queryset.filter(
                    Q(details__exploit_available=False) | Q(details__isnull=True)
                )
        
        # Add filter for vulnerabilities with details
        has_details = self.request.query_params.get('has_details', None)
        if has_details is not None:
            has_details = has_details.lower() == 'true'
            if has_details:
                queryset = queryset.filter(details__isnull=False)
            else:
                queryset = queryset.filter(details__isnull=True)
        
        # Add filter for CISA KEV vulnerabilities
        cisa_kev = self.request.query_params.get('cisa_kev', None)
        if cisa_kev is not None:
            cisa_kev = cisa_kev.lower() == 'true'
            if cisa_kev:
                queryset = queryset.filter(details__cisa_kev_known_exploited=True)
            else:
                queryset = queryset.filter(
                    Q(details__cisa_kev_known_exploited=False) | Q(details__isnull=True)
                )
        
        # Add filter for ransomware vulnerabilities
        ransomware = self.request.query_params.get('ransomware', None)
        if ransomware is not None:
            ransomware = ransomware.lower() == 'true'
            if ransomware:
                queryset = queryset.filter(details__cisa_kev_ransomware_use='Known')
            else:
                queryset = queryset.filter(
                    Q(details__cisa_kev_ransomware_use__in=['Unknown', 'None']) | Q(details__isnull=True)
                )
        
        return queryset

    def filter_queryset(self, queryset):
        ordering = self.request.query_params.get('ordering')
        custom_ordering_map = {
            'severity': '_severity_order',
            '-severity': '-_severity_order',
            'cisa_kev': '_cisa_kev_order',
            '-cisa_kev': '-_cisa_kev_order',
            'exploit_available': '_exploit_available_order',
            '-exploit_available': '-_exploit_available_order',
            'has_details': '_has_details_order',
            '-has_details': '-_has_details_order',
        }
        if ordering in custom_ordering_map:
            # Apply filter and search backends first (skip OrderingFilter)
            for backend in self.filter_backends:
                if backend == filters.OrderingFilter:
                    continue
                queryset = backend().filter_queryset(self.request, queryset, self)
            # Custom severity order: Critical > High > Medium > Low > Unknown.
            severity_order = Case(
                When(severity='CRITICAL', then=Value(0)),
                When(severity='HIGH', then=Value(1)),
                When(severity='MEDIUM', then=Value(2)),
                When(severity='LOW', then=Value(3)),
                When(severity='UNKNOWN', then=Value(4)),
                default=Value(5),
                output_field=IntegerField()
            )
            queryset = queryset.annotate(
                _severity_order=severity_order,
                _cisa_kev_order=Case(
                    When(details__cisa_kev_known_exploited=True, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
                _exploit_available_order=Case(
                    When(details__exploit_available=True, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
                _has_details_order=Case(
                    When(details__isnull=False, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
            )
            queryset = queryset.order_by(custom_ordering_map[ordering], 'vulnerability_id')
            return queryset
        return super().filter_queryset(queryset)

    def get_serializer_class(self):
        if self.action == 'list':
            return VulnerabilityListSerializer
        if self.action == 'retrieve':
            include_analytics = self.request.query_params.get('include_analytics', '1').lower()
            if include_analytics in {'0', 'false', 'no'}:
                return VulnerabilityBaseDetailSerializer
            return VulnerabilityDetailSerializer
        return VulnerabilitySerializer

    @action(detail=True, methods=['get'], url_path='risk-prioritization')
    def risk_prioritization(self, request, uuid=None):
        vulnerability = self.get_object()
        payload = build_vulnerability_detail_analytics(vulnerability)
        serializer = VulnerabilityRiskPrioritizationSerializer(payload)
        return Response(serializer.data)

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'])
    def severity_stats(self, request):
        """Return statistics about vulnerabilities grouped by severity."""
        stats = Vulnerability.objects.values('severity').annotate(
            count=Count('id')
        ).order_by('severity')
        
        return Response({
            'severity_stats': list(stats),
            'total_vulnerabilities': Vulnerability.objects.count()
        })

    @action(detail=False, methods=['post'], url_path='cleanup-orphaned')
    def cleanup_orphaned(self, request):
        """
        Delete vulnerabilities that have no associated component versions (and thus no images).
        Use after deleting images to keep statistics accurate.
        """
        orphaned = Vulnerability.objects.annotate(
            n=Count('component_versions')
        ).filter(n=0)
        count = orphaned.count()
        orphaned.delete()
        return Response({
            'deleted': count,
            'message': f'Removed {count} orphaned vulnerability(ies) with no linked components or images.'
        })

    @action(detail=True, methods=['post'])
    def update_details(self, request, uuid=None):
        """
        Update detailed information for a vulnerability from external sources.
        """
        from .tasks import update_vulnerability_details
        
        vulnerability = self.get_object()
        
        # Trigger the update task
        task = update_vulnerability_details.delay(str(vulnerability.uuid))
        
        return Response({
            'status': 'task_started',
            'task_id': task.id,
            'vulnerability_id': vulnerability.vulnerability_id,
            'message': 'Vulnerability details update started'
        })

    @action(detail=False, methods=['get'])
    def exploit_stats(self, request):
        """Return statistics about vulnerabilities with exploit information."""
        total_vulns = Vulnerability.objects.count()
        vulns_with_details = Vulnerability.objects.filter(details__isnull=False).count()
        vulns_with_exploits = Vulnerability.objects.filter(details__exploit_available=True).count()
        vulns_with_public_exploits = Vulnerability.objects.filter(details__exploit_public=True).count()
        vulns_with_verified_exploits = Vulnerability.objects.filter(details__exploit_verified=True).count()
        
        return Response({
            'total_vulnerabilities': total_vulns,
            'vulnerabilities_with_details': vulns_with_details,
            'vulnerabilities_with_exploits': vulns_with_exploits,
            'vulnerabilities_with_public_exploits': vulns_with_public_exploits,
            'vulnerabilities_with_verified_exploits': vulns_with_verified_exploits,
            'percentage_with_details': round((vulns_with_details / total_vulns * 100), 2) if total_vulns > 0 else 0,
            'percentage_with_exploits': round((vulns_with_exploits / total_vulns * 100), 2) if total_vulns > 0 else 0
        })

    @action(detail=False, methods=['post'])
    def bulk_update_details(self, request):
        """
        Update detailed information for all vulnerabilities.
        """
        from .tasks import update_all_vulnerability_details
        
        # Trigger the bulk update task
        task = update_all_vulnerability_details.delay()
        
        return Response({
            'status': 'task_started',
            'task_id': task.id,
            'message': 'Bulk vulnerability details update started'
        })

    @action(detail=False, methods=['post'])
    def update_critical_details(self, request):
        """
        Update detailed information for critical and high severity vulnerabilities.
        """
        from .tasks import update_critical_vulnerability_details
        
        # Trigger the critical update task
        task = update_critical_vulnerability_details.delay()
        
        return Response({
            'status': 'task_started',
            'task_id': task.id,
            'message': 'Critical vulnerability details update started'
        })

    @action(detail=True, methods=['get'])
    def images(self, request, uuid=None):
        """
        Get all images that contain this vulnerability.
        """
        vulnerability = get_object_or_404(Vulnerability, uuid=uuid)

        image_ids_subquery = ComponentVersionVulnerability.objects.filter(
            vulnerability=vulnerability
        ).values('component_version__images__pk')

        images = _build_vulnerability_image_queryset(
            Image.objects.filter(pk__in=image_ids_subquery),
            vulnerability,
        )

        search = (request.query_params.get('search') or '').strip()
        if search:
            images = images.filter(
                Q(name__icontains=search)
                | Q(digest__icontains=search)
                | Q(repository_tags__tag__icontains=search)
                | Q(repository_tags__repository__name__icontains=search)
            )

        ordering = VULNERABILITY_IMAGE_ORDERING_MAP.get(
            request.query_params.get('ordering'),
            'name',
        )
        images = images.distinct().order_by(ordering, 'uuid')

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(images, request)

        if page is not None:
            serializer = VulnerabilityAffectedImageSerializer(
                page,
                many=True,
                context={'request': request, 'vulnerability': vulnerability},
            )
            return paginator.get_paginated_response(serializer.data)

        serializer = VulnerabilityAffectedImageSerializer(
            images,
            many=True,
            context={'request': request, 'vulnerability': vulnerability},
        )
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def components(self, request, uuid=None):
        """
        Get all component versions that contain this vulnerability.
        """
        vulnerability = self.get_object()
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Fetching components for vulnerability: {vulnerability.vulnerability_id}")
        
        # Get component versions that have this vulnerability with proper ordering and annotations
        component_versions = ComponentVersion.objects.filter(
            vulnerabilities=vulnerability
        ).select_related('component').annotate(
            vulnerabilities_count=models.Count('vulnerabilities', distinct=True),
            images_count=models.Count('images', distinct=True),
        ).order_by(
            'component__name', 'version', 'created_at'
        )
        
        # Debug logging
        logger.info(f"Found {component_versions.count()} component versions")
        for cv in component_versions:
            logger.info(f"Component: {cv.component.name} {cv.version}")
        
        # Apply pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(component_versions, request)
        
        if page is not None:
            serializer = ComponentVersionListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = ComponentVersionListSerializer(component_versions, many=True)
        return Response(serializer.data)


class VulnerabilityDetailsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing vulnerability details.
    
    list:
    Return a list of all vulnerability details.
    
    retrieve:
    Return the details of a specific vulnerability detail record.
    """
    permission_classes = [IsAuthenticated]
    queryset = VulnerabilityDetails.objects.all()
    serializer_class = VulnerabilityDetailsSerializer
    filterset_fields = ['exploit_available', 'exploit_public', 'exploit_verified', 'data_source']
    ordering_fields = ['last_updated', 'cve_details_score']
    ordering = ['-last_updated']

    @action(detail=False, methods=['get'])
    def exploit_summary(self, request):
        """Return summary of exploit information."""
        total_details = VulnerabilityDetails.objects.count()
        with_exploits = VulnerabilityDetails.objects.filter(exploit_available=True).count()
        with_public_exploits = VulnerabilityDetails.objects.filter(exploit_public=True).count()
        with_verified_exploits = VulnerabilityDetails.objects.filter(exploit_verified=True).count()
        
        return Response({
            'total_details': total_details,
            'with_exploits': with_exploits,
            'with_public_exploits': with_public_exploits,
            'with_verified_exploits': with_verified_exploits,
            'percentage_with_exploits': round((with_exploits / total_details * 100), 2) if total_details > 0 else 0
        })

class HasACRRegistryView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = HasACRRegistryResponseSerializer

    def get(self, request):
        exists = ContainerRegistry.objects.filter(provider='acr').exists()
        return Response({'has_acr': exists})

class ListACRRegistriesView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ListACRRegistriesResponseSerializer

    def get(self, request):
        registries = ContainerRegistry.objects.filter(provider='acr')
        data = [
            {
                'uuid': str(r.uuid),
                'name': r.name,
                'api_url': r.api_url
            }
            for r in registries
        ]
        return Response({'registries': data})


class ListRegistriesView(GenericAPIView):
    """List container registries by provider (acr or jfrog). Used by frontend for ACR and Artifactory."""
    permission_classes = [IsAuthenticated]
    serializer_class = ListACRRegistriesResponseSerializer

    def get(self, request):
        provider = request.query_params.get('provider', 'acr')
        if provider not in ('acr', 'jfrog', 'ecr'):
            return Response({'registries': []})
        registries = ContainerRegistry.objects.filter(provider=provider)
        data = [
            {
                'uuid': str(r.uuid),
                'name': r.name,
                'api_url': r.api_url,
                'image_fallback_repositories': r.image_fallback_repositories or [],
            }
            for r in registries
        ]
        return Response({'registries': data})


class RegistryDetailView(GenericAPIView):
    """Get or update a single container registry (supports PATCH for fallback repos)."""
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _registry_response(registry):
        return {
            'uuid': str(registry.uuid),
            'name': registry.name,
            'api_url': registry.api_url,
            'image_fallback_repositories': registry.image_fallback_repositories or [],
        }

    def get(self, request, uuid):
        registry = ContainerRegistry.objects.filter(uuid=uuid).first()
        if not registry:
            return Response({'error': 'Registry not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(self._registry_response(registry))

    def patch(self, request, uuid):
        registry = ContainerRegistry.objects.filter(uuid=uuid).first()
        if not registry:
            return Response({'error': 'Registry not found'}, status=status.HTTP_404_NOT_FOUND)
        entries = request.data.get('image_fallback_repositories')
        if entries is not None:
            if not isinstance(entries, list):
                return Response(
                    {'image_fallback_repositories': 'Must be a list of {url, name, registry_uuid} entries.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            valid_reg_uuids = set(
                str(u) for u in ContainerRegistry.objects.values_list('uuid', flat=True)
            )
            cleaned = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                url = (entry.get('url') or '').strip()
                name = (entry.get('name') or '').strip()
                reg_uuid = str(entry.get('registry_uuid') or '').strip()
                if not url or not name or reg_uuid not in valid_reg_uuids:
                    continue
                cleaned.append({'url': url, 'name': name, 'registry_uuid': reg_uuid})
            registry.image_fallback_repositories = cleaned
            registry.save(update_fields=['image_fallback_repositories'])
        return Response(self._registry_response(registry))

class StatsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = StatsResponseSerializer

    def list(self, request):
        data = {
            'repositories': Repository.objects.count(),
            'images': Image.objects.count(),
            'vulnerabilities': Vulnerability.objects.count(),
            'components': Component.objects.count(),
        }
        return Response(data)

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'])
    def dashboard_metrics(self, request):
        """Get comprehensive dashboard metrics with optimized queries"""
        return Response({
            **_build_dashboard_overview_payload(),
            **_build_dashboard_visualizations_payload(),
            **_build_dashboard_top_lists_payload(),
            **_build_dashboard_activity_payload(),
            **_build_dashboard_threat_intel_payload(),
            **_build_dashboard_analytics_payload(),
            **_build_dashboard_root_causes_payload(),
            **_build_dashboard_base_lineage_root_causes_payload(),
        })

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='dashboard-overview')
    def dashboard_overview(self, request):
        return Response(_build_dashboard_overview_payload())

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='dashboard-visualizations')
    def dashboard_visualizations(self, request):
        return Response(_build_dashboard_visualizations_payload())

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='dashboard-top-lists')
    def dashboard_top_lists(self, request):
        return Response(_build_dashboard_top_lists_payload())

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='dashboard-activity')
    def dashboard_activity(self, request):
        return Response(_build_dashboard_activity_payload())

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='dashboard-threat-intel')
    def dashboard_threat_intel(self, request):
        return Response(_build_dashboard_threat_intel_payload())

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='dashboard-analytics')
    def dashboard_analytics(self, request):
        return Response(_build_dashboard_analytics_payload())

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='dashboard-root-causes')
    def dashboard_root_causes(self, request):
        return Response({
            **_build_dashboard_root_causes_payload(),
            **_build_dashboard_base_lineage_root_causes_payload(),
        })

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='recent-activities')
    def recent_activities(self, request):
        """Get paginated recent activities for the last 30 days."""
        thirty_days_ago = timezone.now() - timedelta(days=30)
        paginator = CustomPageNumberPagination()
        requested_types = request.query_params.getlist('type')
        if not requested_types:
            single_type = request.query_params.get('type')
            if single_type:
                requested_types = [single_type]

        activities = _build_recent_activity_queryset(
            thirty_days_ago,
            activity_types=requested_types or ['scan', 'vulnerability'],
        )
        page = paginator.paginate_queryset(activities, request)
        results = list(page if page is not None else activities)
        for activity in results:
            activity['type'] = activity.pop('activity_type')
            activity['severity'] = activity.pop('activity_severity')
            activity['status'] = activity.pop('activity_status')

        if page is not None:
            return paginator.get_paginated_response(results)
        return Response(results)

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='weekly-threat-intel')
    def weekly_threat_intel(self, request):
        """Get paginated weekly threat-intel rows for the current week."""
        selected_type = request.query_params.get('type', 'all')
        summary = get_dashboard_weekly_threat_intel(limit=None)
        rows = _build_weekly_threat_intel_rows(summary, selected_type)

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(rows, request)
        results = list(page if page is not None else rows)

        if page is not None:
            response = paginator.get_paginated_response(results)
            response.data['period_start'] = summary.get('period_start')
            response.data['period_end'] = summary.get('period_end')
            response.data['selected_type'] = selected_type
            return response

        return Response({
            'count': len(results),
            'next': None,
            'previous': None,
            'period_start': summary.get('period_start'),
            'period_end': summary.get('period_end'),
            'selected_type': selected_type,
            'results': results,
        })

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='shared-root-causes')
    def shared_root_causes(self, request):
        from .models import SharedRootCauseAnalyticsSnapshotRow

        search = (request.query_params.get('search') or '').strip()
        component_type = (request.query_params.get('component_type') or 'all').strip().lower()
        scope = (request.query_params.get('scope') or 'cross_repository').strip().lower()
        fixability = (request.query_params.get('fixability') or 'all').strip().lower()
        latest_snapshot = get_latest_root_cause_analytics_snapshots().get('shared')
        snapshot_generated_at = latest_snapshot.updated_at.isoformat() if latest_snapshot else None

        if latest_snapshot:
            queryset = SharedRootCauseAnalyticsSnapshotRow.objects.filter(
                snapshot=latest_snapshot,
            ).defer('repositories_preview', 'vulnerabilities_preview')

            if search:
                queryset = queryset.filter(
                    Q(component_name__icontains=search)
                    | Q(version__icontains=search)
                    | Q(purl__icontains=search)
                )

            if component_type not in {'', 'all'}:
                queryset = queryset.filter(component_type__iexact=component_type)

            if scope == 'cross_repository':
                queryset = queryset.filter(affected_repositories_count__gt=1)
            elif scope == 'single_repository':
                queryset = queryset.filter(affected_repositories_count__lte=1)

            if fixability == 'fixable_now':
                queryset = queryset.filter(max_fix_priority__gte=3)
            elif fixability == 'fix_exists_but_not_in_repo':
                queryset = queryset.filter(max_fix_priority=2)
            elif fixability == 'no_fix':
                queryset = queryset.filter(max_fix_priority=1)
            elif fixability == 'fix_unknown':
                queryset = queryset.filter(max_fix_priority__lte=0)

            ordered = _apply_root_cause_ordering(
                queryset,
                request.query_params.get('ordering', '-weighted_risk_score'),
                ordering_map=ROOT_CAUSE_SNAPSHOT_ORDERING_MAP,
            )
        else:
            queryset = build_shared_root_cause_queryset()

            if search:
                queryset = queryset.filter(
                    Q(component__name__icontains=search)
                    | Q(version__icontains=search)
                    | Q(purl__icontains=search)
                )

            if component_type not in {'', 'all'}:
                queryset = queryset.filter(component__type__iexact=component_type)

            if scope == 'cross_repository':
                queryset = queryset.filter(affected_repositories_count__gt=1)
            elif scope == 'single_repository':
                queryset = queryset.filter(affected_repositories_count__lte=1)

            if fixability == 'fixable_now':
                queryset = queryset.filter(max_fix_priority__gte=3)
            elif fixability == 'fix_exists_but_not_in_repo':
                queryset = queryset.filter(max_fix_priority=2)
            elif fixability == 'no_fix':
                queryset = queryset.filter(max_fix_priority=1)
            elif fixability == 'fix_unknown':
                queryset = queryset.filter(max_fix_priority__lte=0)

            ordered = _apply_root_cause_ordering(
                queryset,
                request.query_params.get('ordering', '-weighted_risk_score'),
            )

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(ordered, request)
        component_versions = list(page) if page is not None else list(ordered)
        if latest_snapshot:
            serialized = SharedRootCauseSerializer(component_versions, many=True).data
        else:
            serialized = SharedRootCauseSerializer(
                _serialize_root_causes(component_versions, include_previews=False),
                many=True,
            ).data

        if page is not None:
            response = paginator.get_paginated_response(serialized)
            response.data['scope'] = scope
            response.data['component_type'] = component_type
            response.data['fixability'] = fixability
            response.data['snapshot_generated_at'] = snapshot_generated_at
            return response

        return Response({
            'count': len(serialized),
            'next': None,
            'previous': None,
            'scope': scope,
            'component_type': component_type,
            'fixability': fixability,
            'snapshot_generated_at': snapshot_generated_at,
            'results': serialized,
        })

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='shared-root-causes-preview')
    def shared_root_causes_preview(self, request):
        from .models import SharedRootCauseAnalyticsSnapshotRow
        from .models import ComponentVersion

        component_version_uuid = (request.query_params.get('component_version_uuid') or '').strip()
        if not component_version_uuid:
            return Response(
                {'detail': 'component_version_uuid query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        latest_snapshot = get_latest_root_cause_analytics_snapshots().get('shared')
        if latest_snapshot:
            snapshot_row = SharedRootCauseAnalyticsSnapshotRow.objects.filter(
                snapshot=latest_snapshot,
                component_version_uuid=component_version_uuid,
            ).first()
            if snapshot_row and (
                snapshot_row.repositories_preview or snapshot_row.vulnerabilities_preview
            ):
                return Response(SharedRootCausePreviewSerializer(snapshot_row).data)

        component_version = get_object_or_404(
            ComponentVersion.objects.select_related('component'),
            uuid=component_version_uuid,
        )
        serialized = SharedRootCausePreviewSerializer(
            _build_shared_root_cause_preview_payload(component_version)
        ).data
        return Response(serialized)

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='base-lineage-root-causes')
    def base_lineage_root_causes(self, request):
        from .models import BaseLineageRootCauseAnalyticsSnapshotRow

        search = (request.query_params.get('search') or '').strip()
        scope = (request.query_params.get('scope') or 'cross_repository').strip().lower()
        fixability = (request.query_params.get('fixability') or 'all').strip().lower()
        include_unknown = str(request.query_params.get('include_unknown', '0')).lower() in {'1', 'true', 'yes'}
        latest_snapshot = get_latest_root_cause_analytics_snapshots().get('base_lineage')
        snapshot_generated_at = latest_snapshot.updated_at.isoformat() if latest_snapshot else None

        if latest_snapshot:
            grouped_queryset = BaseLineageRootCauseAnalyticsSnapshotRow.objects.filter(
                snapshot=latest_snapshot,
            )

            if not include_unknown:
                grouped_queryset = grouped_queryset.exclude(lineage_label='unknown')

            if search:
                grouped_queryset = grouped_queryset.filter(
                    Q(lineage_label__icontains=search)
                )

            if scope == 'cross_repository':
                grouped_queryset = grouped_queryset.filter(affected_repositories_count__gt=1)
            elif scope == 'single_repository':
                grouped_queryset = grouped_queryset.filter(affected_repositories_count__lte=1)

            if fixability == 'fixable_now':
                grouped_queryset = grouped_queryset.filter(max_fix_priority__gte=3)
            elif fixability == 'fix_exists_but_not_in_repo':
                grouped_queryset = grouped_queryset.filter(max_fix_priority=2)
            elif fixability == 'no_fix':
                grouped_queryset = grouped_queryset.filter(max_fix_priority=1)
            elif fixability == 'fix_unknown':
                grouped_queryset = grouped_queryset.filter(max_fix_priority__lte=0)

            ordered = _apply_base_lineage_ordering(
                grouped_queryset,
                request.query_params.get('ordering', '-weighted_risk_score'),
                ordering_map=BASE_LINEAGE_SNAPSHOT_ORDERING_MAP,
            )
        else:
            lineage_members = build_base_lineage_image_queryset()

            if not include_unknown:
                lineage_members = lineage_members.exclude(lineage_label='unknown')

            if search:
                lineage_members = lineage_members.filter(
                    Q(lineage_label__icontains=search)
                    | Q(os_distro_name__icontains=search)
                    | Q(os_distro_version__icontains=search)
                )

            grouped_queryset = build_base_lineage_grouped_queryset(lineage_members)

            if scope == 'cross_repository':
                grouped_queryset = grouped_queryset.filter(affected_repositories_count__gt=1)
            elif scope == 'single_repository':
                grouped_queryset = grouped_queryset.filter(affected_repositories_count__lte=1)

            if fixability == 'fixable_now':
                grouped_queryset = grouped_queryset.filter(max_fix_priority__gte=3)
            elif fixability == 'fix_exists_but_not_in_repo':
                grouped_queryset = grouped_queryset.filter(max_fix_priority=2)
            elif fixability == 'no_fix':
                grouped_queryset = grouped_queryset.filter(max_fix_priority=1)
            elif fixability == 'fix_unknown':
                grouped_queryset = grouped_queryset.filter(max_fix_priority__lte=0)

            ordered = _apply_base_lineage_ordering(
                grouped_queryset,
                request.query_params.get('ordering', '-weighted_risk_score'),
            )

        paginator = CustomPageNumberPagination()
        page = paginator.paginate_queryset(ordered, request)
        grouped_rows = list(page) if page is not None else list(ordered)
        if latest_snapshot:
            serialized = BaseLineageRootCauseSerializer(grouped_rows, many=True).data
        else:
            serialized = BaseLineageRootCauseSerializer(
                _serialize_base_lineage_root_causes(grouped_rows, include_previews=False),
                many=True,
            ).data

        if page is not None:
            response = paginator.get_paginated_response(serialized)
            response.data['scope'] = scope
            response.data['fixability'] = fixability
            response.data['include_unknown'] = include_unknown
            response.data['snapshot_generated_at'] = snapshot_generated_at
            return response

        return Response({
            'count': len(serialized),
            'next': None,
            'previous': None,
            'scope': scope,
            'fixability': fixability,
            'include_unknown': include_unknown,
            'snapshot_generated_at': snapshot_generated_at,
            'results': serialized,
        })

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='base-lineage-root-causes-preview')
    def base_lineage_root_causes_preview(self, request):
        from .models import BaseLineageRootCauseAnalyticsSnapshotRow

        lineage_label = (request.query_params.get('lineage_label') or '').strip()
        lineage_source = (request.query_params.get('lineage_source') or '').strip()
        include_unknown = str(request.query_params.get('include_unknown', '0')).lower() in {'1', 'true', 'yes'}

        if not lineage_label:
            return Response(
                {'detail': 'lineage_label query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        latest_snapshot = get_latest_root_cause_analytics_snapshots().get('base_lineage')
        if latest_snapshot:
            snapshot_row = BaseLineageRootCauseAnalyticsSnapshotRow.objects.filter(
                snapshot=latest_snapshot,
                lineage_label=lineage_label,
            ).first()
            if snapshot_row and (
                snapshot_row.repositories_preview
                or snapshot_row.components_preview
                or snapshot_row.vulnerabilities_preview
            ):
                return Response(BaseLineageRootCausePreviewSerializer(snapshot_row).data)
            if snapshot_row and not lineage_source:
                lineage_source = snapshot_row.lineage_source

        lineage_members = _build_targeted_base_lineage_members_queryset(
            lineage_label=lineage_label,
            lineage_source=lineage_source or None,
            include_unknown=include_unknown,
        )
        if not lineage_members.exists():
            return Response(
                {'detail': 'Base lineage not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serialized = BaseLineageRootCausePreviewSerializer(
            _build_base_lineage_preview_payload(lineage_label, lineage_members)
        ).data
        return Response(serialized)

    @action(detail=False, methods=['post'], url_path='base-lineage-root-causes-previews-batch')
    def base_lineage_root_causes_previews_batch(self, request):
        from .models import BaseLineageRootCauseAnalyticsSnapshotRow

        entries = request.data.get('entries') or []
        if not isinstance(entries, list):
            return Response(
                {'detail': 'entries must be a list'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        latest_snapshot = get_latest_root_cause_analytics_snapshots().get('base_lineage')
        results = []

        for entry in entries[:10]:
            if not isinstance(entry, dict):
                continue

            lineage_label = (entry.get('lineage_label') or '').strip()
            lineage_source = (entry.get('lineage_source') or '').strip()
            include_unknown = str(entry.get('include_unknown', '0')).lower() in {'1', 'true', 'yes'}

            if not lineage_label:
                continue

            payload = None
            if latest_snapshot:
                snapshot_row = BaseLineageRootCauseAnalyticsSnapshotRow.objects.filter(
                    snapshot=latest_snapshot,
                    lineage_label=lineage_label,
                ).first()
                if snapshot_row and (
                    snapshot_row.repositories_preview
                    or snapshot_row.components_preview
                    or snapshot_row.vulnerabilities_preview
                ):
                    payload = BaseLineageRootCausePreviewSerializer(snapshot_row).data
                    if not lineage_source:
                        lineage_source = snapshot_row.lineage_source

            if payload is None:
                lineage_members = _build_targeted_base_lineage_members_queryset(
                    lineage_label=lineage_label,
                    lineage_source=lineage_source or None,
                    include_unknown=include_unknown,
                )
                if not lineage_members.exists():
                    payload = {
                        'repositories_preview': [],
                        'components_preview': [],
                        'vulnerabilities_preview': [],
                    }
                else:
                    payload = BaseLineageRootCausePreviewSerializer(
                        _build_base_lineage_preview_payload(lineage_label, lineage_members)
                    ).data

            results.append({
                'lineage_label': lineage_label,
                'lineage_source': lineage_source or 'unknown',
                **payload,
            })

        return Response({'results': results})

    @method_decorator(cache_page(60))
    @action(detail=False, methods=['get'], url_path='base-lineage-root-causes-section')
    def base_lineage_root_causes_section(self, request):
        section = (request.query_params.get('section') or '').strip()
        lineage_label = (request.query_params.get('lineage_label') or '').strip()
        lineage_source = (request.query_params.get('lineage_source') or '').strip()
        include_unknown = str(request.query_params.get('include_unknown', '0')).lower() in {'1', 'true', 'yes'}
        offset = _parse_bounded_integer(request.query_params.get('offset'), 0, minimum=0)
        limit = _parse_bounded_integer(request.query_params.get('limit'), 20, minimum=1, maximum=50)

        if section not in {'repositories', 'components', 'vulnerabilities'}:
            return Response(
                {'detail': 'section must be one of repositories, components, vulnerabilities'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not lineage_label:
            return Response(
                {'detail': 'lineage_label query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lineage_members = _build_targeted_base_lineage_members_queryset(
            lineage_label=lineage_label,
            lineage_source=lineage_source or None,
            include_unknown=include_unknown,
        )
        if not lineage_members.exists():
            return Response(
                {'detail': 'Base lineage not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payload = _build_base_lineage_section_payload(
                lineage_members,
                section=section,
                offset=offset,
                limit=limit,
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(payload)

class JobViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = JobAddRepositoriesResponseSerializer

    @action(detail=False, methods=['post'], url_path='add-repositories')
    def add_repositories(self, request):
        """
        Add new repositories if they do not exist in the system yet.
        Repository is uniquely identified by the combination of name and url.
        The registry_uuid should be provided to link repositories to the correct registry.
        """
        serializer = JobAddRepositoriesRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            repositories = serializer.validated_data['repositories']
            registry_uuid = serializer.validated_data.get('registry_uuid')

            # Get the registry by uuid or fallback to first ACR (for backward compatibility)
            registry = None
            if registry_uuid:
                registry = ContainerRegistry.objects.filter(uuid=registry_uuid).first()
            else:
                registry = ContainerRegistry.objects.filter(provider='acr').first()
            if not registry:
                return Response(
                    {'error': 'No registry found'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            results = []
            for repo_data in repositories:
                # Use repository_type from payload (e.g. docker/helm from JFrog) or default 'none'
                repo_type = repo_data.get('repository_type') or repo_data.get('package_type') or 'none'
                if repo_type not in ('docker', 'helm', 'none', 'Unknown'):
                    repo_type = 'none'
                defaults = {
                    'status': True,
                    'repository_type': repo_type,
                    'container_registry': registry,
                }
                if repo_data.get('repo_key'):
                    defaults['repo_key'] = repo_data['repo_key']
                repository, created = Repository.objects.get_or_create(
                    url=repo_data['repository_url'],
                    name=repo_data['repository_name'],
                    defaults=defaults,
                )
                result = {
                    'repository': repo_data['repository_name'],
                    'repository_id': str(repository.uuid),
                    'created': created
                }
                if not created:
                    result['message'] = 'Repository already exists'
                results.append(result)

            return Response({
                'status': 'success',
                'message': f'Processed {len(repositories)} repositories',
                'results': results
            })

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class RepositoryTagListForRepositoryView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RepositoryTagListSerializer
    pagination_class = CustomPageNumberPagination
    ordering = ['-updated_at']

    def get_queryset(self):
        repository_uuid = self.kwargs['repository_uuid']
        return RepositoryTag.objects.filter(
            repository__uuid=repository_uuid
        ).only(*REPOSITORY_TAG_LIST_ONLY_FIELDS)
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(tag__icontains=search)

        ordered = _apply_repository_tag_ordering(
            queryset,
            request.query_params.get('ordering', '-updated_at'),
        )

        page = self.paginate_queryset(ordered)
        items = list(page) if page is not None else list(ordered[:self.pagination_class.page_size])
        _attach_repository_tag_summary_data(items)

        serializer = self.get_serializer(items, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

class ReportGeneratorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Generate a vulnerability report for selected images or a release.
        Returns an Excel file with vulnerability data.
        
        Request body:
        - For images: {"image_uuids": ["uuid1", "uuid2", ...]}
        - For release: {"release_uuid": "uuid"}
        """
        image_uuids = request.data.get('image_uuids', [])
        release_uuid = request.data.get('release_uuid')
        
        if not image_uuids and not release_uuid:
            return Response(
                {'error': 'No images or release selected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # If release_uuid is provided, get all images from that release
        if release_uuid:
            try:
                release = Release.objects.get(uuid=release_uuid)
                # Get all images from repository tags in this release
                images = Image.objects.filter(
                    repository_tags__releases__release=release
                ).distinct()
            except Release.DoesNotExist:
                return Response(
                    {'error': 'Release not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Use provided image UUIDs
            images = Image.objects.filter(uuid__in=image_uuids)

        try:
            # Create Excel file in memory
            output = BytesIO()
            wb = Workbook()
            ws = wb.active
            ws.title = 'Vulnerability Report'
            ws.append([
                'Image Name', 'Component Name', 'Component Type', 'Component Version',
                'Vulnerability ID', 'Vulnerability Severity', 'Fixed In'
            ])

            for image in images:
                findings_qs = ComponentVersionVulnerability.objects.filter(
                    component_version__images=image
                ).select_related(
                    'component_version',
                    'component_version__component',
                    'vulnerability'
                )
                if findings_qs.exists():
                    for cvv in findings_qs:
                        ws.append([
                            image.name,
                            cvv.component_version.component.name,
                            cvv.component_version.component.type,
                            cvv.component_version.version,
                            cvv.vulnerability.vulnerability_id,
                            cvv.vulnerability.severity,
                            cvv.fix or 'No fix metadata'
                        ])
                else:
                    ws.append([
                        image.name, '', '', '', '', '', ''
                    ])

            wb.save(output)
            output.seek(0)

            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            
            # Generate appropriate filename based on report type
            if release_uuid:
                release_name = Release.objects.get(uuid=release_uuid).name
                filename = f"release_{release_name}_vulnerability_report_{timestamp}.xlsx"
            else:
                filename = f"vulnerability_report_{timestamp}.xlsx"

            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Access-Control-Expose-Headers'] = 'Content-Disposition'
            return response

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ComponentMatrixView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Generate a component matrix for selected repositories or images.
        Returns JSON: columns are repo:tag or image names, rows are components, cells are versions.
        
        Request body:
        {
            "type": "repository" | "image",  # Type of comparison
            "repository_tags": [{"repo_uuid": "uuid1", "tag": "tag1"}, ...],  # For repository comparison
            "image_uuids": ["uuid1", "uuid2"]  # For image comparison
        }
        """
        comparison_type = request.data.get('type', 'repository')
        repo_tags = request.data.get('repository_tags', [])
        image_uuids = request.data.get('image_uuids', [])

        if comparison_type == 'repository' and not repo_tags:
            return Response({'error': 'No repositories selected'}, status=400)
        elif comparison_type == 'image' and not image_uuids:
            return Response({'error': 'No images selected'}, status=400)

        # Get all relevant data with a single query
        from core.models import Repository, RepositoryTag, Image, ComponentVersion, ComponentVersionVulnerability
        from django.db.models import Max, Prefetch, Subquery, OuterRef

        if comparison_type == 'repository':
            tags = RepositoryTag.objects.filter(
                repository__uuid__in=[rt['repo_uuid'] for rt in repo_tags],
                tag__in=[rt['tag'] for rt in repo_tags]
            ).select_related('repository').order_by('repository__uuid', '-tag')

            tag_mapping = {
                f"{tag.repository.uuid}:{tag.tag}": tag
                for tag in tags
            }

            columns = []
            component_set = set()
            image_components = {}
            seen_col_labels = set()
            for repo_tag in repo_tags:
                repo_uuid = repo_tag['repo_uuid']
                tag_name = repo_tag['tag']
                tag_key = f"{repo_uuid}:{tag_name}"
                tag = tag_mapping.get(tag_key)
                if not tag:
                    continue
                col_label = f"{tag.repository.name}:{tag.tag}"
                if col_label in seen_col_labels:
                    continue  # avoid duplicate columns
                seen_col_labels.add(col_label)
                columns.append({
                    'repo': tag.repository.name,
                    'tag': tag.tag,
                    'label': col_label,
                    'type': 'repository'
                })
                images_for_tag = Image.objects.filter(repository_tags=tag, sbom_data__isnull=False).order_by('-updated_at')
                image_components[col_label] = {}
                for image in images_for_tag:
                    cvs = image.component_versions.all()
                    for cv in cvs:
                        cname = cv.component.name
                        component_set.add(cname)
                        if cname not in image_components[col_label]:
                            image_components[col_label][cname] = {
                                'version': cv.version,
                                'has_vuln': cv.componentversionvulnerability_set.exists(),
                                'latest_version': cv.latest_version
                            }

        else:  # comparison_type == 'image'
            # Get all relevant images with SBOM in one query
            images = Image.objects.filter(
                uuid__in=image_uuids,
                sbom_data__isnull=False
            ).prefetch_related(
                'component_versions',
                'component_versions__component',
                'component_versions__componentversionvulnerability_set'
            ).order_by('-updated_at')

            # Build columns and collect all component versions in one go
            columns = []
            component_set = set()
            image_components = {}
            
            for image in images:
                col_label = image.name
                columns.append({
                    'name': image.name,
                    'digest': image.digest,
                    'label': col_label,
                    'type': 'image'
                })
                
                # Get all component versions for this image with their vulnerabilities
                cvs = image.component_versions.all()
                image_components[col_label] = {}
                
                for cv in cvs:
                    cname = cv.component.name
                    component_set.add(cname)
                    image_components[col_label][cname] = {
                        'version': cv.version,
                        'has_vuln': cv.componentversionvulnerability_set.exists(),
                        'latest_version': cv.latest_version
                    }

        components = sorted(component_set)

        # Build matrix using the pre-fetched data
        matrix = {}
        for cname in components:
            matrix[cname] = {}
            for col in columns:
                col_label = col['label']
                if col_label in image_components and cname in image_components[col_label]:
                    matrix[cname][col_label] = image_components[col_label][cname]
                else:
                    matrix[cname][col_label] = {'version': '', 'has_vuln': False, 'latest_version': None}

        # Get component types
        component_types = {}
        for component in Component.objects.filter(name__in=components):
            component_types[component.name] = component.type

        return Response({
            'components': components,
            'columns': columns,
            'matrix': matrix,
            'type': comparison_type,
            'component_types': component_types
        })

# Celery Task Views
from django_celery_results.models import TaskResult
from django_celery_beat.models import PeriodicTask
from django.db.models import Q, Avg, Count
from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from celery import current_app
import json

# Import task serializers after they are defined
from .serializers import (
    TaskResultSerializer, TaskResultListSerializer, 
    PeriodicTaskSerializer, TaskStatisticsSerializer
)

class TestViewSet(viewsets.ViewSet):
    """
    Simple test viewset to check if imports work
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def test(self, request):
        """Simple test endpoint"""
        return Response({
            'message': 'Test endpoint works!',
            'task_count': TaskResult.objects.count(),
            'periodic_task_count': PeriodicTask.objects.count()
        })
    
    @action(detail=False, methods=['get'], url_path='endpoint')
    def test_endpoint(self, request):
        """Simple test endpoint for frontend"""
        return Response({
            'message': 'Test endpoint works!',
            'status': 'success'
        })
    
    @action(detail=False, methods=['get'], url_path='direct')
    def test_direct(self, request):
        """Direct test endpoint"""
        return Response({
            'message': 'Direct API test works!',
            'status': 'success',
            'timestamp': timezone.now().isoformat()
        })

class TaskManagementViewSet(BaseViewSet):
    """
    ViewSet for managing and monitoring Celery tasks
    """
    queryset = TaskResult.objects.all().order_by('-date_created')
    serializer_class = TaskResultSerializer
    filterset_fields = ['status', 'task_name']
    search_fields = ['task_id', 'task_name']
    ordering_fields = ['task_id', 'task_name', 'date_created', 'date_done', 'status']
    ordering = ['-date_created']
    lookup_field = 'task_id'
    
    def get_serializer_class(self):
        """Use different serializers for list and detail views"""
        if self.action == 'list':
            return TaskResultListSerializer
        return TaskResultSerializer
    
    def list(self, request):
        """List tasks with proper pagination and filtering"""
        # Use the parent class's list method which handles pagination, filtering, and search
        return super().list(request)
    
    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action == 'list':
            queryset = queryset.only(
                'task_id',
                'task_name',
                'status',
                'result',
                'date_created',
                'date_done',
            )
        
        # Filter by date range
        days = self.request.query_params.get('days', None)
        if days:
            try:
                days = int(days)
                cutoff_date = timezone.now() - timedelta(days=days)
                queryset = queryset.filter(date_created__gte=cutoff_date)
            except ValueError:
                pass
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            if status_filter == 'success':
                queryset = queryset.filter(status='SUCCESS')
            elif status_filter == 'error':
                queryset = queryset.filter(status='FAILURE')
            elif status_filter == 'pending':
                queryset = queryset.filter(status='PENDING')
            elif status_filter == 'in_process':
                queryset = queryset.filter(status='STARTED')
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get task statistics"""
        # Get date range
        days = int(request.query_params.get('days', 7))
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Get tasks in date range
        tasks = TaskResult.objects.filter(date_created__gte=cutoff_date)
        
        # Calculate statistics
        total_tasks = tasks.count()
        successful_tasks = tasks.filter(status='SUCCESS').count()
        failed_tasks = tasks.filter(status='FAILURE').count()
        pending_tasks = tasks.filter(status='PENDING').count()
        running_tasks = tasks.filter(status='STARTED').count()
        
        # Calculate average duration
        completed_tasks = tasks.filter(status='SUCCESS', date_done__isnull=False)
        if completed_tasks.exists():
            # Calculate duration for each task and then average
            total_duration = 0
            count = 0
            for task in completed_tasks:
                if task.date_done and task.date_created:
                    duration = task.date_done - task.date_created
                    total_duration += duration.total_seconds()
                    count += 1
            
            avg_duration = total_duration / count if count > 0 else 0.0
        else:
            avg_duration = 0.0
        
        # Get recent tasks
        recent_tasks = tasks.order_by('-date_created')[:10]
        recent_tasks_data = []
        for task in recent_tasks:
            duration = None
            if task.date_done and task.date_created:
                duration = (task.date_done - task.date_created).total_seconds()
            
                    # Get proper task name
        task_name = task.task_name
        if not task_name:
            try:
                from celery import current_app
                task_func = current_app.tasks.get(task.task_id)
                if task_func:
                    task_name = task_func.name
            except:
                pass
        
        if not task_name:
            # Try to extract from task_id by looking for known patterns
            if task.task_id:
                if 'generate_sbom' in task.task_id or 'sbom' in task.task_id:
                    task_name = "Generate SBOM and Create Components"
                elif 'scan' in task.task_id and 'grype' in task.task_id:
                    task_name = "Scan Image with Grype"
                elif 'vulnerability' in task.task_id and 'update' in task.task_id:
                    task_name = "Update Vulnerability Details"
                elif 'process' in task.task_id and 'tag' in task.task_id:
                    task_name = "Process Single Tag"
                elif 'repository' in task.task_id and 'scan' in task.task_id:
                    task_name = "Scan Repository"
                elif 'parse' in task.task_id and 'sbom' in task.task_id:
                    task_name = "Parse SBOM and Create Components"
                elif 'update' in task.task_id and 'component' in task.task_id:
                    task_name = "Update Components Latest Versions"
                elif 'process' in task.task_id and 'grype' in task.task_id:
                    task_name = "Process Grype Scan Results"
                elif 'cleanup' in task.task_id:
                    task_name = "Cleanup Old Vulnerability Data"
                elif 'cisa' in task.task_id or 'kev' in task.task_id:
                    task_name = "Update CISA KEV Vulnerabilities"
                elif 'test' in task.task_id:
                    task_name = "Test Task"
                else:
                    task_name = f"Task-{task.task_id[:8]}"
            else:
                task_name = 'Unknown'
            
            recent_tasks_data.append({
                'task_id': task.task_id,
                'task_name': task_name,
                'status': task.status,
                'duration': duration,
                'created': task.date_created
            })
        
        data = {
            'total_tasks': total_tasks,
            'successful_tasks': successful_tasks,
            'failed_tasks': failed_tasks,
            'pending_tasks': pending_tasks,
            'running_tasks': running_tasks,
            'average_duration': avg_duration,
            'recent_tasks': recent_tasks_data
        }
        
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def task_types(self, request):
        """Get statistics by task type"""
        days = int(request.query_params.get('days', 7))
        cutoff_date = timezone.now() - timedelta(days=days)
        
        tasks = TaskResult.objects.filter(date_created__gte=cutoff_date)
        
        # Group by task name and status
        task_stats = tasks.values('task_name').annotate(
            total=Count('id'),
            success=Count('id', filter=Q(status='SUCCESS')),
            failure=Count('id', filter=Q(status='FAILURE')),
            pending=Count('id', filter=Q(status='PENDING')),
            running=Count('id', filter=Q(status='STARTED'))
        ).order_by('-total')
        
        return Response(task_stats)
    
    @action(detail=True, methods=['get'])
    def result_details(self, request, pk=None):
        """Get detailed result information for a task"""
        task = self.get_object()
        
        # Parse result if it's JSON
        result_data = None
        if task.result:
            try:
                result_data = json.loads(task.result)
            except (json.JSONDecodeError, TypeError):
                result_data = str(task.result)
        
        data = {
            'task_id': task.task_id,
            'task_name': task.task_name,
            'status': task.status,
            'created': task.date_created,
            'updated': task.date_done,
            'duration': (task.date_done - task.date_created).total_seconds() if task.date_done else None,
            'result': result_data,
            'traceback': task.traceback,
            'meta': task.meta
        }
        
        return Response(data)
    
    @action(detail=True, methods=['post'])
    def retry_task(self, request, task_id=None):
        """Retry a failed task"""
        try:
            task = TaskResult.objects.get(task_id=task_id)
            if task.status != 'FAILURE':
                return Response(
                    {'error': 'Only failed tasks can be retried'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Retry the task
            celery_app = current_app
            celery_app.control.revoke(task_id, terminate=True)
            
            # Get the task function and retry it
            if task.task_name:
                task_func = celery_app.tasks.get(task.task_name)
                if task_func:
                    # Retry the task
                    result = task_func.delay()
                    return Response({
                        'message': 'Task retry initiated',
                        'new_task_id': result.id
                    })
            
            return Response(
                {'error': 'Could not retry task'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except TaskResult.DoesNotExist:
            return Response(
                {'error': 'Task not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def stop_task(self, request, task_id=None):
        """Stop a running task"""
        try:
            # Get the task result
            task_result = TaskResult.objects.get(task_id=task_id)
            
            # Check if task is running
            if task_result.status not in ['STARTED', 'PENDING']:
                return Response(
                    {'error': f'Task is in {task_result.status} state and cannot be stopped'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Revoke the task in Celery
            from celery import current_app
            current_app.control.revoke(task_id, terminate=True)
            
            # Update the task status in database
            task_result.status = 'REVOKED'
            task_result.save()
            
            return Response({
                'message': 'Task stopped successfully',
                'task_id': task_id,
                'status': 'REVOKED'
            })
            
        except TaskResult.DoesNotExist:
            return Response(
                {'error': 'Task not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Failed to stop task: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PeriodicTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing periodic tasks
    """
    permission_classes = [IsAuthenticated]
    queryset = PeriodicTask.objects.select_related('interval', 'crontab').all().order_by('name')
    serializer_class = PeriodicTaskSerializer
    filterset_fields = ['enabled', 'task']
    search_fields = ['name', 'task']
    ordering_fields = ['name', 'task', 'enabled', 'last_run_at', 'total_run_count']
    ordering = ['name']
    
    @action(detail=True, methods=['post'])
    def toggle_enabled(self, request, pk=None):
        """Toggle periodic task enabled/disabled status"""
        task = self.get_object()
        task.enabled = not task.enabled
        task.save()
        
        return Response({
            'id': task.id,
            'name': task.name,
            'enabled': task.enabled
        })
    
    @action(detail=True, methods=['post'])
    def run_now(self, request, pk=None):
        """Run a periodic task immediately"""
        task = self.get_object()
        
        try:
            # Get the task function and run it
            celery_app = current_app
            task_func = celery_app.tasks.get(task.task)
            if task_func:
                result = task_func.delay()
                return Response({
                    'message': 'Task started',
                    'task_id': result.id
                })
            else:
                return Response(
                    {'error': 'Task function not found'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class TestTaskViewSet(viewsets.ViewSet):
    """
    ViewSet for testing tasks
    """
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def run_test_task(self, request):
        """Run a simple test task"""
        from .tasks import test_task
        
        try:
            # Use apply_async with explicit task name
            result = test_task.apply_async(task_name="Test Task")
            return Response({
                'message': 'Test task started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def run_failing_task(self, request):
        """Run a task that will fail"""
        from .tasks import test_failing_task
        
        try:
            # Use apply_async with explicit task name
            result = test_failing_task.apply_async(task_name="Test Failing Task")
            return Response({
                'message': 'Failing test task started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def update_all_components_latest_versions(self, request):
        """Update latest versions for all components in the system"""
        from .tasks import update_all_components_latest_versions
        
        try:
            result = update_all_components_latest_versions.delay()
            return Response({
                'message': 'All components latest versions update started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def update_deb_components_latest_versions(self, request):
        """Update latest versions only for deb components in the system"""
        from .tasks import update_deb_components_latest_versions

        try:
            result = update_deb_components_latest_versions.delay()
            return Response({
                'message': 'Deb components latest versions update started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def backfill_image_lineage_fields(self, request):
        """Backfill persisted image OS lineage fields from SBOM and package metadata"""
        from .tasks import backfill_image_lineage_fields

        try:
            result = backfill_image_lineage_fields.delay()
            return Response({
                'message': 'Image lineage backfill started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def backfill_image_sbom_security_metadata(self, request):
        """Backfill image OS lifecycle and per-image component metadata from existing SBOM/Grype data"""
        from .tasks import backfill_image_sbom_security_metadata

        try:
            result = backfill_image_sbom_security_metadata.delay()
            return Response({
                'message': 'Image SBOM security metadata backfill started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def recalculate_vulnerability_fix_availability(self, request):
        """Recalculate fix availability metadata for existing vulnerability rows"""
        from .tasks import recalculate_vulnerability_fix_availability

        try:
            result = recalculate_vulnerability_fix_availability.delay()
            return Response({
                'message': 'Vulnerability fix availability recalculation started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def collect_root_cause_analytics_snapshot(self, request):
        """Collect persisted root-cause analytics snapshot rows for dashboard and comparison pages"""
        from .tasks import collect_root_cause_analytics_snapshot

        try:
            result = collect_root_cause_analytics_snapshot.delay()
            return Response({
                'message': 'Root cause analytics snapshot collection started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def rescan_all_images_with_sbom(self, request):
        """Re-analyze all images that have SBOM data using Grype"""
        from .tasks import rescan_all_images_with_sbom
        
        try:
            result = rescan_all_images_with_sbom.delay()
            return Response({
                'message': 'Mass rescan of all images with SBOM started (individual tasks scheduled)',
                'task_id': result.id,
                'note': 'Individual scan tasks are scheduled asynchronously. Use monitor_mass_rescan_progress to track progress.'
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def monitor_mass_rescan_progress(self, request):
        """Monitor the progress of mass rescan by checking image scan statuses"""
        from .tasks import monitor_mass_rescan_progress
        
        try:
            result = monitor_mass_rescan_progress.delay()
            return Response({
                'message': 'Progress monitoring started',
                'task_id': result.id
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def check_images_with_sbom(self, request):
        """Check how many images have SBOM data and their scan status"""
        from .models import Image
        from django.db.models import Q, Count
        
        try:
            # Get stats on images with SBOM
            total_images = Image.objects.count()
            images_with_sbom = Image.objects.filter(
                Q(sbom_data__isnull=False) & 
                ~Q(sbom_data={})
            ).count()
            
            # Count by scan status
            status_counts = Image.objects.filter(
                Q(sbom_data__isnull=False) & 
                ~Q(sbom_data={})
            ).values('scan_status').annotate(count=Count('id'))
            
            status_breakdown = {item['scan_status']: item['count'] for item in status_counts}
            
            return Response({
                'total_images': total_images,
                'images_with_sbom': images_with_sbom,
                'status_breakdown': status_breakdown,
                'ready_for_rescan': Image.objects.filter(
                    Q(sbom_data__isnull=False) & 
                    ~Q(sbom_data={}) &
                    ~Q(scan_status__in=['in_process', 'pending'])
                ).count()
            })
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
