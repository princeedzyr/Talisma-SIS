# Institutional Physical Schema Review Gate

Status: **Slice A, Campus Slice B1, and Academic Unit Slice B2 approved on 2026-07-11; later slices not approved**

This gate determines whether accepted ADR-003 is specified sufficiently for a minimal implementation. Merging the design documents does not authorize DocTypes.

## Review artifacts

- [ADR-003 Acceptance Record](ADR-003-ACCEPTANCE-RECORD.md)
- [Institutional Physical Schema Proposal](INSTITUTIONAL_PHYSICAL_SCHEMA_PROPOSAL.md)
- [Operations, Security and Performance](INSTITUTIONAL_SCHEMA_OPERATIONS_AND_SECURITY.md)
- [Migration and Test Plan](INSTITUTIONAL_SCHEMA_MIGRATION_AND_TEST_PLAN.md)
- [Standard DocType Fit-Gap](INSTITUTIONAL_STANDARD_DOCTYPE_FIT_GAP.md)

## Proposed implementation order

1. Slice A: Talisma Institution only.
2. Slice B1: Campus.
3. Slice B2: Academic Unit Type and Academic Unit stable masters.
4. Separately gated hierarchy slices: Structure Version, Placement, Closure, and Scope Grant.
5. Slice C: Standard Mapping and Academic Ownership.
6. Deferred: lineage, responsibility assignment, external identifiers, facilities and reorganization automation.

Each slice requires independent approval and verification. Schema approval does not approve all slices at once unless explicitly stated.

## Review checklist

- [x] UUID naming and immutable stable-code rules approved for Slice A.
- [x] Institution fields and lifecycle approved for Slice A, with policy-profile field deferred.
- [x] Campus fields, address behavior, and deferral of parent grouping approved in Slice B1.
- [x] Academic Unit Type capabilities approved in Slice B2.
- [x] Academic Unit fields and lifecycle approved in Slice B2.
- [ ] Structure Version submission/effective-date rules approved.
- [ ] Placement uniqueness and cycle prevention approved.
- [ ] Closure-table generation, integrity and recovery approved.
- [ ] Standard mapping target allowlist/cardinality approved.
- [ ] Academic ownership roles and primary-owner constraint approved.
- [ ] Scope Grant semantics and Frappe role interaction approved.
- [ ] Composite indexes and MariaDB concurrency strategy approved.
- [x] Minimal Institution Manager/Viewer enforcement approved for Slice A; hierarchy scope remains pending.
- [ ] Reorganization impact and scope-expansion review approved.
- [ ] Audit events and idempotency approved.
- [x] No-data-migration Slice A install/migrate/backup tests approved; later migration remains pending.
- [ ] Numeric performance/volume targets recorded.
- [x] Education remains optional and absent from Slice A metadata Links.
- [x] Slice A scope and exclusions approved in the [Slice A approval record](INSTITUTIONAL_SCHEMA_SLICE_A_APPROVAL.md).
- [x] Campus Slice B1 accepted through the [Campus proposal](INSTITUTIONAL_SCHEMA_SLICE_B1_CAMPUS_PROPOSAL.md) and [acceptance record](INSTITUTIONAL_SCHEMA_SLICE_B1_CAMPUS_ACCEPTANCE.md).
- [x] Slice B2 Academic Unit Type and Academic Unit accepted through the [B2 proposal](INSTITUTIONAL_SCHEMA_SLICE_B2_ACADEMIC_UNIT_PROPOSAL.md) and [acceptance record](INSTITUTIONAL_SCHEMA_SLICE_B2_ACADEMIC_UNIT_ACCEPTANCE.md).
- [ ] Slice B3 Structure Version and Unit Placement reviewed through the [B3 proposal](INSTITUTIONAL_SCHEMA_SLICE_B3_STRUCTURE_PROPOSAL.md).

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

The project owner approved Slice A, Campus Slice B1, and Academic Unit Slice B2 on 2026-07-11. Their exact authorizations are recorded in the [Slice A approval record](INSTITUTIONAL_SCHEMA_SLICE_A_APPROVAL.md), [Campus Slice B1 acceptance record](INSTITUTIONAL_SCHEMA_SLICE_B1_CAMPUS_ACCEPTANCE.md), and [Slice B2 acceptance record](INSTITUTIONAL_SCHEMA_SLICE_B2_ACADEMIC_UNIT_ACCEPTANCE.md). All unchecked items and all later slices remain design-only; Structure Version, Placement, Unit Closure, and Scope Grant remain separately gated.
