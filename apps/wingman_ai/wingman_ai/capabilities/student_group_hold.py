import re
from difflib import SequenceMatcher

from wingman_ai.business_skills.record_creation.capability import build_actions
from wingman_ai.business_skills.record_creation.service import get_record_creation_service
from wingman_ai.capabilities.base import Capability, CapabilityResult


GROUP_HOLD_DOCTYPE = "Talisma Student Group Hold"
HOLD_TYPES = (
    "International Student",
    "Disciplinary",
    "Financial",
    "Registrar",
    "Advising",
    "Health",
    "Other",
)
BLOCK_DEFAULTS = {
    "Financial": ("blocks_registration", "blocks_financial_activity"),
    "Registrar": ("blocks_registration", "blocks_transcript"),
    "Advising": ("blocks_registration",),
    "Disciplinary": ("blocks_registration",),
    "Health": ("blocks_registration",),
    "International Student": ("blocks_registration",),
    "Other": ("blocks_registration",),
}


class StudentGroupHoldCapability(Capability):
    name = "student_group_hold"

    def handle(self, message, context, intent):
        service = get_record_creation_service()
        parsed = parse_group_hold_prompt(message)
        group = resolve_student_group(parsed.get("student_group"), service, user=context.get("user"))
        data = {
            key: value
            for key, value in {
                "student_group": group,
                "hold_type": parsed.get("hold_type"),
                "reason": parsed.get("reason"),
                "effective_from": parsed.get("effective_from"),
                "effective_to": parsed.get("effective_to"),
            }.items()
            if value not in (None, "", [])
        }
        hold_type = data.get("hold_type")
        for fieldname in BLOCK_DEFAULTS.get(hold_type, ()):
            data[fieldname] = 1
        explicit_blocks = parsed.get("explicit_blocks") or []
        if explicit_blocks:
            for fieldname in ("blocks_registration", "blocks_transcript", "blocks_graduation", "blocks_financial_activity"):
                data[fieldname] = 1 if fieldname in explicit_blocks else 0

        blueprint = service.build_blueprint(GROUP_HOLD_DOCTYPE)
        prepared = service.build_prepared_create(
            GROUP_HOLD_DOCTYPE,
            data,
            blueprint["fields"]["all"],
            context=context,
            user=context.get("user"),
            intent=intent,
            blueprint=blueprint,
        )
        service.sync_pending_draft(prepared, context=context)
        if prepared.get("ready"):
            prepared["message"] = format_group_hold_review(prepared, member_count(service, group, user=context.get("user")))
        return CapabilityResult(
            message=prepared.get("message") or "Student Group Hold prepared.",
            actions=build_actions(prepared),
            data={"business_skill": "student_group_hold", "operation": "create", "result": prepared},
            requires_confirmation=bool(prepared.get("ready")),
        )


def is_student_group_hold_request(message):
    text = normalize(message)
    return "hold" in text and "group" in text and any(word in text for word in ("put", "place", "apply", "create"))


