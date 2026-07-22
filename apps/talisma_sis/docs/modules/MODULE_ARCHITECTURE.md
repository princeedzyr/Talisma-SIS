# Talisma SIS Module Architecture

Status: **Proposed for domain review**

DocType names marked **candidate** describe architectural records, not approved schemas. No DocType should be created until its module design is approved.

## Classification summary

| Module | Strategy |
|---|---|
| Admissions | Extend ERPNext |
| Student Information | Extend ERPNext |
| Academic Programs | Extend ERPNext |
| Departments | Extend ERPNext |
| Faculty Management | Extend ERPNext |
| Curriculum Management | Build New |
| Course Catalog | Extend ERPNext |
| Course Offering | Build New |
| Enrollment & Registration | Build New |
| Student Attendance | Extend ERPNext |
| Assessments | Extend ERPNext |
| Gradebook | Build New |
| Transcript Management | Build New |
| Degree Audit | Build New |
| Graduation | Build New |
| Student Finance | Extend ERPNext |
| Scholarships & Financial Aid | Build New |
| Student Portal | Build New |
| Faculty Portal | Build New |
| Administration | Extend ERPNext |
| Reports & Analytics | Build New |
| Integrations | Build New |

“Extend ERPNext” includes supported extensions to Frappe Education when the dependency is approved; it never means editing upstream source.

## 1. Admissions — Extend ERPNext

**Purpose:** Manage the applicant journey from an open admission cycle through a governed admission decision and matriculation handoff.

**Business capabilities:** admission cycles; online applications; program choices; requirements and checklists; document verification; review assignments; scoring; interviews; decisions; offers; deposits; deferrals; withdrawals; duplicate-person resolution; applicant-to-student conversion.

**Primary DocTypes:** Education `Student Admission`, `Student Applicant`, and `Student Admission Program`; Frappe `Web Form`, `Workflow`, `File`, `Communication`, and `Assignment`; candidates `Admission Application Requirement`, `Admission Review`, `Admission Decision`, `Admission Offer`, and `Application Status History`.

**Related ERPNext modules:** CRM/communications where useful, Selling/Accounts for deposits, Setup for organization and contacts.

**Dependencies:** Administration, Departments, Academic Programs, identity matching, document privacy, workflow, Student Information handoff.

**Future integrations:** application portals, identity verification, document verification, test-score providers, CRM, payment gateways, government admissions services.

## 2. Student Information — Extend ERPNext

**Purpose:** Maintain the authoritative academic identity and effective-dated student relationship with the institution.

**Business capabilities:** student profile; institutional identifiers; names and contacts; guardians/emergency contacts; demographic data; academic career/status; residency; privacy restrictions; holds; service indicators; documents; status history; duplicate resolution.

**Primary DocTypes:** Education `Student`, `Guardian`, `Student Guardian`, `Student Language`, `Student Log`; Frappe `User`, `Contact`, `Address`, `File`; ERPNext `Customer` only as a billing party; candidates `Student Academic Career`, `Student Status History`, `Student Hold`, `Privacy Restriction`, and `External Identifier`.

**Related ERPNext modules:** Setup, Contacts, Accounts/Selling.

**Dependencies:** Administration and institutional identity policy.

**Future integrations:** identity providers, national identity services, CRM, document management, housing, library, health and conduct systems.

## 3. Academic Programs — Extend ERPNext

**Purpose:** Define academic programs and credentials offered by institutional units.

**Business capabilities:** programs; credentials; academic careers and levels; ownership; campuses; effective dates; admission availability; program status; concentrations, majors and minors; accreditation references.

**Primary DocTypes:** Education `Program`, `Academic Year`, `Academic Term`, and `Program Fee`; candidates `Academic Career`, `Credential`, `Program Version`, `Program Plan`, and `Program Accreditation`.

**Related ERPNext modules:** Setup and Department; Accounts for financial dimensions where applicable.

**Dependencies:** Administration and Departments.

