# Identity Threat Model

Status: **Proposed for ADR-002 approval**

## Scope and assets

This review covers canonical identity, names, identifiers, relationships, role links, proxy grants, identity evidence, matching, merge/split workflows, exports, and integrations. Critical assets are identity integrity, confidentiality, authorization correctness, audit evidence, institutional separation, and availability of resolution workflows.

## Trust boundaries

- browser or portal to Frappe application;
- staff workstation to administrative UI;
- application to database, files, cache, and background workers;
- Talisma to ERPNext/Education role records;
- Talisma to identity providers and external integrations;
- one institution's administrative scope to another;
- normal administration to emergency or privileged operations.

## Threat register

| Threat | Example impact | Required mitigation | Verification |
|---|---|---|---|
| Account/person misbinding | Attacker gains another student's portal | Stable IdP subject mapping; no email-only binding; reviewed recovery | SSO and email-change tests |
| False positive match | Records of two people combined | Tiered evidence; no score-only merge; human review | Twins/shared-contact scenarios |
| Duplicate identity | Fragmented transcript, billing, access | Resolution before role creation; idempotency; reconciliation | Applicant conversion/retry tests |
| Unauthorized merge | Academic/financial corruption | Restricted workflow, dual approval for high risk, impact preview | Permission and audit tests |
| Incomplete merge propagation | Conflicting downstream identities | Versioned events, consumer registry, retry/dead-letter reconciliation | Failure-injection tests |
| Privilege escalation via relationship | Guardian sees adult student's records | Relationship separate from scoped grant; effective-date checks | Proxy matrix tests |
| Directory suppression leak | Protected student appears in search/export | Central suppression policy across every channel | Portal/report/API tests |
| Restricted identifier exposure | Government ID leaks to logs or exports | Encryption/tokenization, masking, log filtering, field allowlists | Log/export inspection |
| Cross-institution access | Staff sees another institution's people | Mandatory institution scope and server-side checks | Negative tenancy tests |
| Overprivileged administrator | Technical admin browses business data | Separate support elevation, purpose logging, review | Admin denial/elevation tests |
| Malicious integration | Source overwrites authoritative values | Field ownership contract, service scopes, validation | Contract and replay tests |
| Replay/duplicate event | Duplicate role or identifier | Idempotency keys, version/correlation checks | Replay tests |
| Evidence-file compromise | Identity documents exposed | Restricted storage, malware scan, signed access, retention | Storage/access tests |
| Enumeration | API reveals whether a person exists | Rate limits, generic responses, scoped search | Abuse tests |
| Audit tampering | Misuse cannot be investigated | Append-oriented protected logs, limited deletion, monitoring | Integrity/access tests |
| Denial of resolution service | Admissions blocked or bypassed | Queues, safe hold behavior, monitoring; never fail open | Availability tests |

## Security requirements

- TLS for network transport and platform-supported encryption at rest for restricted values and evidence.
- Secrets remain outside documents, logs, fixtures, repositories, and URLs.
- Server-side authorization for every read, mutation, report, export, API, and background job.
- CSRF/session controls for browser operations and scoped credentials for services.
- Rate limiting and abuse detection for identity lookup, recovery, and portal endpoints.
- File type/size validation, malware scanning, restricted storage, and expiring access for evidence.
- Masking does not replace authorization or encryption.
- Production data is prohibited in development and automated tests unless formally de-identified.

## Privacy abuse cases

- Staff searches acquaintances without educational interest.
- An adviser bulk-exports a cohort outside assigned scope.
- A guardian retains access after consent expires.
- An integration retains data after its purpose ends.
- Support personnel use impersonation without a support case.
- Suppressed directory data remains cached externally.

Mitigations include purpose capture for sensitive access, anomaly monitoring, periodic access certification, immediate revocation, cache invalidation, export controls, and institutional incident response.

## Residual risks requiring institutional decision

- Jurisdiction-specific identity evidence and retention requirements.
- Whether government identifiers are collected at all.
- Maximum emergency-access duration and eligible roles.
- Acceptable matching evidence and false-match tolerance.
- External systems unable to consume merge or suppression events.
- Legal feasibility and operational cost of separating mistaken merges.

## Security gate

Before implementation, perform permission tests, abuse-case review, data-flow mapping, dependency/security scanning, backup/restore tests for encrypted data, key-rotation design, incident-response tabletop, integration failure injection, and privacy/legal sign-off.
