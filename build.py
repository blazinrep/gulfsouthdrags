#!/usr/bin/env python3
"""Build Gulf South Drags from tracks.json.

Usage:  python3 build.py
Edit tracks.json, run this, commit. Nothing to install.

Output uses directory-style URLs (/tracks/gulfport-dragway/) and carries
Schema.org JSON-LD so search engines and answer engines can read the facts
without parsing the page.
"""

import html
import json
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "site")

LON_MIN, LON_MAX = -94.5, -84.6
LAT_MIN, LAT_MAX = 28.85, 35.15
MAP_W, MAP_H = 960, 720


def px(lon, lat):
    x = (lon - LON_MIN) / (LON_MAX - LON_MIN) * MAP_W
    y = (LAT_MAX - lat) / (LAT_MAX - LAT_MIN) * MAP_H
    return round(x, 1), round(y, 1)


def path_of(points):
    return "M " + " L ".join(f"{px(lo, la)[0]},{px(lo, la)[1]}" for lo, la in points) + " Z"


# Shared borders, defined once so the polygons meet exactly.
RIVER = [
    (-91.05, 33.00), (-91.18, 32.60), (-91.02, 32.25), (-91.45, 31.95),
    (-91.32, 31.60), (-91.50, 31.28), (-91.16, 30.99),
]
PEARL = [(-89.75, 31.00), (-89.65, 30.60), (-89.60, 30.18)]

MISSISSIPPI = (
    [(-90.31, 34.99), (-88.20, 34.99), (-88.33, 32.99), (-88.42, 31.89),
     (-88.44, 30.99), (-88.40, 30.39), (-88.90, 30.39), (-89.32, 30.25)]
    + PEARL[::-1] + [(-91.16, 30.99)] + RIVER[::-1][1:]
    + [(-91.13, 33.42), (-90.90, 33.70), (-90.55, 34.08), (-90.58, 34.40),
       (-90.20, 34.70)]
)

ALABAMA = [
    (-88.20, 34.99), (-85.61, 34.99), (-85.47, 33.90), (-85.14, 32.87),
    (-85.00, 32.52), (-84.92, 32.26), (-85.11, 31.79), (-85.05, 31.33),
    (-85.00, 31.00), (-87.60, 31.00), (-87.52, 30.99), (-87.60, 30.40),
    (-88.10, 30.23), (-88.40, 30.39), (-88.44, 30.99), (-88.42, 31.89),
    (-88.33, 32.99),
]

LOUISIANA = (
    [(-94.04, 33.02)] + RIVER + PEARL
    + [(-89.40, 29.85), (-89.02, 29.20), (-89.35, 29.05), (-90.10, 29.15),
       (-90.80, 29.10), (-91.60, 29.55), (-92.20, 29.55), (-93.00, 29.75),
       (-93.85, 29.68), (-93.72, 30.05), (-93.55, 30.30), (-93.75, 31.00),
       (-94.04, 31.60)]
)

STATE_LABELS = [("MISSISSIPPI", -89.9, 33.6), ("ALABAMA", -86.9, 33.6),
                ("LOUISIANA", -92.6, 31.2)]

STATE_NAME = {"MS": "Mississippi", "LA": "Louisiana", "AL": "Alabama"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def e(s):
    return html.escape(s or "", quote=True)


def nice_date(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MONTHS[int(m) - 1]} {y}"


def jsonld(obj):
    return ('<script type="application/ld+json">'
            + json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            + "</script>")


def faq_block(pairs):
    """Visible Q&A. Answer engines lift these; so do featured snippets."""
    if not pairs:
        return "", None
    items = "".join(f"<h3>{e(q)}</h3><p>{e(a)}</p>" for q, a in pairs)
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in pairs],
    }
    return f'<section class="section faq prose"><h2>Common questions</h2>{items}</section>', schema


