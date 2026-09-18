# GulfSouthDrags lead capture setup

The site now contains two forms:

- Weekend Tow Report signup
- Founding Trackside Partner interest

Both POST to `/api/lead`, a Cloudflare Pages Function. The function stores submissions in a Cloudflare D1 database binding named `GSD_LEADS_DB`.

## Important

Do not deploy the new forms until the D1 database is created, the schema is applied, and the Pages project has the `GSD_LEADS_DB` D1 binding. Otherwise the public form will return a 503 message.

The normal site deployment remains Wrangler Direct Upload. Cloudflare Pages uploads a root-level `functions/` directory when deployment is run with Wrangler from the project directory.

## Data collected

Tow Report: email + source page.
Partner interest: email, name, business, website, message + source page.

A hidden honeypot field suppresses basic form bots. No visitor IP address is stored by this code.
