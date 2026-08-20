<div align="center">
  <img src="docs/logo.png" alt="HITrack Logo" width="200" height="200">

  # HITrack
  ### Container, Helm, SBOM, Vulnerability, Threat-Intel, and Root-Cause Tracking Platform

  [![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
  [![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
  [![Vue.js](https://img.shields.io/badge/Vue.js-3.4+-green.svg)](https://vuejs.org/)
  [![Django](https://img.shields.io/badge/Django-5.0+-darkgreen.svg)](https://www.djangoproject.com/)
</div>

HITrack is a self-hosted platform for tracking security exposure across container repositories, Helm charts, images, components, vulnerabilities, releases, and shared root causes.

It is built for teams that need more than "scan image, list CVEs". HITrack combines inventory, SBOM parsing, vulnerability enrichment, release-aware analysis, threat-intelligence correlation, and cross-repository analytics in one platform.

Core technologies:

- Syft for SBOM generation
- Grype for vulnerability matching
- Django + Django REST Framework for API and domain model
- Celery + Redis for asynchronous orchestration
- PostgreSQL for storage and analytics
- Vue 3 + Vuetify for the UI

<p align="center">
  <img src="docs/metrics.png" width="500" alt="HITrack dashboard" />
  <img src="docs/vulnview.png" width="500" alt="HITrack vulnerability view" />
</p>

## Overview

HITrack focuses on the questions security and platform teams actually ask:

- What is in this image or Helm release?
- Which vulnerabilities are truly present right now?
- Is a finding fixable here, or is the fix missing from the package repository?
- Did the latest scan or release introduce new risk?
- Which new advisories from this week are relevant to our environment?
- What shared package or distro is creating the same problem across many repositories?

The platform is designed around a few core ideas:

- continuous repository and tag scanning
- shared component and vulnerability tracking across many images
- release-aware reporting and scan delta analysis
- threat-intelligence correlation against local data
- root-cause analytics that explain repeated exposure
- operational safety nets such as backfills, deduplication, snapshot jobs, and repair tasks

## Core Capabilities

### 1. Repository and Registry Workflows

HITrack can ingest repositories manually or from configured registries.

Current first-class workflows include:

- Azure Container Registry (ACR)
- JFrog Artifactory
- Docker repositories
- Helm repositories and OCI-style Helm artifacts

Repositories can be classified as:

- `docker`
- `helm`
- `none`

Container registries can define fallback Docker repositories for cases where Helm chart image references are incomplete or inconsistent. The registry-level policy applies to all Helm repositories linked to that registry.

### 2. Tag and Image Scanning

HITrack supports multiple scanning modes:

- scan full repository tag history
- scan only the latest tag
- scan the latest tag in every supported major or major/minor release line
- periodically process all active repositories
- manually process tags from the UI
- rescan stored images
- rerun Grype against existing SBOM data

For Docker repositories, tags resolve to images directly.

For Helm repositories, HITrack:

1. discovers the chart artifact
2. extracts child image references from the chart
3. resolves real pull targets with fallback logic where needed
4. scans those child images through the standard image pipeline

The platform also tracks effective processing state correctly across tag and image relationships, so repository/tag status reflects whether child images are still pending, in progress, successful, or failed.

See [Periodic Release-Line Tag Scanning](docs/periodic-tag-scanning.md) for the selection algorithm, Django Admin configuration, ready-to-use JSON examples, and upgrade instructions.

### 3. SBOM Generation, Parsing, and Persisted Image Metadata

For each image, HITrack can:

- generate an SBOM with Syft
- persist raw SBOM data
- parse SBOM artifacts into shared `Component` and `ComponentVersion` records
- link components back to images
- store component locations inside the image
- preserve package identifiers such as PURLs and CPEs

In addition to shared component records, HITrack stores image-specific security metadata derived from SBOM data. This avoids recalculating expensive metadata on every analytics request.

Persisted image-level metadata includes:

- `lineage_label`
- `lineage_source`
- `os_distro_name`
- `os_distro_version`
- `lineage_updated_at`
- `os_eol_status`
- `os_eol_source`
- `os_eol_message`
- `os_eol_checked_at`

HITrack also stores per-image component context without changing component identity globally. This preserves image-specific SBOM facts while keeping `Component` and `ComponentVersion` shared across the whole platform.

Stored image-component context includes:

- dependency scope: `direct`, `transitive`, `unknown`
- dependency depth
- immediate parent package
- direct introducer package
- package architecture
- package distro context
- package repository / channel
- source package metadata
- cataloger / metadata type details where available

This is especially useful for:

- understanding why a transitive package is present
- grouping images by shared OS lineage
- improving fixability interpretation
- supporting root-cause analytics without re-parsing large SBOM payloads every time

Important note:

- HITrack's persisted lineage data represents **OS / distro lineage derived from SBOM data**
- it is **not** the exact Dockerfile `FROM` instruction

### 4. Vulnerability Tracking and Enrichment

HITrack tracks vulnerabilities through `ComponentVersionVulnerability` relationships and enriches them with additional intelligence.

It stores and surfaces:

- severity
- description
- EPSS
- exploit signals
- CISA KEV status
- fixability metadata
- enriched advisory details

The enrichment layer supports:

- CVE detail refresh
- EPSS
- CISA KEV
- exploit-availability signals
- GitHub advisories
- GHSA identifiers
- OSV-backed advisory correlation

Bulk enrichment runs separately from heavy scan work so metadata refresh jobs do not starve tag/image scanning throughput.

### 5. Fixability and Package Update Intelligence

HITrack does more than show a binary "fix available" value.

It tracks fixability states such as:

- `fixable now`
- `fix exists but not in repo`
- `no fix`
- `fix unknown`

It also supports newest-version workflows for components, including:

- global latest-version refresh
- per-image latest-version refresh
- `deb`-only latest-version refresh
- distro-aware Debian and Ubuntu newest-version lookup where possible

There is also a maintenance task to recalculate fix availability from stored Grype data without rescanning images.

### 6. Releases, Deltas, and Change Tracking

HITrack can group repository tags into releases and analyze them as deployment units rather than isolated scans.

Release workflows include:

- creating releases
- assigning repository tags to releases
- viewing release contents in detail
- showing scan progress of tags included in a release
- scanning only the unscanned tags in a release
- generating release-focused reports

The platform also supports delta-style analytics such as:

- new vulnerabilities since the previous scan snapshot
- fixed vulnerabilities
- severity increases
- new KEV-relevant issues

### 7. Threat Intelligence

HITrack includes a weekly threat-intelligence layer with stored snapshots.

Current sources include:

- CISA KEV
- GitHub advisories
- OSV
- weekly "observed in HITrack" signals based on newly seen local vulnerabilities

Threat-intel entries are matched back to local data using:

- advisory identifiers
- aliases
- GHSA IDs
- CVE IDs
- OSV IDs

The weekly threat-intel model distinguishes between:

- `Observed In HITrack`
  first seen by this platform during the current week
- `Relevant`
  exists somewhere in HITrack's historical data
- `Present`
  currently present in active image/component relationships

The UI also explains:

- why a match was made
- which identifier matched
- where it is currently seen inside HITrack

Threat-intel entries can also carry source/attribute tags such as:

- `OSV`
- `GitHub`
- `Malware`
- `Fix available`
- `No fix available`

### 8. Root-Cause and Comparison Analytics

HITrack includes several analytics views focused on explaining repeated exposure instead of just listing findings.

Available views:

- **Image Comparisons**
  compare logically equivalent images across registries and repositories by logical name
- **Shared Root Causes**
  group by shared vulnerable component version across repositories and images
- **Base Images & Distros**
  group by persisted OS / distro lineage

These views surface:

- affected repositories
- affected tags
- affected releases
- affected images
- critical/high counts
- KEV / exploit signals
- weighted risk score
- fixability summary

To keep these views usable on larger datasets, HITrack stores analytics snapshots and lazy-loads detail sections such as:

- affected repositories
- top components
- top vulnerabilities

### 9. Dashboard, Activity, and Data-Heavy UI Workflows

The UI includes dedicated pages for:

- repositories
- repository tags
- images
- image comparisons
- components
- component versions
- vulnerabilities
- vulnerability detail and affected images
- releases
- tasks
- recent activities
- weekly threat intel
- shared root causes
- base images and distros
- component matrix
- report generation

The dashboard now combines:

- overview and security metrics
- vulnerability trend and distributions
- top-risk lists
- recent activity
- weekly threat intel
- weighted risk rankings
- fixability analytics
- recent scan delta summaries
- root-cause previews

Notable UI behavior includes:

- server-side pagination and sorting for large tables
- live status refresh for long-running scan operations
- notifications for user-triggered actions
- compact, data-dense tables instead of oversized cards where appropriate
- clickable recent-activity items
- threat-intel banners on vulnerability detail pages

## What HITrack Stores

### Main Entities

- `Repository`
- `RepositoryTag`
- `Image`
- `Component`
- `ComponentVersion`
- `ImageComponentVersionContext`
- `ComponentVersionVulnerability`
- `Release`
- `Vulnerability`
- `VulnerabilityDetails`

### Important Derived and Snapshot Data

- persisted image lineage and EOL metadata
- image-component SBOM context
- threat-intel snapshots
- root-cause analytics snapshots
- repository-tag scan snapshots

This lets HITrack answer both low-level questions:

- "What packages are in this image?"
- "Is this vulnerability fixable here?"
- "Which transitive dependency introduced this package?"

and higher-level questions:

- "Which repositories are affected by the same component root cause?"
- "Did this release introduce new KEV-relevant issues?"
- "Which weekly advisories are actually present in our environment?"

## Scan Pipeline

At a high level, the standard scan flow is:

1. Discover repository tags
2. Select the target tag or latest-only candidate
3. Resolve a Docker image or extract child images from a Helm chart
4. Create or reuse `Image` records
5. Generate SBOM with Syft
6. Parse SBOM into shared components and image-specific metadata
7. Persist lineage, EOL, and component-context data
8. Run Grype
9. Persist vulnerabilities and fixability metadata
10. Recompute effective tag / repository status
11. Update analytics or snapshots when required

Safety-net and repair workflows also exist, including:

- image deduplication by identity
- lineage backfill
- SBOM security metadata backfill
- fixability recalculation
- threat-intel snapshot collection
- root-cause snapshot collection

## Architecture

The default `docker-compose.yml` starts the full platform:

- `httpd`
  reverse proxy and public entrypoint on `127.0.0.1:1337`
- `hitrack-frontend`
  Vue 3 + Vuetify UI
- `hitrack-api`
  Django API, admin, migrations, initialization, and dev server
- `worker-light`
  Celery worker for lightweight orchestration, maintenance, and admin-friendly tasks
- `worker-scan`
  Celery worker for heavy scan tasks such as tag processing, SBOM generation, Helm discovery, Grype, and rescans
- `worker-enrichment`
  Celery worker for vulnerability enrichment, threat intelligence, newest-version refresh, snapshot building, and metadata backfills
- `beat`
  dedicated Celery Beat service using `django-celery-beat`
- `hitrack-db`
  PostgreSQL 17
- `hitrack-redis`
  Redis broker / backend

### Queue Split

Celery work is intentionally separated:

- `light`
  lightweight and orchestration tasks
- `scan`
  image/tag scanning and processing
- `enrichment`
  vulnerability enrichment, threat intelligence, newest-version refreshes, snapshot jobs, and metadata maintenance

This split keeps heavy scanning, background maintenance, and enrichment work from starving each other.

### Runtime Notes

- The backend container mounts `/var/run/docker.sock` because scanning workflows invoke Docker CLI from inside the app container.
- The backend image installs `syft`, `grype`, `helm`, and Docker CLI during build.
- Persistent local data is stored in folders such as `storage/`, `static_data/`, and `volume/`.

## Quick Start

### Prerequisites

- Docker
- Docker Compose
- access to the host Docker socket

### 1. Clone the repository

```bash
git clone git@github.com:malchikserega/HITrack.git
cd HITrack
```

### 2. Review environment settings

Default runtime settings live in [`env.env`](env.env).

Out of the box, the stack expects:

- PostgreSQL at `hitrack-db:5432`
- Redis at `hitrack-redis:6379`
- time zone `America/New_York`

Optional admin bootstrap variables:

- `SUPERUSER_NAME`
- `SUPERUSER_PSWD`

If they are not set, HITrack creates a default superuser with:

- Username: `admin`
- Password: `P@ssw0rd`

### 3. Start the platform

```bash
docker compose up --build -d
```

The first build can take a while because the backend image installs scanner and runtime tooling.

### 4. Open the platform

- UI: [http://127.0.0.1:1337](http://127.0.0.1:1337)
- Django admin: [http://127.0.0.1:1337/admin/](http://127.0.0.1:1337/admin/)
- Swagger UI: [http://127.0.0.1:1337/api/docs/](http://127.0.0.1:1337/api/docs/)
- ReDoc: [http://127.0.0.1:1337/api/redoc/](http://127.0.0.1:1337/api/redoc/)

### 5. First-use flow

1. Sign in with the admin account.
2. Add one or more registries.
3. Import repositories or create them manually.
4. Trigger a scan for a repository or latest tag.
5. Review results in repositories, images, vulnerabilities, components, releases, threat intel, analytics, and task management.

## Main UI Areas

### Inventory and Scanning

- `/repositories`
- `/repositories/:uuid`
- `/repository-tags/:uuid/images`
- `/images`
- `/images/:uuid`

### Vulnerability and Component Analysis

- `/vulnerabilities`
- `/vulnerabilities/:uuid`
- `/components`
- `/components/:uuid`
- `/component-versions/:uuid`
- `/images/:uuid/component-locations`
- `/component-matrix`

### Analytics and Operations

- `/`
- `/activities`
- `/threat-intel`
- `/image-comparisons`
- `/root-causes`
- `/base-lineage-root-causes`
- `/releases`
- `/tasks`
- `/reports`

## Periodic Tasks and Maintenance

HITrack supports scheduled jobs through `django-celery-beat` and manual operational triggers from the Task Management UI.

Examples of useful built-in tasks:

- `Sync JFrog Repositories`
- `Periodic Repository Scan`
- `Collect Weekly Threat Intel Snapshot`
- `Cleanup Threat Intel Snapshots`
- `Collect Root Cause Analytics Snapshot`
- `Collect Shared Root Cause Analytics Snapshot`
- `Collect Base Lineage Root Cause Analytics Snapshot`
- `Cleanup Root Cause Analytics Snapshots`
- `Deduplicate Images by Identity`
- `Backfill Image Lineage Fields`
- `Backfill Image SBOM Security Metadata`
- `Update All Vulnerability Details`
- `Update Critical Vulnerability Details`
- `Update All Components Latest Versions`
- `Update Deb Components Latest Versions`
- `Recalculate Vulnerability Fix Availability`

Recommended operating pattern:

- discover new JFrog repo keys and applications before repository tag scanning
- run repository scanning continuously or on a schedule
- collect threat-intel snapshots daily
- collect root-cause snapshots periodically
- refresh vulnerability enrichment on a schedule
- use dedupe / cleanup / backfill tasks after upgrades or when importing older data

### Suggested Cadence

This depends on your environment, but a practical starting point is:

- `Sync JFrog Repositories`
  daily, before `Periodic Repository Scan`
- `Periodic Repository Scan`
  every few hours or nightly
- `Collect Weekly Threat Intel Snapshot`
  daily
- `Collect Root Cause Analytics Snapshot`
  daily or after large scan batches
- `Update Critical Vulnerability Details`
  daily
- `Update All Vulnerability Details`
  daily or weekly depending on scale
- `Update Deb Components Latest Versions`
  daily or weekly depending on how often you use newest-version analytics
- `Deduplicate Images by Identity`
  daily as a safety net

For configuration details, see [Periodic JFrog Repository Discovery](docs/jfrog-repository-discovery.md) and [Periodic Release-Line Tag Scanning](docs/periodic-tag-scanning.md).

## Development

### Recommended Local Setup

For most development work, run infrastructure with Docker Compose and edit backend/frontend code locally.

### Backend

```bash
cd HITrack
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Start dependencies:

```bash
cd ..
docker compose up -d hitrack-db hitrack-redis
```

Run the backend locally:

```bash
cd HITrack
python manage.py migrate
python manage.py init
python manage.py runserver 0.0.0.0:8000
```

If you want real scanning workflows outside Docker, your local environment also needs:

- `syft`
- `grype`
- `helm`
- Docker CLI with access to a Docker daemon

### Celery Workers

Run workers according to the task type you are working on:

```bash
cd HITrack
celery -A hitrack_celery worker --queues=light --loglevel=INFO
celery -A hitrack_celery worker --queues=scan --loglevel=INFO
celery -A hitrack_celery worker --queues=enrichment --loglevel=INFO
```

Run beat separately:

```bash
cd HITrack
celery -A hitrack_celery beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=INFO
```

### Frontend

```bash
cd HITrack-frontend
npm install
export VITE_API_URL=http://localhost:8000/api
npm run dev
```

## API and Auth

- API base path: `/api/`
- JWT endpoints:
  - `/api/auth/token/`
  - `/api/auth/token/refresh/`
  - `/api/auth/token/verify/`
- OpenAPI schema:
  - `/api/schema/`
  - `/api/docs/`
  - `/api/redoc/`

## Operational Notes

### Helm Discovery

HITrack processes Helm repositories by discovering child images referenced by a chart and then scanning those child images normally.

Because real-world charts are often incomplete or opinionated, the platform includes resilience around chart image discovery, including:

- Helm render-based extraction
- fallback extraction paths
- same-registry resolution logic
- more defensive error handling when chart rendering fails

### Image Identity

For deduplication and reuse, the platform treats image identity primarily as:

- image `name`
- image `digest`

This matters for:

- scan reuse
- duplicate cleanup
- shared-image processing across multiple tags
- consistent vulnerability/component reuse where the actual artifact is the same

### OS Lineage vs Real Base Image

The "Base Images & Distros" analytics page uses persisted **OS / distro lineage** derived from SBOM data.

That means:

- it is highly useful for vulnerability analytics
- it is reliable for grouping OS-level exposure
- it is not the same thing as the exact Dockerfile `FROM`

### Shared Components vs Image-Specific Metadata

HITrack intentionally keeps `Component` and `ComponentVersion` shared across the whole platform.

Image-specific facts derived from SBOM parsing are stored separately in image context records. This avoids duplicating global component identity while still preserving security-relevant details such as:

- direct vs transitive dependency
- introducer chain
- package architecture
- distro/repository/channel context

## Troubleshooting

### Artifactory: use the base URL, not a repo-key path

For JFrog setup, use the Artifactory base URL so HITrack can discover repository keys through the REST API.

- Correct: `https://repo.example.com/artifactory`
- Wrong: `https://repo.example.com/artifactory/some-docker-repo`

HITrack uses the base URL to query Artifactory APIs such as `GET /api/repositories`, then lets you select the relevant Docker or Helm repo keys.

### Superuser credentials

If you want to override the default admin account, set these before startup:

```bash
export SUPERUSER_NAME=myadmin
export SUPERUSER_PSWD='replace-me'
docker compose up --build -d
```

### Large analytics pages

Pages such as root-cause analytics and base-lineage analytics are designed to use snapshot-backed data on larger environments.

If they feel cold or sparse after deployment:

1. run the relevant snapshot collection task
2. allow it to finish
3. refresh the UI

This is especially important after introducing new analytics schema fields or after large data imports.

### Post-upgrade metadata backfills

After upgrades that add new persisted derived metadata, it can be useful to run maintenance tasks such as:

- `Backfill Image Lineage Fields`
- `Backfill Image SBOM Security Metadata`
- `Recalculate Vulnerability Fix Availability`

This updates older records without rescanning every image.

## Repository Structure

```text
HITrack/
├── HITrack/             # Django project, API, models, tasks, migrations
├── HITrack-frontend/    # Vue/Vuetify frontend
├── redis/               # Redis image build context
├── httpd/               # Apache reverse proxy configuration
├── docs/                # Screenshots and branding assets
├── storage/             # Generated files and runtime data
├── static_data/         # Collected static assets
├── volume/              # PostgreSQL volume data
├── docker-compose.yml   # Full local stack
└── env.env              # Default environment variables
```

## License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License** (CC BY-NC-SA 4.0).

## Contributors

- **Sergei Ovchinnikov** ([@malchikserega](https://github.com/malchikserega))
- **Ilya Kostyulin** ([@vmvarga](https://github.com/vmvarga))

## Publication

- [Humble image security tracking with Syft + Grype under the hood](https://medium.com/@malchikserega/humble-image-security-tracking-with-syft-grype-under-the-hood-76120e917029)

## Acknowledgments

- [Syft](https://github.com/anchore/syft) for SBOM generation
- [Grype](https://github.com/anchore/grype) for vulnerability matching
- [Helm](https://helm.sh/) for chart discovery and templating
- [OSV](https://osv.dev/) and GitHub advisories for advisory correlation
- [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) for known exploited vulnerability signals
- [Django](https://www.djangoproject.com/) and [Vue.js](https://vuejs.org/) for the application stack
