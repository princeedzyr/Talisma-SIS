# Identity Authorization and FERPA Matrix

Status: **Accepted supporting architecture under ADR-002; institution-specific policy and implementation not authorized**

This matrix defines policy expectations, not Frappe roles or permissions. Legal counsel and each institution must validate its FERPA and jurisdiction-specific rules.

## Authorization model

Every decision combines authenticated actor, job function, institution scope, record relationship, declared purpose, data class, record state, disclosure restriction, and exceptional-access state. A role name alone is insufficient.

## Data classes

| Class | Examples | Baseline control |
|---|---|---|
| Directory | Institution-approved directory name or contact | Releasable only under active institutional policy and no suppression |
| Internal | Opaque keys, lifecycle state, operational metadata | Authenticated workforce with scoped need |
| Confidential personal | Names, DOB, personal contact, relationships | Need-to-know and institutional scope |
| Educational record | Enrollment-linked identity and academic associations | Legitimate educational interest or valid authorization |
| Restricted identity | Government IDs, evidence, match details, merge cases | Named steward roles, masking, enhanced audit |
| Highly restricted | Court orders, exceptional evidence, security investigations | Explicit case authorization and security/privacy oversight |

## Persona matrix

Legend: `R` read, `U` update, `A` approve, `S` self-service, `—` denied by default. Every grant remains scope- and purpose-limited.

| Persona | Basic identity | Contact | Identifiers | Relationships | Proxy grants | Match/merge evidence |
|---|---:|---:|---:|---:|---:|---:|
| Person/self | R/S | R/S | Masked R | R | R/S request | — |
| Applicant processor | R/U | R/U | Limited R/U | Limited R | — | Submit review |
| Registrar | R/U | R/U | R/U | R/U | R | Review/approve per delegation |
| Identity steward | R/U | R/U | R/U | R/U | R | R/U/A |
| Instructor | Directory/roster R | Institution contact R | — | — | — | — |
| Academic adviser | Scoped R | Scoped R | Masked R | Scoped R | Scoped R | — |
| Guardian/proxy | Authorized R | Authorized R | — | Own relationship R | Own grant R | — |
| HR officer | Employee-scoped R/U | Employee-scoped R/U | Employee IDs | Limited R | — | Submit review |
| Finance officer | Billing identity R | Billing contact R/U | Billing reference only | Sponsor relation R | — | — |
| Integration service | Contract fields | Contract fields | Scoped external IDs | Contract fields | — | — |
| Privacy/security officer | Audit/policy R | Audit/policy R | Restricted R as justified | R | R/A exceptional | Audit R; emergency oversight |
| System administrator | Technical metadata | — by default | — by default | — by default | — | — |

System administration does not automatically imply business-data access. Production support requires controlled elevation.

## Guardian and proxy rules

1. A relationship never grants access by itself.
2. Adult-student access is denied unless consent, law, court order, or documented institutional policy authorizes it.
3. Minor status and legal authority are evaluated using effective dates and jurisdiction policy.
4. Grants enumerate record categories and actions; they cannot use an unrestricted “all records” default.
5. Revocation takes effect immediately for new sessions and tokens where technically possible.
6. The protected person can view active grants unless law or safety policy prohibits disclosure.
7. Proxy actions are attributed to the proxy, never recorded as actions by the student.

## Directory-information suppression

Directory designation is institution-configured and versioned. Suppression overrides directory release across portals, search, reports, exports, integrations, and public APIs. A suppression change must generate an auditable event and propagate through a monitored workflow.

## Sensitive operations requiring enhanced audit

- viewing unmasked restricted identifiers;
- bulk search or export;
- creating or revoking proxy authority;
- changing legal identity or verification state;
- linking or unlinking role profiles;
- resolving possible matches;
- merging or splitting people;
- impersonation or emergency access;
- changing disclosure restrictions;
- integration replay involving personal data.

Audit events capture actor, subject, institution, purpose/reason, action, timestamp, correlation ID, outcome, and relevant policy version. Audit logs must not contain raw secrets or full government identifiers.

## Emergency access

Break-glass access is disabled by default, time-limited, reason-bound, separately logged, and reviewed after use. It must not bypass legal prohibitions. Institutions define eligible roles and maximum duration; security and privacy officers receive alerts.

## Frappe implementation constraints

- Use role permissions for broad capability, User Permissions and permission-query hooks for scope, and document-level checks for relationship/purpose rules.
- Revalidate authorization server-side for every API and export; client-side hiding is not security.
- Avoid permission logic that depends only on mutable email addresses or display names.
- Background jobs and integrations use dedicated service identities with minimum scope.
- Reports must apply equivalent restrictions to source DocTypes and must not leak counts or identifiers through filters/autocomplete.

## Approval evidence required

Before implementation, test synthetic scenarios for self-service, registrar, adviser, instructor roster, guardian consent, minor guardian, revoked proxy, directory suppression, cross-institution denial, restricted identifier masking, bulk export, emergency access, and service-account integration.
