# Periodic JFrog Repository Discovery

[Back to the documentation index](README.md)

HITrack stores ACR and JFrog applications in the same `Repository` model even though their remote hierarchies differ:

```text
ACR:   Registry -> Repository/Application -> Tag
JFrog: Registry -> Repo key -> Application/Chart -> Tag
```

For JFrog, every application or chart is represented as a scan-ready HITrack repository:

```text
name:            <repo-key>/<application>
repo_key:        <repo-key>
repository_type: docker or helm
container_registry: the JFrog registry containing its own credentials
```

The `Sync JFrog Repositories` periodic task queues one independent `Sync Single JFrog Registry` job for every selected JFrog registry. Those jobs discover new repo keys and applications and create the records. Different Artifactory instances can therefore synchronize in parallel and report failures independently. The workflow deliberately does not scan tags. The existing `Periodic Repository Scan` task later discovers and processes tags for all active repositories.

## Discovery Flow

The scheduled orchestration task first selects the JFrog registries and queues one child job per registry. Every child job:

1. authenticates with that registry's own stored credentials;
2. requests Docker and/or Helm repo keys from the Artifactory REST API;
3. reads every Docker repo key through the paginated Docker catalog;
4. reads chart names from every selected Helm index;
5. builds canonical `<repo-key>/<application>` repository records;
6. bulk-creates missing records and repairs source metadata on matching records;
7. updates the registry's `last_sync` only after a fully successful synchronization.

The operation is idempotent. Repeated runs do not duplicate applications. Existing repository scan state and the user-controlled `status` flag are preserved. A repository manually disabled in HITrack is not silently re-enabled. `activate_new` affects newly created records only.

Failures are isolated. A broken repo key does not prevent applications from other repo keys or registries from being created. Such a registry job returns `partial`, records detailed errors in its result, and does not advance `last_sync`. A cache lock prevents overlapping cron executions from synchronizing the same registry concurrently.

An empty repo key does not create a placeholder database record. Once its first application appears, that application is discovered and the repo key is persisted on the new `Repository` record.

## Django Admin Configuration

Open [Django Admin](http://127.0.0.1:1337/admin/) and then:

1. Open **Periodic tasks** under **Django Celery Beat**.
2. Create a periodic task.
3. Set **Name** to `Daily JFrog repository discovery` or another descriptive name.
4. Set **Task (registered)** to `Sync JFrog Repositories`.
5. Select a crontab or interval schedule.
6. Set **Arguments** to `[]`.
7. Put the configuration below in **Keyword arguments**.
8. Enable and save the task.

Every keyword parameter is optional. Use `{}` to process every JFrog registry with the defaults:

```json
{}
```

The equivalent expanded configuration is:

```json
{
  "include_docker": true,
  "include_helm": true,
  "activate_new": true,
  "catalog_page_size": 500,
  "max_projects_per_repo_key": null,
  "batch_size": 500
}
```

No credentials belong in the periodic-task arguments. They are read separately from every `ContainerRegistry` record.

### Synchronize One Registry Only

Omit `registry_uuid` to process every configured JFrog registry. To create a separate schedule for one registry, add its UUID:

```json
{
  "registry_uuid": "11111111-2222-3333-4444-555555555555",
  "include_docker": true,
  "include_helm": true,
  "activate_new": true,
  "catalog_page_size": 500,
  "max_projects_per_repo_key": null,
  "batch_size": 500
}
```

The selected UUID must belong to a registry whose provider is `jfrog`; otherwise the task fails explicitly.

`Sync Single JFrog Registry` is an internal child task. Do not create a separate periodic schedule for it; schedule only `Sync JFrog Repositories`.

## Parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `registry_uuid` | `null` | Restrict discovery to one JFrog registry. Omit it to process all JFrog registries. |
| `include_docker` | `true` | Discover Docker repo keys and applications. |
| `include_helm` | `true` | Discover native Helm repo keys and charts. |
| `activate_new` | `true` | Make newly discovered repositories active so the tag task can scan them. Does not change existing records. |
| `catalog_page_size` | `500` | Number of Docker catalog entries requested per page. Must be positive. |
| `max_projects_per_repo_key` | `null` | Optional safety cap per repo key. `null` discovers every project. |
| `batch_size` | `500` | Database create/update batch size. Must be positive. |

For complete inventory, keep `max_projects_per_repo_key` as `null`. A cap is useful only when initially evaluating a very large Artifactory instance; projects beyond the cap will not be imported during that run.

## Scheduling with Tag Discovery

Run JFrog structure discovery before the existing tag scan. For example:

```text
01:00  Sync JFrog Repositories
02:00  Periodic Repository Scan
```

The gap should be longer than the slowest normal per-registry discovery duration in your environment. The tasks are intentionally separate: discovery does not immediately start a potentially large scan wave. Newly created repositories have `status=true` by default and are automatically included in the next `Periodic Repository Scan` run.

If you use `activate_new: false`, review and enable the new repositories manually before tag discovery can process them.

## Deployment with Docker

The discovery feature itself adds no model fields or feature-specific backfill. Still run the normal project migration step when upgrading the complete branch, because the branch may contain unrelated migrations. Rebuild the services that register, schedule, and execute the task:

```bash
docker compose up -d --build hitrack-api worker-light beat
```

Then create the schedule in Django Admin. `Sync JFrog Repositories` is routed to the `light` Celery queue.

For the shorter task catalog and cadence guidance, see [Periodic Tasks](periodic-tasks.md).

## Verification and Troubleshooting

After the first run, the `Sync JFrog Repositories` result lists the queued child task ID for every registry. Inspect the corresponding `Sync Single JFrog Registry` results. Each contains:

- whether the registry was processed, partially processed, or skipped;
- projects discovered;
- repository records created;
- repo-key counts and detailed errors.

Confirm that newly discovered records appear under **Repositories** with:

- a name such as `docker-local/apps/orders`;
- the correct registry;
- the expected `repo_key`;
- type `docker` or `helm`;
- active status when `activate_new` is enabled.

Useful logs:

```bash
docker compose logs --since=30m beat worker-light
```

Common causes of partial or failed discovery are:

- the registry API URL does not point to the Artifactory base path;
- the registry credentials cannot list repositories or catalogs;
- a repo key is inaccessible to the configured user;
- a native Helm repository has no readable `index.yaml`;
- a proxy or Artifactory request times out;
- a project name or canonical URL exceeds the current 255-character database limit;
- another discovery run for the same registry is still active.

The task never deletes repositories that disappear from Artifactory. Automatic deletion would risk removing historical scan data. Disable or remove such repositories manually after review.
