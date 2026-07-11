# Institutional Schema Slice B2: Academic Unit Type and Academic Unit Acceptance Record

- **Architecture:** Accepted ADR-003 Institutional Hierarchy
- **Proposal:** [Slice B2 Academic Unit Type and Academic Unit Proposal](INSTITUTIONAL_SCHEMA_SLICE_B2_ACADEMIC_UNIT_PROPOSAL.md)
- **Outcome:** Accepted for implementation within the exact authorized scope
- **Approval date:** 2026-07-11
- **Approver:** Prince Ebinezer, Project Owner
- **Recorded by:** Talisma SIS architecture process

## Accepted decision

The project owner approves `Talisma Academic Unit Type` and `Talisma Academic Unit` as stable academic-governance masters beneath the existing `Talisma Institution` boundary.

This acceptance does not establish an academic hierarchy. Parentage, roots, ordering, effective structures, descendants, and user scope remain outside B2. The proposal's naming, fields, validation, lifecycle, permissions, capability semantics, testing, migration, security limitations, and exclusions form the binding implementation boundary.

## Authorized implementation scope

Two new standard DocTypes in the `talisma_sis` app and `Talisma SIS` module:

1. `Talisma Academic Unit Type`
2. `Talisma Academic Unit`

Both use server-generated UUIDv4 names, disable rename, enable change tracking, remain non-submittable, and initially disable quick entry and import.

### Authorized Unit Type fields

| Field | Type | Required | Accepted constraint |
|---|---|---:|---|
| `type_code` | Data | Yes | Globally unique normalized stable code; immutable |
| `type_name` | Data | Yes | Searchable display name |
| `can_grant_credentials` | Check | Yes | Capability maximum; default off |
| `can_own_programs` | Check | Yes | Capability maximum; default off |
| `can_own_courses` | Check | Yes | Capability maximum; default off |
| `disabled` | Check | Yes | Prevents new assignment; default off |

### Authorized Academic Unit fields

| Field | Type | Required | Accepted constraint |
|---|---|---:|---|
| `institution` | Link: Talisma Institution | Yes | Indexed and immutable |
| `unit_code` | Data | Yes | Normalized uppercase; immutable; unique within Institution |
| `unit_name` | Data | Yes | Searchable display name |
| `short_name` | Data | No | Searchable abbreviation |
| `unit_type` | Link: Talisma Academic Unit Type | Yes | Governed type; indexed |
| `status` | Select | Yes | Planned, Active, Inactive, Closed; default Planned |
| `valid_from` | Date | Yes | Within Institution validity |
| `valid_to` | Date | No | On or after `valid_from`; within Institution validity |
| `can_grant_credentials` | Check | Yes | Bounded by Unit Type; default off |
| `can_own_programs` | Check | Yes | Bounded by Unit Type; default off |
| `can_own_courses` | Check | Yes | Bounded by Unit Type; default off |

No other fields are authorized.

## Accepted constraints

1. Both DocTypes use immutable server-generated UUIDv4 names.
2. Type and Unit codes use `A-Z`, `0-9`, hyphen, and underscore with length 2–32 after trim-and-uppercase normalization.
3. Type codes are globally unique, immutable, and non-recyclable.
4. `(institution, normalized unit_code)` is unique and non-recyclable.
5. Scoped Unit uniqueness must be enforced under concurrent insertion through a reviewed, idempotent app-owned MariaDB mechanism plus clear application validation.
6. Institution and Unit code cannot change after insertion.
7. New Units may reference only Planned or Active Institutions and a non-disabled Unit Type.
8. Unit validity must fall within Institution validity.
9. Unit Type capabilities are maxima; an individual Unit may narrow but cannot broaden them.
10. Referenced Unit Type codes and capability maxima cannot change through ordinary editing; referenced types are disabled rather than deleted.
11. Unit Type changes are allowed only for Planned, unreferenced Units and must preserve capability constraints.
12. Unit status transitions and closure-date rules are exactly those specified in the proposal; Closed Units cannot be reopened through ordinary editing.
13. Active or Inactive Unit capability changes are not authorized in B2.
14. Institution lifecycle does not automatically cascade to Units.
15. Unreferenced deletion is allowed; normal static-Link protection must block referenced deletion when an authorized dependent DocType exists.

## Authorized permissions

No new role is authorized.

| Existing role | Access |
|---|---|
| `Talisma Institution Manager` | Read Unit Types; create, read, and update Units; delete Units only while unreferenced; no import/export by default |
| `Talisma Institution Viewer` | Read Unit Types and Units |
| `System Manager` | Configure Unit Types and perform administrative development/recovery access |

These are DocType-level permissions only. Until Scope Grant and server-side row filtering are independently approved and implemented, Academic Unit access must not be assigned to a user who is not allowed to see every Institution in that site.

## Required verification

Implementation acceptance requires all sixteen test and operational groups in the proposal, including:

- UUID, normalization, immutability, interval, lifecycle, disabled-Type, and capability tests;
- normal and concurrent uniqueness tests;
- confirmation that no hierarchy, campus, mapping, ownership, or permission scope is inferred;
- permission and change-tracking tests;
- installation and repeated migration without Education;
- idempotent database-constraint verification; and
- backup/restore and isolated uninstall/dependency verification.

## Explicit exclusions

This acceptance does not authorize:

- Structure Version or Unit Placement;
- `parent_unit`, roots, ordering, cycle validation, hierarchy approval, or hierarchy activation;
- Unit Closure, closure generation, build IDs, hierarchy caches, or descendant queries;
- Scope Grant, row-level permission hooks, user scope, or reorganization access review;
- lineage, merge/split/successor relationships, name history, or reorganization automation;
- Campus placement, facilities, standard mappings, academic ownership, or responsibility assignments;
- Company, Department, Branch, Cost Center, Program, Course, or Education links and adapters;
- identity changes, standard-record custom fields, source-data migration, or seed data;
- APIs, pages, portals, workspaces, reports, fixtures, workflows, jobs, or integrations;
- Docker/Compose changes or Frappe/ERPNext core modifications.

## Implementation change control

Implementation may begin only after this acceptance record is reviewed and merged into `develop`. It must use a new feature branch and match this record exactly. Any additional field, role, DocType, hook, index purpose, API, migration behavior, fixture, seed record, or standard-record customization requires renewed approval.

Completion requires code review, automated tests, repeated `bench migrate`, database-constraint verification, permissions verification, backup evidence, and updated implementation documentation.

## Future gates

Slice B2 acceptance does not authorize subsequent institutional slices. Structure Version, Placement, Unit Closure, and Scope Grant each remain independently gated. Mapping, ownership, lineage, responsibility, and reorganization behavior also remain independently gated.
