# Platform Capabilities

HITrack stores registry inventory, image scan artifacts, SBOM packages, vulnerability findings, release assignments, and derived analytics. It is intended to keep scan results over time and make them available through a web UI and API.

## Registry and Repository Inventory

Supported registry workflows:

- Azure Container Registry (ACR)
- JFrog Artifactory Docker repositories
- JFrog native Helm repositories
- OCI/Docker manifests that contain Helm artifacts

ACR and JFrog have different remote hierarchies:

```text
ACR:   Registry -> Repository -> Tag
JFrog: Registry -> Repo key -> Application or chart -> Tag
```

HITrack stores a JFrog application as a `Repository` named `<repo-key>/<application>` and keeps the Artifactory repo key in `Repository.repo_key`.

Repositories may be imported through the UI or created by the scheduled JFrog discovery workflow. A repository must be active to be included in `Periodic Repository Scan`.

## Tag Selection

Repository tag discovery supports:

- all returned tags;
- one globally latest tag;
- one latest tag per major release line;
- one latest tag per major.minor release line;
- optional prerelease and `latest` alias handling;
- processing only newly discovered tags or reprocessing existing selected tags.

The release-line behavior and Django Admin parameters are documented in [Release-Line Tag Scanning](periodic-tag-scanning.md).

## Docker and Helm Scanning

For a Docker repository, a selected tag resolves to one image.

For a Helm repository, HITrack downloads or resolves the chart, extracts referenced child images, and runs those child images through the normal Docker image pipeline. Image references are resolved in this order:

1. an already completed matching image in HITrack;
2. the original reference;
3. normalized candidates in the chart's registry;
4. fallback repositories configured on the chart's `ContainerRegistry`.

Fallback configuration is registry-level. There is no repository-level fallback field.

When the scan worker can see the host Docker daemon, an exact image reference already present in that daemon can be scanned without first pulling it from a remote registry. The image must be available to the same Docker daemon exposed to the worker.

## SBOM and Component Data

Syft produces an SBOM for each image. HITrack stores the raw payload and maps packages into shared component records:

- `Component`
- `ComponentVersion`
- image-to-component relationships
- `ComponentLocation`
- `ImageComponentVersionContext`

Image-specific context can include:

- package type and PURL;
- direct, transitive, or unknown dependency scope;
- dependency depth and parent/introducer packages;
- architecture;
- distro and package repository information;
- source package metadata;
- cataloger and evidence location.

Component identity is shared across images. Context that varies by image is stored separately instead of mutating the shared component.

## Vulnerability Findings

Grype findings are stored as relationships between component versions and vulnerabilities. HITrack keeps both raw scan data and normalized fields used by the UI.

Stored or derived data includes:

- severity, including negligible and unknown findings;
- affected component version;
- fixed-in versions and raw Grype fix state;
- normalized fix status;
- component and file locations;
- image-specific finding summaries;
- EPSS, CISA KEV, exploit, and advisory metadata when enrichment succeeds.

External enrichment is failure-aware: a failed or empty external response is recorded as a failed attempt and does not erase previously usable details.

## Image Detail and Summaries

The image detail page presents occurrence-level and unique-vulnerability views. It also groups findings by component ecosystem or package type, such as OS packages, Python, Java, JavaScript, Go, and other detected package types.

The page includes:

- total findings;
- unique vulnerabilities;
- severity distribution;
- fix-status distribution;
- fully-fixable component summary;
- package/ecosystem breakdown;
- component and vulnerability tables;
- component locations;
- distro lineage and end-of-life metadata where available.

Definitions and counting rules are described in [Scanning and Result Semantics](scanning.md).

## Releases and Reports

Repository tags can be assigned to a `Release`. Release views show their tags and scan state, and can queue missing scans.

The report generator produces workbook-based reports from stored release and image data. Report generation depends on completed scan data; a release with pending or failed tags may produce incomplete input or fail validation.

## Vulnerability Intelligence

HITrack can enrich supported vulnerability identifiers with data from configured or built-in external sources. Current code includes handling for CVE/GHSA/OSV-related information, FIRST EPSS, CISA KEV, GitHub advisories, and exploit signals.

Enrichment tasks separate orchestration from batched network work. Recent successful enrichment is skipped until it becomes stale unless a forced single-vulnerability update is requested.

## Threat Intelligence Snapshots

Weekly threat-intelligence snapshots store:

- vulnerabilities first observed in HITrack during the current period;
- CISA KEV additions during the period;
- supply-chain advisory matches from supported sources.

The UI distinguishes historical relevance from findings currently present in stored image/component relationships.

## Analytics

Available analytics include:

- image comparisons;
- shared vulnerable component versions across repositories;
- OS/distro lineage groups;
- repository, image, component, and vulnerability dashboard metrics;
- recent activities and scan deltas;
- component matrix views.

Root-cause pages use persisted snapshots for larger datasets. Snapshot collection is not automatic unless a periodic task is configured.

## Maintenance and Repair

Maintenance tasks exist for:

- image identity deduplication;
- lineage backfill;
- image SBOM security-context backfill;
- fix-availability recalculation from stored Grype payloads;
- vulnerability-detail cleanup;
- threat-intel and analytics snapshot retention.

Backfills update stored data and should normally be run after an upgrade that introduces or changes derived fields. They are not substitutes for regular image scans.

## Current Boundaries

- OS lineage is inferred from SBOM data. It is not guaranteed to equal the exact Dockerfile `FROM` image.
- A registry fallback policy applies to every Helm repository linked to that registry.
- Registry credentials are stored in the current database model and should be protected by deployment controls.
- Scanner accuracy depends on Syft/Grype output, accessible image manifests, and the available vulnerability database.
- The checked-in Compose and Django settings are development-oriented and require hardening before public exposure.
