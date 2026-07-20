# Talisma SIS Demo Environment

This directory defines the isolated client-demo environment. It uses the
`talisma-sis:demo` image, built from `talisma-education-base:v16.0.1`, containing:

- Frappe Framework `v16.25.0`
- ERPNext `v16.26.2`
- Frappe Education `v16.0.1`
- the current `talisma_sis` app

The exact ERPNext and Education Git commits are recorded in `apps.json`.
The implemented US higher-education features and explicit regulatory boundaries
are documented in [US_MVP_SCOPE.md](US_MVP_SCOPE.md).

## Isolation rules

- Compose project: `talisma-demo`
- Site: `demo.talisma.local`
- Browser URL: `http://demo.talisma.local:8082`
- Frontend bind: loopback only (`127.0.0.1`)
- Data: synthetic demo data only
- Never run demo setup against `talisma.local`

Local demo login:

- URL: `http://localhost:8082`
- User: `Administrator`
- Password: `TalismaDemo2026!`

The password is intentionally documented because this environment is local,
loopback-only, and contains no real data. Replace it before any shared demo.

Compose prefixes its named volumes and network with the project name. The demo
therefore does not share the main project's MariaDB, Redis, sites volume, or
network.

## Start the isolated containers

Run these commands from the repository root in PowerShell:

```powershell
$env:CUSTOM_IMAGE = "talisma-sis"
$env:CUSTOM_TAG = "demo"
$env:PULL_POLICY = "never"

docker compose `
  --project-name talisma-demo `
  -f compose.yaml `
  -f overrides/compose.mariadb.yaml `
  -f overrides/compose.redis.yaml `
  -f apps/talisma_sis/demo/compose.override.yaml `
  up -d
```

Site creation, application installation, and demo data loading are deliberately
separate operations. This keeps startup repeatable and prevents accidental
seeding of another site.

## Load the synthetic demo dataset

After installing `erpnext`, `education`, and `talisma_sis` on the demo site,
run:

```powershell
docker compose `
  --project-name talisma-demo `
  -f compose.yaml `
  -f overrides/compose.mariadb.yaml `
  -f overrides/compose.redis.yaml `
  -f apps/talisma_sis/demo/compose.override.yaml `
  exec -T backend bench --site demo.talisma.local execute talisma_sis.demo.setup
```

The command is idempotent and refuses to run against any other site.

Verify the launcher configuration after setup:

```powershell
docker compose `
  --project-name talisma-demo `
  -f compose.yaml `
  -f overrides/compose.mariadb.yaml `
  -f overrides/compose.redis.yaml `
  -f apps/talisma_sis/demo/compose.override.yaml `
  exec -T backend bench --site demo.talisma.local execute talisma_sis.demo.healthcheck
```

The result must contain `"ok": true` before a client demonstration.

## Create a rollback checkpoint

Before applying a new demo increment, create a database and file backup:

```powershell
docker compose `
  --project-name talisma-demo `
  -f compose.yaml `
  -f overrides/compose.mariadb.yaml `
  -f overrides/compose.redis.yaml `
  -f apps/talisma_sis/demo/compose.override.yaml `
  exec -T backend bench --site demo.talisma.local backup --with-files --compress
```

The backup is stored in the isolated `talisma-demo` sites volume under
`sites/demo.talisma.local/private/backups`. Record the four paths printed by
the command. A checkpoint was created before the current MVP increment on
2026-07-13 at `20260713_071419`.

## Restore the demo checkpoint

Stop queue and scheduler services before restoring, then use the database and
file paths printed by the backup command:

```powershell
docker compose `
  --project-name talisma-demo `
  -f compose.yaml `
  -f overrides/compose.mariadb.yaml `
  -f overrides/compose.redis.yaml `
  -f apps/talisma_sis/demo/compose.override.yaml `
  stop scheduler queue-short queue-long

docker compose `
  --project-name talisma-demo `
  -f compose.yaml `
  -f overrides/compose.mariadb.yaml `
  -f overrides/compose.redis.yaml `
  -f apps/talisma_sis/demo/compose.override.yaml `
  exec -T backend bench --site demo.talisma.local restore `
    /home/frappe/frappe-bench/sites/demo.talisma.local/private/backups/20260713_071419-demo_talisma_local-database.sql.gz `
    --with-public-files /home/frappe/frappe-bench/sites/demo.talisma.local/private/backups/20260713_071419-demo_talisma_local-files.tgz `
    --with-private-files /home/frappe/frappe-bench/sites/demo.talisma.local/private/backups/20260713_071419-demo_talisma_local-private-files.tgz

docker compose `
  --project-name talisma-demo `
  -f compose.yaml `
  -f overrides/compose.mariadb.yaml `
  -f overrides/compose.redis.yaml `
  -f apps/talisma_sis/demo/compose.override.yaml `
  start scheduler queue-short queue-long
```

This restore affects only `demo.talisma.local`. It does not use the volumes or
database of `talisma.local`.

## Stop the demo

```powershell
docker compose `
  --project-name talisma-demo `
  -f compose.yaml `
  -f overrides/compose.mariadb.yaml `
  -f overrides/compose.redis.yaml `
  -f apps/talisma_sis/demo/compose.override.yaml `
  down
```

Do not add `--volumes` unless the demo database and site are intentionally being
discarded.
