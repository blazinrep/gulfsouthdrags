// GulfSouthDrags lead capture — Cloudflare Pages Function
// Requires:
//   D1 binding: GSD_LEADS_DB
//   Secret: RESEND_API_KEY
//
// D1 remains the source-of-truth. For Weekend Tow Report signups we also
// sync the contact into Resend. If Resend is temporarily unavailable, the
// signup is still saved in D1 and the visitor still reaches the thank-you page.

const RESEND_API = 'https://api.resend.com';
const TOW_SEGMENT_NAME = 'GulfSouthDrags — Weekend Tow Report';
const TOW_TOPIC_NAME = 'Weekend Tow Report';

function clean(v, max = 500) {
  return String(v || '').trim().slice(0, max);
}

function validEmail(v) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) && v.length <= 254;
}

function redirectFor(kind) {
  const suffix = kind === 'partner' ? 'partner' : 'tow-report';
  return `/thanks/?kind=${suffix}`;
}

async function resendRequest(apiKey, path, options = {}) {
  const response = await fetch(`${RESEND_API}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
  });

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { raw: text };
    }
  }

  return { response, data };
}

async function findResendResource(apiKey, path, wantedName) {
  const { response, data } = await resendRequest(apiKey, path);
  if (!response.ok) {
    throw new Error(`Resend ${path} lookup failed (${response.status})`);
  }

  const item = (data?.data || []).find((x) => x?.name === wantedName);
  if (!item?.id) {
    throw new Error(`Resend resource not found: ${wantedName}`);
  }
  return item;
}

async function syncTowReportContact(apiKey, email, firstName) {
  const [segment, topic] = await Promise.all([
    findResendResource(apiKey, '/segments', TOW_SEGMENT_NAME),
    findResendResource(apiKey, '/topics', TOW_TOPIC_NAME),
  ]);

  const createBody = {
    email,
    unsubscribed: false,
    segments: [{ id: segment.id }],
    topics: [{ id: topic.id, subscription: 'opt_in' }],
  };
  if (firstName) createBody.first_name = firstName;

  const created = await resendRequest(apiKey, '/contacts', {
    method: 'POST',
    body: JSON.stringify(createBody),
  });

  if (created.response.ok) return;

  if (created.response.status === 409) {
    const encodedEmail = encodeURIComponent(email);

    const segmentResult = await resendRequest(
      apiKey,
      `/contacts/${encodedEmail}/segments/${segment.id}`,
      { method: 'POST' },
    );

    if (!segmentResult.response.ok && segmentResult.response.status !== 409) {
      throw new Error(
        `Resend segment sync failed (${segmentResult.response.status})`,
      );
    }

    const topicResult = await resendRequest(
      apiKey,
      `/contacts/${encodedEmail}/topics`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          topics: [
            { id: topic.id, subscription: 'opt_in' },
          ],
        }),
      },
    );

    if (!topicResult.response.ok) {
      throw new Error(
        `Resend topic sync failed (${topicResult.response.status})`,
      );
    }
    return;
  }

  throw new Error(`Resend contact create failed (${created.response.status})`);
}

export async function onRequestPost(context) {
  const form = await context.request.formData();
  const kind = clean(form.get('kind'), 40);
  const source = clean(form.get('source'), 160);
  const honeypot = clean(form.get('fax_number'), 100);

  if (!['tow_report', 'partner'].includes(kind)) {
    return new Response('Invalid submission.', { status: 400 });
  }

  if (honeypot) {
    return Response.redirect(
      new URL(redirectFor(kind), context.request.url).toString(),
      303,
    );
  }

  const email = clean(form.get('email'), 254).toLowerCase();
  if (!validEmail(email)) {
    return new Response('Please enter a valid email address.', { status: 400 });
  }

  if (!context.env.GSD_LEADS_DB) {
    return new Response(
      'Signup storage is not connected yet. Please try again shortly.',
      { status: 503 },
    );
  }

  const firstName = clean(form.get('first_name'), 120);
  const businessName = clean(form.get('business_name'), 160);
  const website = clean(form.get('website'), 500);
  const message = clean(form.get('message'), 1200);

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
    `)
      .bind(kind, email, firstName, businessName, website, message, source)
      .run();
  } catch (err) {
    console.error('lead insert failed', err);
    return new Response('We could not save that right now. Please try again.', {
      status: 500,
    });
  }

  if (kind === 'tow_report') {
    if (!context.env.RESEND_API_KEY) {
      console.error('Resend sync skipped: RESEND_API_KEY is not configured');
    } else {
      try {
        await syncTowReportContact(
          context.env.RESEND_API_KEY,
          email,
          firstName,
        );
      } catch (err) {
        console.error('Resend contact sync failed', err);
      }
    }
  }

  return Response.redirect(
    new URL(redirectFor(kind), context.request.url).toString(),
    303,
  );
}

export function onRequestGet() {
  return new Response('Method not allowed', {
    status: 405,
    headers: { Allow: 'POST' },
  });
}
