from wingman_ai.business_skills.record_creation.service import RecordCreationService
from wingman_ai.business_skills.record_delete.service import RecordDeleteService
from wingman_ai.business_skills.record_update.service import RecordUpdateService
from wingman_ai.erp_service import get_erp_service


class UniversalCreateService:
    def __init__(self, service=None, erp_service=None):
        self.service = service or RecordCreationService(erp_service=erp_service)

    def prepare(self, message, context=None, intent=None):
        return self.service.prepare_create_from_message(message, context=context, intent=intent)

    def execute(self, doctype, data=None, user=None):
        return self.service.create_record(doctype, data or {}, user=user)


class UniversalReadService:
    def __init__(self, erp_service=None):
        self.erp_service = erp_service or get_erp_service()

    def execute(self, doctype, docname, user=None):
        return self.erp_service.read_document(doctype, docname, user=user)


class UniversalSearchService:
    def __init__(self, erp_service=None):
        self.erp_service = erp_service or get_erp_service()

    def execute(self, doctype, text=None, fields=None, filters=None, order_by=None, page=1, page_size=10, user=None):
        return self.erp_service.search_documents(
            doctype,
            text=text,
            fields=fields,
            filters=filters,
            order_by=order_by,
            page=page,
            page_size=page_size,
            user=user,
        )


class UniversalUpdateService:
    def __init__(self, service=None, erp_service=None):
        self.service = service or RecordUpdateService(erp_service=erp_service)

    def prepare(self, message, context=None, intent=None):
        return self.service.prepare_update_from_message(message, context=context, intent=intent)

    def execute(self, doctype, docname, data=None, user=None):
        return self.service.update_record(doctype, docname, data or {}, user=user)


class UniversalDeleteService:
    def __init__(self, service=None, erp_service=None):
        self.service = service or RecordDeleteService(erp_service=erp_service)

    def prepare(self, message, context=None, intent=None):
        return self.service.handle_message(message, context=context, intent=intent)

    def execute(self, doctype, docname, user=None):
        return self.service.delete_record(doctype, docname, user=user)
