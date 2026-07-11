# ADR-003 Approval Package

Status: **Ready for stakeholder review; not approved**

This package resolves the conceptual choices needed for ADR-003. It authorizes no DocTypes, fields, permissions, migrations or runtime changes.

## Recommended decisions

| Decision | Recommendation |
|---|---|
| Site topology | Domain supports multiple Institutions per site; deployment may still isolate institutions by site |
| Permission/policy root | New Talisma Institution |
| Identity `institution_scope` target | Talisma Institution |
| Legal/accounting entity | ERPNext Company remains authoritative and maps explicitly |
| Campus | New Talisma Campus; Branch is optional mapping only |
| Academic governance | Stable Talisma Academic Unit |
| Academic hierarchy | Versioned Structure and Unit Placement, not mutable Department tree history |
| Operational/HR hierarchy | ERPNext Department remains authoritative and maps explicitly |
| Financial responsibility | ERPNext Cost Center/accounting dimensions remain authoritative |
| Program/Course ownership | Effective-dated Talisma ownership assignment with Primary/Joint roles |
| Leadership/administration | Effective-dated responsibility assignment, not copied names |
| Reorganizations | New structure versions and lineage; no historical rewrite |
| Codes | Stable, scoped, non-recycled identifiers |
| Permissions | Institution boundary plus approved structure-version descendant scope |
| Education dependency | Optional adapter only while ADR-001 remains Proposed |

## Review artifacts

- [ADR-003](ADR-003-INSTITUTIONAL-HIERARCHY.md)
- [Standard DocType Fit-Gap](INSTITUTIONAL_STANDARD_DOCTYPE_FIT_GAP.md)
- [Institutional Hierarchy Model](INSTITUTIONAL_HIERARCHY_MODEL.md)
- [Governance and Validation](INSTITUTIONAL_HIERARCHY_GOVERNANCE.md)

## Approval checklist

- [ ] Multi-institution-per-site domain capability approved.
- [ ] Talisma Institution approved as permission and policy root.
- [ ] Talisma Institution approved as ADR-002 `institution_scope` target.
- [ ] Company retained exclusively for legal/accounting authority.
- [ ] Campus separated from Branch and Academic Unit.
- [ ] Academic Unit types and capabilities approved.
- [ ] Versioned Structure/Placement model approved.
- [ ] Department and Cost Center mapping boundaries approved.
- [ ] Program/Course ownership roles and effective dating approved.
- [ ] Joint and cross-campus ownership behavior approved.
- [ ] Reorganization, lineage and historical-query rules approved.
- [ ] Permission scope and reorganization-review behavior approved.
- [ ] Stable code and non-reuse policy approved.
- [ ] Migration and reconciliation strategy approved.
- [ ] Education remains optional until ADR-001 is accepted.
- [ ] Physical-schema design remains a separate gate.

## Required reviewers

Product architecture, institutional administration, registrar/academic governance, finance, HR, security/privacy, reporting/data governance, integration architecture and Frappe engineering.

## Conditions for ADR acceptance

ADR-003 may become Accepted when the applicable checklist is approved and exceptions are recorded. Acceptance unblocks the conceptual identity `institution_scope` target but does not authorize physical schema. Exact DocTypes, fields, indexes, permission queries, hierarchy cache/materialization and migration scripts require a later schema review.

## Next gate after acceptance

Prepare the institutional physical schema, including exact Institution/Campus/Unit/Structure/Placement/Mapping/Ownership fields; uniqueness and effective-date constraints; permission-query strategy; current-hierarchy cache; reorganization events; migration mapping; and performance tests.
