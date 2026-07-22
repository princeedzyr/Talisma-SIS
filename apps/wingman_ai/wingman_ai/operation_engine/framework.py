from wingman_ai.operation_engine.blueprint import UniversalOperationBlueprintBuilder
from wingman_ai.operation_engine.plan import OperationPlanBuilder
from wingman_ai.preflight_validation import UniversalPreflightValidationEngine
from wingman_ai.review_builder.service import ReviewBuilderService


class UniversalOperationFramework:
    """Shared operation services used by create, update, and future write flows."""

    def __init__(self, erp_service=None, review_builder=None, preflight=None):
        self.erp_service = erp_service
        self.blueprint_builder = UniversalOperationBlueprintBuilder(erp_service=erp_service)
        self.plan_builder = OperationPlanBuilder()
        self.review_builder = review_builder or ReviewBuilderService()
        self.preflight = preflight or UniversalPreflightValidationEngine(erp_service=erp_service)

    def build_blueprint(self, doctype, operation="create", metadata=None):
        return self.blueprint_builder.build(doctype, metadata=metadata, operation=operation)

    def editable_fields(self, blueprint):
        return list((((blueprint or {}).get("fields") or {}).get("editable")) or [])

    def build_create_plan(self, blueprint, **kwargs):
        return self.plan_builder.build_create_plan(blueprint, **kwargs)

    def build_update_plan(self, blueprint, **kwargs):
        return self.plan_builder.build_update_plan(blueprint, **kwargs)

    def build_creation_review(self, doctype, **kwargs):
        return self.review_builder.build_creation_review(doctype, **kwargs)

    def build_update_review(self, doctype, **kwargs):
        return self.review_builder.build_update_review(doctype, **kwargs)

    def validate_create(self, doctype, data=None, fields=None, user=None):
        return self.preflight.validate_create(doctype, data=data, fields=fields, user=user)

    def validate_update(self, doctype, docname, changes=None, fields=None, user=None):
        return self.preflight.validate_update(doctype, docname, changes=changes, fields=fields, user=user)

    def execution_strategy(self, operation):
        return {
            "create": {"erp_method": "insert", "service_method": "create_document"},
            "update": {"erp_method": "save", "service_method": "update_document"},
            "delete": {"erp_method": "delete", "service_method": "delete_document"},
            "read": {"erp_method": "get_doc", "service_method": "read_document"},
            "search": {"erp_method": "get_list", "service_method": "search_documents"},
        }.get(str(operation or "").lower(), {"erp_method": "custom", "service_method": None})
