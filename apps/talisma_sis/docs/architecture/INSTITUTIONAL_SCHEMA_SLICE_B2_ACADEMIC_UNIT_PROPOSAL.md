# Institutional Schema Slice B2: Academic Unit Type and Academic Unit Proposal

- **Architecture:** Accepted ADR-003 Institutional Hierarchy
- **Status:** Accepted on 2026-07-11; implementation boundary recorded in the acceptance record
- **Prepared:** 2026-07-11
- **Scope:** `Talisma Academic Unit Type` and `Talisma Academic Unit` only

## Purpose

This proposal defines the stable masters needed to identify academic-governance units beneath an existing `Talisma Institution`. It does not define a hierarchy. Parentage, roots, ordering, and descendant relationships belong to later Structure Version and Placement slices so that reorganization does not rewrite stable unit identity.

The project owner accepted this proposal on 2026-07-11. The exact authorization and change-control conditions are recorded in the [Slice B2 Acceptance Record](INSTITUTIONAL_SCHEMA_SLICE_B2_ACADEMIC_UNIT_ACCEPTANCE.md). This document itself creates no DocTypes, roles, hooks, migrations, APIs, fixtures, or runtime behavior.

## Architectural boundary

| Concern | Authority in or after this slice |
|---|---|
| Institutional policy and security root | Existing `Talisma Institution` |
| Physical or operational location | Existing `Talisma Campus` |
| Stable academic-governance category | Proposed `Talisma Academic Unit Type` |
| Stable academic-governance identity | Proposed `Talisma Academic Unit` |
| Parent, root, ordering, and effective hierarchy | Deferred Structure Version and Placement slices |
| Descendant materialization | Deferred Unit Closure slice |
| User authorization scope | Deferred Scope Grant slice |
| Legal, HR, financial, and Education ownership | Existing standard records and separately gated mappings |

Institution and Campus are not Academic Unit types. An Academic Unit does not imply a Company, Department, Branch, Cost Center, campus, Program, Course, employee assignment, or permission grant.

## Proposed `Talisma Academic Unit Type`

- **Module:** `Talisma SIS`
- **Naming:** server-generated UUIDv4 stored in `name`
- **Submittable:** No
- **Rename:** Disabled
- **Track changes:** Enabled
- **Quick entry:** Disabled initially
- **Allow import:** Disabled initially

### Fields

| Field | Type | Required | Constraint and meaning |
|---|---|---:|---|
| `type_code` | Data | Yes | Globally unique, normalized stable code; immutable |
| `type_name` | Data | Yes | Current searchable display name |
| `can_grant_credentials` | Check | Yes | Maximum credential-granting capability; default off |
| `can_own_programs` | Check | Yes | Maximum program-ownership capability; default off |
| `can_own_courses` | Check | Yes | Maximum course-ownership capability; default off |
| `disabled` | Check | Yes | Prevents assignment to new Units; default off |

The type master is governed configuration, not a hierarchy level. The initial design does not seed fixed College, School, Faculty, Department, Division, Institute, Center, or Other records; institutions may use the governed types that are explicitly configured. Type codes are global so their meaning cannot vary silently between Institutions.

### Type naming and lifecycle

- `name` is an immutable UUIDv4 and carries no business meaning.
- `type_code` permits `A-Z`, `0-9`, hyphen, and underscore only, with length 2–32.
- Normalization trims and uppercases `type_code` before validation.
- A type code cannot change or be reused.
- Display names and capability maxima may change only while the type is unreferenced.
- Once referenced by an Academic Unit, capability maxima cannot be reduced or broadened in this slice; a later governed migration may define that transition.
- A referenced type is disabled rather than deleted. Normal Frappe Link protection blocks its deletion.
- Disabled types remain visible on historical Units but cannot be selected for a new Unit or assigned during an ordinary Unit type change.

## Proposed `Talisma Academic Unit`

- **Module:** `Talisma SIS`
- **Naming:** server-generated UUIDv4 stored in `name`
- **Submittable:** No
- **Rename:** Disabled
- **Track changes:** Enabled
- **Quick entry:** Disabled initially
- **Allow import:** Disabled initially

### Fields

