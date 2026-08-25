# HITrack

HITrack is a self-hosted platform for discovering container and Helm artifacts, generating SBOMs, preserving scanner evidence, and turning vulnerability data into remediation decisions.

<div class="grid cards" markdown>

- :material-radar:{ .lg .middle } **See what is exposed**

  ---

  Inventory registries, repositories, tags, images, packages and vulnerabilities with traceable relationships.

  [:octicons-arrow-right-24: Platform capabilities](capabilities.md)

- :material-priority-high:{ .lg .middle } **Prioritize what matters**

  ---

  Rank fixable packages by severity, KEV/exploit evidence and blast radius; find stale or incomplete scans.

  [:octicons-arrow-right-24: Prioritization](prioritization.md)

- :material-shield-check:{ .lg .middle } **Govern exceptions**

  ---

  Record time-bounded risk acceptance with a reason, administrator authorization and append-only audit events.

  [:octicons-arrow-right-24: Vulnerability workflow](vulnerabilities.md)

- :material-api:{ .lg .middle } **Automate through the API**

  ---

  Use the authenticated REST API and interactive OpenAPI documentation for integrations.

  [:octicons-arrow-right-24: API reference](api.md)

</div>

## Typical workflow

1. Connect an ACR or JFrog registry.
2. Discover repositories and choose a tag-selection policy.
3. Scan images or Helm-referenced child images with Syft and Grype.
4. Validate coverage and freshness on **Prioritization**.
5. Remediate high-impact component versions or record an explicitly reviewed risk decision.
6. Track releases, scan state, root causes and threat-intelligence signals.

!!! info "Evidence, not a replacement for review"
    HITrack ranks and explains stored evidence. A recommended fixed version is a candidate derived from scanner metadata, not a guarantee of application compatibility. Validate upgrades in your normal build and test pipeline.

## Start here

- New evaluator: [Getting started](getting-started.md)
- Security analyst: [Prioritization and remediation](prioritization.md)
- Platform administrator: [Operations and deployment](operations.md)
- Contributor: [Architecture](architecture.md) and [Contributing](contributing.md)
