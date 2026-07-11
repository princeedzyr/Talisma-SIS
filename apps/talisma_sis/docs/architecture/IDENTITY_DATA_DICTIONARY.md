# Identity Conceptual Data Dictionary

Status: **Proposed for ADR-002 approval**

This is a field-level conceptual model, not an approved Frappe schema. Names are architectural labels and must not be treated as authorized DocType or field names.

## Design decisions proposed for approval

1. Talisma owns a canonical natural-person identity; standard role records remain authoritative for their domains.
2. A deployment may serve multiple institutions, but every institutional identifier and authorization is explicitly institution-scoped.
3. Standard `Contact` and `Address` remain communication records. Talisma adds governed associations and history only where upstream semantics are insufficient.
4. Authentication remains owned by `User`; email is never a durable identity key.
5. Organizations are not represented as people. ERPNext party masters remain authoritative until a separate organization-party decision is approved.

## Person

| Attribute | Meaning | Classification | Required rule |
|---|---|---|---|
| Person key | Opaque, immutable internal identity | Internal | System generated; never reused or derived from PII |
| Lifecycle status | Candidate, active, inactive, restricted, merged | Internal | Independent of role status |
| Survivor reference | Canonical person after merge | Restricted | Required only for merged records; immutable |
| Primary institution | Administrative home, if applicable | Internal | Does not limit additional affiliations |
| Verification state | Unverified, partially verified, verified, disputed | Confidential | Derived from approved evidence and review |
| Created source | Originating workflow or integration | Internal | Immutable provenance |
| Created/modified audit | Actor and timestamps | Internal | Framework audit plus protected events |

The person record must not own admission, enrollment, employment, teaching, billing, or login status.

## Person name

| Attribute | Meaning | Classification | Rule |
|---|---|---|---|
| Name type | Legal, preferred, former, local-script, alias | Confidential | Controlled vocabulary |
| Components | Prefix, given, middle, family, suffix | Confidential | Store components without assuming every culture uses all components |
| Display value | Approved formatted representation | Confidential | Derived or explicitly supplied; not a match key by itself |
| Script/language | Representation metadata | Internal | BCP 47/language and script conventions where used |
| Effective interval | Valid-from and valid-to | Confidential | No overlapping legal-name intervals without review |
| Preferred flag | Preferred institutional display | Confidential | At most one effective preferred name per context |
| Evidence/source | Provenance of assertion | Restricted | Evidence metadata; documents stored under stricter control |

## Person identifier

| Attribute | Meaning | Classification | Rule |
|---|---|---|---|
| Namespace | Institution and identifier type | Internal | Uniqueness boundary |
| Value | Identifier presented or issued | Varies | Normalized for comparison; original representation retained if required |
| Type | Person, applicant, student, employee, government, external | Internal | Controlled and versioned |
| Issuer | Issuing institution or authority | Internal | Mandatory for externally issued identifiers |
| Status | Active, retired, replaced, disputed | Internal | Values are retired, never silently overwritten |
| Issue/expiry dates | Identifier validity | Confidential | Optional by type |
| Verification | Verification state, method, time | Restricted | Required before deterministic matching |
| Replacement link | Corrected or successor identifier | Restricted | Preserves lineage |

Institutional person identifiers must be opaque. Government identifiers must be encrypted or tokenized, masked by default, excluded from logs and URLs, and prohibited as document names.

## Role profile link

| Attribute | Meaning | Classification | Rule |
|---|---|---|---|
| Person key | Canonical person | Internal | Exactly one per link |
| Role type | Applicant, student, employee, instructor, user, customer, guardian | Internal | Controlled vocabulary |
| Target type/key | Standard or Talisma record reference | Internal | Unique for target type and target key |
| Institution scope | Institution owning the relationship | Internal | Mandatory unless target is globally scoped |
| Effective interval | Relationship validity | Confidential | Does not replace target record status |
| Link status | Pending, active, inactive, disputed | Internal | Disputed links block sensitive propagation |
| Provenance | Workflow, integration, reviewer | Restricted | Required for manual links |

