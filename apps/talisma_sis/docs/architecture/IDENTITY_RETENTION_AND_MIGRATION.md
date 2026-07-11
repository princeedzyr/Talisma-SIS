# Identity Retention and Migration Strategy

Status: **Proposed for ADR-002 approval**

This document defines control requirements. Exact retention periods are institution- and jurisdiction-specific and must be configured from an approved schedule rather than embedded in application code.

## Retention principles

- Retain only for documented academic, operational, contractual, legal, audit, or security purposes.
- A legal hold overrides ordinary disposition.
- Role-record retention does not automatically determine every identity attribute's retention.
- Deactivation, restriction, minimization, and pseudonymization are preferred when history must remain referentially intact.
- Destruction must include primary data, derived indexes, exports under institutional control, and eventual backup expiry where feasible.
- Every disposition action is authorized, logged, and reconcilable.

## Retention matrix

| Data category | Retention trigger | Proposed treatment | Approval owner |
|---|---|---|---|
| Canonical person key and merge alias | End of all institutional obligations | Retain while referenced; minimize descriptive data where permitted | Registrar/privacy |
| Core name history | End of last applicable academic/employment/legal obligation | Retain necessary history; dispose unsupported aliases | Registrar/HR/privacy |
| Institutional identifiers | Replacement or end of relationship | Retain lineage while referenced; prevent reuse | Issuing domain owner |
| Government identifiers | Purpose completion | Remove/tokenize as early as permitted; never retain by convenience | Privacy/legal |
| Contact/address history | Superseded or relationship end | Retain only required operational/audit history | Registrar/HR/privacy |
| Role links | End of role | Retain while role records and audit obligations exist | Domain owner |
| Relationships | Relationship end | Retain verified history only as policy requires | Registrar/privacy |
| Proxy authorizations | Expiry/revocation | Retain grant and action audit for approved period | Registrar/legal |
| Match-review evidence | Case closure | Minimize and dispose according to identity-risk schedule | Identity governance |
| Merge/split case | Reconciliation completion | Retain decision, lineage, approvals, and exceptions | Registrar/security |
| Identity evidence files | Verification completion | Delete promptly unless law/policy requires retention | Privacy/legal |
| External mappings | Integration termination | Retain reconciliation key only while obligations persist | Integration owner |
| Security/audit events | Event date | Protected retention aligned to incident and compliance needs | Security/privacy |

## Disposition workflow

1. Identify records eligible under the policy version in force.
2. Check legal hold, active role, open case, downstream reference, and backup constraints.
3. Generate an impact report without exposing unnecessary PII.
4. Obtain required approval.
5. Apply delete, redact, tokenize, or pseudonymize action idempotently.
6. Notify registered consumers and reconcile outcomes.
7. Record policy, authority, counts, exceptions, and completion evidence.

Hard deletion of a canonical person is prohibited while academic, financial, employment, consent, audit, integration, or legal records reference that identity.

## Migration objectives

- Link existing records without changing their native business behavior.
- Preserve existing identifiers and audit history.
- Avoid automatic merges based on weak evidence.
- Make every transformation repeatable, observable, restartable, and reversible where feasible.
- Complete rehearsal and reconciliation before production cutover.

## Source inventory

At minimum inventory `User`, `Contact`, `Address`, `Student Applicant`, `Student`, `Guardian`, `Employee`, `Instructor`, `Customer`, party links, portal users, external IDs, and relevant custom fields. For every source field document owner, meaning, quality, nullability, uniqueness, normalization, sensitivity, and target disposition.

## Migration phases

### 1. Discovery and profiling

Use read-only profiling to measure counts, duplicates, invalid identifiers, shared contacts, conflicting relationships, orphan links, and institution scope. Use masked results outside the authorized migration team.

### 2. Mapping approval

Approve source-to-concept mappings and explicitly classify each field as migrate, reference, transform, archive, or discard. No field migrates merely because it exists upstream.

### 3. Dry-run identity resolution

Run deterministic matches against a frozen extract. Produce categories: unique trusted match, new person, possible match, conflict, and invalid source. Do not mutate production.

### 4. Manual remediation

Identity stewards resolve ambiguous and conflicting cases. Decisions are captured as migration inputs with provenance, not hidden spreadsheet edits.

### 5. Rehearsal

Restore a production-like, access-controlled backup into an isolated environment; apply the migration; run count, referential, permission, and workflow tests; then destroy the environment under policy.

### 6. Cutover

Take an approved backup, establish the change window, stop conflicting writes or capture deltas, run idempotent patches, reconcile, and obtain domain-owner sign-off before enabling dependent workflows.

### 7. Post-cutover monitoring

Monitor duplicates, authorization denials, failed events, orphan links, identifier conflicts, and role conversion. Retain rollback artifacts until the acceptance window closes.

## Linking precedence

1. Existing approved explicit mapping.
2. Verified unique identifier in the correct namespace.
3. Authorized migration decision from reviewed evidence.
4. Otherwise create a candidate or review case—never guess.

Email, phone, name, date of birth, or address alone cannot authorize an existing-person link. A `User` email match is especially insufficient because accounts and email addresses may be shared, renamed, or recycled.

## Reconciliation controls

| Control | Acceptance expectation |
|---|---|
| Source/target counts | Every source record classified and accounted for |
| Role links | Every migrated role links to exactly one person or documented exception |
| Identifier uniqueness | No duplicate active value inside a namespace |
| Orphans | No unresolved target reference outside approved exception register |
| Permissions | Cross-person and cross-institution negative tests pass |
| Financial/academic integrity | No totals, grades, enrollment, or ledger behavior altered |
| Audit | Migration batch, rule version, source key, outcome, and errors recorded |
| Retry | Re-running a completed batch creates no duplicates |
| Backup/restore | Recovery procedure tested before production cutover |

## Rollback

Migration design must separate creation of canonical records, role linking, and consumer enablement. Rollback may disable new workflows and restore link state, but it must not blindly delete records after downstream transactions begin. The cutover plan defines the point of no automatic rollback and the forward-repair procedure.

## Go-live blockers

- unapproved retention schedule or legal-hold process;
- unresolved high-risk duplicate/conflict cases;
- missing institution scope;
- untested permission matrix;
- unreconciled role or external mappings;
- unavailable verified backup/restore;
- migration scripts that are not idempotent;
- production data copied to uncontrolled environments.
