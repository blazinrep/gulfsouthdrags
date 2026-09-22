#!/usr/bin/env python3
"""TrackWatch V0.2 discovery core.

Discovery is deliberately separate from the known-source watcher.

WATCH:
    known URL -> fetch -> compare -> classify -> review

DISCOVER:
    search result -> identify track -> score racing relevance -> dedupe -> review

This module does not publish anything and does not modify sources.json.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse, urlunparse

try:
    from . import review_queue
except ImportError:
    import review_queue

TW_DIR = Path(__file__).resolve().parent
CONFIG_PATH = TW_DIR / "config" / "discovery.json"
SOURCES_PATH = TW_DIR / "config" / "sources.json"
STATE_PATH = TW_DIR / "state" / "discovery_seen.json"

RACING_TERMS = {
    "drag race", "drag racing", "dragway", "dragstrip",
    "bracket", "footbrake", "dragster", "race",
    "qualifying", "eliminations", "time trials",
    "test and tune", "test-n-tune",
}

EVENT_TERMS = {
    "entry", "enter here", "registration", "register",
    "to win", "purse", "runner up", "semi",
    "gates", "spectator", "admission",
}

ACTION_TERMS = {
    "this weekend", "race week", "upcoming", "schedule",
    "scheduled", "november", "october", "september",
    "entry", "entries", "registration", "register",
    "tickets", "purse", "to win", "qualifying",
    "eliminations", "cancelled", "canceled", "postponed",
    "rescheduled", "results", "winner", "r/u",
}

REFERENCE_HOSTS = {
    "mapquest.com",
    "tripadvisor.com",
    "yelp.com",
    "coastalmississippi.com",
}

REFERENCE_PATH_HINTS = {
    "track_directory",
    "/directory/",
    "/attraction_review",
    "/biz/",
}

DATE_RE = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
    r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?\s+\d{1,2}\b",
    re.I,
)

MONEY_RE = re.compile(r"\$\s?[\d,]+(?:\.\d{2})?")

OWN_DOMAINS = {
    "gulfsouthdrags.com",
    "www.gulfsouthdrags.com",
}


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass
class DiscoveryCandidate:
    track_slug: str
    title: str
    url: str
    snippet: str
    score: int
    reasons: list[str]


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))



def get_brave_api_key() -> str:
    """Read the Brave Search API key from macOS Keychain."""
    account = subprocess.check_output(
        ["whoami"],
        text=True,
    ).strip()

    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-a", account,
            "-s", "TrackWatch Brave Search API",
            "-w",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    key = result.stdout.strip()

    if not key:
        raise RuntimeError("Brave Search API key was empty.")

    return key


def clean_search_text(value: str) -> str:
    """Remove HTML from Brave titles/snippets."""
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(value.split())


def brave_search(query: str, count: int = 10) -> list[SearchResult]:
    """Run a Brave web search and return normalized results."""
    count = max(1, min(int(count), 20))

    params = urllib.parse.urlencode({
        "q": query,
        "count": count,
    })

    endpoint = (
        "https://api.search.brave.com/res/v1/web/search?"
        + params
    )

    request = urllib.request.Request(
        endpoint,
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": get_brave_api_key(),
            "User-Agent": "GulfSouthDrags-TrackWatch/0.2",
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)

    results = []

    for item in payload.get("web", {}).get("results", []):
        raw_url = (item.get("url") or "").strip()

        if not raw_url:
            continue

        results.append(
            SearchResult(
                title=clean_search_text(item.get("title", "")),
                url=raw_url,
                snippet=clean_search_text(
                    item.get("description", "")
                ),
            )
        )

    return results


def canonical_url(url: str) -> str:
    """Normalize URLs for discovery dedupe without destroying identity."""
    parsed = urlparse(url.strip())

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")

    tracking = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
    }

    query_items = [
        (k, v)
        for k, v in urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
        if k.lower() not in tracking
    ]

    query = urllib.parse.urlencode(query_items, doseq=True)

    return urlunparse((
        parsed.scheme.lower() or "https",
        host,
        path,
        "",
        query,
        "",
    ))

def result_key(track_slug: str, url: str) -> str:
    raw = f"{track_slug}|{canonical_url(url)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def load_seen() -> dict:
    if not STATE_PATH.exists():
        return {}

    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_seen(seen: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(seen, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _contains(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


def known_source_urls(track_slug: str) -> set[str]:
    """Return URLs already covered by TrackWatch's WATCH lane."""
    try:
        data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()

    track = data.get("tracks", {}).get(track_slug, {})
    urls = set()

    for source in track.get("sources", []):
        url = source.get("url")
        if url:
            urls.add(canonical_url(url))

    return urls



