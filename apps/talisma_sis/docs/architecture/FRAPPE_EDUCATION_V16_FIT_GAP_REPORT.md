# Frappe Education v16 Compatibility and Fit-Gap Report

- **Status:** Preliminary technical evaluation complete
- **Evaluation date:** 2026-07-11
- **Related decision:** [ADR-001](ADR-001-FRAPPE-EDUCATION-DEPENDENCY.md)
- **Environment:** Isolated Docker Compose project; no production or `talisma.local` data used

## 1. Executive conclusion

Frappe Education `v16.0.1` can be built, installed, migrated, and operated alongside Frappe `v16.25.0`, ERPNext `v16.26.2`, and Talisma SIS `0.0.1` in an isolated Docker environment. Core services become healthy, the Education schema installs, assets are generated and served, a standard backup succeeds, and the app registry remains consistent after migration.

The evaluation also confirms that Education is a useful academic foundation but not a complete higher-education SIS. Its Student, Instructor, Program, Course, academic calendar, attendance, assessment, fee, and simple enrollment models are candidates for reuse or extension. Talisma must own effective-dated curriculum, course offerings, registration transactions, academic attempts, gradebook, transcript, degree audit, graduation, financial aid, commercial portals, FERPA policy, and stable integration contracts.

**Recommendation:** Keep ADR-001 in `Proposed` status. Technical feasibility is demonstrated, but legal review, desktop-navigation remediation, restore testing, permission testing, functional workflow testing, performance testing, and a field-level data model review remain mandatory before acceptance.

## 2. Evaluated versions

| Component | Version | Source |
|---|---:|---|
| Frappe Framework | `v16.25.0` | Verified Git tag `9a8daf3…` |
| ERPNext | `v16.26.2` | Verified Git tag `d1d3b24…` |
| Frappe Education | `v16.0.1` | Verified Git tag `ab3794d…` |
| Talisma SIS | `0.0.1` | Current working tree |
| MariaDB | `11.8` | Existing project override |
| Redis | `8.6-alpine` | Existing project override |

The image was built from exact Git tags. No official Education container image existed at `ghcr.io/frappe/education:v16.0.1` or `:stable` when evaluated.

## 3. Isolation controls

- Compose project: `talisma-education-eval`
- Site: `education-eval.local`
- Frontend: `127.0.0.1:8082`
- Independent network: `talisma-education-eval_default`
- Independent named volumes for sites, MariaDB, and Redis queue data
- Separate image: `talisma-sis:education-eval`
- No real student or institutional data
- No changes to the `talisma.local` database, volumes, network, containers, or port

## 4. Technical test results

| Test | Result | Evidence/notes |
|---|---|---|
| Exact Git tags resolve | Pass | All three upstream tags verified against official repositories. |
| Reproducible layered image build | Pass with workaround | Official layered flow succeeded after increasing Yarn network timeout. |
| Talisma overlay image | Pass | Talisma package installed as `0.0.1`. |
| Windows shell-script compatibility | Pass with workaround | Evaluation image normalizes CRLF to LF during build. |
| Isolated Compose topology | Pass | Separate project, network, volumes, image, and port verified. |
| Frappe site creation | Pass | `education-eval.local` created in isolated MariaDB. |
| ERPNext installation | Pass | `16.26.2` registered. |
| Education installation | Pass with warning | `16.0.1` registered; Desktop Icon sync logged a nonfatal error. |
| Talisma installation | Pass with warning | `0.0.1` registered; same Desktop Icon error repeated. |
| `bench migrate` | Pass | All four apps synchronized and after-migrate hooks completed. |
| Service health | Pass | Backend, frontend, MariaDB, and both Redis containers healthy; workers, scheduler, websocket running. |
| Login route | Pass | HTTP 200. |
| Education Desk route | Partial | HTTP 301 unauthenticated redirect; authenticated navigation not yet automated. |
| Education portal route | Partial | `/edu-portal/` returns 301; route without trailing slash returns 404. Authenticated portal behavior not yet tested. |
| Education asset bundle | Pass | `education.bundle.js` maps to fingerprinted `education.bundle.PSPI3YNS.js`. |
| Site backup with files | Pass | Database, config, public files, and private files generated successfully. |
| Backup restore | Not run | Required before ADR acceptance. |
| Upgrade from earlier Education release | Not run | Required before production release strategy. |
| Uninstall/rollback | Not run | Required before ADR acceptance. |
| Permissions and FERPA scenarios | Not run | Requires approved identity and authorization models. |
| Load/performance | Not run | Requires realistic synthetic data volumes. |

## 5. Installed runtime inventory

### Applications

- Frappe `16.25.0`
- ERPNext `16.26.2`
- Education `16.0.1`
- Talisma SIS `0.0.1`

### Education metadata

- 75 Education-module DocTypes, including primary, child, and tool DocTypes
- 1 public Education workspace
- 9 Education reports
- Relevant installed roles: `Academics User`, `Education Manager`, `Instructor`, and `Student`
- Education hooks reference Guardian portal behavior, but a `Guardian` Role was not present on the fresh site
- A built Education JavaScript bundle and portal/Desk routes

## 6. Compatibility defects and operational findings

### 6.1 Desktop Icon synchronization error

Both Education and Talisma installation logged:

```text
Error creating icons 'NoneType' object has no attribute 'startswith'
```

Installation continued, app registration succeeded, and migration completed. This appears related to Frappe v16 Desktop Icon generation rather than Education schema synchronization. It must be reproduced with a traceback and resolved through upstream-compatible metadata or an upstream fix before production acceptance.

### 6.2 Portal trailing-slash behavior

