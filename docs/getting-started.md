# Getting started

## Prerequisites

- Docker Engine with the Compose plugin
- enough disk for pulled images, PostgreSQL and raw scanner artifacts
- network access from workers to configured registries and vulnerability data sources
- credentials with read-only registry access wherever possible

## Start the local stack

```bash
git clone https://github.com/malchikserega/HITrack.git
cd HITrack
docker compose up -d --build
```

Create the first administrator explicitly. HITrack does not ship a default password:

```bash
docker compose exec hitrack-api python manage.py createsuperuser
```

Open `http://127.0.0.1:1337`, sign in, and verify that **Dashboard**, **Registries**, **Images**, **Components**, **Vulnerabilities**, **Prioritization**, and **Tasks** are available.

## First scan

1. Open **Container Registries** and create a registry.
2. Use a provider-appropriate API URL. For JFrog use the Artifactory base URL such as `https://repo.example.com/artifactory`, not a single repo-key URL.
3. Import or discover repositories.
4. Enable the repository and run a scan with a conservative tag policy such as latest only.
5. Follow the parent and child work on **Tasks**.
6. Open the image and confirm both SBOM and Grype coverage.
7. Check **Prioritization** for fixable packages and stale/incomplete images.

## Verify the installation

```bash
docker compose ps
docker compose logs --tail=100 hitrack-api worker-scan
```

The API documentation is available to authenticated users at:

- `http://127.0.0.1:1337/api/docs/`
- `http://127.0.0.1:1337/api/redoc/`

## Before production

The checked-in Compose stack is a local reference deployment. Complete the [production checklist](production.md), especially external secret management, TLS, an application server, database/Redis isolation, backup testing and Docker-socket containment.
