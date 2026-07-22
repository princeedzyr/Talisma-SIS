from copy import deepcopy
from datetime import datetime, timezone

from wingman_ai.repositories.conversation_repository import get_conversation_state, set_conversation_state
from wingman_ai.conversation.state_machine import ConversationStateMachine


STATE_IDLE = "idle"
STATE_CREATE = "create_session"
STATE_UPDATE = "update_session"
STATE_REVIEW = "review_session"
STATE_DEPENDENCY = "dependency_session"
STATE_NAVIGATION = "navigation_session"
STATE_SEARCH = "search_session"
STATE_REPORT = "report_session"
STATE_HELP = "help_session"

STATE_BY_CAPABILITY = {
    "create": STATE_CREATE,
    "update": STATE_UPDATE,
    "navigation": STATE_NAVIGATION,
    "reports": STATE_REPORT,
    "reasoning": STATE_HELP,
}

TASK_CAPABILITIES = {"create", "update", "delete", "reports", "navigation"}
EXPLICIT_CONTEXT_CATEGORIES = {"Read", "Summarize", "Explain", "Recommend", "Search", "List"}
COMPLETION_ACTION_TYPES = {"create", "update", "delete", "submit", "cancel", "apply_workflow"}


class ConversationStateManager:
    def __init__(self, state_machine=None):
        self.state_machine = state_machine or ConversationStateMachine()

    def get_state(self, conversation_id, user=None):
        state = get_conversation_state(conversation_id, user=user) or {}
        return normalize_state(state)

    def attach_to_context(self, context, user=None):
        context = context or {}
        conversation_id = context.get("conversation_id")
        state = self.get_state(conversation_id, user=user) if conversation_id else normalize_state({})
        context["conversation_state"] = state
        return context

    def complete_turn(self, context, intent, result):
        context = context or {}
        conversation_id = context.get("conversation_id")
        if not conversation_id:
            return normalize_state({})

        current = normalize_state(context.get("conversation_state") or self.get_state(conversation_id, user=context.get("user")))
        updated = self.next_state(current, context=context, intent=intent, result=result)
        set_conversation_state(conversation_id, updated, user=context.get("user"))
        return updated

    def next_state(self, current, context=None, intent=None, result=None):
        state = normalize_state(current)
        result_data = getattr(result, "data", {}) or {}
        capability = getattr(intent, "capability", None)
        category = ((getattr(intent, "structured_intent", None) or {}).get("intent_category") or "").strip()
        inner_result = result_data.get("result") or {}

        if inner_result.get("cancelled"):
            updated = self.end_task(state, completed_state=state.get("active_state"), reason="cancelled")
            return self.with_unified_state(updated, context=context, intent=intent, result=result)

        if capability == "create":
            updated = self.state_for_create(state, inner_result, result=result)
            return self.with_unified_state(updated, context=context, intent=intent, result=result)

        if capability == "update":
            updated = self.state_for_update(state, inner_result, result=result)
            return self.with_unified_state(updated, context=context, intent=intent, result=result)

        if capability in STATE_BY_CAPABILITY:
            if capability == "navigation":
                updated = self.end_task(self.set_active(state, STATE_NAVIGATION), completed_state=STATE_NAVIGATION, reason="navigation_complete")
            else:
                updated = self.set_active(state, STATE_BY_CAPABILITY[capability], suppress_context=False)
            return self.with_unified_state(updated, context=context, intent=intent, result=result)

        if category in ("Greeting", "Goodbye", "Help", "Conversation"):
            updated = self.set_active(state, STATE_IDLE, suppress_context=False)
            return self.with_unified_state(updated, context=context, intent=intent, result=result)

        if category in EXPLICIT_CONTEXT_CATEGORIES:
            updated = self.set_active(state, STATE_HELP, suppress_context=False)
            return self.with_unified_state(updated, context=context, intent=intent, result=result)

        if result_data.get("response_mode") in ("conversation", "fast_context", "document_read", "explicit_document_read"):
            updated = self.set_active(state, STATE_IDLE, suppress_context=False)
            return self.with_unified_state(updated, context=context, intent=intent, result=result)

        return self.with_unified_state(state, context=context, intent=intent, result=result)

    def state_for_create(self, state, inner_result, result=None):
        if not inner_result.get("supported"):
            return self.end_task(state, completed_state=STATE_CREATE, reason="unsupported_create")

        if has_pending_dependency(inner_result):
            return self.set_active(state, STATE_DEPENDENCY, parent_state=STATE_CREATE, suppress_context=True)

        if inner_result.get("ready"):
            return self.set_active(state, STATE_REVIEW, parent_state=STATE_CREATE, suppress_context=True)

        if inner_result.get("next_missing_field") or inner_result.get("missing_fields"):
            return self.set_active(state, STATE_CREATE, suppress_context=True)

        if has_completion_action(result):
            return self.set_active(state, STATE_REVIEW, parent_state=STATE_CREATE, suppress_context=True)

        return self.end_task(state, completed_state=STATE_CREATE, reason="create_complete")

    def state_for_update(self, state, inner_result, result=None):
        if not inner_result.get("supported"):
            return self.end_task(state, completed_state=STATE_UPDATE, reason="unsupported_update")

        if has_pending_dependency(inner_result):
            return self.set_active(state, STATE_DEPENDENCY, parent_state=STATE_UPDATE, suppress_context=True)

        if inner_result.get("ready"):
            return self.set_active(state, STATE_REVIEW, parent_state=STATE_UPDATE, suppress_context=True)

        if inner_result.get("next_missing_field") or inner_result.get("stage"):
            return self.set_active(state, STATE_UPDATE, suppress_context=True)

        if has_completion_action(result):
            return self.set_active(state, STATE_REVIEW, parent_state=STATE_UPDATE, suppress_context=True)

        return self.end_task(state, completed_state=STATE_UPDATE, reason="update_complete")

    def set_active(self, state, active_state, parent_state=None, suppress_context=False):
        state = normalize_state(state)
        stack = list(state.get("stack") or [])
        if parent_state and (not stack or stack[-1].get("state") != parent_state):
            stack.append({"state": parent_state, "entered_at": now()})

        state.update(
            {
                "active_state": active_state or STATE_IDLE,
                "stack": stack,
                "suppress_implicit_context": bool(suppress_context),
                "updated_at": now(),
                "unified_state": state.get("unified_state"),
            }
        )
        return state

    def end_task(self, state, completed_state=None, reason=None):
        state = normalize_state(state)
        state.update(
            {
                "active_state": STATE_IDLE,
                "stack": [],
                "last_completed_state": completed_state or state.get("active_state"),
                "completion_reason": reason,
                "suppress_implicit_context": True,
                "updated_at": now(),
                "unified_state": state.get("unified_state"),
            }
        )
        return state

    def with_unified_state(self, state, context=None, intent=None, result=None):
        state = normalize_state(state)
        state["unified_state"] = self.state_machine.build_turn_state(
            context=context,
            intent=intent,
            result=result,
            legacy_state=state,
        )
        return state


def normalize_state(state):
    payload = deepcopy(state or {})
    stack = payload.get("stack")
    if not isinstance(stack, list):
        stack = []
    return {
        "active_state": payload.get("active_state") or STATE_IDLE,
        "stack": stack,
        "last_completed_state": payload.get("last_completed_state"),
        "completion_reason": payload.get("completion_reason"),
        "suppress_implicit_context": bool(payload.get("suppress_implicit_context")),
        "updated_at": payload.get("updated_at"),
        "unified_state": deepcopy(payload.get("unified_state")) if payload.get("unified_state") else None,
    }


def has_pending_dependency(result):
    return bool((result or {}).get("missing_dependencies") or (result or {}).get("missing_link_dependencies"))


def has_completion_action(result):
    return any((action or {}).get("type") in COMPLETION_ACTION_TYPES for action in getattr(result, "actions", []) or [])


def now():
    return datetime.now(timezone.utc).isoformat()
