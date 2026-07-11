# Identity Standard DocType Fit-Gap

Status: **Proposed for physical-schema approval**

Evidence source: metadata inspected from the project's Frappe/ERPNext v16 images and the isolated Frappe Education v16.0.1 evaluation image on 2026-07-11. This analysis does not install Education or modify any DocType.

## Decision summary

| Standard record | Reuse | Do not use as | Talisma integration |
|---|---|---|---|
| `User` | Authentication, sessions, roles, account status | Canonical person or authoritative legal identity | Explicit optional role link; IdP subject stored separately |
| `Contact` | Communication channels and dynamic party links | Canonical person, identity evidence, or authorization | Governed association with purpose, effective dates, verification and disclosure class |
| `Address` | Postal address structure and party links | Person master or complete address history | Governed association with purpose and effective dates |
| `Employee` | Employment status, company, HR attributes, employee number | Cross-role person | Explicit role link; HR retains field ownership |
| `Customer` | Billing party, accounts and receivables | Natural-person identity | Explicit role link only when finance creates a customer |
| Education `Student Applicant` | Application participant and status | Durable canonical person | Optional role link; resolve identity before applicant-to-student conversion |
| Education `Student` | Academic student profile and Education workflows | Cross-role person or durable contact master | Optional role link; email uniqueness must not drive person matching |
| Education `Instructor` | Teaching profile linked optionally to Employee | Canonical faculty identity | Optional role link; Employee and Instructor retain their own status |
| Education `Guardian` | Education guardian profile and student table | Proxy authorization | Optional role link; relationships and access grants remain Talisma-owned |

## Frappe User

Observed fields include required `email` and `first_name`; optional middle/last/full name, gender, phone, mobile, birth date and location; unique username, mobile and API key; roles and role profiles; login restrictions and session state.

### Reuse

- Account identifier and authentication lifecycle.
- Roles, role profiles, user permissions, login controls and session auditing.
- User preferences and portal/Desk account configuration.

### Gaps and constraints

- A person can exist without a user account.
- Profile fields are convenience/account fields and can diverge from legal identity.
- Email is mutable and must not be a durable person or IdP key.
- Multiple accounts require an exceptional federation decision.
- Technical administrators must not inherit unrestricted business-data access.

### Proposed treatment

Link `User` through a generic role/profile link and store external IdP namespace plus immutable subject in a separate external-identity record. Synchronize display/contact fields only through explicit, one-directional policies.

## Contact

Observed fields include names, primary email/phone/mobile, child email and phone tables, optional `User`, `Address`, designation/department and dynamic links.

### Reuse

- Standard communication-channel mechanics.
- Dynamic party links used by ERPNext.
- Existing email and phone child tables where their semantics satisfy the use case.

### Gaps and constraints

- No canonical-person identity or verification workflow.
- No effective-dated purpose, consent, disclosure classification or source semantics across the association.
- Primary flags are insufficient for context-specific preferred channels.
- Contact may represent an organizational contact rather than a canonical natural person.

### Proposed treatment

Do not add canonical identity fields directly to core. Create a Talisma-owned association between Person and Contact with purpose, interval, verification and disclosure controls. Perform a field-level fit check before deciding whether any contact-point details require separate Talisma records.

## Address

Observed fields include required title, type, line 1, city and country; state, postal code, email/phone; primary/shipping/disabled flags; and dynamic party links.

### Reuse

- Postal structure, country link and standard ERPNext party association.
- Billing/shipping behavior within finance and selling.

### Gaps and constraints

- No governed person-association interval, provenance, consent or disclosure class.
- Address type does not express every SIS purpose or legal residency rule.
- Primary flags are global rather than context/effective-date aware.

### Proposed treatment

Associate Person to Address through a Talisma record. Do not copy address strings onto the canonical person.

## Employee

Observed fields include required name, company, status, gender, birth and joining dates; employee number; optional `User`; department/designation/branch; work and personal contact; address text; passport and other HR-sensitive attributes.

### Reuse

