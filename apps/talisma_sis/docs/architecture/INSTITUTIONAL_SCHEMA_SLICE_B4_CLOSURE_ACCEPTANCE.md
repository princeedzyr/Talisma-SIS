# Institutional Schema Slice B4: Unit Closure Materialization Acceptance Record

- **Architecture:** Accepted ADR-003 Institutional Hierarchy
- **Proposal:** [Slice B4 Unit Closure Materialization Proposal](INSTITUTIONAL_SCHEMA_SLICE_B4_CLOSURE_PROPOSAL.md)
- **Outcome:** Accepted for implementation within the exact authorized scope
- **Approval date:** 2026-07-11
- **Approver:** Prince Ebinezer, Project Owner
- **Recorded by:** Talisma SIS architecture process

## Accepted decision

The project owner approves a deterministic, system-managed transitive-closure projection of submitted B3 Structure Versions.

`Talisma Unit Placement` remains the sole authoritative parentage record. Closure records are derived, rebuildable query projections and must never be treated as active hierarchy selection, ownership, authorization, or historical source data.

## Authorized implementation scope

Two new standard DocTypes in the `talisma_sis` app and `Talisma SIS` module:

1. `Talisma Closure Build`
2. `Talisma Unit Closure`

Both use server-generated UUIDv4 names, disable rename, quick entry and import, enable change tracking where operationally meaningful, and create no fixtures or seed data. Neither is user-submittable. Controllers deny ordinary direct creation, mutation, and deletion; records are managed only through an app-owned internal domain service.

### Authorized Closure Build fields

| Field | Type | Required | Accepted constraint |
|---|---|---:|---|
| `structure_version` | Link: Talisma Structure Version | Yes | Submitted B3 version; immutable; at most one Ready build at a time |
| `institution` | Link: Talisma Institution | Yes | Derived from Structure Version; immutable |
| `status` | Select | Yes | Building, Ready, Failed, Superseded |
| `started_on` | Datetime | Yes | Server-generated timestamp |
| `completed_on` | Datetime | Conditional | Required for Ready and Failed |
| `expected_unit_count` | Int | Yes | Placement count captured under lock |
| `closure_row_count` | Int | Conditional | Verified persisted row count |
| `source_fingerprint` | Data | Yes | Deterministic SHA-256 of canonical placements and schema context |
| `failure_code` | Data | Conditional | Stable sanitized machine classification |
| `failure_summary` | Small Text | Conditional | Sanitized operational explanation |

### Authorized Unit Closure fields

| Field | Type | Required | Accepted constraint |
|---|---|---:|---|
| `closure_build` | Link: Talisma Closure Build | Yes | Immutable generation boundary |
| `structure_version` | Link: Talisma Structure Version | Yes | Derived and immutable |
| `institution` | Link: Talisma Institution | Yes | Derived and immutable |
| `ancestor_unit` | Link: Talisma Academic Unit | Yes | Includes self; immutable |
| `descendant_unit` | Link: Talisma Academic Unit | Yes | Includes self; immutable |
| `depth` | Int | Yes | Zero for self and positive below; immutable |

No other fields are authorized.

## Accepted closure semantics

1. Every placed Unit has exactly one self row at depth zero.
2. Every strict ancestor-descendant relationship has exactly one row with the unique forest-path depth.
3. Roots retain self rows and have no strict ancestors.
4. Multiple roots remain valid.
5. Maximum depth remains B3's accepted limit of 32 edges.
6. Expected closure count is the sum of `(node depth + 1)` across all placed Units.
7. Closure rows cannot create, repair, or override parentage.
8. Consumers must address exactly one Ready build; generations cannot be mixed.
9. Ready means materially verified only. It does not mean Active, current, authorized, or approved for consumer use.

## Accepted build lifecycle

The internal service must:

1. accept only a submitted B3 Structure Version;
2. acquire a bounded MariaDB advisory lock scoped to that version;
3. lock and revalidate the submitted Structure row;
4. load authoritative Placements and re-run B3 forest validation;
5. capture count and deterministic fingerprint;
6. create a Building generation and produce closure rows deterministically;
7. verify fingerprint, row counts, self rows, paths, scope, uniqueness and depth;
8. transition to Ready only in a transaction that establishes complete verified state;
9. leave failed or interrupted generations unconsumable;
10. release advisory locking only after final database state is established.

The first implementation is synchronous. B3 submission must remain side-effect free. Automatic materialization, queues, retries, progress UI and scheduled work are not authorized.

