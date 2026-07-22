from wingman_ai.erp_intelligence import get_erp_intelligence_service
from wingman_ai.erp_service.config import get_erp_service_config
from wingman_ai.erp_service.models import ResponseBuilder, ValidationIssue
from wingman_ai.erp_service.permissions import ERPPermissionService
from wingman_ai.erp_service.repository import FrappeDocumentRepository
from wingman_ai.erp_service.search import ERPSearchService
from wingman_ai.erp_service.validation import ERPValidationService, safe_validation_message
from wingman_ai.erp_service.workflow import ERPWorkflowService
from wingman_ai.exception_intelligence import get_exception_interceptor
from wingman_ai.logging.service import log_error, log_info, log_warning


class BaseERPService:
    def __init__(self, repository=None, metadata_service=None, config=None):
        self.config = config or get_erp_service_config()
        self.repository = repository or FrappeDocumentRepository()
        self.metadata_service = metadata_service or get_erp_intelligence_service()
        self.permissions = ERPPermissionService(self.repository)
        self.validation = ERPValidationService(self.repository, permission_service=self.permissions)
        self.search = ERPSearchService(self.repository, metadata_service=self.metadata_service, config=self.config)
        self.workflow = ERPWorkflowService(self.repository, metadata_service=self.metadata_service, permission_service=self.permissions)

    def create_document(self, doctype, data=None, user=None):
        response = ResponseBuilder()
        try:
            issues = self.validation.validate_document(doctype, data=data, operation="create", user=user, run_business_hooks=True)["issues"]
            if issues:
                return self.finish_failure(response, "create", doctype, "validation_failed", "Document could not be created because validation failed.", validation_issues=issues, data=data or {}, user=user)
            doc = self.repository.create(doctype, data or {})
            return self.finish_success(response, "create", doctype, self.repository.serialize_doc(doc))
        except Exception as exc:
            issue = ValidationIssue(fieldname=None, issue_type="business_rule", message=safe_validation_message(exc))
            return self.finish_failure(response, "create", doctype, "validation_failed", "Talisma OneCampus did not complete the create action.", validation_issues=[issue], data=data or {}, user=user)

    def read_document(self, doctype, docname, user=None):
        response = ResponseBuilder()
        try:
            issues = self.validation.validate_document(doctype, docname=docname, operation="read", user=user)["issues"]
            if issues:
                return self.finish_failure(response, "read", doctype, "validation_failed", "Document could not be read because validation failed.", validation_issues=issues)
            return self.finish_success(response, "read", doctype, self.repository.serialize_doc(self.repository.read(doctype, docname)))
        except Exception as exc:
            return self.handle_exception(response, exc, "Read document failed", doctype=doctype)

    def update_document(self, doctype, docname, data=None, user=None):
        response = ResponseBuilder()
        try:
            issues = self.validation.validate_document(doctype, data=data, docname=docname, operation="write", user=user, run_business_hooks=True)["issues"]
            if issues:
                return self.finish_failure(response, "update", doctype, "validation_failed", "Document could not be updated because validation failed.", validation_issues=issues, docname=docname, data=data or {}, user=user)
            doc = self.repository.update(doctype, docname, data or {})
            return self.finish_success(response, "update", doctype, self.repository.serialize_doc(doc))
        except Exception as exc:
            issue = ValidationIssue(fieldname=None, issue_type="business_rule", message=safe_validation_message(exc))
            return self.finish_failure(response, "update", doctype, "validation_failed", "Talisma OneCampus did not complete the update action.", validation_issues=[issue], docname=docname, data=data or {}, user=user)

    def delete_document(self, doctype, docname, user=None):
        response = ResponseBuilder()
        try:
            issues = self.validation.validate_document(doctype, docname=docname, operation="delete", user=user)["issues"]
            if issues:
                return self.finish_failure(response, "delete", doctype, "validation_failed", "Document could not be deleted because validation failed.", validation_issues=issues)
            return self.finish_success(response, "delete", doctype, self.repository.delete(doctype, docname))
        except Exception as exc:
            return self.handle_exception(response, exc, "Delete document failed", doctype=doctype)

    def list_documents(self, doctype, fields=None, filters=None, order_by=None, page=1, page_size=None, user=None):
        response = ResponseBuilder()
        try:
            issues = self.permissions.require(doctype, "read", user=user)
            if issues:
                return self.finish_failure(response, "list", doctype, "permission_denied", "Document list could not be read.", validation_issues=issues)
            return self.finish_success(response, "list", doctype, self.search.list_documents(doctype, fields=fields, filters=filters, order_by=order_by, page=page, page_size=page_size))
        except Exception as exc:
            return self.handle_exception(response, exc, "List documents failed", doctype=doctype)

    def search_documents(self, doctype, text=None, fields=None, filters=None, order_by=None, page=1, page_size=None, user=None):
        response = ResponseBuilder()
        try:
            issues = self.permissions.require(doctype, "read", user=user)
            if issues:
                return self.finish_failure(response, "search", doctype, "permission_denied", "Document search could not be performed.", validation_issues=issues)
            return self.finish_success(response, "search", doctype, self.search.search_documents(doctype, text=text, fields=fields, filters=filters, order_by=order_by, page=page, page_size=page_size))
        except Exception as exc:
            return self.handle_exception(response, exc, "Search documents failed", doctype=doctype)

    def global_search(self, text=None, doctypes=None, fields=None, page_size=None, user=None):
        response = ResponseBuilder()
        try:
            allowed_doctypes = []
            warnings = []
            for doctype in doctypes or self.search.get_global_search_doctypes():
                issues = self.permissions.require(doctype, "read", user=user)
                if issues:
                    warnings.append(f"{doctype} was skipped because the current role context cannot read it.")
                    continue
                allowed_doctypes.append(doctype)
            return self.finish_success(response, "global_search", "multiple", self.search.global_search(text=text, doctypes=allowed_doctypes, fields=fields, page_size=page_size), warnings=warnings)
        except Exception as exc:
            return self.handle_exception(response, exc, "Global search failed", doctype="multiple")

    def get_metadata(self, doctype):
        response = ResponseBuilder()
        try:
            return self.finish_success(response, "metadata", doctype, self.metadata_service.get_doctype_metadata(doctype))
        except Exception as exc:
            return self.handle_exception(response, exc, "Get metadata failed", doctype=doctype)

    def check_permissions(self, doctype, docname=None, user=None, permissions=None):
        response = ResponseBuilder()
        try:
            return self.finish_success(response, "permissions", doctype, self.permissions.check_many(doctype, docname=docname, user=user, permissions=permissions))
        except Exception as exc:
            return self.handle_exception(response, exc, "Permission check failed", doctype=doctype)

    def validate_document(self, doctype, data=None, docname=None, operation="read", user=None, run_business_hooks=False):
        response = ResponseBuilder()
        try:
            result = self.validation.validate_document(doctype, data=data, docname=docname, operation=operation, user=user, run_business_hooks=run_business_hooks)
            return self.finish_success(response, "validate", doctype, result, validation_issues=result.get("issues") or [])
        except Exception as exc:
            return self.handle_exception(response, exc, "Document validation failed", doctype=doctype)

    def get_workflow(self, doctype, docname=None, user=None):
        response = ResponseBuilder()
        try:
            return self.finish_success(response, "workflow", doctype, self.workflow.get_workflow(doctype, docname=docname, user=user))
        except Exception as exc:
            return self.handle_exception(response, exc, "Workflow lookup failed", doctype=doctype)

    def apply_workflow_action(self, doctype, docname, action, user=None):
        response = ResponseBuilder()
        try:
            issues = self.permissions.require(doctype, "write", docname=docname, user=user)
            if issues:
                return self.finish_failure(response, "workflow_action", doctype, "permission_denied", "Workflow action could not be applied.", validation_issues=issues)
            result = self.workflow.apply_action(doctype, docname, action, user=user)
            if not result.get("applied"):
                return self.finish_failure(response, "workflow_action", doctype, "workflow_validation_failed", result.get("message") or "Workflow action is not available.")
            return self.finish_success(response, "workflow_action", doctype, result)
        except Exception as exc:
            return self.handle_exception(response, exc, "Workflow action failed", doctype=doctype)

    def finish_success(self, response, operation, doctype, result=None, warnings=None, validation_issues=None):
        payload = response.success(result, warnings=warnings, validation_issues=validation_issues).to_dict()
        log_info(
            "ERP service operation completed",
            operation=operation,
            doctype=doctype,
            trace_id=payload.get("trace_id"),
            execution_time_ms=payload.get("execution_time_ms"),
        )
        return payload

    def finish_failure(self, response, operation, doctype, code, message, validation_issues=None, warnings=None, **context):
        payload = response.failure(code, message, validation_issues=validation_issues, warnings=warnings).to_dict()
        payload = get_exception_interceptor().attach_to_response(
            payload,
            context={
                **context,
                "operation": operation,
                "doctype": doctype,
                "failure_stage": code,
                "erpnext_api": f"UniversalERPService.{operation}",
                "component": "UniversalERPService",
            },
        )
        log_warning(
            "ERP service operation failed",
            operation=operation,
            doctype=doctype,
            code=code,
            trace_id=payload.get("trace_id"),
            execution_time_ms=payload.get("execution_time_ms"),
        )
        return payload

    def handle_exception(self, response, exc, message, **context):
        payload = response.exception(exc).to_dict()
        operation = str(message or "operation").replace(" failed", "").lower().replace(" ", "_")
        payload = get_exception_interceptor().attach_to_response(
            payload,
            context={
                **context,
                "operation": operation,
                "failure_stage": message,
                "erpnext_api": "UniversalERPService",
                "component": "UniversalERPService",
            },
        )
        log_error(
            message,
            error_type=type(exc).__name__,
            trace_id=payload.get("trace_id"),
            execution_time_ms=payload.get("execution_time_ms"),
            **context,
        )
        return payload


class UniversalERPService(BaseERPService):
    pass


_SERVICE = None


def get_erp_service():
    global _SERVICE
    if _SERVICE is None:
        log_info("Universal ERP service initialized")
        _SERVICE = UniversalERPService()
    return _SERVICE
