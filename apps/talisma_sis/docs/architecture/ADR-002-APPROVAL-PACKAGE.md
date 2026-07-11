# ADR-002 Approval Package

Status: **Ready for stakeholder review; not approved**

This package converts the proposed identity architecture into reviewable decisions. It does not authorize DocTypes, fields, APIs, migrations, permissions, or production changes.

## Recommended decisions

| Decision | Recommendation | Rationale |
|---|---|---|
| Canonical identity | Use a narrow Talisma-owned natural-person concept | No standard record spans applicant, student, employee, instructor, guardian, customer, and user lifecycles safely |
| Role ownership | Keep standard role records authoritative | Preserves ERPNext/Education behavior and upgrade compatibility |
| Authentication | Keep `User`/IdP separate and optional | A person may exist without access; email is mutable |
| Contact/address | Reuse standard records with governed Talisma associations only where needed | Avoids duplication while supporting purpose, privacy, and history |
| Institution model | Support explicit institution scoping from the start | Prevents retrofitting tenancy into identifiers and permissions |
| Identifier policy | Opaque, namespaced, non-recycled identifiers | Prevents PII leakage and cross-institution collision |
| Matching | Automatic linking only on a unique trusted verified identifier | Reduces harmful false positives |
| Merge authority | Steward approval; dual approval for high-risk cases | Protects academic, financial, HR, and legal integrity |
| Relationships/access | Separate relationships from proxy authorization | Family or guardian status must not imply portal access |
| FERPA/privacy | Server-side, purpose- and scope-aware authorization with suppression | Role-only permission is insufficient |
| Retention | Configurable approved schedule with legal hold | Requirements vary by institution and jurisdiction |
| Migration | Inventory, dry-run, remediation, rehearsal, idempotent cutover | Existing records cannot be linked safely through weak bulk matching |
| Organizations | Defer common party abstraction | ERPNext parties cover current organization needs; natural-person identity is the immediate scope |

## Review artifacts

- [Identity and Party Model](IDENTITY_AND_PARTY_MODEL.md)
- [Conceptual Data Dictionary](IDENTITY_DATA_DICTIONARY.md)
- [Authorization and FERPA Matrix](IDENTITY_AUTHORIZATION_MATRIX.md)
- [Lifecycle and Resolution Rules](IDENTITY_LIFECYCLE_AND_RESOLUTION.md)
- [Threat Model](IDENTITY_THREAT_MODEL.md)
- [Retention and Migration Strategy](IDENTITY_RETENTION_AND_MIGRATION.md)

## Approval roles

| Reviewer | Required determination |
|---|---|
| Product architecture | Boundaries, reuse strategy, multi-institution scalability |
| Registrar/records owner | Student identity, numbering, lifecycle, merge authority, record integrity |
| Admissions | Applicant resolution and conversion workflow |
| HR/faculty administration | Employee/instructor ownership and cross-role behavior |
| Finance | Customer/billing associations and merge constraints |
| Privacy/legal | FERPA, consent, proxy authority, data minimization, retention |
| Security | Threat model, restricted data, audit, privileged operations |
| Integration architecture | External identifiers, events, reconciliation, idempotency |
| Engineering | Frappe feasibility, performance, migration, testing, operability |

## Acceptance checklist

- [ ] Canonical person and role-record boundary approved.
- [ ] Standard `Contact`/`Address` fit-gap approved.
- [ ] Multi-institution scoping decision approved.
- [ ] Identifier namespaces and issuance authority approved.
- [ ] Matching tiers and prohibited automatic matches approved.
- [ ] Merge, split, correction, and separation-of-duty rules approved.
- [ ] Guardian/proxy authorization model approved.
- [ ] FERPA/data classification and permission matrix approved.
- [ ] Directory suppression and emergency-access rules approved.
- [ ] Threat model and security gates approved.
- [ ] Retention schedule ownership and legal-hold workflow approved.
- [ ] Existing-data migration and reconciliation strategy approved.
- [ ] ADR-001 dependency implications acknowledged.
- [ ] Legal review of Frappe Education dependency completed or implementation explicitly remains independent of it.
- [ ] All material objections and exceptions recorded.

## Conditions for accepting ADR-002

ADR-002 may move from `Proposed` to `Accepted` only when named owners approve every applicable checklist item, unresolved items are either blockers or explicitly documented exceptions, and the acceptance commit records approval date and decision owners. Approval does not itself authorize implementation; a separate schema design review follows.

## Next gate after acceptance

1. Produce standard-DocType field fit-gap and physical schema proposal.
2. Define exact Frappe roles, permission queries, document checks, and audit events.
3. Define API/event contracts and idempotency behavior.
4. Create synthetic acceptance fixtures and negative permission tests.
5. Review performance, indexing, encryption, backup, and key management.
6. Approve a minimal implementation slice before creating DocTypes.

The recommended first slice is canonical person plus explicit links to existing roles, with no merge automation, proxy portal, bulk migration, or external write API until their controls are implemented and tested.
