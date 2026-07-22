from wingman_ai.erp_intelligence.config import get_erp_intelligence_config
from wingman_ai.erp_intelligence.frappe_adapter import FrappeERPAdapter
from wingman_ai.erp_intelligence.metadata import MetadataDiscoveryService
from wingman_ai.erp_intelligence.relationships import RelationshipDiscoveryService


class SearchMetadataService:
    def __init__(self, adapter=None, config=None, metadata_service=None, relationship_service=None):
        self.adapter = adapter or FrappeERPAdapter()
        self.config = config or get_erp_intelligence_config()
        self.metadata_service = metadata_service or MetadataDiscoveryService(adapter=self.adapter, config=self.config)
        self.relationship_service = relationship_service or RelationshipDiscoveryService(
            adapter=self.adapter,
            config=self.config,
            metadata_service=self.metadata_service,
        )

    def get_search_metadata(self, doctype):
        self.adapter.log("info", "ERP intelligence search metadata discovery started", doctype=doctype)
        metadata = self.metadata_service.get_doctype_metadata(doctype)
        relationships = self.relationship_service.get_doctype_relationships(doctype)
        return {
            "doctype": doctype,
            "title_field": metadata.get("title_field"),
            "search_fields": metadata.get("search", {}).get("search_fields") or [],
            "filter_fields": metadata.get("search", {}).get("filter_fields") or [],
            "autocomplete_fields": metadata.get("search", {}).get("autocomplete_fields") or [],
            "linked_documents": {
                "outgoing": relationships.get("outgoing") or [],
                "incoming": relationships.get("incoming") or [],
                "child_tables": relationships.get("child_tables") or [],
            },
            "recent_documents": {
                "enabled": False,
                "reason": "Business record queries are intentionally excluded from the metadata engine.",
            },
        }
