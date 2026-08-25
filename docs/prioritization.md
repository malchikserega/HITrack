# Prioritization and remediation

The **Prioritization** page is the operational work queue for large inventories. It intentionally separates actionable analytics from the high-level dashboard.

## Remediation opportunities

Rows are grouped by affected component version rather than by raw finding. The score increases with:

- critical and high vulnerabilities;
- CISA KEV and exploit evidence;
- EPSS;
- affected images, tags, repositories and releases.

Only findings reported as fixable are included. **Recommended version** is selected from structured Grype fixed-in versions; the known latest package version is used only as a fallback. Treat it as an upgrade candidate and test compatibility.

## High-impact packages

This view includes both fixable and unfixable findings and identifies shared component versions with the largest security blast radius. It is useful for finding one dependency upgrade or base-image rebuild that reduces exposure across multiple teams or releases.

## Scan freshness and coverage

Coverage reports whether images contain:

- an SBOM payload;
- Grype results;
- both, which counts as fully analysed.

Freshness uses the latest successful `ScanRun`. Older records without a scan run fall back to the stored Grype update timestamp. The threshold is configurable in the page filter. **Never scanned** and **stale** images appear in the attention list.

## Filters

- **Ecosystem** filters by normalized component type (`dotnet`, `npm`, `python`, `java`, `go`, OS package types, and others).
- **Search** matches component name or PURL.
- **Stale after** changes only the coverage classification.
- **Include accepted risk** adds findings with a current risk acceptance; they are excluded by default.

## Interpreting the score

The score is an ordering aid, not a universal probability or SLA. Compare rows within the same HITrack deployment. Scanner input, inventory completeness and organizational impact still require analyst judgement.
