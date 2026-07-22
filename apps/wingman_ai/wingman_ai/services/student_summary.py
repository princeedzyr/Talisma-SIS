def get_student_360_response(doctype, docname, base_summary, message=None):
    if doctype != "Student":
        return None

    try:
        from talisma_sis.student_360 import get_student_360

        student_360 = get_student_360(docname)
    except (ImportError, ModuleNotFoundError):
        return None

    activity = get_student_academic_activity(docname)
    focus = student_response_focus(message)
    formatter = {
        "enrollment": format_student_enrollment,
        "courses": format_student_courses,
        "finance": format_student_finance,
    }.get(focus, format_student_360)
    return {
        "message": formatter(student_360, base_summary, activity),
        "data": {
            "record_summary": base_summary,
            "student_360": student_360,
            "student_activity": activity,
            "response_mode": f"student_{focus}_read" if focus != "360" else "student_360_read",
            "read_only": True,
        },
    }


def student_response_focus(message):
    text = " ".join(str(message or "").lower().split())
    if "account balance" in text or "student account" in text or " fees" in f" {text}":
        return "finance"
    if "course" in text or "grade" in text:
        return "courses"
    if "enrollment" in text or "enrolment" in text:
        return "enrollment"
    return "360"


def format_student_360(student_360, base_summary, activity=None):
    student_name = student_360.get("student_name") or base_summary.get("title") or student_360.get("student")
    record_summary = (student_360.get("student_records") or {}).get("summary") or {}
    enrollment = (student_360.get("enrollment") or {}).get("current") or {}
    courses = (student_360.get("course_registration") or {}).get("records") or []
    finance = student_360.get("finance") or {}
    finance_summary = finance.get("summary") or {}
    activity = activity or {}
    fields = {item.get("fieldname"): item.get("value") for item in base_summary.get("fields") or []}

    lines = [
        "Student 360",
        student_name,
        "",
        "Academic Overview",
        detail("Record Status", record_summary.get("record_status") or fields.get("talisma_record_status") or base_summary.get("status")),
        detail("Program", enrollment.get("program_name") or record_summary.get("primary_program") or fields.get("talisma_primary_program")),
        detail("Academic Level", record_summary.get("academic_level") or fields.get("talisma_academic_level")),
        detail("Academic Term", enrollment.get("academic_term")),
        detail("Academic Standing", record_summary.get("standing") or fields.get("talisma_class_standing")),
        detail("Advisor", readable_link("Instructor", record_summary.get("advisor") or fields.get("talisma_advisor"), "instructor_name")),
    ]

    contact = compact_details(
        detail("Email", fields.get("student_email_id")),
        detail("Phone", fields.get("student_mobile_number")),
        detail("Campus", enrollment.get("campus_name") or readable_link("Talisma Campus", enrollment.get("campus") or fields.get("talisma_home_campus"), "campus_name")),
    )
    if contact:
        lines.extend(["", "Contact & Campus", *contact])

    lines.extend(["", "Enrollment & Courses"])
    if enrollment:
        lines.append(detail("Enrollment", f"{enrollment.get('enrollment_status') or 'Active'} | {enrollment.get('academic_year') or 'Academic year not set'}"))
    else:
        lines.append("- No current program enrollment was found.")
    if courses:
        lines.append(f"- Registered Courses: {len(courses)}")
        for course in courses[:4]:
            label = course.get("course_name") or course.get("course_code") or course.get("name")
            state = course.get("completion_status") or course.get("course_status")
            grade = course.get("grade")
            suffix = " | ".join(str(value) for value in (state, f"Grade {grade}" if grade else None) if value)
            lines.append(f"  - {label}{f' | {suffix}' if suffix else ''}")
    else:
        lines.append("- No course registrations were found.")

    attendance = activity.get("attendance") or {}
    results = activity.get("assessment_results") or []
    lines.extend(["", "Attendance & Results"])
    if attendance.get("total"):
        lines.append(detail("Attendance Records", attendance.get("total")))
        lines.append(detail("Present", attendance.get("present")))
        lines.append(detail("Absent", attendance.get("absent")))
        if attendance.get("attendance_rate") is not None:
            lines.append(detail("Attendance Rate", f"{attendance.get('attendance_rate'):.1f}%"))
    else:
        lines.append("- No attendance records were found.")
    if results:
        lines.append(f"- Assessment Results: {len(results)}")
        for result in results[:4]:
            label = result.get("course") or result.get("assessment_plan") or result.get("name")
            outcome = result.get("grade") or result.get("score") or result.get("total_score")
            lines.append(f"  - {label}{f' | {outcome}' if outcome not in (None, '') else ''}")
    else:
        lines.append("- No assessment results were found.")

    lines.extend(["", "Alerts & Student Account"])
    lines.append(detail("Active Holds", record_summary.get("active_holds", 0)))
    lines.append(detail("Privacy Restriction", "Active" if record_summary.get("privacy_restriction") else "None"))
    if finance.get("restricted"):
        lines.append("- Student account information is restricted for your role.")
    elif finance_summary:
        currency = finance_summary.get("currency") or ""
        lines.append(detail("Outstanding Balance", money(finance_summary.get("outstanding_balance"), currency)))
        lines.append(detail("Next Due Date", finance_summary.get("next_due_date")))
    else:
        lines.append("- No student account activity was found.")

    lines.extend(
        [
            "",
            "What You Can Do Next",
            f'- Ask "show enrollment for student {student_name}".',
            f'- Ask "summarize courses and grades for student {student_name}".',
            f'- Ask "show account balance for student {student_name}".',
            f'- Ask "open student {student_name}".',
        ]
    )
    return "\n".join(line for line in lines if line is not None)


