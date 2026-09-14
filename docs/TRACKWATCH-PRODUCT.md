# TrackWatch — Standalone Product Opportunity

_Last updated: 2026-09-14_

## Why this document exists

TrackWatch began as a GulfSouthDrags support system, but the underlying capability is broader than drag racing.

The commercial opportunity is not "a drag-strip bot." It is a reusable monitoring product for businesses that repeatedly check fragmented public information and only need human attention when something meaningful changes.

The core promise:

> **Stop paying people to repeatedly check the same sources. TrackWatch watches them, filters the noise, and tells a human when something worth acting on changes.**

This document preserves that opportunity without changing GulfSouthDrags' immediate product focus.

## Product thesis

Many industries depend on information scattered across ordinary public webpages, portals, calendars, notices, schedules, listings, procurement pages, and other sources.

The expensive part is often not finding the information once. It is checking the same sources again and again to answer:

- Did anything change?
- Is the change meaningful?
- Does it conflict with what we currently believe?
- Does a person need to act?

TrackWatch turns that repeated manual checking into a monitored workflow.

General pattern:

**watch public sources -> remember prior state -> detect change -> classify significance -> discard noise -> compare with current known data -> alert a human -> human review/action**

The output is not raw scraped data. The output is **attention**.

## What already works today

GulfSouthDrags is proof case #1.

The working TrackWatch system can already:

- watch configured public webpages
- respect `robots.txt`
- use ordinary HTTP requests rather than browser/login automation
- use conditional requests such as ETag / Last-Modified where supported
- normalize visible webpage content
- keep source baselines and snapshots
- hash and compare current content against prior content
- surface changed excerpts
- classify obvious racing-related changes with a deterministic classifier
- automatically filter low-value changes
- compare possible changes against GulfSouthDrags' current structured data
- queue meaningful detections for human review
- provide a private local Control Room
- run a sweep from the Control Room without Terminal
- run automatically on a macOS schedule
- send a Mac notification when something needs review or a source fails
- remain silent when nothing meaningful changed

This is a real working monitoring loop, not a mockup.

## Current proof event

On 2026-09-14, TrackWatch checked four enabled racing sources. Three were unchanged. Holiday Raceway changed, but the classifier determined the change contained no meaningful racing signal, so it was filtered automatically and nothing was added to the human review queue.

That is exactly the intended economic behavior: **do the repetitive checking automatically and avoid wasting a person's attention on noise.**

## The product is not tied to drag racing

The racing-specific layer is currently the source registry, classifier vocabulary, current-data comparison, and the meaning assigned to a detected change.

The underlying engine is much more general:

1. source registry
2. responsible fetcher
3. normalizer
4. baseline / snapshot history
5. change detector
6. meaningful-change classifier
7. optional comparison against known business data
8. review queue
9. notifications
10. human decision

A future standalone product should preserve this separation so each industry can plug in its own source types, classifier rules, and business-data comparison logic.

## Best second proof case

The strongest next proof case is **South Mississippi Project Radar**.

Contractors repeatedly monitor procurement portals, municipal project pages, plan rooms, DOT sources, bid notices, and related pages. TrackWatch could watch for things such as:

- new project posted
- bid deadline changed
- addendum issued
- scope text changed
- pre-bid meeting changed
- plan/specification link changed
- project status changed
- source unavailable or broken

If substantially the same TrackWatch engine can serve both drag racing and contractor/project intelligence, that is strong evidence the product is reusable rather than merely a one-off GulfSouthDrags feature.

## Candidate markets

Potential verticals should be judged by one question:

> **Are people repeatedly checking public sources because missing one meaningful change costs time, money, opportunity, or risk?**

Promising examples include:

- contractor bids and public procurement
- municipal projects and infrastructure notices
- permits and planning/zoning agendas
- grants and funding opportunities
- event and venue schedule monitoring
- niche industry directories
- racing organizations, tracks, promoters, and series
- supplier / distributor availability pages
- regulatory or compliance notice pages
- commercial real-estate or development notices
- government meeting agendas and posted documents
- specialized association and membership sites

Do not chase all of these. They are a market map, not a build queue.

## Commercial models

### 1. Vertical SaaS

Package TrackWatch for one specific industry with that industry's vocabulary, sources, filters, and workflows.

Example positioning:

> TrackWatch for Contractors — know when the bid page changes without checking it every morning.

Possible pricing should be tested against measurable time saved and opportunity value rather than guessed from software-industry averages.

### 2. Done-for-you monitoring

A business supplies the public sources it cares about and the kinds of changes that matter. TrackWatch is configured and maintained for them.

Potential pricing structure:

- one-time setup/configuration fee
- recurring monitoring fee based on source count, check frequency, and workflow complexity

This may be the fastest way to earn early revenue because it can be sold before a polished self-service SaaS exists.

### 3. White-label / embedded monitoring

Other niche software products could use TrackWatch as the monitoring layer behind their own dashboard.

The customer sees "changes detected" or "needs review" inside their product while TrackWatch handles source monitoring underneath.