**Future integrations:** catalog publishing, accreditation, government program registries, admissions platforms, analytics.

## 4. Departments — Extend ERPNext

**Purpose:** Represent academic and administrative ownership without duplicating legal or accounting organization records.

**Business capabilities:** department hierarchy; academic schools/colleges/faculties; campus affiliation; leadership; effective dates; program and course ownership; financial mapping.

**Primary DocTypes:** ERPNext `Company`, `Department`, `Cost Center`; candidate `Academic Unit` only if Department cannot represent higher-education governance and effective dating.

**Related ERPNext modules:** Setup, Accounts, Human Resources records retained in ERPNext.

**Dependencies:** Administration.

**Future integrations:** HR, identity governance, finance, institutional directories, data warehouse.

## 5. Faculty Management — Extend ERPNext

**Purpose:** Connect employment and identity records to teaching, advising, qualification, and academic assignments.

**Business capabilities:** instructor profiles; qualifications; ranks and affiliations; teaching eligibility; workload; section assignment; advisor assignment; availability; delegation; active/inactive lifecycle.

**Primary DocTypes:** ERPNext `Employee`, `Department`, `User`; Education `Instructor`, `Instructor Log`, `Student Group Instructor`; candidates `Faculty Qualification`, `Faculty Appointment`, `Teaching Assignment`, and `Advisor Assignment`.

**Related ERPNext modules:** Setup and employee records; Projects/Timesheets only if institutionally appropriate.

**Dependencies:** Departments, Administration, identity and authorization.

**Future integrations:** HRMS, identity provider, LMS, workload planning, research systems, directory services.

## 6. Curriculum Management — Build New

**Purpose:** Maintain immutable, effective-dated curriculum versions and requirement structures against which students can be evaluated.

**Business capabilities:** curriculum proposals and approval; versions; requirement groups; credit and course rules; electives; alternatives; substitutions; residency rules; minimum grades; applicability by cohort; publication; historical preservation.

**Primary DocTypes:** Education `Program` and `Program Course` as references; candidates `Curriculum`, `Curriculum Version`, `Curriculum Requirement`, `Requirement Group`, `Course Rule`, `Requirement Alternative`, and `Curriculum Exception`.

**Related ERPNext modules:** Workflow, Department, document approval and communications.

**Dependencies:** Academic Programs, Departments, Course Catalog, Administration.

**Future integrations:** curriculum governance, catalog publishing, accreditation, degree-planning tools, LMS.

## 7. Course Catalog — Extend ERPNext

**Purpose:** Define governed course identities and effective-dated academic catalog information independently of individual offerings.

**Business capabilities:** course identity; versions; title and description; credits/contact hours; ownership; level; grading basis; repeatability; prerequisites and corequisites; equivalencies; retirement; catalog publication.

**Primary DocTypes:** Education `Course`, `Topic`, `Course Topic`, `Course Assessment Criteria`; candidates `Course Version`, `Course Requisite`, `Course Equivalency`, and `Course Attribute`.

**Related ERPNext modules:** Department and Item only for mapped financial charge components; an ERPNext Item must not replace Course.

**Dependencies:** Departments and Administration.

**Future integrations:** LMS, catalog publishing, transfer-articulation systems, accreditation and scheduling systems.

## 8. Course Offering — Build New

**Purpose:** Represent a schedulable, enrollable instance of a course in a term.

**Business capabilities:** sections; term and session; campus/modality; capacity; instructor assignments; meeting patterns; rooms; cross-listing; combined sections; status; cancellation; reserved capacity; final-exam schedule.

**Primary DocTypes:** Education `Course Schedule`, `Student Group`, `Room`, `Instructor`; candidates `Course Offering`, `Offering Section`, `Meeting Pattern`, `Offering Instructor`, `Reserved Capacity`, and `Cross Listing`.

**Related ERPNext modules:** Department, Employee, Company and facilities references where applicable.

**Dependencies:** Course Catalog, Academic Programs, Faculty Management, Administration, academic calendar.