def build_map(tracks):
    parts = [f'<svg viewBox="0 0 {MAP_W} {MAP_H}" role="img" '
             f'aria-label="Map of drag strips across Mississippi, Louisiana and Alabama" '
             f'xmlns="http://www.w3.org/2000/svg">']
    for shape in (LOUISIANA, MISSISSIPPI, ALABAMA):
        parts.append(f'<path class="state-shape" d="{path_of(shape)}"/>')
    for name, lon, lat in STATE_LABELS:
        x, y = px(lon, lat)
        parts.append(f'<text class="state-label" x="{x}" y="{y}" text-anchor="middle">{name}</text>')
    gx, gy = px(-90.6, 29.0)
    parts.append(f'<text class="gulf-label" x="{gx}" y="{gy}" text-anchor="middle">Gulf of Mexico</text>')
    for i, t in enumerate(tracks, 1):
        x, y = px(t["lon"], t["lat"])
        cls = "pin is-unconfirmed" if t["status"] == "unconfirmed" else "pin"
        parts.append(
            f'<g class="{cls}"><a href="/tracks/{t["slug"]}/">'
            f'<title>{e(t["name"])} \u2014 {e(t["city"])}, {e(t["state"])}</title>'
            f'<circle cx="{x}" cy="{y}" r="15"/>'
            f'<text x="{x}" y="{y + 5.5}">{i}</text></a></g>')
    parts.append("</svg>")
    return "\n".join(parts)


def head(title, desc, path, schemas, modified):
    base = f'https://{SITE["domain"]}'
    url = base + path
    blocks = "".join(jsonld(s) for s in schemas if s)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{e(SITE['name'])}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(desc)}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<meta name="author" content="{e(SITE['name'])}">
<meta property="article:modified_time" content="{modified}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;600;700&family=Archivo+Black&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css">
{blocks}
</head>
<body>
<header class="masthead wrap">
<a class="wordmark" href="/"><span class="bulb"></span>{e(SITE['name'])}</a>
<span class="stamp">Last checked <time datetime="{SITE['last_checked']}">{nice_date(SITE['last_checked'])}</time></span>
</header>
"""


FOOT = """
<footer class="wrap">
<p>Gulf South Drags lists drag strips in Mississippi, Louisiana and Alabama. Every listing carries the date we last checked it. Schedules change and tracks rain out &mdash; call ahead before you load the trailer.</p>
<p>Not affiliated with NHRA, IHRA, WDRA or any track listed here.</p>
</footer>
</body>
</html>
"""


def crumbs(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i, "name": n,
                 "item": f'https://{SITE["domain"]}{u}'}
                for i, (n, u) in enumerate(items, 1)]}


def track_schema(t):
    base = f'https://{SITE["domain"]}'
    same = [u for u in (t.get("website"), t.get("facebook")) if u]
    obj = {
        "@context": "https://schema.org",
        "@type": "SportsActivityLocation",
        "@id": f'{base}/tracks/{t["slug"]}/#track',
        "name": t["name"],
        "url": f'{base}/tracks/{t["slug"]}/',
        "description": t.get("answer") or t["notes"][:300],
        "address": {"@type": "PostalAddress", "streetAddress": t["address"],
                    "addressLocality": t["city"], "addressRegion": t["state"],
                    "addressCountry": "US"},
        "geo": {"@type": "GeoCoordinates", "latitude": t["lat"], "longitude": t["lon"]},
        "additionalType": "https://en.wikipedia.org/wiki/Dragstrip",
    }
    if t.get("phone"):
        obj["telephone"] = t["phone"].split("/")[0].strip()
    if same:
        obj["sameAs"] = same
    return obj


def build_index(data):
    tracks, events, s = data["tracks"], data["events"], data["site"]
    base = f'https://{s["domain"]}'

    rows = []
    for i, t in enumerate(tracks, 1):
        flag = ""
        if t["status"] == "unconfirmed":
            flag = '<span class="flag flag-unconfirmed">Unconfirmed</span>'
        elif t["slug"] == "swamp-bottom-dragstrip":
            flag = '<span class="flag flag-new">New</span>'
        meta = f'{e(t["length"])} &middot; {e(t["city"])}, {e(t["state"])}'
        if t["sanction"] and t["sanction"] != "Unconfirmed":
            meta += f' &middot; {e(t["sanction"].split("—")[0].strip())}'
        rows.append(
            f'<a class="row" href="/tracks/{t["slug"]}/">'
            f'<span class="row-num">{i}</span>'
            f'<span><span class="row-name">{e(t["name"])}{flag}</span>'
            f'<span class="row-meta">{meta}</span></span>'
            f'<span class="row-dist">{t["miles"]} mi</span></a>')

    ev = "".join(
        f'<a class="event-card" href="/events/{x["slug"]}/">'
        f'<span class="event-when">{e(x["dates"])}</span>'
        f'<span class="event-name">{e(x["name"])}</span>'
        f'<span class="event-where">{e(x["track_name"])} &mdash; {e(x["city"])}, {e(x["state"])}</span></a>'
        for x in events)

    ser = "".join(
        f'<a class="event-card" href="/series/{x["slug"]}/">'
        f'<span class="event-when">{e(x["sanction"])}</span>'
        f'<span class="event-name">{e(x["name"])}</span>'
        f'<span class="event-where">{e(x["region"])}</span></a>'
        for x in data["series"])

    faq_html, faq_schema = faq_block([tuple(p) for p in data["faq"]])

    itemlist = {
        "@context": "https://schema.org", "@type": "ItemList",
        "name": "Drag strips in Mississippi, Louisiana and Alabama",
        "numberOfItems": len(tracks),
        "itemListElement": [
            {"@type": "ListItem", "position": i,
             "url": f'{base}/tracks/{t["slug"]}/', "name": t["name"]}
            for i, t in enumerate(tracks, 1)],
    }
    website = {
        "@context": "https://schema.org", "@type": "WebSite",
        "@id": f"{base}/#website", "name": s["name"], "url": base + "/",
        "description": s["description"], "inLanguage": "en-US",
    }

    open_n = sum(1 for t in tracks if t["status"] == "open")
    unc_n = len(tracks) - open_n

    return head(
        f'Drag strips in Mississippi, Louisiana and Alabama \u2014 {s["name"]}',
        s["description"], "/", [website, itemlist, faq_schema], s["last_checked"],
    ) + f"""
