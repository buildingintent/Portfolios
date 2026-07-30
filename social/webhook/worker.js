const META_API_VERSION = "v24.0"
const APP_STORE_HOST = "https://apps.apple.com/"

function textResponse(text, status) {
  return new Response(text, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  })
}

function privacyResponse() {
  return new Response(
    `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Privacy Policy | Building Intent Social Publish</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, sans-serif; }
    body { margin: 0; color: #24211f; background: #fbf2e8; }
    main { max-width: 720px; margin: auto; padding: 48px 24px 72px; }
    h1 { font-size: clamp(2rem, 6vw, 3.5rem); margin-bottom: 8px; }
    h2 { margin-top: 36px; }
    p, li { font-size: 1.05rem; line-height: 1.7; }
    a { color: #9c3524; }
    .date { color: #625b56; }
  </style>
</head>
<body>
  <main>
    <h1>Privacy Policy</h1>
    <p class="date">Effective date: July 30, 2026</p>
    <p>Building Intent Social Publish helps manage Instagram posts and sends
    the resource described on a registered post when someone comments on that
    post.</p>

    <h2>Information We Receive</h2>
    <p>Meta may send us an Instagram comment ID, media ID, username where
    supplied, and comment text when someone comments on content managed by
    Building Intent Social Publish. We use the media ID to find the approved
    reply for that post. We do not store the comment text or username.</p>

    <h2>Information We Store</h2>
    <p>We store the media-specific keyword and approved reply, comment IDs used
    to prevent duplicate replies, delivery status, and Meta message IDs.</p>

    <h2>How We Use Information</h2>
    <p>We use this information to send the requested resource and relevant App
    Store link, prevent duplicate messages, secure the service, and
    troubleshoot delivery failures.</p>

    <h2>Sharing and Service Providers</h2>
    <p><a href="https://privacycenter.instagram.com/policy/">Meta</a> provides
    the Instagram platform. <a href="https://www.cloudflare.com/privacypolicy/">
    Cloudflare</a> hosts this service and its database. We do not sell personal
    information or share it for third-party advertising.</p>

    <h2>Retention and Deletion</h2>
    <p>We keep stored identifiers and delivery records only as long as needed
    to operate the service and prevent duplicate replies. To request access to
    or deletion of information associated with your Instagram interaction,
    email <a href="mailto:buildingintent@gmail.com">
    buildingintent@gmail.com</a>.</p>

    <h2>Contact</h2>
    <p>Email <a href="mailto:buildingintent@gmail.com">
    buildingintent@gmail.com</a> with privacy questions.</p>

    <h2>Changes to This Policy</h2>
    <p>We may update this policy when the service or its data practices change.
    The effective date above identifies the current version.</p>
  </main>
</body>
</html>`,
    {
      status: 200,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    },
  )
}

function hexBytes(value) {
  if (!/^[0-9a-f]+$/i.test(value) || value.length % 2) {
    return null
  }
  const bytes = new Uint8Array(value.length / 2)
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number.parseInt(value.slice(index * 2, index * 2 + 2), 16)
  }
  return bytes
}

function equalBytes(first, second) {
  if (!first || !second || first.length !== second.length) {
    return false
  }
  let difference = 0
  for (let index = 0; index < first.length; index += 1) {
    difference |= first[index] ^ second[index]
  }
  return difference === 0
}

async function equalText(first, second) {
  if (typeof first !== "string" || typeof second !== "string") {
    return false
  }
  const encoder = new TextEncoder()
  const [firstHash, secondHash] = await Promise.all(
    [first, second].map((value) =>
      crypto.subtle.digest("SHA-256", encoder.encode(value)),
    ),
  )
  return equalBytes(
    new Uint8Array(firstHash),
    new Uint8Array(secondHash),
  )
}

export async function verifySignature(rawBody, signature, secret) {
  if (
    typeof signature !== "string" ||
    !signature.startsWith("sha256=") ||
    typeof secret !== "string" ||
    !secret
  ) {
    return false
  }
  const supplied = hexBytes(signature.slice("sha256=".length))
  if (!supplied) {
    return false
  }
  const encoder = new TextEncoder()
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  )
  const expected = new Uint8Array(
    await crypto.subtle.sign("HMAC", key, encoder.encode(rawBody)),
  )
  return equalBytes(expected, supplied)
}

function commentChanges(payload) {
  if (payload?.object !== "instagram" || !Array.isArray(payload.entry)) {
    return []
  }
  const changes = []
  for (const entry of payload.entry) {
    if (Array.isArray(entry?.changes)) {
      for (const change of entry.changes) {
        changes.push({ accountId: entry.id, ...change })
      }
    } else if (entry?.field) {
      changes.push({
        accountId: entry.id,
        field: entry.field,
        value: entry.value,
      })
    }
  }
  return changes
}

