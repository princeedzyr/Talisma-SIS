import re


CATEGORY_ENVIRONMENT = "Environment Issue"
CATEGORY_CONFIGURATION = "Configuration Issue"
CATEGORY_VALIDATION = "Validation Issue"
CATEGORY_PERMISSION = "Permission Issue"
CATEGORY_DEPENDENCY = "Dependency Issue"
CATEGORY_AUTHENTICATION = "Authentication Issue"
CATEGORY_API = "API Issue"
CATEGORY_FRAMEWORK = "Framework Issue"
CATEGORY_WORKFLOW = "Workflow Issue"
CATEGORY_INTEGRATION = "Integration Issue"
CATEGORY_INFRASTRUCTURE = "Infrastructure Issue"
CATEGORY_UNEXPECTED = "Unexpected Issue"


KNOWLEDGE_BASE = [
    {
        "category": CATEGORY_ENVIRONMENT,
        "patterns": (
            "programmingerror",
            "operationalerror",
            "missing table",
            "doesn't exist",
            "does not exist",
            "unknown column",
            "no module named",
            "module not found",
            "bench migrate",
            "patch",
        ),
        "root_cause": "The Talisma OneCampus environment is missing required schema, module, or migration state.",
        "business_impact": "The requested Talisma OneCampus operation was not completed. Your entered information has been preserved.",
        "resolution": "Ask an ERP Administrator to repair the Talisma OneCampus site setup, then retry from the saved Wingman session.",
        "business_resolution": "Ask an ERP Administrator to repair the Talisma OneCampus site setup, then retry from the saved Wingman session.",
        "admin_resolution": "Run bench migrate, clear cache, clear website cache, and restart the affected Talisma OneCampus services.",
        "team": "ERP Administrator",
        "severity": "Critical",
        "recovery": "Pause operation and retry after the environment is repaired.",
    },
    {
        "category": CATEGORY_PERMISSION,
        "patterns": (
            "permission",
            "not permitted",
            "not allowed",
            "insufficient permission",
            "role",
            "workflow restriction",
        ),
        "root_cause": "Talisma OneCampus permissions or workflow rules do not allow this action for the current role context.",
        "business_impact": "No Talisma OneCampus data was changed.",
        "resolution": "Ask an ERP Administrator to grant the required role or complete the required workflow step.",
        "business_resolution": "Ask an ERP Administrator to review your role or workflow step, then retry from the saved Wingman session.",
        "admin_resolution": "Review Role Permission Manager, User roles, document sharing, and workflow state for the blocked action.",
        "team": "ERP Administrator",
        "severity": "High",
        "recovery": "Pause operation and retry after access is corrected.",
    },
    {
        "category": CATEGORY_DEPENDENCY,
        "patterns": (
            "linkvalidationerror",
            "could not find",
            "not found",
            "missing parent",
            "missing child",
            "references a",
            "linked document",
        ),
        "root_cause": "Talisma OneCampus needs a related record before this operation can continue.",
        "business_impact": "No Talisma OneCampus data was changed. Wingman can continue after the dependency is resolved.",
        "resolution": "Create or select the missing linked record, then retry from the preserved conversation.",
        "business_resolution": "Create or select the missing related record, then continue from the saved Wingman session.",
        "admin_resolution": "Verify the referenced Link field value exists and the current user has permission to read it.",
        "team": "Business User",
        "severity": "Medium",
        "recovery": "Offer dependency creation or record selection.",
    },
    {
        "category": CATEGORY_CONFIGURATION,
        "patterns": (
            "missing company",
            "default company",
            "currency",
            "naming series",
            "email account",
            "default warehouse",
            "setup prerequisite",
            "configuration",
        ),
        "root_cause": "Required Talisma OneCampus setup or company-level configuration is missing.",
        "business_impact": "The operation is paused until the required setup is available.",
        "resolution": "Complete the missing Talisma OneCampus setup value, then retry from the preserved conversation.",
        "business_resolution": "Ask an ERP Administrator to complete the missing Talisma OneCampus setup, then retry from the saved Wingman session.",
        "admin_resolution": "Complete the missing company, currency, naming series, warehouse, email, or module setup value reported in the diagnostic.",
        "team": "ERP Administrator",
        "severity": "High",
        "recovery": "Pause operation and show setup guidance.",
    },
    {
        "category": CATEGORY_VALIDATION,
        "patterns": (
            "validationerror",
            "mandatory",
            "required",
            "duplicate",
            "business rule",
            "cannot",
            "invalid",
        ),
        "root_cause": "Talisma OneCampus validation did not accept one or more values for this operation.",
        "business_impact": "No Talisma OneCampus data was changed.",
        "resolution": "Correct the highlighted field or business condition, then continue.",
        "business_resolution": "Correct the highlighted business detail, then continue the Wingman workflow.",
        "admin_resolution": "Review the DocType validation rule, mandatory field, workflow condition, or linked field that rejected the value.",
        "team": "Business User",
        "severity": "Medium",
        "recovery": "Continue the conversation and collect the corrected value.",
    },
    {
        "category": CATEGORY_AUTHENTICATION,
        "patterns": (
            "authenticationerror",
            "authentication failed",
            "not logged in",
            "login required",
            "session expired",
            "csrf",
            "invalid token",
        ),
        "root_cause": "The Talisma OneCampus session or authentication context is not valid for this operation.",
        "business_impact": "No Talisma OneCampus data was changed. The operation is paused until the user is authenticated.",
        "resolution": "Sign in again or ask an ERP Administrator to verify the authentication configuration.",
        "business_resolution": "Sign in again, then retry from the saved Wingman session.",
        "admin_resolution": "Verify session, CSRF, OAuth, SSO, and API key configuration for the affected user.",
        "team": "ERP Administrator",
        "severity": "High",
        "recovery": "Pause operation until authentication is restored.",
    },
    {
        "category": CATEGORY_WORKFLOW,
        "patterns": (
            "workflowtransitionerror",
            "workflow transition",
            "invalid workflow",
            "workflow action",
            "state transition",
        ),
        "root_cause": "The requested workflow action is not available from the current document state.",
        "business_impact": "No Talisma OneCampus data was changed. The record remains in its current workflow state.",
        "resolution": "Use an available workflow action or ask an ERP Administrator to review the workflow rules.",
        "business_resolution": "Choose an available workflow action, or ask an administrator to review the workflow setup.",
        "admin_resolution": "Review Workflow, Workflow State, allowed roles, and transition conditions for this DocType.",
        "team": "ERP Administrator",
        "severity": "Medium",
        "recovery": "Guide the user to an available workflow action.",
    },
    {
        "category": CATEGORY_API,
        "patterns": (
            "timeout",
            "timed out",
            "connection",
            "server unavailable",
            "rate limit",
            "request failed",
        ),
        "root_cause": "Wingman could not complete the request because an API or connectivity problem occurred.",
        "business_impact": "The operation may not have completed. Wingman preserved the session before retrying.",
        "resolution": "Retry the action. If it repeats, check Talisma OneCampus service health and network connectivity.",
        "business_resolution": "Retry the action. If it repeats, ask support to check Talisma OneCampus connectivity.",
        "admin_resolution": "Check Talisma OneCampus, proxy, worker, websocket, and network health before retrying.",
        "team": "Technical Support",
        "severity": "High",
        "recovery": "Retry using the configured retry policy.",
    },
    {
        "category": CATEGORY_INTEGRATION,
        "patterns": (
            "integration",
            "webhook",
            "api key",
            "external service",
            "remote service",
            "third party",
        ),
        "root_cause": "An external integration required by Talisma OneCampus did not complete successfully.",
        "business_impact": "The Talisma OneCampus operation is paused until the integration becomes available or is corrected.",
        "resolution": "Retry after the integration is available, or ask support to inspect the integration logs.",
        "business_resolution": "Retry after the connected service is available, or ask support to inspect the integration.",
        "admin_resolution": "Check integration credentials, webhook logs, request payloads, and upstream service health.",
        "team": "Technical Support",
        "severity": "High",
        "recovery": "Pause operation and retry after the integration is corrected.",
    },
    {
        "category": CATEGORY_INFRASTRUCTURE,
        "patterns": (
            "redis",
            "mariadb",
            "database server",
            "worker unavailable",
            "queue timeout",
            "socket",
            "service unavailable",
            "connection refused",
        ),
        "root_cause": "A required Talisma OneCampus infrastructure service is unavailable or unstable.",
        "business_impact": "The operation may not have completed. Wingman preserved the session before retrying.",
        "resolution": "Retry after Talisma OneCampus infrastructure health is restored.",
        "business_resolution": "Retry after Talisma OneCampus is stable. If it repeats, ask support to check Talisma OneCampus service health.",
        "admin_resolution": "Check Docker services, MariaDB, Redis, workers, scheduler, websocket, and frontend/backend containers.",
        "team": "Technical Support",
        "severity": "Critical",
        "recovery": "Retry with backoff after infrastructure health is restored.",
    },
    {
        "category": CATEGORY_FRAMEWORK,
        "patterns": (
            "conversation",
            "metadata bug",
            "blueprint",
            "validation engine",
            "wingman",
            "keyerror",
            "attributeerror",
            "typeerror",
        ),
        "root_cause": "Wingman hit an internal framework handling issue.",
        "business_impact": "The operation was stopped safely and the conversation state was preserved.",
        "resolution": "Review the Wingman framework component named in the diagnostic and retry after correction.",
        "business_resolution": "Wingman preserved the session. Ask Wingman Engineering to review the diagnostic, then retry.",
        "admin_resolution": "Review the Wingman framework component, diagnostic ID, and captured operation context.",
        "team": "Wingman Engineering",
        "severity": "High",
        "recovery": "Log diagnostic, preserve session, and retry after a fix.",
    },
]