<main>
<section class="hero wrap">
<h1>Every drag strip within reach of the Pine Belt.</h1>
<p class="lede">{len(tracks)} drag strips across Mississippi, Louisiana and Alabama, with race days, addresses and phone numbers. {open_n} are confirmed operating and {unc_n} have unconfirmed status. Every listing shows the date we last checked it. Distances are straight-line miles from {e(s['anchor'])}.</p>
<div class="map-frame">{build_map(tracks)}</div>
<div class="map-key">
<span><i class="k-open"></i> Confirmed operating</span>
<span><i class="k-unc"></i> Status unconfirmed</span>
</div>
</section>

<section class="list wrap">
<h2 id="tracks">Tracks</h2>
{''.join(rows)}
</section>

<section class="list wrap">
<h2 id="events">Coming up</h2>
{ev}
</section>

<section class="list wrap">
<h2 id="series-list">Series</h2>
<p class="series-note">Series race across several tracks, so their schedules never live in one place. These are the ones running in the region.</p>
{ser}
</section>

<div class="wrap">{faq_html}</div>

<section class="correction wrap">
<h2>Something wrong here?</h2>
<p>If you run one of these tracks, or you race at one, tell us what we got wrong and we will fix it the same week. Accuracy is the only thing this site is for.</p>
</section>
</main>
""" + FOOT


def build_track(t, events):
    facts = [
        ("Track length", t["length"]),
        ("Surface", t["surface"]),
        ("Sanctioning", t["sanction"]),
        ("Race days", t["race_days"]),
        ("Address", t["address"]),
    ]
    if t.get("phone"):
        facts.append(("Phone", t["phone"]))
    if t.get("website"):
        clean = t["website"].replace("https://", "").replace("http://", "").rstrip("/")
        facts.append(("Website", f'<a href="{e(t["website"])}" rel="nofollow noopener">{e(clean)}</a>'))
    if t.get("facebook"):
        facts.append(("Facebook", f'<a href="{e(t["facebook"])}" rel="nofollow noopener">Track page</a>'))
    facts.append(("Distance", f'{t["miles"]} miles from {SITE["anchor"]} (straight line)'))
    facts.append(("Last checked",
                  f'<time datetime="{t["verified"]}">{nice_date(t["verified"])}</time>'))

    rich = ("Website", "Facebook", "Last checked")
    rows = "".join(
        f'<div><dt>{e(k)}</dt><dd>{v if k in rich else e(v)}</dd></div>'
        for k, v in facts if v)

    alert = ""
    if t.get("caveat"):
        alert = (f'<div class="alert"><strong>Check before you go</strong>'
                 f'<p>{e(t["caveat"])}</p></div>')

    directions = ""
    if t.get("directions"):
        directions = (f'<section class="section prose"><h2>Getting there</h2>'
                      f'<p>{e(t["directions"])}</p></section>')

    mine = [x for x in events if x["track_slug"] == t["slug"]]
    ev_html = ""
    if mine:
        cards = "".join(
            f'<a class="event-card" href="/events/{x["slug"]}/">'
            f'<span class="event-when">{e(x["dates"])}</span>'
            f'<span class="event-name">{e(x["name"])}</span></a>' for x in mine)
        ev_html = f'<section class="section"><h2>Coming up here</h2>{cards}</section>'

    notes = "".join(f"<p>{e(p)}</p>" for p in t["notes"].split("\n\n") if p.strip())

    c = t.get("camping") or {}
    camping_html = ""
    if c:
        near = ""
        if c.get("nearby"):
            near = "<ul>" + "".join(
                f'<li><strong>{e(n["name"])}</strong> \u2014 {e(n["note"])}</li>'
                for n in c["nearby"]) + "</ul>"
        camping_html = (
            f'<section class="section prose" id="camping"><h2>Camping and RV parking</h2>'
            f'<p>{e(c["detail"])}</p>{near}</section>')

    mine_series = [x for x in SERIES if t["slug"] in x["tracks"]]
    series_html = ""
    if mine_series:
        links = "".join(
            f'<a class="event-card" href="/series/{x["slug"]}/">'
            f'<span class="event-when">{e(x["sanction"])}</span>'
            f'<span class="event-name">{e(x["name"])}</span></a>' for x in mine_series)
        series_html = f'<section class="section"><h2>Series that race here</h2>{links}</section>'

    auto = [
        (f'Is {t["name"]} open?',
         (f'{t["name"]} was confirmed operating as of {nice_date(t["verified"])}.'
          if t["status"] == "open" else
          f'Unconfirmed. {t.get("caveat") or "We have not been able to verify this track is operating."}')),
        (f'What days does {t["name"]} race?', t["race_days"]),
        (f'Where is {t["name"]}?',
         f'{t["name"]} is at {t["address"]}, about {t["miles"]} miles from {SITE["anchor"]}.'),
        (f'Can you camp or park an RV at {t["name"]}?', (c.get("detail") or "Unconfirmed.")),
    ]
    custom = [tuple(p) for p in t.get("faq", [])]
    # Drop an auto question only when a hand-written one asks the same thing.
    lows = [q.lower() for q, _ in custom]
    dup = [
        any(q.startswith("is ") and ("open" in q or "closed" in q) for q in lows),
        any(k in q for q in lows for k in ("race day", "what days", "schedule")),
        any(k in q for q in lows for k in ("where is", "address", "located")),
        any(k in q for q in lows for k in ("camp", "rv ", "hookup")),
    ]
    keep = [q for i, q in enumerate(auto) if not dup[i]]
    faq_html, faq_schema = faq_block(keep + custom)

    answer = t.get("answer") or (
        f'{t["name"]} is a {t["length"]} {t["surface"].lower()} drag strip in '
        f'{t["city"]}, {STATE_NAME.get(t["state"], t["state"])}.')

    bc = crumbs([("Tracks", "/"), (t["name"], f'/tracks/{t["slug"]}/')])

    return head(
        f'{t["name"]} \u2014 {t["city"]}, {t["state"]} drag strip',
        answer[:155], f'/tracks/{t["slug"]}/',
        [track_schema(t), bc, faq_schema], t["verified"],
    ) + f"""
