from collections import Counter, defaultdict
from datetime import datetime


class ExceptionIntelligenceReporter:
    def summarize(self, diagnostics):
        diagnostics = diagnostics or []
        categories = Counter(item.get("category") for item in diagnostics if item.get("category"))
        doctypes = defaultdict(set)
        modules = defaultdict(set)
        components = Counter()
        root_causes = Counter()
        resolution_statuses = Counter()
        recovery_durations = []
        for item in diagnostics:
            category = item.get("category")
            if item.get("target_doctype"):
                doctypes[category].add(item.get("target_doctype"))
                module = item.get("module") or infer_module(item.get("target_doctype"))
                modules[module].add(item.get("target_doctype"))
            if item.get("framework_component"):
                components[item.get("framework_component")] += 1
            if item.get("root_cause"):
                root_causes[item.get("root_cause")] += 1
            if item.get("resolution_status"):
                resolution_statuses[item.get("resolution_status")] += 1
            duration = recovery_duration_seconds(item)
            if duration is not None:
                recovery_durations.append(duration)
        return {
            "exception_category_frequency": dict(categories),
            "affected_doctypes": {key: sorted(value) for key, value in doctypes.items()},
            "affected_modules": {key: sorted(value) for key, value in modules.items()},
            "framework_components_most_frequently_involved": dict(components),
            "root_cause_summary": [item.get("root_cause") for item in diagnostics if item.get("root_cause")],
            "top_root_causes": dict(root_causes.most_common(10)),
            "recovery_success_rate": recovery_success_rate(resolution_statuses),
            "average_recovery_time": average(recovery_durations),
            "most_common_environment_issues": top_by_category(diagnostics, "Environment Issue"),
            "most_common_validation_issues": top_by_category(diagnostics, "Validation Issue"),
            "most_common_permission_issues": top_by_category(diagnostics, "Permission Issue"),
        }


def top_by_category(diagnostics, category):
    counter = Counter(
        item.get("root_cause")
        for item in diagnostics
        if item.get("category") == category and item.get("root_cause")
    )
    return dict(counter.most_common(10))


def recovery_success_rate(statuses):
    total = sum(statuses.values())
    if not total:
        return None
    successful = statuses.get("resolved", 0) + statuses.get("recovered", 0)
    return round(successful / total, 4)


def recovery_duration_seconds(item):
    started = parse_datetime(item.get("timestamp") or item.get("created_at"))
    ended = parse_datetime(item.get("resolved_at") or item.get("recovered_at"))
    if not started or not ended:
        return None
    return max((ended - started).total_seconds(), 0)


def average(values):
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def infer_module(doctype):
    if doctype in {"Lead", "Opportunity", "Customer", "Contact", "Address", "Territory", "Lead Source", "Campaign", "Customer Group", "Sales Person"}:
        return "CRM"
    return "Talisma OneCampus"
