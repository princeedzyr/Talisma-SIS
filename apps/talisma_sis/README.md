# Talisma SIS

Talisma SIS is a commercial Student Information System for higher-education institutions, built as an upgrade-safe Frappe application on ERPNext v16. It will provide a coherent academic platform spanning the student lifecycle from admission through graduation while integrating with ERPNext services where they are authoritative.

## Current status

The application is at its foundation stage. The approved `Talisma Institution` scope root and its Manager/Viewer roles are implemented; Campus and all other business domains remain design-only. No workflows, reports, APIs, portals, or user interfaces have been implemented.

## Architecture principles

- Keep Frappe and ERPNext core unmodified.
- Prefer standard extension points: hooks, custom applications, DocType extensions, workflows, permissions, fixtures, and versioned patches.
- Treat student records as sensitive institutional data and design access around least privilege and FERPA-aligned controls.
- Reuse ERPNext and Frappe Education capabilities only after confirming ownership, lifecycle, and upgrade compatibility.
- Keep domain modules cohesive and integrations explicit.
- Make every schema and data migration repeatable through `bench migrate`.

See [Project Vision](docs/PROJECT_VISION.md), [Architecture](docs/ARCHITECTURE.md), [Architecture Decisions](docs/architecture/ADR_INDEX.md), [Target Architecture](docs/architecture/SYSTEM_ARCHITECTURE.md), [Identity Model](docs/architecture/IDENTITY_AND_PARTY_MODEL.md), [Identity Approval Package](docs/architecture/ADR-002-APPROVAL-PACKAGE.md), [ADR-002 Acceptance Record](docs/architecture/ADR-002-ACCEPTANCE-RECORD.md), [Identity Schema Review](docs/architecture/IDENTITY_SCHEMA_REVIEW_GATE.md), [Institutional Hierarchy Review](docs/architecture/ADR-003-APPROVAL-PACKAGE.md), [ADR-003 Acceptance Record](docs/architecture/ADR-003-ACCEPTANCE-RECORD.md), [Institutional Schema Review](docs/architecture/INSTITUTIONAL_SCHEMA_REVIEW_GATE.md), [Institutional Slice A Approval](docs/architecture/INSTITUTIONAL_SCHEMA_SLICE_A_APPROVAL.md), [Campus Slice B1 Proposal](docs/architecture/INSTITUTIONAL_SCHEMA_SLICE_B1_CAMPUS_PROPOSAL.md), [Campus Slice B1 Acceptance](docs/architecture/INSTITUTIONAL_SCHEMA_SLICE_B1_CAMPUS_ACCEPTANCE.md), [Academic Unit Slice B2 Proposal](docs/architecture/INSTITUTIONAL_SCHEMA_SLICE_B2_ACADEMIC_UNIT_PROPOSAL.md), [Academic Unit Slice B2 Acceptance](docs/architecture/INSTITUTIONAL_SCHEMA_SLICE_B2_ACADEMIC_UNIT_ACCEPTANCE.md), [Roadmap](docs/ROADMAP.md), [Modules](docs/MODULES.md), and [Coding Standards](docs/CODING_STANDARDS.md).

## Development environment

The repository builds a local `talisma-sis:dev` image from the pinned ERPNext v16.26.2 base. After changing application source, rebuild the image and recreate the Frappe services using the project Docker Compose configuration.

Run site operations from the backend service:

```bash
bench --site talisma.local migrate
bench --site talisma.local list-apps
```

The development site is available at `http://talisma.local:8081`.

## Quality expectations

All functional changes should include appropriate automated tests, migration considerations, permission analysis, and documentation. Run the generated pre-commit checks before committing application code.

## License

MIT
