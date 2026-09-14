# TrackWatch V0.1

TrackWatch is the monitoring engine behind the TrackWatch feature shown on
the Gulf South Drags homepage. This is the real bot — V0.1, human-review
only, nothing here touches the public site automatically.

## What TrackWatch is

TrackWatch monitors public racing-information sources for changes and
surfaces meaningful ones for a human to review. The pipeline:

```
source watchers -> change detector -> meaningful-change classifier
   -> compare against tracks.json -> private human review queue
   -> approve / ignore
```

## What TrackWatch is not

- It is **not** an automatic truth engine. Nothing it detects is published
  until a person reviews it.
- It is **not** a Facebook scraper, and it does not depend on Facebook —
  V0.1 only watches ordinary public webpages. Facebook is a possible
  *future* adapter (see Roadmap), and only if there is a legitimate,
  supported way to access it — no login automation, ever.
- It does **not** bypass authentication, paywalls, CAPTCHAs, or anti-bot
  protection. If a source needs any of that to read, TrackWatch does not
  watch it.
- It does **not** edit `tracks.json` or `site/`. V0.1 stops at "approved
  for action" — an approved detection is a human judgment that the change
  is real and worth acting on, not an automated edit.

## Why this exists, in one sentence

A track's Facebook post from March, or a schedule buried three posts deep,
is exactly the kind of stale information Gulf South Drags exists to catch
— TrackWatch is how that checking stops being 100% manual.

## Folder structure

```
trackwatch/
  README.md              this file
  config/
    sources.json         which tracks/sources are watched
  normalizer.py           HTML -> normalized visible text (stdlib html.parser)
  fetcher.py              responsible HTTP fetching (stdlib urllib + robotparser)
  detector.py             snapshots, hashing, diffing, tracks.json comparison
  classifier.py           meaningful-change classification (pluggable interface)
  review_queue.py         the pending/approved/ignored detection store
  review_server.py        the private localhost review UI (stdlib http.server)
  trackwatch.py           the CLI entry point — run / pending / status
  TrackWatch Control Room.command       one-click launcher — see "Opening the Control Room"
  TrackWatch Control Room.app           app-bundle wrapper around the .command file
  TrackWatch Control Room.applescript   source for the .app (rebuild with osacompile)
  com.gulfsouthdrags.trackwatch-review.plist   optional start-at-login LaunchAgent (not installed by default)
  templates/
    review.html           the review UI's HTML template
  tests/
    test_trackwatch.py     unittest suite (no network access)
    fixtures/               sample before/after HTML used by the tests
  state/                  per-source fetch metadata (gitignored)
  snapshots/              normalized before/after text per source (gitignored)
  review/
    pending/ approved/ ignored/    detection records — status = which folder (gitignored)
  logs/                   one log file per sweep (gitignored)
```

`state/`, `snapshots/`, `review/*/`, and `logs/` are all runtime data —
see `.gitignore` at the repo root. Only the code, `config/sources.json`,
`templates/`, and `tests/` (including fixtures) are version controlled.

`build.py` (the public site generator) never imports anything from
`trackwatch/`, and `trackwatch/` never imports `build.py`. They are
deliberately separate systems that both happen to read `tracks.json`.

## How to

All commands run from the repo root.

**Run every enabled source once:**
```bash
python3 trackwatch/trackwatch.py run
```

**Run just one track, or one source on one track:**
```bash
python3 trackwatch/trackwatch.py run --track gulfport-dragway
python3 trackwatch/trackwatch.py run --track gulfport-dragway --source official-site
```

**See what's waiting for review:**
```bash
python3 trackwatch/trackwatch.py pending
```

**See registry + queue counts:**
```bash
python3 trackwatch/trackwatch.py status
```

**Open the private review queue:**
```bash
python3 trackwatch/review_server.py
```
Then open http://localhost:8765/ — binds to `127.0.0.1` only. This page is
never part of `site/`; Cloudflare never sees it, and it only exists on
whatever machine you run it on.

**Approve / Ignore:** click the buttons in the review queue. Approved and
ignored detections move to `trackwatch/review/approved/` and
`trackwatch/review/ignored/` respectively — that move *is* the status; there's
no separate database to get out of sync with it.

