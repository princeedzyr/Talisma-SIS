from wingman_ai.crm_crud.metadata import CRMMetadataService
from wingman_ai.crm_crud.recommendations import CRMRecommendationService
from wingman_ai.crm_crud.ui_components import component_for_field
from wingman_ai.conversation_decision_policy import can_use_metadata_default
from wingman_ai.field_filters import is_editable_business_field
from wingman_ai.operation_engine import CreationBlueprintBuilder


CRUD_OPERATIONS = {"create", "read", "update", "delete", "search"}


class CRUDBlueprintBuilder:
    """Builds one metadata-driven CRUD blueprint for all CRM DocTypes."""

    def __init__(self, erp_service=None, metadata_service=None, recommendation_service=None):
        self.metadata_service = metadata_service or CRMMetadataService(erp_service=erp_service)
        self.creation_blueprint_builder = CreationBlueprintBuilder(erp_service=erp_service)
        self.recommendations = recommendation_service or CRMRecommendationService()

    def build(self, doctype, operation="create", metadata=None):
        operation = normalize_operation(operation)
        metadata = metadata or self.metadata_service.get_metadata(doctype)
        base = self.creation_blueprint_builder.build(doctype, metadata=metadata)
        fields = base.get("fields") or {}
        editable_fields = [field for field in fields.get("all") or [] if is_editable_business_field(field)]
        primary_fieldname = (base.get("primary_field") or {}).get("fieldname")
        safe_default_values = {
            field.get("fieldname"): field.get("default")
            for field in editable_fields
            if field.get("fieldname")
            and field.get("default") not in (None, "")
            and can_use_metadata_default(field, primary_fieldname=primary_fieldname)
        }

        blueprint = {
            **base,
            "operation": operation,
            "raw_default_values": base.get("default_values") or {},
            "default_values": safe_default_values,
            "operations": self.operation_matrix(base),
            "module": (metadata or {}).get("module"),
            "ui_components": {
                field.get("fieldname"): component_for_field(field)
                for field in editable_fields
                if field.get("fieldname")
            },
            "dependency_rules": self.dependency_rules(base),
            "validation_rules": base.get("validation_metadata") or {},
            "permission_rules": base.get("permission_rules") or [],
            "workflow_rules": base.get("workflow_rules") or [],
            "business_fieldnames": [field.get("fieldname") for field in editable_fields if field.get("fieldname")],
            "readonly_fieldnames": [field.get("fieldname") for field in fields.get("read_only") or [] if field.get("fieldname")],
            "hidden_fieldnames": [field.get("fieldname") for field in fields.get("hidden") or [] if field.get("fieldname")],
            "virtual_fieldnames": [field.get("fieldname") for field in fields.get("virtual") or [] if field.get("fieldname")],
        }
        blueprint["post_operation_recommendations"] = self.recommendations.build(blueprint, operation=operation)
        return blueprint

    def operation_matrix(self, blueprint):
        permission_rules = blueprint.get("permission_rules") or []
        return {
            "create": {"uses": "RecordCreationService", "permission": "create", "metadata_driven": True},
            "read": {"uses": "ERPService.read_document", "permission": "read", "metadata_driven": True},
            "update": {"uses": "RecordUpdateService", "permission": "write", "metadata_driven": True},
            "delete": {"uses": "RecordDeleteService", "permission": "delete", "metadata_driven": True},
            "search": {"uses": "ERPService.search_documents", "permission": "read", "metadata_driven": True},
            "permission_rules_loaded": bool(permission_rules),
        }

    def dependency_rules(self, blueprint):
        dependencies = []
        for link in blueprint.get("links") or []:
            dependencies.append(
                {
                    "fieldname": link.get("fieldname"),
                    "label": link.get("label"),
                    "target_doctype": link.get("target_doctype"),
                    "required": bool(link.get("required")),
                    "resolver": "UniversalLinkResolutionEngine",
                    "create_missing": True,
                }
            )
        for table in blueprint.get("child_tables") or []:
            dependencies.append(
                {
                    "fieldname": table.get("fieldname"),
                    "label": table.get("label"),
                    "target_doctype": table.get("child_doctype"),
                    "required": bool(table.get("required")),
                    "resolver": "ChildTableConversation",
                    "create_missing": False,
                }
            )
        return dependencies


def normalize_operation(operation):
    operation = str(operation or "create").lower()
    return operation if operation in CRUD_OPERATIONS else "create"
