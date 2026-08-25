# Contributing

## Repository layout

```text
HITrack/            Django API, models, Celery tasks and migrations
HITrack-frontend/   Vue 3, TypeScript and Vuetify application
docs/               MkDocs source
docker-compose.yml  local full-stack topology
```

## Local checks

```bash
docker compose build hitrack-api
docker compose run --rm --no-deps --entrypoint python hitrack-api manage.py test core.tests

cd HITrack-frontend
npm ci
npm run type-check
npm run build

python -m pip install -r docs/requirements.txt
mkdocs build --strict
```

Every behavior change should include tests and documentation when it affects API semantics, permissions, scan interpretation, configuration or user workflow. Preserve raw scanner evidence and make destructive maintenance actions previewable wherever possible.

## Migrations

Create migrations with `python manage.py makemigrations`, inspect them, and test both a clean database and an upgrade copy. Never edit an already released migration merely to satisfy local state.

## Pull requests

Describe the user-visible outcome, data migration impact, authorization impact and validation performed. Screenshots are useful for dense UI changes. Do not include registry tokens, SBOMs from private applications or production database extracts.
