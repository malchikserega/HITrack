# Security policy

## Reporting a vulnerability

Do not open a public issue containing exploit details, credentials or private deployment data. Use the GitHub repository's private vulnerability reporting feature when enabled, or contact the maintainers through a private channel listed by the project.

Include the affected version/commit, deployment assumptions, reproduction steps, impact and any suggested mitigation. Maintainers should acknowledge the report, validate scope, coordinate a fix and publish an advisory when appropriate.

## Security model

HITrack processes untrusted metadata from registries and scanners and operates a scan worker with powerful Docker-daemon access. Deploy it as an internal security service with strict network boundaries, least-privilege registry credentials and monitored administrator accounts.

The project does not claim that a clean scan proves an image is secure. Results depend on inventory reachability, SBOM quality, vulnerability databases, matching logic and enrichment freshness.

## Supported configuration

Production deployments must disable debug, provide unique secrets and exact origins/hosts, use TLS, isolate PostgreSQL/Redis and protect Docker access. See the [production checklist](production.md).
