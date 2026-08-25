# Registries and Repository Discovery

## Container Registry Records

A HITrack `ContainerRegistry` record represents one credential and API endpoint context. For JFrog, one record normally represents one Artifactory installation and the credentials used to query it.

Required values depend on the provider, but the current model stores:

- display name;
- provider;
- API URL;
- login/password or token fields;
- last successful repository discovery time;
- optional registry-level image fallback entries.

Credentials are used by backend workers. Do not place credentials in Celery Beat keyword arguments.

## Azure Container Registry

The ACR hierarchy maps directly to the HITrack model:

```text
ContainerRegistry -> Repository -> RepositoryTag
```

Use the Container Registries page to select an ACR record, browse repositories, and add selected repositories to HITrack.

## JFrog Artifactory

Configure the Artifactory base URL:

```text
https://repo.example.com/artifactory
```

Do not configure a repo-key-specific URL such as:

```text
https://repo.example.com/artifactory/docker-local
```

HITrack uses Artifactory repository APIs to discover Docker and Helm repo keys, then reads applications or charts inside each key.

Remote hierarchy:

```text
Artifactory
├── docker-local
│   ├── team/orders
│   └── team/payments
└── helm-local
    └── platform-chart
```

Stored repositories:

```text
docker-local/team/orders
docker-local/team/payments
helm-local/platform-chart
```

Each stored row keeps its `repo_key`, type, and parent Container Registry.

## Manual Import

The Container Registries UI supports a two-stage JFrog import:

1. list repo keys and their package type;
2. list the applications/charts in a selected repo key;
3. add selected items as HITrack repositories.

Newly added repositories are active unless the workflow explicitly creates them inactive.

## Periodic JFrog Discovery

Schedule `Sync JFrog Repositories` to find:

- new Docker or Helm repo keys;
- new applications in existing Docker repo keys;
- new charts in existing native Helm repo keys.

The scheduled task queues one `Sync Single JFrog Registry` child task for every selected JFrog Container Registry. The child task uses that Registry record's API URL and credentials.

Discovery creates repository records only. It does not enumerate or scan tags. Run `Periodic Repository Scan` after discovery.

Recommended ordering:

```text
01:00  Sync JFrog Repositories
02:00  Periodic Repository Scan
```

See [Periodic JFrog Repository Discovery](jfrog-repository-discovery.md) for all parameters and failure behavior.

## Repository Active State

`Periodic Repository Scan` processes repositories with `status=true`.

The JFrog discovery task defaults to `activate_new=true`, so newly discovered applications are picked up by the next tag scan. Existing repositories that were manually disabled are not re-enabled by discovery.

## Helm Image Fallback

Fallback is configured on a Container Registry and applies to all Helm repositories linked to it.

Each entry has:

- a base Docker repository URL;
- a display name;
- the UUID of the Container Registry whose credentials should be used for the fallback request.

This supports cases where a chart contains an unusable or environment-specific image reference but the same image is mirrored in another repository.

Resolution first tries the original and normalized same-registry candidates. Configured fallback entries are attempted only if those fail.

There is no repository-level fallback field. Configure and review fallback entries only on the Container Registries page.

## Local Docker Images

The scan pipeline checks whether an exact image reference exists in the Docker daemon visible to the scan worker. If it does, Syft and Grype can operate on that local image without a successful remote pull.

In the default Compose stack, workers use the mounted host Docker socket. On Docker Desktop, this normally exposes images in the Docker Desktop daemon.

Requirements:

- build or tag the image with the exact reference HITrack will scan;
- ensure the scan worker uses the same Docker daemon;
- keep the image available until the scan finishes.

Example:

```bash
docker build -t local/my-application:1.0.0 .
docker image inspect local/my-application:1.0.0
```

If HITrack stores a different name, registry prefix, or tag, the exact-reference lookup will not match.

## Registry Permissions

The configured account must be able to perform the operations used by its workflow:

- list repositories or repo keys;
- read Docker catalogs/tags;
- read manifests and blobs;
- read native Helm `index.yaml` and chart archives where applicable;
- pull or inspect images used by the scanner.

Use the least privilege that still permits these read operations. HITrack does not need permission to publish images or charts for its normal scan workflow.

## Discovery Troubleshooting

Check the worker result and logs:

```bash
docker compose logs --since=30m worker-light worker-scan
```

Common causes of missing repositories:

- wrong Artifactory base URL;
- insufficient permissions for `/api/repositories` or Docker catalog endpoints;
- package type excluded by task parameters;
- `max_projects_per_repo_key` set too low;
- another sync for the same registry holds the discovery lock;
- invalid or inaccessible Helm index;
- repository names exceeding current database field limits.