- Employment status and dates, company, reporting line, HR identifiers and HR-owned personal data.
- Existing `User` relationship for HR workflows where configured.

### Gaps and constraints

- Employee lifecycle cannot represent applicants, students, guardians or non-employee instructors.
- Several identity/contact fields overlap other standard records.
- Passport, bank, health and employment fields require HR-specific access, not general identity access.

### Proposed treatment

Link Employee to Person without copying HR state or restricted HR values. Employee number remains an HR namespace identifier and may also be registered as an identity alias only under an approved, one-directional issuance rule.

## Customer

Observed fields include required customer name/type, group and territory; billing/tax/account fields; primary Contact/Address; portal users and finance configuration.

### Reuse

- Receivables party and accounting configuration.
- Primary finance contact/address and portal-user behavior.

### Gaps and constraints

- Customer may be an organization or individual.
- Customer status and naming are finance-owned.
- Tax IDs and account details must not become general identity fields.

### Proposed treatment

Use a role link only for individual customers connected to a person. Organizational customers remain outside the natural-person model.

## Education Student Applicant

Observed fields duplicate name, date of birth, gender, blood group, email, mobile and full address data. It owns program, admission, academic year/term, application status and applicant number. Email is indexed but not unique.

### Reuse

- Education application record only if ADR-001 later authorizes the dependency.
- Application status, admission cycle and program intent.

### Gaps and constraints

- Duplicated identity/contact fields have no cross-role history.
- Applicant-to-student conversion can create another identity profile.
- No match/review workflow or canonical person reference.

### Proposed treatment

Resolve/create Person before or during applicant creation, then create a role link. Treat copied applicant fields as a workflow snapshot with explicit ownership, not bidirectional person synchronization.

## Education Student

Observed fields duplicate name, email, mobile, birth data, gender, nationality and address. `student_email_id` is required and unique. It owns joining/leaving data, applicant/customer/user links and student number.

### Reuse

- Education academic profile only if ADR-001 is accepted.
- Existing Education relationships and workflows after compatibility review.

### Gaps and constraints

- Unique student email conflicts with real-world shared/recycled/changed email scenarios.
- Student is not suitable for staff-only, guardian-only or applicant-only people.
- Address/contact duplication lacks effective history.
- No institution-scoped canonical person identifier or resolution workflow.

### Proposed treatment

Role-link Student to Person. Never use the unique email constraint as identity evidence. Applicant conversion must reuse the applicant's Person link idempotently.

## Education Instructor

Observed fields include required instructor name, optional Employee and Department, image, status, gender and log table.

### Reuse

- Teaching profile and optional Employee link if ADR-001 is accepted.

### Gaps and constraints

- Instructor status is teaching-specific.
- Name and gender do not establish canonical identity.

### Proposed treatment

Role-link Instructor to Person. When Employee is present, validate that both role links resolve to the same Person or open an identity review.

## Education Guardian

Observed fields include name, contact details, birth date, optional User, occupation/work details and Student relationships.

### Reuse

- Education guardian profile and legacy relationships only if ADR-001 is accepted.

### Gaps and constraints

- A Guardian record is not proof of legal authority.
- Student membership does not encode consent, scope, effective dates, revocation or permitted actions.
- Guardian may also be employee, student or customer.

### Proposed treatment

Role-link Guardian to Person, migrate its student connections as relationships, and require a separate proxy authorization before access is granted.

## Extension policy

- Do not modify core JSON or Python.
- Prefer Talisma-owned related records over broad custom fields on standard DocTypes.
- If a direct reference is necessary for query performance, add it through supported app-owned customization only after dependency, uninstall and migration behavior are tested.
- Keep Education references dynamic/optional until ADR-001 is accepted.
- Do not implement uncontrolled bidirectional synchronization between Person and standard profiles.

## Blocking dependency

The exact institution-scope link target depends on [ADR-003](ADR-003-INSTITUTIONAL-HIERARCHY.md), which remains proposed. The identity schema may define the requirement and field semantics, but physical creation of institution-scoped records must wait until ADR-003 selects the authoritative institution model.