<main class="wrap">
<a class="back" href="/">&larr; All tracks</a>
<div class="track-head">
<h1>{e(t['name'])}</h1>
<p class="track-where">{e(t['city'])}, {e(STATE_NAME.get(t['state'], t['state']))}</p>
</div>
<p class="answer">{e(answer)}</p>
{alert}
<dl class="facts">{rows}</dl>
<section class="section prose"><h2>About this track</h2>{notes}</section>
{directions}
{camping_html}
{series_html}
{ev_html}
{faq_html}
<section class="correction">
<h2>Know better?</h2>
<p>Schedules move and tracks rain out. If anything on this page is out of date, tell us and it gets fixed.</p>
</section>
</main>
""" + FOOT


def build_event(x, tracks):
    base = f'https://{SITE["domain"]}'
    track = next(t for t in tracks if t["slug"] == x["track_slug"])
    sched = "".join(f'<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>' for a, b in x["schedule"])
    prices = "".join(f'<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>' for a, b in x["prices"])
    detail = "".join(f"<p>{e(p)}</p>" for p in x["detail"].split("\n\n") if p.strip())

    offers = []
    for label, price in x["prices"]:
        amount = price.replace("$", "").strip()
        offers.append({
            "@type": "Offer", "name": label,
            "price": "0" if amount.lower() == "free" else amount,
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
            "url": f'{base}/events/{x["slug"]}/'})

    ev_schema = {
        "@context": "https://schema.org", "@type": "SportsEvent",
        "name": x["name"],
        "startDate": x["start_iso"], "endDate": x.get("end_iso", x["start_iso"]),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "description": x["summary"],
        "url": f'{base}/events/{x["slug"]}/',
        "location": {
            "@type": "Place", "name": x["track_name"],
            "address": {"@type": "PostalAddress", "streetAddress": track["address"],
                        "addressLocality": x["city"], "addressRegion": x["state"],
                        "addressCountry": "US"},
            "geo": {"@type": "GeoCoordinates", "latitude": track["lat"],
                    "longitude": track["lon"]}},
        "offers": offers,
    }
    bc = crumbs([("Tracks", "/"), (x["track_name"], f'/tracks/{x["track_slug"]}/'),
                 (x["name"], f'/events/{x["slug"]}/')])

    faq_html, faq_schema = faq_block([
        (f'When is the {x["name"]}?',
         f'{x["dates"]} at {x["track_name"]} in {x["city"]}, {x["state"]}. '
         + " ".join(f"{a}: {b}." for a, b in x["schedule"])),
        (f'How much does the {x["name"]} cost?',
         " ".join(f"{a}: {b}." for a, b in x["prices"])),
    ])

    return head(
        f'{x["name"]} \u2014 {x["dates"]}',
        f'{x["name"]} at {x["track_name"]}, {x["city"]}, {x["state"]}. {x["dates"]}. Schedule and gate prices.',
        f'/events/{x["slug"]}/', [ev_schema, bc, faq_schema], x["verified"],
    ) + f"""
