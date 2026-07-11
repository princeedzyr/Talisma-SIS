# Identity Physical Schema Review Gate

Status: **Ready for review; not approved**

This gate determines whether the accepted ADR-002 architecture is sufficiently specified to authorize a minimal DocType implementation. Merging this document does not approve the schema.

## Review artifacts

- [Standard DocType Fit-Gap](IDENTITY_STANDARD_DOCTYPE_FIT_GAP.md)
- [Physical Schema Proposal](IDENTITY_PHYSICAL_SCHEMA_PROPOSAL.md)
- [Security, Permissions and Indexing](IDENTITY_SCHEMA_SECURITY_AND_PERMISSIONS.md)
- [Migration and Test Plan](IDENTITY_SCHEMA_MIGRATION_AND_TEST_PLAN.md)
- [ADR-002 Acceptance Record](ADR-002-ACCEPTANCE-RECORD.md)

## Proposed first slice

- Talisma Person.
- Talisma Person Name child table.
- Talisma Identifier Type.
- Talisma Person Identifier limited to non-government institutional identifiers.
- Talisma Role Link for installed, approved standard targets.
- Talisma Contact Association only if permission and upstream-behavior tests pass.

No automatic matching, merge/split automation, proxy access, evidence files, government identifiers, bulk production migration, external write API or Education-specific link is included.

## Blocking decisions

| Blocker | Required resolution |
|---|---|
| ADR-003 remains Proposed | Accept authoritative institution hierarchy and Link target before physical institution-scoped fields are created |
| Identifier protection | Approve keyed hashing, encryption/key ownership, masking and recovery requirements |
| Composite uniqueness | Approve MariaDB-compatible constraint/index and concurrency strategy |
| Contact/Address association | Verify permissions, delete behavior and no conflict with ERPNext party links |
| Exact role design | Approve Frappe roles, user-permission scope and controlled elevation |
| Legal/policy configuration | Define minimum deployable FERPA, retention, directory and emergency-access policy set |

## Review checklist

- [ ] Every proposed field has a single authoritative owner.
- [ ] No PII appears in document names.
- [ ] Standard fields are reused without bidirectional sync ambiguity.
- [ ] Education remains optional and no metadata Link requires it.
- [ ] Institution scope target is approved through ADR-003.
- [ ] UUID naming and immutable rename policy are approved.
- [ ] Identifier normalization, hashing, masking and encryption are approved.
- [ ] Composite uniqueness and race handling are approved.
- [ ] Dynamic Link target allowlists are approved.
- [ ] Deletion, merge alias and retention behavior are approved.
- [ ] Exact permission roles and server-side enforcement points are approved.
- [ ] Audit event catalogue is approved.
- [ ] Migration mapping, idempotency and reconciliation are approved.
- [ ] Synthetic negative-permission scenarios are approved.
- [ ] First-slice exclusions are accepted.
- [ ] No implementation begins until blockers are closed and approval is recorded.

## Required reviewers

Product architecture, registrar/records ownership, privacy/legal, security, ERPNext/Frappe engineering, database engineering, operations, migration ownership and representatives for HR and finance. Education-specific review is deferred until ADR-001 permits that integration.

## Approval outcome

When all blockers and applicable checklist items are closed, create a schema approval record identifying the exact proposal revision and first implementation scope. Until then, these documents are design inputs only.
