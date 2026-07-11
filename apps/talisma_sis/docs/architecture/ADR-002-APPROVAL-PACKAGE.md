# ADR-002 Approval Package

Status: **Approved on 2026-07-11; implementation not authorized**

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

- [x] Canonical person and role-record boundary approved.
- [x] Standard `Contact`/`Address` reuse direction approved; field fit-gap remains an implementation gate.
- [x] Multi-institution scoping decision approved.
- [x] Identifier namespaces and issuance authority approved conceptually.
- [x] Matching tiers and prohibited automatic matches approved.
- [x] Merge, split, correction, and separation-of-duty rules approved.
- [x] Guardian/proxy authorization model approved conceptually.
- [x] FERPA/data classification and permission architecture approved, subject to institutional legal review.
- [x] Directory suppression and emergency-access architecture approved, with institution-specific policy pending.
- [x] Threat model and security gates approved.
- [x] Retention ownership and legal-hold architecture approved; exact schedule remains institution-specific.
- [x] Existing-data migration and reconciliation strategy approved.
- [x] ADR-001 dependency implications acknowledged.
- [x] Implementation remains independent of a mandatory Frappe Education dependency until ADR-001 legal and technical gates are accepted.
- [x] Material conditions and exceptions recorded in the acceptance record.

## Conditions for accepting ADR-002

These conditions were satisfied by project-owner approval on 2026-07-11 with the qualifications recorded in the [acceptance record](ADR-002-ACCEPTANCE-RECORD.md). Approval does not itself authorize implementation; a separate schema design review follows.

## Next gate after acceptance

1. Produce standard-DocType field fit-gap and physical schema proposal.
2. Define exact Frappe roles, permission queries, document checks, and audit events.
3. Define API/event contracts and idempotency behavior.
4. Create synthetic acceptance fixtures and negative permission tests.
5. Review performance, indexing, encryption, backup, and key management.
6. Approve a minimal implementation slice before creating DocTypes.

The recommended first slice is canonical person plus explicit links to existing roles, with no merge automation, proxy portal, bulk migration, or external write API until their controls are implemented and tested.
