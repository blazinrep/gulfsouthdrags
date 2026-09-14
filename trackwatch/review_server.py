#!/usr/bin/env python3
"""TrackWatch's private review queue.

    python3 trackwatch/review_server.py
    -> http://localhost:8765/

Binds to 127.0.0.1 only — never 0.0.0.0. This page is not part of site/
and Cloudflare never sees it; it exists purely for local human review.
Stdlib only: http.server + string templating, no framework.
"""

import html
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TW_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TW_DIR))

import review_queue as rq  # noqa: E402

TEMPLATE_PATH = TW_DIR / "templates" / "review.html"
HOST = "127.0.0.1"
PORT = 8765


def _e(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def render_detection_card(record):
    conflicts_html = ""
    conflicts = record.get("conflicts_with_site_data") or []
    if conflicts:
        items = "".join(f"<li>{_e(c)}</li>" for c in conflicts)
        conflicts_html = f'<div class="conflict"><strong>Possible conflict with current site data</strong><ul>{items}</ul></div>'

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


def render_page():
    pending = rq.list_detections("pending")
    counts = rq.counts()

    if pending:
        cards_html = "\n".join(render_detection_card(r) for r in pending)
    else:
        cards_html = '<p class="empty">No pending detections. Run <code>python3 trackwatch/trackwatch.py run</code> to sweep sources.</p>'

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    return (
        template
        .replace("{{PENDING_COUNT}}", str(counts["pending"]))
        .replace("{{APPROVED_COUNT}}", str(counts["approved"]))
        .replace("{{IGNORED_COUNT}}", str(counts["ignored"]))
        .replace("{{CARDS}}", cards_html)
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "TrackWatchReview/0.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[review] " + (fmt % args) + "\n")

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            body = render_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        path = urlparse(self.path).path
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
    print(f"TrackWatch review queue running at {url}")
    print("This is a private, local-only page — it is never part of site/ and is never deployed.")
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
