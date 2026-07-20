from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUT = Path(__file__).resolve().parents[1] / "docs" / "client" / "Talisma_University_Client_User_Guide.docx"
NAVY = RGBColor(18, 48, 74)
BLUE = RGBColor(36, 107, 158)
GOLD = RGBColor(217, 164, 65)
GRAY = RGBColor(86, 96, 105)
LIGHT_BLUE = "E8EEF5"
LIGHT_GOLD = "FFF8E8"
WHITE = RGBColor(255, 255, 255)


def set_cell_shading(cell, fill):
	tc_pr = cell._tc.get_or_add_tcPr()
	shd = tc_pr.find(qn("w:shd"))
	if shd is None:
		shd = OxmlElement("w:shd")
		tc_pr.append(shd)
	shd.set(qn("w:fill"), fill)


def set_cell_width(cell, width_dxa):
	tc_pr = cell._tc.get_or_add_tcPr()
	tc_w = tc_pr.find(qn("w:tcW"))
	if tc_w is None:
		tc_w = OxmlElement("w:tcW")
		tc_pr.append(tc_w)
	tc_w.set(qn("w:w"), str(width_dxa))
	tc_w.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths):
	table.autofit = False
	table.alignment = WD_TABLE_ALIGNMENT.LEFT
	tbl_pr = table._tbl.tblPr
	tbl_w = tbl_pr.find(qn("w:tblW"))
	if tbl_w is None:
		tbl_w = OxmlElement("w:tblW")
		tbl_pr.append(tbl_w)
	tbl_w.set(qn("w:w"), str(sum(widths)))
	tbl_w.set(qn("w:type"), "dxa")
	tbl_ind = tbl_pr.find(qn("w:tblInd"))
	if tbl_ind is None:
		tbl_ind = OxmlElement("w:tblInd")
		tbl_pr.append(tbl_ind)
	tbl_ind.set(qn("w:w"), "120")
	tbl_ind.set(qn("w:type"), "dxa")
	grid = table._tbl.tblGrid
	for child in list(grid):
		grid.remove(child)
	for width in widths:
		col = OxmlElement("w:gridCol")
		col.set(qn("w:w"), str(width))
		grid.append(col)
	for row in table.rows:
		for index, cell in enumerate(row.cells):
			set_cell_width(cell, widths[index])
			cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def set_font(run, size=11, bold=False, color=None, name="Calibri", italic=False):
	run.font.name = name
	run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
	run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
	run.font.size = Pt(size)
	run.bold = bold
	run.italic = italic
	if color:
		run.font.color.rgb = color


def add_paragraph(doc, text="", bold_prefix=None, style=None, after=6):
	p = doc.add_paragraph(style=style)
	p.paragraph_format.space_after = Pt(after)
	p.paragraph_format.line_spacing = 1.25
	if bold_prefix and text.startswith(bold_prefix):
		set_font(p.add_run(bold_prefix), bold=True, color=NAVY)
		set_font(p.add_run(text[len(bold_prefix):]))
	else:
		set_font(p.add_run(text))
	return p


def add_bullet(doc, text, level=0):
	p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
	p.paragraph_format.space_after = Pt(4)
	p.paragraph_format.line_spacing = 1.25
	set_font(p.add_run(text))
	return p


def add_number(doc, text):
	p = doc.add_paragraph(style="List Number")
	p.paragraph_format.space_after = Pt(4)
	p.paragraph_format.line_spacing = 1.25
	set_font(p.add_run(text))
	return p


def add_heading(doc, text, level=1):
	p = doc.add_paragraph(text, style=f"Heading {level}")
	p.paragraph_format.keep_with_next = True
	return p


def add_callout(doc, title, text, fill=LIGHT_GOLD):
	table = doc.add_table(rows=1, cols=1)
	set_table_geometry(table, [9360])
	set_cell_shading(table.cell(0, 0), fill)
	p = table.cell(0, 0).paragraphs[0]
	p.paragraph_format.space_after = Pt(3)
	set_font(p.add_run(title + ": "), bold=True, color=NAVY)
	set_font(p.add_run(text))
	doc.add_paragraph().paragraph_format.space_after = Pt(1)


