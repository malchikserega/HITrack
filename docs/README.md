# HITrack Documentation

This directory contains the current user, administrator, and developer documentation for HITrack.

## Start Here

| Document | Purpose |
| --- | --- |
| [Platform Capabilities](capabilities.md) | What HITrack currently does and does not do. |
| [Architecture and Data Flow](architecture.md) | Services, queues, core data model, and scan flow. |
| [Registries and Repository Discovery](registries.md) | ACR, JFrog, Helm fallback, local images, and repository import. |
| [Scanning and Result Semantics](scanning.md) | Scan stages, statuses, image metrics, severity, uniqueness, and fix availability. |
| [Periodic Tasks](periodic-tasks.md) | Tasks suitable for Django Admin schedules, parameters, cadence, and internal tasks to avoid scheduling directly. |
| [Operations and Deployment](operations.md) | Docker startup, upgrades, backups, logs, worker operation, and current deployment limitations. |

## Detailed Task Guides

- [Periodic JFrog Repository Discovery](jfrog-repository-discovery.md)
- [Release-Line Tag Scanning](periodic-tag-scanning.md)

## Scope

The documentation describes the code and `docker-compose.yml` in this repository. Environment-specific proxying, authentication policy, registry permissions, retention requirements, and production hardening remain the responsibility of the deployment owner.

When behavior and documentation differ, treat the registered task names in `HITrack/core/tasks.py`, queue routing in `HITrack/HITrack/settings.py`, and service definitions in `docker-compose.yml` as the implementation source of truth, then update the documentation.
