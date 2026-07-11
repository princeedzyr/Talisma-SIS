# Coding Standards

## General principles

- Follow existing Frappe v16 patterns before introducing new abstractions.
- Keep changes small, cohesive, reviewable, and tied to a defined product capability.
- Do not modify Frappe or ERPNext core.
- Avoid dependencies unless their operational and upgrade costs are justified.
- Prefer explicit domain names over generic helpers and unexplained abbreviations.

## Python

- Follow the generated Ruff configuration and Frappe's tab-indentation convention.
- Keep document controllers focused on document invariants and lifecycle behavior.
- Place cross-document orchestration in a clearly named service only when it cannot remain local.
- Use Frappe ORM and query builder APIs; avoid raw SQL unless measured need and safe parameterization are documented.
- Use `frappe.throw` with translatable user-facing messages for expected validation failures.
- Do not catch broad exceptions unless adding context and preserving failure semantics.
- Avoid hidden commits, direct database writes, and side effects during validation.

## JavaScript and user interfaces

- Follow generated ESLint and Prettier configuration.
- Treat client scripts as interaction aids, not security or authoritative validation.
- Keep business rules on the server and reuse APIs rather than duplicating logic in forms.
- Support keyboard navigation, accessible labels, meaningful errors, and responsive layouts.
- Do not introduce global browser state when Frappe page or form state is sufficient.

## DocTypes and metadata

- Define ownership, naming, lifecycle, permissions, indexes, and retention before creating a DocType.
- Prefer Link fields and explicit child tables over duplicated text snapshots unless history requires a snapshot.
- Use Select only for genuinely stable enumerations; use reference DocTypes for governed institutional values.
- Make submitted or immutable records intentional and document amendment behavior.
- Avoid destructive field renames or type changes; use migration-safe transitions and patches.
- Do not use Customize Form as the sole source of production metadata. Version application-owned customizations.

## APIs

- Expose the smallest necessary surface and version externally consumed contracts.
- Validate authentication, authorization, input shape, record state, and idempotency server-side.
- Return stable, documented response structures rather than raw internal documents by default.
- Never expose credentials, internal tracebacks, unrestricted queries, or unnecessary student data.
- Use background jobs for operations that can exceed normal request duration.

## Permissions and privacy

- Apply least privilege and test both allowed and denied cases.
- Use role permissions, user permissions, permission-query conditions, and document-level checks as appropriate.
- Never rely on hidden fields, client logic, or report filters as authorization.
- Treat student records, advising notes, grades, financial aid, and disciplinary information as sensitive.
- Avoid personal data in logs, filenames, cache keys, and integration diagnostics.

## Tests

- Add tests with every functional change.
- Cover document invariants, lifecycle transitions, permissions, failure paths, migrations, and integration boundaries.
- Make tests deterministic and independent; do not depend on execution order or uncontrolled global records.
- Use factories or focused fixtures rather than large opaque datasets.
- Include regression coverage for every corrected defect.

## Migrations

- Keep DocType metadata in source control.
- Register data migrations in `patches.txt` under the correct phase.
- Make patches idempotent or safely resumable and suitable for large datasets.
- Never assume a migration runs only once without checking existing state.
- Test installation on an empty site and migration from the previous supported release.

## Documentation

- Update architecture or module documentation when ownership or boundaries change.
- Document public APIs, configuration, operational procedures, and irreversible decisions.
- Record significant architectural choices before implementation.
- Comments should explain intent or constraints, not restate code.

## Review checklist

- Is this capability owned by Talisma SIS rather than an existing standard module?
- Is core modification avoided?
- Are permissions and privacy enforced on the server?
- Is the schema migration-safe and indexed appropriately?
- Are tests and documentation proportional to risk?
- Will all Docker services receive the same application code?
- Can the change survive a Frappe/ERPNext v16 upgrade?
