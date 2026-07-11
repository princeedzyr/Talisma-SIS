# Institutional Schema Slice B1: Campus Acceptance Record

- **Architecture:** Accepted ADR-003 Institutional Hierarchy
- **Proposal:** [Campus Slice B1 Proposal](INSTITUTIONAL_SCHEMA_SLICE_B1_CAMPUS_PROPOSAL.md)
- **Outcome:** Accepted for implementation within the exact authorized scope
- **Approval date:** 2026-07-11
- **Approver:** Prince Ebinezer, Project Owner
- **Recorded by:** Talisma SIS architecture process

## Accepted decision

The project owner approves `Talisma Campus` as the physical and operational campus master beneath `Talisma Institution`.

Campus remains distinct from:

- ERPNext `Branch`, `Company`, `Department`, and `Cost Center`;
- academic governance and the future Talisma Academic Unit hierarchy; and
- buildings, rooms, facilities, and geospatial boundaries.

The proposal is accepted without qualifications. Its naming, fields, validation, lifecycle, permissions, testing, migration, security limitations, and exclusions form the binding implementation boundary.

## Authorized implementation scope

One new standard DocType in the `talisma_sis` app:

- **DocType:** `Talisma Campus`
- **Module:** `Talisma SIS`
- **Naming:** server-generated UUIDv4
- **Submittable:** No
- **Rename:** Disabled
- **Track changes:** Enabled
- **Quick entry:** Disabled initially
- **Import:** Disabled initially

Only these fields are authorized:

| Field | Type | Required | Accepted constraint |
|---|---|---:|---|
| `institution` | Link: Talisma Institution | Yes | Indexed and immutable |
| `campus_code` | Data | Yes | Normalized uppercase; immutable; unique within Institution |
| `campus_name` | Data | Yes | Searchable display name |
| `short_name` | Data | No | Searchable abbreviation |
| `campus_type` | Select | Yes | Main, Satellite, Learning Center, Virtual, Other |
| `status` | Select | Yes | Planned, Active, Inactive, Closed; default Planned |
| `valid_from` | Date | Yes | Within Institution validity |
| `valid_to` | Date | No | On or after `valid_from`; within Institution validity |
| `timezone` | Autocomplete | Yes | Valid IANA timezone; initialized from Institution |
| `address` | Link: Address | Conditional | Required unless campus type is Virtual |
| `website` | Data | No | Valid HTTP or HTTPS URL |

## Accepted constraints

1. `name` is an immutable server-generated UUIDv4.
2. `campus_code` uses `A-Z`, `0-9`, hyphen, and underscore with length 2–32.
3. `(institution, normalized campus_code)` is unique and non-recyclable.
4. Scoped uniqueness must be enforced for concurrent inserts through a reviewed, idempotent app-owned MariaDB mechanism plus clear application validation.
5. Institution and campus code cannot change after insertion.
6. New campuses may reference only Planned or Active Institutions.
7. Campus validity must fall within Institution validity.
8. Physical campus types require Address; Virtual campuses may omit it.
9. Closed campuses cannot be reopened through ordinary editing in the initial implementation.
10. Institution lifecycle does not automatically cascade to Campus.
11. Unreferenced deletion is allowed; normal static-Link protection must block referenced deletion when an authorized dependent DocType exists.

## Authorized permissions

No new role is authorized.

| Existing role | Access |
|---|---|
| `Talisma Institution Manager` | Create, read, update, and delete only while unreferenced; no import/export by default |
| `Talisma Institution Viewer` | Read only |
| `System Manager` | Administrative development and recovery access |

These are DocType-level permissions. Until Scope Grant and server-side row filtering are separately approved and implemented, Campus access must not be assigned to a user who is not allowed to see every Institution in that site.

## Required verification

Implementation acceptance requires all sixteen tests and operational checks specified in the proposal, including:

- UUIDv4, normalization, immutability, interval, type, address, timezone, and URL tests;
- normal and concurrent composite-uniqueness tests;
- permission and change-tracking tests;
- install and repeated-migrate verification without Education;
- backup/restore and isolated uninstall/dependency verification; and
- confirmation that the composite database mechanism is idempotent.

## Explicit exclusions

This acceptance does not authorize:

- `parent_campus`, `is_virtual`, facilities, buildings, rooms, or campus hierarchy;
- Academic Unit Type, Academic Unit, Structure Version, Placement, Closure, or Scope Grant;
- ERPNext or Education mappings and custom fields;
- row-level permission hooks, identity changes, data migration, or seed data;
- APIs, pages, portals, workspaces, reports, fixtures, workflows, jobs, or integrations;
- Docker/Compose changes or Frappe/ERPNext core modifications.

## Implementation change control

Implementation may begin only after this acceptance record is reviewed and merged into `develop`. It must use a new feature branch and match this record exactly. Any additional field, role, DocType, hook, index purpose, API, migration behavior, fixture, or standard-record customization requires renewed approval.

Completion requires code review, automated tests, repeated `bench migrate`, database-constraint verification, permissions verification, backup evidence, and updated implementation documentation.

## Future gates

Campus implementation does not authorize subsequent institutional slices. Academic Unit, versioned hierarchy, closure materialization, Scope Grant, mappings, and ownership each remain independently gated.
