# Institutional Schema Slice B3: Structure Version and Unit Placement Proposal

- **Architecture:** Accepted ADR-003 Institutional Hierarchy
- **Status:** Accepted on 2026-07-11; implementation boundary recorded in the acceptance record
- **Prepared:** 2026-07-11
- **Scope:** `Talisma Structure Version` and `Talisma Unit Placement` only

## Purpose

This proposal adds an immutable, effective-dated representation of academic-unit parentage without changing stable `Talisma Academic Unit` records. It allows governance teams to prepare and approve a structure snapshot while preserving prior versions for historical interpretation. The project owner accepted it on 2026-07-11; the exact authorization is recorded in the [B3 Acceptance Record](INSTITUTIONAL_SCHEMA_SLICE_B3_STRUCTURE_ACCEPTANCE.md).

B3 does not activate a structure for permissions, ownership, reporting, or integrations. Submission means the placement graph passed governance validation; it does not mean Closure rows exist or that any consumer may traverse it in production.

## Architectural boundary

| Concern | Authority in or after B3 |
|---|---|
| Stable Institution, Campus, Unit Type, and Unit identity | Existing implemented masters |
| Effective academic parentage | Proposed Structure Version and Unit Placement |
| Structure approval and immutability boundary | Structure Version submission |
| Descendant materialization and graph cache | Deferred Unit Closure slice |
| Active-version pointer and atomic activation | Deferred Unit Closure/activation slice |
| User organizational scope | Deferred Scope Grant slice |
| Program/Course ownership and standard mappings | Separately gated records |

No B3 record is an authorization source. Consumers must fail closed rather than infer descendants directly from Draft or merely Submitted placements.

## Proposed `Talisma Structure Version`

- **Module:** `Talisma SIS`
- **Naming:** server-generated UUIDv4 stored in `name`
- **Submittable:** Yes
- **Rename:** Disabled
- **Track changes:** Enabled
- **Quick entry:** Disabled
- **Allow import:** Disabled

### Fields

| Field | Type | Required | Constraint and meaning |
|---|---|---:|---|
| `institution` | Link: Talisma Institution | Yes | Immutable scope; indexed |
| `structure_code` | Data | Yes | Stable normalized code, unique within Institution and purpose; immutable |
| `structure_name` | Data | Yes | Searchable display title |
| `structure_purpose` | Select | Yes | `Academic Governance` only in B3 |
| `valid_from` | Date | Yes | Inclusive effective start |
| `valid_to` | Date | Conditional | Exclusive effective end; optional in Draft and required on submit |
| `supersedes` | Link: Talisma Structure Version | No | Prior submitted version in the same Institution and purpose |
| `change_summary` | Small Text | Yes | Governance explanation |
| `approval_reference` | Data | Yes on submit | External decision or meeting reference |

`materialization_status`, `materialized_on`, active-version pointers, build IDs, cache keys, and activation timestamps are excluded from B3.

## Proposed `Talisma Unit Placement`

- **Module:** `Talisma SIS`
- **Naming:** server-generated UUIDv4 stored in `name`
- **Submittable:** No
- **Rename:** Disabled
- **Track changes:** Enabled
- **Quick entry:** Disabled
- **Allow import:** Disabled

### Fields

| Field | Type | Required | Constraint and meaning |
|---|---|---:|---|
| `structure_version` | Link: Talisma Structure Version | Yes | Owning Draft/Submitted version; indexed and immutable |
| `institution` | Link: Talisma Institution | Yes | Read-only value derived from Structure Version; indexed and immutable |
| `academic_unit` | Link: Talisma Academic Unit | Yes | Child unit; unique once per Structure Version |
| `parent_unit` | Link: Talisma Academic Unit | No | Null identifies a root in that version |
| `display_order` | Int | No | Non-negative sibling presentation hint; no identity meaning |

Placement is standalone for indexing and graph validation. It is authoritative only as part of its submitted Structure Version. It does not copy Unit names or codes.

## Naming and database constraints

- Both DocTypes use immutable UUIDv4 names.
- `structure_code` is trimmed, uppercased, and restricted to `A-Z`, `0-9`, hyphen, and underscore with length 2–32.
- `(institution, structure_purpose, normalized structure_code)` is unique and non-recyclable.
- `(structure_version, academic_unit)` is unique.
- `supersedes`, when present, is unique so an accepted chain cannot silently fork.
- App-owned MariaDB constraints must be created through idempotent post-model-sync patches.
- Application pre-checks provide clear errors; database constraints remain authoritative for competing requests and validation bypass.

