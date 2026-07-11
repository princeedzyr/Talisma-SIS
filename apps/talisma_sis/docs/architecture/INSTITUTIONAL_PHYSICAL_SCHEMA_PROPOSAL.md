# Institutional Physical Schema Proposal

Status: **Partially approved: Slice A (`Talisma Institution`) only; later slices not authorized**

This proposal translates accepted ADR-003 into Frappe records. Names and fields are exact design candidates but remain unapproved until the institutional schema review gate is accepted.

## Conventions

- All records belong to the `talisma_sis` app and Talisma SIS module.
- Core domain records use server-generated UUIDv4 document names; no PII or mutable code appears in `name`.
- Human-facing codes are explicit immutable fields, unique within their defined scope and never recycled.
- Composite uniqueness requires reviewed MariaDB indexes/constraints plus transactional validation because ordinary DocType field flags cannot express every scoped rule.
- Dates use half-open intervals: effective at `valid_from`, no longer effective after `valid_to`; null end means open-ended.
- Historical approved structures are immutable.
- Education-specific Dynamic Link targets are disabled while ADR-001 remains unaccepted.

## Entity overview

```mermaid
erDiagram
    TALISMA_INSTITUTION ||--o{ TALISMA_CAMPUS : operates
    TALISMA_INSTITUTION ||--o{ TALISMA_ACADEMIC_UNIT : governs
    TALISMA_INSTITUTION ||--o{ TALISMA_STRUCTURE_VERSION : versions
    TALISMA_STRUCTURE_VERSION ||--o{ TALISMA_UNIT_PLACEMENT : contains
    TALISMA_ACADEMIC_UNIT ||--o{ TALISMA_UNIT_PLACEMENT : child
    TALISMA_ACADEMIC_UNIT ||--o{ TALISMA_UNIT_PLACEMENT : parent
    TALISMA_STRUCTURE_VERSION ||--o{ TALISMA_UNIT_CLOSURE : materializes
    TALISMA_INSTITUTION ||--o{ TALISMA_STANDARD_MAPPING : scopes
    TALISMA_ACADEMIC_UNIT ||--o{ TALISMA_ACADEMIC_OWNERSHIP : owns
    TALISMA_INSTITUTION ||--o{ TALISMA_SCOPE_GRANT : authorizes
```

## Talisma Institution

Standalone, non-submittable root for security, policy and data partitioning. This is the physical target required by ADR-002 `institution_scope` fields.

| Field | Frappe type | Required | Index/unique | Semantics |
|---|---|---:|---|---|
| `name` | System name | Yes | PK | UUIDv4, immutable |
| `institution_code` | Data | Yes | Unique | Stable uppercase machine code; immutable |
| `institution_name` | Data | Yes | Search index | Current display name |
| `legal_name` | Data | No | No | Informational; Company remains legal/accounting owner |
| `short_name` | Data | No | Search index | Display abbreviation, not identity key |
| `status` | Select | Yes | Index | Planned, Active, Inactive, Closed |
| `valid_from` | Date | Yes | Index | Start of institutional validity |
| `valid_to` | Date | No | Index | Must not precede start |
| `default_timezone` | Autocomplete/Data | Yes | No | Valid IANA timezone |
| `default_language` | Link: Language | No | No | Default presentation language |
| `country` | Link: Country | No | Index | Policy/reporting context, not Company ownership |
| `website` | Data | No | No | URL validation |
| `primary_address` | Link: Address | No | No | Standard address; governed deletion |
| `policy_profile_code` | Data | No | No | Deferred from Slice A until a policy-profile schema is approved |

### Rules

- `institution_code` is normalized before uniqueness checks and cannot change after insert.
- Closed/Inactive Institutions remain referenceable historically.
- Deletion is denied after any Campus, Unit, identity scope, mapping, assignment or transaction exists.
- Company is never auto-created from Institution.

## Talisma Campus

Standalone physical/operational campus scoped to exactly one Institution.

| Field | Type | Required | Index/unique | Semantics |
|---|---|---:|---|---|
| `name` | System name | Yes | PK | UUIDv4 |
| `institution` | Link: Talisma Institution | Yes | Composite index | Security root |
| `campus_code` | Data | Yes | Composite unique | Stable code within Institution |
| `campus_name` | Data | Yes | Search index | Display name |
| `campus_type` | Select | Yes | Index | Main, Satellite, Learning Center, Virtual, Other |
| `status` | Select | Yes | Index | Planned, Active, Inactive, Closed |
| `valid_from` | Date | Yes | Index | Effective start |
| `valid_to` | Date | No | Index | Effective end |
| `timezone` | Autocomplete/Data | Yes | No | Valid IANA timezone |
| `address` | Link: Address | Conditional | No | Required except approved Virtual campus |
| `parent_campus` | Link: Talisma Campus | No | Index | Physical grouping only; same Institution, acyclic |
| `is_virtual` | Check | Yes | Index | Must align with type |

Unique constraint: `(institution, normalized campus_code)`. Campus placement does not imply academic ownership.