## Accepted database and query strategy

- Unique `(closure_build, ancestor_unit, descendant_unit)`.
- Descendant index `(closure_build, ancestor_unit, depth, descendant_unit)`.
- Ancestor index `(closure_build, descendant_unit, depth, ancestor_unit)`.
- Version/build and Institution/build integrity indexes.
- At most one Ready build per Structure Version, enforced transactionally inside the version-scoped lock with reviewed database support where feasible.
- Deterministic batch generation with no per-result recursive traversal.

The following internal Python domain-service contract is authorized:

- `get_ready_build(structure_version)`
- `get_descendants(build, ancestor_unit, include_self=True)`
- `get_ancestors(build, descendant_unit, include_self=True)`
- `verify_build(build)`

These methods are not whitelisted APIs. They must verify Ready state and Institution/version consistency and fail closed for missing, Building, Failed, Superseded or mismatched generations.

## Accepted idempotency and recovery

- An equivalent repeated build request returns the existing Ready generation without duplicate writes.
- Concurrent requests serialize and produce at most one Ready generation.
- Fingerprint change for submitted Placements is an integrity failure.
- Explicit rebuild creates a new complete generation; it never patches individual rows.
- Replacement Ready and prior-generation Superseded transitions occur atomically.
- Failed and interrupted builds remain unavailable for queries and retain sanitized diagnostic evidence.
- Retention automation is deferred; cleanup is an explicit controlled recovery operation.
- Backup restoration requires integrity verification before any Ready generation is consumed.

## Authorized permissions

- Institution Manager, Institution Viewer, and Academic Structure Approver receive no mutation rights.
- Institution Viewer receives no closure-row read authorization in B4 because row-level institutional scope is not yet approved.
- System Manager may receive operational read access only and gains no business authorization.
- Guest, portal, ordinary REST, report and export exposure are prohibited.
- Only the app-owned service may manage builds and rows.

## Accepted performance targets

The implementation must record its reference environment and meet:

- 1,000 representative Placements: build and verification under 5 seconds;
- 10,000 Placements at depth up to 32: build and verification under 30 seconds;
- 10,000 direct children: warm descendant query under 250 milliseconds;
- depth-32 chain: warm ancestor query under 100 milliseconds.

Query-plan evidence must demonstrate composite-index use and no N+1 or per-result recursive traversal. Evidence must include row count and storage size for representative deep and wide forests.

## Verification required for implementation acceptance

Implementation must automate all sixteen test groups in the proposal, including:

- exact metadata and mutation denial;
- self, direct, deep, wide and multi-root closure correctness;
- independent row-count and set comparison;
- deterministic fingerprinting;
- rejected Draft, missing or inconsistent sources;
- uniqueness and composite-index verification;
- interrupted/failed build isolation;
- idempotent repeat and explicit rebuild;
- competing build serialization;
- atomic generation supersession;
- query fail-closed behavior;
- numeric performance evidence;
- repeated migration, isolated dependency behavior, backup/restore verification and the full regression suite.

## Explicit exclusions

This acceptance does not authorize:

- active/current Structure pointers, activation, retirement or scheduled transitions;
- automatic build on B3 submission, background queues, retry jobs or progress UI;
- Redis or database caching layers, invalidation hooks or cache warming;
- Scope Grant, permission query hooks, descendant authorization, user scope or new roles;
- Standard Mapping, Academic Ownership, Programs, Courses or Education adapters;
- whitelisted/public/REST APIs, pages, portals, workspaces, reports or exports;
- fixtures, seed structures, automatic migration of existing submitted versions, or standard-record custom fields;
- lineage, merge/split, responsibility assignment or reorganization automation;
- Docker/Compose changes or Frappe/ERPNext core modifications.

## Migration and change control

Implementation may begin only after this acceptance record is reviewed and merged into `develop`. It must occur on a new feature branch and match this record exactly.

Migrations may add the two DocTypes and idempotent app-owned constraints/indexes, but must not create Build or Closure data. Existing submitted versions may be inventoried in dry-run form; materialization is a separately invoked resumable operation after backup.

Any additional field, status, role, DocType, hook behavior, automatic job, API, cache, activation behavior, migration side effect or consumer permission requires renewed architecture approval.

## Future gates

The next dependent gate is active-version selection and atomic activation. Scope Grant remains independently gated and cannot consume B4 projections until activation/current-version ownership and row-level authorization contracts are accepted.
