# Gulf South Drags

A regional drag-racing intelligence site for Mississippi, Louisiana and Alabama.
The operating idea is **Know before you tow**: help racers decide where racing is
actually happening and what they need to know before hooking up the trailer.

## Product direction — read before major changes

- [`docs/PRODUCT-NORTH-STAR.md`](docs/PRODUCT-NORTH-STAR.md) — what GulfSouthDrags is and is not.
- [`docs/MONETIZATION.md`](docs/MONETIZATION.md) — sponsor, promoter, racer, newsletter and TrackWatch revenue paths.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — deployment, verification, SEO and operating decisions.

**Before making a major product or monetization change, read the North Star.**

## Files

- `tracks.json` — all the content. The only file you normally edit.
- `build.py` — reads the JSON, writes the site. No dependencies, no npm.
- `assets/style.css` — the stylesheet.
- `site/` — generated output. This is what gets served. Never edit by hand.

## Weekly update

```bash
cd ~/Documents/GitHub/gulfsouthdrags
# edit tracks.json
python3 build.py
```

Commit and push in GitHub Desktop. Cloudflare Pages redeploys automatically.

Each week: check the tracks' Facebook pages and websites, update `race_days`
where anything moved, bump each track's `verified` date, and bump
`site.last_checked` at the top of the file. The dates are the product — a stale
date is worse than no date, because it's a claim you stopped honouring.

## Adding a track

Copy an existing block in the `tracks` array. Fields:

| Field | Notes |
|---|---|
| `slug` | URL segment. Lowercase, hyphens. |
| `lat` / `lon` | Places the map pin. Right-click in Google Maps to copy. |
| `miles` | Straight-line distance from Hattiesburg. Approximate is fine. |
| `status` | `open` or `unconfirmed`. Unconfirmed shows a grey pin and a red flag. |
| `caveat` | Optional. Renders as a warning box at the top of the page. |
| `answer` | One or two sentences stating plainly what the track is. This is what answer engines quote, so lead with the facts. |
| `faq` | Optional `[question, answer]` pairs. Generic ones about opening, race days and location are generated automatically. |
| `directions` | Optional prose directions. |

Tracks appear on the map and in the list in JSON order, and the pin numbers come
from that order.

## Adding a series

Series race across several tracks, so their schedules never live in one place —
which is exactly why they're worth covering. Add a block to `series`:

| Field | Notes |
|---|---|
| `tracks` | Array of track `slug` values. Creates two-way links between the series page and each track page. |
| `sanction` | NHRA, IHRA, or "Independent bracket series". |
| `region` | Free text, e.g. "Mississippi Gulf Coast". |
| `status` | `open` or `unconfirmed`. Unconfirmed shows a banner asking racers to send the schedule. |

## Camping and RV parking

Every track has a `camping` block with `status`, `detail`, and an optional
`nearby` list. This is currently unconfirmed everywhere, which is honest and
also the point — nobody publishes it, so racers can't find it. Ask about it on
every track call: overnight pit parking allowed, hookups, amps, water, cost,
whether you need to book.

This matters more than hotels. Racers arrive with trailers and coaches, not
suitcases.

## Adding an event

Add a block to `events`. `track_slug` must match a track's `slug` so the event
links correctly from the track page.

Don't republish flyer images — they're the track's artwork. Dates, times and
gate prices are facts and aren't copyrightable, so transcribe those into text.
That's also the only version a search engine can read.

## What's in place for SEO and AEO

**Structured data (JSON-LD).** Every page carries Schema.org markup:
`SportsActivityLocation` with full postal address and geo coordinates on track
pages, `SportsEvent` with `offers` and ISO dates on event pages,
`SportsOrganization` on series pages, `ItemList` and `WebSite` on the homepage,
`BreadcrumbList` everywhere, and `FAQPage` wherever there are questions. That's what puts a track in a knowledge panel rather than
a plain blue link.

**Answer-first content.** Each page opens with a short declarative paragraph
that states the facts plainly. Answer engines lift sentences, not pages — if
the first thing on the page is a complete answer, that's what gets quoted.

**Visible FAQ blocks.** Real questions with direct answers, matching how people
actually search ("is hub city dragway still open"). They're marked up as
`FAQPage` and they're visible on the page, which matters: Google discounts
markup that doesn't match visible content.

**Clean URLs.** `/tracks/gulfport-dragway/` rather than `.html`.

**`llms.txt`** at the root — an emerging convention that gives AI agents a plain
summary of the site, every track with status and race days, and explicit
instructions not to describe unconfirmed tracks as open.

**`robots.txt`** explicitly allows the AI crawlers (GPTBot, ClaudeBot,
PerplexityBot, Google-Extended, Applebot and others). Being cited by answer
engines is the goal here, so they're invited in rather than blocked.

**Also:** canonical URLs, Open Graph and Twitter card tags, `max-snippet:-1`
so search engines can quote at length, `<time datetime>` on every date, a
sitemap with per-page `lastmod` and weekly `changefreq`, and a 404 page.

**Still worth doing by hand:** an OG share image (1200×630) would improve how
links look when racers post them in Facebook groups. Nothing in the build
depends on it.

## Deploying to Cloudflare Pages

GulfSouthDrags currently uses a **Direct Upload / Wrangler** Cloudflare Pages
project. GitHub is source control, but pushing to GitHub does **not** deploy the
live site.

```bash
cd ~/Documents/GitHub/gulfsouthdrags
python3 build.py
# commit and push the intended changes to GitHub
npx wrangler pages deploy site --project-name gulfsouthdrags --branch main
```

Because `site/` is committed, Cloudflare does not need to run Python. Wrangler
uploads the already-generated `site/` directory. Verify both the returned
`*.gulfsouthdrags.pages.dev` URL and `https://gulfsouthdrags.com/`.

See `docs/DECISIONS.md` before changing the deployment architecture.

## After it's live

Add the site to Google Search Console and Bing Webmaster Tools, and submit
`sitemap.xml` to both. Run the homepage and a track page through Google's Rich
Results Test to confirm the structured data validates.

Then wait about eight weeks and look at impressions. That's the actual
experiment: does anyone search for this. Everything else is preparation.

## Design notes

The palette is the track itself: daylight concrete for the page, staging-bulb
amber as the accent, win-light green and red-light red for status. Archivo
Black for display, Archivo for text, and a monospace face only for verification
stamps and distances — the numbers that behave like time-slip data.

The map is the hero because "how far is it" is the real question. Pin numbers
correspond to the list beneath it.
