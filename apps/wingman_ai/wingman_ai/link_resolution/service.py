import re

from wingman_ai.erp_service import get_erp_service


LINK_SEARCH_METHOD = "wingman_ai.api.link_resolution.search"
DEFAULT_PAGE_SIZE = 8
MAX_PAGE_SIZE = 20


class UniversalLinkResolutionEngine:
    def __init__(self, erp_service=None):
        self.erp_service = erp_service or get_erp_service()

    def describe_field(self, field):
        field = dict(field or {})
        fieldtype = field.get("fieldtype")
        target_doctype = field.get("options")
        if fieldtype == "Dynamic Link":
            target_doctype = field.get("target_doctype")
        return {
            "type": "dynamic_link" if fieldtype == "Dynamic Link" else "link",
            "target_doctype": target_doctype,
            "dynamic_target_field": field.get("options") if fieldtype == "Dynamic Link" else None,
            "search_method": LINK_SEARCH_METHOD,
            "allow_create": True,
            "allow_create_missing": True,
            "display_fields": self.display_fields(target_doctype),
        }

    def choices_for_field(self, field, user=None, page_size=DEFAULT_PAGE_SIZE):
        target_doctype = (field or {}).get("options")
        if not target_doctype:
            return []
        return self.search(target_doctype, text="", user=user, page_size=page_size).get("rows") or []

    def resolve_value(self, field, value, user=None):
        target_doctype = (field or {}).get("options")
        cleaned = clean_query(value)
        if not target_doctype or not cleaned:
            return {"accepted": False, "message": "A linked record is required."}

        existing = self.read_existing(target_doctype, cleaned, user=user)
        if existing:
            return {"accepted": True, "value": existing}

        search_result = self.search(target_doctype, text=cleaned, user=user, page_size=DEFAULT_PAGE_SIZE)
        rows = search_result.get("rows") or []
        exact = first_exact_match(rows, cleaned)
        if exact:
            return {"accepted": True, "value": exact.get("value") or exact.get("label")}

        return {
            "accepted": True,
            "value": cleaned,
            "missing_dependency": {"doctype": target_doctype, "value": cleaned},
            "matches": rows,
        }

    def read_existing(self, doctype, value, user=None):
        if not hasattr(self.erp_service, "read_document"):
            return None
        try:
            response = self.erp_service.read_document(doctype, value, user=user)
        except Exception:
            return None
        if not response.get("success"):
            return None
        result = response.get("result") or {}
        return result.get("name") or value

    def search(self, doctype, text=None, user=None, page_size=DEFAULT_PAGE_SIZE):
        query = clean_query(text)
        size = clamp_page_size(page_size)
        fields = self.search_fields(doctype)
        rows = []

        for candidate_query in search_queries(query):
            rows = self.search_once(doctype, candidate_query, fields=fields, user=user, page_size=size)
            if rows:
                break

        normalized = normalize_rows(rows, doctype=doctype, display_fields=self.display_fields(doctype))
        ranked = rank_rows(normalized, query)
        return {
            "doctype": doctype,
            "query": query,
            "rows": ranked[:size],
            "has_matches": bool(ranked),
        }

    def search_once(self, doctype, text=None, fields=None, user=None, page_size=DEFAULT_PAGE_SIZE):
        if not doctype or not hasattr(self.erp_service, "search_documents"):
            return []
        try:
            response = self.erp_service.search_documents(
                doctype,
                text=text or "",
                filters={},
                fields=fields or ["name"],
                page=1,
                page_size=page_size,
                user=user,
            )
        except Exception:
            return []
        if not response.get("success"):
            return []
        return ((response.get("result") or {}).get("rows") or [])

    def search_fields(self, doctype):
        fields = ["name"]
        fields.extend(self.metadata_search_fields(doctype))
        fields.extend(self.display_fields(doctype))
        return unique([field for field in fields if field])

    def metadata_search_fields(self, doctype):
        metadata_service = getattr(self.erp_service, "metadata_service", None)
        if metadata_service and hasattr(metadata_service, "get_search_metadata"):
            try:
                search = metadata_service.get_search_metadata(doctype) or {}
                return (search.get("autocomplete_fields") or []) + (search.get("search_fields") or [])
            except Exception:
                pass

        metadata = self.get_metadata(doctype)
        search = metadata.get("search") or {}
        configured = []
        configured.extend(search.get("autocomplete_fields") or [])
        configured.extend(search.get("search_fields") or [])
        configured.extend(split_csv(metadata.get("search_fields")))
        return configured

    def display_fields(self, doctype):
        metadata = self.get_metadata(doctype)
        fields = metadata.get("fields") or []
        configured = []
        configured.extend(split_csv(metadata.get("title_field")))
        configured.extend(split_csv(metadata.get("description_field")))
        configured.extend((metadata.get("search") or {}).get("autocomplete_fields") or [])

        fieldnames = {field.get("fieldname") for field in fields if field.get("fieldname")}
        generic_names = []
        for candidate in ("title", "subject"):
            if candidate in fieldnames:
                generic_names.append(candidate)
        for field in fields:
            fieldname = field.get("fieldname")
            if fieldname and field.get("fieldtype") in ("Data", "Small Text") and fieldname.endswith("_name"):
                generic_names.append(fieldname)

        return unique([field for field in configured + generic_names + ["name"] if field])

    def get_metadata(self, doctype):
        if not doctype or not hasattr(self.erp_service, "get_metadata"):
            return {}
        try:
            response = self.erp_service.get_metadata(doctype)
        except Exception:
            return {}
        if isinstance(response, dict):
            return response.get("result") or {}
        return response or {}


