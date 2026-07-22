from dataclasses import dataclass


@dataclass(frozen=True)
class LeadQualificationConfig:
    contact_points: int = 25
    identity_points: int = 20
    source_points: int = 10
    territory_points: int = 10
    ownership_points: int = 10
    status_points: int = 15
    recency_points: int = 10
    qualified_threshold: int = 70
    nurture_threshold: int = 45


class LeadQualificationService:
    def __init__(self, config=None):
        self.config = config or LeadQualificationConfig()

    def qualify(self, lead, metadata):
        lead = lead or {}
        score = 0
        reasons = []
        missing = []

        if has_any(lead, metadata, "lead_name", "company_name"):
            score += self.config.identity_points
            reasons.append("Lead identity is available.")
        else:
            missing.append("Lead name or company name")

        if has_any(lead, metadata, "email", "phone"):
            score += self.config.contact_points
            reasons.append("At least one contact channel is available.")
        else:
            missing.append("Email or phone number")

        if has_value(lead, metadata, "source"):
            score += self.config.source_points
            reasons.append("Lead source is captured.")
        else:
            missing.append("Lead source")

        if has_value(lead, metadata, "territory"):
            score += self.config.territory_points
            reasons.append("Territory is available for ownership and routing.")
        else:
            missing.append("Territory")

        if lead.get("owner") or has_value(lead, metadata, "sales_person"):
            score += self.config.ownership_points
            reasons.append("Lead ownership is available.")
        else:
            missing.append("Owner or sales person")

        status = get_semantic_value(lead, metadata, "status")
        if status and str(status).lower() not in {"unqualified", "lost"}:
            score += self.config.status_points
            reasons.append(f"Status is {status}.")
        else:
            missing.append("Qualified/open status")

        if lead.get("modified") or lead.get("creation"):
            score += self.config.recency_points
            reasons.append("Lead has trackable Talisma OneCampus activity timestamps.")

        score = min(100, score)
        return {
            "score": score,
            "grade": grade(score, self.config),
            "missing_information": missing,
            "reasons": reasons,
            "recommended_next_steps": recommended_steps(score, missing, status, self.config),
            "facts_used": {
                "status": status,
                "owner": lead.get("owner"),
                "has_contact": has_any(lead, metadata, "email", "phone"),
            },
        }


def has_any(lead, metadata, *semantic_names):
    return any(has_value(lead, metadata, semantic_name) for semantic_name in semantic_names)


def has_value(lead, metadata, semantic_name):
    value = get_semantic_value(lead, metadata, semantic_name)
    return value not in (None, "", [])


def get_semantic_value(lead, metadata, semantic_name):
    fieldname = metadata.semantic_fields.get(semantic_name)
    return lead.get(fieldname) if fieldname else None


def grade(score, config):
    if score >= config.qualified_threshold:
        return "Ready to qualify"
    if score >= config.nurture_threshold:
        return "Needs follow-up"
    return "Incomplete"


def recommended_steps(score, missing, status, config):
    steps = []
    if missing:
        steps.append("Complete missing fields: " + ", ".join(missing[:4]) + ".")
    if score >= config.qualified_threshold and str(status or "").lower() != "qualified":
        steps.append("Review the lead and mark it as Qualified if the business context is confirmed.")
    elif score < config.qualified_threshold:
        steps.append("Schedule a follow-up before converting this lead.")
    steps.append("Use Talisma OneCampus permissions and workflow review before changing lead status.")
    return steps
