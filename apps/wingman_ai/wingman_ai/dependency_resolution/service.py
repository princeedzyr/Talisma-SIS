import re

from wingman_ai.erp_service import get_erp_service
from wingman_ai.field_filters import is_editable_business_field
from wingman_ai.link_resolution import UniversalLinkResolutionEngine
from wingman_ai.review_builder.workflow import build_dependency_review_actions


LINKED_DOCUMENT_PATTERN = re.compile(
    r"(?P<label>.+?)\s+references\s+a[n]?\s+(?P<doctype>.+?)\s+record\s+that\s+was\s+not\s+found",
    re.IGNORECASE,
)
COULD_NOT_FIND_PATTERN = re.compile(
    r"(?:could\s+not\s+find|not\s+found)\s+(?P<label>[A-Za-z][\w\s/-]*?):\s*(?P<value>.+)",
    re.IGNORECASE,
)


class DependencyResolutionService:
    def __init__(self, erp_service=None, supported_doctypes=None, primary_name_fields=None):
        self.erp_service = erp_service or get_erp_service()
        self.supported_doctypes = set(supported_doctypes or [])
        self.primary_name_fields = dict(primary_name_fields or {})
        self.link_resolution = UniversalLinkResolutionEngine(erp_service=self.erp_service)

    def detect_for_operation(self, source_doctype, source_data=None, operation="create", docname=None, user=None, blueprint=None):
        source_data = source_data or {}
        validation_response = self.validate_source_document(source_doctype, source_data, operation=operation, docname=docname, user=user)
        if validation_response:
            dependencies = self.detect_from_validation_response(source_doctype, source_data, validation_response, user=user, blueprint=blueprint)
            if dependencies:
                return dependencies
        return self.detect_from_link_fields(source_doctype, source_data, user=user, blueprint=blueprint)

    def validate_source_document(self, source_doctype, source_data, operation="create", docname=None, user=None):
        if not hasattr(self.erp_service, "validate_document"):
            return None
        try:
            return self.erp_service.validate_document(
                source_doctype,
                data=source_data,
                docname=docname,
                operation=operation,
                user=user,
            )
        except Exception:
            return None

    def detect_from_validation_response(self, source_doctype, source_data, response, user=None, blueprint=None):
        fields = self.get_fields(source_doctype, blueprint=blueprint)
        field_map = {field.get("fieldname"): field for field in fields if field.get("fieldname")}
        dependencies = []

        for issue in response.get("validation_issues") or []:
            missing_hint = self.parse_missing_link_hint(issue.get("message"))
            if issue.get("issue_type") != "linked_document" and not missing_hint:
                continue
            fieldname = issue.get("fieldname")
            field = field_map.get(fieldname) or {}
            if field and not is_editable_business_field(field):
                continue
            if not field:
                matched = self.match_link_field(fields, source_data, issue, missing_hint)
                fieldname = matched.get("fieldname")
                field = matched.get("field") or {}
            target_doctype = (
                link_target_doctype(field, source_data)
                or (missing_hint or {}).get("target_doctype")
                or self.parse_target_doctype(issue.get("message"))
            )
            value = source_data.get(fieldname) if fieldname else None
            if value in (None, "", []) and missing_hint:
                value = missing_hint.get("value")
            dependency = self.build_dependency(
                fieldname,
                field,
                target_doctype,
                value,
                issue=issue,
                source_doctype=source_doctype,
                source_data=source_data,
                user=user,
            )
            if dependency:
                dependencies.append(dependency)

        return self.dedupe_dependencies(dependencies)

    def match_link_field(self, fields, source_data, issue, missing_hint=None):
        message = normalize((issue or {}).get("message"))
        label = normalize((missing_hint or {}).get("label"))
        value = (missing_hint or {}).get("value")
        candidates = []
        for field in fields or []:
            if field.get("fieldtype") not in {"Link", "Dynamic Link"} or not is_editable_business_field(field):
                continue
            score = self.score_link_field_match(field, source_data or {}, message, label, value)
            if score:
                candidates.append((score, field))
        if not candidates:
            return {}
        candidates.sort(key=lambda item: item[0], reverse=True)
        field = candidates[0][1]
        return {"fieldname": field.get("fieldname"), "field": field}

    def score_link_field_match(self, field, source_data, message, label, value):
        score = 0
        tokens = field_match_tokens(field, source_data)
        if label and any(contains_phrase(label, token) or contains_phrase(token, label) for token in tokens):
            score += 8
        if message and any(contains_phrase(message, token) for token in tokens):
            score += 5
        field_value = source_data.get(field.get("fieldname"))
        if value not in (None, "", []) and field_value not in (None, "", []) and str(field_value) == str(value):
            score += 10
        target_doctype = normalize(link_target_doctype(field, source_data))
        if target_doctype and label and contains_phrase(label, target_doctype):
            score += 4
        return score

    def detect_from_link_fields(self, source_doctype, source_data, user=None, blueprint=None):
        dependencies = []
        for field in self.get_fields(source_doctype, blueprint=blueprint):
            if field.get("fieldtype") not in {"Link", "Dynamic Link"} or not is_editable_business_field(field):
                continue
            fieldname = field.get("fieldname")
            target_doctype = link_target_doctype(field, source_data)
            value = (source_data or {}).get(fieldname)
            if value in (None, "", []):
                continue
            field_for_resolution = {**field, "options": target_doctype}
            resolved = self.link_resolution.resolve_value(field_for_resolution, value, user=user)
            if resolved.get("accepted") and not resolved.get("missing_dependency"):
                resolved_value = resolved.get("value")
                if resolved_value not in (None, "", []) and resolved_value != value:
                    source_data[fieldname] = resolved_value
                continue
            response = self.erp_service.read_document(target_doctype, value, user=user)
            if response.get("success") or not self.is_missing_document_response(response):
                continue
            dependency = self.build_dependency(
                fieldname,
                field,
                target_doctype,
                value,
                source_doctype=source_doctype,
                source_data=source_data,
                user=user,
            )
            if dependency:
                dependencies.append(dependency)
        return self.dedupe_dependencies(dependencies)

    def build_dependency(self, fieldname, field, target_doctype, value, issue=None, source_doctype=None, source_data=None, user=None):
        if not target_doctype or value in (None, "", []):
            return None
        if not self.can_create(target_doctype):
            return None
        create_data = self.build_create_data(target_doctype, value)
        if not create_data:
            return None
        matches = self.link_resolution.search(target_doctype, text=value, user=user, page_size=5).get("rows") or []
        return {
            "fieldname": fieldname,
            "label": target_doctype if (field or {}).get("fieldtype") == "Dynamic Link" and target_doctype else (field_label(field) if field else fieldname),
            "target_doctype": target_doctype,
            "value": value,
            "create_data": create_data,
            "matches": matches,
            "source_doctype": source_doctype,
            "source_data": dict(source_data or {}),
            "source_message": f"Create {target_doctype} {value}",
            "issue": dict(issue or {}),
        }

    def build_dependency_actions(self, dependencies, resume_action=None):
        resume_review = resume_action if isinstance(resume_action, dict) and resume_action.get("message") else None
        return build_dependency_review_actions(dependencies, resume_review=resume_review)

    def build_follow_up(self, source_doctype, dependencies, resume_action=None):
        dependencies = dependencies or []
        if not dependencies:
            return None
        lines = [
            "Missing Dependencies",
            f"Talisma OneCampus needs the following linked record(s) before continuing {source_doctype}.",
            "",
            "Required Records",
        ]
        for item in dependencies:
            lines.append(f"- {item.get('target_doctype')} {item.get('value')}")
        lines.extend(["", "What You Can Do Next", "- Create the missing record, then Wingman will continue the original action."])
        return {
            "message": "\n".join(lines),
            "actions": self.build_dependency_actions(dependencies, resume_action=resume_action),
        }

    def build_create_data(self, doctype, value, blueprint=None):
        primary_field = self.primary_name_field(doctype, blueprint=blueprint)
        if not primary_field:
            return {}
        return {primary_field: value}

    def primary_name_field(self, doctype, blueprint=None):
        if blueprint and blueprint.get("primary_field"):
            return blueprint["primary_field"].get("fieldname")

        for fieldname in self.primary_name_fields.get(doctype) or ():
            if fieldname:
                return fieldname

        fields = self.get_fields(doctype, blueprint=blueprint)
        fieldnames = {field.get("fieldname") for field in fields if field.get("fieldname")}
        normalized = scrub(doctype)
        for candidate in (f"{normalized}_name", "title", "subject"):
            if candidate in fieldnames:
                return candidate
        for field in fields:
            fieldname = field.get("fieldname")
            if field.get("fieldtype") == "Data" and is_required(field) and fieldname and fieldname != "name":
                return fieldname
        return None

    def can_create(self, doctype, blueprint=None):
        return bool(self.primary_name_field(doctype, blueprint=blueprint))

    def get_fields(self, doctype, blueprint=None):
        if blueprint:
            return [dict(field) for field in ((blueprint.get("fields") or {}).get("all") or [])]
        response = self.erp_service.get_metadata(doctype)
        meta = response.get("result") if isinstance(response, dict) else response
        if isinstance(meta, dict):
            return [dict(field) for field in meta.get("fields") or []]
        return [field_to_dict(field) for field in getattr(meta, "fields", []) or []]

    def parse_target_doctype(self, message):
        match = LINKED_DOCUMENT_PATTERN.search(message or "")
        if match:
            return clean_query(match.group("doctype"))
        hint = self.parse_missing_link_hint(message)
        return hint.get("target_doctype") if hint else None

    def parse_missing_link_hint(self, message):
        text = str(message or "")
        match = COULD_NOT_FIND_PATTERN.search(text)
        if not match:
            return None
        label = clean_query(match.group("label"))
        value = clean_query(match.group("value"))
        if not label or value in (None, "", []):
            return None
        return {"label": label, "value": value, "target_doctype": label}

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

    def dedupe_dependencies(self, dependencies):
        seen = set()
        result = []
        for item in dependencies or []:
            key = (item.get("fieldname"), item.get("target_doctype"), item.get("value"))
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result


