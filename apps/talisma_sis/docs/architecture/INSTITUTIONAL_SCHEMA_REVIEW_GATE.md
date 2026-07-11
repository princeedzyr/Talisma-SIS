# Institutional Physical Schema Review Gate

Status: **Ready for review; not approved**

This gate determines whether accepted ADR-003 is specified sufficiently for a minimal implementation. Merging the design documents does not authorize DocTypes.

## Review artifacts

- [ADR-003 Acceptance Record](ADR-003-ACCEPTANCE-RECORD.md)
- [Institutional Physical Schema Proposal](INSTITUTIONAL_PHYSICAL_SCHEMA_PROPOSAL.md)
- [Operations, Security and Performance](INSTITUTIONAL_SCHEMA_OPERATIONS_AND_SECURITY.md)
- [Migration and Test Plan](INSTITUTIONAL_SCHEMA_MIGRATION_AND_TEST_PLAN.md)
- [Standard DocType Fit-Gap](INSTITUTIONAL_STANDARD_DOCTYPE_FIT_GAP.md)

## Proposed implementation order

1. Slice A: Talisma Institution only.
2. Slice B: Campus, Unit Type, Academic Unit, Structure Version, Placement, Closure and Scope Grant.
3. Slice C: Standard Mapping and Academic Ownership.
4. Deferred: lineage, responsibility assignment, external identifiers, facilities and reorganization automation.

Each slice requires independent approval and verification. Schema approval does not approve all slices at once unless explicitly stated.

## Review checklist

- [ ] UUID naming and immutable stable-code rules approved.
- [ ] Institution fields and lifecycle approved.
- [ ] Campus fields, address and parent behavior approved.
- [ ] Academic Unit Type capabilities approved.
- [ ] Academic Unit fields and lifecycle approved.
- [ ] Structure Version submission/effective-date rules approved.
- [ ] Placement uniqueness and cycle prevention approved.
- [ ] Closure-table generation, integrity and recovery approved.
- [ ] Standard mapping target allowlist/cardinality approved.
- [ ] Academic ownership roles and primary-owner constraint approved.
- [ ] Scope Grant semantics and Frappe role interaction approved.
- [ ] Composite indexes and MariaDB concurrency strategy approved.
- [ ] Server-side permission enforcement points approved.
- [ ] Reorganization impact and scope-expansion review approved.
- [ ] Audit events and idempotency approved.
- [ ] Migration, reconciliation and recovery plan approved.
- [ ] Numeric performance/volume targets recorded.
- [ ] Education remains optional and absent from base metadata Links.
- [ ] Slice A scope and exclusions approved separately.

## Open decisions before approval

- Maximum Institutions, Units and hierarchy depth per site.
- Required numeric closure-build and permission-query targets.
- Whether Institution legal name belongs here or only through Company mappings.
- Exact policy-profile reference type.
- Whether Campus parent grouping is needed in Slice B.
- Which mapping purposes require exactly one Primary mapping.
- Whether Structure Version submission or a dedicated workflow best models approval under Frappe v16.
- Database constraint implementation and safe patch/uninstall behavior.
- Cache backend, active-version pointer and invalidation ownership.

## Required reviewers

Product architecture, institutional administration, registrar/academic governance, finance, HR, security/privacy, database engineering, operations, reporting/data governance and Frappe engineering.

## Approval outcome

Approval must identify the exact document revision and which slice is authorized. The recommended initial authorization is Slice A only. Slice A creates the stable Institution dependency without prematurely implementing hierarchy, mappings, ownership or migration.
