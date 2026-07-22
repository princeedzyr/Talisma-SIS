from wingman_ai.erp_intelligence.cache import ERPKnowledgeCache
from wingman_ai.erp_intelligence.config import get_erp_intelligence_config
from wingman_ai.erp_intelligence.frappe_adapter import FrappeERPAdapter
from wingman_ai.erp_intelligence.interpreter import BusinessMetadataInterpreter
from wingman_ai.erp_intelligence.metadata import MetadataDiscoveryService
from wingman_ai.erp_intelligence.permissions import PermissionIntelligenceService
from wingman_ai.erp_intelligence.relationships import RelationshipDiscoveryService
from wingman_ai.erp_intelligence.search import SearchMetadataService
from wingman_ai.erp_intelligence.workflow import WorkflowDiscoveryService


class ERPIntelligenceService:
    def __init__(self, adapter=None, config=None, cache=None):
        self.adapter = adapter or FrappeERPAdapter()
        self.config = config or get_erp_intelligence_config()
        self.cache = cache or ERPKnowledgeCache(adapter=self.adapter, config=self.config)
        self.metadata = MetadataDiscoveryService(adapter=self.adapter, config=self.config)
        self.relationships = RelationshipDiscoveryService(
            adapter=self.adapter,
            config=self.config,
            metadata_service=self.metadata,
        )
        self.workflow = WorkflowDiscoveryService(adapter=self.adapter, config=self.config)
        self.permissions = PermissionIntelligenceService(adapter=self.adapter, config=self.config)
        self.search = SearchMetadataService(
            adapter=self.adapter,
            config=self.config,
            metadata_service=self.metadata,
            relationship_service=self.relationships,
        )
        self.interpreter = BusinessMetadataInterpreter(intelligence_service=self, config=self.config)

    def list_modules(self):
        return self.cache.get_or_set("modules", self.metadata.list_modules)

    def list_doctypes(self, module=None, include_child_tables=True):
        key = f"doctypes:{module or 'all'}:{int(bool(include_child_tables))}"
        return self.cache.get_or_set(key, lambda: self.metadata.list_doctypes(module=module, include_child_tables=include_child_tables))

    def get_doctype_metadata(self, doctype):
        return self.cache.get_or_set(f"metadata:{doctype}", lambda: self.metadata.get_doctype_metadata(doctype))

    def get_relationships(self, doctype=None):
        key = f"relationships:{doctype or 'all'}"
        return self.cache.get_or_set(key, lambda: self.relationships.get_relationships(doctype=doctype))

    def get_workflow(self, doctype, docname=None, user=None):
        if docname:
            return self.workflow.get_workflow(doctype=doctype, docname=docname, user=user)
        return self.cache.get_or_set(f"workflow:{doctype}", lambda: self.workflow.get_workflow(doctype=doctype, user=user))

    def get_permissions(self, doctype, docname=None, user=None):
        return self.permissions.explain_permissions(doctype=doctype, docname=docname, user=user)

    def get_search_metadata(self, doctype):
        return self.cache.get_or_set(f"search:{doctype}", lambda: self.search.get_search_metadata(doctype=doctype))

    def describe_doctype(self, doctype, user=None):
        return self.cache.get_or_set(
            f"business_summary:{doctype}:{user or 'anonymous'}",
            lambda: self.interpreter.describe_doctype(doctype=doctype, user=user),
        )

    def refresh_metadata(self, doctype=None):
        self.adapter.log("info", "ERP intelligence cache refresh started", scoped=bool(doctype))
        if doctype:
            self.cache.invalidate(f"metadata:{doctype}")
            self.cache.invalidate(f"relationships:{doctype}")
            self.cache.invalidate(f"workflow:{doctype}")
            self.cache.invalidate(f"search:{doctype}")
            self.cache.invalidate_prefix(f"business_summary:{doctype}:")
            return {
                "status": "ok",
                "scope": "doctype",
                "doctype": doctype,
                "metadata": self.get_doctype_metadata(doctype),
                "relationships": self.get_relationships(doctype),
                "workflow": self.get_workflow(doctype),
                "search": self.get_search_metadata(doctype),
                "business_summary": self.describe_doctype(doctype),
            }

        self.cache.invalidate()
        return {
            "status": "ok",
            "scope": "all",
            "modules": self.list_modules(),
            "doctypes": self.list_doctypes(),
        }


_SERVICE = None


def get_erp_intelligence_service():
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ERPIntelligenceService()
    return _SERVICE
