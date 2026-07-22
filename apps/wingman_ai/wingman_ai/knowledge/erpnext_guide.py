EXPLANATION_KEYWORDS = (
    "explain",
    "what is",
    "what does",
    "used for",
    "purpose",
    "tell me about",
    "about this",
    "about that",
    "describe",
    "how is this used",
    "what can i do",
    "profile",
)


WORKSPACE_GUIDES = {
    "crm": {
        "overview": "The CRM workspace is used to manage customer-facing sales activity from lead capture through opportunity follow-up and customer engagement.",
        "uses": [
            "Track Leads, Opportunities, Customers, Contacts, and Campaigns.",
            "Review sales activity and keep ownership clear across the team.",
            "Move qualified prospects toward quotations, orders, and long-term customer records.",
        ],
        "next": [
            'Ask "open Lead" to review leads.',
            'Ask "open Opportunity" to inspect active opportunities.',
            'Ask "open customer Prince" to open a specific customer record.',
        ],
    },
    "sales pipeline": {
        "overview": "The Sales Pipeline workspace is used to monitor selling progress from early prospects through won opportunities.",
        "uses": [
            "Track pipeline health, open opportunities, and recent movement.",
            "Prioritize follow-ups, stalled deals, and ownership gaps.",
            "Give sales teams a working view of what needs attention next.",
        ],
        "next": [
            'Ask "open Opportunity" to review opportunities.',
            'Ask "open Lead" to inspect new leads.',
            'Ask "open sales order SAL-ORD-2026-00001" to open a specific order.',
        ],
    },
    "selling": {
        "overview": "The Selling workspace is used to manage the order-to-customer side of Talisma OneCampus.",
        "uses": [
            "Work with Customers, Quotations, Sales Orders, Delivery Notes, and Sales Invoices.",
            "Track sales documents from inquiry through fulfillment and billing.",
            "Keep customer commercial activity organized in one place.",
        ],
        "next": [
            'Ask "open Customer" to view customers.',
            'Ask "open Sales Order" to review orders.',
            'Ask "open quotation SAL-QTN-2026-00001" to open a specific quotation.',
        ],
    },
    "buying": {
        "overview": "The Buying workspace is used to manage supplier purchasing activity.",
        "uses": [
            "Work with Suppliers, Material Requests, Purchase Orders, and Purchase Receipts.",
            "Track procurement requests and supplier commitments.",
            "Support purchase planning, receiving, and supplier follow-up.",
        ],
        "next": [
            'Ask "open Supplier" to view suppliers.',
            'Ask "open Purchase Order" to review purchase orders.',
            'Ask "open material request MAT-MR-2026-00001" to open a specific request.',
        ],
    },
    "stock": {
        "overview": "The Stock workspace is used to manage inventory, warehouses, and material movement.",
        "uses": [
            "Review Items, Warehouses, Stock Entries, and inventory balances.",
            "Track material transfers, receipts, issues, and adjustments.",
            "Support inventory control and operational visibility.",
        ],
        "next": [
            'Ask "open Item" to view item masters.',
            'Ask "open Warehouse" to inspect warehouses.',
            'Ask "open Stock Entry" to review stock movements.',
        ],
    },
    "accounting": {
        "overview": "The Accounting workspace is used to manage financial transactions, ledgers, and financial reports.",
        "uses": [
            "Work with Sales Invoices, Purchase Invoices, Payment Entries, and Journal Entries.",
            "Review receivables, payables, ledgers, and financial statements.",
            "Support finance operations and period-end review.",
        ],
        "next": [
            'Ask "open Sales Invoice" to review sales invoices.',
            'Ask "open Payment Entry" to review payments.',
            'Ask "open General Ledger" to inspect ledger activity.',
        ],
    },
    "manufacturing": {
        "overview": "The Manufacturing workspace is used to plan and execute production activity.",
        "uses": [
            "Work with BOMs, Work Orders, Job Cards, and production planning.",
            "Track material requirements and production progress.",
            "Support shop-floor execution and manufacturing visibility.",
        ],
        "next": [
            'Ask "open Work Order" to review production orders.',
            'Ask "open BOM" to inspect bills of materials.',
            'Ask "open Job Card" to review shop-floor work.',
        ],
    },
    "projects": {
        "overview": "The Projects workspace is used to organize project delivery, tasks, time, and progress.",
        "uses": [
            "Track Projects, Tasks, Timesheets, and project milestones.",
            "Coordinate ownership, deadlines, and delivery status.",
            "Support project execution and management reporting.",
        ],
        "next": [
            'Ask "open Project" to view projects.',
            'Ask "open Task" to review tasks.',
            'Ask "open timesheet TS-2026-00001" to inspect time entries.',
        ],
    },
}


