INTENT_CATEGORIES = (
    "Create",
    "Read",
    "Update",
    "Delete",
    "Search",
    "List",
    "Summarize",
    "Compare",
    "Explain",
    "Recommend",
    "Navigate",
    "Help",
    "Conversation",
    "Greeting",
    "Goodbye",
    "Unknown",
)


ACTION_KEYWORDS = {
    "Create": ("create", "new", "add", "make", "register", "draft"),
    "Read": ("show", "view", "get", "fetch", "details", "profile", "about this", "tell me about"),
    "Update": ("update", "change", "edit", "modify", "set", "qualify", "mark as qualified"),
    "Delete": ("delete", "remove", "discard"),
    "Search": ("search", "find", "look for", "lookup"),
    "List": ("list", "all", "show all"),
    "Summarize": ("summary", "summarize", "brief", "recap", "tell me about"),
    "Compare": ("compare", "versus", "vs", "difference between"),
    "Explain": ("explain", "what is", "what does", "why", "how does", "used for", "purpose"),
    "Recommend": ("recommend", "suggest", "best", "next step", "advise"),
    "Navigate": ("open", "go to", "goto", "navigate", "navigae", "naviagte", "navgate", "naviate", "take me to", "move to", "redirect", "redirect to"),
    "Help": ("help", "what can you do", "commands", "assist"),
    "Conversation": ("thanks", "thank you", "ok", "okay", "yes", "no", "continue"),
    "Greeting": ("hi", "hello", "hey", "good morning", "good afternoon", "good evening"),
    "Goodbye": ("bye", "goodbye", "see you", "close chat"),
}


ENTITY_ALIASES = {
    "Lead": ("lead", "leads", "prospect", "prospects"),
    "Territory": ("territory", "territories", "region", "area"),
    "Lead Source": ("lead source", "lead sources", "source", "channel"),
    "Customer Group": ("customer group", "customer groups"),
    "Opportunity": ("opportunity", "opportunities", "deal", "deals"),
    "Customer": ("customer", "customers", "client", "clients"),
    "Contact": ("contact", "contacts"),
    "Address": ("address", "addresses"),
    "Quotation": ("quotation", "quotations", "quote", "quotes"),
    "Sales Order": ("sales order", "sales orders", "so"),
    "Sales Invoice": ("sales invoice", "sales invoices"),
    "Delivery Note": ("delivery note", "delivery notes"),
    "Payment Entry": ("payment entry", "payment entries"),
    "Purchase Order": ("purchase order", "purchase orders"),
    "Purchase Receipt": ("purchase receipt", "purchase receipts"),
    "Purchase Invoice": ("purchase invoice", "purchase invoices"),
    "Journal Entry": ("journal entry", "journal entries"),
    "Item": ("item", "items", "product", "products", "sku"),
    "Item Group": ("item group", "item groups"),
    "Brand": ("brand", "brands"),
    "UOM": ("uom", "unit of measure", "units of measure"),
    "Supplier": ("supplier", "suppliers", "vendor", "vendors"),
    "Invoice": ("invoice", "invoices", "sales invoice", "purchase invoice"),
    "Payment": ("payment", "payments", "payment entry"),
    "Employee": ("employee", "employees", "staff"),
    "Department": ("department", "departments"),
    "Company": ("company", "companies"),
    "Warehouse": ("warehouse", "warehouses"),
    "User": ("user", "users", "account", "accounts"),
    "Project": ("project", "projects"),
    "Task": ("task", "tasks", "todo", "to do"),
    "Issue": ("issue", "issues", "ticket", "tickets"),
    "Asset": ("asset", "assets"),
    "Program": ("program", "programs"),
    "Course": ("course", "courses"),
    "Degree": ("degree", "degrees"),
    "Academic Year": ("academic year", "academic years"),
    "Academic Term": ("academic term", "academic terms", "term", "semester"),
    "Talisma Curriculum Version": ("curriculum version", "curriculum versions", "curriculum"),
    "Talisma Student Group Hold": ("student group hold", "group hold", "bulk student hold"),
    "Talisma Class Section": ("class section", "class sections", "class schedule", "class scheduling"),
    "Student": ("student", "students"),
    "Student Group": ("student group", "student groups", "student cohort", "student cohorts"),
    "Student Applicant": ("student applicant", "student applicants", "student application", "student applications"),
    "Program Enrollment": ("program enrollment", "program enrolment"),
    "Course Enrollment": ("course enrollment", "course enrolment", "course registration"),
    "Student Attendance": ("student attendance", "attendance record"),
    "Assessment Result": ("assessment result", "assessment results", "grade result"),
    "Patient": ("patient", "patients"),
}


PARAMETER_ALIASES = {
    "territory": ("territory", "region", "area"),
    "lead_source": ("lead source", "source"),
    "sales_person": ("sales person", "salesperson", "sales rep", "owner"),
    "status": ("status", "stage", "state"),
    "priority": ("priority", "urgent", "high priority", "low priority"),
}


WRITE_INTENTS = {"Create", "Update", "Delete"}


def supported_intents():
    return list(INTENT_CATEGORIES)


def supported_entities():
    return sorted(ENTITY_ALIASES.keys())
