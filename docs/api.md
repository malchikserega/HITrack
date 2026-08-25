# API reference

HITrack exposes a versioned Django REST Framework API under `/api/`. The running deployment is the source of truth for the complete schema:

- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI schema: `/api/schema/`

Most endpoints require `Authorization: Bearer <access-token>`. Browser refresh uses the HttpOnly refresh cookie and logout revokes it.

## Operational endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health/` | Unauthenticated database/cache readiness without configuration details |
| `GET /api/stats/prioritization/` | Remediation, high-impact package and scan coverage analytics |
| `GET /api/vulnerabilities/?suppressed=true|false` | Filter by active risk acceptance |
| `GET /api/vulnerabilities/{uuid}/risk-acceptances/` | Decision history |
| `POST /api/vulnerabilities/{uuid}/accept-risk/` | Admin-only time-bounded acceptance |
| `POST /api/vulnerabilities/{uuid}/revoke-risk-acceptance/` | Admin-only revocation |
| `GET/POST /api/vulnerabilities/cleanup-orphaned/` | Preview / delete unreachable vulnerability records |
| `GET/POST /api/images/cleanup-orphaned/` | Preview / delete safe orphan image candidates |

## Pagination and filtering

List endpoints normally use `page` and `page_size`. Supported endpoints expose server-side search, ordering and field filters. Do not assume a successful orchestration response means all asynchronous children succeeded; retain returned task IDs and inspect task state.

## Compatibility

The default API version is `v1`. Public integrations should generate or validate clients against the OpenAPI schema and pin the HITrack release they deploy.
