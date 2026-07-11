# ADR-002 Acceptance Record

- **Decision:** Identity and Party Model
- **ADR:** [ADR-002](ADR-002-IDENTITY-AND-PARTY-MODEL.md)
- **Outcome:** Accepted
- **Approval date:** 2026-07-11
- **Approver:** Prince Ebinezer, Project Owner
- **Recorded by:** Talisma SIS architecture process

## Approved baseline

The project owner approves the ADR-002 architecture and its supporting package:

- a narrow Talisma-owned canonical natural-person identity;
- standard ERPNext and Education records remain authoritative for their role-specific domains;
- authentication remains separate and optional;
- person and role identifiers are opaque, namespaced, non-recycled, and institution-scoped;
- automatic linking requires an unambiguous trusted verified identifier;
- ambiguous matches, merges, splits, and sensitive corrections use governed human review;
- relationships do not grant access; proxy authority is explicit, scoped, effective-dated, and revocable;
- FERPA and privacy authorization is enforced server-side using role, institution, relationship, purpose, data class, and disclosure restriction;
- retention is driven by an institution-approved schedule and legal-hold process;
- migration uses inventory, dry runs, manual remediation, rehearsal, idempotent execution, and reconciliation.

## Conditions and exceptions

1. This acceptance approves architecture only. It does not authorize DocTypes, fields, permissions, APIs, migrations, or production changes.
2. Physical schema requires a standard-DocType field fit-gap and separate design approval.
3. Institution-specific legal, FERPA, retention, proxy, directory-information, and emergency-access policies require qualified institutional review before deployment.
4. [ADR-001](ADR-001-FRAPPE-EDUCATION-DEPENDENCY.md) remains proposed. ADR-002 implementation must remain independent of a mandatory Frappe Education dependency until ADR-001 and its licensing/legal gates are accepted.
5. Government identifiers are not collected by default. Any collection requires an approved purpose, legal basis, protection design, and retention period.
6. Multi-institution support is an architectural requirement; exact tenancy and row-level permission design belongs to the schema/authorization gate.

## Implementation gate

Before implementation begins, the project must approve:

- standard `Contact`, `Address`, `User`, `Student`, `Student Applicant`, `Employee`, `Instructor`, `Guardian`, and `Customer` field fit-gap;
- physical data model and naming;
- exact Frappe roles, permissions, query restrictions, and document-level checks;
- encryption, key management, audit-event, backup, and restore design;
- API/event contracts, reconciliation, and idempotency;
- synthetic test scenarios and negative authorization tests;
- migration scripts and rollback/forward-repair plan.

## Change control

Material changes to the approved person/role boundary, identifier policy, matching authority, proxy model, institution scope, or privacy controls require a superseding ADR. Editorial clarifications may update supporting documents without changing this decision.
