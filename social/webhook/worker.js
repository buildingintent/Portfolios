const META_API_VERSION = "v24.0"
const APP_STORE_HOST = "https://apps.apple.com/"

function textResponse(text, status) {
  return new Response(text, {
    status,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  })
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

export function normalizeKeyword(text) {
  if (typeof text !== "string") {
    return ""
  }
  return text
    .trim()
    .replace(/^[\p{P}\p{S}]+|[\p{P}\p{S}]+$/gu, "")
    .toUpperCase()
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
    `SELECT keyword, reply
       FROM rules
      WHERE media_id = ?1 AND enabled = 1`,
  )
    .bind(mediaId)
    .first()
  if (!rule || normalizeKeyword(value.text) !== rule.keyword) {
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