GENERIC_DISCOVERY_PHRASES = {
    "no race schedule entered",
    "no schedule entered",
}

GENERIC_TITLE_PATTERNS = (
    re.compile(r"^[^|]{2,80}\s*\|\s*[^|]{2,80}\s*\|\s*facebook$", re.I),
    re.compile(r"^[^|]{2,100}\s*-\s*tickets\s*-\s*thefoat$", re.I),
)

STRONG_CURRENT_TERMS = {
    "this weekend",
    "race week",
    "upcoming",
    "registration",
    "register",
    "enter here",
    "entries available",
    "entry available",
    "cancelled",
    "canceled",
    "postponed",
    "rescheduled",
    "to win",
    "purse",
    "qualifying",
    "eliminations",
}

YEAR_RE = re.compile(r"\b(20\d{2})\b")



MONTH_NUMBERS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

MONTH_DAY_RE = re.compile(
    r"\b("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
    r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")\.?\s+(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?"
    r"(?:,?\s+(20\d{2}))?\b",
    re.I,
)


def extract_month_day_dates(text: str):
    """Return identifiable event dates from search-result text."""
    now = datetime.now(timezone.utc)
    found = []

    for match in MONTH_DAY_RE.finditer(text):
        month_name, start_day, end_day, explicit_year = match.groups()
        month = MONTH_NUMBERS[month_name.lower().rstrip(".")]
        year = int(explicit_year) if explicit_year else now.year

        days = [int(start_day)]
        if end_day:
            days.append(int(end_day))

        for day in days:
            try:
                found.append(datetime(year, month, day, tzinfo=timezone.utc))
            except ValueError:
                continue

    return found


def passes_current_event_gate(title: str, snippet: str) -> tuple[bool, str]:
    """Reject obviously stale or generic discovery results.

    This is intentionally conservative. It rejects only evidence we can
    identify confidently; ambiguous results may continue to the scorer.
    """
    title = title.strip()
    combined = f"{title}\n{snippet}".lower()

    for phrase in GENERIC_DISCOVERY_PHRASES:
        if phrase in combined:
            return False, f"generic page: {phrase}"

    for pattern in GENERIC_TITLE_PATTERNS:
        if pattern.search(title):
            return False, "generic track/profile page"

    now = datetime.now(timezone.utc)
    current_year = now.year
    years = {int(y) for y in YEAR_RE.findall(combined)}

    # If explicit years are present and every one is older than this year,
    # reject the result. A page mentioning both an old and current/future
    # year is allowed through.
    if years and max(years) < current_year:
        return False, f"stale year: {max(years)}"

    event_dates = extract_month_day_dates(combined)

    # Keep a seven-day grace period because recent race results can still
    # be useful. Reject only when every identifiable date is older.
    if event_dates:
        newest_event_date = max(event_dates)
        if newest_event_date < (now - timedelta(days=7)):
            return False, (
                "stale event date: "
                + newest_event_date.strftime("%Y-%m-%d")
            )

    strong_hits = [
        term for term in STRONG_CURRENT_TERMS
        if term in combined
    ]

    date_found = bool(DATE_RE.search(combined))
    money_found = bool(MONEY_RE.search(combined))

    # Generic titles with no actual event evidence should not become alerts.
    title_lower = title.lower().strip()
    weak_title = title_lower in {
        "montgomery international dragway",
        "holiday raceway",
        "no problem raceway",
        "swamp bottom dragstrip",
        "gulfport dragway",
    }

    if weak_title and not strong_hits and not date_found and not money_found:
        return False, "generic track page"

    return True, ""


