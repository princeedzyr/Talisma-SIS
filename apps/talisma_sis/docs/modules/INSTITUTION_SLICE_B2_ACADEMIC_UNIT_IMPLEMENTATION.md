# Institution Slice B2: Academic Unit Implementation

- **Architecture authority:** [Slice B2 Acceptance Record](../architecture/INSTITUTIONAL_SCHEMA_SLICE_B2_ACADEMIC_UNIT_ACCEPTANCE.md)
- **Implementation branch:** `feat/institution-academic-unit-b2`
- **Implemented:** 2026-07-11
- **Scope:** `Talisma Academic Unit Type` and `Talisma Academic Unit` only

## Delivered schema

### Talisma Academic Unit Type

The governed global configuration master provides immutable normalized `type_code`, display name, three capability maxima, and a disabled flag. It uses UUIDv4 names, change tracking, no rename, no quick entry, and no import.

Only `System Manager` can configure Unit Types. Institution Manager and Viewer can read them. Referenced type names and capability maxima cannot change through ordinary editing; referenced types may be disabled and remain protected by normal Link deletion checks.

### Talisma Academic Unit

The stable Institution-scoped identity provides immutable Institution and normalized Unit code, display fields, governed type, status and validity, and three type-bounded capabilities. It uses UUIDv4 names, change tracking, no rename, no quick entry, and no import.

The database patch creates the composite unique index `unique_talisma_academic_unit_institution_code` over `(institution, unit_code)`. Application validation provides controlled duplicate errors, while MariaDB protects validation-bypass and concurrent insertion paths.

## Enforced behavior

- Codes are trimmed, uppercased, validated, immutable, and non-recyclable.
- New Units require a Planned or Active Institution and a non-disabled Unit Type.
- Unit validity must fit within Institution validity.
- Unit capabilities cannot exceed their Type maxima.
- Type changes are restricted to Planned Units.
- Capability changes stop when a Unit leaves Planned status.
- Lifecycle transitions follow the accepted Planned, Active, Inactive, and Closed graph.
- Closed Units require `valid_to` and cannot be changed or reopened through ordinary editing.
- Institution lifecycle does not cascade to Units.
- Manager, Viewer, and System Manager permissions match the acceptance record.

## Boundary confirmation

The implementation adds no:

- Structure Version, Placement, parent field, root, ordering, or cycle behavior;
- Unit Closure, hierarchy cache, descendant query, or build process;
- Scope Grant or row-level permission hook;
- Campus, Company, Department, Branch, Cost Center, Program, Course, or Education Link;
- mapping, ownership, lineage, successor, merge/split, identity, API, report, workflow, fixture, or seed data;
- Docker/Compose configuration or framework/core modification.

## Verification evidence

Verified on `talisma.local` with Frappe 16.25.0, ERPNext 16.26.2, and no Education app:

| Check | Result |
|---|---|
| Initial `bench migrate` | Passed; both DocTypes synchronized and composite-index patch executed |
| Repeated `bench migrate` | Passed; schema and patch behavior remained idempotent |
| Unit Type integration suite | 5 passed |
| Academic Unit integration suite | 11 passed |
| Full `talisma_sis` regression suite | 42 passed |
| Composite index inspection | Unique two-column index present in MariaDB in the correct column order |
| Database validation bypass | Duplicate composite key rejected by MariaDB |
| No-hierarchy metadata check | Passed |
| Site backup | Passed; configuration and compressed database backup created |
| Restore rehearsal | Not performed in this implementation workspace |
| Isolated uninstall/dependency rehearsal | Not performed in this implementation workspace |

The focused suites cover UUID naming, normalization, application and database uniqueness, immutable fields, validity, eligible Institution and Type state, capability bounds, lifecycle, permissions, change tracking, and explicit absence of hierarchy/mapping fields.

## Operational follow-up

Restore and isolated uninstall rehearsals remain release-gate evidence and must be completed before production deployment. They do not change the delivered schema or authorize any later institutional slice.

## Files

- `talisma_academic_unit_type` DocType metadata, controller, and integration tests
- `talisma_academic_unit` DocType metadata, controller, and integration tests
- idempotent composite-unique patch registered in `patches.txt`

Structure Version, Placement, Unit Closure, and Scope Grant remain separately gated.
