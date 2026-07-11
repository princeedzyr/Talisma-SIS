# Institutional Schema Slice A Approval Record

- **Architecture:** Accepted ADR-003 Institutional Hierarchy
- **Schema:** [Institutional Physical Schema Proposal](INSTITUTIONAL_PHYSICAL_SCHEMA_PROPOSAL.md)
- **Outcome:** Slice A approved; all later slices remain unapproved
- **Approval date:** 2026-07-11
- **Approver:** Prince Ebinezer, Project Owner
- **Authorized scope:** Talisma Institution foundation only

## Authorized DocType

One new standard DocType in the `talisma_sis` app:

- **DocType:** `Talisma Institution`
- **Module:** `Talisma SIS`
- **Naming:** server-generated UUIDv4 stored in `name`
- **Submittable:** No
- **Rename:** Disabled after creation
- **Track changes:** Enabled
- **Quick entry:** Disabled initially
- **Allow import:** Disabled initially

## Authorized fields

| Field | Type | Required | Constraint |
|---|---|---:|---|
| `institution_code` | Data | Yes | Uppercase normalized, globally unique, immutable after insert |
| `institution_name` | Data | Yes | Searchable display name |
| `legal_name` | Data | No | Informational only; ERPNext Company remains legal/accounting authority |
| `short_name` | Data | No | Searchable display abbreviation |
| `status` | Select | Yes | Planned, Active, Inactive, Closed; default Planned |
| `valid_from` | Date | Yes | Must be on/before `valid_to` |
| `valid_to` | Date | No | Open-ended when blank |
| `default_timezone` | Autocomplete | Yes | Validate against available IANA/Frappe timezones |
| `default_language` | Link: Language | No | Standard Frappe master |
| `country` | Link: Country | No | Standard Frappe master |
| `website` | Data | No | URL validation |
| `primary_address` | Link: Address | No | Restrict deletion/clear safely; does not transfer address ownership |

`policy_profile_code` from the broader proposal is explicitly deferred until a policy-profile schema exists. No hidden fields, custom fields on core records or child tables are authorized.

## Authorized validation

- Generate UUIDv4 server-side; reject user-supplied naming overrides through normal application flow.
- Normalize code by trimming and uppercasing before validation.
- Permit code characters `A-Z`, `0-9`, hyphen and underscore only; length 2–32.
- Enforce database uniqueness on `institution_code` and provide a clear duplicate error.
- Prevent `institution_code` changes after insert.
- Require `valid_to >= valid_from` when present.
- Validate timezone through framework-supported timezone data.
- Prevent deletion after any reference exists; before dependent schemas exist, normal Frappe link protection plus explicit tests are sufficient.
- Track status, name, date, locale and address changes through framework versioning.

No automatic lifecycle jobs, mapping, synchronization, events, API endpoints or migration are authorized in Slice A.

## Authorized permissions

Two app-owned roles may be created because the DocType cannot be safely delivered without explicit access:

| Role | Access |
|---|---|
| `Talisma Institution Manager` | Create, read, write; delete only while unreferenced; no import/export by default |
| `Talisma Institution Viewer` | Read only |

`System Manager` may receive administrative access for development and recovery, but this does not establish future cross-institution business-data access. Guest, student, applicant, guardian and ordinary Desk users receive no access.

## Required implementation tests

1. App installs and migrates on `talisma.local` without Education.
2. UUID names are generated and immutable.
3. Code normalization and allowed-character rules pass.
4. Duplicate codes fail, including concurrent creation attempts.
5. Date interval validation passes/fails correctly.
6. Invalid timezone and website values fail clearly.
7. Manager, Viewer and unauthorized-user permissions behave as specified.
8. Change tracking records authorized edits without exposing secrets.
9. Unreferenced deletion succeeds; static Link deletion protection is verified with the first authorized dependent DocType rather than a non-blocking generic reference.
10. Repeated `bench migrate` is idempotent.
11. Backup succeeds after schema installation.
12. Uninstall/dependency behavior is documented and tested in an isolated site before production use.

## Explicit exclusions

Not authorized:

- Campus or Academic Unit records;
- Unit Type, Structure Version, Placement or Closure records;
- Scope Grant or descendant permission logic;
- Company, Department, Branch or Cost Center mappings;
- Program/Course ownership;
- identity DocTypes or identity migration;
- institutional data migration or seed institutions;
- custom fields on ERPNext/Frappe/Education records;
- APIs, portal pages, workspaces, reports or integrations;
- Education installation or dependency changes;
- Docker or compose changes.

## Implementation change control

Implementation must occur on a new feature branch and match this record exactly. Any additional field, role, DocType, hook, API, migration, fixture or core customization requires renewed approval. Completion requires code review, tests, `bench migrate`, permission verification and documentation of created files.
