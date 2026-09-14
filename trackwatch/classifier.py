"""Meaningful-change classification.

V0.1 ships a deterministic keyword/pattern classifier — no AI API, no
network dependency, no paid service required to run TrackWatch at all.

The interface (BaseClassifier.classify) is intentionally the only thing a
future LLM-backed classifier would need to implement, so the rest of the
pipeline (detector/queue/review server) never has to change when that
happens — see trackwatch/README.md, "Swapping in a smarter classifier".
"""

import re
from dataclasses import dataclass, field

# --- signal vocabularies -------------------------------------------------

CANCELLATION_WORDS = {
    "cancelled", "canceled", "rainout", "rained out", "postponed",
    "rescheduled", "closed for the weekend", "no racing",
}
SCHEDULE_WORDS = {
    "gates", "gate", "open", "tech", "qualifying", "time trials",
    "test and tune", "test-n-tune", "test & tune", "bracket", "footbrake",
    "dragster", "eliminations", "time runs",
}
MONEY_WORDS = {"purse", "to win", "entry", "spectator", "admission", "gate fee"}
DAY_WORDS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday", "tonight", "tomorrow", "tonite",
}
STATUS_WORDS = {
    "camping", "rv", "hookups", "concessions", "race fuel", "compressed air",
    "phone", "address",
}

TIME_RE = re.compile(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", re.I)
MONEY_RE = re.compile(r"\$\s?[\d,]+(\.\d{2})?")
DATE_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b",
    re.I,
)
PHONE_RE = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")

_WORD_RE_CACHE = {}


def _word_present(word, haystack):
    """Whole-word/phrase match, not substring — otherwise short keywords
    like 'rv' match inside ordinary words (e.g. 'reseRVed', 'seRVice')."""
    pattern = _WORD_RE_CACHE.get(word)
    if pattern is None:
        pattern = re.compile(r"\b" + re.escape(word) + r"\b")
        _WORD_RE_CACHE[word] = pattern
    return pattern.search(haystack) is not None


_ALL_KEYWORD_GROUPS = {
    "cancellation": CANCELLATION_WORDS,
    "schedule": SCHEDULE_WORDS,
    "money": MONEY_WORDS,
    "day": DAY_WORDS,
    "status": STATUS_WORDS,
}


@dataclass
class ClassificationResult:
    is_meaningful: bool
    confidence: float          # the BOT's confidence this is worth a human look
    change_type: str           # e.g. "possible_cancellation"
    summary: str
    keywords: list = field(default_factory=list)


class BaseClassifier:
    """Interface every classifier (deterministic today, LLM-backed later)
    must implement."""

    def classify(self, before_text, after_text, changed_excerpt):
        raise NotImplementedError


class KeywordClassifier(BaseClassifier):
    """V0.1's classifier: no semantic understanding, just reliable surfacing.
    False positives are fine; the brief for this project is explicit that
    silent false negatives are the worse failure mode."""

    #: below this many changed characters with zero keyword hits, treat the
    #: diff as boilerplate churn (copyright year, a menu label, etc.)
    MIN_MEANINGFUL_CHARS = 12

    def classify(self, before_text, after_text, changed_excerpt):
        haystack = changed_excerpt.lower()

        hits = {}
        for group, words in _ALL_KEYWORD_GROUPS.items():
            found = sorted({w for w in words if _word_present(w, haystack)})
            if found:
                hits[group] = found

        has_time = bool(TIME_RE.search(haystack))
        has_money = bool(MONEY_RE.search(haystack))
        has_date = bool(DATE_RE.search(haystack))
        has_phone = bool(PHONE_RE.search(haystack))

        keywords = sorted({w for words in hits.values() for w in words})
        signal_count = len(hits) + has_time + has_money + has_date + has_phone

        if signal_count == 0 and len(changed_excerpt.strip()) < self.MIN_MEANINGFUL_CHARS:
            return ClassificationResult(
                is_meaningful=False, confidence=0.05, change_type="low_value",
                summary="Change looks cosmetic (no racing-related keywords, dates, times or amounts).",
                keywords=[],
            )
        if signal_count == 0:
            # A real amount of text changed, but nothing that looks
            # racing-related — still low value, but say so a bit more
            # cautiously than the tiny-diff case above.
            return ClassificationResult(
                is_meaningful=False, confidence=0.15, change_type="low_value",
                summary="Content changed but no racing-related signal was found in it.",
                keywords=[],
            )

        change_type, headline = self._change_type(hits, has_time, has_money, has_date)
        confidence = min(0.95, 0.45 + 0.12 * signal_count)

        return ClassificationResult(
            is_meaningful=True,
            confidence=round(confidence, 2),
            change_type=change_type,
            summary=headline,
            keywords=keywords,
        )

    @staticmethod
    def _change_type(hits, has_time, has_money, has_date):
        if "cancellation" in hits:
            return ("possible_cancellation",
                    "Wording suggests a race may have been cancelled, rained out, or rescheduled.")
        if has_date or "day" in hits:
            return ("possible_schedule_change",
                    "Race day or date wording changed — worth checking against the current schedule.")
        if has_time or "schedule" in hits:
            return ("possible_timing_change",
                    "Gate, tech or start-time wording changed.")
        if has_money or "money" in hits:
            return ("possible_price_change",
                    "Entry fee, purse, or admission wording changed.")
        if "status" in hits:
            return ("possible_logistics_change",
                    "Camping, fuel, concessions, phone or address wording changed.")
        return ("possible_update", "Racing-related wording changed.")


def get_classifier(name="keyword"):
    if name == "keyword":
        return KeywordClassifier()
    raise ValueError(f"Unknown classifier: {name!r}")
