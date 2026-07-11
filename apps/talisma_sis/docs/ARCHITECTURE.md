# Technical Architecture

> This document defines enduring engineering principles. The proposed product architecture is detailed in [Talisma SIS Target Architecture](architecture/SYSTEM_ARCHITECTURE.md), with the [reuse strategy](architecture/ERPNEXT_REUSE_STRATEGY.md), [module dependency map](architecture/MODULE_DEPENDENCIES.md), [module catalog](modules/MODULE_ARCHITECTURE.md), and [Architecture Decision Records](architecture/ADR_INDEX.md). These documents require approval before implementation.

## Architectural position

Talisma SIS is a first-class Frappe application deployed alongside ERPNext. Frappe provides the metadata platform, persistence model, permissions, background jobs, APIs, workflows, and user-interface framework. ERPNext provides reusable enterprise services such as accounting where those services remain authoritative. Frappe Education capabilities must be inventoried and compatibility-tested before Talisma extends or depends on them.

Talisma-owned academic behavior belongs in `talisma_sis`; it must not be implemented by patching framework or ERPNext source.

## Logical layers

1. **Experience layer**
   - Desk workspaces and operational views
   - Student and faculty portal experiences
   - Reports, dashboards, notifications, and print formats

2. **Application layer**
   - Frappe document controllers and services
   - Workflows, validations, orchestration, and background jobs
   - Whitelisted APIs with explicit contracts

3. **Domain layer**
   - Admissions, student records, curriculum, registration, advising, assessment, progression, finance, and graduation rules
   - Shared academic policies represented once and consumed across modules

4. **Platform and integration layer**
   - Frappe ORM, permissions, audit trail, jobs, caching, and events
   - ERPNext financial and organizational services
   - Versioned integrations with identity, learning, payment, and reporting systems

5. **Data layer**
   - MariaDB records managed through Frappe DocTypes
   - Site files and private attachments
   - Redis-backed caching, queues, and realtime services

## Extension strategy

Use the least invasive supported mechanism:

1. Configure an existing standard capability when it owns the required lifecycle.
2. Extend standard DocTypes with supported hooks or custom fields owned by this app.
3. Add a Talisma DocType when the concept has distinct identity, rules, permissions, or retention requirements.
4. Add a service or API only when orchestration cannot remain in a document controller.
5. Override framework behavior only with a documented compatibility reason and regression coverage.

Core source modifications are prohibited.

## Proposed application organization

Frappe-generated DocTypes should remain in their module package. Cross-DocType behavior should be placed in clearly named packages as it becomes necessary:

```text
talisma_sis/
├── api/             # Versioned external and portal API contracts
├── integrations/    # Adapters for external systems
├── permissions/     # Reusable permission-query and record-access policies
├── services/        # Cross-DocType application orchestration
├── utils/           # Small domain-neutral helpers only
└── talisma_sis/     # Frappe module containing generated metadata and controllers
```

These packages should be created only when the first concrete implementation needs them. Empty speculative Python packages are intentionally not part of this foundation.

## Data ownership

Every proposed record must identify:

- its authoritative system and business owner;
- natural and integration identifiers;
- lifecycle and allowed state transitions;
- validation and concurrency rules;
- access, privacy, and retention requirements;
- audit expectations; and
- relationships to existing Frappe, ERPNext, or Education records.

Avoid duplicating person, organization, financial, or academic concepts without an explicit ownership decision.

## Security architecture

- Deny access by default and grant through narrowly scoped roles and user permissions.
- Separate administrative access from faculty, advisor, student, and integration access.
- Apply permissions at query and document level; hiding interface elements is not authorization.
- Keep sensitive documents and attachments private.
- Avoid logging educational records, credentials, tokens, or unnecessary personal data.
- Record consequential academic and administrative decisions through Frappe audit mechanisms.
- Review permission changes as security-sensitive migrations.

## Integration architecture

Integrations should use stable, versioned contracts and idempotent operations. External identifiers must be stored explicitly. Long-running work belongs in background jobs with retry and observability. Direct database access by external systems is not supported.

## Migration and compatibility

- Schema changes must be represented by version-controlled DocType JSON and, where required, ordered patches.
- Patches must be idempotent or safely resumable.
- Install, migrate, backup, restore, and upgrade paths must be tested.
- Dependencies and supported versions must be explicit.
- Compatibility with the pinned Frappe and ERPNext v16 images must be verified before release.

## Scalability approach

Prefer indexed, permission-aware queries; bounded background work; pagination; and asynchronous bulk processing. Measure before denormalizing. Reporting workloads that outgrow transactional queries should move through governed replication or analytics pipelines rather than weakening the SIS data model.
