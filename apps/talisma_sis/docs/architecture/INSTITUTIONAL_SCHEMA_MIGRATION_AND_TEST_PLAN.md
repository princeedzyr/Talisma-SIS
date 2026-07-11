# Institutional Schema Migration and Test Plan

Status: **Proposed for physical-schema approval**

## Source inventory

Inventory ERPNext Company, Department, Branch, Cost Center, Employee organizational links and any custom organization fields. If Education is later approved, separately inventory Program, Course and Instructor Department links. Record source keys, codes, parentage, Company, disabled state, duplicates, orphan nodes and effective-date evidence.

## Source-to-target mapping

| Source | Candidate target | Rule |
|---|---|---|
| Approved institutional register | Talisma Institution | Authoritative code required; never infer from Company name alone |
| Company | Standard Mapping | Legal/accounting purpose; does not create an Institution automatically |
| Approved campus register | Talisma Campus | Campus code and Institution required |
| Branch | Optional Standard Mapping | Map only after governance confirms equivalence |
| Department | Academic Unit and/or Standard Mapping | Names alone insufficient; HR and academic meanings reviewed separately |
| Cost Center | Standard Mapping | Finance-owned purpose and interval |
| Program/Course Department | Academic Ownership candidate | Education-only; reviewed effective owner, not automatic history |
| Instructor Department | Faculty assignment candidate | Not part of first schema slice |

## Migration stages

1. Profile sources read-only and publish exception counts.
2. Approve Institution codes and initial site topology.
3. Create Institutions and reconcile explicit Company mappings.
4. Create Campuses and Academic Units from governed registers.
5. Create a Draft initial Structure Version and placements.
6. Validate cycles, orphans, code collisions and effective dates.
7. Reconcile Department and Cost Center mappings with HR/Finance.
8. Submit/materialize the initial structure in an isolated rehearsal.
9. Run permission, historical, performance and recovery tests.
10. Cut over with backup, change control, idempotent ledger and domain sign-off.

## Idempotency ledger

Every migrated item records source system, source DocType, source key, extraction version, target DocType/name, mapping purpose, rule version, batch ID, outcome and error. Re-running a completed item returns the same result and cannot create duplicate codes, placements or mappings.

## Reconciliation

- Every approved Institution/Campus/Unit source maps once or has a documented exception.
- Every Unit appears once in the initial Structure Version.
- Closure self-row count equals placement/unit count as defined.
- Every closure path belongs to one Institution/build.
- Required Company/Department/Cost Center mappings are complete by purpose.
- No unauthorized cross-Institution access exists.
- Existing accounting, HR and Education behavior is unchanged.
- Historical source reports reconcile to documented mapping assumptions.

## Required test scenarios

1. Single-campus institution with departments directly at root.
2. Multi-campus institution with one Unit operating on multiple campuses.
3. Two Institutions sharing one Company but isolated permissions.
4. One Institution mapped to multiple Companies.
5. Department tree differs from academic structure.
6. Academic Unit mapped to different Cost Centers by purpose/time.
7. Structure cycle and cross-Institution parent rejected.
8. Concurrent submissions for overlapping intervals; one must fail.
9. Closure build fails and prior version remains active.
10. Unit moves parent in successor version without historical rewrite.
11. Merge/split represented through successor design without code reuse.
12. Permission descendant set expands and requires approval.
13. As-of report returns former structure.
14. Migration batch replay creates no duplicates.
15. Education absent and all base hierarchy functions install/migrate.

## Test layers

| Layer | Coverage |
|---|---|
| Unit | Code normalization, intervals, allowlists, capability validation |
| DocType | Required fields, immutable codes, deletion/rename guards |
| Graph | Cycle prevention, one placement, closure correctness |
| Transaction | Concurrent codes, submissions, mappings and activation |
| Permission | Institution isolation, Unit descendants, shared services, denial paths |
| Integration | Company/Department/Branch/Cost Center mappings |
| Migration | Dry run, replay, exceptions, reconciliation and forward repair |
| Performance | Closure build, permission queries, historical reporting and cache |
| Recovery | Failed build, interrupted activation, backup/restore and cache rebuild |

## First-slice acceptance

Slice A may implement only Talisma Institution after approved schema, uniqueness, deletion and permission tests. It must install without Education, migrate idempotently, preserve ERPNext behavior, and provide a safe dependency target for later identity schema work.

Slices B and C require their own go/no-go reviews. No production hierarchy migration occurs in Slice A.

## Production blockers

- Schema review gate not approved.
- Numeric volume and latency targets absent.
- Composite constraint/concurrency strategy untested on supported MariaDB.
- Exact Frappe roles and permission hooks unapproved.
- Closure activation/recovery untested.
- Institution source register or code ownership unresolved.
- Required HR/Finance mapping owners unavailable.
- Backup/restore and forward-repair tests incomplete.
- Education-specific adapters enabled while ADR-001 remains Proposed.
