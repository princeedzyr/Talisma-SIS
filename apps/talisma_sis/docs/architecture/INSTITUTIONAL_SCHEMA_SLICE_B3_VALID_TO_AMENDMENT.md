# Institution Slice B3 Amendment: Bounded Submitted Structure Versions

- **Amends:** [Slice B3 Acceptance Record](INSTITUTIONAL_SCHEMA_SLICE_B3_STRUCTURE_ACCEPTANCE.md)
- **Related proposal:** [Slice B3 Structure Proposal](INSTITUTIONAL_SCHEMA_SLICE_B3_STRUCTURE_PROPOSAL.md)
- **Outcome:** Accepted
- **Approval date:** 2026-07-11
- **Approver:** Prince Ebinezer, Project Owner
- **Scope:** `valid_to` requirement for `Talisma Structure Version` submission

## Problem discovered during implementation review

The accepted B3 design simultaneously allowed a submitted Structure Version to have no `valid_to`, prohibited overlapping submitted versions, required submitted versions to remain immutable, and expected later versions to supersede earlier versions.

Those rules are incompatible. An immutable open-ended submitted interval can never stop overlapping a successor. Implementing the design unchanged would either make succession impossible or require an undocumented mutation of approved history.

## Amended decision

1. `valid_to` remains optional while a Structure Version is Draft.
2. `valid_to` is mandatory before submission.
3. A submitted interval is always half-open and bounded: `[valid_from, valid_to)`.
4. `valid_to` must be strictly later than `valid_from`.
5. A successor may start exactly at its predecessor's `valid_to`.
6. Submitted dates remain immutable; ordinary end-dating after submission is prohibited.
7. Submitted intervals for the same Institution and purpose remain non-overlapping.
8. Supersession does not implicitly rewrite or truncate the predecessor interval.

## Consequences

### Positive

- Every submitted version has deterministic historical bounds.
- Successor versions can be planned without mutating approved records.
- Overlap validation remains direct and auditable.
- Concurrency behavior does not depend on derived or implicit end dates.

### Trade-off

Governance must choose an intended end date before submission. If the future transition date is uncertain, the version must remain Draft or use a governed bounded planning horizon. Changing the boundary after submission requires a correction/superseding governance process that is outside B3.

## Required implementation changes

- Metadata may present `valid_to` as conditionally mandatory for submission.
- Server-side `before_submit` validation must reject a blank `valid_to`.
- Tests must cover blank Draft dates, rejected blank submission, strictly positive intervals, adjacent successor intervals, overlap rejection, and submitted-date immutability.
- Documentation and user-facing errors must distinguish Draft optionality from submission requirements.

## Unchanged boundaries

All other B3 acceptance terms remain unchanged. This amendment does not authorize Closure, materialization, activation, Scope Grant, mappings, ownership, APIs, workflows, data migration, Docker changes, or Frappe/ERPNext core modifications.

## Implementation change control

Implementation may resume only after this amendment is reviewed and merged into `develop`. The B3 feature branch must then be recreated or rebased from the amended baseline before code is added.
