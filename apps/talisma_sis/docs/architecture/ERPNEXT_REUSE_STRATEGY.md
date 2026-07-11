# ERPNext and Frappe Education Reuse Strategy

Status: **Proposed**

## 1. Decision categories

- **Reuse ERPNext**: use an upstream record and lifecycle without creating a competing Talisma master.
- **Extend ERPNext**: preserve upstream ownership but add Talisma-owned fields, validation, services, permissions, or related records through supported extension points. In this document this category also covers extending the separately maintained Frappe Education app.
- **Build New**: create a Talisma-owned domain capability because no upstream model has the required meaning, lifecycle, auditability, or scale.

Extension never means modifying upstream source.

## 2. Installed-state finding

ERPNext v16.26.2 no longer contains its historical Education module. The current site has `frappe`, `erpnext`, and `talisma_sis` installed; `education` is not installed. Any Education reuse below is conditional on the dependency approval gate.

## 3. Frappe platform reuse

| Capability | Standard assets to reuse | Strategy |
|---|---|---|
| Authentication | User, sessions, password policies, OAuth and API keys | Reuse ERPNext/Frappe |
| Authorization | Role, Role Profile, User Permission, DocPerm, permission-query hooks | Extend ERPNext/Frappe |
| Workflow | Workflow, Workflow State, Workflow Action, Assignment and ToDo | Reuse ERPNext/Frappe |
| Audit | Version, Activity Log, document timeline and comments | Extend ERPNext/Frappe |
| Communication | Communication, Email Account, Notification and Email Group | Reuse ERPNext/Frappe |
| Files | File and private attachment handling | Reuse ERPNext/Frappe |
| Metadata | DocType, Custom Field, Property Setter and fixtures | Extend ERPNext/Frappe |
| Jobs | Background jobs, scheduler and Redis queues | Reuse ERPNext/Frappe |
| Reporting | Report, Dashboard, Number Card and Prepared Report | Extend ERPNext/Frappe |
| Import/export | Data Import and controlled export APIs | Extend ERPNext/Frappe |

## 4. ERPNext functional reuse

| Domain | Standard DocTypes/modules | Ownership decision |
|---|---|---|
| Legal entity | Company | ERPNext remains authoritative. |
| Organization | Department | Reuse where operational and academic hierarchies align; extend with related academic units only when required. |
| Workforce | Employee, Department, User | ERPNext owns employment; Talisma links teaching/advising roles. |
| Parties | Customer, Contact, Address | Reuse for billing/contact concerns; do not make Customer the academic student record. |
| Catalog accounting | Item, Item Group | Reuse only for charge components and financial posting references, not academic course identity. |
| Accounting | Account, Cost Center, Accounting Dimension, GL Entry | ERPNext is financial truth. |
| Receivables | Sales Invoice, Payment Entry, Payment Request, Credit Note behavior | ERPNext owns posted financial transactions. |
| Currency and tax | Currency, exchange rates, tax templates | Reuse ERPNext. |
| Documents | Print Format, Letter Head, File | Reuse and extend for controlled academic output. |

## 5. Frappe Education v16 inventory

### Strong reuse candidates

- Academic Year and Academic Term
- Student, Guardian, Student Guardian and related profile children
- Instructor linked to Employee and Department
- Program and Course identities
- Room
- Grading Scale and assessment criteria masters

These are identities or simple masters whose semantics may be extended without competing duplicates.

### Reuse after gap analysis

- Student Admission and Student Applicant
- Program Enrollment and Course Enrollment
- Student Group and Course Schedule
- Student Attendance and Student Leave Application
- Assessment Plan and Assessment Result
- Fee Structure, Fee Schedule, Fees and Payment Record
- Education workspace, student portal, reports, and whitelisted APIs

These models provide useful behavior but require field-level review against higher-education requirements. Their names must not imply architectural approval.

### Do not use as Talisma system of record without redesign

- `Program Course` as a complete curriculum model
- `Course Enrollment` as a complete registration/attempt ledger
- `Course Schedule` as a complete section/offering model
- assessment reports as an authoritative transcript
- Education fee records as a replacement for ERPNext Accounts
- the existing education portal as the final commercial student experience

## 6. Education APIs reviewed

The version-16 app exposes methods for:

- student enrollment and current enrollment;
- attendance entry and attendance retrieval;
- course schedules and program/course lists;
- assessment criteria, students, result entry, grading, and submission;
- student, guardian, instructor, and portal context;
- fee structure/schedule lookup, collection, invoices, and payment callbacks;
- leave applications, quizzes, and activities.

Talisma may call these methods internally through adapters after permission, transaction, error, and compatibility review. External consumers must use Talisma-owned versioned APIs so upstream changes do not break institutional integrations.

## 7. Workspace strategy

- Keep ERPNext workspaces for Accounts, Selling, Setup, and other enterprise operations.
- Treat Education's single workspace as an upstream administrative workspace if Education is installed.
- Build curated Talisma workspaces by persona and business process only during implementation phases.
- Do not modify standard upstream workspace JSON.
- Use Frappe v16 Workspace Sidebar and app-screen hooks for navigation.

## 8. Upgrade strategy

- Pin exact upstream releases in the custom image.
- Maintain a compatibility test matrix for Frappe, ERPNext, Education, and Talisma.
- Test Talisma extensions against upstream schema changes before upgrades.
- Avoid Property Setters when a related Talisma record provides a safer boundary.
- Keep overrides exceptional, documented, and protected by regression tests.
- Never expose an upstream private method as a Talisma contract.

## 9. Sources

- Frappe Education repository and compatibility matrix: <https://github.com/frappe/education>
- Education v16 hooks and required apps: <https://github.com/frappe/education/blob/version-16/education/hooks.py>
- Education v16 package constraints: <https://github.com/frappe/education/blob/version-16/pyproject.toml>
- Frappe v16 migration guidance: <https://github.com/frappe/frappe/wiki/Migrating-to-version-16>
