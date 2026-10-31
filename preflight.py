#!/usr/bin/env python3
"""GulfSouthDrags preflight check — one command, PASS/FAIL.

Proposed home: the gulfsouthdrags repo root, run from the repo root:
    python3 preflight.py [--root DIR]

Stdlib only. No network, no writes outside <root>/site (which build.py
regenerates), no deployment. Exit 0 on PASS, 1 on FAIL.

What it checks, in order:
  1. build.py compiles.
  2. tracks.json / tow_reports.json parse and conform to the shapes
     build.py actually consumes (field presence, types, unique slugs,
     unique (track_slug, start_iso) pairs, resolvable track refs,
     event `alert` MUST be an object — the 2026-10-30 lesson: a string
     alert crashes build.py at `x["alert"].get(...)`).
  3. functions/api/lead.js still exists with its signup contract intact.
  4. The real build runs: `python3 build.py` must exit 0.
  5. Generated output: expected page count and files, every data URL
     generated, sitemap/robots/llms.txt/404 present, no broken internal
     links, one <h1> + title + description per page, signup forms intact.

Warnings are reported but do not fail the run. Errors fail it.
A candidate is NOT "ready to deploy" unless this script prints PASS.
"""

import argparse
import html.parser
import json
import os
import re
import subprocess
import sys

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TRACK_STATUSES = {"open", "closed", "at-risk", "likely-closed", "unconfirmed"}
EVENT_TYPES = {"drag", "road-course", "other"}


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


def is_iso_date(s):
    return isinstance(s, str) and bool(ISO_DATE.match(s))


def is_pair_list(v):
    return (
        isinstance(v, list)
        and all(isinstance(p, list) and len(p) == 2
                and all(isinstance(x, str) for x in p) for p in v)
    )


