#!/usr/bin/env python3
"""TrackWatch scheduled sweep runner for macOS.

Runs the existing TrackWatch sweep, then stays quiet unless:
- one or more possible racing changes are waiting for human review, or
- one or more sources failed to fetch.

Designed to be launched by a macOS LaunchAgent. It never edits tracks.json
or site/ and never publishes anything automatically.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TW_DIR = Path(__file__).resolve().parent
REPO_ROOT = TW_DIR.parent
TRACKWATCH_PY = TW_DIR / "trackwatch.py"
LOG_DIR = TW_DIR / "logs"
SCHEDULER_LOG = LOG_DIR / "scheduler.log"

sys.path.insert(0, str(TW_DIR))
import review_queue as rq  # noqa: E402


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    line = f"[{stamp}] {message}"
    print(line)
    with SCHEDULER_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def notify(message: str, *, sound: bool = True) -> bool:
    """Send a local macOS Notification Center alert."""
    script = [
        "on run argv",
        'set msg to item 1 of argv',
    ]
    if sound:
        script.append(
            'display notification msg with title "TrackWatch" subtitle "GulfSouthDrags" sound name "Glass"'
        )
    else:
        script.append(
            'display notification msg with title "TrackWatch" subtitle "GulfSouthDrags"'
        )
    script.append("end run")

    cmd = ["/usr/bin/osascript"]
    for line in script:
        cmd.extend(["-e", line])
    cmd.append(message)

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        log(f"NOTIFY ERROR: {exc}")
        return False

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown osascript error").strip()
        log(f"NOTIFY ERROR: {detail}")
        return False
    return True


def latest_sweep_log(after_ts: float | None = None) -> Path | None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logs = list(LOG_DIR.glob("sweep_*.log"))
    if not logs:
        return None
    logs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if after_ts is None:
        return logs[0]
    # Allow a couple seconds of filesystem timestamp slop.
    for path in logs:
        if path.stat().st_mtime >= after_ts - 2:
            return path
    return None


def parse_stats(path: Path | None) -> dict[str, int]:
    stats = {
        "checked": 0,
        "baselines": 0,
        "unchanged": 0,
        "low_value": 0,
        "queued": 0,
        "errors": 0,
        "skipped": 0,
    }
    if path is None or not path.exists():
        return stats

    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(
            r"^(checked|baselines|unchanged|low_value|queued|errors|skipped):\s*(\d+)\s*$",
            line.strip(),
        )
        if match:
            stats[match.group(1)] = int(match.group(2))
    return stats


def run_once() -> int:
    if not TRACKWATCH_PY.exists():
        log(f"ERROR: missing {TRACKWATCH_PY}")
        notify("Automatic sweep could not start because trackwatch.py is missing.")
        return 2

    start_ts = datetime.now().timestamp()
    log("Automatic sweep starting.")

    try:
        proc = subprocess.run(
            [sys.executable, str(TRACKWATCH_PY), "run"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired:
        log("ERROR: sweep timed out after 180 seconds.")
        notify("TrackWatch sweep timed out. Open the Control Room or check the scheduler log.")
        return 3
    except Exception as exc:
        log(f"ERROR: could not run sweep: {exc}")
        notify("TrackWatch could not run its automatic sweep. Check the scheduler log.")
        return 4

    sweep_log = latest_sweep_log(after_ts=start_ts)
    stats = parse_stats(sweep_log)
    pending_total = rq.counts().get("pending", 0)

    log(
        "Sweep finished: "
        f"{stats['checked']} checked, {stats['unchanged']} unchanged, "
        f"{stats['low_value']} filtered, {stats['queued']} newly queued, "
        f"{stats['errors']} errors, {pending_total} total pending."
    )

    if proc.returncode != 0:
        log(f"ERROR: trackwatch.py returned exit code {proc.returncode}.")
        notify("TrackWatch finished with an error. Open the Control Room or check the scheduler log.")
        return proc.returncode

    # Human attention policy:
    # 1) New queued changes: alert immediately.
    # 2) Existing pending review: keep reminding on each scheduled sweep until cleared.
    # 3) Fetch errors: alert because 'couldn't check' is not the same as 'no change'.
    # 4) Low-value changes and clean sweeps: stay silent.
    if stats["queued"] > 0:
        plural = "change" if stats["queued"] == 1 else "changes"
        waiting = (
            f" {pending_total} item{'s' if pending_total != 1 else ''} "
            "are waiting in the Control Room."
        )
        notify(f"Found {stats['queued']} new possible racing {plural}.{waiting}")
    elif pending_total > 0:
        notify(
            f"You still have {pending_total} TrackWatch item"
            f"{'s' if pending_total != 1 else ''} waiting for review."
        )
    elif stats["errors"] > 0:
        notify(
            f"TrackWatch could not check {stats['errors']} source"
            f"{'s' if stats['errors'] != 1 else ''}. Open the Control Room for details."
        )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TrackWatch scheduled sweep runner")
    parser.add_argument(
        "--test-notification",
        action="store_true",
        help="Send a test macOS notification and exit without running a sweep.",
    )
    args = parser.parse_args()

    if args.test_notification:
        ok = notify(
            "Automatic monitoring is installed. I’ll stay quiet unless something needs review or a source fails."
        )
        if ok:
            log("Test notification sent.")
            return 0
        return 1

    return run_once()


if __name__ == "__main__":
    raise SystemExit(main())
