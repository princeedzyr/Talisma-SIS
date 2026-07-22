from wingman_ai.intelligence.utils import clamp_score, dependencies, is_ready, validation_issues


class ConfidenceCalculator:
    WEIGHTS = {
        "intent_recognition": 0.20,
        "entity_recognition": 0.15,
        "metadata_resolution": 0.15,
        "dependency_resolution": 0.15,
        "validation_status": 0.15,
        "permission_verification": 0.10,
        "workflow_readiness": 0.10,
    }

    LABELS = {
        "intent_recognition": "Intent Recognition",
        "entity_recognition": "Entity Recognition",
        "metadata_resolution": "Metadata Resolution",
        "dependency_resolution": "Dependency Resolution",
        "validation_status": "Validation",
        "permission_verification": "Permissions",
        "workflow_readiness": "Workflow Readiness",
    }

    def calculate(self, payload, intent=None, readiness=None):
        scores = {
            "intent_recognition": self.intent_score(intent, payload),
            "entity_recognition": self.entity_score(payload, intent),
            "metadata_resolution": self.metadata_score(payload),
            "dependency_resolution": self.dependency_score(payload),
            "validation_status": self.validation_score(payload),
            "permission_verification": self.permission_score(payload),
            "workflow_readiness": self.readiness_score(payload, readiness),
        }
        overall = clamp_score(sum(scores[key] * weight for key, weight in self.WEIGHTS.items()))
        return {
            "score": overall,
            "meter": overall / 100,
            "label": confidence_label(overall),
            "breakdown": [
                {"key": key, "label": self.LABELS[key], "score": clamp_score(value)}
                for key, value in scores.items()
            ],
        }

    def intent_score(self, intent, payload):
        confidence = getattr(intent, "confidence", None) if intent else (payload or {}).get("confidence")
        if confidence is None:
            return 80 if (payload or {}).get("status") == "success" else 40
        return clamp_score(float(confidence) * 100 if float(confidence) <= 1 else confidence)

    def entity_score(self, payload, intent=None):
        details = getattr(intent, "structured_intent", None) if intent else (payload or {}).get("intent_details")
        entity = (details or {}).get("detected_entity") or {}
        data = (payload or {}).get("data") or {}
        result = data.get("result") or {}
        if entity.get("value") or result.get("doctype") or data.get("record_summary"):
            return 100
        if (payload or {}).get("capability") in ("general", "reasoning"):
            return 85
        return 70

    def metadata_score(self, payload):
        result = ((payload or {}).get("data") or {}).get("result") or {}
        if result.get("blueprint") or result.get("operation_plan") or result.get("review"):
            return 100
        if result.get("doctype") or ((payload or {}).get("data") or {}).get("record_summary"):
            return 90
        return 75

    def dependency_score(self, payload):
        items = dependencies(payload)
        if not items:
            return 100
        if any(item.get("ready") for item in items):
            return 75
        return 60

    def validation_score(self, payload):
        issues = validation_issues(payload)
        if not issues:
            return 100
        if any(issue.get("issue_type") == "permission" for issue in issues):
            return 35
        return 55

    def permission_score(self, payload):
        issues = validation_issues(payload)
        if any(issue.get("issue_type") == "permission" or "permission" in str(issue.get("message") or "").lower() for issue in issues):
            return 20
        return 100

    def readiness_score(self, payload, readiness=None):
        if readiness and readiness.get("indicator") == "red":
            return 35
        if readiness and readiness.get("indicator") == "amber":
            return 70
        return 100 if is_ready(payload) or (payload or {}).get("status") == "success" else 50


def confidence_label(score):
    if score >= 85:
        return "High"
    if score >= 65:
        return "Medium"
    return "Low"