def score_result(track_slug: str, track_cfg: dict, result: SearchResult):
    """Return a candidate only when the result looks like actionable racing intel."""
    url = canonical_url(result.url)

    passes_gate, gate_reason = passes_current_event_gate(
        result.title,
        result.snippet,
    )
    if not passes_gate:
        return None

    # Discovery should not rediscover URLs already covered by WATCH.
    if url in known_source_urls(track_slug):
        return None

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if host in OWN_DOMAINS:
        return None

    combined = f"{result.title}\n{result.snippet}".lower()
    reasons = []
    score = 0

    names = track_cfg.get("names", [])
    matched_names = [
        name for name in names
        if _contains(combined, name)
    ]

    # Track identity is mandatory.
    if not matched_names:
        return None

    score += 5
    reasons.append(f"track name: {matched_names[0]}")

    racing_hits = sorted(
        term for term in RACING_TERMS
        if term in combined
    )
    if racing_hits:
        score += min(2, len(racing_hits))
        reasons.append(
            "racing terms: " + ", ".join(racing_hits[:4])
        )

    event_hits = sorted(
        term for term in EVENT_TERMS
        if term in combined
    )
    if event_hits:
        score += min(3, len(event_hits))
        reasons.append(
            "event terms: " + ", ".join(event_hits[:4])
        )

    action_hits = sorted(
        term for term in ACTION_TERMS
        if term in combined
    )
    if action_hits:
        score += min(4, len(action_hits))
        reasons.append(
            "action/update terms: " + ", ".join(action_hits[:5])
        )

    date_found = bool(DATE_RE.search(combined))
    money_found = bool(MONEY_RE.search(combined))

    if date_found:
        score += 2
        reasons.append("date found")

    if money_found:
        score += 2
        reasons.append("money found")

    location_hits = [
        term for term in track_cfg.get("location_terms", [])
        if _contains(combined, term)
    ]
    if location_hits:
        score += 1
        reasons.append(
            "location: " + ", ".join(location_hits)
        )

    # Generic directory/reference pages are not discoveries.
    if (
        host in REFERENCE_HOSTS
        or any(hint in path for hint in REFERENCE_PATH_HINTS)
    ):
        return None

    # A track profile is not enough. Require evidence of an actual
    # event, update, result, schedule item, registration, money, or date.
    actionable = bool(
        event_hits
        or action_hits
        or date_found
        or money_found
    )

    if not actionable:
        return None

    if score < 8:
        return None

    return DiscoveryCandidate(
        track_slug=track_slug,
        title=result.title.strip(),
        url=url,
        snippet=result.snippet.strip(),
        score=score,
        reasons=reasons,
    )

def evaluate_results(track_slug: str, results: list[SearchResult]):
    config = load_config()
    track_cfg = config.get("tracks", {}).get(track_slug)

    if not track_cfg or not track_cfg.get("enabled", True):
        return []

    seen = load_seen()
    candidates = []

    for result in results:
        candidate = score_result(track_slug, track_cfg, result)

        if candidate is None:
            continue

        key = result_key(track_slug, candidate.url)

        if key in seen:
            continue

        candidates.append(candidate)

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates



def queue_candidates(candidates: list[DiscoveryCandidate]) -> list[dict]:
    """Put new discoveries into the existing human review queue."""
    seen = load_seen()
    queued = []

    for candidate in candidates:
        key = result_key(candidate.track_slug, candidate.url)

        if key in seen:
            continue

        confidence = min(
            0.98,
            0.60 + (candidate.score * 0.025),
        )

        summary = f"DISCOVERY: {candidate.title}"

        record = review_queue.create_detection(
            track_slug=candidate.track_slug,
            source_id="discovery:brave",
            source_url=candidate.url,
            change_type="possible_event_discovery",
            confidence=round(confidence, 2),
            summary=summary,
            before_excerpt="",
            after_excerpt=candidate.snippet,
            keywords=candidate.reasons,
            source_hash_before="",
            source_hash_after=key,
            conflicts=[],
        )

        # Mark seen only after successful queue creation.
        seen[key] = {
            "track_slug": candidate.track_slug,
            "url": candidate.url,
            "title": candidate.title,
            "provider": "brave",
            "review_id": record["id"],
        }

        queued.append(record)

    if queued:
        save_seen(seen)

    return queued

if __name__ == "__main__":
    print("TrackWatch Discovery V0.2 core loaded.")
    print("Brave Search provider available.")
