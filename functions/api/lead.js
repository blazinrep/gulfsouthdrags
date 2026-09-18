// GulfSouthDrags lead capture — Cloudflare Pages Function
// Requires a D1 binding named GSD_LEADS_DB.

function clean(v, max = 500) {
  return String(v || "").trim().slice(0, max);
}

function validEmail(v) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) && v.length <= 254;
}

function redirectFor(kind) {
  const suffix = kind === "partner" ? "partner" : "tow-report";
  return `/thanks/?kind=${suffix}`;
}

export async function onRequestPost(context) {
  const form = await context.request.formData();
  const kind = clean(form.get("kind"), 40);
  const source = clean(form.get("source"), 160);
  const honeypot = clean(form.get("fax_number"), 100);

  if (!['tow_report', 'partner'].includes(kind)) {
    return new Response('Invalid submission.', { status: 400 });
  }

  // Quietly accept obvious bots without storing anything.
  if (honeypot) {
    return Response.redirect(new URL(redirectFor(kind), context.request.url).toString(), 303);
  }

  const email = clean(form.get("email"), 254).toLowerCase();
  if (!validEmail(email)) {
    return new Response('Please enter a valid email address.', { status: 400 });
  }

  if (!context.env.GSD_LEADS_DB) {
    return new Response('Signup storage is not connected yet. Please try again shortly.', { status: 503 });
  }

  const firstName = clean(form.get("first_name"), 120);
  const businessName = clean(form.get("business_name"), 160);
  const website = clean(form.get("website"), 500);
  const message = clean(form.get("message"), 1200);

  try {
    await context.env.GSD_LEADS_DB.prepare(`
      INSERT INTO leads (kind, email, first_name, business_name, website, message, source)
      VALUES (?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(kind, email) DO UPDATE SET
        first_name = excluded.first_name,
        business_name = excluded.business_name,
        website = excluded.website,
        message = excluded.message,
        source = excluded.source,
        updated_at = CURRENT_TIMESTAMP
    `).bind(kind, email, firstName, businessName, website, message, source).run();
  } catch (err) {
    console.error('lead insert failed', err);
    return new Response('We could not save that right now. Please try again.', { status: 500 });
  }

  return Response.redirect(new URL(redirectFor(kind), context.request.url).toString(), 303);
}

export function onRequestGet() {
  return new Response('Method not allowed', { status: 405, headers: { Allow: 'POST' } });
}
