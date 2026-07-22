from wingman_ai.intelligence.utils import operation_from


class BusinessImpactEngine:
    def summarize(self, payload):
        operation = operation_from(payload)
        data = (payload or {}).get("data") or {}
        result = data.get("result") or {}

        if operation == "update":
            impacts = list(result.get("impact") or [])
            if not impacts:
                changes = result.get("change_rows") or []
                impacts = [f"{row.get('label') or row.get('fieldname')} will be updated on this record." for row in changes[:4]]
            return {"level": "Medium" if impacts else "Low", "items": impacts or ["No major business impact was detected."]}

        if operation == "delete":
            return {
                "level": "High",
                "items": [
                    "The selected record will be removed if Talisma OneCampus allows deletion.",
                    "Linked transactions, workflows, and reports may be affected depending on Talisma OneCampus rules.",
                ],
            }

        if operation == "create":
            return {"level": "Low", "items": ["A new Talisma OneCampus record will be created after confirmation."]}

        return {"level": "Low", "items": ["This response is informational and does not change Talisma OneCampus data."]}
