# GulfSouthDrags Decisions & Operating Notes

_Last updated: 2026-09-14_

This file exists so we do not repeatedly rediscover important project decisions.

## Product decisions

- Positioning: **Know before you tow.**
- GulfSouthDrags is **racer intelligence, not another generic track directory**.
- Geographic focus: Mississippi, Louisiana, Alabama.
- The differentiator is current operating intelligence, verification, event information, and racer logistics.
- Unknown information should be labeled unknown rather than guessed.
- Commercial rule: **Sponsors can buy exposure. Nobody can buy the truth.**
- Preserve useful existing track URLs and avoid unnecessary rewrites of pages gaining search visibility.
- State hubs are useful for broad search intent; the Mississippi hub is `/drag-strips/mississippi/`.
- Future email concept: **The Weekend Tow Report**.
- First commercial milestone: **first $100 of real revenue**, not AdSense scale.
- TrackWatch remains human-reviewed and should not silently rewrite `tracks.json`.

## Current deployment decision

GulfSouthDrags is the exception among several other projects: its Cloudflare Pages project is currently a **Direct Upload / Wrangler project**, not a Git-connected Pages project.

GitHub remains source control and history, but **a Git push does not make GulfSouthDrags live**.

### Normal release workflow

```bash
cd ~/Documents/GitHub/gulfsouthdrags
python3 build.py
# commit and push the intended changes to GitHub
npx wrangler pages deploy site --project-name gulfsouthdrags --branch main
```

Wrangler returns a `*.gulfsouthdrags.pages.dev` deployment URL. Then verify the custom domain at `https://gulfsouthdrags.com/`.

### Important

Do **not** assume `git push` deployed production.

Do **not** routinely use `git add .` when unrelated TrackWatch or binary files may be modified locally. Stage intended files explicitly or review them carefully in GitHub Desktop.

## Site-generation decision

- `tracks.json` is the structured content source.
- `build.py` generates the static public site.
- `site/` is generated output and is what Wrangler publishes.
- `site/` is committed to the repo.
- Do not hand-edit generated public pages when the change belongs in `tracks.json` or `build.py`.

## TrackWatch decision

TrackWatch is a separate subsystem inside the repo.

Current philosophy:

public source watchers -> change detector -> meaningful-change classifier -> compare against `tracks.json` -> private review queue -> approve / ignore

Key rules: public sources only, no CAPTCHA bypass/login automation, first fetch creates a baseline, human review before public changes, runtime review data stays out of `site/`, Facebook is not automatically scraped, and future approved detections should propose changes rather than silently write them.

## Verification language

Long-term verification may distinguish:

- Owner verified
- GulfSouthDrags checked
- TrackWatch detected
- Unconfirmed

The wording can change; the distinction between evidence types should remain.

## SEO / discovery decision

Do not overreact to tiny Search Console samples, but use them to identify real demand.

Current approach: strengthen pages already earning impressions, add state/regional hubs where intent supports them, keep answer-first factual copy, preserve structured data, request indexing for important new hubs, and watch results before another large SEO change.

## Strategic references

Before a major feature, product, or monetization decision, read:

1. `docs/PRODUCT-NORTH-STAR.md`
2. `docs/MONETIZATION.md`
3. this file

If a new idea conflicts with the North Star, decide deliberately rather than allowing product drift.
