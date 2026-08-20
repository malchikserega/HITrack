# Periodic Release-Line Tag Scanning

[Back to the documentation index](README.md)

HITrack can periodically scan either one latest tag per repository or one latest tag in every supported release line. Release-line mode solves the following case:

1. A repository contains `28.1`, `28.2`, `29.1`, and `29.2`.
2. The globally latest release is `29.2`.
3. A maintained older branch later publishes `28.3`.
4. A latest-only scan would continue selecting `29.2`; release-line mode selects both `28.3` and `29.2`.

The policy is configured globally in the `Periodic Repository Scan` Celery Beat task and is applied to every active repository. Repositories that are already being scanned are skipped until their current scan finishes.

## Selection Modes

| `selection_mode` | Behavior |
| --- | --- |
| omitted or `latest_only` | Select one globally latest tag. Omitting the parameter preserves the historical behavior exactly. |
| `latest_per_release_line` | Select the highest version in every configured release line. |
| `all` | Select all tags returned by the registry query. |

For `latest_per_release_line`, `release_line_depth` defines the release line:

| Depth | Release line | Example result |
| --- | --- | --- |
| `1` | major | `28.x`, `29.x` -> `28.3`, `29.2` |
| `2` | major.minor | `28.1.x`, `28.2.x` -> `28.1.2`, `28.2` |
| `3` | major.minor.patch | Useful when a fourth version component distinguishes releases. |

Versions with fewer components are padded with zeroes for grouping. For example, at depth `2`, `v28` and `28.0` belong to the same `28.0.x` line. Tags may start with `v`, for example `v28.1.2`. Bare numeric tags such as timestamps or build numbers are not treated as release versions unless they have a `v` prefix.

If no version-like tags can be found, HITrack falls back to its historical latest-tag selector instead of silently doing nothing.

## Task Parameters

Configure these values in the `Keyword arguments` field of the Django Celery Beat periodic task:

| Parameter | Default | Description |
| --- | --- | --- |
| `selection_mode` | omitted / `latest_only` | Tag selection policy. Use `latest_per_release_line` to track maintained branches. |
| `release_line_depth` | `1` | Number of version components that identify a release line. Valid values: `1`, `2`, or `3`. |
| `release_lines_limit` | `null` | Maximum number of newest release lines to track. `null` tracks every discovered line. |
| `include_prerelease` | `false` | Include tags marked alpha, beta, RC, preview, dev, or snapshot. |
| `scan_latest_alias` | `false` | Additionally select the literal `latest` tag. |
| `tag_candidates_limit` | `500` in release-line mode | Maximum number of registry tags inspected per image. Use `null` for the provider default. |
| `process_existing` | `true` | Requeue selected tags already stored by HITrack. When `false`, only newly discovered tags are processed. |

`release_lines_limit` applies after release lines are sorted by version, not by registry publication time. If an older branch must remain supported, either set a sufficiently large limit or use `null`. For example, a limit of `2` tracks only the two numerically newest major lines.

`tag_candidates_limit` controls discovery, not the number of scans. HITrack first fetches up to this many candidate tags and then selects one tag per release line. Set the limit high enough to include releases from every maintained branch. JFrog release-line scans default to 500 candidates; ACR and other single-image registries query up to 500 by default. A Helm index is selected after its entries are loaded.

## Recommended Django Admin Configuration

Open [Django Admin](http://127.0.0.1:1337/admin/), then:

1. Open **Periodic tasks** under **Django Celery Beat**.
2. Create a task or open the existing repository scan task.
3. Set **Name** to a descriptive value such as `Repository scan by major release line`.
4. Set **Task (registered)** to `Periodic Repository Scan`.
5. Select the desired interval or crontab schedule.
6. Set **Arguments** to `[]`.
7. Paste one of the configurations below into **Keyword arguments**.
8. Enable the task and save it.

Do not create two overlapping enabled schedules unless scanning the same active repositories twice is intentional.

### Latest Release per Major Branch

This configuration selects `28.3` and `29.2` from `28.1`, `28.2`, `28.3`, `29.1`, and `29.2`:

```json
{
  "selection_mode": "latest_per_release_line",
  "release_line_depth": 1,
  "release_lines_limit": null,
  "include_prerelease": false,
  "scan_latest_alias": false,
  "tag_candidates_limit": 500,
  "process_existing": false
}
```

Use `release_lines_limit: 2` instead of `null` if only the two newest major branches should be tracked.

### Latest Release per Major.Minor Branch

This configuration selects `28.1.2` for the `28.1.x` line while independently following `28.2.x`, `29.1.x`, and `29.2.x`:

```json
{
  "selection_mode": "latest_per_release_line",
  "release_line_depth": 2,
  "release_lines_limit": 10,
  "include_prerelease": false,
  "scan_latest_alias": false,
  "tag_candidates_limit": 500,
  "process_existing": false
}
```

Increase `release_lines_limit` or use `null` if more than ten major.minor branches remain supported.

### Preserve the Previous Behavior

An existing periodic task with no keyword arguments remains backward compatible:

```json
{}
```

It forwards the historical configuration to each repository scan:

```json
{
  "latest_only": true,
  "process_existing": true
}
```

This selects one globally latest tag and reprocesses it on every scheduled run.

## Existing Tags, Mutable Tags, and Prereleases

Use `process_existing: false` for normal release discovery. A newly published version such as `28.3` is created and scanned, while an unchanged version already known to HITrack is not queued again.

Use `process_existing: true` when selected tags must be rescanned on every run. This is more expensive and can generate repeated SBOM and vulnerability work.

The `latest` alias is handled separately from versioned tags. With `scan_latest_alias: true`, it is appended to the selected releases. Because an existing tag is skipped when `process_existing` is `false`, a mutable `latest` alias is not automatically rescanned merely because its registry digest changed. Prefer immutable version tags for release-line tracking, or enable processing of existing tags when mutable aliases must be refreshed.

Prereleases are excluded by default. With `include_prerelease: true`, their ordering within the same numeric version is alpha/dev, then beta/preview, then RC, then the final release. A final release therefore wins over its prereleases when both are present.

## Apply the Change in Docker

No database migration or backfill command is required for this feature. After pulling the code, rebuild the services that load the backend task definitions:

```bash
docker compose up -d --build hitrack-api worker-light worker-scan beat
```

Then save or update the periodic task in Django Admin. Celery Beat reads the database-backed schedule and queues `Periodic Repository Scan` on the `light` queue; that task dispatches individual repository scans to the scan workflow.

For other schedulable and internal task names, see [Periodic Tasks](periodic-tasks.md).

## Verification and Troubleshooting

After the schedule runs:

1. Open the HITrack task page and confirm that `Periodic Repository Scan` completed.
2. Check that its result reports repositories as queued, skipped, or failed.
3. Open repository tags and confirm that the newest tag from every expected release line was discovered.
4. Check worker logs if a repository stays pending or no tag is created:

```bash
docker compose logs --since=30m beat worker-light worker-scan
```

Common causes of missed releases are:

- `release_lines_limit` is smaller than the number of maintained lines;
- `tag_candidates_limit` is too small to include old-branch releases;
- the tag is a prerelease while `include_prerelease` is `false`;
- the tag does not begin with a version-like value;
- the repository is inactive, has no registry, or is already in process;
- the tag already exists and `process_existing` is `false`.

Invalid depths and limits fail explicitly: depth must be `1`, `2`, or `3`, and non-null limits must be positive integers.
