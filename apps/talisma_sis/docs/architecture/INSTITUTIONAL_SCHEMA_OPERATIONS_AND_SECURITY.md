# Institutional Schema Operations, Security and Performance

Status: **Proposed for physical-schema approval**

## Authorization model

| Proposed role | Institution | Campus/Unit | Structure | Mapping/Ownership | Scope grants |
|---|---|---|---|---|---|
| Institutional Viewer | Scoped read | Scoped read | Active/historical read | Scoped read | Own effective scope summary |
| Institutional Editor | No lifecycle close | Create/update draft | Draft preparation | Draft requests | None |
| Academic Structure Approver | Read | Read | Submit/supersede after checks | Academic ownership approval | Impact review |
| Finance Mapping Approver | Read | Read | Impact read | Company/Cost Center mapping approval | None |
| Scope Grant Approver | Read | Read | Active structures | Read | Approve/revoke grants |
| Institutional Administrator | Configuration only | Configuration | Operational recovery | Configuration | No implicit business scope |

Roles are proposed and do not authorize implementation. Institution scope is enforced server-side in list queries, link searches, reports, APIs, exports and background jobs. `System Manager` does not automatically receive cross-institution business access.

## Structure submission and activation

Submission performs one atomic validation gate:

1. Institution and purpose match all placements.
2. Every unit appears at most once.
3. All parents exist in the same version and Institution.
4. No self-parent or cycle exists.
5. Unit and version effective intervals are compatible.
6. No overlapping submitted version exists for the same Institution/purpose.
7. Required ownership, mapping and permission impact reports are complete.
8. Approval reference and authorized approver are present.

After submission, a background job builds a new closure generation. Consumers continue using the prior Ready version until the new generation passes integrity checks. Activation swaps the current-version pointer/cache atomically; failure leaves the prior version active.

## Closure materialization

Authoritative input is Unit Placement. Unit Closure is derived.

Build requirements:

- calculate self rows at depth zero and all ancestor paths;
- reject cycles before writing production generation;
- stage rows under a unique build ID;
- verify expected unit count, unique paths and institution consistency;
- transactionally mark the Structure Version Ready and expose its build ID;
- remove obsolete failed/staged generations under retention policy;
- support deterministic rebuild and comparison.

No request may mix closure rows from different build IDs. Cache keys include Institution, Structure Version and build ID.

## Permission-query strategy

- Institution-only grants filter directly by Institution.
- Unit grants resolve allowed descendants from the Ready closure generation.
- `include_descendants = 0` permits only the named Unit.
- Grants bind to an explicit Structure Version; following a successor version requires reviewed re-evaluation rather than silent expansion.
- Shared-service access uses separate grants per Institution.
- Deny when the required version/cache is unavailable or stale; never fail open.
- Permission evaluation returns stable scoped IDs, not names or prefixes.

High-volume DocTypes should store direct Institution and applicable ownership/scope references to avoid expensive runtime traversal. Denormalization is validated and updated only through domain services.

## Composite constraints

Required database-level strategies include:

- unique normalized Institution code;
- unique `(institution, normalized campus_code)`;
- unique `(institution, normalized unit_code)`;
- unique `(institution, purpose, normalized structure_code)`;
- unique `(structure_version, academic_unit)` placement;
- unique `(structure_version, ancestor_unit, descendant_unit)` closure row;
- effective singular primary mappings/owners where policy requires.

MariaDB cannot express every effective-dated conditional constraint through Frappe JSON. Use transaction locks, overlap queries and reviewed app-owned indexes/constraints. Concurrency tests must demonstrate that simultaneous submissions or mappings cannot violate invariants.

## Events

Publish versioned, idempotent events for Institution/Campus/Unit created, renamed, status changed; Structure submitted, materialized, activated, retired; mapping activated/ended; ownership changed; scope grant activated/revoked; and reconciliation failed/completed.

Events contain UUIDs, stable codes, Institution, effective time, version/build ID, actor, approval/correlation reference and schema version. They do not treat display names as identifiers.

## Reorganization safety

Before activation, calculate:

- units added, removed or moved;
- changed ancestor sets;
- permission grants whose descendant set changes;
- affected Programs/Courses and ownership gaps;
- impacted Department/Cost Center mappings;
- integrations requiring reconciliation;
- historical reports and scheduled extracts affected.

Any grant that gains descendants requires approval. Loss of scope is reported and applied at activation unless a governed transition window exists.

## Performance tests

Representative-scale tests must cover:

- 1, 10 and configured maximum Institutions per site;
- deep and wide academic structures;
- closure build time and storage growth;
- atomic activation under concurrent reads;
- permission-filtered list, report and link-search latency;
- Program/Course ownership as-of queries;
- hierarchy comparison and historical reporting;
- cache cold start, invalidation and rebuild;
- scope-grant evaluation for shared-service users;
- migration and reconciliation batches.

Query plans must show expected composite indexes and no per-row hierarchy traversal. Product owners must set numeric volume/latency targets before implementation approval.

## Failure and recovery

- Failed closure build leaves version non-Ready and prior version active.
- Interrupted activation is idempotently recoverable by build/version ID.
- Cache loss rebuilds from submitted placements and closure generation.
- Mapping/ownership reconciliation failures enter monitored queues.
- Backup/restore must preserve submitted structures, placements, closure generations, grants and audit records consistently.
- Disaster-recovery tests confirm the active-version pointer never references an incomplete build.

## Security test gate

- cross-Institution list/search/report/API denial;
- link-field filtering by Institution;
- generic role without Scope Grant denied;
- descendant and non-descendant Unit access;
- stale/missing closure fails closed;
- reorganization scope-expansion approval;
- technical administrator denial and controlled elevation;
- concurrent structure submission/activation;
- mapping target allowlist and Company consistency;
- export and background-service scope;
- audit attribution and event replay.
