"""Manual Facebook intake for TrackWatch.

This is deliberately NOT a Facebook scraper. A human pastes the text of an
official track/promoter Facebook post into the private local Control Room.
TrackWatch compares that text with current GulfSouthDrags data and creates a
normal pending detection for review.

No Meta login, Page token, or cooperation from the track owner is required.
"""

import json
import re
from pathlib import Path

import review_queue as rq

TW_DIR = Path(__file__).resolve().parent
REPO_ROOT = TW_DIR.parent
TRACKS_PATH = REPO_ROOT / "tracks.json"

PRICE_RE = re.compile(r"\$\s?\d+(?:\.\d{2})?")
TIME_RE = re.compile(r"\b(?:1[0-2]|0?\d)(?::[0-5]\d)?\s?(?:a\.?m\.?|p\.?m\.?)\b", re.I)

SIGNAL_WORDS = (
    "gate", "gates", "admission", "entry", "payout", "race", "racing",
    "cancel", "canceled", "cancelled", "postpone", "postponed", "rainout",
    "reschedule", "rescheduled", "test and tune", "qualifying", "spectator",
    "crew", "driver", "registration", "tech", "open", "closed",
)


def _load_data():
    return json.loads(TRACKS_PATH.read_text(encoding="utf-8"))


def get_track_options():
    data = _load_data()
    tracks = data.get("tracks", [])
    return sorted(
        [
            {
                "slug": t.get("slug", ""),
                "name": t.get("name", t.get("slug", "")),
                "state": t.get("state", ""),
                "facebook": t.get("facebook", ""),
            }
            for t in tracks
            if t.get("slug")
        ],
        key=lambda x: (x["state"], x["name"].lower()),
    )


def _current_snapshot(data, track):
    lines = [
        f"TRACK: {track.get('name', track.get('slug', ''))}",
        f"Status: {track.get('status', 'unknown')}",
        f"Race days: {track.get('race_days', 'unknown')}",
        f"Track verified: {track.get('verified', 'unknown')}",
    ]

    events = [
        e for e in data.get("events", [])
        if e.get("track_slug") == track.get("slug")
    ]
    if events:
        lines.append("")
        lines.append("CURRENT EVENT DATA:")
        for event in events:
            lines.append(f"- {event.get('name', 'Unnamed event')} | {event.get('dates', '')}")
            if event.get("schedule"):
                lines.append(
                    "  Schedule: " +
                    "; ".join(f"{a}: {b}" for a, b in event.get("schedule", []))
                )
            if event.get("prices"):
                lines.append(
                    "  Prices: " +
                    "; ".join(f"{a}: {b}" for a, b in event.get("prices", []))
                )
            if event.get("summary"):
                lines.append(f"  Summary: {event.get('summary')}")
            if event.get("verified"):
                lines.append(f"  Verified: {event.get('verified')}")
    else:
        lines.extend(["", "CURRENT EVENT DATA:", "- No event record currently attached to this track."])

    return "\n".join(lines)



def _canon_time(value):
    compact = (
        str(value or "")
        .lower()
        .replace(".", "")
        .replace(" ", "")
    )
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)", compact)
    if not match:
        return compact
    hour, minute, meridiem = match.groups()
    minute = minute or "00"
    if minute == "00":
        return f"{int(hour)}{meridiem}"
    return f"{int(hour)}:{minute}{meridiem}"


def _signals(post_text):
    prices = list(dict.fromkeys(m.group(0).replace(" ", "") for m in PRICE_RE.finditer(post_text)))
    times = list(dict.fromkeys(m.group(0) for m in TIME_RE.finditer(post_text)))
    low = post_text.lower()
    words = [w for w in SIGNAL_WORDS if w in low]

    keywords = []
    for item in prices + times + words:
        if item not in keywords:
            keywords.append(item)
    return prices, times, keywords[:20]


def _conflicts(post_text, snapshot, prices, times):
    conflicts = []
    low = post_text.lower()
    snapshot_low = snapshot.lower()

    cancellation_language = any(
        word in low
        for word in (
            "cancel", "canceled", "cancelled", "postpone", "postponed",
            "rainout", "reschedule", "rescheduled",
        )
    )
    if cancellation_language:
        conflicts.append(
            "Cancellation/postponement language detected. Check all current event data for this track before publishing."
        )

    unseen_prices = [p for p in prices if p.lower() not in snapshot_low]
    if unseen_prices:
        conflicts.append(
            "Facebook post contains price(s) not found in the current site snapshot: "
            + ", ".join(unseen_prices)
        )

    snapshot_times = {
        _canon_time(m.group(0))
        for m in TIME_RE.finditer(snapshot)
    }
    unseen_times = [
        t for t in times
        if _canon_time(t) not in snapshot_times
    ]
    if unseen_times:
        conflicts.append(
            "Facebook post contains time(s) not found in the current site snapshot: "
            + ", ".join(unseen_times)
        )

    return conflicts


def queue_facebook_update(*, track_slug, post_text, source_url="", source_label=""):
    post_text = (post_text or "").strip()
    source_url = (source_url or "").strip()
    source_label = (source_label or "").strip()

    if not track_slug:
        raise ValueError("Choose a track.")
    if not post_text:
        raise ValueError("Paste the Facebook post text.")
    if len(post_text) > 30000:
        raise ValueError("Facebook post text is too long.")

    low_post = post_text.lower()
    embed_markers = (
        "<iframe",
        "facebook.com/plugins/post.php",
        "facebook.com/plugins/page.php",
        "<script",
        "data-href=",
    )
    if any(marker in low_post for marker in embed_markers):
        raise ValueError(
            "This looks like Facebook embed code, not the post itself. "
            "Copy the visible post text and use Paste from Clipboard."
        )

    if re.fullmatch(r"https?://\S+", post_text.strip(), re.I):
        raise ValueError(
            "This looks like only a link. Copy the visible Facebook post text "
            "instead; the post URL is optional evidence."
        )

    data = _load_data()
    track = next(
        (t for t in data.get("tracks", []) if t.get("slug") == track_slug),
        None,
    )
    if track is None:
        raise ValueError("Track was not found in tracks.json.")

    if not source_label:
        source_label = f"{track.get('name', track_slug)} — Official Facebook"
    if not source_url:
        source_url = track.get("facebook", "") or "#"

    snapshot = _current_snapshot(data, track)
    prices, times, keywords = _signals(post_text)
    conflicts = _conflicts(post_text, snapshot, prices, times)

    detected = []
    if prices:
        detected.append("prices " + ", ".join(prices))
    if times:
        detected.append("times " + ", ".join(times))
    if keywords:
        plain_words = [
            k for k in keywords
            if not k.startswith("$") and not TIME_RE.fullmatch(k)
        ]
        if plain_words:
            detected.append("signals " + ", ".join(plain_words[:8]))

    summary = f"Manual Facebook update pasted for {track.get('name', track_slug)}."
    if detected:
        summary += " Detected " + "; ".join(detected) + "."

    return rq.create_detection(
        track_slug=track_slug,
        source_id=f"facebook-manual / {source_label}",
        source_url=source_url,
        change_type="facebook_update",
        confidence=4,
        summary=summary,
        before_excerpt=snapshot,
        after_excerpt=post_text,
        keywords=keywords or ["facebook", "manual intake"],
        source_hash_before="manual-current-site-snapshot",
        source_hash_after="manual-facebook-paste",
        conflicts=conflicts,
    )
