# Identity Lifecycle and Resolution Rules

Status: **Proposed for ADR-002 approval**

## Person lifecycle

| Current state | Event | Next state | Authority | Required controls |
|---|---|---|---|---|
| None | Identity first observed | Candidate | Approved workflow/integration | Source provenance; duplicate search |
| Candidate | Evidence verified | Active | Identity steward or trusted deterministic process | Evidence policy and audit |
| Candidate | Plausible duplicate found | Review | Resolution service | Preserve transaction; no automatic merge |
| Review | Confirmed distinct | Candidate/Active | Identity steward | Decision reason and evidence snapshot |
| Review | Confirmed same person | Merged or linked | Authorized steward | Impact preview and merge controls |
| Active | No active roles remain | Inactive | Governed lifecycle job/steward | Do not delete history or identifiers |
| Inactive | New valid role | Active | Owning role workflow | Re-resolve before creating a person |
| Active | Legal/privacy hold | Restricted | Privacy/security/registrar authority | Reason, duration, access consequences |
| Restricted | Restriction released | Prior appropriate state | Same policy authority | Release audit |
| Candidate/Active/Inactive | Duplicate merge completed | Merged | Merge approver | Survivor link, alias preservation, reconciliation |

Role status changes do not directly drive person status without a governed evaluation. A rejected applicant, terminated employee, or graduated student remains a person with retained history.

## Role-link lifecycle

| State | Meaning | Allowed transition |
|---|---|---|
| Pending | Proposed link awaiting validation | Active, disputed, cancelled |
| Active | Confirmed link to authoritative role record | Inactive, disputed |
| Inactive | Historical valid relationship | Active, disputed |
| Disputed | Ownership or correctness under review | Active, inactive, replaced |
| Replaced | Link superseded after correction | Terminal with successor reference |

Creating a role record must resolve the person first. Retries use an idempotency key and cannot issue a second role link or institutional identifier.

## Matching rules

### Evidence tiers

| Tier | Evidence | Permitted outcome |
|---|---|---|
| A | Verified unique identifier from a trusted issuer, with matching namespace | Automatic link only when exactly one eligible person matches and no conflict exists |
| B | Multiple corroborating attributes such as legal name, DOB, verified contact, prior identifier | Candidate ranking and manual review |
| C | Name, unverified email/phone, address, demographic similarity | Candidate discovery only |
| D | Conflicting verified identifier or material identity conflict | Mandatory hold and investigation |

No probabilistic score alone may authorize a merge. Rules are versioned; every result stores rule version, normalized evidence, candidates considered, and disposition.

### Normalization

- Normalize case, spacing, Unicode representation, phone format, dates, and identifier formatting without discarding original values.
- Do not transliterate or apply phonetic matching as proof of identity.
- Treat shared household contact data as weak evidence.
- Treat common, preferred, former, and local-script names according to their type and effective dates.
- Never expose restricted identifiers in search suggestions, logs, URLs, or client-side telemetry.

## Review workflow

1. Freeze automatic linking for the affected transaction.
2. Present the minimum evidence needed to trained reviewers.
3. Allow decisions: same person, distinct person, insufficient evidence, or escalate.
4. Require a reason and evidence snapshot.
5. Apply the decision through a controlled service.
6. Notify affected workflows through idempotent events.
7. Retain the case under the approved schedule.

Reviewers cannot approve their own exceptional override when separation-of-duty policy applies.

## Merge policy

### Preconditions

- both people and all role links are identified;
- legal/privacy holds and active disputes are checked;
- survivor selection follows a deterministic policy;
- conflicting identifiers, users, students, employees, customers, and financial records are resolved explicitly;
- downstream impact and rollback feasibility are documented;
- approval authority is satisfied.

### Execution

1. Create a locked merge case and correlation ID.
2. Revalidate that records have not materially changed.
3. Preserve source identifiers and an immutable survivor mapping.
4. Repoint only approved links using recoverable operations.
5. Mark the duplicate merged; do not reuse or hard-delete its key.
6. Publish versioned merge events.
7. Reconcile every registered consumer and record exceptions.
8. Close the case only after reconciliation or approved exception handling.

### Authority

Routine, low-conflict merges require an identity steward. Merges involving two active students, two active employees, financial balances, legal holds, restricted identities, or conflicting verified identifiers require dual approval with the relevant domain owner.

## Split and correction

A mistaken merge is handled as an incident. The system must preserve enough lineage to identify moved links, but automatic reversal is not guaranteed. Academic, financial, payroll, and external transactions require domain reconciliation. A split plan requires security/privacy review and dual approval.

Ordinary corrections preserve prior value, effective dates, provenance, actor, reason, and impacted integrations. Correcting a name or contact does not create a new person.

## Numbering policy

- Person keys are system-generated opaque identifiers.
- Applicant, student, employee, and external identifiers remain distinct namespaces.
- Namespace includes institution/issuer and identifier type.
- Numbers are not recycled.
- Corrections retire and replace values with lineage.
- Human-readable numbers are not authentication factors.
- Cross-institution deployments do not assume student-number uniqueness outside a namespace.

## Operational metrics

Monitor candidate creation rate, possible-match rate, review age, merge/split volume, false-match incidents, identifier conflicts, event reconciliation failures, restricted-data access, and cross-institution authorization denials. Metrics must avoid exposing raw PII.
