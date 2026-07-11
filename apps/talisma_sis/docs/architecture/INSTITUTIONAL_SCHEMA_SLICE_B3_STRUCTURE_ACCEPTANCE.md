# Institutional Schema Slice B3: Structure Version and Unit Placement Acceptance Record

- **Architecture:** Accepted ADR-003 Institutional Hierarchy
- **Proposal:** [Slice B3 Structure Version and Unit Placement Proposal](INSTITUTIONAL_SCHEMA_SLICE_B3_STRUCTURE_PROPOSAL.md)
- **Outcome:** Accepted for implementation within the exact authorized scope
- **Approval date:** 2026-07-11
- **Approver:** Prince Ebinezer, Project Owner
- **Recorded by:** Talisma SIS architecture process

## Accepted decision

The project owner approves `Talisma Structure Version` and `Talisma Unit Placement` as the effective-dated academic-parentage model for stable `Talisma Academic Unit` records.

Submission is accepted as the governance-validation and immutability boundary. A submitted B3 structure is not active, materialized, or usable for authorization, ownership, reporting, or integration. The proposal's exact fields, forest rules, concurrency strategy, lifecycle, permissions, scale targets, tests, migration approach, and exclusions are binding.

## Authorized implementation scope

Two new standard DocTypes in the `talisma_sis` app and `Talisma SIS` module:

1. `Talisma Structure Version`
2. `Talisma Unit Placement`

Both use server-generated UUIDv4 names, disable rename, enable change tracking, disable quick entry and import, and create no seed data. Structure Version is submittable; Unit Placement is not.

### Authorized Structure Version fields

| Field | Type | Required | Accepted constraint |
|---|---|---:|---|
| `institution` | Link: Talisma Institution | Yes | Indexed, immutable scope |
| `structure_code` | Data | Yes | Normalized stable code, unique by Institution and purpose, immutable |
| `structure_name` | Data | Yes | Searchable display title |
| `structure_purpose` | Select | Yes | `Academic Governance` only |
| `valid_from` | Date | Yes | Inclusive effective start |
| `valid_to` | Date | No | Exclusive effective end; open-ended when blank |
| `supersedes` | Link: Talisma Structure Version | No | Unique prior submitted version in the same Institution and purpose |
| `change_summary` | Small Text | Yes | Governance explanation |
| `approval_reference` | Data | Yes on submit | External governance reference |

### Authorized Unit Placement fields

| Field | Type | Required | Accepted constraint |
|---|---|---:|---|
| `structure_version` | Link: Talisma Structure Version | Yes | Indexed and immutable |
| `institution` | Link: Talisma Institution | Yes | Read-only derived scope; indexed and immutable |
| `academic_unit` | Link: Talisma Academic Unit | Yes | Unique once per Structure Version; immutable |
| `parent_unit` | Link: Talisma Academic Unit | No | Null identifies a root; immutable after placement insertion |
| `display_order` | Int | No | Non-negative presentation hint |

No other fields are authorized.

## Accepted graph and lifecycle rules

1. Draft Structures and Placements may be edited only within the accepted Draft rules.
2. Draft graphs may be temporarily incomplete, but individual placements immediately reject self-parenting and Institution conflicts.
3. Submission requires at least one Placement and validates the complete graph atomically.
4. Every Unit appears once; every non-null parent has a Placement in the same version.
5. Multiple roots are allowed; every node belongs to exactly one rooted acyclic component.
6. Maximum depth is 32 edges.
7. Structure and Unit effective intervals must be compatible with Institution validity.
8. Submitted intervals for the same Institution and purpose cannot overlap.
9. Supersession is same-Institution, same-purpose, submitted, chronological, and non-forking.
10. Submitted Structures and Placements cannot be edited, deleted, or ordinarily cancelled. Corrections use a successor version.
11. Submission creates no Closure rows, active pointer, permissions, ownership, mappings, Unit mutation, or integration event.

## Accepted database and concurrency strategy

- Unique `(institution, structure_purpose, structure_code)`.
- Unique `(structure_version, academic_unit)`.
- Unique non-null `supersedes` to prevent silent chain forks.
- Idempotent app-owned post-model-sync MariaDB constraints.
- Clear application validation backed by database enforcement.
- Bounded MariaDB advisory lock scoped to Institution and purpose during submission.
- Overlap and supersession validation repeated inside the locked transaction.
- Competing overlapping submissions must yield one success and one controlled failure.

## Authorized permissions

One new app-owned role is authorized:

- `Talisma Academic Structure Approver`

| Role | Access |
|---|---|
| `Talisma Institution Manager` | Prepare and maintain Draft Structures and Placements; no submit/cancel |
| `Talisma Academic Structure Approver` | Read and submit Structures; read Placements; only framework-required write access |
| `Talisma Institution Viewer` | Read Structures and Placements |
| `System Manager` | Administrative development/recovery access; controller immutability remains enforced |

Frappe DocPerm alone does not prove formal preparer/approver segregation because submit requires write. No formal segregation-of-duties claim is authorized until a separate workflow is approved. Permissions remain site-wide DocType access until Scope Grant exists.

## Accepted scale and verification targets

- Maximum supported depth: 32.
- Representative validation: 1,000 Placements.
- Target validation: 10,000 Placements.
- Submission-validation target: under 30 seconds for 10,000 Placements on a documented production reference environment.
- Graph loading and validation must use bounded queries and deterministic in-memory traversal.

Implementation acceptance requires all sixteen test groups in the proposal, including graph validity, multiple roots, excessive depth, effective intervals, supersession, competing submissions, database constraints, permissions, immutability, no-activation assertions, repeated migration, backup/restore, and isolated uninstall/dependency verification.

## Explicit exclusions

This acceptance does not authorize:

- Unit Closure, transitive paths, materialization, build IDs, caches, or rebuild jobs;
- active-version pointers, activation, scheduled transitions, or consumer APIs;
- Scope Grant, descendant permissions, row-level permission hooks, or user scope;
- mappings, ownership, Program/Course relationships, or Education adapters;
- lineage, merge/split automation, successors beyond Structure supersession, or responsibility assignments;
- source hierarchy migration, seed structures, or standard-record custom fields;
- pages, portals, workspaces, reports, fixtures, workflows, scheduled jobs, or integrations;
- Docker/Compose changes or Frappe/ERPNext core modifications.

## Implementation change control

Implementation may begin only after this acceptance record is reviewed and merged into `develop`. It must occur on a new feature branch and match this record exactly. Any additional field, role, DocType, hook purpose, migration behavior, workflow, API, job, fixture, seed record, or core customization requires renewed approval.

Completion requires code review, automated graph and concurrency tests, repeated `bench migrate`, database-constraint verification, permission verification, backup evidence, performance evidence, and implementation documentation.

## Future gates

Unit Closure/materialization is the next independent architecture gate. Activation and active-version ownership must be explicit within that gate or a separate one. Scope Grant remains independently gated and cannot consume B3 Structures until an approved active/materialized version contract exists.