## Draft behavior

1. A Structure Version may be edited only while Draft.
2. Draft placements may temporarily contain missing parents or cycles while work is in progress, but each individual placement must use the Structure Version's Institution and reject self-parenting immediately.
3. Institution, purpose, and structure code cannot change after the Structure Version is inserted.
4. Structure Version and Unit references on a Placement cannot change after placement insertion; delete and recreate the Draft placement instead.
5. Placements may be created, edited, or deleted only while their Structure Version is Draft.
6. `institution` is derived server-side from `structure_version`; a conflicting supplied value is rejected.
7. `display_order` must be zero or positive. Duplicate sibling order is allowed and resolved secondarily by Unit name/code in presentation clients.
8. Draft Structure deletion requires its placements to be deleted first; no silent cascade is authorized.

## Submission validation

Submission is one transaction and must acquire a bounded MariaDB advisory lock scoped to `(institution, structure_purpose)`. Failure to acquire the lock fails clearly without partial changes.

Before submission, validate:

1. Institution is Planned or Active and the version interval fits Institution validity.
2. `valid_to` is present and strictly after `valid_from` under the half-open interval convention.
3. At least one Placement exists.
4. Every Placement and referenced Unit belongs to the Structure Version's Institution.
5. Every child Unit appears exactly once.
6. Every non-null parent has its own Placement in the same version.
7. No placement is self-parented and the complete graph is acyclic.
8. Multiple roots are allowed; every node is reachable from exactly one root.
9. Maximum supported depth is 32 edges; deeper structures fail submission.
10. Unit validity covers the Structure Version interval. Current Unit status alone does not rewrite historical eligibility.
11. No other submitted version for the same Institution and purpose has an overlapping effective interval.
12. `supersedes`, when set, is submitted, belongs to the same Institution/purpose, precedes this version, and is not already superseded by another version.
13. `change_summary` and `approval_reference` are present.

Cycle and reachability validation must be deterministic and operate on a single in-memory graph loaded in bounded queries, not through per-node database traversal.

## Submitted behavior

- Submitted Structure Versions and their Placements are immutable through ordinary editing and deletion.
- No role receives ordinary cancel permission in B3. Corrections require a new successor version.
- Submission does not activate a structure, create Closure rows, alter Academic Units, change permissions, or publish integration events.
- No transaction, permission decision, report, ownership assignment, or API may claim a B3 version is active.
- A later activation slice must explicitly define materialization, reconciliation, failure recovery, and the active-version pointer.

## Concurrency and effective intervals

Submitted intervals are bounded and half-open: `[valid_from, valid_to)`. Draft versions may leave `valid_to` blank, but submission cannot. Adjacent versions may use `previous.valid_to = next.valid_from`; overlapping submitted versions are forbidden for one Institution and purpose. This rule is clarified by the [B3 valid-to amendment](INSTITUTIONAL_SCHEMA_SLICE_B3_VALID_TO_AMENDMENT.md).

Submission serializes by Institution/purpose using a MariaDB advisory lock and re-runs overlap/supersession queries inside the transaction. Numeric target: two simultaneous overlapping submissions must produce exactly one success and one controlled failure.

## Scale targets

- Validate at least 10,000 Placements in one Structure Version.
- Enforce maximum depth 32.
- Submission validation target is under 30 seconds at 10,000 Placements on the documented production reference environment.
- Draft list/filter queries require indexes on Structure Version, Institution, Academic Unit, and Parent Unit.
- No Closure performance claim is made in B3.

## Permissions

One new app-owned role is proposed to distinguish structure approval from ordinary institutional maintenance:

| Role | Proposed access |
|---|---|
| `Talisma Institution Manager` | Create/read/write/delete Draft Structure Versions and Draft Placements; no submit/cancel |
| `Talisma Academic Structure Approver` | Read and submit Structure Versions; read Placements; framework write permission only where required for submission |
| `Talisma Institution Viewer` | Read Structure Versions and Placements |
| `System Manager` | Administrative development/recovery access; submitted immutability still enforced by controllers |

Because Frappe submit permission also requires write, strict preparer/approver separation cannot rely on DocPerm alone. B3 records the approver through audit and `approval_reference`; a separately approved workflow is required before claiming formal segregation of duties.

Permissions remain DocType-level. Until Scope Grant is implemented, these roles must not be assigned to users who cannot see every Institution in the site.

