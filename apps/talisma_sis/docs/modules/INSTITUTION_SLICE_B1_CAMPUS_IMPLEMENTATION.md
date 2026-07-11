# Institution Slice B1: Campus Implementation

Status: **Implemented for review on `feat/talisma-campus`**

## Scope

This implementation adds only the accepted `Talisma Campus` DocType. It depends on the existing `Talisma Institution` scope root and reuses its Manager and Viewer roles.

## Delivered behavior

- server-generated UUIDv4 document names;
- normalized immutable campus codes scoped to an immutable Institution;
- clear application duplicate validation plus an app-owned composite MariaDB unique constraint;
- Main, Satellite, Learning Center, Virtual, and Other campus types;
- Planned, Active, Inactive, and Closed lifecycle states;
- Institution-relative effective-date validation;
- timezone defaulting from Institution and IANA validation;
- required standard Address links for physical campus types;
- HTTP/HTTPS website validation;
- prevention of ordinary Closed-campus reopening;
- framework change tracking; and
- accepted Manager, Viewer, and System Manager permissions.

## Composite uniqueness

`talisma_sis.patches.v0_0.add_talisma_campus_unique_constraint` runs after DocType synchronization and calls Frappe's idempotent `frappe.db.add_unique()` API. The constraint `unique_talisma_campus_institution_code` covers `(institution, campus_code)`.

The controller pre-check improves the user-facing error. The database constraint remains authoritative when validation is bypassed or competing requests race.

Uninstall requires no independent constraint drop: normal Frappe app removal drops the app-owned Campus DocType table. Isolated uninstall/restore verification remains an operational release gate and must not be run destructively on the development site.

## Security boundary

Permissions are DocType-level. This slice does not implement Scope Grant or institution-filtered permission-query hooks. Until those are approved, Campus roles must not be assigned to a user who is not allowed to see every Institution in the site.

## Exclusions preserved

No parent campus, facilities, academic units, hierarchy versions, closure tables, scope grants, ERPNext mappings, standard-record custom fields, APIs, pages, reports, workflows, jobs, integrations, Education dependency, Docker changes, or core modifications are included.

## Verification

The automated suite covers naming, normalization, scoped uniqueness, direct database enforcement, immutability, interval rules, Institution status, campus types, address behavior, timezone, URL, Closed status, permissions, change tracking, and deletion while unreferenced.
