from wingman_ai.crm_crud.blueprint import CRUDBlueprintBuilder
from wingman_ai.crm_crud.discovery import CRMDiscoveryService
from wingman_ai.crm_crud.metadata import CRMMetadataService
from wingman_ai.crm_crud.operations import (
    UniversalCreateService,
    UniversalDeleteService,
    UniversalReadService,
    UniversalSearchService,
    UniversalUpdateService,
)
from wingman_ai.field_filters import is_editable_business_field


class UniversalCRMCRUDFramework:
    """Reference CRM implementation for Wingman's universal operation engine."""

    def __init__(
        self,
        erp_service=None,
        metadata_service=None,
        discovery_service=None,
        blueprint_builder=None,
        create_service=None,
        read_service=None,
        search_service=None,
        update_service=None,
        delete_service=None,
    ):
        self.metadata_service = metadata_service or CRMMetadataService(erp_service=erp_service)
        self.discovery = discovery_service or CRMDiscoveryService(metadata_service=self.metadata_service)
        self.blueprints = blueprint_builder or CRUDBlueprintBuilder(
            erp_service=erp_service,
            metadata_service=self.metadata_service,
        )
        self.create = create_service or UniversalCreateService(erp_service=erp_service)
        self.read = read_service or UniversalReadService(erp_service=erp_service)
        self.search = search_service or UniversalSearchService(erp_service=erp_service)
        self.update = update_service or UniversalUpdateService(erp_service=erp_service)
        self.delete = delete_service or UniversalDeleteService(erp_service=erp_service)
        self.erp_service = erp_service or self.metadata_service.erp_service

    def discover_doctypes(self):
        return self.discovery.discover_doctypes(include_child_tables=False)

    def discover_names(self):
        return self.discovery.discover_names(include_child_tables=False)

    def build_blueprint(self, doctype, operation="create"):
        return self.blueprints.build(doctype, operation=operation)

    def prepare_create(self, message, context=None, intent=None):
        return self.create.prepare(message, context=context, intent=intent)

    def create_record(self, doctype, data=None, user=None):
        return self.create.execute(doctype, data=data, user=user)

    def read_record(self, doctype, docname, user=None):
        return self.read.execute(doctype, docname, user=user)

    def search_records(self, doctype, text=None, fields=None, filters=None, order_by=None, page=1, page_size=10, user=None):
        return self.search.execute(
            doctype,
            text=text,
            fields=fields,
            filters=filters,
            order_by=order_by,
            page=page,
            page_size=page_size,
            user=user,
        )

    def prepare_update(self, message, context=None, intent=None):
        return self.update.prepare(message, context=context, intent=intent)

    def update_record(self, doctype, docname, data=None, user=None):
        return self.update.execute(doctype, docname, data=data, user=user)

    def prepare_delete(self, message, context=None, intent=None):
        return self.delete.prepare(message, context=context, intent=intent)

    def delete_record(self, doctype, docname, user=None):
        return self.delete.execute(doctype, docname, user=user)

    def self_validate(self, user=None, execute_writes=False, sample_data_factory=None):
        results = []
        for row in self.discover_doctypes():
            doctype = row.get("name")
            result = self.validate_doctype(
                doctype,
                user=user,
                execute_writes=execute_writes,
                sample_data=sample_data_factory(doctype) if sample_data_factory else None,
            )
            results.append(result)
        return {
            "success": all(item.get("success") for item in results),
            "module": self.metadata_service.module,
            "doctype_count": len(results),
            "results": results,
        }

    def validate_doctype(self, doctype, user=None, execute_writes=False, sample_data=None):
        checks = {}
        created_name = None
        try:
            blueprint = self.build_blueprint(doctype, operation="create")
            fields = blueprint.get("fields") or {}
            editable = fields.get("editable") or []
            checks["metadata_loads"] = bool(blueprint.get("metadata"))
            checks["blueprint_builds"] = bool(blueprint.get("doctype") == doctype)
            checks["editable_fields_identified"] = all(is_editable_business_field(field) for field in editable)
            checks["required_fields_resolved"] = fields.get("required") is not None
            checks["conditional_required_resolved"] = fields.get("conditional_required") is not None
            checks["link_fields_use_universal_resolution"] = all(
                item.get("resolver") == "UniversalLinkResolutionEngine"
                for item in blueprint.get("dependency_rules") or []
                if item.get("target_doctype")
            )
            checks["recommendations_built"] = bool(blueprint.get("post_operation_recommendations"))
            data = dict(sample_data or sample_payload_from_blueprint(blueprint))
            validation = self.erp_service.validate_document(
                doctype,
                data=data,
                operation="create",
                user=user,
                run_business_hooks=True,
            )
            checks["preflight_validation_succeeds"] = response_success(validation)

            if execute_writes:
                create_response = self.create_record(doctype, data, user=user)
                checks["create_executes"] = response_success(create_response)
                created_name = document_name(create_response.get("result")) if isinstance(create_response, dict) else None
                checks["read_returns_record"] = response_success(self.read_record(doctype, created_name, user=user)) if created_name else False
                checks["search_returns_records"] = response_success(self.search_records(doctype, text=created_name, fields=["name"], user=user)) if created_name else False
                update_payload = update_payload_from_blueprint(blueprint, data)
                checks["update_executes"] = response_success(self.update_record(doctype, created_name, update_payload, user=user)) if created_name and update_payload else True
                checks["delete_executes"] = response_success(self.delete_record(doctype, created_name, user=user)) if created_name else False
            else:
                checks["create_executes"] = "not_run"
                checks["read_returns_record"] = "not_run"
                checks["search_returns_records"] = "not_run"
                checks["update_executes"] = "not_run"
                checks["delete_executes"] = "not_run"

            return {
                "success": all(value is True or value == "not_run" for value in checks.values()),
                "doctype": doctype,
                "checks": checks,
            }
        except Exception as exc:
            return {
                "success": False,
                "doctype": doctype,
                "checks": checks,
                "error": str(exc),
            }


