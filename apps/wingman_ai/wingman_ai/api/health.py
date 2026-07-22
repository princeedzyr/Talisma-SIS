try:
    import frappe
except ImportError:
    class _FrappeStub:
        @staticmethod
        def whitelist():
            def decorator(fn):
                return fn

            return decorator

    frappe = _FrappeStub()

from wingman_ai.integrations.ai import get_ai_provider_status


@frappe.whitelist()
def ping():
    ai_status = get_ai_provider_status()
    return {
        "status": "ok",
        "app": "wingman_ai",
        "ai": ai_status,
        "message": build_health_message(ai_status),
    }


def build_health_message(ai_status):
    if ai_status.get("provider") == "ollama" and ai_status.get("reachable"):
        return f"Ollama is reachable using {ai_status.get('model')}."

    if ai_status.get("provider") == "ollama":
        return "Ollama is configured but not reachable from the Talisma OneCampus backend container."

    return "No AI provider is configured."
