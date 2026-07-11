# Institutional Schema Slice B4: Unit Closure Materialization Proposal

- **Architecture:** Accepted ADR-003 Institutional Hierarchy
- **Depends on:** Accepted and implemented B3 Structure Version and Unit Placement
- **Status:** Accepted by the project owner; implementation remains gated until the acceptance record is merged
- **Date:** 2026-07-11

## Decision requested

Approve a deterministic, system-managed transitive-closure projection of submitted B3 structures. B4 makes hierarchy traversal scalable and verifiable while preserving `Talisma Unit Placement` as the sole authoritative parentage record.

B4 does not activate a Structure Version, choose a current version, or grant access. Those remain separate architecture gates.

## Problem

B3 validates and freezes a forest, but answering ancestor and descendant questions directly from adjacency records requires repeated traversal. That is unsuitable for high-volume authorization, reporting, ownership, and integration queries. A derived closure projection provides bounded indexed lookups, but introduces generation consistency, recovery, concurrency, and stale-data risks that require explicit governance.

## Authorized records proposed

### Talisma Closure Build

System-managed record representing one materialization attempt.

| Field | Type | Required | Constraint and meaning |
|---|---|---:|---|
| `name` | System name | Yes | Server-generated UUIDv4; immutable |
| `structure_version` | Link: Talisma Structure Version | Yes | Submitted B3 version; immutable; at most one Ready build at a time |
| `institution` | Link: Talisma Institution | Yes | Derived from Structure Version; immutable |
| `status` | Select | Yes | Building, Ready, Failed, Superseded |
| `started_on` | Datetime | Yes | Server timestamp |
| `completed_on` | Datetime | Conditional | Required for Ready or Failed |
| `expected_unit_count` | Int | Yes | Placement count captured under lock |
| `closure_row_count` | Int | Conditional | Verified stored row count |
| `source_fingerprint` | Data | Yes | Deterministic SHA-256 of canonical placements |
| `failure_code` | Data | Conditional | Stable machine-readable failure classification |
| `failure_summary` | Small Text | Conditional | Sanitized operational explanation |

`source_fingerprint` is computed from sorted tuples of `(academic_unit, parent_unit-or-empty)` plus the Structure Version UUID and schema version. It is evidence of source equivalence, not a security signature.

### Talisma Unit Closure

System-managed projection row.

| Field | Type | Required | Constraint and meaning |
|---|---|---:|---|
| `name` | System name | Yes | Server-generated UUIDv4; not a business identifier |
| `closure_build` | Link: Talisma Closure Build | Yes | Generation boundary; immutable |
| `structure_version` | Link: Talisma Structure Version | Yes | Denormalized and validated; immutable |
| `institution` | Link: Talisma Institution | Yes | Denormalized and validated; immutable |
| `ancestor_unit` | Link: Talisma Academic Unit | Yes | Includes self; immutable |
| `descendant_unit` | Link: Talisma Academic Unit | Yes | Includes self; immutable |
| `depth` | Int | Yes | Zero for self; positive for descendants; immutable |

Database uniqueness is `(closure_build, ancestor_unit, descendant_unit)`. Composite indexes must support:

- descendants by `(closure_build, ancestor_unit, depth, descendant_unit)`;
- ancestors by `(closure_build, descendant_unit, depth, ancestor_unit)`;
- version integrity by `(structure_version, closure_build)`;
- Institution cleanup and audit by `(institution, closure_build)`.

Users receive no create, write, delete, import, rename, or submit permission on either record. System Manager may read operational metadata but cannot mutate projections through ordinary document operations.

## Build lifecycle

1. Accept only a submitted B3 Structure Version.
2. Acquire a bounded MariaDB advisory lock scoped to the Structure Version.
3. Lock the Structure Version row and verify it remains submitted.
4. Re-run B3 graph validation from authoritative Placements.
5. Capture placement count and canonical source fingerprint.
6. Create a `Building` build record and generate closure rows in deterministic batches.
7. Verify all integrity conditions before exposing the generation.
8. In one transaction, set row count, completion time, and `Ready` status.
9. Release the advisory lock after the database transaction has established the final state.

Only an explicit app-owned service may create or change build and closure records. Document controllers reject direct creation, mutation, deletion, import, rename, and cancellation.