def sample_payload_from_blueprint(blueprint):
    payload = {}
    for field in ((blueprint.get("fields") or {}).get("required") or []):
        fieldname = field.get("fieldname")
        if not fieldname:
            continue
        value = sample_value_for_field(blueprint.get("doctype"), field)
        if value not in (None, "", []):
            payload[fieldname] = value
    return payload


def update_payload_from_blueprint(blueprint, data):
    for field in ((blueprint.get("fields") or {}).get("editable") or []):
        if field.get("fieldtype") not in {"Data", "Small Text", "Text"}:
            continue
        fieldname = field.get("fieldname")
        if not fieldname or fieldname not in data:
            continue
        return {fieldname: f"{data[fieldname]} Updated"}
    return {}


def sample_value_for_field(doctype, field):
    fieldtype = field.get("fieldtype")
    if fieldtype == "Select":
        options = [line.strip() for line in str(field.get("options") or "").replace(",", "\n").splitlines() if line.strip()]
        return options[0] if options else None
    if fieldtype == "Check":
        return 0
    if fieldtype in {"Int", "Float", "Currency", "Percent"}:
        return 1
    if fieldtype == "Date":
        return "2026-07-04"
    if fieldtype == "Datetime":
        return "2026-07-04 09:00:00"
    if fieldtype == "Link":
        return None
    return f"Sample {doctype}"


def response_success(response):
    if not isinstance(response, dict):
        return False
    if "success" in response:
        return bool(response.get("success"))
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    if "valid" in result:
        return bool(result.get("valid"))
    return True


def document_name(result):
    if isinstance(result, dict):
        return result.get("name") or result.get("docname")
    return None


_FRAMEWORK = None


def get_crm_crud_framework():
    global _FRAMEWORK
    if _FRAMEWORK is None:
        _FRAMEWORK = UniversalCRMCRUDFramework()
    return _FRAMEWORK
