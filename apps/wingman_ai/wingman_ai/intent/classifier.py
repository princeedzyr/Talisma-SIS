import re

from wingman_ai.intent.registry import ACTION_KEYWORDS, INTENT_CATEGORIES, WRITE_INTENTS


class IntentClassifier:
    def classify(self, message, entities=None):
        text = (message or "").strip().lower()
        if not text:
            return build_match("Unknown", 0.0, ["Empty message."])

        notes = []
        scored = []
        for category in INTENT_CATEGORIES:
            if category == "Unknown":
                continue
            score = score_category(text, category)
            if score:
                scored.append((category, score))
                notes.append(f"Matched {category} keywords.")

        if not scored:
            if entities:
                return build_match("Read", 0.48, ["Entity detected without a clear action."])
            return build_match("Unknown", 0.18, ["No category keywords matched."])

        scored.sort(key=lambda item: item[1], reverse=True)
        category, confidence = scored[0]
        confidence = adjust_confidence(category, confidence, entities)
        return build_match(category, confidence, notes[:6])


def score_category(text, category):
    best = 0.0
    for keyword in ACTION_KEYWORDS.get(category, ()):
        if keyword_matches(text, keyword):
            weight = 0.9 if text.startswith(keyword) else 0.74
            best = max(best, weight)
    return best


def keyword_matches(text, keyword):
    escaped = re.escape(keyword)
    return re.search(rf"(?<!\w){escaped}(?!\w)", text) is not None


def adjust_confidence(category, confidence, entities):
    if entities:
        confidence += 0.06
    if category in WRITE_INTENTS and not entities:
        confidence -= 0.12
    return max(0.0, min(confidence, 0.98))


def build_match(category, confidence, notes):
    return {
        "intent_category": category,
        "confidence_score": confidence,
        "requires_write_review": category in WRITE_INTENTS,
        "reasoning_notes": notes,
    }
