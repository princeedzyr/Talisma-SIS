# Module Dependency Map

Status: **Proposed**

The arrows below mean “requires services or authoritative records from,” not Python import direction.

```mermaid
flowchart TB
    Admin[Administration and Shared Foundations]
    Departments[Departments]
    People[Student Information]
    Faculty[Faculty Management]
    Programs[Academic Programs]
    Curriculum[Curriculum Management]
    Catalog[Course Catalog]
    Offering[Course Offering]
    Admissions[Admissions]
    Registration[Enrollment and Registration]
    Attendance[Student Attendance]
    Assessment[Assessments]
    Gradebook[Gradebook]
    Audit[Degree Audit]
    Transcript[Transcript Management]
    Graduation[Graduation]
    Finance[Student Finance]
    Aid[Scholarships and Financial Aid]
    StudentPortal[Student Portal]
    FacultyPortal[Faculty Portal]
    Reports[Reports and Analytics]
    Integrations[Integrations]

    Admin --> Departments
    Admin --> People
    Departments --> Faculty
    Departments --> Programs
    People --> Admissions
    Programs --> Admissions
    Programs --> Curriculum
    Catalog --> Curriculum
    Curriculum --> Offering
    Faculty --> Offering
    Admin --> Offering
    Admissions --> Registration
    People --> Registration
    Offering --> Registration
    Curriculum --> Registration
    Registration --> Attendance
    Registration --> Assessment
    Assessment --> Gradebook
    Registration --> Gradebook
    Gradebook --> Transcript
    Curriculum --> Audit
    Transcript --> Audit
    Audit --> Graduation
    Transcript --> Graduation
    Registration --> Finance
    Finance --> Aid
    People --> Aid
    Admissions --> Aid
    People --> StudentPortal
    Registration --> StudentPortal
    Gradebook --> StudentPortal
    Finance --> StudentPortal
    Faculty --> FacultyPortal
    Offering --> FacultyPortal
    Attendance --> FacultyPortal
    Gradebook --> FacultyPortal
    Admin --> Reports
    People --> Reports
    Registration --> Reports
    Finance --> Reports
    Admin --> Integrations
    People --> Integrations
    Registration --> Integrations
    Finance --> Integrations
```

## Dependency rules

1. Shared foundations cannot depend on a downstream academic module.
2. Portals orchestrate module services; they do not own authoritative academic data.
3. Reports consume governed records; they do not repair or mutate them.
4. Integrations call application services rather than bypassing validation through direct inserts.
5. Student Finance posts to ERPNext Accounts and does not implement a second ledger.
6. Transcript and degree-audit results depend on finalized academic attempts, not mutable display grades.
