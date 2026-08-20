# Periodic Tasks

HITrack uses `django-celery-beat`. Schedules are stored in PostgreSQL and dispatched by the `beat` service.

## Create a Schedule in Django Admin

1. Open **Django Admin → Periodic tasks → Periodic tasks**.
2. Create or reuse an interval or crontab schedule.
3. Add a periodic task and select the exact registered task name.
4. Set positional arguments to `[]` unless this document says otherwise.
5. Set keyword arguments to `{}` to use defaults, or provide a valid JSON object.
6. Enable the task and save it.
7. Confirm the result on the Tasks page and in worker logs after the first run.

Do not put registry credentials in arguments. The task reads them from the selected `ContainerRegistry` record.

Avoid two enabled schedules for the same orchestration task unless their scopes are intentionally different. A short interval can produce overlapping work; registry discovery has a per-registry lock, while not every maintenance task does.

## Recommended Baseline

This is a starting point, not a universal retention or capacity policy:

| Task | Example cadence | Purpose |
| --- | --- | --- |
| `Sync JFrog Repositories` | daily, before tag discovery | Discover new JFrog repo keys, applications, and charts. Omit when JFrog is not used. |
| `Periodic Repository Scan` | daily or every few hours | Select tags for all active repositories and queue their processing. |
| `Update Critical Vulnerability Details` | daily | Refresh stale or missing critical/high-priority external details. |
| `Update All Vulnerability Details` | weekly | Refresh other supported vulnerability details in batches. Adjust for external API limits. |
| `Update CISA KEV Vulnerabilities` | daily | Refresh CISA KEV flags. |
| `Collect Weekly Threat Intel Snapshot` | daily | Persist the current rolling-week view and apply snapshot retention. |
| `Collect Root Cause Analytics Snapshot` | daily, after scans | Refresh shared-component and base-lineage analytics and cleanup old snapshots. |
| `Update All Components Latest Versions` | monthly | Refresh latest-version metadata; records updated in the last 30 days are skipped. |
| `Cleanup Old Vulnerability Data` | weekly | Delete stale enrichment details only for vulnerabilities with no linked components. |

For example, schedule JFrog discovery at 01:00 and repository tag scanning at 02:00 so newly created repositories are active before tags are listed.

## Repository and Registry Tasks

### Sync JFrog Repositories

Registered name:

```text
Sync JFrog Repositories
```

All parameters are optional. Empty kwargs discover Docker and Helm applications in every configured JFrog registry:

```json
{}
```

Full example:

```json
{
  "registry_uuid": null,
  "include_docker": true,
  "include_helm": true,
  "activate_new": true,
  "catalog_page_size": 500,
  "max_projects_per_repo_key": null,
  "batch_size": 500
}
```

Set `registry_uuid` only to restrict the run to one Artifactory record. The normal architecture is one `ContainerRegistry` per Artifactory credential/API context, so the default `null` scans every JFrog registry independently.

The task creates repository records; it does not scan tags. It queues the internal `Sync Single JFrog Registry` task for each selected registry. See [Periodic JFrog Repository Discovery](jfrog-repository-discovery.md).

### Periodic Repository Scan

Registered name:

```text
Periodic Repository Scan
```

Empty kwargs preserve the historical behavior: choose one globally latest tag for every active repository and process existing selected tags:

```json
{}
```

To choose the newest tag in every major branch:

```json
{
  "selection_mode": "latest_per_release_line",
  "release_line_depth": 1,
  "release_lines_limit": null,
  "include_prerelease": false,
  "scan_latest_alias": false,
  "tag_candidates_limit": null,
  "process_existing": true
}
```

With tags `28.1`, `28.2`, `28.3`, `29.1`, and `29.2`, this selects `28.3` and `29.2`. Set `release_line_depth` to `2` to track major.minor lines; `28.1.2` then competes only inside line `28.1`.

See [Release-Line Tag Scanning](periodic-tag-scanning.md) for selection, sorting, limits, prereleases, and legacy behavior.

### Delete Old Repository Tags

Registered name:

```text
Delete Old Repository Tags
```

> **Destructive:** this deletes repository tags older than `days` and also deletes images that become orphaned. The default is only one day. Do not add this to a schedule without an approved retention policy, a database backup, and an explicit value.

Example for a deliberate 90-day policy:

```json
{"days": 90}
```

