# Institution Slice B4: Unit Closure Implementation

- **Architecture authority:** [B4 Acceptance Record](../architecture/INSTITUTIONAL_SCHEMA_SLICE_B4_CLOSURE_ACCEPTANCE.md)
- **Status:** Implemented within the accepted scope

## Delivered

- `Talisma Closure Build` records deterministic materialization attempts and integrity evidence.
- `Talisma Unit Closure` stores immutable, generation-scoped transitive paths derived from submitted B3 Placements.
- The internal synchronous service builds, verifies, queries and explicitly rebuilds closure generations.
- MariaDB advisory and Structure row locking serialize competing builds.
- Savepoint recovery removes partial derived rows while retaining sanitized Failed build evidence.
- Composite indexes support ancestor and descendant set queries.
- Migration verification repaired the accepted B3 single-successor uniqueness on upgraded sites and declared it in DocType metadata so later schema synchronization retains it.

## Operation

The service is internal Python code and is not whitelisted. B3 submission remains side-effect free. An authorized future operational entry point may invoke `talisma_sis.closure.build_closure` only after the separately approved exposure and authorization design exists.

## Exclusions preserved

No activation/current pointer, automatic job, retry scheduler, cache, Scope Grant, permission hook, mapping, ownership, public API, page, report, workspace, fixture, seed data, Docker change or core modification is included.