class ExceptionKnowledgeBase:
    def lookup(self, text):
        return lookup_known_exception(text)

    def classify_issue_type(self, issue_type):
        return classify_issue_type(issue_type)

    def categories(self):
        return [
            CATEGORY_ENVIRONMENT,
            CATEGORY_CONFIGURATION,
            CATEGORY_VALIDATION,
            CATEGORY_PERMISSION,
            CATEGORY_DEPENDENCY,
            CATEGORY_AUTHENTICATION,
            CATEGORY_API,
            CATEGORY_FRAMEWORK,
            CATEGORY_WORKFLOW,
            CATEGORY_INTEGRATION,
            CATEGORY_INFRASTRUCTURE,
            CATEGORY_UNEXPECTED,
        ]


def lookup_known_exception(text):
    normalized = normalize(text)
    for category in (CATEGORY_AUTHENTICATION, CATEGORY_INFRASTRUCTURE, CATEGORY_WORKFLOW, CATEGORY_INTEGRATION):
        entry = find_entry(category)
        if entry and any(pattern in normalized for pattern in entry["patterns"]):
            return dict(entry)
    for entry in KNOWLEDGE_BASE:
        if any(pattern in normalized for pattern in entry["patterns"]):
            return dict(entry)
    return {
        "category": CATEGORY_UNEXPECTED,
        "root_cause": "Wingman received an unexpected Talisma OneCampus or framework failure.",
        "business_impact": "The operation was stopped safely and the conversation state was preserved.",
        "resolution": "Retry once. If the issue repeats, share the diagnostic reference with the support team.",
        "business_resolution": "Retry once. If it repeats, share the diagnostic reference with support.",
        "admin_resolution": "Review the diagnostic ID, operation context, and application logs for the affected request.",
        "team": "Wingman Engineering",
        "severity": "High",
        "recovery": "Log diagnostic and preserve session.",
    }


def find_entry(category):
    for entry in KNOWLEDGE_BASE:
        if entry.get("category") == category:
            return entry
    return None


def classify_issue_type(issue_type):
    normalized = normalize(issue_type)
    if "permission" in normalized:
        return CATEGORY_PERMISSION
    if "authentication" in normalized or "login" in normalized or "session" in normalized:
        return CATEGORY_AUTHENTICATION
    if "link" in normalized or "existence" in normalized or "not found" in normalized:
        return CATEGORY_DEPENDENCY
    if "schema" in normalized or "setup" in normalized:
        return CATEGORY_ENVIRONMENT
    if "configuration" in normalized:
        return CATEGORY_CONFIGURATION
    if "mandatory" in normalized or "validation" in normalized or "business" in normalized:
        return CATEGORY_VALIDATION
    if "workflow" in normalized:
        return CATEGORY_WORKFLOW
    return None


def normalize(value):
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()