**Future integrations:** timetabling, room scheduling, LMS provisioning, video conferencing, campus access and calendar systems.

## 9. Enrollment & Registration — Build New

**Purpose:** Govern student registration and preserve every academic attempt and registration transaction.

**Business capabilities:** eligibility; registration appointments; prerequisite checking; holds; conflicts; capacity; waitlists; reserved seats; add/drop/swap; withdrawal; audits; overrides; repeat handling; credit load; census; enrollment status history.

**Primary DocTypes:** Education `Program Enrollment`, `Course Enrollment`, and tools as references; candidates `Registration Period`, `Registration Appointment`, `Enrollment`, `Enrollment Transaction`, `Waitlist Entry`, `Registration Override`, `Enrollment Status History`, and `Student Term`.

**Related ERPNext modules:** Workflow and communications; Accounts through Student Finance events.

**Dependencies:** Student Information, Curriculum, Course Offering, Academic Programs, Administration and policy engine.

**Future integrations:** LMS, national enrollment reporting, identity/access provisioning, billing, advising and mobile applications.

## 10. Student Attendance — Extend ERPNext

**Purpose:** Record attendance or participation for valid students in scheduled offerings.

**Business capabilities:** session rosters; presence/absence/late/excused status; bulk entry; leave handling; corrections; thresholds; alerts; summaries; locked periods.

**Primary DocTypes:** Education `Student Attendance`, `Student Attendance Tool`, `Student Leave Application`, `Course Schedule`, `Student Group`; candidate `Attendance Session` or extensions if offering-level semantics require it.

**Related ERPNext modules:** Employee/User for instructors, Notification and Workflow.

**Dependencies:** Enrollment & Registration, Course Offering, Faculty Management.

**Future integrations:** LMS participation, classroom devices, card access, mobile check-in and advising alerts.

## 11. Assessments — Extend ERPNext

**Purpose:** Define assessment structures and capture controlled assessment results.

**Business capabilities:** assessment plans; criteria; weighting; schedules; eligible rosters; accommodations; result entry; moderation; submission; correction; publication.

**Primary DocTypes:** Education `Assessment Group`, `Assessment Criteria`, `Assessment Criteria Group`, `Assessment Plan`, `Assessment Plan Criteria`, `Assessment Result`, and `Assessment Result Detail`.

**Related ERPNext modules:** Workflow, File, Communication and Employee/User.

**Dependencies:** Course Offering, Enrollment & Registration, Faculty Management and grading policy.

**Future integrations:** LMS grade passback, examination platforms, proctoring, accommodations and plagiarism services.

## 12. Gradebook — Build New

**Purpose:** Calculate, approve, publish, and preserve course grades from assessments and institutional grading policies.

**Business capabilities:** gradebook columns; weighted calculation; rounding; missing/incomplete handling; grading basis; final-grade calculation; approval; publication; grade changes; audit and recalculation explanation.

**Primary DocTypes:** Education `Grading Scale`, `Grading Scale Interval`, `Assessment Result`; candidates `Gradebook`, `Gradebook Item`, `Student Grade`, `Final Grade`, `Grade Change Request`, and `Grade Calculation Snapshot`.

**Related ERPNext modules:** Workflow, Assignment, Communication and audit records.

**Dependencies:** Assessments, Enrollment & Registration, Course Offering and policy configuration.

**Future integrations:** LMS, examination systems, student portal, transcript and analytics.

## 13. Transcript Management — Build New

**Purpose:** Maintain and produce authoritative, reproducible academic histories.

**Business capabilities:** academic attempt ledger; earned credits; GPA and honors; repeat treatment; transfer work; test credit; transcript comments; holds; official/unofficial production; release authorization; issue history; verification.

**Primary DocTypes:** candidates `Academic Attempt`, `Transfer Institution`, `Transfer Credit`, `Transcript`, `Transcript Line`, `Transcript Request`, `Transcript Release`, and `GPA Calculation Snapshot`.

**Related ERPNext modules:** Print Format, File, Payment Request/Sales Invoice for transcript fees, Workflow and Communication.

