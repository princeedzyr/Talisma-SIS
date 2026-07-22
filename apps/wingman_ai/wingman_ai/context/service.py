from wingman_ai.application.context_builder import build_context
from wingman_ai.context.models import WingmanContext
from wingman_ai.conversation.state_manager import ConversationStateManager
from wingman_ai.repositories.conversation_repository import (
    get_history,
    get_pending_create_draft,
    get_pending_update_draft,
    get_pending_workflow_session,
)


class ContextService:
    def __init__(self, state_manager=None):
        self.state_manager = state_manager or ConversationStateManager()

    def build(self, raw_context=None, user=None, conversation_id=None, variables=None):
        context = build_context(raw_context=raw_context, user=user)
        context_object = context.get("object") or {}
        conversation_id = conversation_id or context.get("raw", {}).get("conversation_id")
        workspace = context_object.get("workspace")
        conversation_state = self.state_manager.get_state(conversation_id, user=user) if conversation_id else None

        wingman_context = WingmanContext(
            current_user=user,
            current_workspace=workspace,
            conversation_id=conversation_id,
            current_erp_context=context_object,
            current_module=infer_module(context_object),
            variables=variables or context.get("raw", {}).get("variables") or {},
            conversation_history=get_history(conversation_id, user=user) if conversation_id else [],
        )

        context.update(
            {
                "conversation_id": conversation_id,
                "workspace": workspace,
                "module": wingman_context.current_module,
                "variables": wingman_context.variables,
                "history": wingman_context.conversation_history,
                "pending_create_draft": get_pending_create_draft(conversation_id, user=user) if conversation_id else None,
                "pending_update_draft": get_pending_update_draft(conversation_id, user=user) if conversation_id else None,
                "pending_workflow_session": get_pending_workflow_session(conversation_id, user=user) if conversation_id else None,
                "conversation_state": conversation_state,
                "wingman_context": wingman_context.to_dict(),
            }
        )
        return context


def infer_module(context_object):
    workspace = context_object.get("workspace")
    if workspace:
        return workspace

    route = context_object.get("route") or []
    if route and route[0] == "List" and len(route) > 1:
        return route[1]
    if route and route[0] == "Form" and len(route) > 1:
        return route[1]
    if context_object.get("route_type") == "Query Report":
        return context_object.get("report_name")
    return None