## Talisma Academic Unit Type

Governed configuration master.

| Field | Type | Required | Semantics |
|---|---|---:|---|
| `type_code` | Data | Yes/unique | Immutable code |
| `type_name` | Data | Yes | College, School, Faculty, Department, Division, Institute, Center, Other |
| `can_grant_credentials` | Check | Yes | Capability default |
| `can_own_programs` | Check | Yes | Capability default |
| `can_own_courses` | Check | Yes | Capability default |
| `disabled` | Check | Yes | Prevent new usage; retain history |

Capabilities on a Unit may narrow but cannot broaden its type defaults without an approved exception record.

## Talisma Academic Unit

Stable academic-governance identity without a mutable parent field.

| Field | Type | Required | Index/unique | Semantics |
|---|---|---:|---|---|
| `name` | System name | Yes | PK | UUIDv4 |
| `institution` | Link: Talisma Institution | Yes | Composite index | Owning scope |
| `unit_code` | Data | Yes | Composite unique | Stable within Institution |
| `unit_name` | Data | Yes | Search index | Current display name |
| `short_name` | Data | No | Search index | Display abbreviation |
| `unit_type` | Link: Talisma Academic Unit Type | Yes | Index | Governed type |
| `status` | Select | Yes | Index | Planned, Active, Inactive, Closed, Merged |
| `valid_from` | Date | Yes | Index | Effective start |
| `valid_to` | Date | No | Index | Effective end |
| `successor_unit` | Link: Talisma Academic Unit | Conditional | Index | Same Institution; required for Merged when one successor exists |
| `can_grant_credentials` | Check | Yes | Index | Constrained by type/policy |
| `can_own_programs` | Check | Yes | Index | Constrained by type/policy |
| `can_own_courses` | Check | Yes | Index | Constrained by type/policy |

Unique constraint: `(institution, normalized unit_code)`. Name changes are audited; codes do not change. Splits and multi-successor reorganizations use a separate lineage record in a later slice.

## Talisma Structure Version

Submittable institutional hierarchy version. Submission is approval and immutability boundary.

| Field | Type | Required | Index/unique | Semantics |
|---|---|---:|---|---|
| `name` | System name | Yes | PK | UUIDv4 |
| `institution` | Link: Talisma Institution | Yes | Composite index | Scope |
| `structure_code` | Data | Yes | Composite unique | Stable version code within Institution/purpose |
| `structure_name` | Data | Yes | Search | Display title |
| `structure_purpose` | Select | Yes | Composite index | Academic Governance initially |
| `valid_from` | Date | Yes | Composite index | Activation date |
| `valid_to` | Date | No | Composite index | Retirement date |
| `supersedes` | Link: Talisma Structure Version | No | Index | Same Institution/purpose |
| `change_summary` | Small Text | Yes | No | Human review summary |
| `approval_reference` | Data | Yes | No | Governance decision reference |
| `materialization_status` | Select | Yes | Index | Pending, Building, Ready, Failed, Stale |
| `materialized_on` | Datetime | Conditional | No | Required when Ready |

### Rules

- Draft versions can change placements; submitted versions and their placements cannot.
- Submitted effective intervals cannot overlap for the same Institution/purpose.
- Submission requires complete validation and impact report.
- A submitted version cannot be cancelled after it has governed transactions or permission decisions; supersede instead.
- Version becomes usable only when materialization is Ready.

## Talisma Unit Placement

Standalone record for queryability and scale; immutable when its Structure Version is submitted.

| Field | Type | Required | Index/unique | Semantics |
|---|---|---:|---|---|
| `structure_version` | Link: Talisma Structure Version | Yes | Composite unique | Version |
| `institution` | Link: Talisma Institution | Yes | Index | Denormalized validated scope |
| `academic_unit` | Link: Talisma Academic Unit | Yes | Composite unique | Child unit |
| `parent_unit` | Link: Talisma Academic Unit | No | Index | Null for root |
| `display_order` | Int | No | No | Sibling presentation only |

Unique `(structure_version, academic_unit)`. Both units must share Institution. Self-parent and cycles are rejected. Unit validity must cover the structure interval where required by policy.

## Talisma Unit Closure

System-managed materialized transitive closure for descendant permission and reporting queries. Users cannot create/edit/delete these records directly.

| Field | Type | Required | Index/unique | Semantics |
|---|---|---:|---|---|
| `structure_version` | Link: Talisma Structure Version | Yes | Composite unique | Version |
| `institution` | Link: Talisma Institution | Yes | Composite index | Scope |
| `ancestor_unit` | Link: Talisma Academic Unit | Yes | Composite unique/index | Ancestor |
| `descendant_unit` | Link: Talisma Academic Unit | Yes | Composite unique/index | Descendant, including self |
| `depth` | Int | Yes | Index | Zero for self, positive below |
| `build_id` | Data | Yes | Index | Atomic materialization generation |