def normalize_rows(rows, doctype=None, display_fields=None):
    result = []
    seen = set()
    for row in rows or []:
        normalized = normalize_row(row, display_fields=display_fields)
        if not normalized:
            continue
        key = normalized.get("value")
        if key in seen:
            continue
        seen.add(key)
        normalized["doctype"] = doctype
        result.append(normalized)
    return result


def normalize_row(row, display_fields=None):
    if isinstance(row, str):
        return {"label": row, "value": row, "description": ""}
    if not isinstance(row, dict):
        return None

    value = first_present(row, ("value", "name"))
    if value in (None, ""):
        return None

    label = first_present(row, ("label", "title", "description"))
    if not label or str(label) == str(value):
        for fieldname in display_fields or []:
            candidate = row.get(fieldname)
            if candidate not in (None, "", value):
                label = candidate
                break
    label = label or value

    description = row.get("description") if str(row.get("description") or "") != str(label) else ""
    if not description and str(label) != str(value):
        description = f"ID: {value}"

    aliases = [row.get(fieldname) for fieldname in row if "alias" in str(fieldname).lower()]
    return {
        "label": str(label),
        "value": str(value),
        "description": str(description or ""),
        "aliases": [str(alias) for alias in aliases if alias not in (None, "")],
    }


def rank_rows(rows, query):
    normalized_query = normalize_key(query)
    if not normalized_query:
        return rows

    def score(row):
        haystacks = [
            normalize_key(row.get("label")),
            normalize_key(row.get("value")),
            normalize_key(row.get("description")),
        ] + [normalize_key(alias) for alias in row.get("aliases") or []]
        if any(item == normalized_query for item in haystacks):
            return 0
        if any(item.startswith(normalized_query) for item in haystacks if item):
            return 1
        if any(normalized_query in item for item in haystacks if item):
            return 2
        if any(tokens_overlap(normalized_query, item) for item in haystacks if item):
            return 3
        return 9

    return sorted(rows, key=lambda row: (score(row), row.get("label") or row.get("value") or ""))


def first_exact_match(rows, query):
    normalized_query = normalize_key(query)
    for row in rows or []:
        values = [row.get("label"), row.get("value")] + list(row.get("aliases") or [])
        if any(normalize_key(value) == normalized_query for value in values):
            return row
    return None


def search_queries(query):
    if not query:
        return [""]
    result = [query]
    tokens = [token for token in re.split(r"\s+", query) if len(token) >= 3]
    if tokens:
        result.append(tokens[0])
    return unique(result)


def tokens_overlap(left, right):
    left_tokens = {token for token in re.split(r"[^a-z0-9]+", left) if token}
    right_tokens = {token for token in re.split(r"[^a-z0-9]+", right) if token}
    return bool(left_tokens & right_tokens)


def clean_query(value):
    return " ".join(str(value or "").strip().strip(".,;:()[]{}\"'").split())


def normalize_key(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def split_csv(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace("\n", ",").split(",") if item.strip()]


def first_present(row, fields):
    for fieldname in fields:
        value = row.get(fieldname)
        if value not in (None, ""):
            return value
    return None


def unique(values):
    seen = set()
    result = []
    for value in values or []:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def clamp_page_size(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = DEFAULT_PAGE_SIZE
    return max(1, min(number, MAX_PAGE_SIZE))
