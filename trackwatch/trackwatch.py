#!/usr/bin/env python3
"""TrackWatch V0.1 — command-line entry point.

    python3 trackwatch/trackwatch.py run
    python3 trackwatch/trackwatch.py run --track gulfport-dragway
    python3 trackwatch/trackwatch.py run --source official-site --track gulfport-dragway
    python3 trackwatch/trackwatch.py pending
    python3 trackwatch/trackwatch.py status

See trackwatch/README.md for the full pipeline explanation. In short:
source watchers -> change detector -> keyword classifier -> compare against
tracks.json -> private local review queue. Nothing here ever edits
tracks.json or site/ automatically.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

TW_DIR = Path(__file__).resolve().parent
REPO_ROOT = TW_DIR.parent
sys.path.insert(0, str(TW_DIR))

import classifier          # noqa: E402
import detector             # noqa: E402
import fetcher               # noqa: E402
import normalizer            # noqa: E402
import review_queue as rq    # noqa: E402
import discovery             # noqa: E402

SOURCES_PATH = TW_DIR / "config" / "sources.json"
TRACKS_JSON_PATH = REPO_ROOT / "tracks.json"
LOG_DIR = TW_DIR / "logs"


def load_sources():
    return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))


def load_tracks_json():
    return json.loads(TRACKS_JSON_PATH.read_text(encoding="utf-8"))


def get_track_by_slug(tracks_data, slug):
    for t in tracks_data["tracks"]:
        if t["slug"] == slug:
            return t
    return None


def iter_sources(sources_cfg, track_filter=None, source_filter=None):
    for track_slug, track_cfg in sources_cfg["tracks"].items():
        if track_filter and track_slug != track_filter:
            continue
        for src in track_cfg.get("sources", []):
            if source_filter and src["id"] != source_filter:
                continue
            if not src.get("enabled", True):
                continue
            yield track_slug, src


def run_sweep(track_filter=None, source_filter=None, force=False, reset_baseline=False):
    sources_cfg = load_sources()
    defaults = sources_cfg.get("defaults", {})
    tracks_data = load_tracks_json()
    clf = classifier.get_classifier()

    stats = {"checked": 0, "baselines": 0, "unchanged": 0, "low_value": 0,
              "queued": 0, "errors": 0, "skipped": 0}
    log_lines = []

    sources = list(iter_sources(sources_cfg, track_filter, source_filter))
    if not sources:
        print("No enabled sources matched that filter.")
        return stats

    for i, (track_slug, src) in enumerate(sources):
        if src.get("type") != "webpage":
            log_lines.append(f"SKIP     {track_slug}/{src['id']}: unsupported source type {src.get('type')!r}")
            stats["skipped"] += 1
            continue

        key = detector.source_key(track_slug, src["id"])
        if reset_baseline:
            detector.reset_state(key)

        state = detector.load_state(key)

        if i > 0:
            fetcher.polite_sleep(1.0)

        result = fetcher.fetch(
            src["url"],
            user_agent=defaults.get("user_agent", fetcher.DEFAULT_USER_AGENT),
            timeout=defaults.get("timeout_seconds", fetcher.DEFAULT_TIMEOUT),
            etag=("" if force else (state or {}).get("etag", "")),
            last_modified=("" if force else (state or {}).get("last_modified", "")),
        )
        stats["checked"] += 1

        if not result.ok:
            reason = "blocked by robots.txt" if result.blocked_by_robots else result.error
            log_lines.append(f"ERROR    {track_slug}/{src['id']}: {reason}")
            stats["errors"] += 1
            continue

        if result.not_modified:
            log_lines.append(f"OK       {track_slug}/{src['id']}: unchanged (304 Not Modified)")
            stats["unchanged"] += 1
            new_state = dict(state or {})
            new_state["last_checked"] = detector.now_iso()
            new_state["last_status"] = 304
            detector.save_state(key, new_state)
            continue

        text = normalizer.html_to_text(result.body)
        previous_text = detector.load_latest_snapshot(key)

        # A successful HTTP response is not automatically a trustworthy
        # content snapshot. Some sites intermittently return an empty shell,
        # broken template, or nearly blank page with HTTP 200. Never replace
        # the last good baseline with that response.
        current_clean = text.strip()
        previous_clean = (previous_text or "").strip()

        if not current_clean:
            log_lines.append(
                f"ERROR    {track_slug}/{src['id']}: empty normalized response; "
                "last good baseline retained"
            )
            stats["errors"] += 1
            continue

        if (
            previous_clean
            and len(previous_clean) >= 500
            and len(current_clean) < 80
            and len(current_clean) < int(len(previous_clean) * 0.05)
        ):
            log_lines.append(
                f"ERROR    {track_slug}/{src['id']}: suspiciously small response "
                f"({len(current_clean)} chars vs {len(previous_clean)} baseline); "
                "last good baseline retained"
            )
            stats["errors"] += 1
            continue

        new_hash = detector.content_hash(text)
        is_baseline = state is None or previous_text is None

        detector.save_snapshot(key, text)
        new_state = {
            "url": src["url"],
            "final_url": result.final_url,
            "etag": result.etag,
            "last_modified": result.last_modified,
            "content_hash": new_hash,
            "last_checked": detector.now_iso(),
            "last_status": result.status,
            "first_seen": (state or {}).get("first_seen") or detector.now_iso(),
            "baseline_created": True,
        }
        detector.save_state(key, new_state)

        if is_baseline:
            log_lines.append(f"BASELINE {track_slug}/{src['id']}: baseline created")
            stats["baselines"] += 1
            continue

        if new_hash == state.get("content_hash"):
            log_lines.append(f"OK       {track_slug}/{src['id']}: unchanged (hash match)")
            stats["unchanged"] += 1
            continue

        before_excerpt, after_excerpt = detector.changed_excerpt(previous_text, text)
        if not before_excerpt and not after_excerpt:
            log_lines.append(f"OK       {track_slug}/{src['id']}: hash differs but nothing line-level surfaced")
            stats["unchanged"] += 1
            continue

        result_cls = clf.classify(previous_text, text, before_excerpt + "\n" + after_excerpt)

        if not result_cls.is_meaningful:
            log_lines.append(f"CHANGED  {track_slug}/{src['id']}: ignored as low-value ({result_cls.summary})")
            stats["low_value"] += 1
            continue

        track = get_track_by_slug(tracks_data, track_slug)
        conflicts = detector.compare_with_site_data(track, after_excerpt)

        rq.create_detection(
            track_slug=track_slug,
            source_id=src["id"],
            source_url=result.final_url or src["url"],
            change_type=result_cls.change_type,
            confidence=result_cls.confidence,
            summary=result_cls.summary,
            before_excerpt=before_excerpt,
            after_excerpt=after_excerpt,
            keywords=result_cls.keywords,
            source_hash_before=state.get("content_hash"),
            source_hash_after=new_hash,
            conflicts=conflicts,
        )
        log_lines.append(
            f"QUEUED   {track_slug}/{src['id']}: {result_cls.change_type} "
            f"(confidence {result_cls.confidence})"
        )
        stats["queued"] += 1

    _print_report(stats, log_lines)
    _write_log(stats, log_lines)
    return stats


def _print_report(stats, log_lines):
    print("TRACKWATCH SWEEP")
    print("-" * 16)
    for line in log_lines:
        print(line)
    print()
    print(f"{stats['checked']} sources checked")
    if stats["baselines"]:
        print(f"{stats['baselines']} baseline(s) created")
    print(f"{stats['unchanged']} unchanged")
    print(f"{stats['low_value']} changed — ignored as low-value")
    print(f"{stats['queued']} possible racing changes queued")
    print(f"{stats['errors']} fetch errors")
    if stats["skipped"]:
        print(f"{stats['skipped']} source(s) skipped (unsupported type)")


def _write_log(stats, log_lines):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = LOG_DIR / f"sweep_{ts}.log"
    with path.open("w", encoding="utf-8") as f:
        f.write("TRACKWATCH SWEEP\n----------------\n")
        for line in log_lines:
            f.write(line + "\n")
        f.write("\n")
        for k, v in stats.items():
            f.write(f"{k}: {v}\n")
    print(f"\nLog written to {path.relative_to(REPO_ROOT)}")


def cmd_discover(args):
    """Search the public web for relevant racing intelligence."""
    config = discovery.load_config()
    tracks = config.get("tracks", {})
    defaults = config.get("defaults", {})

    max_results = defaults.get("max_results_per_track", 10)

    if args.track:
        if args.track not in tracks:
            print(f"Unknown discovery track: {args.track}")
            return 1
        track_items = [(args.track, tracks[args.track])]
    else:
        track_items = list(tracks.items())

    total_searches = 0
    total_results = 0
    total_candidates = 0
    total_queued = 0

    print("TRACKWATCH DISCOVERY")
    print("--------------------")

    for track_slug, track_cfg in track_items:
        if not track_cfg.get("enabled", True):
            print(f"SKIP     {track_slug}: discovery disabled")
            continue

        names = track_cfg.get("names") or []

        if not names:
            print(f"SKIP     {track_slug}: no track names configured")
            continue

        primary_name = names[0]
        query = f'"{primary_name}" race'

        try:
            results = discovery.brave_search(
                query,
                count=max_results,
            )
        except Exception as exc:
            print(f"ERROR    {track_slug}: {exc}")
            continue

        total_searches += 1
        total_results += len(results)

        candidates = discovery.evaluate_results(
            track_slug,
            results,
        )

        total_candidates += len(candidates)

        queued = discovery.queue_candidates(candidates)
        total_queued += len(queued)

        print(
            f"OK       {track_slug}: "
            f"{len(results)} results, "
            f"{len(candidates)} candidate(s), "
            f"{len(queued)} queued"
        )

        for record in queued:
            print(f"         + {record['summary']}")

    print()
    print(f"{total_searches} web searches")
    print(f"{total_results} search results examined")
    print(f"{total_candidates} qualified discoveries")
    print(f"{total_queued} new item(s) queued for human review")

    return 0


def cmd_pending(_args):
    records = rq.list_detections("pending")
    if not records:
        print("No pending detections.")
        return
    for r in records:
        print(f"[{r['id']}] {r['track_slug']} / {r['source_id']} — {r['change_type']} "
              f"(confidence {r['confidence']})")
        print(f"    {r['summary']}")
        for c in r.get("conflicts_with_site_data") or []:
            print(f"    ! {c}")
    print(f"\n{len(records)} pending detection(s). Review at:\n"
          f"  python3 trackwatch/review_server.py  ->  http://localhost:8765/")


def cmd_status(_args):
    sources_cfg = load_sources()
    n_tracks = len(sources_cfg["tracks"])
    all_sources = [s for t in sources_cfg["tracks"].values() for s in t.get("sources", [])]
    n_enabled = sum(1 for s in all_sources if s.get("enabled"))
    c = rq.counts()
    state_files = list((TW_DIR / "state").glob("*.json"))
    print("TRACKWATCH STATUS")
    print("-" * 17)
    print(f"{n_tracks} tracks in source registry")
    print(f"{len(all_sources)} sources configured ({n_enabled} enabled)")
    print(f"{len(state_files)} source baseline(s) on disk")
    print(f"{c['pending']} pending review")
    print(f"{c['approved']} approved")
    print(f"{c['ignored']} ignored")


def main():
    parser = argparse.ArgumentParser(prog="trackwatch", description="TrackWatch V0.1 monitoring bot")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run enabled watchers once")
    p_run.add_argument("--track", help="Limit to one track slug")
    p_run.add_argument("--source", help="Limit to one source id (use with --track)")
    p_run.add_argument("--force", action="store_true",
                        help="Ignore ETag/Last-Modified caching for this run")
    p_run.add_argument("--reset-baseline", action="store_true",
                        help="Deliberately clear the baseline for the matched source(s) first")

    p_discover = sub.add_parser(
        "discover",
        help="Search the public web for racing intelligence",
    )
    p_discover.add_argument(
        "--track",
        help="Limit discovery to one track slug",
    )

    sub.add_parser("pending", help="List pending detections")
    sub.add_parser("status", help="Show registry and queue status")

    args = parser.parse_args()
    if args.command == "run":
        run_sweep(track_filter=args.track, source_filter=args.source,
                  force=args.force, reset_baseline=args.reset_baseline)
    elif args.command == "discover":
        cmd_discover(args)
    elif args.command == "pending":
        cmd_pending(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