| Field | Type | Required | Constraint and meaning |
|---|---|---:|---|
| `institution` | Link: Talisma Institution | Yes | Immutable security root; indexed |
| `unit_code` | Data | Yes | Trimmed and uppercased; unique within Institution; immutable |
| `unit_name` | Data | Yes | Current searchable display name |
| `short_name` | Data | No | Searchable display abbreviation |
| `unit_type` | Link: Talisma Academic Unit Type | Yes | Active governed type; indexed |
| `status` | Select | Yes | Planned, Active, Inactive, Closed; default Planned |
| `valid_from` | Date | Yes | Start of stable Unit validity |
| `valid_to` | Date | No | Open-ended when blank; cannot precede `valid_from` |
| `can_grant_credentials` | Check | Yes | Unit capability, bounded by its type; default off |
| `can_own_programs` | Check | Yes | Unit capability, bounded by its type; default off |
| `can_own_courses` | Check | Yes | Unit capability, bounded by its type; default off |

There is deliberately no `parent_unit`, `campus`, `company`, `department`, `cost_center`, `leader`, `successor_unit`, structure pointer, or descendant field. `Merged` is not an ordinary Unit status in B2 because merger and split semantics require the separately gated lineage and structure design.

## Unit naming and uniqueness

- `name` is an immutable UUIDv4 and contains no Institution or Unit code.
- `unit_code` permits `A-Z`, `0-9`, hyphen, and underscore only, with length 2–32.
- The business key is `(institution, normalized unit_code)`.
- The same code may exist in different Institutions but cannot be reused within one Institution, including after closure.
- Application validation must provide a clear duplicate message.
- Implementation must add and verify an app-owned MariaDB composite unique constraint or index because ordinary Frappe metadata cannot express scoped uniqueness.
- Concurrent inserts of the same normalized business key must result in one success and one controlled duplicate failure.

## Validation and lifecycle

1. Institution and Unit code cannot change after insertion.
2. A new Unit may reference a Planned or Active Institution, but not an Inactive or Closed Institution.
3. `valid_from` cannot precede the Institution's `valid_from`.
4. When the Institution has `valid_to`, the Unit interval must not extend beyond it.
5. `valid_to` must be on or after `valid_from`.
6. A new Unit must use a non-disabled Unit Type.
7. Each enabled Unit capability must also be enabled as a maximum on its Unit Type.
8. Changing `unit_type` is allowed only while the Unit is Planned and unreferenced, and the new type must permit every enabled Unit capability.
9. Active, Inactive, or Closed Units cannot change type through ordinary editing.
10. Planned may transition to Active or Closed; Active may transition to Inactive or Closed; Inactive may transition to Active or Closed.
11. Reopening a Closed Unit is not authorized initially; a separately reviewed correction procedure is required.
12. Setting Closed requires `valid_to`; setting `valid_to` does not by itself change status or create structure, lineage, or descendant records.
13. Closed and Inactive Units remain available for historical references but are invalid for new assignments in later slices.
14. Deletion succeeds only while a Unit is unreferenced. Once a dependent static Link exists, Frappe link protection must block deletion.

No Institution status cascade is proposed. Institution lifecycle changes must report affected Units and require an explicit governed action in a later operational slice.

## Capability semantics

Type capabilities are maxima, while Unit capabilities state what that specific Unit may do. A Unit may narrow its type by leaving a capability off, but cannot broaden it. These flags do not themselves authorize credential conferral or create Program/Course ownership; they are validation inputs for future, separately approved ownership workflows.

Capability changes on an Active or Inactive Unit are not authorized in B2 because their downstream impact cannot be assessed until ownership records exist. Planned, unreferenced Units may change capabilities within their type maxima. Closed Units are immutable except through a separately reviewed correction procedure.

## Permissions

No new roles are proposed.

| Existing role | Proposed access |
|---|---|
| `Talisma Institution Manager` | Read Unit Types; create, read, and update Academic Units; delete Units only while unreferenced; no import/export by default |
| `Talisma Institution Viewer` | Read Unit Types and Academic Units |
| `System Manager` | Configure Unit Types and perform administrative development/recovery access |

These permissions are DocType-level only. Until Scope Grant and server-side row filtering are separately approved and implemented, a multi-institution production deployment must not assign Academic Unit access to users who are not permitted to see every Institution in that site. A generic role does not establish Institution or descendant scope.

## Audit and security

- Framework change tracking records display, type, status, date, and capability changes.
- UUIDs and stable codes are used in integration and audit references; display names are not identifiers.
- Institution, Unit Type, code, status, dates, and capabilities are never authorization shortcuts.
- Link searches and APIs require row-level scope enforcement before multi-institution business use.
- No capability flag grants a Frappe permission, role, hierarchy scope, or ownership right.

## Required implementation tests

If B2 is later accepted, implementation verification must include:

