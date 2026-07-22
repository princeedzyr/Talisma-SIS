class ExecutionVerificationEngine:
    """Best-effort read-back verification after Talisma OneCampus write operations."""

    def __init__(self, erp_service=None):
        self.erp_service = erp_service

    def verify_create(self, doctype, response=None, expected_data=None, user=None):
        if not self.erp_service or not (response or {}).get("success"):
            return skipped("No successful create response was available.")
        result = (response or {}).get("result") or {}
        docname = result.get("name") or (expected_data or {}).get("name")
        return self.verify_document(doctype, docname, expected_data=expected_data, user=user)

    def verify_update(self, doctype, docname, expected_changes=None, user=None):
        if not self.erp_service:
            return skipped("No ERP service was available for verification.")
        return self.verify_document(doctype, docname, expected_data=expected_changes, user=user)

    def verify_document(self, doctype, docname, expected_data=None, user=None):
        if not doctype or not docname:
            return skipped("Talisma OneCampus did not return a readable document name.")
        if not hasattr(self.erp_service, "read_document"):
            return skipped("The ERP service does not support read-back verification.")

        read_response = self.erp_service.read_document(doctype, docname, user=user)
        if not read_response.get("success"):
            return skipped("The document could not be read back with the current permissions.")

        stored = read_response.get("result") or {}
        mismatches = compare_expected_values(stored, expected_data or {})
        if mismatches:
            return {
                "verified": False,
                "status": "failed",
                "docname": docname,
                "mismatches": mismatches,
            }
        return {
            "verified": True,
            "status": "passed",
            "docname": docname,
            "mismatches": [],
        }


def compare_expected_values(stored, expected):
    mismatches = []
    for fieldname, expected_value in (expected or {}).items():
        if expected_value in (None, "", []):
            continue
        if isinstance(expected_value, (dict, list)):
            continue
        stored_value = (stored or {}).get(fieldname)
        if normalize_value(stored_value) != normalize_value(expected_value):
            mismatches.append(
                {
                    "fieldname": fieldname,
                    "expected": expected_value,
                    "actual": stored_value,
                }
            )
    return mismatches


def normalize_value(value):
    if isinstance(value, bool):
        return int(value)
    return str(value)


def skipped(reason):
    return {
        "verified": None,
        "status": "skipped",
        "reason": reason,
        "mismatches": [],
    }