def field_to_dict(field):
        return {
            "fieldname": getattr(field, "fieldname", None),
            "label": getattr(field, "label", None),
            "fieldtype": getattr(field, "fieldtype", None),
            "options": getattr(field, "options", None),
            "reqd": getattr(field, "reqd", None),
            "mandatory": getattr(field, "mandatory", None),
            "default": getattr(field, "default", None),
            "hidden": getattr(field, "hidden", None),
            "read_only": getattr(field, "read_only", None),
            "is_virtual": getattr(field, "is_virtual", None),
        }


def field_label(field):
    return (field or {}).get("label") or str((field or {}).get("fieldname") or "Field").replace("_", " ").title()


def link_target_doctype(field, source_data=None):
    if not field:
        return None
    if field.get("fieldtype") == "Dynamic Link":
        controller = field.get("options")
        return (source_data or {}).get(controller) or field.get("target_doctype")
    return field.get("options")


def is_required(field):
    return bool((field or {}).get("reqd") or (field or {}).get("mandatory"))


def scrub(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def clean_query(value):
    return " ".join(str(value or "").strip().strip(".,;:()[]{}\"'").split())


def field_match_tokens(field, source_data=None):
    tokens = {
        normalize((field or {}).get("fieldname")),
        normalize(field_label(field)),
        normalize(str((field or {}).get("fieldname") or "").replace("_", " ")),
    }
    target = link_target_doctype(field, source_data or {})
    if target:
        tokens.add(normalize(target))
    if field and field.get("fieldtype") == "Dynamic Link":
        controller = field.get("options")
        if controller:
            tokens.add(normalize(controller))
            tokens.add(normalize(str(controller).replace("_", " ")))
            controller_value = (source_data or {}).get(controller)
            if controller_value:
                tokens.add(normalize(controller_value))
    return {token for token in tokens if token and token not in {"name", "type", "status"}}


def contains_phrase(text, phrase):
    return bool(re.search(rf"(?<!\w){re.escape(str(phrase or '').lower())}(?!\w)", str(text or "").lower()))


def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()