**Reset one source's baseline** (deliberately re-baseline instead of
diffing against history — e.g. after a site redesign made the old snapshot
meaningless):
```bash
python3 trackwatch/trackwatch.py run --track gulfport-dragway --source official-site --reset-baseline
```

**Add a source:** edit `trackwatch/config/sources.json`. Add an entry
under the right track's `"sources"` array:
```json
{ "id": "official-site", "type": "webpage", "url": "https://example.com/", "enabled": true, "priority": "primary" }
```
Only `"type": "webpage"` is implemented in V0.1. `enabled: false` keeps a
source in the registry (so its URL is documented) without including it in
sweeps — useful for sources you haven't verified are worth polling yet.

**Run the tests** (no network access, pure fixtures):
```bash
python3 trackwatch/tests/test_trackwatch.py
```

## Opening the Control Room

You don't have to run `review_server.py` and open the URL by hand anymore.

**One-click launcher.** Double-click **`trackwatch/TrackWatch Control Room.command`**
in Finder (or **`trackwatch/TrackWatch Control Room.app`**, a small app wrapper
around the same script — see below). It will:

1. find the gulfsouthdrags repo from its own location, not your current folder
2. check whether the review server is already answering on `localhost:8765`
3. if not, start it in the background and wait (up to ~10 seconds) for it to respond
4. open **http://localhost:8765/** in your default browser
5. if something goes wrong, print a clear reason instead of failing silently
   (missing `review_server.py`, no `python3`, or the server not responding in time)

Running it again while the server is already up just re-opens the browser —
it will never start a second copy.

**Using the `.app` version from the Dock.** `TrackWatch Control Room.app` is a
tiny AppleScript app (built with `osacompile`) that just runs the `.command`
file sitting next to it — same behavior, but it's a real app bundle, so you
can drag it onto the Dock or into `/Applications` (as an alias, or move the
whole `trackwatch/` folder's copy — just keep the `.app` and `.command` files
together, since the app calls the command file by relative location). If you
ever edit `TrackWatch Control Room.applescript`, rebuild the app with:
```bash
cd trackwatch
osacompile -o "TrackWatch Control Room.app" "TrackWatch Control Room.applescript"
```

**Starting automatically at login (optional, not installed by default).**
`trackwatch/com.gulfsouthdrags.trackwatch-review.plist` is a macOS LaunchAgent
that starts the review server at login and keeps it available in the
background — nothing installs it for you. To install it yourself:
```bash
cp trackwatch/com.gulfsouthdrags.trackwatch-review.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.gulfsouthdrags.trackwatch-review.plist
```
To uninstall it:
```bash
launchctl unload ~/Library/LaunchAgents/com.gulfsouthdrags.trackwatch-review.plist
rm ~/Library/LaunchAgents/com.gulfsouthdrags.trackwatch-review.plist
```
The plist hardcodes this checkout's path
(`/Users/chadgill/Documents/GitHub/gulfsouthdrags`) — if you ever move the
repo, edit the paths in the plist before reinstalling it.

