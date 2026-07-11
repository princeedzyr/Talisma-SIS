# Institutional Hierarchy Governance and Validation

Status: **Proposed for ADR-003 approval**

## Governance ownership

| Concern | Owner |
|---|---|
| Institution identity and policy boundary | Institutional administration with security/privacy approval |
| Legal entity and accounting books | ERPNext Company / Finance |
| Campus identity and location | Institutional administration/facilities |
| Academic Unit identity and structure versions | Academic governance/registrar |
| Department mapping | HR/operations plus academic governance |
| Cost Center mapping | Finance |
| Program/Course ownership | Academic governance/registrar |
| Permission-scope grants | Data owner plus security administration |
| External organization codes | Integration governance |

No single administrator may activate a structure version and approve all resulting high-risk permission or finance changes without separation-of-duty review.

## Structure lifecycle

| State | Allowed actions | Transition authority |
|---|---|---|
| Draft | Add/remove placements, validate scenarios | Academic structure editor |
| Approved | Immutable pending activation; run impact reports | Academic governance approver |
| Active | Used for current hierarchy and descendant scope | Scheduled/authorized activation |
| Retired | Historical queries only | Automatic after supersession or governance action |
| Superseded | Corrected by named successor | Governance approver |

Activation requires no cycles, one placement per unit, valid effective dates, institution consistency, complete required mappings, permission impact review and approval evidence.

## Reorganization workflow

1. Clone or create the proposed structure version.
2. Apply placements and unit lifecycle/lineage changes.
3. Produce differences from the current version.
4. Identify affected programs, courses, faculty assignments, permission grants, integrations, reports and financial mappings.
5. Resolve required ownership/mapping changes with their domain owners.
6. Run synthetic and production-like read-only validation.
7. Obtain academic, security and relevant finance/HR approvals.
8. Schedule activation and publish versioned events.
9. Reconcile consumers and review permission expansion.
10. Retain the former version for historical reporting.

## Permission rules

- Every scoped record links directly or derivably to one Institution.
- A user receives no Institution access merely because they have a generic role.
- Academic Unit descendant grants bind to an active structure version or a defined policy for following future versions.
- Reorganization never silently expands access; grants with changed descendant sets enter review.
- Shared-service users require explicit grants for each Institution.
- Company, Department and Cost Center permissions do not automatically grant Talisma academic access, or vice versa.
- Reports, APIs, search and background jobs apply the same scope policy server-side.
- Emergency access is time-bound, justified, audited and reviewed.

## Finance mapping rules

- Required accounting operations fail closed when no valid Company/Cost Center mapping exists.
- Academic placement does not infer Company or Cost Center.
- A mapping declares purpose, because payroll, student billing, procurement and budget responsibility may differ.
- Effective intervals cannot overlap for mappings required to be singular.
- Historical postings retain original ERPNext dimensions; reorganizations do not rewrite ledger entries.
- Cross-company academic ownership requires explicit allocation/posting policy outside the hierarchy master.

## Migration approach

### Inventory

Profile Company, Department, Branch, Cost Center, Education Department links, Program, Course, Instructor, Employee and existing custom organization fields. Record codes, parents, company scope, duplicates, inactive nodes, inconsistent names and orphan mappings.

### Mapping precedence

1. Approved institutional code or explicit mapping.
2. Reviewed exact source identifier in a defined namespace.
3. Authorized governance decision.
4. Otherwise create an exception; never infer equivalence from name alone.

### Initial structure

Build Institution and Campus roots first, then stable Academic Units, then an initial Structure Version and placements. Import mappings separately with finance/HR ownership. Program/Course ownership assignments are rehearsed and reconciled before enabling Talisma reporting or permissions.

### Idempotency

Migration ledger keys include source system, DocType, record key, extraction version and mapping purpose. Re-running a completed batch cannot create duplicate institutions, units, placements or mappings.

## Required scenarios

1. Single-campus college with departments directly under Institution governance.
2. Multi-campus university with one academic unit operating at several campuses.
3. Federated group with two Institutions and one shared-service Company.
4. College renamed without changing code or historical identity.
5. Department transferred between colleges in a new structure version.
6. Two departments merged into a successor unit.
7. One unit split into two successors.
8. Jointly owned Program with one Primary and one Joint owner.
9. Course delivered at another Campus without changing academic owner.
10. Department mapping differs from Cost Center mapping.
11. Permission descendant set changes during reorganization and requires review.
12. Historical report reproduces the former structure as of a prior date.
13. Education app absent while Institution scope remains functional.
14. Cross-institution access denied for ordinary staff.

## Acceptance tests

- Cycle and cross-institution placements are rejected.
- Approved/active structure versions cannot be edited.
- Overlapping active structure versions are rejected for the same purpose.
- Stable codes cannot be reused.
- Effective-date gaps/overlaps are reported where policy requires continuity.
- Invalid or missing finance mappings fail clearly.
- Joint ownership does not duplicate Program/Course.
- Permission queries use institution and selected structure, not string names.
- Migration replay is idempotent.
- Historical queries return the correct structure and ownership.
- Education-specific adapters remain disabled when Education is absent.

## Operational monitoring

Monitor unmapped units, expired mappings, upcoming structure activation, permission-scope changes, cross-institution denial events, orphan ownership, invalid effective intervals, reconciliation failures and historical-report exceptions.