Unique `(structure_version, ancestor_unit, descendant_unit)`. Build in a transaction/staged generation; mark version Ready only after count, cycle and integrity checks. Never treat closure rows as authoritative history—the submitted placements are authoritative.

## Talisma Standard Mapping

Effective-dated mapping from Institution, Campus or Academic Unit to allowlisted ERPNext records.

| Field | Type | Required | Index/unique | Semantics |
|---|---|---:|---|---|
| `institution` | Link: Talisma Institution | Yes | Index | Security scope |
| `source_type` | Select | Yes | Composite index | Institution, Campus, Academic Unit |
| `source_name` | Dynamic Link | Yes | Composite index | Validated source |
| `target_doctype` | Link: DocType | Yes | Composite index | Company, Department, Branch, Cost Center only initially |
| `target_name` | Dynamic Link | Yes | Composite index | Existing standard target |
| `mapping_purpose` | Select | Yes | Composite index | Legal, HR, Operations, Payroll, Billing, Budget, Procurement, Reporting |
| `is_primary` | Check | Yes | Index | Singular only where purpose policy requires |
| `valid_from` | Date | Yes | Index | Effective start |
| `valid_to` | Date | No | Index | Effective end |
| `status` | Select | Yes | Index | Draft, Active, Inactive, Disputed |
| `source_reference` | Data | Yes | No | Provenance/approval reference |

Validation checks target Company consistency for Department/Cost Center and prevents overlapping primary mappings where policy requires one.

## Talisma Academic Ownership

Effective ownership of allowlisted academic objects.

| Field | Type | Required | Index/unique | Semantics |
|---|---|---:|---|---|
| `institution` | Link: Talisma Institution | Yes | Index | Scope |
| `target_doctype` | Link: DocType | Yes | Composite index | Allowlisted Program, Course, Curriculum or future master |
| `target_name` | Dynamic Link | Yes | Composite index | Owned record |
| `academic_unit` | Link: Talisma Academic Unit | Yes | Index | Owner |
| `ownership_role` | Select | Yes | Index | Primary, Joint, Administrative, Curriculum, Delivery |
| `campus` | Link: Talisma Campus | No | Index | Delivery/context only |
| `structure_version` | Link: Talisma Structure Version | Yes | Index | Historical hierarchy context |
| `valid_from` | Date | Yes | Composite index | Effective start |
| `valid_to` | Date | No | Composite index | Effective end |
| `allocation_percent` | Percent | No | No | Only where approved meaning exists |
| `approval_reference` | Data | Yes | No | Governance evidence |
| `status` | Select | Yes | Index | Draft, Active, Inactive, Disputed |

Exactly one effective Primary owner per target when required. Joint percentages are optional unless policy explicitly requires totals.

## Talisma Scope Grant

Effective organizational scope assigned to a User for server-side authorization.

| Field | Type | Required | Index/unique | Semantics |
|---|---|---:|---|---|
| `user` | Link: User | Yes | Composite index | Actor |
| `institution` | Link: Talisma Institution | Yes | Composite index | Mandatory boundary |
| `academic_unit` | Link: Talisma Academic Unit | No | Index | Optional narrower root |
| `structure_version` | Link: Talisma Structure Version | Conditional | Index | Required for unit descendant scope |
| `include_descendants` | Check | Yes | Index | Uses closure table |
| `scope_purpose` | Link/controlled value | Yes | Index | Registrar, advising, reporting, administration, etc. |
| `valid_from` | Datetime | Yes | Index | Effective start |
| `valid_to` | Datetime | No | Index | Expiry |
| `status` | Select | Yes | Index | Pending, Active, Revoked, Expired |
| `approval_reference` | Data | Yes | No | Authorization evidence |

This supplements rather than replaces Frappe roles. A generic role without an effective Scope Grant confers no institutional data scope.

## Deferred records

- Unit Name History.
- Unit Lineage for merge/split many-to-many predecessor/successor relationships.
- Responsibility Assignment linked to approved Person/Employee/User actors.
- External Organization Identifier.
- Building/facility hierarchy.
- Structure impact/reconciliation case.

## Deletion and rename policy

- UUID names cannot be renamed.
- Institution, Campus and Academic Unit use restrictive deletion after reference.
- Codes cannot change or be reused.
- Submitted Structure Versions, Placements and their authoritative audit are immutable.
- Closure rows may be atomically rebuilt from submitted placements.
- Mapping/ownership/grant records are ended or revoked, not deleted after use.

## Minimal implementation slices

### Slice A: institutional scope foundation

1. Talisma Institution only.
2. Minimal institution-scoped permission tests.
3. No identity Link-field migration until dependency installation order and rollback are tested.

### Slice B: current academic structure

1. Campus, Academic Unit Type and Academic Unit.
2. Structure Version and Unit Placement.
3. Unit Closure materialization.
4. Scope Grant and permission-query enforcement.

### Slice C: integrations

1. Standard Mapping.
2. Academic Ownership.
3. Optional Education adapters only after ADR-001 acceptance.

Reorganization automation, lineage, responsibility assignments and production migration remain excluded until later approval.