**Dependencies:** Gradebook, Enrollment & Registration, Student Information, Academic Programs and policy versions.

**Future integrations:** transcript exchanges, credential wallets, clearinghouses, government reporting, e-signature and document verification.

## 14. Degree Audit — Build New

**Purpose:** Explain a student's progress against an assigned curriculum version and approved exceptions.

**Business capabilities:** requirement evaluation; course matching; credits; minimum grades; residency; GPA rules; substitutions; waivers; what-if audits; planned work; deficiency explanation; advisor approval; frozen audit snapshots.

**Primary DocTypes:** candidates `Degree Audit`, `Degree Audit Result`, `Requirement Evaluation`, `Student Curriculum Assignment`, `Academic Exception`, and `What If Plan`.

**Related ERPNext modules:** Workflow, Assignment and reporting.

**Dependencies:** Curriculum Management, Transcript Management, Course Catalog, Academic Programs and Student Information.

**Future integrations:** advising/planning products, catalog systems, transfer articulation and student portal.

## 15. Graduation — Build New

**Purpose:** Coordinate graduation eligibility, clearances, approvals, conferral, and credential issuance.

**Business capabilities:** graduation application; expected graduation; audit review; institutional clearances; honors; ceremony participation; approval; degree conferral; credential record; revocation/correction; alumni handoff.

**Primary DocTypes:** candidates `Graduation Application`, `Graduation Clearance`, `Graduation Review`, `Degree Conferral`, `Credential`, and `Ceremony Participation`.

**Related ERPNext modules:** Workflow, File, Print Format, Communication and Accounts for fees/holds.

**Dependencies:** Degree Audit, Transcript Management, Student Finance, Student Information and Academic Programs.

**Future integrations:** diploma vendors, credential wallets, alumni systems, government registries and ceremony systems.

## 16. Student Finance — Extend ERPNext

**Purpose:** Translate academic activity and institutional policy into transparent student-account activity while ERPNext remains the accounting system of record.

**Business capabilities:** tuition/fee assessment; charge rules; deposits; invoices; payment allocation; sponsorship; waivers; refunds; payment plans; holds; reconciliation; student account view.

**Primary DocTypes:** ERPNext `Customer`, `Item`, `Sales Invoice`, `Payment Entry`, `Payment Request`, `Account`, `Cost Center`, `Accounting Dimension`; Education `Fee Category`, `Fee Structure`, `Fee Schedule`, `Fees`, `Payment Record`; candidates `Charge Rule`, `Charge Assessment`, `Student Account Item`, `Sponsor Authorization`, and `Refund Request`.

**Related ERPNext modules:** Accounts, Selling and regional tax functionality.

**Dependencies:** Student Information, Enrollment & Registration, Academic Programs, Administration and accounting configuration.

**Future integrations:** payment gateways, banking, cashiering, government sponsorship, collections and financial reporting.

## 17. Scholarships & Financial Aid — Build New

**Purpose:** Manage institutional and external aid from application through award, disbursement, adjustment, and reconciliation.

**Business capabilities:** aid years; funds; applications; eligibility; need/merit rules; document requirements; packaging; awards; acceptance; disbursement; satisfactory academic progress; return/cancellation; reconciliation.

**Primary DocTypes:** candidates `Aid Year`, `Financial Aid Application`, `Aid Fund`, `Eligibility Evaluation`, `Student Award`, `Award Disbursement`, `Scholarship`, `Scholarship Application`, and `Satisfactory Academic Progress Review`.

**Related ERPNext modules:** Accounts, Payment Entry, Journal Entry where approved, Cost Center, Workflow and File.

**Dependencies:** Student Information, Admissions, Academic Programs, Enrollment & Registration, Gradebook and Student Finance.

**Future integrations:** government aid systems, scholarship providers, banking, tax reporting and document verification.

## 18. Student Portal — Build New

**Purpose:** Provide secure, accessible self-service for the complete student journey.

