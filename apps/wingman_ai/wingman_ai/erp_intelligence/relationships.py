from wingman_ai.erp_intelligence.config import get_erp_intelligence_config
from wingman_ai.erp_intelligence.frappe_adapter import FrappeERPAdapter
from wingman_ai.erp_intelligence.metadata import CHILD_TABLE_FIELD_TYPES, LINK_FIELD_TYPES, MetadataDiscoveryService


class RelationshipDiscoveryService:
    def __init__(self, adapter=None, config=None, metadata_service=None):
        self.adapter = adapter or FrappeERPAdapter()
        self.config = config or get_erp_intelligence_config()
        self.metadata_service = metadata_service or MetadataDiscoveryService(adapter=self.adapter, config=self.config)

    def get_relationships(self, doctype=None):
        self.adapter.log("info", "ERP intelligence relationship discovery started", doctype=doctype)
        if doctype:
            return self.get_doctype_relationships(doctype)

        return {
            "mode": "metadata_discovery",
            "relationships": [
                self.get_doctype_relationships(item["name"])
                for item in self.metadata_service.list_doctypes(include_child_tables=True)
            ],
        }

    def get_doctype_relationships(self, doctype):
        metadata = self.metadata_service.get_doctype_metadata(doctype)
        all_doctypes = self.metadata_service.list_doctypes(include_child_tables=True)
        incoming = self.discover_incoming_relationships(doctype, all_doctypes)

        return {
            "doctype": doctype,
            "outgoing": self.discover_outgoing_relationships(metadata),
            "incoming": incoming,
            "child_tables": self.discover_child_tables(metadata),
            "parent_tables": self.discover_parent_tables(doctype, all_doctypes),
            "custom_relationships_supported": True,
        }

    def discover_outgoing_relationships(self, metadata):
        links = []
        for field in metadata.get("fields") or []:
            if field.get("fieldtype") not in LINK_FIELD_TYPES:
                continue
            links.append(
                {
                    "relationship_type": field.get("fieldtype"),
                    "source_doctype": metadata.get("doctype"),
                    "source_field": field.get("fieldname"),
                    "target_doctype": field.get("options") if field.get("fieldtype") == "Link" else None,
                    "dynamic_target_field": field.get("options") if field.get("fieldtype") == "Dynamic Link" else None,
                    "mandatory": field.get("mandatory"),
                    "custom": metadata.get("custom"),
                }
            )
        return links

    def discover_child_tables(self, metadata):
        return [
            {
                "relationship_type": field.get("fieldtype"),
                "parent_doctype": metadata.get("doctype"),
                "parent_field": field.get("fieldname"),
                "child_doctype": field.get("options"),
                "mandatory": field.get("mandatory"),
            }
            for field in metadata.get("fields") or []
            if field.get("fieldtype") in CHILD_TABLE_FIELD_TYPES
        ]

    def discover_incoming_relationships(self, doctype, all_doctypes):
        incoming = []
        for item in all_doctypes:
            source_doctype = item.get("name")
            if source_doctype == doctype:
                continue
            try:
                metadata = self.metadata_service.get_doctype_metadata(source_doctype)
            except Exception:
                continue

            for field in metadata.get("fields") or []:
                if field.get("fieldtype") == "Link" and field.get("options") == doctype:
                    incoming.append(
                        {
                            "relationship_type": "Link",
                            "source_doctype": source_doctype,
                            "source_field": field.get("fieldname"),
                            "target_doctype": doctype,
                            "mandatory": field.get("mandatory"),
                            "custom": metadata.get("custom"),
                        }
                    )
                elif field.get("fieldtype") == "Dynamic Link":
                    incoming.append(
                        {
                            "relationship_type": "Dynamic Link Candidate",
                            "source_doctype": source_doctype,
                            "source_field": field.get("fieldname"),
                            "target_doctype": doctype,
                            "dynamic_target_field": field.get("options"),
                            "requires_record_value": True,
                            "custom": metadata.get("custom"),
                        }
                    )
        return incoming

    def discover_parent_tables(self, child_doctype, all_doctypes):
        parents = []
        for item in all_doctypes:
            parent_doctype = item.get("name")
            if parent_doctype == child_doctype:
                continue
            try:
                metadata = self.metadata_service.get_doctype_metadata(parent_doctype)
            except Exception:
                continue

            for child_table in self.discover_child_tables(metadata):
                if child_table.get("child_doctype") == child_doctype:
                    parents.append(child_table)
        return parents