DOCTYPE_HINTS = {
    "Lead": "Leads represent early sales prospects that may be qualified into opportunities or customers.",
    "Opportunity": "Opportunities track qualified sales potential, expected value, stage, and follow-up ownership.",
    "Customer": "Customers store the approved customer master data used across selling, accounting, and service flows.",
    "Sales Order": "Sales Orders capture confirmed customer demand before delivery and billing.",
    "Quotation": "Quotations document commercial offers shared with prospects or customers.",
    "Item": "Items define goods or services used across buying, selling, stock, and manufacturing.",
    "Supplier": "Suppliers store vendor master data used for procurement and payables.",
}


DOCTYPE_EXAMPLES = {
    "Customer": "Prince",
    "Lead": "LEAD-2026-00001",
    "Opportunity": "CRM-OPP-2026-00001",
    "Sales Order": "SAL-ORD-2026-00001",
    "Quotation": "SAL-QTN-2026-00001",
    "Sales Invoice": "ACC-SINV-2026-00001",
    "Purchase Order": "PUR-ORD-2026-00001",
    "Item": "ITEM-0001",
    "Supplier": "SUPP-0001",
}


DOCUMENT_GUIDES = {
    "Customer": {
        "overview": "This is the customer master profile for {docname}. It is the central record Talisma OneCampus uses for selling, billing, contacts, addresses, and customer-related history.",
        "uses": [
            "Review customer identity, group, territory, billing currency, and default commercial settings.",
            "Manage addresses, contacts, portal access, sales team assignment, and customer-specific preferences.",
            "Use connections to review related quotations, sales orders, invoices, payments, and activity.",
        ],
        "next": [
            'Ask "open customer {docname}" to return to this profile from anywhere.',
            'Ask "open sales order SAL-ORD-2026-00001" to open a specific sales order.',
            'Ask "open Customer" to go back to the full customer list.',
        ],
    },
    "Sales Order": {
        "overview": "This is Sales Order {docname}. It represents confirmed customer demand and is commonly used before delivery and billing.",
        "uses": [
            "Review the customer, items, quantities, rates, taxes, delivery schedule, and order status.",
            "Use linked documents to follow fulfillment, delivery, and invoicing progress.",
            "Keep changes within Talisma OneCampus approval, submit, and permission controls.",
        ],
        "next": [
            'Ask "open sales order {docname}" to return to this order.',
            'Ask "open Customer" to review customer records.',
            'Ask "open Sales Order" to go back to the sales order list.',
        ],
    },
}


def build_fast_context_answer(message, context):
    if not is_explanation_request(message):
        return None

    context_object = context.get("object") or {}
    doctype = context_object.get("doctype")
    docname = context_object.get("docname")
    workspace = context_object.get("workspace") or context.get("workspace") or context.get("module")

    if doctype and docname:
        return build_document_answer(doctype, docname)
    if doctype:
        return build_doctype_answer(doctype)
    if workspace:
        return build_workspace_answer(workspace)

    return {
        "message": format_answer(
            overview="This page is part of Talisma OneCampus Desk, where users access modules, records, reports, and operational workflows.",
            uses=[
                "Navigate to Talisma OneCampus workspaces and lists.",
                "Open documents and review business records.",
                "Use Wingman to find records, explain flows, and prepare guided actions.",
            ],
            next_steps=[
                'Ask "open students" to view student records.',
                'Ask "open Liam Patel" to open a student profile.',
                'Ask "explain this page" from any Talisma OneCampus page for contextual guidance.',
            ],
        ),
        "source": "fast_context",
    }


