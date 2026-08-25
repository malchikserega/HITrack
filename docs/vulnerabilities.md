# Vulnerabilities and risk decisions

## Finding lifecycle

A vulnerability is stored once and linked to affected component versions through `ComponentVersionVulnerability`. That relationship carries fix state and fixed-in versions. Images link to component versions, preserving the path from CVE to package to image, tag, repository and release.

An orphan is a vulnerability with no path to any currently stored image. Administrators/operators can preview and delete orphaned vulnerabilities from the table. The preview count is shown before the irreversible delete request.

## Vulnerability table

Use severity, identifier type, fixability, CISA KEV, exploit and ransomware filters. **Risk status** distinguishes:

- **Active** — included in prioritization;
- **Accepted** — excluded from prioritization until its review date unless the analyst enables “include accepted risk”.

Accepted findings remain in inventory, image counts and decision history.

## Accepting risk

Only a superuser or member of the `admin` group can accept or revoke risk. A decision requires:

- a meaningful reason of at least 10 characters;
- a future review/expiry timestamp;
- a duration no longer than 365 days.

Only one active acceptance can exist per vulnerability. Creation and revocation produce `AuditEvent` records. Expired decisions no longer suppress prioritization and are marked expired when history is read or a replacement is created.

!!! warning
    Risk acceptance is not deletion and does not alter scanner evidence. Use it for a documented exception with compensating controls, an owner and a review plan—not to make dashboards look better.

## Enrichment

Supported identifiers can be enriched with EPSS, CISA KEV, GitHub/OSV and exploit-related evidence. A failed external lookup records failure state without erasing previously successful data. Displayed timestamps distinguish last attempt from last successful update.