`/edu-portal/` is recognized and redirects unauthenticated users; `/edu-portal` returns 404. Talisma should not expose this upstream route as its final portal contract. Any retained route requires canonical redirect behavior and automated route tests.

### 6.3 Guardian role inconsistency

Education hooks contain Guardian portal routing, but the evaluated fresh site did not include a Guardian Role among the expected roles. Guardian access must not be assumed. Talisma needs an explicit guardian/proxy-access security design.

### 6.4 Build-network sensitivity

The official layered build initially failed because Yarn's network request timed out. Increasing `YARN_NETWORK_TIMEOUT` to 600000 allowed the pinned build to complete. Production CI should use reliable dependency networking, cached registries where appropriate, locked dependencies, and observable build timeouts.

### 6.5 Windows line endings

Shell scripts copied from the Windows checkout contained CRLF line endings and could not execute in Linux. The evaluation Containerfile normalizes copied scripts during build. Repository-wide line-ending policy should be enforced before relying on host-copied shell scripts.

## 7. Functional fit-gap matrix

| Capability | Education v16 assets | Fit | Talisma direction |
|---|---|---|---|
| Academic calendar | Academic Year, Academic Term | Good foundation | Reuse after effective-date and registration-period review. |
| Student identity | Student, Guardian, Student Guardian, categories/languages | Partial | Link to Talisma canonical identity and add academic-career/privacy history. |
| Faculty identity | Instructor linked to Employee and Department | Good foundation | Extend with appointments, qualifications, workload and advisor assignments. |
| Programs | Program, Program Course, Program Fee | Partial | Reuse Program identity; build versioned curriculum and credential structures. |
| Course catalog | Course, Topic and assessment criteria | Partial | Reuse Course identity; add versions, requisites, equivalencies and repeat rules. |
| Admissions | Student Admission, Student Applicant | Partial | Extend with requirements, review, decision, offer, deferral and identity resolution. |
| Program enrollment | Program Enrollment and tools | Partial | Reuse only after lifecycle review; Talisma owns academic career/plan history. |
| Course enrollment | Course Enrollment | Insufficient | Build registration transaction, attempt, status-history, waitlist and override models. |
| Course offering | Course Schedule, Student Group, Room | Insufficient | Build section/offering, capacity, meeting, cross-list and instructor assignment model. |
| Attendance | Student Attendance, tool, leave application | Good foundation | Extend to offering/session semantics and locked periods. |
| Assessments | Assessment Plan/Result, groups, criteria and grading scale | Good foundation | Extend for higher-education moderation, accommodations and controlled publication. |
| Gradebook | Assessment results and final-grade reports | Insufficient | Build authoritative calculation, approval, publication and grade-change records. |
| Transcript | No authoritative transcript model | Gap | Build new. |
| Degree audit | No requirement-evaluation engine | Gap | Build new. |
| Graduation | No conferral lifecycle | Gap | Build new. |
| Student finance | Fee structures/schedules/fees plus ERPNext invoices | Partial | ERPNext Accounts remains ledger; Talisma owns charge assessment and student account orchestration. |
| Scholarships/aid | No full aid lifecycle | Gap | Build new. |
| Student portal | Education portal and many whitelisted context methods | Prototype only | Build Talisma portal on stable Talisma services. |
| Faculty portal | No complete commercial faculty experience | Gap | Build new. |
| Reporting | 9 operational reports | Partial | Reuse where valid; build governed Talisma analytics definitions and extracts. |
| Integrations | Whitelisted methods and Frappe integration platform | Partial | Wrap upstream operations; publish versioned Talisma APIs/events. |

## 8. Education API finding

The source exposes whitelisted methods for enrollment, attendance, schedules, assessment entry/submission, grading, student and guardian context, portal data, invoices, fee collection, payments, leave, quizzes, and activities.

These methods are useful implementation references and possible internal adapter targets. They are not accepted as Talisma external contracts because their payloads, permissions, transaction boundaries, and compatibility guarantees have not been reviewed.

## 9. Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| GPL-3.0 commercial distribution obligations | Critical | Qualified legal review before dependency acceptance or distribution. |
| Upstream school-oriented semantics constrain university design | High | Field-level fit-gap; isolate higher-education records in Talisma. |
| Desktop navigation error | Medium | Reproduce with traceback; verify hooks and app-screen metadata; contribute upstream fix if appropriate. |
| Permissions not aligned with FERPA | Critical | Complete ADR-002 and permission threat model before functional use. |
| Upstream API changes | High | Talisma adapters and versioned external contracts. |
| Migration/upgrade coupling | High | Pin versions and maintain compatibility/upgrade test matrix. |
| Duplicate identity across Student/Employee/User/Customer | Critical | Adopt and implement approved canonical identity model. |
| Finance duplication | Critical | Keep ERPNext Accounts authoritative; prohibit parallel ledger behavior. |

## 10. Remaining approval work

Before ADR-001 can move to `Accepted`:

1. Obtain written legal guidance for GPL-3.0 and the commercial distribution model.
2. Reproduce and resolve the Desktop Icon error with a full traceback.
3. Complete restore, uninstall, rollback, and supported-upgrade tests.
4. Complete field-level schema comparison for all proposed reused DocTypes.
5. Test permissions for applicant, student, guardian/proxy, instructor, advisor, registrar, finance, and administrator personas.
6. Exercise representative workflows with synthetic data.
7. Test portal behavior in an authenticated browser session.
8. Define supported version pinning and release cadence.
9. Confirm Education is mandatory rather than an optional adapter.

## 11. Recommendation

Proceed to the next architecture gate—field-level domain and permission analysis—while keeping the evaluation environment isolated. Do not install Education on `talisma.local` and do not mark ADR-001 accepted until legal and remaining technical gates are complete.