**Business capabilities:** profile and privacy; application status; registration; schedule; attendance; grades; degree progress; transcripts; finances; aid; requests; documents; notifications and consent.

**Primary DocTypes:** no authoritative portal DocTypes by default; use domain services, Frappe `User`, portal roles, `Web Form`, `File`, `Communication`, and candidate `Student Request` where a durable request is required.

**Related ERPNext modules:** Portal, Accounts payment flows, Print Formats and Communications.

**Dependencies:** Student Information, Registration, Attendance, Gradebook, Degree Audit, Transcript, Finance, Aid and FERPA controls.

**Future integrations:** IdP, payment gateway, LMS, mobile app, notification providers and digital credentials.

## 19. Faculty Portal — Build New

**Purpose:** Give instructors and advisors relationship-scoped access to assigned academic work.

**Business capabilities:** assigned sections; rosters; attendance; assessments; gradebook; final-grade submission; advisees; approvals; announcements and controlled exports.

**Primary DocTypes:** no authoritative portal DocTypes by default; use `Instructor`, `Employee`, offering assignments, advisor assignments and domain services.

**Related ERPNext modules:** Employee/User, Assignment, Communication and Workflow.

**Dependencies:** Faculty Management, Course Offering, Registration, Attendance, Assessments, Gradebook, Advising capabilities and FERPA controls.

**Future integrations:** IdP, LMS, timetable, research systems and communication providers.

## 20. Administration — Extend ERPNext

**Purpose:** Configure institutional scope, calendars, policies, security, reference data, workflows, and operational controls.

**Business capabilities:** institution/campus structure; academic calendars; policy versions; reason codes; numbering; role design; delegated administration; data retention; jobs; feature configuration; audit review.

**Primary DocTypes:** ERPNext `Company`, `Department`, `Cost Center`; Education `Academic Year`, `Academic Term`, `Education Settings`; Frappe `Role`, `Role Profile`, `User Permission`, `Workflow`, `Notification`, `Naming Series`; candidates `Institution`, `Campus`, `Policy Set`, and `Academic Session` only where gaps are approved.

**Related ERPNext modules:** Setup, Accounts and all shared Frappe platform modules.

**Dependencies:** none beyond the platform; this is a foundation for all modules.

**Future integrations:** IdP, HR, directory services, configuration management, monitoring and compliance tooling.

## 21. Reports & Analytics — Build New

**Purpose:** Deliver governed operational reporting, compliance extracts, and analytical data products.

**Business capabilities:** registrar operations; enrollment and retention; admissions funnel; finance and aid; faculty workload; outcomes; compliance; data quality; scheduled extracts; metric catalog.

**Primary DocTypes:** Frappe `Report`, `Dashboard`, `Dashboard Chart`, `Number Card`, `Prepared Report`; candidate `Data Extract Definition` only if operationally required.

**Related ERPNext modules:** Reports across Accounts, Setup and Education; all Talisma domain modules.

**Dependencies:** Administration, permissions, shared definitions and the domain records being reported.

**Future integrations:** Frappe Insights, institutional data warehouse, BI platforms, regulatory submissions and secure file exchange.

## 22. Integrations — Build New

**Purpose:** Provide governed, observable contracts between Talisma and the institutional ecosystem.

**Business capabilities:** API versioning; credentials; external IDs; inbound staging; validation; outbound events; idempotency; retries; reconciliation; monitoring; error resolution; data contracts.

**Primary DocTypes:** Frappe `Integration Request`, OAuth/API credentials and background jobs; candidates `Integration Endpoint`, `External Identifier`, `Integration Event`, `Import Batch`, `Import Row`, and `Reconciliation Issue`.

**Related ERPNext modules:** ERPNext integrations and domain modules exposed through Talisma services.

**Dependencies:** Administration, security, audit and every integrated domain.

**Future integrations:** IdP, LMS, CRM, payment and banking, government reporting, transcript exchanges, document/e-sign, library, housing, health, alumni and analytics platforms.
