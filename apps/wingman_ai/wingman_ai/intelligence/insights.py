class InsightEngine:
    def build(self, payload, context=None):
        data = (payload or {}).get("data") or {}
        result = data.get("result") or {}
        insights = []

        rows = ((result.get("search") or {}).get("rows") or result.get("rows") or [])
        if rows:
            insights.append({"label": "Search Coverage", "detail": f"{len(rows)} matching record(s) were available in this response."})

        record_summary = data.get("record_summary") or {}
        child_tables = record_summary.get("child_tables") or []
        for table in child_tables:
            label = table.get("label")
            count = table.get("count")
            if label and count:
                insights.append({"label": label, "detail": f"{count} related row(s) are present on this record."})

        related = data.get("related_summary") or result.get("related_summary") or {}
        for section in related.get("sections") or []:
            if section.get("count"):
                insights.append({"label": section.get("label") or "Related Activity", "detail": f"{section.get('count')} related item(s) found."})

        if not insights:
            return [{"label": "AI Insights", "detail": "No additional insights available."}]
        return insights[:6]
