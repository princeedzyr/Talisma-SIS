import time
from wingman_ai.api.ai_core import provider_status
from wingman_ai.application.orchestrator import get_orchestrator
from wingman_ai.intent.service import IntentRecognitionService


def quick():
    """Fast import-level deployment check for refresh scripts."""
    from wingman_ai.business_workflows.service import BusinessWorkflowService

    IntentRecognitionService()
    BusinessWorkflowService()
    return {"status": "ok", "check": "quick", "app": "wingman_ai"}

def opportunity_prompt():
    """Validate the exact Opportunity business workflow path used from Desk."""
    started = time.time()
    response = get_orchestrator().handle_message(
        "create opportunity for ABCD Technologies worth 10 lakh",
        raw_context={"route": ["Workspace", "CRM"], "route_type": "Workspace", "workspace": "CRM"},
        user="Administrator",
    )
    elapsed_ms = int((time.time() - started) * 1000)
    workflow = ((response.get("data") or {}).get("business_workflow") or {})
    return {
        "status": response.get("status"),
        "capability": response.get("capability"),
        "elapsed_ms": elapsed_ms,
        "workflow_status": workflow.get("status"),
        "actions": [action.get("label") for action in response.get("actions") or []],
        "message_preview": str(response.get("message") or "")[:240],
    }



def opportunity_profile():
    """Profile the exact Opportunity workflow path used from Desk."""
    from wingman_ai.application.intent_router import detect_intent
    from wingman_ai.business_workflows.service import BusinessWorkflowService, OPPORTUNITY_PARTY_DOCTYPES, opportunity_party_query

    message = "create opportunity for ABCD Technologies worth 10 lakh"
    raw_context = {"route": ["Workspace", "CRM"], "route_type": "Workspace", "workspace": "CRM"}
    context = {"user": "Administrator", "object": {"workspace": "CRM"}, "raw": raw_context}
    stages = []

    def timed(label, callback):
        started = time.time()
        result = callback()
        stages.append({"stage": label, "elapsed_ms": int((time.time() - started) * 1000)})
        return result

    intent = timed("intent_detection", lambda: detect_intent(message, context=context))
    service = BusinessWorkflowService()
    create_result = timed("opportunity_blueprint_and_defaults", lambda: service.build_lightweight_opportunity_goal(message, context=context, intent=intent))
    entity = opportunity_party_query(message, dict(create_result.get("data") or {}))
    party_checks = []

    def run_party_checks():
        for doctype in OPPORTUNITY_PARTY_DOCTYPES:
            started = time.time()
            match = service.find_party_record(doctype, entity, user="Administrator")
            party_checks.append(
                {
                    "doctype": doctype,
                    "elapsed_ms": int((time.time() - started) * 1000),
                    "matched": bool(match),
                    "name": (match or {}).get("name"),
                }
            )
        return party_checks

    timed("party_lookup_total", run_party_checks)
    direct = timed("business_workflow_direct", lambda: service.handle_opportunity_goal(message, context=context, intent=intent))
    full = timed("orchestrator_full", lambda: get_orchestrator().handle_message(message, raw_context=raw_context, user="Administrator"))
    workflow = ((full.get("data") or {}).get("business_workflow") or {})
    return {
        "status": "ok",
        "entity": entity,
        "stages": stages,
        "party_checks": party_checks,
        "direct_capability": getattr(direct, "data", {}).get("executed_capability") if hasattr(direct, "data") else None,
        "full_capability": full.get("capability"),
        "workflow_status": workflow.get("status"),
        "actions": [action.get("label") for action in full.get("actions") or []],
    }

def run():
    """Validate the installed app inside an initialized Frappe site."""
    orchestrator = get_orchestrator()

    response = orchestrator.handle_message(
        "open CRM",
        raw_context={"route": ["Workspace", "Desktop"]},
        user="Administrator",
    )
    action = (response.get("actions") or [{}])[0]
    if response.get("capability") != "navigation" or action.get("type") != "navigate":
        raise RuntimeError("Wingman backend did not load the navigation build")

    document_response = orchestrator.handle_message(
        "open user Administrator",
        raw_context={"route": ["Workspace", "Desktop"]},
        user="Administrator",
    )
    document_action = (document_response.get("actions") or [{}])[0]
    target = document_action.get("target") or {}
    if target.get("kind") != "document" or target.get("route") != ["Form", "User", "Administrator"]:
        raise RuntimeError("Wingman backend did not resolve document navigation")

    provider = provider_status()
    if provider.get("provider") != "ollama":
        raise RuntimeError("Wingman AI Core provider is not available")

    intent = IntentRecognitionService().parse("open CRM", context={"object": {"route": ["Workspace", "Desktop"]}})
    if intent.get("intent_category") != "Navigate":
        raise RuntimeError("Wingman Intent Engine did not classify navigation")

    create_response = orchestrator.handle_message(
        "Create Territory Bengaluru",
        raw_context={"route": ["Form", "Lead", "CRM-LEAD-SMOKE"], "doctype": "Lead", "docname": "CRM-LEAD-SMOKE"},
        user="Administrator",
    )
    create_action = (create_response.get("actions") or [{}])[0]
    if create_response.get("capability") != "create" or create_action.get("method") != "wingman_ai.api.record_creation.create_record":
        raise RuntimeError("Wingman create pipeline did not prepare the record creation action")

    runtime_response = orchestrator.handle_message(
        "Create Opportunity for ABC Technologies worth 10 Lakhs",
        raw_context={"route": ["Workspace", "CRM"], "route_type": "Workspace", "workspace": "CRM"},
        user="Administrator",
    )
    workflow = ((runtime_response.get("data") or {}).get("business_workflow") or {})
    workflow_actions = runtime_response.get("actions") or []
    if (
        runtime_response.get("capability") != "business_workflow"
        or (workflow.get("primary_goal") or {}).get("doctype") != "Opportunity"
        or not workflow.get("execution_graph")
    ):
        raise RuntimeError("Wingman Opportunity workflow did not load")
    if workflow.get("status") not in {"awaiting_confirmation", "awaiting_party_decision", "collecting_inputs"}:
        raise RuntimeError(f"Wingman Opportunity workflow returned unexpected status: {workflow.get('status')}")
    if not any(action.get("label") in {"Create Opportunity", "Create Customer", "Create Lead", "Create Prospect", "Cancel"} for action in workflow_actions):
        raise RuntimeError("Wingman Opportunity workflow did not expose a continuation action")

    return {
        "status": "ok",
        "navigation": response.get("capability"),
        "document_navigation": target,
        "ai": provider,
        "opportunity_workflow_status": workflow.get("status"),
        "opportunity_actions": [action.get("label") for action in workflow_actions],
    }