def format_student_enrollment(student_360, base_summary, activity=None):
    student_name = student_360.get("student_name") or base_summary.get("title") or "Student"
    enrollment = (student_360.get("enrollment") or {}).get("current") or {}
    courses = (student_360.get("course_registration") or {}).get("records") or []
    lines = ["Enrollment", student_name, "", "Current Enrollment"]
    if enrollment:
        lines.extend(
            compact_details(
                detail("Program", enrollment.get("program_name")),
                detail("Enrollment Status", enrollment.get("enrollment_status") or "Active"),
                detail("Academic Year", enrollment.get("academic_year")),
                detail("Academic Term", enrollment.get("academic_term")),
                detail("Campus", enrollment.get("campus_name")),
                detail("Expected Start Date", enrollment.get("expected_start_date")),
                detail("Registered Courses", len(courses)),
            )
        )
    else:
        lines.append("- No current program enrollment was found.")
    lines.extend(
        [
            "",
            "What You Can Do Next",
            f'- Ask "summarize courses and grades for student {student_name}".',
            f'- Ask "tell me about student {student_name}" for the full Student 360 view.',
        ]
    )
    return "\n".join(line for line in lines if line is not None)


def format_student_courses(student_360, base_summary, activity=None):
    student_name = student_360.get("student_name") or base_summary.get("title") or "Student"
    enrollment = (student_360.get("enrollment") or {}).get("current") or {}
    courses = (student_360.get("course_registration") or {}).get("records") or []
    lines = [
        "Courses & Grades",
        student_name,
        "",
        "Academic Context",
        detail("Program", enrollment.get("program_name")),
        detail("Academic Term", enrollment.get("academic_term")),
        detail("Registered Courses", len(courses)),
        "",
        "Course Results",
    ]
    if courses:
        for course in courses[:8]:
            label = course.get("course_name") or course.get("course_code") or "Course"
            details = [course.get("completion_status") or course.get("course_status")]
            if course.get("credit_hours") not in (None, ""):
                details.append(f"{course.get('credit_hours'):g} credits")
            if course.get("grade") not in (None, ""):
                details.append(f"Grade {course.get('grade')}")
            lines.append(f"- {label}{' | ' + ' | '.join(details) if details else ''}")
    else:
        lines.append("- No course registrations were found.")
    lines.extend(
        [
            "",
            "What You Can Do Next",
            f'- Ask "show enrollment for student {student_name}".',
            f'- Ask "tell me about student {student_name}" for the full Student 360 view.',
        ]
    )
    return "\n".join(line for line in lines if line is not None)