## Contact and address association

| Attribute | Meaning | Classification | Rule |
|---|---|---|---|
| Standard record reference | `Contact` or `Address` | Confidential | Upstream record remains communication master |
| Person key | Associated person | Internal | Association must be explicit |
| Purpose | Personal, institutional, emergency, mailing, permanent, billing | Confidential | A value may have more than one governed purpose |
| Effective interval | Period of use | Confidential | Historical associations remain auditable |
| Verification state | Unverified or verified | Confidential | Verification method/time recorded separately |
| Disclosure class | Directory, internal, confidential, restricted | Restricted | Drives release policy, not authentication |
| Source/consent | Provenance and permitted use | Restricted | Required where policy or law demands it |

Before implementation, a field-level fit-gap must confirm which attributes can use standard fields and which require Talisma-owned related records. No uncontrolled bidirectional synchronization is permitted.

## Person relationship

| Attribute | Meaning | Classification | Rule |
|---|---|---|---|
| Source/target person | Directional participants | Confidential | Self-relationships prohibited |
| Relationship type | Parent, guardian, dependent, spouse, emergency contact, sponsor | Confidential | Does not grant access |
| Effective interval | Relationship validity | Confidential | Required for authorization evaluation |
| Verification/source | Basis for relationship | Restricted | Required for guardian or legal relationships |
| Status | Pending, verified, disputed, ended | Confidential | Only verified relationships may support proxy review |

## Proxy authorization

| Attribute | Meaning | Classification | Rule |
|---|---|---|---|
| Grantor/subject/proxy | Person granting, protected subject, authorized person | Restricted | Grantor may be institution where law permits |
| Authority basis | Consent, law, court order, institutional policy | Restricted | Mandatory and evidence-backed |
| Scope | Record categories and permitted actions | Restricted | Deny by default; no blanket implicit access |
| Effective interval | Start, end, revocation | Restricted | Evaluated on every access |
| Institution scope | Applicable institution | Restricted | Mandatory |
| Verification/reviewer | Approval evidence | Restricted | Dual review for exceptional grants |

## External identity link

| Attribute | Meaning | Classification | Rule |
|---|---|---|---|
| System namespace | IdP or integration identifier | Internal | Unique and immutable |
| External subject | Source-system stable key | Restricted | Never infer from email |
| Person key | Canonical identity | Internal | One active mapping per namespace/subject |
| Sync ownership | Fields owned by each system | Internal | Explicit contract |
| State/version | Sync cursor, status, schema version | Internal | Supports replay and reconciliation |

## Identity review and merge case

| Attribute | Meaning | Classification | Rule |
|---|---|---|---|
| Case type | Possible match, correction, merge, split, disputed link | Restricted | Controlled workflow |
| Candidates | Person records under review | Restricted | Minimum necessary evidence |
| Rule/evidence snapshot | Why the case exists | Restricted | Versioned and immutable after decision |
| Decision | Match, distinct, merge, correct, hold | Restricted | Reason mandatory |
| Reviewer(s) | Authorized stewards | Restricted | Separation of duties for high-risk operations |
| Downstream impact | Affected roles and integrations | Restricted | Required before merge approval |
| Reconciliation state | Pending, complete, exception | Restricted | Case remains open until consumers reconcile |

## Explicit exclusions

- Passwords, sessions, and authentication secrets remain in the identity provider/Frappe authentication layer.
- Grades, attendance, applications, employment, invoices, and role-specific statuses remain in their owning modules.
- Disability, conduct, health, and financial-aid details are not general identity attributes.
- Scanned evidence is not stored in ordinary attachments without restricted storage and access controls.

## Schema gate

Before any DocType is created, this dictionary requires registrar, privacy, security, HR, finance, and engineering review; a standard-field fit-gap; naming approval; cardinality validation; and representative-data modeling using synthetic records only.
