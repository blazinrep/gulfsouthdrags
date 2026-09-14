#!/usr/bin/env python3
"""TrackWatch's private local Control Room.

    python3 trackwatch/review_server.py
    -> http://localhost:8765/

Binds to 127.0.0.1 only — never 0.0.0.0. This page is not part of site/
and Cloudflare never sees it; it exists purely for local human review.

V0.2 adds:
- a one-click "Run TrackWatch Sweep" button
- last-sweep status and counts
- visibility into low-value changes that were automatically filtered
- the pending human-review queue below the sweep dashboard

Stdlib only: http.server + subprocess + string templating, no framework.
"""

import html
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

TW_DIR = Path(__file__).resolve().parent
REPO_ROOT = TW_DIR.parent
sys.path.insert(0, str(TW_DIR))

import review_queue as rq  # noqa: E402

TEMPLATE_PATH = TW_DIR / "templates" / "review.html"
LOG_DIR = TW_DIR / "logs"
TRACKWATCH_PY = TW_DIR / "trackwatch.py"
HOST = "127.0.0.1"
PORT = 8765

SWEEP_LOCK = threading.Lock()


def _e(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def render_detection_card(record):
    conflicts_html = ""
    conflicts = record.get("conflicts_with_site_data") or []
    if conflicts:
        items = "".join(f"<li>{_e(c)}</li>" for c in conflicts)
        conflicts_html = (
            '<div class="conflict"><strong>Possible conflict with current site data</strong>'
            f"<ul>{items}</ul></div>"
        )

    keywords = record.get("keywords") or []
    kw_html = "".join(f'<span class="kw">{_e(k)}</span>' for k in keywords)

    return f"""
<article class="card" id="{_e(record['id'])}">
  <div class="card-head">
    <div>
      <span class="track">{_e(record['track_slug'])}</span>
      <span class="source">via {_e(record['source_id'])}</span>
    </div>
    <span class="confidence">confidence {record['confidence']}</span>
  </div>
  <div class="meta">
    <span class="change-type">{_e(record['change_type'].replace('_', ' '))}</span>
    <span class="detected-at">detected {_e(record['detected_at'])}</span>
  </div>
  <p class="summary">{_e(record['summary'])}</p>
  {conflicts_html}
  <div class="diff">
    <div class="before"><h4>Before</h4><pre>{_e(record['before_excerpt']) or '(no prior text)'}</pre></div>
    <div class="after"><h4>After</h4><pre>{_e(record['after_excerpt']) or '(empty)'}</pre></div>
  </div>
  <div class="keywords">{kw_html}</div>
  <div class="actions">
    <form method="post" action="/approve/{_e(record['id'])}"><button class="approve">Approve</button></form>
    <form method="post" action="/ignore/{_e(record['id'])}"><button class="ignore">Ignore</button></form>
    <a class="view-source" href="{_e(record['source_url'])}" target="_blank" rel="noopener">View source →</a>
  </div>
</article>
"""


def _latest_sweep():
    """Return parsed information from the newest TrackWatch sweep log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logs = list(LOG_DIR.glob("sweep_*.log"))
    if not logs:
        return None

    path = max(logs, key=lambda p: p.stat().st_mtime)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    stat_keys = {
        "checked", "baselines", "unchanged", "low_value",
        "queued", "errors", "skipped",
    }
    stats = {key: 0 for key in stat_keys}
    detail_lines = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "TRACKWATCH SWEEP" or set(stripped) == {"-"}:
            continue

        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key in stat_keys and value.isdigit():
                stats[key] = int(value)
                continue

        detail_lines.append(stripped)

    local_dt = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    time_text = local_dt.strftime("%b %d, %Y · %I:%M:%S %p %Z").replace("· 0", "· ")

    return {
        "path": path,
        "time": time_text,
        "stats": stats,
        "details": detail_lines,
    }


def _render_sweep_panel():
    latest = _latest_sweep()

    if latest is None:
        status_class = "neutral"
        headline = "No sweep recorded yet"
        subtext = "Run TrackWatch once to check the enabled track sources."
        stats_html = """
          <div class="stat"><strong>—</strong><span>sources checked</span></div>
          <div class="stat"><strong>—</strong><span>unchanged</span></div>
          <div class="stat"><strong>—</strong><span>filtered</span></div>
          <div class="stat"><strong>—</strong><span>queued</span></div>
          <div class="stat"><strong>—</strong><span>errors</span></div>
        """
        details_html = ""
        last_run = "Never"
    else:
        s = latest["stats"]
        last_run = latest["time"]

        if s["queued"] > 0:
            status_class = "attention"
            headline = f"{s['queued']} item{'s' if s['queued'] != 1 else ''} need review"
            subtext = "TrackWatch found possible racing-related changes. Review them below."
        elif s["errors"] > 0:
            status_class = "warning"
            headline = "Sweep completed with fetch errors"
            subtext = "No review item may be needed, but one or more sources could not be checked."
        else:
            status_class = "clear"
            headline = "Nothing needs your review"
            if s["low_value"]:
                subtext = (
                    f"TrackWatch filtered {s['low_value']} low-value change"
                    f"{'s' if s['low_value'] != 1 else ''} automatically."
                )
            else:
                subtext = "All enabled sources were checked with no meaningful racing changes found."

        stats_html = f"""
          <div class="stat"><strong>{s['checked']}</strong><span>sources checked</span></div>
          <div class="stat"><strong>{s['unchanged']}</strong><span>unchanged</span></div>
          <div class="stat"><strong>{s['low_value']}</strong><span>filtered</span></div>
          <div class="stat"><strong>{s['queued']}</strong><span>queued</span></div>
          <div class="stat"><strong>{s['errors']}</strong><span>errors</span></div>
        """

        if latest["details"]:
            detail_text = "\n".join(latest["details"])
            details_html = f"""
            <details class="sweep-details">
              <summary>Show source-by-source result</summary>
              <pre>{_e(detail_text)}</pre>
            </details>
            """
        else:
            details_html = ""

    return f"""
<section class="sweep-panel">
  <div class="sweep-top">
    <div>
      <div class="eyebrow">TRACKWATCH SWEEP</div>
      <h2 class="sweep-status {status_class}">{_e(headline)}</h2>
      <p class="sweep-subtext">{_e(subtext)}</p>
      <div class="last-run">Last sweep: {_e(last_run)}</div>
    </div>
    <form method="post" action="/sweep" class="sweep-form"
          onsubmit="const b=this.querySelector('button'); b.disabled=true; b.textContent='Running sweep…';">
      <button class="run-sweep" type="submit">Run TrackWatch Sweep</button>
      <span class="run-note">Checks the enabled public sources now.</span>
    </form>
  </div>
  <div class="sweep-stats">
    {stats_html}
  </div>
  {details_html}
</section>
"""


def render_page():
    pending = rq.list_detections("pending")
    counts = rq.counts()

    if pending:
        cards_html = "\n".join(render_detection_card(r) for r in pending)
        queue_heading = f"""
        <section class="queue-heading">
          <div class="eyebrow">HUMAN REVIEW QUEUE</div>
          <h2>{len(pending)} possible racing change{'s' if len(pending) != 1 else ''}</h2>
          <p>Approve or ignore each detection after checking the source.</p>
        </section>
        """
    else:
        queue_heading = """
        <section class="queue-heading">
          <div class="eyebrow">HUMAN REVIEW QUEUE</div>
          <h2>Queue is clear</h2>
          <p>Nothing needs a human decision right now.</p>
        </section>
        """
        cards_html = ""

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return (
        template
        .replace("{{PENDING_COUNT}}", str(counts["pending"]))
        .replace("{{APPROVED_COUNT}}", str(counts["approved"]))
        .replace("{{IGNORED_COUNT}}", str(counts["ignored"]))
        .replace("{{SWEEP_PANEL}}", _render_sweep_panel())
        .replace("{{QUEUE_HEADING}}", queue_heading)
        .replace("{{CARDS}}", cards_html)
    )


def _run_sweep():
    """Run one TrackWatch sweep as a separate process."""
    if not TRACKWATCH_PY.exists():
        raise FileNotFoundError(f"Could not find {TRACKWATCH_PY}")

    return subprocess.run(
        [sys.executable, str(TRACKWATCH_PY), "run"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
        check=False,
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "TrackWatchReview/0.2"

    def log_message(self, fmt, *args):
        sys.stderr.write("[review] " + (fmt % args) + "\n")

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = render_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/sweep":
            if not SWEEP_LOCK.acquire(blocking=False):
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
                return

            try:
                result = _run_sweep()
                if result.returncode != 0:
                    sys.stderr.write("[review] Sweep returned non-zero exit code.\n")
                    sys.stderr.write(result.stdout + "\n")
            except Exception as exc:
                sys.stderr.write(f"[review] Sweep failed: {exc}\n")
            finally:
                SWEEP_LOCK.release()

            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        parts = [p for p in path.split("/") if p]
        if len(parts) == 2 and parts[0] in ("approve", "ignore"):
            det_id = parts[1]
            new_status = "approved" if parts[0] == "approve" else "ignored"
            rq.set_status(det_id, new_status)
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        self.send_error(404, "Not found")


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    url = f"http://{HOST}:{PORT}/"
    print(f"TrackWatch Control Room running at {url}")
    print("Private + local only — never part of site/ and never deployed.")
    print("Press Ctrl+C to stop.")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.shutdown()


if __name__ == "__main__":
    main()
