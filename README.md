<div align="center">
  <img src="docs/logo.png" alt="HITrack" width="160" height="160">

  # HITrack
</div>

HITrack is a self-hosted application for inventorying container images and Helm charts, generating SBOMs, storing vulnerability scan results, and reviewing how components and vulnerabilities are distributed across repositories and releases.

The backend uses Django, PostgreSQL, Redis, and Celery. Syft generates SBOMs, Grype produces vulnerability findings, and the web interface is built with Vue 3 and Vuetify.

## Supported Workflows

- Import repositories from Azure Container Registry (ACR).
- Discover JFrog Docker and Helm repo keys and the applications inside them.
- Track all tags, one latest tag, or the latest tag in each release line.
- Scan Docker images and child images referenced by Helm charts.
- Use an image already present in the Docker daemon available to the scan worker.
- Store SBOM packages, locations, dependency context, distro metadata, and Grype findings.
- Review severity, fix availability, EPSS, CISA KEV, exploit signals, and external vulnerability details.
- Compare images and group repeated exposure by component version or OS lineage.
- Group repository tags into releases and generate reports.
- Schedule discovery, enrichment, snapshot, and maintenance tasks through Django Admin.

See [Platform Capabilities](docs/capabilities.md) for the complete functional description.

## Quick Start

Requirements:

- Docker
- Docker Compose
- access to a Docker daemon for image scanning

Start the complete local stack:

```bash
git clone git@github.com:malchikserega/HITrack.git
cd HITrack
docker compose up -d --build
```

Open:

- UI: [http://127.0.0.1:1337](http://127.0.0.1:1337)
- Django Admin: [http://127.0.0.1:1337/admin/](http://127.0.0.1:1337/admin/)
- OpenAPI UI: [http://127.0.0.1:1337/api/docs/](http://127.0.0.1:1337/api/docs/)
- ReDoc: [http://127.0.0.1:1337/api/redoc/](http://127.0.0.1:1337/api/redoc/)

The API container automatically runs migrations and the initialization command when it starts.

Default bootstrap credentials are currently created when no active superuser exists:

```text
username: admin
password: P@ssw0rd
```

Set `SUPERUSER_NAME` and `SUPERUSER_PSWD` before the first start to override them.

> **Deployment note:** the checked-in Compose configuration is intended for local or controlled environments. It runs Django with `runserver`, enables development settings, exposes PostgreSQL and Redis ports, uses default database credentials, and mounts the Docker socket into backend services. Review [Operations and Deployment](docs/operations.md) before exposing HITrack outside a trusted host.

## First Configuration

1. Sign in and open **Container Registries**.
2. Add an ACR or JFrog registry with its API URL and credentials.
3. Import repositories manually or configure JFrog repository discovery.
4. Start a repository/tag scan.
5. Review the resulting images, components, vulnerabilities, and task states.
6. Configure periodic tasks only after the manual flow works for at least one repository.

For JFrog, configure the Artifactory base URL, for example:

```text
https://repo.example.com/artifactory
```

Do not include a specific repo key in the Registry API URL.

## Documentation

- [Documentation Index](docs/README.md)
- [Platform Capabilities](docs/capabilities.md)
- [Architecture and Data Flow](docs/architecture.md)
- [Registries and Repository Discovery](docs/registries.md)
- [Scanning and Result Semantics](docs/scanning.md)
- [Periodic Tasks](docs/periodic-tasks.md)
- [Operations and Deployment](docs/operations.md)
- [Periodic JFrog Repository Discovery](docs/jfrog-repository-discovery.md)
- [Release-Line Tag Scanning](docs/periodic-tag-scanning.md)

## Repository Layout

```text
HITrack/
├── HITrack/                 Django project, API, tasks, and migrations
├── HITrack-frontend/        Vue/Vuetify frontend
├── docs/                    Project documentation and screenshots
├── httpd/                   Apache reverse-proxy configuration
├── redis/                   Redis image build context
├── storage/                 Generated files and static output
├── static_data/             Additional static data
├── volume/                  Local PostgreSQL data
├── docker-compose.yml       Local full-stack configuration
└── env.env                  Default runtime variables
```

## Development Checks

Backend tests:

```bash
docker compose build hitrack-api
docker compose run --rm --no-deps --entrypoint python \
  hitrack-api manage.py test core.tests
```

Frontend type check and build:

```bash
cd HITrack-frontend
npm install
npm run type-check
npm run build
```

## License

HITrack is licensed under the [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-nc-sa/4.0/).

Contributors:

- Sergei Ovchinnikov ([@malchikserega](https://github.com/malchikserega))
- Ilya Kostyulin ([@vmvarga](https://github.com/vmvarga))