def check_data(root, rep):
    """Schema/type checks against what build.py consumes. Returns data or None."""
    try:
        with open(os.path.join(root, "tracks.json")) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        rep.err(f"tracks.json unreadable/invalid JSON: {exc}")
        return None
    try:
        with open(os.path.join(root, "tow_reports.json")) as f:
            tow = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        rep.err(f"tow_reports.json unreadable/invalid JSON: {exc}")
        return None

    site = data.get("site")
    if not isinstance(site, dict):
        rep.err("tracks.json: missing 'site' object")
        return None
    for key in ("name", "domain", "last_checked"):
        if not site.get(key):
            rep.err(f"tracks.json: site.{key} missing/empty")
    if not is_iso_date(site.get("last_checked", "")):
        rep.err(f"tracks.json: site.last_checked not ISO date: {site.get('last_checked')!r}")

    tracks = data.get("tracks")
    events = data.get("events")
    series = data.get("series", [])
    if not isinstance(tracks, list) or not tracks:
        rep.err("tracks.json: 'tracks' must be a non-empty list")
        return None
    if not isinstance(events, list):
        rep.err("tracks.json: 'events' must be a list")
        return None
    if not isinstance(series, list):
        rep.err("tracks.json: 'series' must be a list")
        return None

    track_slugs = set()
    for i, t in enumerate(tracks):
        if not isinstance(t, dict):
            rep.err(f"tracks[{i}]: not an object")
            continue
        slug = t.get("slug")
        if not slug:
            rep.err(f"tracks[{i}]: missing slug")
        elif slug in track_slugs:
            rep.err(f"duplicate track slug: {slug}")
        track_slugs.add(slug)
        for key in ("name", "city", "state", "length", "surface", "sanction",
                    "race_days", "address", "notes", "verified", "status"):
            if t.get(key) in (None, ""):
                rep.err(f"track {slug}: missing/empty {key}")
        if t.get("status") not in TRACK_STATUSES:
            rep.err(f"track {slug}: unknown status {t.get('status')!r}")
        if not is_iso_date(t.get("verified", "")):
            rep.err(f"track {slug}: verified not ISO date: {t.get('verified')!r}")
        if not isinstance(t.get("lat"), (int, float)) or not isinstance(t.get("lon"), (int, float)):
            rep.err(f"track {slug}: lat/lon must be numbers")
        if not isinstance(t.get("miles"), (int, float)):
            rep.err(f"track {slug}: miles must be a number")

    event_slugs = set()
    pairs = set()
    for i, x in enumerate(events):
        if not isinstance(x, dict):
            rep.err(f"events[{i}]: not an object")
            continue
        slug = x.get("slug")
        if not slug:
            rep.err(f"events[{i}]: missing slug")
        elif slug in event_slugs:
            rep.err(f"duplicate event slug: {slug}")
        event_slugs.add(slug)
        pair = (x.get("track_slug"), x.get("start_iso"))
        if pair in pairs:
            rep.err(f"duplicate (track_slug, start_iso) pair: {pair}")
        pairs.add(pair)
        if x.get("track_slug") not in track_slugs:
            rep.err(f"event {slug}: track_slug {x.get('track_slug')!r} has no track")
        for key in ("name", "track_slug", "track_name", "dates", "start_iso",
                    "summary", "detail", "source", "verified"):
            if x.get(key) in (None, ""):
                rep.err(f"event {slug}: missing/empty {key}")
        if x.get("event_type", "drag") not in EVENT_TYPES:
            rep.err(f"event {slug}: unknown event_type {x.get('event_type')!r}")
        if not is_iso_date(x.get("start_iso", "")):
            rep.err(f"event {slug}: start_iso not ISO date: {x.get('start_iso')!r}")
        if x.get("end_iso") and not is_iso_date(x["end_iso"]):
            rep.err(f"event {slug}: end_iso not ISO date: {x.get('end_iso')!r}")
        if not is_iso_date(x.get("verified", "")):
            rep.err(f"event {slug}: verified not ISO date: {x.get('verified')!r}")
        if not is_pair_list(x.get("schedule", [])):
            rep.err(f"event {slug}: schedule must be a list of [label, text] pairs")
        if not is_pair_list(x.get("prices", [])):
            rep.err(f"event {slug}: prices must be a list of [label, text] pairs")
        alert = x.get("alert")
        if alert is not None:
            if not isinstance(alert, dict):
                # THE 2026-10-30 FAILURE: build_event calls alert.get(...).
                rep.err(f"event {slug}: alert must be an object, got {type(alert).__name__}")
            else:
                if not isinstance(alert.get("label"), str) or not alert["label"].strip():
                    rep.err(f"event {slug}: alert.label must be a non-empty string")
                if not alert.get("headline") and not alert.get("detail"):
                    rep.warn(f"event {slug}: alert has neither headline nor detail; "
                             "the alert box will render empty")

    series_slugs = set()
    for i, s in enumerate(series):
        if not isinstance(s, dict):
            rep.err(f"series[{i}]: not an object")
            continue
        slug = s.get("slug")
        if not slug:
            rep.err(f"series[{i}]: missing slug")
        elif slug in series_slugs:
            rep.err(f"duplicate series slug: {slug}")
        series_slugs.add(slug)
        for key in ("name", "region", "sanction", "answer", "notes", "verified"):
            if s.get(key) in (None, ""):
                rep.err(f"series {slug}: missing/empty {key}")
        for ts in s.get("tracks", []):
            if ts not in track_slugs:
                rep.err(f"series {slug}: unknown host track slug {ts!r}")

    reports = tow.get("reports", None)
    if not isinstance(reports, list):
        rep.err("tow_reports.json: 'reports' must be a list")
        return None
    report_slugs = set()
    for i, r in enumerate(reports):
        if not isinstance(r, dict):
            rep.err(f"reports[{i}]: not an object")
            continue
        slug = r.get("slug")
        if not slug:
            rep.err(f"reports[{i}]: missing slug")
        elif slug in report_slugs:
            rep.err(f"duplicate tow report slug: {slug}")
        report_slugs.add(slug)
        for key in ("number", "date", "title", "subject", "preview"):
            if r.get(key) in (None, ""):
                rep.err(f"tow report {slug}: missing/empty {key}")
        alert = r.get("alert")
        if not isinstance(alert, dict):
            rep.err(f"tow report {slug}: alert must be an object")
        else:
            for key in ("label", "headline", "body", "href"):
                if not alert.get(key):
                    rep.err(f"tow report {slug}: alert.{key} missing/empty")
            if not isinstance(alert.get("bullets", []), list):
                rep.err(f"tow report {slug}: alert.bullets must be a list")
        for key in ("feature", "worth"):
            block = r.get(key)
            if not isinstance(block, dict):
                rep.err(f"tow report {slug}: {key} must be an object")
        if not isinstance(r.get("questions", []), list):
            rep.err(f"tow report {slug}: questions must be a list")

    return {"site": site, "tracks": tracks, "events": events,
            "series": series, "reports": reports}


class LinkParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.forms = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "a" and d.get("href"):
            self.links.append(d["href"])
        if tag == "form":
            self.forms.append(d)


def check_output(root, data, rep):
    """Checks against the generated site/ directory."""
    out = os.path.join(root, "site")
    n_expected = (5 + len(data["reports"]) + len(data["tracks"])
                  + len(data["events"]) + len(data["series"]))
    expected_urls = {"/", "/drag-strips/mississippi/", "/partners/",
                     "/tow-report/"}
    expected_urls |= {f"/tow-report/{r['slug']}/" for r in data["reports"]}
    expected_urls |= {f"/tracks/{t['slug']}/" for t in data["tracks"]}
    expected_urls |= {f"/events/{x['slug']}/" for x in data["events"]}
    expected_urls |= {f"/series/{s['slug']}/" for s in data["series"]}

    pages = []
    for dirpath, _dirs, files in os.walk(out):
        for fn in files:
            if fn == "index.html":
                pages.append(os.path.join(dirpath, fn))
    if len(pages) != n_expected:
        rep.err(f"page count {len(pages)} != expected {n_expected} "
                "(5 + reports + tracks + events + series)")

    for rel in ("index.html", "sitemap.xml", "robots.txt", "llms.txt", "404.html"):
        if not os.path.isfile(os.path.join(out, rel)):
            rep.err(f"missing generated file: site/{rel}")
    for url in sorted(expected_urls):
        path = os.path.join(out, url.strip("/"), "index.html") if url != "/" \
            else os.path.join(out, "index.html")
        if not os.path.isfile(path):
            rep.err(f"missing generated page for {url}")

    # _redirects is generated only when some track has former_slugs.
    former = [t for t in data["tracks"] if t.get("former_slugs")]
    redirects_path = os.path.join(out, "_redirects")
    if former and not os.path.isfile(redirects_path):
        rep.err("missing site/_redirects (tracks carry former_slugs)")
    redirect_sources = set()
    if os.path.isfile(redirects_path):
        with open(redirects_path) as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    redirect_sources.add(parts[0])

    with open(os.path.join(out, "sitemap.xml")) as f:
        sitemap = f.read()
    base = f"https://{data['site']['domain']}"
    sitemap_urls = set(re.findall(r"<loc>(.*?)</loc>", sitemap))
    expected_sitemap = {base + u for u in expected_urls}
    missing = expected_sitemap - sitemap_urls
    if missing:
        rep.err(f"sitemap missing {len(missing)} URLs, e.g. {sorted(missing)[:3]}")
    with open(os.path.join(out, "robots.txt")) as f:
        robots = f.read()
    if "Sitemap:" not in robots:
        rep.err("robots.txt has no Sitemap line")
    with open(os.path.join(out, "llms.txt")) as f:
        llms = f.read()
    if "Last checked:" not in llms:
        rep.err("llms.txt has no Last checked line")

    # Internal links + per-page basics + signup forms.
    valid_targets = set()
    for dirpath, _dirs, files in os.walk(out):
        for fn in files:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, out).replace(os.sep, "/")
            if rel.endswith("/index.html"):
                valid_targets.add("/" + rel[: -len("index.html")])
            else:
                valid_targets.add("/" + rel)
    valid_targets |= redirect_sources
    valid_targets.add("/404.html")

    broken = set()
    forms_found = {"home": 0, "track": 0, "event": 0}
    for page in pages:
        with open(page, errors="replace") as f:
            html_text = f.read()
        rel = os.path.relpath(page, out).replace(os.sep, "/")
        parser = LinkParser()
        parser.feed(html_text)
        for href in parser.links:
            if href.startswith(("http://", "https://", "mailto:", "#", "javascript:")):
                continue
            target = href.split("#")[0].split("?")[0]
            if not target.startswith("/"):
                continue
            if target == "/":
                continue
            if target.endswith("/"):
                if target not in valid_targets:
                    broken.add((rel, href))
            elif target not in valid_targets:
                broken.add((rel, href))
        title = re.search(r"<title>(.*?)</title>", html_text, re.S)
        if not title or not title.group(1).strip():
            rep.err(f"{rel}: missing/empty <title>")
        if '<meta name="description" content=""' in html_text or \
                'name="description" content="' not in html_text:
            rep.err(f"{rel}: missing/empty meta description")
        if html_text.count("<h1") != 1:
            rep.err(f"{rel}: expected exactly 1 <h1>, found {html_text.count('<h1')}")
        if "googletagmanager.com" not in html_text:
            rep.warn(f"{rel}: no analytics snippet found")
        lead_forms = [fm for fm in parser.forms
                      if fm.get("action") == "/api/lead"]
        if lead_forms:
            bucket = ("home" if rel == "index.html" else
                      "track" if rel.startswith("tracks/") else
                      "event" if rel.startswith("events/") else None)
            if bucket:
                forms_found[bucket] += len(lead_forms)
            if 'name="fax_number"' not in html_text:
                rep.err(f"{rel}: lead form missing honeypot field fax_number")
            if 'name="kind"' not in html_text or 'name="source"' not in html_text:
                rep.err(f"{rel}: lead form missing hidden kind/source fields")
    for link_rel, href in sorted(broken):
        rep.err(f"broken internal link: {link_rel} -> {href}")
    if forms_found["home"] < 1:
        rep.err("homepage has no /api/lead signup form")
    if forms_found["track"] < 1:
        rep.err("no track page carries an /api/lead signup form")
    if forms_found["event"] < 1:
        rep.err("no event page carries an /api/lead signup form")
    return {"pages": len(pages), "expected": n_expected,
            "broken_links": len(broken)}


