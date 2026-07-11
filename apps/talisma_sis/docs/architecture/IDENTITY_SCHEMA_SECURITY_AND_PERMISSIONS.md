# Identity Schema Security, Permissions and Indexing

Status: **Proposed for physical-schema approval**

## Permission architecture

Frappe Role Permission Manager supplies broad capability only. Identity access additionally requires server-side institution scope, relationship/purpose evaluation, field classification and record state checks.

| Proposed role | Person | Name/contact association | Identifier | Role link | Review/merge | Configuration |
|---|---|---|---|---|---|---|
| Talisma Identity Viewer | Scoped read | Scoped read | Masked only | Scoped read | None | None |
| Talisma Identity Editor | Scoped read/update | Scoped create/update | No protected value | Create/request correction | Submit review | None |
| Talisma Identity Steward | Scoped full lifecycle | Scoped full lifecycle | Restricted scoped access | Resolve disputed links | Decide routine cases | Read |
| Talisma Identity Approver | Scoped read | Scoped read | Restricted as justified | Approve high-risk action | Dual approval | Read |
| Talisma Privacy Officer | Policy/audit access | Disclosure oversight | Justified restricted read | Audit | Exceptional oversight | Privacy configuration |
| Talisma Identity Administrator | Technical configuration | None by default | None by default | None by default | None by default | Identifier types/rules |
| Integration service | Contract allowlist | Contract allowlist | External/scoped IDs only | Contract operations | None | None |

Role names are proposed and do not authorize creation. System Manager does not automatically receive unmasked restricted identity data.

## Enforcement points

- `permission_query_conditions` limits lists, search, reports and link queries by institution scope and allowed relationships.
- `has_permission` or approved v16 extension mechanisms enforce document-level purpose and state rules.
- Controller/service validation protects create, update, lifecycle transitions and target allowlists.
- Whitelisted APIs re-evaluate permissions and expose explicit response schemas.
- Reports and exports use the same policy service and field allowlists.
- Background jobs run as dedicated service identities with explicit institution scope.
- Direct database reports are prohibited for protected identity data unless separately governed.

Client-side hiding is usability only and is never treated as authorization.

## Sensitive fields

| Field category | Storage | Display | Search/log/export |
|---|---|---|---|
| UUID person key | Plain internal key | Limited operational display | May be logged as correlation key |
| Institutional identifier | Protected according to type; equality hash | Masked by default | Exact authorized lookup; no autocomplete leakage |
| Government identifier | Not in first slice; encrypted/tokenized if later approved | Strong mask and explicit reveal | Never logs/URLs/general exports |
| Identity evidence | Restricted file store, not ordinary public attachment | Time-limited authorized access | No full-text search or telemetry |
| Match evidence | Restricted structured snapshot | Steward-only | No broad export |
| Restriction/legal reason | Controlled code plus restricted case reference | Need-to-know | No list-column exposure |

Frappe `Password` fields may encrypt recoverable values, but the implementation review must verify key management, backup/restore, rotation and operational access. A keyed normalized hash supports equality checks without exposing raw values; its key is stored outside the database and repository.

## Database constraints and indexes

### Talisma Person

- Primary key on UUID `name`.
- Index `(lifecycle_status, modified)` for operational queues.
- Index `survivor_person` for merge resolution.
- Search index on `display_name`, with suppression and scope enforced before results are returned.

### Talisma Person Identifier

- Index `person`.
- Composite unique strategy on `(issuer_namespace, identifier_type, normalized_value_hash)` for eligible active values.
- Index `(institution_scope, identifier_type, status)`.
- Index `expires_on` for expiry processing.
- Index `replaced_by`.

Conditional uniqueness is not expressible solely through ordinary DocType field flags. The implementation must use a reviewed MariaDB-compatible constraint/index strategy plus transactional validation and race-condition tests.

### Talisma Role Link

- Unique `(profile_doctype, profile_name)` for non-replaced links.
- Index `(person, role_type, status)`.
- Index `(institution_scope, role_type, status)`.
- Index `valid_to` for lifecycle processing.

### Talisma Contact Association

- Index `(person, purpose, status/effective interval)` as finalized.
- Index `(record_type, record_name)`.
- Enforce one effective preferred association per person/purpose using transactional validation and an approved constraint strategy.

## Query safety

- Person list search returns display value and minimum contextual disambiguators only.
- Restricted identifiers require exact normalized lookup and explicit permission; partial/wildcard search is denied.
- Cross-institution searches require an approved central-office scope.
- Search results exclude merged aliases unless resolving through the survivor service.
- Directory suppression applies before cached/autocomplete output.
- Rate limits and anomaly monitoring apply to identity lookup endpoints.

## Audit events

In addition to framework document versions, emit structured events for person creation, verification change, restricted-data reveal, identifier issuance/retirement, role link/unlink, relationship/proxy change, disclosure change, review decision, merge/split, export, emergency access and migration batch.

Events include actor, effective user, person, institution scope, purpose/reason code, policy/rule version, correlation ID, outcome and timestamp. They exclude raw protected values.

## Performance acceptance targets

Exact service-level targets require product approval. Before implementation, load tests must cover exact identifier lookup, scoped person search, profile-to-person resolution, applicant conversion, permission-filtered lists and event reconciliation at representative institutional volumes. Query plans must prove indexes are used and that permission hooks do not cause unbounded per-row queries.

## Security test gate

- Cross-institution negative tests.
- Restricted-field masking and reveal audit.
- Link-search and report leakage tests.
- Service-user scope tests.
- Race tests for identifier and role-link uniqueness.
- Merge alias authorization tests.
- Directory suppression across search, portal, report, export and API.
- Backup/restore test for encrypted values and hashes.
- Key rotation and revoked credential tests.
- System Manager denial and controlled elevation tests.
