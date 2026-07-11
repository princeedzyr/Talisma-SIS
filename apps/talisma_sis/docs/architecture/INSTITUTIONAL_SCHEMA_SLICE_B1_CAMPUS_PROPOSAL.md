# Institutional Schema Slice B1: Campus Proposal

- **Architecture:** Accepted ADR-003 Institutional Hierarchy
- **Status:** Proposed for architecture approval; implementation is not authorized
- **Prepared:** 2026-07-11
- **Scope:** `Talisma Campus` only

## Purpose

This proposal introduces the physical and operational campus master beneath an existing `Talisma Institution`. It deliberately separates campus location from academic governance, ERPNext legal/accounting structure, and ERPNext Branch semantics.

Approval of this document would authorize a later implementation package only after the project owner records explicit acceptance. This proposal itself creates no DocTypes, roles, hooks, migrations, APIs, or runtime behavior.

## Architectural boundary

| Concern | Authority |
|---|---|
| Institutional policy and security root | `Talisma Institution` |
| Physical/operational campus | Proposed `Talisma Campus` |
| Legal entity and accounting books | ERPNext `Company` |
| ERPNext operational branch | ERPNext `Branch` |
| Academic governance hierarchy | Deferred Talisma Academic Unit slices |
| Buildings, rooms, facilities and geospatial boundaries | Deferred facilities architecture |

Campus does not establish academic ownership, financial posting, HR reporting, or descendant permission scope. Any future mapping to Branch, Company, Department, Cost Center, or Education records requires a separately approved mapping slice.

## Proposed DocType

- **DocType:** `Talisma Campus`
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
| `campus_code` | Data | Yes | Trimmed and uppercased; unique within Institution; immutable |
| `campus_name` | Data | Yes | Current searchable display name |
| `short_name` | Data | No | Searchable display abbreviation |
| `campus_type` | Select | Yes | Main, Satellite, Learning Center, Virtual, Other |
| `status` | Select | Yes | Planned, Active, Inactive, Closed; default Planned |
| `valid_from` | Date | Yes | Start of campus validity |
| `valid_to` | Date | No | Open-ended when blank; cannot precede `valid_from` |
| `timezone` | Autocomplete | Yes | Valid IANA timezone; initialized from Institution for a new record |
| `address` | Link: Address | Conditional | Required for non-Virtual campuses; blank for Virtual is permitted |
| `website` | Data | No | Valid HTTP or HTTPS URL |

`parent_campus` and `is_virtual` are excluded. Parent grouping overlaps the deferred facilities model, while a separate virtual flag would duplicate `campus_type`. Virtual behavior is derived exclusively from `campus_type = Virtual`.

## Naming and uniqueness

- `name` is an immutable UUIDv4 and contains no institution or campus code.
- `campus_code` permits `A-Z`, `0-9`, hyphen and underscore only, with length 2–32.
- The business key is `(institution, normalized campus_code)`.
- The same code may exist in different Institutions but cannot be reused within one Institution, including after closure.
- Application validation must provide a clear duplicate message.
- Implementation must add and verify an app-owned MariaDB composite unique constraint or index because ordinary Frappe field metadata cannot express scoped uniqueness.
- Concurrent inserts of the same normalized key must result in one success and one controlled duplicate failure.

## Validation and lifecycle

1. Institution and campus code cannot change after insertion.
2. A new campus may reference a Planned or Active Institution, but not an Inactive or Closed Institution.
3. `valid_from` cannot precede the Institution's `valid_from`.
4. When the Institution has `valid_to`, the Campus interval must not extend beyond it.
5. `valid_to` must be on or after `valid_from`.
6. `timezone` must resolve through framework-supported IANA timezone data.
7. Physical campus types require an Address; Virtual must not require one.
8. Website, when present, must use HTTP or HTTPS.
9. Closed and Inactive campuses remain available for historical references but are not valid for new operational assignments.
10. Reopening a Closed campus is not authorized initially; a separately reviewed correction procedure is required.
11. Deletion succeeds only while the campus is unreferenced. Once a dependent static Link exists, Frappe link protection must block deletion.

No automatic Institution status cascade is proposed. Institution lifecycle changes must instead report affected campuses and require an explicit governed action in a later operational slice.

## Permissions

No new roles are required.

| Existing role | Proposed access |
|---|---|
| `Talisma Institution Manager` | Create, read and update Campus; delete only while unreferenced; no import/export by default |
| `Talisma Institution Viewer` | Read only |
| `System Manager` | Administrative access for development and recovery |