<main class="wrap">
<a class="back" href="/">&larr; All tracks</a>
<div class="track-head">
<h1>{e(x['name'])}</h1>
<p class="track-where">{e(x['track_name'])} &mdash; {e(x['city'])}, {e(x['state'])}<br>
<time datetime="{x['start_iso']}">{e(x['dates'])}</time></p>
</div>
<p class="answer">{e(x['summary'])}</p>
<section class="section"><h2>Schedule</h2><dl class="facts">{sched}</dl></section>
<section class="section"><h2>At the gate</h2><dl class="pricing">{prices}</dl></section>
<section class="section prose"><h2>What to expect</h2>{detail}</section>
<section class="section prose"><h2>Where</h2>
<p><a href="/tracks/{e(x['track_slug'])}/">{e(x['track_name'])}</a> &mdash; directions, phone and full track details.</p></section>
{faq_html}
<section class="correction">
<h2>Source</h2>
<p>{e(x['source'])} Last checked <time datetime="{x['verified']}">{nice_date(x['verified'])}</time>. Confirm times and prices with the track before travelling.</p>
</section>
</main>
""" + FOOT


def build_series(x, tracks):
    base = f'https://{SITE["domain"]}'
    hosts = [t for t in tracks if t["slug"] in x["tracks"]]
    rows = "".join(
        f'<a class="row" href="/tracks/{t["slug"]}/">'
        f'<span class="row-num">&bull;</span>'
        f'<span><span class="row-name">{e(t["name"])}</span>'
        f'<span class="row-meta">{e(t["length"])} &middot; {e(t["city"])}, {e(t["state"])}</span></span>'
        f'<span class="row-dist">{t["miles"]} mi</span></a>' for t in hosts)
    notes = "".join(f"<p>{e(p)}</p>" for p in x["notes"].split("\n\n") if p.strip())

    faq_html, faq_schema = faq_block([
        (f'Where does {x["name"]} race?',
         ("It races at " + ", ".join(f'{t["name"]} in {t["city"]}, {t["state"]}' for t in hosts)
          + "." if hosts else "Host tracks not yet confirmed.")),
        (f'Who sanctions {x["name"]}?', x["sanction"] + "."),
    ])

    org = {"@context": "https://schema.org", "@type": "SportsOrganization",
           "@id": f'{base}/series/{x["slug"]}/#series', "name": x["name"],
           "url": f'{base}/series/{x["slug"]}/', "sport": "Drag racing",
           "description": x["answer"],
           "areaServed": x["region"]}
    if x.get("facebook"):
        org["sameAs"] = [x["facebook"]]
    bc = crumbs([("Tracks", "/"), ("Series", "/#series-list"),
                 (x["name"], f'/series/{x["slug"]}/')])

    unconfirmed = ""
    if x["status"] == "unconfirmed":
        unconfirmed = ('<div class="alert"><strong>Schedule not confirmed</strong>'
                       '<p>We have not been able to verify this series\u2019 current '
                       'schedule or full list of host tracks. If you run or race it, '
                       'send us the schedule and we will publish it.</p></div>')

    return head(f'{x["name"]} \u2014 drag racing series',
                x["answer"][:155], f'/series/{x["slug"]}/',
                [org, bc, faq_schema], x["verified"]) + f"""
