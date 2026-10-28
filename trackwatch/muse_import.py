"""Import Muse Facebook discoveries into the TrackWatch review queue.

Muse is an external scout only. This importer validates its JSON feed,
deduplicates Facebook findings, and creates normal TrackWatch detections.

Nothing here publishes to the GulfSouthDrags site.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import review_queue as rq


TW_DIR = Path(__file__).resolve().parent


def slugify(name):
    value = name.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def fingerprint(item):
    """Stable identity for the same Facebook finding."""
    source = (
        item.get("post_url")
        or item.get("facebook_page_url")
        or ""
    ).strip()

    text = item.get("text", "").strip()
    date = item.get("date", "").strip()
    track = item.get("track", "").strip()

    raw = "|".join([source, date, track, text])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def existing_muse_hashes():
    hashes = set()

    for status in rq.STATUSES:
        for record in rq.list_detections(status):
            if record.get("source_id") != "muse:facebook":
                continue

            h = record.get("source_hash_after")
            if h:
                hashes.add(h)

    return hashes


def import_feed(feed_path):
    path = Path(feed_path)

    if not path.exists():
        raise FileNotFoundError(f"Muse feed not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError("Muse feed must contain a JSON array.")

    known = existing_muse_hashes()

    created = 0
    duplicates = 0
    skipped = 0

    for item in data:
        if not isinstance(item, dict):
            skipped += 1
            continue

        track = item.get("track", "").strip()
        text = item.get("text", "").strip()
        source_url = (
            item.get("post_url")
            or item.get("facebook_page_url")
            or ""
        ).strip()

        if not track or not text or not source_url:
            skipped += 1
            continue

        fp = fingerprint(item)

        if fp in known:
            duplicates += 1
            continue

        date = item.get("date", "").strip()
        truncated = bool(item.get("truncated", False))

        summary = f"Facebook update from {track}"
        if date:
            summary += f" ({date})"
        if truncated:
            summary += " — source text may be truncated"

        rq.create_detection(
            track_slug=slugify(track),
            source_id="muse:facebook",
            source_url=source_url,
            change_type="facebook_discovery",
            confidence="medium" if truncated else "high",
            summary=summary,
            before_excerpt="",
            after_excerpt=text,
            keywords=["facebook", "muse"],
            source_hash_before="",
            source_hash_after=fp,
            conflicts=[],
        )

        known.add(fp)
        created += 1

    return {
        "examined": len(data),
        "created": created,
        "duplicates": duplicates,
        "skipped": skipped,
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 trackwatch/muse_import.py PATH_TO_MUSE_JSON")
        return 2

    try:
        result = import_feed(sys.argv[1])
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print("TRACKWATCH MUSE IMPORT")
    print("----------------------")
    print(f"{result['examined']} Facebook findings examined")
    print(f"{result['created']} new item(s) queued")
    print(f"{result['duplicates']} duplicate(s) ignored")
    print(f"{result['skipped']} invalid item(s) skipped")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
