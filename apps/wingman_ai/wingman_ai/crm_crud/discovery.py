from wingman_ai.crm_crud.metadata import CRMMetadataService


class CRMDiscoveryService:
    """Discovers CRM DocTypes from Talisma OneCampus metadata instead of a hand-maintained list."""

    def __init__(self, metadata_service=None):
        self.metadata_service = metadata_service or CRMMetadataService()

    def discover_doctypes(self, include_child_tables=False):
        return self.metadata_service.list_crm_doctypes(include_child_tables=include_child_tables)

    def discover_names(self, include_child_tables=False):
        return [row["name"] for row in self.discover_doctypes(include_child_tables=include_child_tables) if row.get("name")]

    def get_metadata(self, doctype):
        return self.metadata_service.get_metadata(doctype)

    def is_crm_doctype(self, doctype):
        metadata = self.get_metadata(doctype)
        row = {
            "name": doctype,
            "module": metadata.get("module"),
            "is_child_table": metadata.get("is_child_table") or metadata.get("istable"),
        }
        return bool(metadata) and self.metadata_service.is_crm_doctype(row, metadata=metadata)
