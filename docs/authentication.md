# Authentication and authorization

## Browser session flow

1. The login endpoint validates username/password and returns a short-lived JWT access token.
2. The refresh token is stored in an HttpOnly cookie and is not exposed to JavaScript.
3. The frontend keeps the access token in `sessionStorage`, calls `/api/auth/me/` for roles, and refreshes through the cookie when needed.
4. Logout blacklists the refresh token when available, clears the cookie and removes the frontend session even if the access token is already invalid.

Access tokens expire after 60 minutes and refresh tokens after one day by default. Basic Authentication is disabled unless `ENABLE_BASIC_AUTH=true` is explicitly set.

## Roles

| Role | Read | Normal mutations | Security administration |
| --- | --- | --- | --- |
| Authenticated user | Yes | No | No |
| `operator` group | Yes | Yes | No |
| `admin` group | Yes | Yes | Yes |
| Django superuser | Yes | Yes | Yes |

Security-administration operations include risk acceptance/revocation and other endpoints guarded by `IsSecurityAdmin`. Frontend button visibility is a usability feature only; backend permissions are authoritative.

## Account bootstrap

No default administrator password is created. Run `python manage.py createsuperuser`, or provide both `SUPERUSER_NAME` and `SUPERUSER_PSWD` for a one-time automated bootstrap. Never store production values in `env.env` or source control.

## Deployment requirements

- serve the UI and API only over TLS;
- set an unpredictable `DJANGO_SECRET_KEY`;
- configure exact allowed hosts, CORS origins and CSRF trusted origins;
- protect the Django Admin route with network controls where possible;
- use an external identity provider or stronger account lifecycle controls if required by your organization;
- review audit events and revoke unused accounts.
