# ADR-004: Bryan University Next Baseline

Status: **Accepted**  
Date: **2026-07-15**

## Context

The existing Bryan University client demo is a valuable comparison and sales
environment. Product development must not alter its database, files, port,
containers, volumes, image tag, or runtime behavior. The approved master
blueprint also requires an exact Frappe, ERPNext, and Education v16 dependency
tuple before durable SIS records are introduced.

The repository currently contains an untracked Education source tree reporting
`17.0.0-dev`; it is not an approved source for the Frappe v16 product line.

## Decision

1. Keep the existing demo frozen as Compose project `talisma-demo`, site
   `demo.talisma.local`, port `8082`, and image `talisma-sis:demo`.
2. Build the proper system only as Compose project `bryan-next`, site
   `next.bryan.local`, port `8083`, and a dedicated Next image tag.
3. Support exactly this initial application tuple:
   - Frappe Framework `16.25.0`
   - ERPNext `16.26.2`, commit `d1d3b241ae7bc21d18cf830a4bacd568e21a2a19`
   - Frappe Education `16.0.1`, commit `ab3794da21dfd145825293319f89c746811a15cd`
4. Enforce the tuple during Talisma SIS installation and migration.
5. Build ERPNext and Education from remote pinned commits. Never copy the local
   `apps/education` working tree into a Next image.
6. Preserve independent MariaDB, Redis, sites, and network resources for the two
   environments.
7. Use synthetic data until a separately approved migration and security plan
   authorizes other data.

## Consequences

- An upstream version change requires an explicit ADR amendment, compatibility
  evidence, migration rehearsal, and rollback checkpoint.
- Next can evolve without changing the frozen demo.
- Branch names remain useful discovery metadata, but commit hashes are the
  reproducible build authority.
- GPL-3.0 and commercial-distribution review remains a release-governance gate;
  this technical decision does not replace qualified legal review.

## Verification

- Image build fails when either dependency cannot be checked out at the approved
  commit.
- Application installation and migration fail on any unsupported version tuple.
- Both ports return independent health responses.
- Installed application versions and volume names are recorded in release
  evidence.
