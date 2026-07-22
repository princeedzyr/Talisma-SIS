from wingman_ai.application.capability_router import route_capability


WRITE_ACTION_TYPES = {
    "create",
    "update",
    "delete",
    "submit",
    "cancel",
    "send_email",
    "apply_workflow",
    "draft_workflow",
    "prepare_crm_action",
}


class ExecutionService:
    def execute_plan(self, plan):
        result = route_capability(
            intent=plan.intent,
            message=plan.message,
            context=plan.context,
        )
        result.actions = enforce_confirmation(result.actions)
        if any(action.get("requires_confirmation") for action in result.actions):
            result.requires_confirmation = True
        return result


def enforce_confirmation(actions):
    guarded_actions = []
    for action in actions or []:
        action_type = action.get("type")
        if action_type in WRITE_ACTION_TYPES:
            direct_curriculum_create = (
                action_type == "create"
                and action.get("wingman_direct_create") is True
                and ((action.get("payload") or {}).get("doctype") == "Talisma Curriculum Version")
            )
            if direct_curriculum_create:
                guarded_actions.append(action)
                continue
            action = dict(action)
            action["requires_confirmation"] = True
            action["auto_execute"] = False
        guarded_actions.append(action)
    return guarded_actions