def parse_group_hold_prompt(message):
    text = str(message or "").strip()
    hold_type = next((item for item in HOLD_TYPES if re.search(rf"\b{re.escape(item)}\b", text, re.IGNORECASE)), None)
    group = None
    patterns = (
        r"\b(?:put|place|apply)\s+(?:the\s+)?(.+?)(?:\s+student\s+group|\s+group)?\s+(?:on|under)\s+(?:an?\s+)?(?:international\s+student|disciplinary|financial|registrar|advising|health|other)\s+hold\b",
        r"\b(?:put|place|apply)\s+(?:an?\s+)?(?:international\s+student|disciplinary|financial|registrar|advising|health|other)\s+hold\s+(?:on|to)\s+(?:the\s+)?(.+?)(?:\s+student\s+group|\s+group)?(?:\s+because\b|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            group = clean(match.group(1))
            break

    reason_match = re.search(r"\b(?:because(?:\s+of)?|reason(?:\s+is)?|for\s+reason)\s+(.+)$", text, re.IGNORECASE)
    reason = clean(reason_match.group(1)) if reason_match else None
    date_values = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    explicit_blocks = []
    lowered = text.lower()
    if "block" in lowered:
        if "registration" in lowered:
            explicit_blocks.append("blocks_registration")
        if "transcript" in lowered:
            explicit_blocks.append("blocks_transcript")
        if "graduation" in lowered:
            explicit_blocks.append("blocks_graduation")
        if "financial" in lowered and ("activity" in lowered or "activities" in lowered):
            explicit_blocks.append("blocks_financial_activity")
    return {
        "student_group": group,
        "hold_type": hold_type,
        "reason": reason,
        "effective_from": date_values[0] if date_values else None,
        "effective_to": date_values[1] if len(date_values) > 1 else None,
        "explicit_blocks": explicit_blocks,
    }


def resolve_student_group(query, service, user=None):
    if not query:
        return None
    direct = service.erp_service.read_document("Student Group", query, user=user)
    if (direct or {}).get("success"):
        return ((direct.get("result") or {}).get("name")) or query
    rows = service.link_resolution.search("Student Group", text=query, user=user, page_size=8).get("rows") or []
    requested = normalize_group_name(query)
    exact = next(
        (
            row
            for row in rows
            if normalize_group_name(row.get("label")) == requested
            or normalize_group_name(row.get("value")) == requested
        ),
        None,
    )
    if exact:
        return exact.get("value")

    # Link search is intentionally strict and can miss harmless spelling
    # variants such as Honors/Honours. Compare the available group names, but
    # resolve automatically only when one candidate is clearly stronger.
    response = service.erp_service.list_documents(
        "Student Group",
        fields=["name", "student_group_name"],
        page_size=200,
        user=user,
    )
    available = (((response or {}).get("result") or {}).get("rows") or [])
    ranked = []
    for row in available:
        value = row.get("name") or row.get("value")
        label = row.get("student_group_name") or row.get("label") or value
        candidate = normalize_group_name(label)
        if not value or not candidate:
            continue
        score = SequenceMatcher(None, requested, candidate).ratio()
        if requested == candidate:
            score = 1.0
        ranked.append((score, value))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked:
        return None
    best_score, best_value = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0
    if best_score >= 0.88 and best_score - second_score >= 0.08:
        return best_value
    return None


def member_count(service, student_group, user=None):
    if not student_group:
        return 0
    response = service.erp_service.list_documents(
        "Student Group Student",
        fields=["name"],
        filters={"parent": student_group, "parenttype": "Student Group", "active": 1},
        page_size=100,
        user=user,
    )
    return len((((response or {}).get("result") or {}).get("rows") or []))


def format_group_hold_review(prepared, students):
    data = prepared.get("data") or {}
    blocked = []
    for fieldname, label in (
        ("blocks_registration", "Registration"),
        ("blocks_transcript", "Transcript"),
        ("blocks_graduation", "Graduation"),
        ("blocks_financial_activity", "Financial Activity"),
    ):
        if data.get(fieldname):
            blocked.append(label)
    return "\n".join(
        [
            "Student Group Hold Review",
            "Please confirm this bulk hold before any student records are changed.",
            "",
            "Hold Details",
            f"- Student Group: {data.get('student_group')}",
            f"- Hold Type: {data.get('hold_type')}",
            f"- Hold Reason: {data.get('reason')}",
            f"- Effective From: {data.get('effective_from')}",
            f"- Effective To: {data.get('effective_to') or 'No end date'}",
            f"- Blocks: {', '.join(blocked)}",
            "",
            "Impact",
            f"- {students} current group member{'s' if students != 1 else ''} will receive an individual hold.",
            "- Existing unrelated holds will not be changed.",
            "",
            "Current Status",
            "- No Talisma OneCampus data has been changed yet.",
        ]
    )


def normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()


def normalize_group_name(value):
    normalized = normalize(value)
    aliases = {
        "honours": "honors",
        "programme": "program",
        "centre": "center",
    }
    return " ".join(aliases.get(word, word) for word in normalized.split())


def clean(value):
    return " ".join(str(value or "").strip().strip(".,;:()[]{}\"'").split())
