# Identity Schema Migration and Test Plan

Status: **Proposed for physical-schema approval**

This plan refines the accepted migration strategy for the proposed schema. It does not authorize production migration.

## Source-to-target mapping

| Source | Candidate target | Rule |
|---|---|---|
| Existing explicit cross-system mapping | Talisma Person and Role Link | Highest precedence after validation |
| `User` | Role Link (`User`) | Never create/link Person from email alone |
| `Employee` | Role Link (`Employee`) | Preserve employee number in HR; register identifier only under approved namespace |
| `Customer` individual | Role Link (`Customer`) | Organizations excluded; finance remains authoritative |
| `Contact` | Contact Association | Only after distinguishing person contact from organizational contact |
| `Address` | Contact Association | Preserve standard record; add governed purpose/interval |
| Education Applicant | Role Link (`Applicant`) | Optional and blocked by ADR-001; copied fields remain application snapshot |
| Education Student | Role Link (`Student`) | Optional and blocked by ADR-001; never match by unique email alone |
| Education Instructor | Role Link (`Instructor`) | Reconcile Employee link to the same Person |
| Education Guardian | Role Link plus Person Relationship | Access requires separate proxy authorization |

## Idempotency

Every migration input has source system, source DocType, source key, extraction version and batch ID. A migration ledger records target Person/link, rule version, outcome and error. Re-running a completed item returns the recorded result and creates no duplicate.

## Reconciliation

- Every in-scope source record maps to one target result or documented exception.
- Every non-replaced role target links to at most one Person.
- Every active identifier is unique inside its namespace.
- No new Person is created solely from weak evidence.
- Source academic, financial, HR and authentication behavior remains unchanged.
- Institution scope exists on every scoped identifier and role link.
- Permission-negative tests pass before consumer workflows are enabled.

## Synthetic scenarios

1. Applicant converts to Student and retains one Person.
2. Student is also Employee and Instructor.
3. Two twins share surname, DOB, address and guardian but remain distinct.
4. One person changes legal name and email without changing person key.
5. Shared household email does not cause a link.
6. Employee and Student have conflicting verified identifiers and enter review.
7. Individual Customer links to Person; organizational Customer does not.
8. Guardian relationship exists without portal authorization.
9. Proxy grant expires and access is denied immediately.
10. Directory-suppressed person is absent from search/export.
11. Cross-institution staff cannot discover another institution's person.
12. Duplicate migration batch is replayed without duplicate records.
13. Role target deletion is blocked while linked.
14. Merged person resolves to survivor without exposing restricted alias data.
15. Education is absent and the base identity module installs/migrates successfully.

## Test layers

| Layer | Required coverage |
|---|---|
| Unit | Normalization, lifecycle validation, allowlists, interval rules, masking |
| DocType | Required fields, state transitions, deletion guards, rename denial |
| Permission | Persona matrix, scope, purpose, restricted fields, negative cases |
| Transaction | Concurrent identifier issuance and role linking |
| Integration | User/Employee/Customer and optional Education adapters |
| Migration | Dry run, restart, replay, reconciliation, exception handling |
| Security | Enumeration, export leakage, audit, service accounts, restricted files |
| Performance | Identifier lookup, scoped search, list/report filtering, bulk reconciliation |
| Recovery | Backup/restore, encryption keys, interrupted migration, forward repair |

## First-slice acceptance

The first implementation slice is acceptable only when it installs without Education, migrates repeatedly with no changes after the first run, supports synthetic person/name/identifier/role records, enforces uniqueness under concurrency, prevents unauthorized cross-scope access, blocks unsafe deletion, produces required audit events and uninstalls/rolls back according to an approved test plan.

## Production blockers

- ADR-003 not accepted or institution target unresolved.
- Exact roles/permissions not approved.
- Identifier hashing/encryption key design not approved.
- Composite uniqueness not race-tested on supported MariaDB.
- Migration inventory or reconciliation incomplete.
- Legal/retention policies absent.
- Education-specific fields enabled while ADR-001 remains proposed.
- Backup/restore and forward-repair tests incomplete.