**Stopping or restarting the server.** There's no "Quit" button in the
browser page itself (it's just a review queue, not a menu-bar app), so:
```bash
pkill -f trackwatch/review_server.py     # stop it
python3 trackwatch/trackwatch.py status   # confirm the queue/registry state any time
```
Then relaunch with the Control Room launcher, or `python3 trackwatch/review_server.py`
directly, whenever you want it running again. If you installed the
LaunchAgent above, it will also restart the server the next time you log in.

## Automatic sweeps + macOS notifications

TrackWatch can run without you opening Terminal.

The installed macOS LaunchAgent (`com.gulfsouthdrags.trackwatch-sweep`) runs:

- **every day at 8:00 AM local time**
- **an extra Friday sweep at 3:00 PM local time** before the race weekend

The scheduled runner is `trackwatch/scheduled_sweep.py`. It uses the exact same
TrackWatch detection pipeline as the manual **Run TrackWatch Sweep** button.

Notification policy is deliberately quiet:

- meaningful racing change queued -> notify
- an existing review item is still waiting -> remind on the next scheduled sweep
- one or more sources failed to check -> notify
- unchanged source -> stay quiet
- low-value/cosmetic change automatically filtered -> stay quiet

Nothing is ever published automatically. A notification means **open the
TrackWatch Control Room and make the human decision**.

Useful commands:

```bash
# Run the scheduled wrapper manually
python3 trackwatch/scheduled_sweep.py

# Test Notification Center without sweeping
python3 trackwatch/scheduled_sweep.py --test-notification

# See whether macOS has the scheduler loaded
launchctl print gui/$(id -u)/com.gulfsouthdrags.trackwatch-sweep

# Remove the automatic scheduler
launchctl bootout gui/$(id -u)/com.gulfsouthdrags.trackwatch-sweep
rm ~/Library/LaunchAgents/com.gulfsouthdrags.trackwatch-sweep.plist
```

The scheduler writes its own history to `trackwatch/logs/scheduler.log`, while
each actual sweep still writes the normal `trackwatch/logs/sweep_<timestamp>.log`.
The Control Room always reads the newest sweep log, so automatic sweeps appear
there the same way manual sweeps do.

If the Mac is asleep at a scheduled time, macOS `launchd` generally runs a missed
calendar job after the Mac wakes. If the Mac is fully shut down, TrackWatch
cannot run until macOS is running again.

## First-run behavior (important)

The first time TrackWatch sees a source, there is nothing to compare
against — that fetch becomes the **baseline**. You'll see:
```
BASELINE gulfport-dragway/official-site: baseline created
```
No detection is queued from a baseline run. Only the *second* and later
sweeps compare against what TrackWatch has already seen, so you never get
a flood of "changes" from a source's entire homepage on day one.

## Reading a sweep's output

```
TRACKWATCH SWEEP
----------------
OK       gulfport-dragway/official-site: unchanged (hash match)
CHANGED  holiday-raceway/official-site: ignored as low-value (...)
QUEUED   no-problem-raceway/official-site: possible_schedule_change (confidence 0.69)

4 sources checked
3 unchanged
1 changed — ignored as low-value
1 possible racing changes queued
0 fetch errors
```
One bad source (timeout, 404, blocked by robots.txt) is logged and
skipped — it never aborts the rest of the sweep. Full detail for every run
is written to `trackwatch/logs/sweep_<timestamp>.log`.

## Being a responsible visitor

- Custom User-Agent: `GulfSouthDrags-TrackWatch/0.1 (+https://gulfsouthdrags.com)`
- `robots.txt` is checked (stdlib `urllib.robotparser`) before every fetch;
  a disallowed URL is skipped and logged, never bypassed.
- Conditional GET: TrackWatch sends `If-None-Match`/`If-Modified-Since`
  when a source has previously returned an ETag/Last-Modified, so an
  unchanged page usually costs the source a cheap `304`, not a full body
  transfer.
- A short fixed pause runs between fetches within one sweep.
- We're monitoring dragstrip schedules, not stock prices — there's no
  reason to poll faster than a human checking back occasionally.

## Swapping in a smarter classifier later

`classifier.py`'s `BaseClassifier.classify(before_text, after_text,
changed_excerpt) -> ClassificationResult` is the entire interface.
`KeywordClassifier` (V0.1's classifier) is a deterministic implementation
of it — no API key, no network call, no cost to run. A future
LLM-backed classifier is just another class implementing the same method;
nothing in `detector.py`, `review_queue.py`, or `review_server.py` needs to
change when that lands.

## Roadmap (design for these — not built yet)

- **V0.2** — an approved detection becomes a *proposed* `tracks.json`
  change (still requires a human to apply it — not auto-committed).
- **V0.3** — track owners can submit their own updates directly.
- **V0.4** — scheduled sweeps (cron / GitHub Actions), once V0.1's
  detection quality is trusted. Not part of this version on purpose.
- **V0.5** — email/newsletter monitoring as another source adapter.
- **Future** — additional source adapters (RSS/Atom, promoter feeds, an
  API, and yes, Facebook — but only through legitimate, supported access,
  never login automation or scraping evasion).
- **Future / commercial** — TrackWatch as monitoring for tracks, promoters,
  and other motorsports sites, not hardwired to Gulf South Drags. That's
  why this lives in its own `trackwatch/` subsystem instead of being woven
  into `build.py`.

## A note on the homepage TrackWatch module

The homepage currently and correctly says TrackWatch is "in development"
and its example feed is explicitly labeled as an example. Don't change
that copy to claim live source counts, "real-time" status, or actual
detection numbers until this bot's output is genuinely wired into the
homepage build — see `build.py`'s TrackWatch section and
`assets/style.css`'s `.trackwatch-*` rules.