These permissions are DocType-level only. Institution-scoped row-level enforcement depends on the future approved Scope Grant model. Until then, a multi-institution production deployment must not assign Campus access to users who are not permitted to see every Institution in that site.

## Audit and security

- Framework change tracking records name, type, status, dates, timezone, address, and website changes.
- UUIDs and stable codes are used in integration/audit references; display names are not identifiers.
- Address remains a standard Frappe record and is not owned or automatically deleted by Campus.
- Campus code, Institution, and UUID are never exposed as authorization shortcuts.
- Link searches and APIs require row-level scope enforcement before multi-institution business use.

## Required implementation tests

1. Install and migrate on `talisma.local` without Education.
2. Generate immutable UUIDv4 names.
3. Normalize campus codes and reject invalid characters or length.
4. Enforce scoped uniqueness across normal and concurrent inserts.
5. Allow the same code in different Institutions.
6. Prevent Institution and campus-code changes after insertion.
7. Validate Institution and Campus effective intervals.
8. Reject new campuses for Inactive or Closed Institutions.
9. Validate all campus types and Virtual address behavior.
10. Validate IANA timezone and HTTP/HTTPS website values.
11. Verify Manager, Viewer, System Manager, and unauthorized-user permissions.
12. Verify change tracking.
13. Verify unreferenced deletion and, once a dependent static Link is authorized, referenced deletion protection.
14. Run repeated `bench migrate` and verify the composite unique constraint remains idempotent.
15. Run backup and restore verification after schema installation.
16. Document and test uninstall/dependency behavior on an isolated site.

## Migration and rollback

- The initial implementation creates no Campus seed data and modifies no standard DocTypes.
- Schema installation must be migration-safe and repeatable.
- The composite uniqueness mechanism must have an explicit idempotent creation and uninstall strategy.
- Rollback before business use removes the app-owned schema through the normal app/site test process.
- Rollback after Campus references exist requires governed data export and dependency analysis; destructive automatic cleanup is prohibited.

## Explicit exclusions

Not authorized by this proposal:

- Academic Unit Type, Academic Unit, Structure Version, Placement, Closure, or Scope Grant;
- `parent_campus`, buildings, rooms, facilities, geofences, or campus hierarchies;
- mappings to Company, Branch, Department, Cost Center, Address ownership, or accounting dimensions;
- Program, Course, Curriculum, ownership, registration, or delivery relationships;
- identity records, row-level permission hooks, custom fields on standard records, or data migration;
- APIs, portal pages, workspaces, reports, fixtures, workflows, scheduled jobs, or integrations;
- Education installation, Docker/Compose changes, or Frappe/ERPNext core changes.

## Approval checklist

- [ ] Campus is approved as distinct from Branch and Academic Unit.
- [ ] Exact fields and Select values are approved.
- [ ] Institution-scoped immutable code and composite uniqueness are approved.
- [ ] `parent_campus` and redundant `is_virtual` are deferred.
- [ ] Address requirements for Virtual versus physical campuses are approved.
- [ ] Lifecycle and effective-interval rules are approved.
- [ ] Existing Manager/Viewer roles are approved; no new role is required.
- [ ] Multi-institution limitation before Scope Grant enforcement is accepted.
- [ ] Tests, migration, rollback, and exclusions are approved.
- [ ] Project owner has recorded explicit implementation authorization.

## Decision requested

Approve, reject, or request changes to **Slice B1: Talisma Campus only**. Approval must identify the project owner, date, exact authorized scope, and any qualifications. Implementation must occur on a separate feature branch after acceptance.

## References

- [ADR-003 Institutional Hierarchy](ADR-003-INSTITUTIONAL-HIERARCHY.md)
- [ADR-003 Acceptance Record](ADR-003-ACCEPTANCE-RECORD.md)
- [Institutional Physical Schema Proposal](INSTITUTIONAL_PHYSICAL_SCHEMA_PROPOSAL.md)
- [Institutional Schema Review Gate](INSTITUTIONAL_SCHEMA_REVIEW_GATE.md)
- [Institutional Schema Operations and Security](INSTITUTIONAL_SCHEMA_OPERATIONS_AND_SECURITY.md)
- [Institutional Slice A Approval](INSTITUTIONAL_SCHEMA_SLICE_A_APPROVAL.md)
