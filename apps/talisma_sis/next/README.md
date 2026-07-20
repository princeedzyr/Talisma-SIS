# Bryan University Next Environment

This is the isolated development baseline for the future Bryan University SIS.
It begins as a data-and-files clone of the existing client demo so that current
features can be evaluated for reuse, replacement, or extension.

## Isolation contract

| Boundary | Existing demo | Bryan University Next |
| --- | --- | --- |
| Compose project | `talisma-demo` | `bryan-next` |
| Site | `demo.talisma.local` | `next.bryan.local` |
| Browser URL | `http://localhost:8082` | `http://localhost:8083` |
| Docker volumes | `talisma-demo_*` | `bryan-next_*` |
| Network | `talisma-demo_default` | `bryan-next_default` |

The environments must never share a MariaDB volume, Redis volume, sites volume,
or Compose project name. Changes intended for Next must not be applied to the
demo site.

## Baseline

- Image: `talisma-sis:next`
- Frappe Framework: `16.25.0`
- ERPNext: `16.26.2`
- Frappe Education: `16.0.1`
- Talisma SIS: `0.0.1`
- Source snapshot: cloned from `demo.talisma.local` on 2026-07-14

The exact ERPNext and Education source commits are recorded in `apps.json`.

The baseline uses its own image tag so future Next builds never replace the
frozen demo image. Do not build Next changes with the `talisma-sis:demo` tag.

The reproducible base is defined in `Containerfile.base`. It checks out the
approved ERPNext and Education commits explicitly, verifies each Git HEAD, then
rebuilds requirements and assets before repository metadata is removed from the
runtime image. The Talisma application also rejects installation or migration
on any unapproved version tuple.

## Start or stop Next

The ignored local `.env` file contains this environment's image selection and
database bootstrap password. Run Compose from the repository root:

```powershell
docker compose `
  --env-file apps/talisma_sis/next/.env `
  --project-name bryan-next `
  -f compose.yaml `
  -f overrides/compose.mariadb.yaml `
  -f overrides/compose.redis.yaml `
  -f apps/talisma_sis/next/compose.override.yaml `
  up -d
```

Open `http://localhost:8083`. The cloned site initially has the same local demo
users and credentials as the source snapshot. Change them before sharing this
environment beyond the local machine.

To stop Next without deleting its independent data:

```powershell
docker compose `
  --env-file apps/talisma_sis/next/.env `
  --project-name bryan-next `
  -f compose.yaml `
  -f overrides/compose.mariadb.yaml `
  -f overrides/compose.redis.yaml `
  -f apps/talisma_sis/next/compose.override.yaml `
  down
```

Never add `--volumes` unless the Next environment is intentionally being reset.

## Development rule

Treat the copied functionality as a baseline, not as a permanent architecture
decision. For each future increment, decide explicitly whether the existing
behavior should be reused, extended, replaced, or retired. The client demo on
port `8082` remains the frozen comparison environment.
