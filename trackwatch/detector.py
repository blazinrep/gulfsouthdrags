"""Snapshot storage, change detection, and comparison against tracks.json.

Runtime state (state/, snapshots/) never touches the public site/ output —
build.py and this module don't import each other. See trackwatch/README.md.
"""

import difflib
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from normalizer import normalize_for_hashing

TW_DIR = Path(__file__).resolve().parent
STATE_DIR = TW_DIR / "state"
SNAPSHOT_DIR = TW_DIR / "snapshots"

DAY_WORDS = ["monday", "tuesday", "wednesday", "thursday", "friday",
             "saturday", "sunday"]
PHONE_RE = re.compile(r"\d{3}[-.\s]?\d{3}[-.\s]?\d{4}")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def source_key(track_slug, source_id):
    return f"{track_slug}__{source_id}"


def content_hash(normalized_text):
    return hashlib.sha256(normalize_for_hashing(normalized_text).encode("utf-8")).hexdigest()


# --- per-source state (etag / last-modified / hash / timestamps) --------

def load_state(key):
    path = STATE_DIR / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(key, state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / f"{key}.json"
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def reset_state(key):
    path = STATE_DIR / f"{key}.json"
    if path.exists():
        path.unlink()
    snap_dir = SNAPSHOT_DIR / key
    for name in ("latest.txt", "previous.txt"):
        p = snap_dir / name
        if p.exists():
            p.unlink()


# --- normalized-text snapshots -------------------------------------------

def load_latest_snapshot(key):
    path = SNAPSHOT_DIR / key / "latest.txt"
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def save_snapshot(key, normalized_text):
    """Rotate latest -> previous, write the new latest."""
    snap_dir = SNAPSHOT_DIR / key
    snap_dir.mkdir(parents=True, exist_ok=True)
    latest_path = snap_dir / "latest.txt"
    if latest_path.exists():
        (snap_dir / "previous.txt").write_text(
            latest_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
    latest_path.write_text(normalized_text, encoding="utf-8")


# --- diffing ---------------------------------------------------------------

def changed_excerpt(before_text, after_text, context=1, max_chars=1200):
    """A compact excerpt of what changed, for both the classifier and the
    human-facing before/after in the review queue. Line-based diff — good
    enough for prose pages, and every line survives normalizer.py's
    whitespace collapsing so lines are a meaningful unit here."""
    before_lines = before_text.split("\n")
    after_lines = after_text.split("\n")
    sm = difflib.SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)

    before_bits, after_bits = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        before_bits.extend(before_lines[i1:i2])
        after_bits.extend(after_lines[j1:j2])

    before_excerpt = "\n".join(before_bits).strip()
    after_excerpt = "\n".join(after_bits).strip()
    return before_excerpt[:max_chars], after_excerpt[:max_chars]


# --- comparison against Gulf South Drags' own data -----------------------

def compare_with_site_data(track, changed_text):
    """Very deliberately shallow: day-of-week and phone-number mismatches
    only, per the brief ('does not have to handle every field in V0.1').
    Returns a list of short human-readable conflict notes, or []."""
    if not track or not changed_text:
        return []
    notes = []
    haystack = changed_text.lower()

    stored_days = {d for d in DAY_WORDS if d in (track.get("race_days") or "").lower()}
    mentioned_days = {d for d in DAY_WORDS if d in haystack}
    new_days = mentioned_days - stored_days
    if stored_days and new_days:
        notes.append(
            f"POSSIBLE CONFLICT WITH CURRENT SITE DATA: source mentions "
            f"{', '.join(d.title() for d in sorted(new_days))}, but our race_days "
            f"currently says: “{track.get('race_days')}”"
        )

    stored_phone = re.sub(r"\D", "", (track.get("phone") or "").split("/")[0])
    for m in PHONE_RE.findall(changed_text):
        digits = re.sub(r"\D", "", m)
        if stored_phone and digits and digits != stored_phone:
            notes.append(
                f"POSSIBLE CONFLICT WITH CURRENT SITE DATA: source shows phone "
                f"{m}, our listing currently shows {track.get('phone')}"
            )
            break

    return notes
