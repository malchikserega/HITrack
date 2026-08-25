# Architecture and Data Flow

## Runtime Services

The default Compose stack contains these services:

| Service | Responsibility |
| --- | --- |
| `httpd` | Public entry point on `127.0.0.1:1337`; proxies the UI and API. |
| `hitrack-frontend` | Static Vue 3/Vuetify application served by Nginx. |
| `hitrack-api` | Django REST API, Django Admin, migrations, initialization, and static-file collection. |
| `worker-light` | Celery orchestration, short maintenance tasks, and fan-out jobs. |
| `worker-scan` | Registry tag processing, Helm image discovery, Syft, Grype, and scan parsing. |
| `worker-enrichment` | External vulnerability enrichment, metadata backfills, threat intelligence, and analytics snapshots. |
| `beat` | Database-backed Celery Beat scheduler. |
| `hitrack-db` | PostgreSQL data store. |
| `hitrack-redis` | Celery broker and Django cache. |

The backend image includes Docker CLI, Syft, Grype, and Helm.

## Celery Queues

HITrack defines three queues:

```text
light       orchestration and short maintenance work
scan        image, tag, SBOM, Helm, and Grype work
enrichment  external data collection, backfills, and analytics snapshots
```

Queue routing is configured in `HITrack/HITrack/settings.py`. The registered task name, not the Python function path, is used by Django Celery Beat.

Orchestration tasks normally return after queueing child tasks. A successful parent result therefore means the children were queued; it does not mean all child scans succeeded. Use the Tasks page and child task IDs to follow the complete workflow.

## Registry and Repository Model

`ContainerRegistry` stores the provider, API URL, credentials, last successful discovery timestamp, and Helm fallback policy.

`Repository` is the scan policy boundary. It stores an active flag, scan state, repository type, registry link, and optional JFrog repo key.

The JFrog mapping is intentionally flattened:

```text
Artifactory ContainerRegistry
└── repo key: docker-local
    └── application: team/orders

HITrack Repository
├── name: docker-local/team/orders
├── repo_key: docker-local
├── repository_type: docker
└── container_registry: Artifactory ContainerRegistry
```

`RepositoryTag` belongs to one repository. An image can be linked to multiple tags when they resolve to the same stored image identity.

## Image and Scan Model

`Image` stores the resolved name, digest, artifact reference, raw SBOM, raw Grype data, scan state, and derived image metadata.

Durable scan records include:

- `ScanRun`: idempotency key, state, attempt count, lease, task ID, and scanner/policy versions;
- `ScanArtifact`: stored raw scanner artifacts and checksums;
- `AuditEvent`: append-only records for API mutations and explicit security decisions.

Image deduplication primarily uses normalized image name and digest. Existing historical duplicates can be repaired by `Deduplicate Images by Identity`.

## Component Model

The main component relationships are:

```text
Image
├── ComponentVersion
│   └── Component
├── ImageComponentVersionContext
└── ComponentLocation
```

`Component` and `ComponentVersion` are shared across images. Image-specific dependency, distro, architecture, source-package, and location data is stored in context/location records.

## Vulnerability Model

`Vulnerability` stores the identifier, type, base severity, description, and EPSS value used by list views.

`ComponentVersionVulnerability` connects a component version to a vulnerability and stores normalized fix metadata:

- raw fix text and state;
- structured fixed-in versions;
- normalized fix status;
- compatibility boolean used by older views.

`VulnerabilityDetails` stores external enrichment, timestamps for attempted and successful updates, source labels, CISA KEV, EPSS, and exploit-related fields.

Image summary data is derived from image/component/finding relationships and may also be persisted for fast image-detail responses. When derived schema changes, a documented backfill may be required for older images.

## Release and Snapshot Models

`Release` groups repository tags through `RepositoryTagRelease`.

Snapshot models store data used by:

- repository-tag deltas;
- weekly threat intelligence;
- shared component root causes;
- base-lineage root causes.

Snapshot-backed pages do not imply that snapshots are scheduled. Configure the corresponding periodic tasks explicitly.

## Standard Scan Flow

```text
Registry discovery
  -> Repository
  -> Tag discovery and selection
  -> RepositoryTag
  -> Docker image or Helm child image resolution
  -> Image / ScanRun
  -> Syft SBOM
  -> components, versions, contexts, and locations
  -> Grype findings
  -> vulnerabilities and fix metadata
  -> image/tag/repository status and summaries
```

Detailed scan semantics are documented in [Scanning and Result Semantics](scanning.md).

## Helm Fallback Ownership

Fallback repositories are stored only in `ContainerRegistry.image_fallback_repositories`. A fallback entry contains:

```json
{
  "url": "registry.example/docker-local",
  "name": "docker-local",
  "registry_uuid": "UUID of the registry that supplies credentials"
}
```

The policy applies to all Helm repositories linked to that Container Registry. Repository-level fallback storage was removed to avoid two conflicting sources of configuration.

## Storage

The default stack uses:

- PostgreSQL bind-mounted under `volume/`;
- generated/static files under `storage/` and `static_data/`;
- Django database result backend for Celery task results;
- Redis for Celery messages and Django cache.

Raw scan artifact storage uses Django storage abstractions. The checked-in configuration uses local filesystem storage.

## Reference Deployment Characteristics

The repository keeps development-oriented runtime choices in its local Compose profile:

- Django debug mode (explicit in `env.env`);
- API started with Django `runserver` by the default Compose command;
- default local database credentials;
- loopback host bindings for PostgreSQL and Redis;
- Docker socket mounted only into the scan worker.

Production mode requires an explicit secret and allowed hosts and defaults to restricted CORS. These controls do not turn the local Compose profile into a production design. See the [Production checklist](production.md).
