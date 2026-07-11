# ADR-001: Frappe Education Dependency Strategy

- **Status:** Proposed
- **Date:** 2026-07-11
- **Decision owners:** Product Architecture, Engineering, Legal and Product Management
- **Supersedes:** None

## Context

ERPNext v16.26.2 no longer contains the historical Education module. The official `frappe/education` application is maintained separately. Its `version-16` branch declares compatibility with Frappe v16, requires ERPNext, and contains useful education records and services including Student, Guardian, Instructor, Program, Course, Academic Year, Academic Term, admissions, enrollments, attendance, assessments, fees, a workspace, reports, and a student portal.

Talisma SIS needs many of these concepts, but its target market is higher education. The Education models are substantially school-oriented and do not provide complete higher-education curriculum versioning, section registration, academic-attempt history, repeat/transfer policy, degree audit, official transcript, graduation, or financial aid capabilities.

The current Talisma site does not have the Education app installed. Talisma is currently declared MIT, while Frappe Education is GPL-3.0. Commercial distribution and combined-work licensing obligations require qualified legal review.

## Decision drivers

- Avoid rebuilding mature upstream capabilities without product value.
- Preserve upgradeability and avoid upstream source forks.
- Support the complete higher-education lifecycle and historical academic integrity.
- Maintain predictable dependency, migration, and release behavior.
- Understand commercial licensing obligations before distribution.
- Prevent upstream implementation details from becoming Talisma public contracts.

## Options considered

### Option A — Adopt Frappe Education as a required upstream dependency

Use a pinned v16 release and extend its suitable DocTypes through Talisma hooks, related records, services, permissions, and adapters.

**Advantages**

- Reuses existing student, program, course, attendance, assessment, fee, portal, and reporting foundations.
- Reduces initial schema and workflow duplication.
- Follows the upstream separation established for ERPNext v16.

**Disadvantages**

- Adds release, compatibility, migration, and licensing dependencies.
- Requires careful separation between school-oriented upstream behavior and higher-education Talisma behavior.
- Upstream DocType semantics may constrain future design.

### Option B — Build all academic foundations inside Talisma SIS

Do not install Education; create Talisma-owned equivalents for all academic records.

**Advantages**

- Full control over schema, lifecycle, release schedule, and product semantics.
- Avoids behavioral dependency on school-oriented models.

**Disadvantages**

- Duplicates a large upstream feature surface.
- Increases implementation scope, migration burden, testing cost, and time to product value.
- Risks recreating standard concepts inconsistently.

### Option C — Optional compatibility adapter

Keep Talisma independent and provide optional integration with Education installations.

**Advantages**

- Reduces mandatory dependency coupling.
- Supports institutions already using Education.

**Disadvantages**

- Requires two supported operating modes and mapping between competing academic masters.
- Significantly increases test and support complexity.
- Does not reduce initial Talisma schema scope.

## Proposed decision

Adopt **Option A conditionally**: Frappe Education v16 should become a required, pinned upstream dependency if and only if it passes the approval gates below.

Talisma will:

1. Reuse stable upstream identities and simple masters where their semantics fit.
2. Extend upstream behavior only through supported Frappe mechanisms.
3. Build Talisma-owned higher-education records for curriculum versions, offerings, registration transactions, gradebook, academic attempts, transcripts, degree audit, graduation, aid, portals, and integration contracts.
4. Place upstream API calls behind Talisma-owned adapters and never expose Education methods as Talisma's external API contract.
5. Pin a tested release or immutable commit; never build production images from a moving branch.
6. Avoid modifying or maintaining a fork of Frappe Education unless a separately approved ADR documents an exceptional need.

This proposal does not authorize installation yet.

## Approval gates

Before changing the custom image or installing Education:

- Legal approves GPL-3.0 implications for the intended commercial model.
- Engineering pins a specific release compatible with the exact Frappe and ERPNext versions.
- A field-level fit-gap review is completed for every proposed reused DocType.
- Fresh install, existing-site install, migrate, backup, restore, and rollback scenarios pass.
- Portal, workspace, permissions, and background jobs pass Frappe v16 compatibility tests.
- Ownership boundaries between Education and Talisma records are approved.
- The dependency is documented in build, release, and disaster-recovery procedures.

If any blocking gate fails, Architecture must reconsider Option B or C rather than silently forking upstream.

## Consequences

### Positive

- Talisma focuses engineering effort on differentiated higher-education capabilities.
- Standard academic identities remain compatible with the upstream Frappe ecosystem.
- Existing Education reports and tools can support early administrative use where appropriate.

### Negative

- Every Talisma release must include an Education compatibility check.
- Upstream migrations and schema changes become product release inputs.
- Licensing and attribution requirements become part of release governance.
- Some upstream screens may coexist with Talisma experiences and require clear user guidance.

## Validation plan

1. Build a disposable image containing a pinned Education v16 release.
2. Install it on a disposable copy or new test site, not the current development site first.
3. Inventory schema, fixtures, roles, workspaces, patches, APIs, reports, and accounting behavior.
4. Execute compatibility and migration tests.
5. Produce a fit-gap matrix and legal decision record.
6. Change this ADR to Accepted, Rejected, or Superseded.

## References

- <https://github.com/frappe/education>
- <https://github.com/frappe/education/tree/version-16>
- <https://github.com/frappe/education/blob/version-16/education/hooks.py>
- <https://github.com/frappe/education/blob/version-16/pyproject.toml>
- [Talisma reuse strategy](ERPNEXT_REUSE_STRATEGY.md)
