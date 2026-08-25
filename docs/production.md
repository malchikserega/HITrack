# Production checklist

The repository Compose file is a development/reference topology. Before exposing HITrack, complete and test every applicable item.

## Required configuration

Set `DJANGO_DEBUG=false` plus:

```text
DJANGO_SECRET_KEY=<random secret, at least 50 characters>
DJANGO_ALLOWED_HOSTS=hitrack.example.com
CORS_ALLOWED_ORIGINS=https://hitrack.example.com
CSRF_TRUSTED_ORIGINS=https://hitrack.example.com
SECURE_SSL_REDIRECT=true
TRUST_PROXY_HTTPS_HEADER=true
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
```

With debug disabled, startup fails when the secret or allowed hosts are absent. Keep database, registry and bootstrap credentials in a secret manager.

Enable HSTS only after HTTPS works for the complete domain scope. Do not enable preload until every subdomain is permanently ready.

## Runtime

- replace Django `runserver` with a supported WSGI/ASGI server;
- terminate TLS at a controlled reverse proxy;
- restrict Admin and API ingress;
- keep PostgreSQL and Redis on private networks (the local Compose bindings are loopback-only);
- set resource limits and health checks;
- separate scan-worker capacity from lightweight orchestration and enrichment.

## Docker socket

Only the scan worker is intended to receive the Docker socket in the reference stack. Socket access is effectively host-level privilege. For stronger isolation, use a dedicated scanner host/VM, a rootless daemon or a narrowly scoped proxy, and prevent untrusted users from controlling image references or scan-worker configuration.

## Data protection

- encrypt disks and backups;
- restrict PostgreSQL access because registry credentials are stored in the application database;
- define retention for raw SBOM/Grype artifacts, task results and snapshots;
- test PostgreSQL and artifact restore together;
- rotate registry tokens and use read-only scopes;
- monitor failed logins, task failures, disk growth and stale scans.

## Upgrade procedure

1. Back up PostgreSQL and artifact storage.
2. Build the target image and review migrations.
3. Stop beat and workers before schema changes when required.
4. Apply migrations once.
5. Start API, workers and beat.
6. Run documented backfills for changed derived fields.
7. Smoke-test login/logout, one registry sync, one scan and prioritization.
