from wingman_ai.business_skills.lead_management.formatter import (
    display_fields,
    fact_fields,
    format_conversion_review,
    format_creation_review,
    format_lead_summary,
    format_qualification,
    format_record_type_mismatch,
    format_search_results,
    format_update_review,
)
from wingman_ai.business_skills.lead_management.metadata import LeadMetadataService
from wingman_ai.business_skills.lead_management.parser import (
    detect_lead_operation,
    extract_create_data,
    extract_search_request,
    extract_target_lead,
    extract_update_request,
)
from wingman_ai.business_skills.lead_management.qualification import LeadQualificationService
from wingman_ai.business_skills.record_creation.service import PRIMARY_NAME_FIELDS, SUPPORTED_CREATE_DOCTYPES, RecordCreationService
from wingman_ai.creation_session.service import CreationSessionManager
from wingman_ai.dependency_resolution.service import DependencyResolutionService
from wingman_ai.erp_service import get_erp_service
from wingman_ai.review_builder.service import ReviewBuilderService


class LeadManagementService:
    def __init__(self, erp_service=None, metadata_service=None, qualification_service=None, dependency_service=None, review_builder=None):
        self.erp_service = erp_service or get_erp_service()
        self.metadata_service = metadata_service or LeadMetadataService(self.erp_service)
        self.qualification_service = qualification_service or LeadQualificationService()
        self.dependency_service = dependency_service or DependencyResolutionService(
            erp_service=self.erp_service,
            supported_doctypes=SUPPORTED_CREATE_DOCTYPES,
            primary_name_fields=PRIMARY_NAME_FIELDS,
        )
        self.review_builder = review_builder or ReviewBuilderService()
        self.creation_session = CreationSessionManager(self.erp_service)
        self.record_creation_service = RecordCreationService(
            erp_service=self.erp_service,
            dependency_service=self.dependency_service,
            review_builder=self.review_builder,
        )

    def understand(self):
        metadata = self.metadata_service.get_metadata()
        return {
            "doctype": "Lead",
            "fields": metadata.fields,
            "mandatory_fields": metadata.mandatory_fields,
            "select_options": metadata.select_options,
            "link_fields": metadata.link_fields,
            "semantic_fields": metadata.semantic_fields,
        }

    def prepare_create_from_message(self, message, context=None, intent=None):
        context = context or {}
        metadata = self.metadata_service.get_metadata()
        data = extract_create_data(message, metadata, structured_intent=getattr(intent, "structured_intent", None))
        supplied_data = dict(data or {})
        data, defaults_applied = self.apply_create_defaults(data, metadata)
        missing_fields = self.get_missing_mandatory_fields(data, metadata)
        missing = [field.get("label") or field.get("fieldname", "").replace("_", " ").title() for field in missing_fields]
        missing_dependencies = self.dependency_service.detect_for_operation("Lead", data, operation="create", user=context.get("user"))
        missing_dependencies = self.record_creation_service.add_dependency_reviews(missing_dependencies, context=context, user=context.get("user"))
        review = self.review_builder.build_creation_review(
            "Lead",
            data=data,
            fields=metadata.fields,
            supplied_data=supplied_data,
            defaults_applied=defaults_applied,
            context=context,
            user=context.get("user"),
        )
        prepared = {
            "operation": "create",
            "doctype": "Lead",
            "data": data,
            "display_fields": display_fields(data, metadata),
            "defaults_applied": defaults_applied,
            "missing_fields": missing,
            "missing_dependencies": missing_dependencies,
            "missing_link_dependencies": missing_dependencies,
            "review": review,
            "dependency_context": {
                "original_message": message,
                "parsed_intent": getattr(intent, "structured_intent", None),
                "pending_action": "create",
            "workflow_step": "dependency_resolution",
            },
            "next_missing_field": self.creation_session.serialize_field(missing_fields[0], user=context.get("user")) if missing_fields else None,
            "ready": not missing,
        }
        prepared["message"] = format_creation_review(prepared)
        return prepared

    def create_lead(self, data, user=None):
        metadata = self.metadata_service.get_metadata()
        data, _defaults_applied = self.apply_create_defaults(data, metadata)
        return self.erp_service.create_document("Lead", data=data or {}, user=user)

    def apply_create_defaults(self, data, metadata):
        payload = dict(data or {})
        defaults_applied = []

        status_field = metadata.semantic_fields.get("status")
        if status_field and payload.get(status_field) in (None, "", []):
            status = self.default_lead_status(metadata, status_field)
            if status:
                payload[status_field] = status
                defaults_applied.append(
                    {
                        "fieldname": status_field,
                        "label": self.metadata_field_label(metadata, status_field),
                        "value": status,
                        "reason": "Default Lead status from Talisma OneCampus metadata.",
                    }
                )

        return payload, defaults_applied

    def default_lead_status(self, metadata, status_field):
        field = self.metadata_field(metadata, status_field)
        configured_default = field.get("default") if field else None
        if configured_default and self.is_valid_select_value(metadata, status_field, configured_default):
            return configured_default

        for preferred in ("Lead", "Open", "New"):
            option = self.match_select_option(metadata, status_field, preferred)
            if option:
                return option

        options = metadata.select_options.get(status_field) or []
        return options[0] if options else configured_default

    def is_valid_select_value(self, metadata, fieldname, value):
        options = metadata.select_options.get(fieldname) or []
        if not options:
            return True
        return bool(self.match_select_option(metadata, fieldname, value))

    def match_select_option(self, metadata, fieldname, value):
        requested = normalize_match_text(value)
        if not requested:
            return None
        for option in metadata.select_options.get(fieldname) or []:
            if normalize_match_text(option) == requested:
                return option
        return None

    def metadata_field(self, metadata, fieldname):
        for field in metadata.fields:
            if field.get("fieldname") == fieldname:
                return field
        return {}

    def metadata_field_label(self, metadata, fieldname):
        field = self.metadata_field(metadata, fieldname)
        return field.get("label") or fieldname.replace("_", " ").title()

    def search_leads(self, text=None, filters=None, page=1, page_size=10, user=None):
        metadata = self.metadata_service.get_metadata()
        fields = self.metadata_service.lead_display_fields()
        return self.erp_service.search_documents(
            "Lead",
            text=text,
            filters=filters or {},
            fields=fields,
            page=page,
            page_size=page_size,
            user=user,
        )

    def search_from_message(self, message, context=None, intent=None):
        metadata = self.metadata_service.get_metadata()
        request = extract_search_request(message, metadata)
        result = self.search_leads(text=request["text"], filters=request["filters"], user=(context or {}).get("user"))
        return {
            "operation": "search",
            "request": request,
            "result": result,
            "message": format_search_results(result),
        }

    def summarize_lead(self, lead_name, user=None):
        if not lead_name:
            return self.not_enough_context("Lead Summary", "Please specify which Lead to summarize, or open a Lead record first.")
        metadata = self.metadata_service.get_metadata()
        response = self.read_lead_by_reference(lead_name, user=user)
        if not response.get("success"):
            mismatch = self.find_record_type_mismatch(lead_name, user=user)
            if mismatch:
                return self.record_type_mismatch("Lead", lead_name, mismatch)
            return self.failed_operation("Lead Summary", response, f"I could not read Lead {lead_name}.")
        lead = response.get("result") or {}
        lead_name = lead.get("name") or lead_name
        related = self.related_activity(lead_name, user=user)
        qualification = self.qualification_service.qualify(lead, metadata)
        summary = {
            "lead_name": lead_name,
            "lead": lead,
            "facts": fact_fields(lead, metadata),
            "related": related,
            "business_state": self.lead_business_state(lead, related),
            "qualification": qualification,
            "recommendations": qualification.get("recommended_next_steps") or [],
        }
        return {"success": True, "summary": summary, "message": format_lead_summary(summary)}

    def prepare_update_from_message(self, message, context=None, intent=None):
        metadata = self.metadata_service.get_metadata()
        request = extract_update_request(message, metadata, context=context, structured_intent=getattr(intent, "structured_intent", None))
        prepared = {
            "operation": "update",
            "doctype": "Lead",
            "lead_name": request.get("lead_name"),
            "data": request.get("data") or {},
            "display_fields": display_fields(request.get("data") or {}, metadata),
            "ready": bool(request.get("lead_name") and request.get("data")),
        }
        prepared["message"] = format_update_review(prepared)
        return prepared

    def update_lead(self, lead_name, data, user=None):
        return self.erp_service.update_document("Lead", lead_name, data=data or {}, user=user)

    def qualify_lead(self, lead_name, user=None):
        if not lead_name:
            return self.not_enough_context("Lead Qualification", "Please specify which Lead to qualify, or open a Lead record first.")
        metadata = self.metadata_service.get_metadata()
        response = self.read_lead_by_reference(lead_name, user=user)
        if not response.get("success"):
            return self.failed_operation("Lead Qualification", response, f"I could not read Lead {lead_name}.")
        lead = response.get("result") or {}
        lead_name = lead.get("name") or lead_name
        qualification = self.qualification_service.qualify(lead, metadata)
        return {"success": True, "qualification": qualification, "message": format_qualification(qualification, lead_name=lead_name)}

    def prepare_conversion(self, lead_name, user=None):
        if not lead_name:
            return self.not_enough_context("Lead Conversion Review", "Please specify which Lead to convert, or open a Lead record first.")
        metadata = self.metadata_service.get_metadata()
        response = self.read_lead_by_reference(lead_name, user=user)
        if not response.get("success"):
            return self.failed_operation("Lead Conversion Review", response, f"I could not read Lead {lead_name}.")
        lead = response.get("result") or {}
        lead_name = lead.get("name") or lead_name
        prerequisites = self.conversion_prerequisites(lead, metadata)
        prepared = {
            "operation": "convert",
            "lead_name": lead_name,
            "source_doctype": "Lead",
            "target_doctype": "Opportunity",
            "opportunity_data": self.build_opportunity_payload(lead_name, lead),
            "prerequisites": prerequisites,
            "ready": not prerequisites,
        }
        prepared["message"] = format_conversion_review(prepared)
        return prepared

    def convert_to_opportunity(self, lead_name, user=None):
        prepared = self.prepare_conversion(lead_name, user=user)
        if not prepared.get("ready"):
            return {"success": False, "result": prepared, "errors": [{"code": "conversion_prerequisites", "message": "Lead conversion prerequisites are not complete."}]}
        return self.erp_service.create_document("Opportunity", data=prepared["opportunity_data"], user=user)

    def handle_message(self, message, context=None, intent=None):
        operation = detect_lead_operation(message, structured_intent=getattr(intent, "structured_intent", None))
        if operation == "create":
            return self.prepare_create_from_message(message, context=context, intent=intent)
        if operation == "search":
            return self.search_from_message(message, context=context, intent=intent)
        if operation == "update":
            return self.prepare_update_from_message(message, context=context, intent=intent)
        lead_name = extract_target_lead(message, context=context, structured_intent=getattr(intent, "structured_intent", None))
        if operation == "qualify":
            return self.qualify_lead(lead_name, user=(context or {}).get("user"))
        if operation == "convert":
            return self.prepare_conversion(lead_name, user=(context or {}).get("user"))
        return self.summarize_lead(lead_name, user=(context or {}).get("user"))

    def read_lead_by_reference(self, lead_reference, user=None):
        exact = self.erp_service.read_document("Lead", lead_reference, user=user)
        if exact.get("success"):
            return exact

        resolved = self.resolve_lead_reference(lead_reference, user=user)
        if not resolved:
            return exact
        return self.erp_service.read_document("Lead", resolved, user=user)

    def resolve_lead_reference(self, lead_reference, user=None):
        if not lead_reference:
            return None
        metadata = self.metadata_service.get_metadata()
        fields = self.metadata_service.lead_display_fields()
        if "name" not in fields:
            fields = ["name"] + fields
        response = self.erp_service.search_documents(
            "Lead",
            text=lead_reference,
            filters={},
            fields=fields,
            page_size=5,
            user=user,
        )
        if not response.get("success"):
            return None
        rows = ((response.get("result") or {}).get("rows") or [])
        if not rows:
            return None
        return select_best_lead_match(lead_reference, rows)

    def related_activity(self, lead_name, user=None):
        related = {}
        specs = [
            ("Open Tasks", "Task", {"reference_type": "Lead", "reference_name": lead_name}),
            ("Opportunities", "Opportunity", {"opportunity_from": "Lead", "party_name": lead_name}),
            ("Communications", "Communication", {"reference_doctype": "Lead", "reference_name": lead_name}),
        ]
        for label, doctype, filters in specs:
            response = self.erp_service.search_documents(doctype, filters=filters, fields=["name", "status", "subject", "modified"], page_size=5, user=user)
            if response.get("success"):
                related[label] = ((response.get("result") or {}).get("rows") or [])
        return related

    def lead_business_state(self, lead, related):
        status = normalize_match_text(lead.get("status"))
        opportunities = (related or {}).get("Opportunities") or []
        if status == "opportunity" or opportunities:
            return {
                "state": "opportunity",
                "message": "This is a Lead record, but it has already moved to the Opportunity stage.",
                "records": [self.with_doctype("Opportunity", row) for row in opportunities[:3]],
            }
        return {}

    def find_record_type_mismatch(self, reference, user=None):
        if not reference:
            return None
        for doctype, fields in (
            ("Opportunity", ["name", "title", "party_name", "customer_name", "status", "sales_stage"]),
            ("Customer", ["name", "customer_name", "customer_group", "territory"]),
            ("Contact", ["name", "first_name", "last_name", "email_id", "mobile_no"]),
        ):
            response = self.erp_service.search_documents(doctype, text=reference, fields=fields, page_size=3, user=user)
            if not response.get("success"):
                continue
            rows = ((response.get("result") or {}).get("rows") or [])
            matches = [self.with_doctype(doctype, row) for row in rows if self.is_confident_record_match(reference, row)]
            if matches:
                return matches
        return None

    def record_type_mismatch(self, requested_doctype, requested_reference, matches):
        return {
            "success": False,
            "operation": "record_type_mismatch",
            "requested_doctype": requested_doctype,
            "requested_reference": requested_reference,
            "matches": matches,
            "message": format_record_type_mismatch(
                {
                    "requested_doctype": requested_doctype,
                    "requested_reference": requested_reference,
                    "matches": matches,
                }
            ),
        }

    def with_doctype(self, doctype, row):
        result = dict(row or {})
        result["doctype"] = doctype
        return result

    def is_confident_record_match(self, reference, row):
        normalized_reference = normalize_match_text(reference)
        if not normalized_reference:
            return False
        values = [
            row.get("name"),
            row.get("title"),
            row.get("lead_name"),
            row.get("customer_name"),
            row.get("company_name"),
            row.get("party_name"),
            row.get("email_id"),
        ]
        return any(normalize_match_text(value) == normalized_reference for value in values if value)

    def get_missing_mandatory_labels(self, data, metadata):
        return [field.get("label") or field.get("fieldname", "").replace("_", " ").title() for field in self.get_missing_mandatory_fields(data, metadata)]

    def get_missing_mandatory_fields(self, data, metadata):
        return [
            field
            for field in metadata.mandatory_fields
            if field.get("fieldname") and data.get(field.get("fieldname")) in (None, "", [])
        ]

    def get_missing_link_dependencies(self, data, metadata, user=None):
        dependencies = []
        for fieldname, target_doctype in (metadata.link_fields or {}).items():
            value = (data or {}).get(fieldname)
            if value in (None, "", []):
                continue
            if target_doctype not in SUPPORTED_CREATE_DOCTYPES:
                continue
            response = self.erp_service.read_document(target_doctype, value, user=user)
            if response.get("success"):
                continue
            if not self.is_missing_document_response(response):
                continue
            create_data = self.build_dependency_create_data(target_doctype, value)
            if not create_data:
                continue
            dependencies.append(
                {
                    "fieldname": fieldname,
                    "label": self.metadata_field_label(metadata, fieldname),
                    "target_doctype": target_doctype,
                    "value": value,
                    "create_data": create_data,
                }
            )
        return dependencies

    def build_dependency_create_data(self, doctype, value):
        primary_fields = PRIMARY_NAME_FIELDS.get(doctype) or ()
        if not primary_fields:
            return {}
        return {primary_fields[0]: value}

    def is_missing_document_response(self, response):
        issues = response.get("validation_issues") or []
        if any(issue.get("issue_type") == "permission" for issue in issues):
            return False
        if any(issue.get("issue_type") == "existence" for issue in issues):
            return True
        if issues:
            return False
        for error in response.get("errors") or []:
            if "not found" in str(error.get("message") or "").lower():
                return True
        return response.get("result") in (None, {})

    def conversion_prerequisites(self, lead, metadata):
        missing = []
        if not any(lead.get(metadata.semantic_fields.get(name)) for name in ("lead_name", "company_name")):
            missing.append("Lead name or company name is required.")
        if not any(lead.get(metadata.semantic_fields.get(name)) for name in ("email", "phone")):
            missing.append("At least one contact channel is recommended before conversion.")
        return missing

    def build_opportunity_payload(self, lead_name, lead):
        return {
            "opportunity_from": "Lead",
            "party_name": lead_name,
            "title": lead.get("company_name") or lead.get("lead_name") or lead_name,
        }

    def not_enough_context(self, title, message):
        return {
            "success": False,
            "message": "\n".join([title, message, "", "What You Can Do Next", '- Try "summarize lead <name>" or open a Lead record and ask again.']),
            "errors": [{"code": "missing_lead_context", "message": message}],
        }

    def failed_operation(self, title, response, message):
        return {
            "success": False,
            "message": "\n".join([title, message, "", "Current Status", "- No Talisma OneCampus data was changed."]),
            "service_response": response,
        }


_SERVICE = None


def get_lead_management_service():
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = LeadManagementService()
    return _SERVICE


def select_best_lead_match(query, rows):
    normalized_query = normalize_match_text(query)
    best = None
    for row in rows:
        values = [row.get("name"), row.get("lead_name"), row.get("company_name"), row.get("email_id"), row.get("mobile_no")]
        for value in values:
            normalized_value = normalize_match_text(value)
            if not normalized_value:
                continue
            score = 1.0 if normalized_value == normalized_query else 0.0
            if not score and normalized_query in normalized_value:
                score = 0.9
            if score and (not best or score > best[0]):
                best = (score, row)
    selected = (best[1] if best else rows[0]) if rows else None
    return selected.get("name") if selected else None


def normalize_match_text(value):
    import re

    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()
