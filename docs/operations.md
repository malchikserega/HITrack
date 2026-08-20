# Operations and Deployment

## Intended Use of the Checked-In Stack

The current `docker-compose.yml` is a complete local or controlled-environment stack. It is useful for development, evaluation, and an internally protected installation. It is not a hardened public production deployment.

The public entry point is bound to localhost:

```text
http://127.0.0.1:1337
```

## Start and Stop

Build and start all services:

```bash
docker compose up -d --build
docker compose ps
```

Follow startup:

```bash
docker compose logs -f hitrack-api worker-light worker-scan worker-enrichment beat
```

Stop containers without deleting PostgreSQL files:

```bash
docker compose down
```

Do not add `-v` unless you have deliberately reviewed which named volumes can be removed. PostgreSQL is currently stored in the bind-mounted `volume/` directory.

## Migrations and Initialization

The default API command is `dev`. On every API container start, its entrypoint runs:

```text
collectstatic -> migrate -> init -> runserver
```

Therefore a normal `docker compose up -d --build` applies migrations automatically. Run migrations manually when you want a visible, controlled deployment step or when diagnosing startup:

```bash
docker compose exec hitrack-api python manage.py migrate
```

The initialization command currently creates a superuser if no active superuser exists. Its checked-in defaults are `admin` / `P@ssw0rd`; set `SUPERUSER_NAME` and `SUPERUSER_PSWD` before first startup and change existing default credentials immediately.

## Upgrade Procedure

For an internal installation:

1. read new migrations and release notes;
2. back up PostgreSQL and the generated storage required by your retention policy;
3. pull the intended Git branch or commit;
4. rebuild the backend and frontend images;
5. start the database, Redis, and API;
6. verify migrations;
7. run any release-specific backfill;
8. start/verify all workers and Beat;
9. test one scan and the affected UI pages.

Typical commands after the backup:

```bash
git pull --ff-only
docker compose build
docker compose up -d
docker compose exec hitrack-api python manage.py migrate
docker compose ps
```

Migration `0022_remove_repository_image_fallback_repositories` removes the obsolete repository-level Helm fallback field. Before applying it to an older database, verify that every required fallback is present on the associated Container Registry. The migration intentionally does not copy ambiguous repository-level values.

## Image Vulnerability Summary Backfill

Run this once after an upgrade that changes image counter, ecosystem, unique-vulnerability, or fix-summary semantics:

```bash
docker compose exec hitrack-api python manage.py backfill_image_vulnerability_summaries
```

Run migrations first. The command rebuilds persisted summaries for existing images; normal new scans use the current summary schema automatically.

By default it skips images already stored with summary schema version 2. To deliberately rebuild every image during a repair, add `--force`; use `--batch-size N` to change the iterator batch size.

The task `Backfill Image SBOM Security Metadata` also rebuilds broader stored SBOM security metadata in batches. Use it through Django Admin only when that upgrade path calls for the wider backfill.

To recalculate fix availability from already stored Grype payloads without rescanning, run the registered task `Recalculate Vulnerability Fix Availability` as controlled maintenance.

## Database Backup

Create a logical PostgreSQL backup on the host:

```bash
docker compose exec -T hitrack-db pg_dump -U hitrack -d hitrack > hitrack-backup.sql
```

Verify that the output file is non-empty and protect it as sensitive data because the current schema contains registry credentials.

Restoring overwrites database state and should be tested in a separate environment first. Stop API/workers, create a fresh target database, then use `psql` with the reviewed backup. Do not restore into a live database while Celery workers are writing to it.

## Services and Queues

All of these must be healthy for the complete workflow:

| Service | Operational role |
| --- | --- |
| `hitrack-api` | API, Admin, startup migrations, initialization. |
| `worker-light` | orchestration and short jobs. |
| `worker-scan` | tag, Helm, image, Syft, and Grype work. |
| `worker-enrichment` | external details, backfills, and analytics. |
| `beat` | database-backed periodic schedule. |
| `hitrack-db` | durable application and task-result data. |
| `hitrack-redis` | broker and cache. |

Current default concurrency is configured in `docker-compose.yml`. Increase it only after measuring registry limits, CPU, memory, disk I/O, database load, and external API limits. Scan tasks are substantially heavier than orchestration tasks.

## Logs and Basic Diagnostics

Service state:

```bash
docker compose ps
```

Recent backend logs:

```bash
docker compose logs --since=30m hitrack-api worker-light worker-scan worker-enrichment beat
```

Database and Redis health:

```bash
docker compose exec hitrack-db pg_isready -U hitrack
docker compose exec hitrack-redis redis-cli ping
```

Inspect registered Django migrations:

```bash
docker compose exec hitrack-api python manage.py showmigrations
```

Use the Tasks page for stored Celery results. For orchestration tasks, open the result payload and follow returned child task IDs.

## Common Problems

### A task finishes immediately

Many parent tasks only select records and queue child tasks. Check `status`, summary counts, skipped reasons, and child IDs in the result. Then check the target records and the worker for the child's queue.

### A task remains pending

Confirm that the worker consuming its queue is running. Repository/image work needs `worker-scan`; external data and snapshots may need `worker-enrichment`; orchestration usually needs `worker-light`.

### Local image is not found

The worker must use the same Docker daemon and the exact stored reference. Compare the intended reference with:

```bash
docker image inspect local/my-application:1.0.0
```

### Reports or release selectors are slow

First verify API and database logs, then confirm the release has completed tags/images and that required summary backfills ran after an upgrade. Avoid overlapping mass rescans, enrichment batches, and report generation on a small database host.

### JFrog discovery finds no applications

Check the Artifactory base URL, API permissions, included package types, project limits, and the per-registry child result. See [Registries and Repository Discovery](registries.md).

## Current Security and Production Gaps

The repository currently includes these deployment characteristics:

- Django `DEBUG=True`, wildcard hosts/CORS behavior, and a hard-coded secret key;
- predictable bootstrap and database defaults unless overridden;
- registry credentials stored in the application database;
- Django `runserver` in the default Compose path;
- a `service` entrypoint that references `config.wsgi`, which is not the project's WSGI module;
- no application health check on the API service;
- exposed PostgreSQL and Redis host ports;
- the host Docker socket mounted into the API and all worker containers.

The Docker socket grants capabilities comparable to host root access if a mounted container is compromised. Keep the current stack on a trusted host and network.

Before public or multi-tenant deployment, at minimum:

- use environment/secret-managed Django and database credentials;
- separate development and production settings and define explicit domains/CORS policy;
- use a supported WSGI server with `HITrack.wsgi` and add health checks;
- remove unnecessary host port exposure;
- isolate Docker pull/Syft/Grype execution in a constrained scan runner instead of mounting the socket into web/orchestration services;
- move registry credentials to a secret store or encrypt them with a key held outside PostgreSQL;
- set resource limits, backup/restore tests, monitoring, log retention, and TLS/authentication at the ingress.

These are deployment requirements; the checked-in Compose file does not implement them yet.

## Development Checks

Backend test suite using the built image:

```bash
docker compose build hitrack-api
docker compose run --rm --no-deps --entrypoint python hitrack-api manage.py test core.tests
```

Frontend checks:

```bash
cd HITrack-frontend
npm install
npm run type-check
npm run build
```
