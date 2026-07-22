from wingman_ai.ai.errors import invalid_prompt
from wingman_ai.prompts.registry import get_prompt


class PromptManager:
    def build(self, template_name, message, context=None, purpose="general"):
        template = get_prompt(template_name)
        context = context or {}
        context_object = context.get("object") or {}

        variables = context.get("variables") or {}
        user_prompt = template["user_template"].format(
            purpose=purpose,
            summary=context.get("summary") or "No page context available",
            route=context_object.get("route") or [],
            workspace=context_object.get("workspace") or "not applicable",
            module=context.get("module") or "not applicable",
            doctype=context_object.get("doctype") or "not applicable",
            docname=context_object.get("docname") or "not applicable",
            variables=format_variables(variables),
            message=message,
        )

        validate_prompt(user_prompt)
        return {
            "name": template["name"],
            "version": template["version"],
            "system_prompt": "\n".join(template.get("system_prompt") or []),
            "developer_prompt": "\n".join(template.get("developer_prompt") or []),
            "user_prompt": user_prompt,
        }


def format_variables(variables):
    if not variables:
        return "- none"

    return "\n".join(f"- {key}: {value}" for key, value in sorted(variables.items()))


def validate_prompt(prompt):
    if not prompt or not prompt.strip():
        raise invalid_prompt("Prompt template produced an empty prompt.")

    if len(prompt) > 24000:
        raise invalid_prompt("Prompt context is too large.")
