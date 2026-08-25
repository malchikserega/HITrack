# Solution audit

Audit date: 2026-08-25. Scope: repository architecture, Django/DRF authentication and permissions, frontend session handling, scan/result semantics, destructive maintenance controls, runtime configuration, tests and public documentation.

## Corrected in this review

| Area | Result |
| --- | --- |
| Logout | Refresh cookie is revoked/cleared even when the access token is invalid; frontend session is always cleared. |
| Authorization | Current-user capabilities come from `/auth/me/`; mutation and security-admin controls are enforced by backend permissions. |
| Vulnerability ecosystems | Package identity uses normalized PURLs and ecosystem inference, including NuGet/.NET and additional package types; UI avoids declaring no exposure merely because one summary bucket is empty. |
| Threat intelligence | Signal and presence filters separate observed, KEV and supply-chain entries; Present is documented as current inventory reachability. |
| Orphan cleanup | Images and vulnerabilities have preview-before-delete operations with authorization and conservative reachability rules. |
| Prioritization | Added fixable remediation opportunities, high-impact packages, and scan freshness/coverage. |
| Risk acceptance | Added admin-only reason, expiry (maximum 365 days), history, revocation, database uniqueness and audit events. |
| Secrets and hosts | Removed hard-coded production fallback secret, wildcard hosts/CORS in production and default administrator password. |
| Basic Auth | Disabled by default; JWT/session authentication remain. |
| Service exposure | PostgreSQL and Redis reference bindings are loopback-only; Docker socket removed from API/light/enrichment containers. |
| Readiness | Added a non-secret database/cache health endpoint and Compose health check. |
| Documentation | Added versioned MkDocs portal with strict build and GitHub Pages workflow. |
| Dependencies | Upgraded to patched Django 5.2 and Axios/toolchain releases; removed vulnerable browser SheetJS in favor of injection-safe CSV. Live `pip-audit` and `npm audit` report zero known vulnerabilities. |
| Continuous assurance | CI checks migration drift and dependency advisories; Dependabot and CodeQL workflows were added. |

## Open risks requiring deployment or future design work

| Severity | Risk | Recommended action |
| --- | --- | --- |
| High | The scan worker's Docker socket is equivalent to host-level control. | Isolate scanner workers on dedicated hosts/VMs or use a rootless/narrowly scoped daemon proxy. |
| High | Registry passwords/tokens are fields in the primary database. | Add application-layer envelope encryption backed by an external KMS/secret manager and a rotation migration. |
| Medium | The reference API command uses Django `runserver`. | Provide a production Compose/Helm profile using Gunicorn/Uvicorn and explicit health checks. |
| Medium | Local Compose uses known database credentials. | Override through secret management and private networking; never expose the local profile publicly. |
| Medium | No external identity provider, MFA or automated account lifecycle is built in. | Integrate organizational SSO at the reverse proxy/application layer for production. |
| Low | Advisory databases and base images continue to change after each release. | Keep Dependabot/CodeQL enabled, review CI audit failures, and scan released HITrack images on a schedule. |
| Low | Accepted risk has expiry but no separate owner/ticket fields. | Add owner and ticket URL when organizational workflows require them. |

## Assurance limits

The review and automated tests reduce known defects but are not a penetration test or formal security certification. Production assurance also requires infrastructure review, threat modelling for the deployment, dependency/image scanning, backup restoration exercises and periodic authorization testing.