The first implementation may run synchronously for the accepted 10,000-placement ceiling. Background jobs, progress UI, retry scheduling, and automatic build-on-submit require separate approval because B3 submission currently has no materialization side effect.

## Closure semantics

- Every placed Unit has exactly one self row at depth zero.
- Each strict ancestor has exactly one row for each descendant with the unique forest path depth.
- Roots have no strict ancestors but retain self rows.
- Multiple roots remain valid.
- Depth cannot exceed B3's accepted maximum of 32.
- Closure rows never create parentage and never override Placements.
- Queries must select one Ready `closure_build`; mixing generations is forbidden.
- A consumer cannot infer that Ready means Active or current.

For a version with `n` Units, expected closure rows equal the sum of `(node depth + 1)`. Verification independently computes this value from the validated forest and compares it with inserted and persisted counts.

## Integrity gate

A build becomes Ready only when all checks pass:

1. Structure Version is submitted and matches the build Institution.
2. Placement count equals `expected_unit_count` and is at least one.
3. Source fingerprint is unchanged after generation.
4. Exactly one self row exists per Placement with depth zero.
5. No non-self row has depth zero; no row has negative depth.
6. Every ancestor and descendant is placed in the same Structure Version and Institution.
7. Stored uniqueness and row count match the independently computed closure.
8. The deepest stored path does not exceed 32.
9. No closure rows exist outside the build being finalized.

Any failure leaves the build non-Ready. A failure records a stable code and sanitized summary; it must not expose SQL, credentials, or personal data.

## Idempotency, concurrency, and rebuild

- Repeating a build request for a Ready version with the same fingerprint returns that Ready build without writing duplicate rows.
- Two competing build requests for one version serialize; at most one becomes Ready.
- A changed fingerprint is a hard integrity failure because submitted B3 Placements are immutable.
- Rebuild is an explicit recovery operation that creates a new build UUID and compares it with the prior generation.
- A replacement generation may become Ready only after complete verification; the prior Ready generation is then marked Superseded in the same transaction.
- Failed builds and their rows are retained for a configurable diagnostic period. Retention automation is deferred; initial cleanup is an explicit recovery command with audit evidence.
- Deleting a submitted Structure, Ready build, or closure generation through ordinary document operations is prohibited.

## Failure recovery

| Failure | Required outcome |
|---|---|
| Lock timeout | Controlled retryable failure; no build created or changed |
| Graph validation failure | Failed build with validation code; no Ready projection |
| Interrupted row generation | Building/Failed generation remains unconsumable |
| Count or fingerprint mismatch | Failed build; retain evidence; no partial exposure |
| Duplicate-key race | Roll back competing transaction and return existing Ready build when equivalent |
| Cache loss | Database Ready build remains authoritative; cache reconstruction is separately gated |
| Restore from backup | Re-run integrity verification before consumers may use restored Ready builds |

No recovery path edits submitted Placements or patches individual closure rows. Recovery rebuilds the complete projection.

## Query contract

B4 may expose internal Python domain-service methods for tests and later consumers:

- `get_ready_build(structure_version)`
- `get_descendants(build, ancestor_unit, include_self=True)`
- `get_ancestors(build, descendant_unit, include_self=True)`
- `verify_build(build)`

These are not whitelisted APIs. Each method verifies Ready status, Structure Version, and Institution consistency, uses indexed set queries, and fails closed for missing, Building, Failed, or Superseded builds.

## Performance and volume targets

The reference environment must document CPU, memory, MariaDB version, storage, container limits, and dataset shape.

| Dataset | Required target |
|---|---:|
| 1,000 Placements, representative mixed forest | Build and verify under 5 seconds |
| 10,000 Placements, maximum depth 32 | Build and verify under 30 seconds |
| 10,000 direct children of one root | Descendant query under 250 ms, warm database |
| One depth-32 ancestor chain | Ancestor query under 100 ms, warm database |

Query plans must use the accepted composite indexes and show no per-result recursive traversal or N+1 reads. Storage evidence must report closure row count and bytes for deep, wide, and representative forests.

## Permissions and security

