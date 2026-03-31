from datetime import date, datetime, timedelta
from typing import Dict

from django.utils import timezone

from core.models import ThreatIntelSnapshot, Vulnerability
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
        return {
            'count': bucket.get('count', len(entries)),
            'entries': entries[:limit],
        }

    return {
        'period_start': summary.get('period_start'),
        'period_end': summary.get('period_end'),
        'observed_this_week': limited_bucket(summary.get('observed_this_week')),
        'kev_added_this_week': limited_bucket(summary.get('kev_added_this_week')),
        'supply_chain_this_week': limited_bucket(summary.get('supply_chain_this_week')),
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

    observed_entries = [
        {
            'uuid': str(vulnerability.uuid),
            'vulnerability_id': vulnerability.vulnerability_id,
            'severity': vulnerability.severity,
            'type': vulnerability.vulnerability_type,
            'created_at': vulnerability.created_at.isoformat(),
            'epss': round(vulnerability.epss or 0, 3),
            'cisa_kev': bool(getattr(vulnerability.details, 'cisa_kev_known_exploited', False))
            if getattr(vulnerability, 'details', None) else False,
            'exploit_available': bool(getattr(vulnerability.details, 'exploit_available', False))
            if getattr(vulnerability, 'details', None) else False,
        }
        for vulnerability in (observed_queryset if limit is None else observed_queryset[:limit])
    ]

    collector = VulnerabilityDataCollector()

    try:
        kev_summary = collector.get_weekly_cisa_kev_entries(week_start, week_end, limit=limit)
    except Exception:
        kev_summary = {'count': 0, 'entries': []}

    try:
        supply_chain_summary = collector.get_weekly_github_supply_chain_advisories(
            week_start,
            week_end,
            limit=limit,
        )
    except Exception:
        supply_chain_summary = {'count': 0, 'entries': []}

    return {
        'period_start': week_start.isoformat(),
        'period_end': week_end.isoformat(),
        'observed_this_week': {
            'count': observed_queryset.count(),
            'entries': observed_entries,
        },
        'kev_added_this_week': kev_summary,
        'supply_chain_this_week': supply_chain_summary,
    }


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
