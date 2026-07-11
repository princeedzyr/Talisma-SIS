# Institution Slice B3: Structure Version and Unit Placement

## Status

Implemented from the accepted B3 architecture and its bounded-validity amendment.

## Delivered scope

- `Talisma Structure Version` is a governed, submittable snapshot for one Institution and purpose.
- `Talisma Unit Placement` assigns each Academic Unit at most once in a snapshot and optionally identifies its parent.
- Draft snapshots may omit `valid_to`; submission requires a bounded half-open interval `[valid_from, valid_to)`.
- Submission validates Institution and Unit validity, interval overlap, supersession, parent completeness, cycles, and the 32-level depth limit.
- Submission is serialized per Institution and purpose using a MariaDB advisory lock plus an Institution row lock.
- Submitted snapshots and their placements are immutable and cannot be cancelled.
- Database unique constraints protect scoped structure codes, single-successor lineage, and one placement per Unit per version.

## Permissions

- `Talisma Institution Manager`: maintain Draft versions and placements; cannot submit.
- `Talisma Academic Structure Approver`: review and submit versions; cannot maintain placements.
- `Talisma Institution Viewer`: read-only access.
- `System Manager`: administrative maintenance and submission; submitted cancellation remains prohibited by domain validation.

## Explicit exclusions

This slice does not implement activation, active pointers, transitive closure or materialized paths, scope grants, ERPNext mappings, APIs, workspaces, reports, workflows, scheduled jobs, or seed data.

## Verification

Run migration twice to prove idempotency, then run the app test suite:

```text
bench --site talisma.local migrate
bench --site talisma.local migrate
bench --site talisma.local run-tests --app talisma_sis
```

Verify that the three B3 unique constraints exist in `information_schema.TABLE_CONSTRAINTS`, and confirm no B3-excluded DocTypes or fields were introduced.