- Existing Institution Manager, Viewer, and Academic Structure Approver roles receive no mutation rights on closure records.
- Institution Viewer may receive read access only after Scope Grant or another row-level institutional filter is approved; B4 grants no site-wide closure-row access.
- System Manager receives operational read only and no business authorization from B4.
- Internal service calls enforce explicit Structure Version and Institution boundaries.
- Raw closure records are not exposed through guest, portal, report, export, or REST endpoints in B4.
- Build failures and logs contain UUIDs, counts, stable codes, and correlation identifiers only.

## Verification plan

Implementation approval requires automated evidence for:

1. UUID naming, disabled rename/import/quick entry, and system-managed mutation denial.
2. Exact metadata fields and explicit absence of activation, pointer, cache, grant, mapping, and ownership fields.
3. Self rows, direct children, deep chains, wide forests, and multiple roots.
4. Expected row-count formula and independent set comparison.
5. Source fingerprint determinism regardless of Placement query order.
6. Rejection of Draft/cancelled/missing Structure Versions.
7. Cross-Institution and missing-Placement corruption detection.
8. Database uniqueness and composite-index existence.
9. Interrupted and failed builds remaining unconsumable.
10. Idempotent repeat request and explicit full rebuild behavior.
11. Two concurrent build attempts producing one Ready generation.
12. Ready-generation replacement and atomic supersession.
13. Query contract rejection of non-Ready or mismatched builds.
14. Depth-32 boundary and representative 1,000/10,000-node performance.
15. Repeated `bench migrate`, isolated install/uninstall dependency behavior, and backup/restore integrity verification.
16. Full existing `talisma_sis` regression suite.

## Migration strategy

- Add the two DocTypes and app-owned MariaDB constraints/indexes through idempotent post-model-sync patches.
- Do not automatically materialize existing submitted B3 structures during migrate.
- Provide a dry-run inventory of submitted versions requiring builds.
- Materialization of existing data is a separately invoked, resumable operational step after backup.
- Repeated migration must not create builds or closure rows.

## Explicit exclusions

B4 does not authorize:

- an active/current Structure Version pointer or activation workflow;
- scheduled activation, automatic materialization on B3 submit, background queues, or retry jobs;
- Scope Grant, permission-query hooks, User scope, descendant authorization, or role changes;
- cache records, Redis keys, cache invalidation hooks, or cache warming;
- Program/Course ownership, Standard Mapping, Education adapters, or standard-record custom fields;
- hierarchy comparison UI, reports, workspaces, pages, portals, public/REST APIs, exports, or fixtures;
- Unit lineage, merge/split automation, responsibility assignments, or reorganization workflows;
- source-data migration, seed data, Docker/Compose changes, or Frappe/ERPNext core modifications.

## Approval gate

The project owner approved this architecture on 2026-07-11. No DocType, patch, role, hook, service, command, job, test fixture, or runtime behavior may be implemented until the [B4 acceptance record](INSTITUTIONAL_SCHEMA_SLICE_B4_CLOSURE_ACCEPTANCE.md) is reviewed and merged into `develop`.

Approval should explicitly confirm:

- the two-record Build plus Closure design;
- synchronous initial operation and no automatic build on B3 submission;
- immutable generation replacement and retention approach;
- numeric performance targets;
- internal query contract and no authorization use;
- activation and Scope Grant remaining separately gated.

## References

- [ADR-003 Institutional Hierarchy](ADR-003-INSTITUTIONAL-HIERARCHY.md)
- [B3 Structure Acceptance](INSTITUTIONAL_SCHEMA_SLICE_B3_STRUCTURE_ACCEPTANCE.md)
- [B3 Valid-To Amendment](INSTITUTIONAL_SCHEMA_SLICE_B3_VALID_TO_AMENDMENT.md)
- [Institutional Physical Schema](INSTITUTIONAL_PHYSICAL_SCHEMA_PROPOSAL.md)
- [Institutional Operations and Security](INSTITUTIONAL_SCHEMA_OPERATIONS_AND_SECURITY.md)
- [Institutional Schema Review Gate](INSTITUTIONAL_SCHEMA_REVIEW_GATE.md)
- [B4 Closure Acceptance Record](INSTITUTIONAL_SCHEMA_SLICE_B4_CLOSURE_ACCEPTANCE.md)
