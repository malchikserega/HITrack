# Threat intelligence

Weekly threat-intelligence snapshots combine three signal families:

- **Observed** — vulnerabilities first observed in HITrack during the period;
- **KEV** — CISA Known Exploited Vulnerabilities added during the period;
- **Supply chain** — supported external supply-chain advisories.

## Confirmed versus informational signals

The feed uses three deliberately different exposure states:

- **Confirmed in current images** means a scanner finding for the advisory identifier is linked to an exact stored component version and to at least one image that still belongs to a repository tag. The row lists the package name, installed version, ecosystem and image count. This is evidence about your inventory.
- **Historical** means the identifier exists in HITrack, but it no longer has a path to a current tagged image. It does not mean the advisory was withdrawn.
- **External intelligence only** means CISA, GitHub or OSV published the signal, but HITrack has no scanner-confirmed match. It is useful for awareness and must not be interpreted as proof that one of your components is vulnerable.

The full-page feed opens with **Confirmed in Current Images** selected. Change the exposure filter to review historical or unmatched external intelligence.

Identifier matching is case-insensitive and checks the advisory's CVE, GHSA, OSV and alias identifiers. Ecosystem filtering normalizes common equivalents, including `.NET`/`NuGet`, `pip`/`PyPI`, `Rust`/`crates.io`, and `Composer`/`Packagist`.

## Working with large datasets

Use signal, exposure, ecosystem and text filters before inspecting rows. Text search includes matched component names, versions, ecosystems and PURLs. Source labels and match reasons explain why a signal is shown. The page keeps signal families separate so that “new in inventory,” “known exploited,” and “supply-chain advisory” are not interpreted as equivalent evidence.

Summary counters show confirmed vulnerabilities, exact affected component versions, historical matches and external-only entries before filtering. Feed refresh time is displayed. If an external source fails, the API marks that source unavailable and the page displays an incomplete-feed warning instead of presenting an empty response as a clean result.

Snapshots are only as current as their Celery Beat schedule. A daily collection is the recommended minimum; more frequent collection increases external API traffic. GitHub requests use the largest supported page size. OSV collection has configurable safety caps (`OSV_WEEKLY_MAX_IDS_PER_ECOSYSTEM` and `OSV_WEEKLY_MAX_TOTAL_IDS`); when the global cap is reached, candidates are sampled round-robin across every supported ecosystem instead of allowing early ecosystems to consume the limit. The UI marks this state as partial coverage. See [Periodic tasks](periodic-tasks.md).