def add_table(doc, headers, rows, widths):
	table = doc.add_table(rows=1, cols=len(headers))
	table.style = "Table Grid"
	set_table_geometry(table, widths)
	for index, header in enumerate(headers):
		cell = table.rows[0].cells[index]
		set_cell_shading(cell, LIGHT_BLUE)
		p = cell.paragraphs[0]
		set_font(p.add_run(header), bold=True, color=NAVY, size=10)
	for row in rows:
		cells = table.add_row().cells
		for index, value in enumerate(row):
			set_cell_width(cells[index], widths[index])
			cells[index].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
			p = cells[index].paragraphs[0]
			p.paragraph_format.space_after = Pt(2)
			p.paragraph_format.line_spacing = 1.15
			set_font(p.add_run(str(value)), size=9.5)
	doc.add_paragraph().paragraph_format.space_after = Pt(2)
	return table


def add_page_break(doc):
	doc.add_page_break()


def build():
	doc = Document()
	section = doc.sections[0]
	section.top_margin = Inches(1)
	section.bottom_margin = Inches(1)
	section.left_margin = Inches(1)
	section.right_margin = Inches(1)
	section.header_distance = Inches(0.492)
	section.footer_distance = Inches(0.492)

	styles = doc.styles
	normal = styles["Normal"]
	normal.font.name = "Calibri"
	normal.font.size = Pt(11)
	normal.paragraph_format.space_after = Pt(6)
	normal.paragraph_format.line_spacing = 1.25
	for level, size, before, after, color in (
		(1, 16, 18, 10, BLUE),
		(2, 13, 14, 7, BLUE),
		(3, 12, 10, 5, NAVY),
	):
		style = styles[f"Heading {level}"]
		style.font.name = "Calibri"
		style.font.size = Pt(size)
		style.font.bold = True
		style.font.color.rgb = color
		style.paragraph_format.space_before = Pt(before)
		style.paragraph_format.space_after = Pt(after)

	header = section.header.paragraphs[0]
	header.alignment = WD_ALIGN_PARAGRAPH.LEFT
	set_font(header.add_run("TALISMA UNIVERSITY  |  CLIENT USER GUIDE"), size=8.5, bold=True, color=GRAY)
	footer = section.footer.paragraphs[0]
	footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
	set_font(footer.add_run("Demo environment | Synthetic data only"), size=8.5, color=GRAY)

	# Customer-pack cover.
	cover = doc.add_paragraph()
	cover.paragraph_format.space_before = Pt(28)
	cover.paragraph_format.space_after = Pt(4)
	set_font(cover.add_run("CLIENT ENABLEMENT GUIDE"), size=10, bold=True, color=GOLD)
	title = doc.add_paragraph()
	title.paragraph_format.space_after = Pt(8)
	set_font(title.add_run("Bryan University"), size=31, bold=True, color=NAVY)
	subtitle = doc.add_paragraph()
	subtitle.paragraph_format.space_after = Pt(20)
	set_font(subtitle.add_run("System prerequisites, operating flows, and end-to-end client use cases"), size=14, color=GRAY)
	add_table(doc, ["Guide", "Environment", "Audience"], [["Version 1.0", "Client demonstration", "Admissions, Registrar, Faculty, Administration"]], [2200, 2800, 4360])
	add_callout(doc, "Purpose", "Use this guide to prepare the demonstration site, understand the data model, operate the supported workflows, and explain current MVP boundaries accurately.", LIGHT_GOLD)
	add_heading(doc, "What this demonstration proves", 2)
	for item in [
		"A branded higher-education experience built on Frappe Education and the Talisma institutional foundation.",
		"A connected journey from applicant intake through student, program enrollment, and course enrollment.",
		"Reusable institutional, campus, academic-unit, program, course, instructor, and student records.",
		"A safe isolated environment containing synthetic data only.",
	]:
		add_bullet(doc, item)
	add_callout(doc, "Important scope statement", "This is a demo-ready MVP, not a production registration, official transcript, financial-aid, billing, or FERPA-certification release.", "FCE8E6")

	add_page_break(doc)
	add_heading(doc, "1. Quick start", 1)
	add_table(doc, ["Item", "Value"], [
		["Demo URL", "http://localhost:8082"],
		["Primary workspace", "Bryan University"],
		["Administrator user", "Administrator"],
		["Demonstration password", "TalismaDemo2026!"],
		["Site", "demo.talisma.local"],
		["Data policy", "Synthetic demonstration data only"],
	], [2700, 6660])
	add_heading(doc, "First login", 2)
	for step in [
		"Open http://localhost:8082 in a private browser window or clear previous site data.",
		"Sign in using the assigned demonstration account.",
		"If the desktop opens, select the single Bryan University icon.",
		"Confirm the left sidebar contains education-oriented navigation such as Admissions, Student Management, Academics, Assessment, Attendance, and Reports.",
		"Use Search (Ctrl+K) when a record or tool is not visible in the current sidebar section.",
	]:
		add_number(doc, step)
	add_callout(doc, "Browser recovery", "After configuration changes, log out and sign in again. Desktop icons and sidebar data are loaded in the Frappe boot payload and may survive a normal refresh.")

	add_heading(doc, "2. User roles and responsibilities", 1)
	add_table(doc, ["Persona", "Primary responsibility", "Typical records"], [
		["Admissions Officer", "Capture and progress applications", "Student Applicant, Student Admission, Program"],
		["Registrar", "Maintain student and enrollment records", "Student, Program Enrollment, Course Enrollment"],
		["Faculty", "Review rosters, attendance, and results", "Instructor, Student Group, Attendance, Assessment Result"],
		["Academic Administrator", "Maintain catalog and academic calendar", "Academic Year, Academic Term, Program, Course"],
		["System Administrator", "Control users, configuration, backups, and environment", "User, Role, System Settings"],
	], [1900, 3500, 3960])
	add_callout(doc, "Demo access", "The current demonstration uses broad administrative access for speed. A production implementation must use least-privilege roles, campus or academic-unit scoping, and tested FERPA controls.", "FCE8E6")

	add_page_break(doc)
	add_heading(doc, "3. Prerequisites and setup order", 1)
	add_paragraph(doc, "Records should be created in dependency order. Skipping foundation records produces broken links or incomplete reporting.")
	add_table(doc, ["Sequence", "Required record", "Why it comes first"], [
		["1", "Institution", "Defines the legal and operating institution."],
		["2", "Address and Campus", "Establishes the physical or virtual delivery location."],
		["3", "Academic Unit Types and Units", "Defines colleges, schools, and owning departments."],
		["4", "Academic Year and Term", "Defines the dates used by admissions and enrollment."],
		["5", "Programs", "Defines the credential pathway and owning academic unit."],
		["6", "Courses", "Defines catalog offerings linked to an academic unit."],
		["7", "Instructors", "Defines teaching personnel linked to an academic unit."],
		["8", "Applicants and Students", "Creates people records for lifecycle processing."],
		["9", "Program Enrollment", "Places a student into a program, year, term, and campus."],
		["10", "Course Enrollment", "Registers the enrolled student into individual courses."],
	], [1100, 3000, 5260])
	add_heading(doc, "Configured demonstration foundation", 2)
	add_table(doc, ["Domain", "Demonstration data"], [
		["Institution", "Talisma State University (TSU)"],
		["Campus", "Main Campus, Boston, Massachusetts"],
		["Academic units", "College of Arts and Sciences; School of Computing"],
		["Calendar", "Academic Year 2026-2027; Fall 2026"],
		["Programs", "BS Computer Science; MS Data Science"],
		["Catalog", "Six CS/DS courses"],
		["People", "Three instructors, three applicants, six students"],
		["Enrollments", "Six program enrollments and eighteen course enrollments"],
	], [2500, 6860])

	add_page_break(doc)
	add_heading(doc, "4. End-to-end lifecycle", 1)
	add_callout(doc, "Lifecycle", "Applicant -> Admissions decision -> Student -> Program Enrollment -> Course Enrollment -> Attendance and assessment -> Academic record.", LIGHT_BLUE)
	add_heading(doc, "Use case A: Applicant intake and decision", 2)
	for step in [
		"Navigate to Admissions > Student Applicant.",
		"Create or open an applicant and confirm name, email, intended Program, Academic Year, Academic Term, and Campus.",
		"Set the application status to Applied when the application is complete enough for review.",
		"Progress the status to Approved or Rejected after the institutional decision.",
		"Use Admitted when the applicant accepts and is ready for student creation or downstream enrollment processing.",
	]:
		add_number(doc, step)
	add_table(doc, ["Status", "Meaning", "Next action"], [
		["Applied", "Application received", "Review completeness and eligibility"],
		["Approved", "Institution approved admission", "Communicate decision and collect acceptance"],
		["Rejected", "Institution declined admission", "Record final disposition"],
		["Admitted", "Applicant accepted for the demo flow", "Create or associate Student record"],
	], [1800, 3500, 4060])

	add_heading(doc, "Use case B: Student record creation", 2)
	for step in [
		"Open Student from Student Management.",
		"Create the student using a unique institutional email address.",
		"Confirm the Home Campus is populated.",
		"Review the student record before creating program enrollment; avoid duplicate person records.",
	]:
		add_number(doc, step)
	add_callout(doc, "Data-quality rule", "Search by email and legal name before creating a Student. The MVP does not yet provide production-grade identity matching or merge governance in the user interface.")

	add_page_break(doc)
	add_heading(doc, "5. Enrollment workflows", 1)
	add_heading(doc, "Use case C: Program enrollment", 2)
	for step in [
		"Navigate to Student Management > Program Enrollment.",
		"Select the Student and the approved Program.",
		"Set Academic Year to 2026-2027 and Academic Term to Fall 2026.",
		"Set Enrollment Date and Campus.",
		"Save and confirm that the enrollment appears in the program-enrollment list.",
	]:
		add_number(doc, step)
	add_heading(doc, "Use case D: Course enrollment", 2)
	for step in [
		"Navigate to Student Management > Course Enrollment.",
		"Choose the student's Program Enrollment.",
		"Confirm the Student populated from the program enrollment.",
		"Select a Course and set the Enrollment Date.",
		"Save one record for each registered course.",
	]:
		add_number(doc, step)
	add_table(doc, ["Control", "Expected behavior"], [
		["Program context", "Course enrollment references a valid Program Enrollment."],
		["Student consistency", "The student matches the selected Program Enrollment."],
		["Course uniqueness", "Do not create duplicate course enrollment for the same student and term."],
		["Term validity", "Use courses and enrollments appropriate to the selected academic period."],
	], [2700, 6660])

	add_heading(doc, "Use case E: Faculty and academic operations", 2)
	add_paragraph(doc, "The following Education capabilities are available for demonstrations after their required setup records exist:")
	for item in [
		"Instructor records for faculty identity and academic-unit association.",
		"Student Groups for cohort or class roster organization.",
		"Course Schedule for instructional meeting planning.",
		"Student Attendance and attendance tools.",
		"Assessment Plan, Assessment Criteria, Grading Scale, and Assessment Result.",
	]:
		add_bullet(doc, item)
	add_callout(doc, "Current demo boundary", "The seed data establishes instructors and enrollments, but does not fully seed schedules, attendance events, assessment plans, grades, or official transcript output.", "FCE8E6")

	add_page_break(doc)
	add_heading(doc, "6. Navigation and common tasks", 1)
	add_table(doc, ["Goal", "Navigation"], [
		["Review applications", "Admissions > Student Applicant"],
		["Configure admission cycles", "Admissions > Student Admission"],
		["Find students", "Student Management > Student"],
		["Review program enrollments", "Student Management > Program Enrollment"],
		["Review course registrations", "Student Management > Course Enrollment"],
		["Maintain calendar", "Academics > Academic Year / Academic Term"],
		["Maintain catalog", "Academics > Program / Course"],
		["Maintain faculty", "Setup > Instructor"],
		["Review results", "Assessment > Assessment Result"],
		["Run reports", "Reports section or Ctrl+K search"],
	], [3400, 5960])
	add_heading(doc, "List-view operating pattern", 2)
	for step in [
		"Use filters to narrow records by status, program, year, term, campus, or student.",
		"Open a record by selecting its identifier or title.",
		"Use New only after confirming a matching record does not already exist.",
		"Save changes and verify the record returns to the expected list or workflow state.",
		"Use browser Back cautiously after saving; prefer breadcrumbs and sidebar navigation.",
	]:
		add_number(doc, step)

	add_heading(doc, "7. Demonstration scenarios", 1)
	add_table(doc, ["Scenario", "Records to show", "Client message"], [
		["Admissions pipeline", "Avery Johnson, Jordan Lee, Taylor Morgan", "Show Applied, Approved, and Admitted stages."],
		["Student profile", "Alex Carter or Priya Shah", "Show institutional email and Home Campus."],
		["Program progression", "BS Computer Science enrollment", "Show program, Fall 2026, and Main Campus."],
		["Course registration", "Three course enrollments per student", "Show connected academic activity without duplicate entry."],
		["Institutional ownership", "Program/Course Academic Unit", "Show School of Computing ownership."],
	], [2200, 3200, 3960])

	add_page_break(doc)
	add_heading(doc, "8. Data stewardship and operating controls", 1)
	for item in [
		"Use synthetic data only in the demonstration environment.",
		"Do not enter real student PII, financial information, health information, or protected education records.",
		"Do not share the demonstration administrator password outside the approved demo team.",
		"Do not use this environment to issue official transcripts, bills, aid awards, or regulatory reports.",
		"Before production, configure least-privilege roles, institutional scoping, audit review, backup/restore, retention, and FERPA procedures.",
	]:
		add_bullet(doc, item)
	add_heading(doc, "MVP capability classification", 2)
	add_table(doc, ["Capability", "Current position"], [
		["Institution, campus, academic unit", "Implemented Talisma foundation"],
		["Programs, courses, instructors", "Reused Education with Talisma links"],
		["Applicants and students", "Demo-ready Education records"],
		["Program and course enrollment", "Demo-ready basic records"],
		["Attendance and assessment", "Available Education foundation; not fully seeded"],
		["Official transcript", "Not production-ready"],
		["Student finance and financial aid", "Out of current MVP scope"],
		["FERPA controls and certification", "Requires production security design and validation"],
	], [3500, 5860])

	add_heading(doc, "9. Troubleshooting", 1)
	add_table(doc, ["Symptom", "Resolution"], [
		["Old icons or sidebar remain", "Log out completely, close the tab, reopen localhost:8082, and sign in again."],
		["Bryan icon does not open", "Use Ctrl+K and search Bryan University; report the exact message to the demo administrator."],
		["Page not found", "Return to /desk, sign out, sign in, then use the desktop icon rather than an old bookmark."],
		["CSS or logo missing", "Hard refresh with Ctrl+Shift+R and confirm the URL uses port 8082."],
		["Record cannot save", "Review mandatory fields and linked prerequisites such as Campus, Academic Year, Term, or Program."],
		["Duplicate record warning", "Cancel creation and search for the existing student, program, course, or enrollment."],
	], [2800, 6560])

	add_page_break(doc)
	add_heading(doc, "10. Client demonstration checklist", 1)
	add_heading(doc, "Before the session", 2)
	for item in [
		"Confirm http://localhost:8082 loads and the login page is branded.",
		"Confirm the Bryan University desktop is the only visible app icon.",
		"Open Bryan University and confirm sidebar navigation loads.",
		"Verify applicants, students, programs, courses, instructors, and enrollments are present.",
		"Use a private browser window or log out of unrelated accounts.",
		"Prepare the client narrative and disclose MVP boundaries.",
	]:
		add_bullet(doc, item)
	add_heading(doc, "Recommended 12-minute walkthrough", 2)
	add_table(doc, ["Time", "Action", "Outcome"], [
		["0-2 min", "Open Bryan University and explain the institutional foundation.", "Client understands the product context."],
		["2-5 min", "Show three applicants at different decision stages.", "Client sees the admissions pipeline."],
		["5-7 min", "Open a student and program enrollment.", "Client sees student-to-program continuity."],
		["7-9 min", "Show course enrollments and catalog ownership.", "Client sees registration and academic structure."],
		["9-11 min", "Show faculty, attendance, assessment, and reporting navigation.", "Client sees the expansion path."],
		["11-12 min", "State MVP boundaries and proposed next phase.", "Expectations remain accurate."],
	], [1300, 4700, 3360])

	add_heading(doc, "11. Glossary", 1)
	add_table(doc, ["Term", "Definition"], [
		["Applicant", "A prospective student with an application under review."],
		["Student", "An admitted person represented in the student record system."],
		["Program", "A credential pathway such as BS Computer Science."],
		["Course", "A catalog unit of instruction."],
		["Program Enrollment", "A student's placement into a program and academic period."],
		["Course Enrollment", "A student's registration in a specific course."],
		["Academic Unit", "A college, school, or department that owns academic activity."],
		["Workspace", "A role-oriented Frappe page containing shortcuts, cards, and navigation."],
	], [2600, 6760])

	add_callout(doc, "End state", "A successful demonstration ends with a client understanding how Bryan University connects institutional structure, admissions, student records, programs, and course registration - and which production capabilities remain to be implemented.", LIGHT_BLUE)

	OUT.parent.mkdir(parents=True, exist_ok=True)
	doc.save(OUT)
	print(OUT)


if __name__ == "__main__":
	build()