def main():
    ap = argparse.ArgumentParser(description="GulfSouthDrags preflight check")
    ap.add_argument("--root", default=os.getcwd(),
                    help="repo root (default: current directory)")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    rep = Report()

    build_py = os.path.join(root, "build.py")
    if not os.path.isfile(build_py):
        rep.err(f"build.py not found under {root}")
        print("PREFLIGHT: FAIL")
        for msg in rep.errors:
            print(f"  ERROR: {msg}")
        return 1
    rc = subprocess.run([sys.executable, "-m", "py_compile", build_py],
                        capture_output=True, text=True)
    if rc.returncode != 0:
        rep.err(f"build.py does not compile:\n{rc.stderr.strip()}")

    lead_js = os.path.join(root, "functions", "api", "lead.js")
    if not os.path.isfile(lead_js):
        rep.err("missing functions/api/lead.js (signup endpoint)")
    else:
        with open(lead_js) as f:
            js = f.read()
        for marker in ("onRequestPost", "GSD_LEADS_DB", "tow_report", "/thanks/"):
            if marker not in js:
                rep.err(f"functions/api/lead.js missing contract marker: {marker}")
    if not os.path.isfile(os.path.join(root, "assets", "style.css")):
        rep.err("missing assets/style.css")
    if not os.path.isfile(os.path.join(
            root, "assets", "gulfsouthdrags-homepage-banner.png")):
        rep.err("missing homepage banner asset")

    data = check_data(root, rep)
    if data is None or rep.errors:
        print("PREFLIGHT: FAIL (data/schema checks)")
        for msg in rep.errors:
            print(f"  ERROR: {msg}")
        for msg in rep.warnings:
            print(f"  WARNING: {msg}")
        return 1

    rc = subprocess.run([sys.executable, "build.py"], cwd=root,
                        capture_output=True, text=True, timeout=120)
    if rc.returncode != 0:
        rep.err(f"build.py failed (exit {rc.returncode}):\n{rc.stderr.strip()[-800:]}")
        print("PREFLIGHT: FAIL (build)")
        for msg in rep.errors:
            print(f"  ERROR: {msg}")
        return 1
    built = re.search(r"Built (\d+) pages", rc.stdout)
    if not built:
        rep.err(f"build.py output unexpected: {rc.stdout.strip()[:200]}")

    stats = check_output(root, data, rep)
    status = "FAIL" if rep.errors else "PASS"
    print(f"PREFLIGHT: {status}")
    print(f"  pages: {stats['pages']} (expected {stats['expected']})")
    print(f"  broken internal links: {stats['broken_links']}")
    print(f"  tracks: {len(data['tracks'])}  events: {len(data['events'])}  "
          f"series: {len(data['series'])}  tow reports: {len(data['reports'])}")
    for msg in rep.errors:
        print(f"  ERROR: {msg}")
    for msg in rep.warnings:
        print(f"  WARNING: {msg}")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