## Required implementation tests

1. Install and migrate without Education; generate immutable UUIDv4 names.
2. Normalize and validate Structure codes.
3. Enforce scoped Structure-code, Placement-unit, and supersedes uniqueness at application and database layers.
4. Verify immutable Structure identity and Placement links.
5. Derive and enforce Placement Institution.
6. Reject Placement edits/deletes when the Structure is submitted.
7. Validate Institution, Unit, and interval consistency.
8. Reject empty submissions, missing-parent placements, self-parenting, cycles, and excessive depth.
9. Accept multiple roots and a valid forest.
10. Reject overlapping submitted intervals and invalid supersession chains.
11. Prove competing overlapping submissions cannot both succeed.
12. Confirm submission creates no Closure, active pointer, permission scope, mapping, ownership, or Unit mutation.
13. Verify Manager, Approver, Viewer, System Manager, and unauthorized-user permissions.
14. Verify change tracking and Draft/submitted deletion behavior.
15. Run deterministic graph validation at representative 1,000 and target 10,000 Placement scales.
16. Run repeated migrate, constraint inspection, backup/restore, and isolated uninstall/dependency tests.

## Migration and rollback

- B3 creates no Structure, Placement, or seed hierarchy data automatically.
- Existing Department or other trees are not imported or inferred.
- Initial hierarchy migration remains a separately approved, rehearsed process.
- Constraint patches must be repeatable and documented for uninstall; app uninstall normally removes app-owned DocType tables.
- Rollback after submitted structures exist requires governed export and dependency analysis. Destructive automatic cleanup is prohibited.

## Explicit exclusions

This proposal does not authorize:

- Unit Closure, transitive rows, build IDs, caches, materialization state, or rebuild jobs;
- active-version pointers, activation, scheduled transitions, or consumer APIs;
- Scope Grant, descendant permissions, row-level hooks, or user scope;
- Standard Mapping, Academic Ownership, Program/Course relationships, or Education adapters;
- Unit lineage, mergers, splits, successors, responsibility assignments, or reorganization automation;
- custom fields on standard records, source-data migration, or seed structures;
- pages, portals, workspaces, reports, fixtures, workflows, scheduled jobs, or integrations;
- Docker/Compose changes or Frappe/ERPNext core modifications.

## Review checklist

- [x] Exact Structure Version and Placement fields approved.
- [x] Submission selected as the approval and immutability boundary.
- [x] Forest, root, parent-presence, cycle, depth, and interval rules approved.
- [x] Composite constraints and MariaDB submission lock strategy approved.
- [x] Supersession and non-overlap rules approved.
- [x] Submitted structures explicitly remain inactive and unusable for permissions.
- [x] New Academic Structure Approver role and DocPerm limitation accepted.
- [x] Scale targets and required tests approved.
- [x] Migration, rollback, and exclusions approved.
- [x] Project owner recorded explicit implementation authorization on 2026-07-11.

## Decision outcome

**Slice B3: Talisma Structure Version and Talisma Unit Placement only** was accepted without qualifications by Prince Ebinezer, Project Owner, on 2026-07-11. Implementation must remain blocked until the acceptance record is reviewed and merged.

## References

- [ADR-003 Institutional Hierarchy](ADR-003-INSTITUTIONAL-HIERARCHY.md)
- [Institutional Hierarchy Model](INSTITUTIONAL_HIERARCHY_MODEL.md)
- [Institutional Physical Schema Proposal](INSTITUTIONAL_PHYSICAL_SCHEMA_PROPOSAL.md)
- [Institutional Schema Review Gate](INSTITUTIONAL_SCHEMA_REVIEW_GATE.md)
- [Institutional Operations and Security](INSTITUTIONAL_SCHEMA_OPERATIONS_AND_SECURITY.md)
- [Institutional Migration and Test Plan](INSTITUTIONAL_SCHEMA_MIGRATION_AND_TEST_PLAN.md)
- [Slice B2 Acceptance Record](INSTITUTIONAL_SCHEMA_SLICE_B2_ACADEMIC_UNIT_ACCEPTANCE.md)
- [Slice B3 Acceptance Record](INSTITUTIONAL_SCHEMA_SLICE_B3_STRUCTURE_ACCEPTANCE.md)
- [Slice B3 Valid-To Amendment](INSTITUTIONAL_SCHEMA_SLICE_B3_VALID_TO_AMENDMENT.md)
