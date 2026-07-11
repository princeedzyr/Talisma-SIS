# ADR-003 Acceptance Record

- **Decision:** Institutional and Academic Organization Hierarchy
- **ADR:** [ADR-003](ADR-003-INSTITUTIONAL-HIERARCHY.md)
- **Outcome:** Accepted
- **Approval date:** 2026-07-11
- **Approver:** Prince Ebinezer, Project Owner
- **Recorded by:** Talisma SIS architecture process

## Approved baseline

The project owner approves the ADR-003 architecture and supporting package:

- `Talisma Institution` is the stable institutional policy, permission and data-partition root;
- `Talisma Institution` is the approved conceptual target for ADR-002 `institution_scope`;
- the domain supports multiple Institutions per site, while deployment policy may use separate sites for stronger isolation;
- ERPNext `Company` remains the legal/accounting authority and maps explicitly to Institution;
- `Talisma Campus` is separate from ERPNext Branch and from academic governance;
- `Talisma Academic Unit` is the stable identity for colleges, schools, faculties, departments, institutes and centers;
- academic parentage is represented through approved, effective Structure Versions and Unit Placements rather than destructive tree rewrites;
- ERPNext Department and Cost Center retain operational/HR and financial authority;
- Program and Course ownership is explicit, effective-dated and supports primary, joint and campus-context roles;
- reorganizations preserve unit codes, lineage, historical ownership and historical permission/reporting context;
- permissions use Institution as the top boundary and approved structure-version descendant scope;
- Education remains optional until ADR-001 is accepted.

## Conditions and exceptions

1. This decision approves conceptual architecture only; it does not authorize DocTypes, fields, permissions, APIs, migrations or runtime changes.
2. The identity schema may name `Talisma Institution` as its target, but cannot create a physical Link field until the institutional physical schema is approved and implemented in dependency order.
3. Exact multi-institution deployment topology remains an operational decision; shared-site deployment requires verified server-side isolation.
4. Institution-specific governance, legal-entity mapping, finance policy, reporting and retention require deployment-specific approval.
5. Current-hierarchy materialization, caching and permission-query performance must be designed and load-tested before implementation.
6. ADR-001 remains proposed; Education-specific mappings and ownership adapters remain disabled until accepted.

## Next design gate

Before implementation, approve exact physical schemas for Institution, Campus, Academic Unit, Structure Version, Unit Placement, standard mappings, ownership assignments and responsibility assignments, including:

- fields, naming, uniqueness and effective-date constraints;
- immutable version/activation workflows;
- cycle prevention and historical queries;
- permission-query and descendant-expansion strategy;
- hierarchy cache/materialization and invalidation;
- Company, Department, Branch and Cost Center mapping cardinalities;
- migration, reconciliation and reorganization events;
- MariaDB indexes and representative-scale performance tests.

## Change control

Material changes to the Institution boundary, Company ownership, Campus/Academic Unit separation, versioned hierarchy, permission scope or historical-reorganization model require a superseding ADR.