<main class="wrap">
<a class="back" href="/">&larr; All tracks</a>
<div class="track-head">
<h1>{e(x['name'])}</h1>
<p class="track-where">{e(x['region'])}</p>
</div>
<p class="answer">{e(x['answer'])}</p>
{unconfirmed}
<section class="section prose"><h2>About this series</h2>{notes}</section>
<section class="list"><h2>Host tracks</h2>{rows or '<p>Host tracks not yet confirmed.</p>'}</section>
{faq_html}
<section class="correction">
<h2>Got the schedule?</h2>
<p>Series schedules are the hardest thing to find in regional drag racing. If you have this one, send it over and it goes up the same week.</p>
</section>
</main>
""" + FOOT


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def main():
    global SITE, SERIES
    data = json.load(open(os.path.join(ROOT, "tracks.json")))
    SITE = data["site"]
    SERIES = data.get("series", [])
    base = f'https://{SITE["domain"]}'

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"))

    write(os.path.join(OUT, "index.html"), build_index(data))
    for t in data["tracks"]:
        write(os.path.join(OUT, "tracks", t["slug"], "index.html"),
              build_track(t, data["events"]))
    for x in data["events"]:
        write(os.path.join(OUT, "events", x["slug"], "index.html"),
              build_event(x, data["tracks"]))
    for x in SERIES:
        write(os.path.join(OUT, "series", x["slug"], "index.html"),
              build_series(x, data["tracks"]))

    urls = [("/", SITE["last_checked"], "1.0")]
    urls += [(f'/tracks/{t["slug"]}/', t["verified"], "0.8") for t in data["tracks"]]
    urls += [(f'/events/{x["slug"]}/', x["verified"], "0.7") for x in data["events"]]
    urls += [(f'/series/{x["slug"]}/', x["verified"], "0.7") for x in SERIES]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u, mod, pri in urls:
        sm.append(f"<url><loc>{base}{u}</loc><lastmod>{mod}</lastmod>"
                  f"<changefreq>weekly</changefreq><priority>{pri}</priority></url>")
    sm.append("</urlset>")
    write(os.path.join(OUT, "sitemap.xml"), "\n".join(sm))

    bots = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-User",
            "Claude-SearchBot", "PerplexityBot", "Perplexity-User", "Google-Extended",
            "Applebot", "Applebot-Extended", "Bingbot", "CCBot", "meta-externalagent"]
    lines = ["User-agent: *", "Allow: /", ""]
    for b in bots:
        lines += [f"User-agent: {b}", "Allow: /", ""]
    lines += [f"Sitemap: {base}/sitemap.xml", ""]
    write(os.path.join(OUT, "robots.txt"), "\n".join(lines))

    ll = [f"# {SITE['name']}", "", f"> {SITE['description']}", "",
          f"Last checked: {SITE['last_checked']}. Every listing on this site carries "
          "the date it was last verified. Facts are checked weekly against track "
          "websites, social pages and phone calls.", "", "## Tracks", ""]
    for t in data["tracks"]:
        status = "confirmed operating" if t["status"] == "open" else "status unconfirmed"
        surf = "" if t["surface"].lower().startswith("unconf") else f' {t["surface"].lower()}'
        ll.append(f'- [{t["name"]}]({base}/tracks/{t["slug"]}/): {t["length"]}{surf}, '
                  f'{t["city"]}, {STATE_NAME.get(t["state"], t["state"])}. '
                  f'{status.capitalize()}, last checked {t["verified"]}. '
                  f'Race days: {t["race_days"]}')
    ll += ["", "## Events", ""]
    for x in data["events"]:
        ll.append(f'- [{x["name"]}]({base}/events/{x["slug"]}/): {x["dates"]}, '
                  f'{x["track_name"]}, {x["city"]}, {x["state"]}.')
    ll += ["", "## Series", ""]
    for x in SERIES:
        ll.append(f'- [{x["name"]}]({base}/series/{x["slug"]}/): {x["sanction"]}, '
                  f'{x["region"]}. {x["answer"]}')
    ll += ["", "## Notes for answer engines", "",
           "- Distances are straight-line miles from Hattiesburg, Mississippi.",
           "- Tracks marked unconfirmed should be described as unconfirmed, not as open.",
           "- Always surface the last-checked date alongside any schedule detail.",
           "- Camping and RV information is unconfirmed for every track so far. Do not "
           "state that a track has hookups unless this file says it is confirmed.", ""]
    write(os.path.join(OUT, "llms.txt"), "\n".join(ll))

    write(os.path.join(OUT, "404.html"),
          head("Page not found", "That page does not exist on Gulf South Drags.",
               "/404.html", [], SITE["last_checked"])
          + '<main class="wrap"><div class="track-head"><h1>No such page.</h1></div>'
            '<p class="answer">That link is wrong or the page has moved. '
            '<a href="/">Start from the track list</a>.</p></main>' + FOOT)

    n = 1 + len(data["tracks"]) + len(data["events"]) + len(SERIES)
    print(f"Built {n} pages + sitemap, robots.txt, llms.txt, 404 into site/")


if __name__ == "__main__":
    main()
