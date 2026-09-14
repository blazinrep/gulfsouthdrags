"""The detection review queue.

Each detection is one JSON file. Its status is literally which folder it
lives in: review/pending -> review/approved | review/ignored. That's the
whole history model — `git log`-free, human-inspectable with `ls` and
`cat`, and impossible to corrupt with a partial write to some bigger
queue.json.

V0.1 stops at "approved for action" — see trackwatch/README.md. Nothing
here ever writes to tracks.json or site/.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

TW_DIR = Path(__file__).resolve().parent
REVIEW_DIR = TW_DIR / "review"
STATUSES = ("pending", "approved", "ignored")

for _s in STATUSES:
    (REVIEW_DIR / _s).mkdir(parents=True, exist_ok=True)


def new_id():
    return "det_" + uuid.uuid4().hex[:12]


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_detection(*, track_slug, source_id, source_url, change_type,
                      confidence, summary, before_excerpt, after_excerpt,
                      keywords, source_hash_before, source_hash_after,
                      conflicts=None):
    record = {
        "id": new_id(),
        "track_slug": track_slug,
        "source_id": source_id,
        "source_url": source_url,
        "detected_at": _now_iso(),
        "change_type": change_type,
        "confidence": confidence,
        "status": "pending",
        "summary": summary,
        "before_excerpt": before_excerpt,
        "after_excerpt": after_excerpt,
        "keywords": keywords,
        "source_hash_before": source_hash_before,
        "source_hash_after": source_hash_after,
        "conflicts_with_site_data": conflicts or [],
        "reviewed_at": None,
    }
    path = REVIEW_DIR / "pending" / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def list_detections(status="pending"):
    folder = REVIEW_DIR / status
    records = []
    for path in sorted(folder.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    records.sort(key=lambda r: r.get("detected_at", ""), reverse=True)
    return records


def get_detection(det_id):
    for status in STATUSES:
        path = REVIEW_DIR / status / f"{det_id}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8")), status
    return None, None


def set_status(det_id, new_status):
    if new_status not in ("approved", "ignored"):
        raise ValueError("set_status only moves items to approved or ignored")
    record, current_status = get_detection(det_id)
    if record is None:
        return None
    old_path = REVIEW_DIR / current_status / f"{det_id}.json"
    record["status"] = new_status
    record["reviewed_at"] = _now_iso()
    new_path = REVIEW_DIR / new_status / f"{det_id}.json"
    new_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    old_path.unlink(missing_ok=True)
    return record


def counts():
    return {status: len(list(( REVIEW_DIR / status).glob("*.json"))) for status in STATUSES}
