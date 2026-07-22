import re

from wingman_ai.intent.registry import ENTITY_ALIASES, PARAMETER_ALIASES
from wingman_ai.intent.schema import IntentEntity


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
AMOUNT_PATTERN = re.compile(r"(?<!\w)(?:INR|USD|EUR|GBP|RS\.?|\$)?\s?\d+(?:,\d{3})*(?:\.\d{1,2})?(?!\w)", re.IGNORECASE)
DATE_PATTERN = re.compile(
    r"\b(?:today|tomorrow|yesterday|next week|next month|this month|"
    r"\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})\b",
    re.IGNORECASE,
)
QUOTED_NAME_PATTERN = re.compile(r"['\"]([^'\"]{2,120})['\"]")
PREPOSITION_NAME_PATTERN = re.compile(
    r"\b(?:for|to|called|named|name)\s+([A-Za-z][A-Za-z0-9 .&_-]{1,80})",
    re.IGNORECASE,
)
RECORD_NAME_PATTERN = re.compile(
    r"\b(?:customer|lead|supplier|employee|project|task|user)\s+(?!for\b|with\b|and\b)([A-Za-z][A-Za-z0-9 .&_-]{1,80})",
    re.IGNORECASE,
)


class EntityExtractor:
    def extract(self, message):
        text = message or ""
        entities = []
        entities.extend(self._extract_business_entities(text))
        entities.extend(self._extract_pattern_entities(text))
        entities.extend(self._extract_parameter_entities(text))
        entities.extend(self._extract_names(text))
        return dedupe_entities(entities)

    def _extract_business_entities(self, text):
        found = []
        lowered = text.lower()
        for entity_type, aliases in ENTITY_ALIASES.items():
            for alias in aliases:
                if contains_phrase(lowered, alias):
                    found.append(IntentEntity(entity_type="BusinessEntity", value=entity_type, label=alias, confidence=0.88))
                    break
        return found

    def _extract_pattern_entities(self, text):
        found = []
        found.extend(IntentEntity("Email", match.group(0), confidence=0.97) for match in EMAIL_PATTERN.finditer(text))
        phone_spans = []
        for match in PHONE_PATTERN.finditer(text):
            phone_spans.append(match.span())
            found.append(IntentEntity("Phone", clean_space(match.group(0)), confidence=0.88))
        found.extend(IntentEntity("Date", clean_space(match.group(0)), confidence=0.86) for match in DATE_PATTERN.finditer(text))
        for match in AMOUNT_PATTERN.finditer(text):
            if any(overlaps(match.span(), span) for span in phone_spans):
                continue
            found.append(IntentEntity("Amount", clean_space(match.group(0)), confidence=0.82))
        return found

    def _extract_parameter_entities(self, text):
        found = []
        lowered = text.lower()
        for parameter, aliases in PARAMETER_ALIASES.items():
            for alias in aliases:
                if contains_phrase(lowered, alias):
                    found.append(IntentEntity(entity_type=parameter, value=alias, confidence=0.72))
                    break
        return found

    def _extract_names(self, text):
        found = []
        for match in QUOTED_NAME_PATTERN.finditer(text):
            found.append(IntentEntity(entity_type="Name", value=clean_space(match.group(1)), confidence=0.84))

        for pattern in (PREPOSITION_NAME_PATTERN, RECORD_NAME_PATTERN):
            for match in pattern.finditer(text):
                candidate = clean_candidate_name(match.group(1))
                if candidate and not looks_like_known_keyword(candidate):
                    found.append(IntentEntity(entity_type="Name", value=candidate, confidence=0.64))

        return found


def overlaps(first, second):
    return first[0] < second[1] and second[0] < first[1]


def dedupe_entities(entities):
    unique = []
    seen = set()
    for entity in entities:
        key = (entity.entity_type, str(entity.value).lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(entity.to_dict())
    return unique


def contains_phrase(text, phrase):
    return re.search(rf"(?<!\w){re.escape(phrase.lower())}(?!\w)", text) is not None


def clean_space(value):
    return " ".join(str(value or "").split())


def clean_candidate_name(value):
    value = clean_space(value)
    value = re.split(r"\b(?:with|and|for|on|by|from|to|status|priority|email|phone)\b", value, flags=re.IGNORECASE)[0]
    return clean_space(value.strip(" .,:;"))


def looks_like_known_keyword(value):
    lowered = value.lower()
    blocked = {"lead", "customer", "sales", "order", "quotation", "invoice", "payment", "task", "project"}
    return lowered in blocked