def format_student_finance(student_360, base_summary, activity=None):
    student_name = student_360.get("student_name") or base_summary.get("title") or "Student"
    finance = student_360.get("finance") or {}
    summary = finance.get("summary") or {}
    currency = summary.get("currency") or ""
    lines = ["Account Balance", student_name, "", "Student Account"]
    if finance.get("restricted"):
        lines.append("- Student account information is restricted for your role.")
    elif summary:
        lines.extend(
            compact_details(
                detail("Outstanding Balance", money(summary.get("outstanding_balance"), currency)),
                detail("Total Charges", money(summary.get("total_charges"), currency)),
                detail("Total Payments", money(summary.get("total_payments"), currency)),
                detail("Scholarships", money(summary.get("total_scholarships"), currency)),
                detail("Last Payment Date", summary.get("last_payment_date")),
                detail("Next Due Date", summary.get("next_due_date")),
            )
        )
        lines.append(detail("Account Status", "Balance due" if float(summary.get("outstanding_balance") or 0) > 0 else "Paid in full"))
    else:
        lines.append("- No student account activity was found.")
    lines.extend(
        [
            "",
            "What You Can Do Next",
            f'- Ask "show enrollment for student {student_name}".',
            f'- Ask "tell me about student {student_name}" for the full Student 360 view.',
        ]
    )
    return "\n".join(line for line in lines if line is not None)


def compact_details(*items):
    return [item for item in items if item]


def detail(label, value):
    if value in (None, ""):
        return None
    return f"- {label}: {value}"


def money(value, currency):
    if value in (None, ""):
        return None
    try:
        formatted = f"{float(value):,.2f}"
    except (TypeError, ValueError):
        formatted = str(value)
    if str(currency or "").upper() == "USD":
        return f"${formatted}"
    return f"{currency} {formatted}".strip()


def readable_link(doctype, value, title_field):
    if value in (None, ""):
        return None
    try:
        import frappe

        return frappe.db.get_value(doctype, value, title_field) or value
    except Exception:
        return value


def get_student_academic_activity(student):
    try:
        import frappe
    except ImportError:
        return {}

    attendance_rows = permission_aware_student_rows(
        frappe,
        "Student Attendance",
        student,
        ("name", "date", "status", "course_schedule", "student_group"),
        limit=200,
    )
    statuses = [str(row.get("status") or "").strip().lower() for row in attendance_rows]
    present = sum(status in {"present", "late", "half day", "work from home"} for status in statuses)
    absent = sum(status == "absent" for status in statuses)
    attendance_rate = (present / len(attendance_rows) * 100) if attendance_rows else None

    assessment_results = permission_aware_student_rows(
        frappe,
        "Assessment Result",
        student,
        ("name", "course", "assessment_plan", "grade", "score", "total_score", "maximum_score", "modified"),
        limit=20,
    )
    return {
        "attendance": {
            "total": len(attendance_rows),
            "present": present,
            "absent": absent,
            "attendance_rate": attendance_rate,
        },
        "assessment_results": assessment_results,
    }


def permission_aware_student_rows(frappe, doctype, student, candidate_fields, limit):
    try:
        if not frappe.has_permission(doctype, "read"):
            return []
        meta = frappe.get_meta(doctype)
        fields = [field for field in candidate_fields if field == "name" or meta.has_field(field)]
        return frappe.get_list(
            doctype,
            filters={"student": student},
            fields=fields,
            order_by="modified desc",
            limit_page_length=limit,
        )
    except Exception:
        return []