1. Install and migrate on `talisma.local` without Education.
2. Generate immutable UUIDv4 names for both DocTypes.
3. Normalize codes and reject invalid characters or length.
4. Enforce global Type-code and Institution-scoped Unit-code uniqueness, including concurrent inserts.
5. Allow the same Unit code in different Institutions.
6. Prevent Institution, Unit code, and referenced Type-code changes.
7. Validate Institution and Unit effective intervals.
8. Reject new Units for Inactive or Closed Institutions.
9. Reject disabled types for new assignment and protect referenced Type deletion.
10. Enforce capability maxima and Planned/unreferenced change rules.
11. Enforce Unit type-change, status-transition, close-date, and Closed immutability rules.
12. Verify that no parentage, descendant, campus, standard mapping, or permission behavior is inferred.
13. Verify Manager, Viewer, System Manager, and unauthorized-user permissions.
14. Verify change tracking and unreferenced/referenced deletion behavior.
15. Run repeated `bench migrate` and verify database constraints remain idempotent.
16. Run backup/restore verification and isolated uninstall/dependency tests.

## Migration and rollback

- Initial implementation would create no Type or Unit seed data and modify no standard DocTypes.
- Department, Campus, Company, Branch, Cost Center, Program, and Course records must not be auto-converted or auto-mapped.
- Schema installation and composite uniqueness mechanisms must be migration-safe, repeatable, and have an explicit uninstall strategy.
- Rollback before business use removes app-owned schema through the normal app/site test process.
- Rollback after references exist requires governed export and dependency analysis; destructive automatic cleanup is prohibited.

## Explicit exclusions and separate gates

This proposal does not authorize:

- Structure Version, Unit Placement, any `parent_unit`, roots, ordering, cycle checks, or hierarchy activation;
- Unit Closure rows, closure generation, build IDs, hierarchy caches, or descendant queries;
- Scope Grant, row-level permission hooks, user scope, or reorganization access review;
- lineage, merge/split/successor relationships, name history, or reorganization automation;
- Campus placement, facilities, or physical-location ownership;
- Standard Mapping, Academic Ownership, responsibility assignment, Company/Department/Branch/Cost Center links, or Education adapters;
- identity changes, custom fields on standard records, source-data migration, or seed data;
- APIs, pages, portals, workspaces, reports, fixtures, workflows, scheduled jobs, or integrations;
- Docker/Compose changes or Frappe/ERPNext core changes.

Structure Version, Placement, Unit Closure, and Scope Grant must each remain separately gated. Acceptance of B2 must not be interpreted as approval to implement or scaffold any of them.

## Review checklist

- [x] Unit Type global governance, fields, naming, and disabled behavior approved.
- [x] Academic Unit fields, naming, scoped uniqueness, and effective interval approved.
- [x] Stable Unit identity without parent, campus, mapping, or successor fields approved.
- [x] Type maxima and Unit capability semantics approved.
- [x] Unit type-change and lifecycle transition rules approved.
- [x] Existing roles and the pre-Scope-Grant multi-institution limitation approved.
- [x] Tests, migration, rollback, and no-seed-data behavior approved.
- [x] Separate gates for Structure Version, Placement, Unit Closure, and Scope Grant reaffirmed.
- [x] Project owner recorded explicit implementation authorization on 2026-07-11.

## Decision outcome

**Slice B2: Talisma Academic Unit Type and Talisma Academic Unit only** was accepted without qualifications by Prince Ebinezer, Project Owner, on 2026-07-11. Implementation must occur on a separate feature branch after the acceptance record is merged.

## References

- [ADR-003 Institutional Hierarchy](ADR-003-INSTITUTIONAL-HIERARCHY.md)
- [ADR-003 Acceptance Record](ADR-003-ACCEPTANCE-RECORD.md)
- [Institutional Hierarchy Model](INSTITUTIONAL_HIERARCHY_MODEL.md)
- [Institutional Physical Schema Proposal](INSTITUTIONAL_PHYSICAL_SCHEMA_PROPOSAL.md)
- [Institutional Schema Review Gate](INSTITUTIONAL_SCHEMA_REVIEW_GATE.md)
- [Institutional Schema Operations and Security](INSTITUTIONAL_SCHEMA_OPERATIONS_AND_SECURITY.md)
- [Institutional Schema Migration and Test Plan](INSTITUTIONAL_SCHEMA_MIGRATION_AND_TEST_PLAN.md)
- [Campus Slice B1 Acceptance Record](INSTITUTIONAL_SCHEMA_SLICE_B1_CAMPUS_ACCEPTANCE.md)
- [Slice B2 Acceptance Record](INSTITUTIONAL_SCHEMA_SLICE_B2_ACADEMIC_UNIT_ACCEPTANCE.md)