async function registerRule(request, env) {
  const expected = `Bearer ${env.INSTAGRAM_WEBHOOK_ADMIN_TOKEN}`
  if (!(await equalText(request.headers.get("Authorization"), expected))) {
    return textResponse("Unauthorized", 401)
  }

  let rule
  try {
    rule = await request.json()
  } catch {
    return textResponse("Invalid JSON", 400)
  }
  const mediaId = rule?.media_id
  const keyword = rule?.keyword
  const promise = rule?.promise
  const reply = rule?.reply
  if (
    typeof mediaId !== "string" ||
    !/^\d{5,30}$/.test(mediaId) ||
    typeof keyword !== "string" ||
    !/^[A-Z][A-Z0-9]{1,19}$/.test(keyword) ||
    typeof promise !== "string" ||
    !promise.trim() ||
    typeof reply !== "string" ||
    !reply.trim() ||
    !reply.includes(APP_STORE_HOST)
  ) {
    return textResponse("Invalid rule", 400)
  }

  await env.DB.prepare(
    `INSERT INTO rules (media_id, keyword, promise, reply, enabled, updated_at)
     VALUES (?1, ?2, ?3, ?4, 1, CURRENT_TIMESTAMP)
     ON CONFLICT(media_id) DO UPDATE SET
       keyword = excluded.keyword,
       promise = excluded.promise,
       reply = excluded.reply,
       enabled = 1,
       updated_at = CURRENT_TIMESTAMP`,
  )
    .bind(mediaId, keyword, promise, reply)
    .run()
  return Response.json({ success: true })
}

async function sendPrivateReply(commentId, reply, env, fetcher) {
  const response = await fetcher(
    `https://graph.instagram.com/${META_API_VERSION}/` +
      `${env.INSTAGRAM_USER_ID}/messages`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.INSTAGRAM_ACCESS_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        recipient: { comment_id: commentId },
        message: { text: reply },
      }),
    },
  )
  if (!response.ok) {
    throw new Error("Instagram private reply failed")
  }
  let result
  try {
    result = await response.json()
  } catch {
    throw new Error("Instagram returned invalid JSON")
  }
  if (typeof result?.message_id !== "string" || !result.message_id) {
    throw new Error("Instagram response did not contain a message ID")
  }
  return result.message_id
}

async function handleComment(change, env, fetcher) {
  if (
    change.field !== "comments" ||
    change.accountId !== env.INSTAGRAM_USER_ID
  ) {
    return
  }
  const value = change.value
  const commentId = value?.id
  const mediaId = value?.media?.id
  const from = value?.from
  if (
    typeof commentId !== "string" ||
    typeof mediaId !== "string" ||
    typeof value?.text !== "string" ||
    from?.self_ig_scoped_id ||
    from?.id === env.INSTAGRAM_USER_ID
  ) {
    return
  }

  const rule = await env.DB.prepare(
    `SELECT reply
       FROM rules
      WHERE media_id = ?1 AND enabled = 1`,
  )
    .bind(mediaId)
    .first()
  if (!rule) {
    return
  }

  const claim = await env.DB.prepare(
    `INSERT OR IGNORE INTO deliveries
       (comment_id, media_id, status, updated_at)
     VALUES (?1, ?2, 'processing', CURRENT_TIMESTAMP)`,
  )
    .bind(commentId, mediaId)
    .run()
  if (claim?.meta?.changes !== 1) {
    return
  }

  try {
    const messageId = await sendPrivateReply(
      commentId,
      rule.reply,
      env,
      fetcher,
    )
    await env.DB.prepare(
      `UPDATE deliveries
          SET status = 'sent',
              message_id = ?1,
              updated_at = CURRENT_TIMESTAMP
        WHERE comment_id = ?2`,
    )
      .bind(messageId, commentId)
      .run()
  } catch {
    await env.DB.prepare(
      "DELETE FROM deliveries WHERE comment_id = ?1",
    )
      .bind(commentId)
      .run()
    throw new Error("Private reply delivery failed")
  }
}

async function receiveWebhook(request, env, fetcher) {
  const rawBody = await request.text()
  const valid = await verifySignature(
    rawBody,
    request.headers.get("X-Hub-Signature-256"),
    env.META_APP_SECRET,
  )
  if (!valid) {
    return textResponse("Unauthorized", 401)
  }

  let payload
  try {
    payload = JSON.parse(rawBody)
  } catch {
    return textResponse("Invalid JSON", 400)
  }
  try {
    for (const change of commentChanges(payload)) {
      await handleComment(change, env, fetcher)
    }
  } catch {
    return textResponse("Delivery failed", 500)
  }
  return textResponse("OK", 200)
}

async function verifyWebhook(request, env) {
  const url = new URL(request.url)
  const mode = url.searchParams.get("hub.mode")
  const token = url.searchParams.get("hub.verify_token")
  const challenge = url.searchParams.get("hub.challenge")
  if (
    mode === "subscribe" &&
    typeof challenge === "string" &&
    (await equalText(token, env.INSTAGRAM_WEBHOOK_VERIFY_TOKEN))
  ) {
    return textResponse(challenge, 200)
  }
  return textResponse("Forbidden", 403)
}

export async function handleRequest(request, env, fetcher = fetch) {
  const { pathname } = new URL(request.url)
  if (pathname === "/privacy" && request.method === "GET") {
    return privacyResponse()
  }
  if (pathname === "/instagram/webhook" && request.method === "GET") {
    return verifyWebhook(request, env)
  }
  if (pathname === "/instagram/webhook" && request.method === "POST") {
    return receiveWebhook(request, env, fetcher)
  }
  if (pathname === "/admin/rules" && request.method === "POST") {
    try {
      return await registerRule(request, env)
    } catch {
      return textResponse("Registration failed", 500)
    }
  }
  return textResponse("Not found", 404)
}

export default {
  fetch(request, env) {
    return handleRequest(request, env)
  },
}
