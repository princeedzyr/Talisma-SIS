# Architecture-Led Development Roadmap

Status: **Proposed; implementation begins only after architecture approval**

The sequence minimizes rework by establishing authoritative identities, effective-dated academic structures, and permissions before transactional modules.

## Gate 0 — Architecture and dependency decisions

1. Approve the target architecture and module ownership.
2. Decide whether Frappe Education v16 is mandatory or optional.
3. Complete GPL-3.0/commercial distribution review.
4. Pin and compatibility-test exact Frappe, ERPNext, and Education releases.
5. Approve identity/party, institutional hierarchy, academic calendar, and FERPA models.
6. Record decisions as ADRs.

**Exit criterion:** dependency strategy and foundational domain boundaries are signed off.

## Phase 1 — Shared administration and institutional foundations

1. Administration
2. Departments
3. Academic Programs
4. Course Catalog
5. Student Information foundation
6. Faculty Management foundation

**Why first:** every downstream transaction requires stable institutions, terms, people, programs, courses, and permissions.

## Phase 2 — Admissions vertical slice

1. Admission cycles and program availability
2. Applicant identity and duplicate prevention
3. Requirements, review, decisions, and offers
4. Applicant portal slice
5. Controlled applicant-to-student conversion

**Exit criterion:** one applicant can move through a fully audited admission process into a valid student/program relationship.

## Phase 3 — Curriculum and offering foundations

1. Curriculum Management
2. Course versioning and requisites
3. Course Offering
4. Faculty teaching assignments
5. Scheduling and capacity

**Exit criterion:** an approved curriculum and term offering can be reproduced historically.

## Phase 4 — Enrollment and registration

1. Registration periods and appointments
2. Eligibility, prerequisite, hold, conflict, and capacity checks
3. Add/drop/swap/withdraw transactions
4. Waitlists, overrides, census, and audit
5. Student and faculty portal registration/roster slices

**Exit criterion:** every registration outcome is deterministic, authorized, and auditable.

## Phase 5 — Attendance, assessments, and gradebook

1. Student Attendance
2. Assessments
3. Gradebook
4. Final-grade approval and publication
5. LMS integration contract

**Exit criterion:** finalized grades are reproducible from controlled inputs and policy versions.

## Phase 6 — Academic record, audit, and graduation

1. Transcript Management
2. Degree Audit
3. Academic advising and exceptions
4. Graduation
5. Official document and credential integrations

**Exit criterion:** academic history, progress, and conferral are authoritative and explainable.

## Phase 7 — Student finance and aid

1. Student Finance event and posting model
2. Tuition/fee assessment and student account
3. Payments, sponsorship, waivers, refunds, and holds
4. Scholarships & Financial Aid
5. Reconciliation and finance portal slices

This phase may begin earlier in parallel after Enrollment reaches stable contracts, but ERPNext Accounts ownership cannot be compromised.

## Phase 8 — Complete experiences, analytics, and integrations

1. Student Portal completion
2. Faculty Portal completion
3. Reports & Analytics
4. Priority enterprise integrations
5. Accessibility, localization, performance, retention, disaster recovery, and compliance hardening

## Cross-cutting work in every phase

- FERPA permission and privacy threat modeling
- migration and rollback planning
- automated tests and compatibility tests
- data-quality controls and observability
- API and event contract documentation
- performance measurement
- operational and user documentation

## Definition of done

A module is not complete until its ownership, lifecycle, permissions, migrations, tests, reports, operational procedures, audit behavior, and integration contracts are approved and verified.

## Architecture documents

- [Architecture Decision Records](architecture/ADR_INDEX.md)
- [Target Architecture](architecture/SYSTEM_ARCHITECTURE.md)
- [ERPNext and Education Reuse Strategy](architecture/ERPNEXT_REUSE_STRATEGY.md)
- [Module Dependency Map](architecture/MODULE_DEPENDENCIES.md)
- [Detailed Module Architecture](modules/MODULE_ARCHITECTURE.md)
