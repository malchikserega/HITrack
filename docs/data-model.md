# Data model

## Inventory relationships

```text
ContainerRegistry
└── Repository
    └── RepositoryTag ── Release (many-to-many assignment)
        └── Image (many-to-many; tags may resolve to one digest)
            └── ComponentVersion
                ├── Component
                └── Vulnerability via ComponentVersionVulnerability
```

Image-specific package context lives in `ImageComponentVersionContext` and `ComponentLocation`. It must not be inferred solely from a globally shared component version.

## Scan evidence

- `ScanRun` is the durable pipeline execution record with state, lease, task ID and timestamps.
- `ScanArtifact` identifies raw SBOM/Grype artifacts and checksums.
- `Image.sbom_data` and `Image.grype_data` retain payloads used by operational views.
- derived summaries accelerate image and dashboard responses and may require backfills after schema changes.

## Vulnerability state

`Vulnerability` contains identifier-level fields. `ComponentVersionVulnerability` contains occurrence context such as fix state and fixed-in versions. `VulnerabilityDetails` contains external enrichment.

`RiskAcceptance` is a time-bounded decision linked to a vulnerability and an administrator. It does not delete or unlink findings. The database constraint permits at most one row with active status per vulnerability.

## Audit and analytics

`AuditEvent` records security-sensitive mutations with actor, action, target and JSON details. Snapshot models persist weekly intelligence and root-cause analytics for scalable pages. Snapshot timestamps are part of the result semantics and should be visible to users.