### 4. Premium alerting / intelligence

Basic data may remain free while customers pay for:

- immediate meaningful-change alerts
- followed-source alerts
- source health monitoring
- change history
- higher check frequency
- industry-specific filters
- team review workflows
- integrations or exports

### 5. Lead / opportunity intelligence

In some industries, the valuable event is not simply that a page changed. It is that a **business opportunity appeared**.

Examples: a new bid, permit, project, grant, race event, vendor opening, or procurement notice.

In those cases TrackWatch can evolve from monitoring software into decision-support intelligence.

## The economic value

TrackWatch should eventually be sold on outcomes such as:

- hours of repetitive checking eliminated
- fewer missed changes
- earlier awareness of opportunities
- reduced stale-data risk
- less dependence on one employee remembering to check sources
- fewer false alarms than naive "page changed" tools
- auditable source and change history

The strongest sales sentence is likely closer to:

> **We watch the public sources your business depends on and tell you only when something worth your attention changes.**

Not:

> We scrape websites.

## Product principles

### Human review remains a strength

TrackWatch should not pretend every detected change is automatically true or actionable.

For high-value business information, the workflow should remain:

**machine detects -> machine summarizes/classifies -> human verifies -> business acts**

Automation should eliminate repetitive inspection, not remove judgment where judgment matters.

### Responsible source access

A commercial TrackWatch product should maintain the rules established in GulfSouthDrags:

- public sources only unless an authorized supported integration exists
- respect `robots.txt` and source terms where applicable
- no CAPTCHA bypass
- no credential theft or login automation
- no anti-bot evasion
- reasonable check frequencies
- conditional requests where possible
- descriptive identification when appropriate

A durable business should not depend on adversarial scraping.

### Noise reduction is part of the product

A simple webpage-diff tool is not enough.

TrackWatch becomes valuable when it distinguishes:

- content changed

from:

- **something changed that may require action**

The Holiday Raceway low-value filter is a small but important example of this distinction.

## Technical product direction

A future reusable architecture should gradually separate:

### Core engine

- scheduling
- source registry
- fetching
- normalization
- snapshots
- change detection
- source health
- notification plumbing
- review-state management

### Vertical adapter

- industry vocabulary
- meaningful-change rules
- data schema
- conflict/comparison logic
- source templates
- alert wording
- action workflows

### Future intelligence layer

An LLM-backed classifier may later improve nuanced classification or summarization, but it should be optional.

The current deterministic classifier has useful advantages: low cost, predictable behavior, no API dependency, and easy debugging.

## Commercial validation plan

Do not build a broad SaaS yet.

Use two real internal proving grounds first:

### Proof case #1 — GulfSouthDrags

Measure:

- sources monitored
- sweeps completed
- meaningful detections
- low-value changes filtered
- source failures caught
- hours of manual checking avoided
- useful site updates triggered by TrackWatch

### Proof case #2 — Project Radar

Adapt the same monitoring core to contractor/project sources and measure the same categories plus:

- new bid opportunities found
- addenda/deadline changes detected
- contractor-relevant actions created
- manual portal-checking time eliminated

### Reusability milestone

Do not call TrackWatch a standalone platform merely because it can theoretically serve other industries.

Call it reusable when the same core engine is successfully operating in **two materially different verticals** with industry logic kept outside the core.

## First revenue test

Before building accounts, billing, dashboards, multi-tenant architecture, or an elaborate SaaS website:

1. Identify one business with a real repeated-monitoring burden.
2. Ask what sources someone checks manually today.
3. Estimate time spent checking them each week.
4. Ask what a missed change can cost.
5. Configure a small TrackWatch monitoring set for that workflow.
6. Run it alongside the current human process.
7. Measure useful detections, false positives, and time saved.
8. Ask the business to pay for continued monitoring.

The goal is not a perfect product. The goal is evidence that **someone will pay to stop doing the checking manually**.

## Things not to do yet

- do not create ten vertical versions at once
- do not stop improving GulfSouthDrags to chase a generic SaaS prematurely
- do not build self-service billing before anyone pays manually
- do not add AI simply to make the product sound more advanced
- do not increase polling frequency without a real need
- do not weaken responsible-access rules to monitor a difficult source
- do not promise that every change is correct without human review

## Near-term roadmap

1. Keep TrackWatch operating automatically for GulfSouthDrags and collect real history.
2. Record meaningful detections, filtered noise, source failures, and resulting human actions.
3. Adapt TrackWatch to one Project Radar source as proof case #2.
4. Identify which pieces are truly generic and extract them cleanly from racing-specific logic.
5. Create a simple before/after case study showing time saved and changes caught.
6. Test one paid done-for-you monitoring customer before building a full standalone SaaS.

## Strategic conclusion

TrackWatch may ultimately be more commercially valuable than the site feature that created it.

GulfSouthDrags should remain its first proving ground, not be abandoned for the new opportunity.

The discipline is:

**prove -> measure -> reuse -> sell -> then productize.**