def is_explanation_request(message):
    text = (message or "").strip().lower()
    return bool(text and any(keyword in text for keyword in EXPLANATION_KEYWORDS))


def build_workspace_answer(workspace):
    normalized = normalize_label(workspace)
    guide = WORKSPACE_GUIDES.get(normalized) or generic_workspace_guide(workspace)
    return {
        "message": format_answer(
            overview=guide["overview"],
            uses=guide["uses"],
            next_steps=guide["next"],
        ),
        "source": "fast_context",
    }


def build_doctype_answer(doctype, docname=None):
    dynamic_answer = build_dynamic_doctype_answer(doctype, docname=docname)
    if dynamic_answer:
        return dynamic_answer

    description = DOCTYPE_HINTS.get(doctype) or f"{doctype} records store and organize business information used by Talisma OneCampus workflows."
    target = f"{doctype} {docname}" if docname else f"the {doctype} list"
    example = get_doctype_example(doctype, docname)
    return {
        "message": format_answer(
            overview=f"You are viewing {target}. {description}",
            uses=[
                f"Review {doctype} records available to your Talisma OneCampus role.",
                "Use filters, linked documents, and activity to understand the business context.",
                "Apply changes only through the normal Talisma OneCampus actions and permission model.",
            ],
            next_steps=[
                f'Ask "open {doctype}" to view the list.',
                f'Ask "open {doctype.lower()} {example}" to open a specific record.',
                "Ask Wingman for a summary or next-step recommendation.",
            ],
        ),
        "source": "fast_context",
    }


def build_dynamic_doctype_answer(doctype, docname=None):
    if docname:
        return None

    try:
        from wingman_ai.erp_intelligence import get_erp_intelligence_service

        summary = get_erp_intelligence_service().describe_doctype(doctype)
    except Exception:
        return None

    message = summary.get("message") if isinstance(summary, dict) else None
    if not message:
        return None

    return {
        "message": message,
        "source": "erp_intelligence_business_summary",
    }


def build_document_answer(doctype, docname):
    guide = DOCUMENT_GUIDES.get(doctype)
    if guide:
        return {
            "message": format_answer(
                overview=guide["overview"].format(docname=docname),
                uses=[item.format(docname=docname) for item in guide["uses"]],
                next_steps=[item.format(docname=docname) for item in guide["next"]],
            ),
            "source": "fast_context",
        }

    return build_doctype_answer(doctype, docname=docname)


def generic_workspace_guide(workspace):
    example_doctype = label_from_workspace(workspace)
    example_record = get_doctype_example(example_doctype)
    return {
        "overview": f"The {workspace} workspace groups Talisma OneCampus tools, records, and reports for that business area.",
        "uses": [
            "Access the most relevant documents and reports from one place.",
            "Review operational work without switching across multiple modules.",
            "Keep daily Talisma OneCampus tasks organized by business function.",
        ],
        "next": [
            f'Ask "open {workspace}" to return to this workspace.',
            f'Ask "open {example_doctype}" to navigate to a list.',
            f'Ask "open {example_doctype.lower()} {example_record}" to open a specific record.',
        ],
    }


def format_answer(overview, uses, next_steps):
    return "\n".join(
        [
            "Overview",
            overview,
            "",
            "Key Uses",
            *[f"- {item}" for item in uses],
            "",
            "What You Can Do Next",
            *[f"- {item}" for item in next_steps],
        ]
    )


def normalize_label(value):
    return " ".join(str(value or "").replace("%20", " ").split()).lower()


def get_doctype_example(doctype, docname=None):
    return docname or DOCTYPE_EXAMPLES.get(doctype) or f"{doctype.upper().replace(' ', '-')}-00001"


def label_from_workspace(workspace):
    normalized = normalize_label(workspace)
    if normalized in ("customer", "customers", "crm"):
        return "Customer"
    if normalized in ("selling", "sales pipeline", "sales"):
        return "Sales Order"
    if normalized == "buying":
        return "Purchase Order"
    if normalized == "stock":
        return "Item"
    return "Customer"
