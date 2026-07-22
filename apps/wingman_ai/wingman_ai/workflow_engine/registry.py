from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RuntimeWorkflowRegistration:
    """Configuration-only registration for a DocType handled by the runtime workflow engine."""

    doctype: str
    operations: tuple = ("create",)
    aliases: tuple = ()


class WorkflowRegistry:
    def __init__(self):
        self._registrations = {}
        self._aliases = {}

    def register(self, doctype, operations=("create",), aliases=()):
        registration = RuntimeWorkflowRegistration(
            doctype=doctype,
            operations=tuple(operations or ()),
            aliases=tuple(alias for alias in aliases or () if alias),
        )
        self._registrations[doctype] = registration
        for alias in registration.aliases:
            self._aliases[normalize(alias)] = doctype
        self._aliases[normalize(doctype)] = doctype
        return registration

    def get(self, doctype):
        return self._registrations.get(doctype)

    def supports(self, doctype, operation="create"):
        registration = self.get(doctype)
        return bool(registration and operation in registration.operations)

    def resolve_doctype(self, message=None, intent=None, operation="create"):
        structured = getattr(intent, "structured_intent", None) or {}
        entity = structured.get("detected_entity") or {}
        entity_value = entity.get("value")
        if self.supports(entity_value, operation=operation):
            return entity_value

        text = normalize(message)
        if not text:
            return None

        tokens = set(text.split())
        for alias, doctype in self._aliases.items():
            if self.supports(doctype, operation=operation) and alias and alias in tokens:
                return doctype

        for alias, doctype in self._aliases.items():
            if self.supports(doctype, operation=operation) and alias and re.search(rf"\b{re.escape(alias)}\b", text):
                return doctype
        return None

    def supports_message(self, message=None, intent=None, operation="create"):
        return bool(self.resolve_doctype(message=message, intent=intent, operation=operation))

    def registered_doctypes(self, operation=None):
        doctypes = []
        for doctype, registration in self._registrations.items():
            if operation and operation not in registration.operations:
                continue
            doctypes.append(doctype)
        return doctypes


def build_default_registry():
    registry = WorkflowRegistry()
    registry.register("Opportunity", operations=("create",), aliases=("opportunity", "opportunities", "deal", "deals"))
    return registry


def get_runtime_workflow_registry():
    return _RUNTIME_WORKFLOW_REGISTRY


def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()


_RUNTIME_WORKFLOW_REGISTRY = build_default_registry()