## Vulnerability Intelligence Tasks

| Registered task | Arguments | Notes |
| --- | --- | --- |
| `Update Critical Vulnerability Details` | `{}` | Queues bulk enrichment for critical/stale targets. |
| `Update All Vulnerability Details` | `{}` | Queues batched enrichment for eligible records. |
| `Update CISA KEV Vulnerabilities` | `{}` | Refreshes KEV data. |
| `Cleanup Old Vulnerability Data` | `{}` | Deletes details older than 90 days only when the vulnerability has no linked component versions. |

These are network-dependent. Stagger them and respect the limits of external services. A successful orchestration result means batches were queued; inspect batch tasks for final completion.

`Update Vulnerability Details` accepts a vulnerability UUID and optional `force`, but is intended for a manual single-record action rather than a generic periodic schedule.

## Snapshot Tasks

### Threat Intelligence

`Collect Weekly Threat Intel Snapshot` accepts:

```json
{"retention_days": 90, "limit": null}
```

It saves the current weekly summary and invokes retention cleanup. Scheduling `Cleanup Threat Intel Snapshots` separately is optional when collection runs regularly.

### Root-Cause Analytics

`Collect Root Cause Analytics Snapshot` accepts:

```json
{"retention_days": 30, "batch_size": 500}
```

It queues shared-component collection, base-lineage collection, and cleanup. Do not separately schedule the two child collectors unless you deliberately want independent cadences.

Scheduling `Cleanup Root Cause Analytics Snapshots` separately is optional when the parent collection task runs regularly.

## Component Version Tasks

`Update All Components Latest Versions` refreshes stored latest-version information in batches and skips component versions updated within 30 days. Monthly is the intended baseline.

`Update Deb Components Latest Versions` applies the same policy only to stored Debian packages. Use it instead of the all-component task when only distro-aware Debian data needs refresh; normally do not schedule both at the same time.

## Manual and Upgrade Maintenance

These registered tasks are normally run once after a relevant upgrade or during controlled maintenance, not on a frequent cron:

| Task | Use |
| --- | --- |
| `Backfill Image Lineage Fields` | Rebuild persisted distro/base-lineage fields for existing images. |
| `Backfill Image SBOM Security Metadata` | Rebuild image security metadata and vulnerability summaries from stored data. |
| `Recalculate Vulnerability Fix Availability` | Recalculate normalized fix fields from stored Grype results without rescanning. |
| `Deduplicate Images by Identity` | Merge historical duplicate image identities. Review backups and results. |
| `Rescan All Images with SBOM` | Queue a mass rescan and its monitor; capacity-intensive. |

Prefer the management commands documented in [Operations and Deployment](operations.md) for upgrade backfills because they are explicit and easier to observe during deployment.

## Internal Tasks: Do Not Schedule Directly

The following registered names are child, parser, batching, or monitoring implementation details:

- `Sync Single JFrog Registry`
- `Scan Repository Tags`
- `Process Single Tag`
- `Scan Repository`
- `Process All Tags`
- `Generate SBOM and Create Components`
- `Parse SBOM and Create Components`
- `Scan Image with Grype`
- `Process Grype Scan Results`
- `Update Components Latest Versions`
- `Update Vulnerability Details (Bulk)`
- `Update Critical Vulnerabilities (Bulk)`
- `Monitor Task Status`
- `Monitor Bulk Update Progress`
- `Monitor Mass Rescan Progress`
- `Collect Shared Root Cause Analytics Snapshot`
- `Collect Base Lineage Root Cause Analytics Snapshot`

Use their parent orchestration task or the corresponding UI action.

Never schedule `Test Task` or `Test Failing Task`. `Performance Monitor` assumes PostgreSQL statistics support such as `pg_stat_statements` and should only be enabled after verifying that dependency and deciding how its results will be consumed.

## Queues and Observation

The scheduler dispatches tasks by registered name; routing sends work to `light`, `scan`, or `enrichment`. Keep all three worker services running for the complete workflow.

```bash
docker compose ps
docker compose logs --since=30m beat worker-light worker-scan worker-enrichment
```

After changing a periodic task, confirm:

- the `beat` service sees the database schedule;
- the expected parent task starts only once;
- returned child IDs appear in task results;
- child tasks reach a terminal state;
- affected repositories, tags, images, or snapshots have the expected timestamps.
