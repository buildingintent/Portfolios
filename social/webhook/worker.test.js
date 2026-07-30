import assert from "node:assert/strict"
import { createHmac } from "node:crypto"
import test from "node:test"

import { handleRequest } from "./worker.js"

const MEDIA_ID = "18000000000000001"
const COMMENT_ID = "17900000000000002"
const APP_URL =
  "https://apps.apple.com/us/app/fina-financial-companion/id6778169653"

class FakeStatement {
  constructor(db, sql) {
    this.db = db
    this.sql = sql
    this.values = []
  }

  bind(...values) {
    this.values = values
    return this
  }

  async first() {
    if (this.sql.includes("FROM rules")) {
      const rule = this.db.rules.get(this.values[0])
      return rule?.enabled ? { ...rule } : null
    }
    throw new Error(`Unexpected first query: ${this.sql}`)
  }

  async run() {
    if (this.sql.includes("INSERT INTO rules")) {
      const [mediaId, keyword, promise, reply] = this.values
      this.db.rules.set(mediaId, {
        media_id: mediaId,
        keyword,
        promise,
        reply,
        enabled: 1,
      })
      return { success: true, meta: { changes: 1 } }
    }
    if (this.sql.includes("INSERT OR IGNORE INTO deliveries")) {
      const [commentId, mediaId] = this.values
      if (this.db.deliveries.has(commentId)) {
        return { success: true, meta: { changes: 0 } }
      }
      this.db.deliveries.set(commentId, {
        comment_id: commentId,
        media_id: mediaId,
        status: "processing",
      })
      return { success: true, meta: { changes: 1 } }
    }
    if (this.sql.includes("UPDATE deliveries")) {
      const [messageId, commentId] = this.values
      const delivery = this.db.deliveries.get(commentId)
      if (delivery) {
        delivery.status = "sent"
        delivery.message_id = messageId
      }
      return { success: true, meta: { changes: delivery ? 1 : 0 } }
    }
    if (this.sql.includes("DELETE FROM deliveries")) {
      const changed = this.db.deliveries.delete(this.values[0])
      return { success: true, meta: { changes: changed ? 1 : 0 } }
    }
    throw new Error(`Unexpected run query: ${this.sql}`)
  }
}

class FakeDB {
  constructor() {
    this.rules = new Map()
    this.deliveries = new Map()
    this.prepareCalls = 0
  }

  prepare(sql) {
    this.prepareCalls += 1
    return new FakeStatement(this, sql)
  }
}

function environment() {
  return {
    DB: new FakeDB(),
    INSTAGRAM_ACCESS_TOKEN: "instagram-token",
    INSTAGRAM_USER_ID: "17841425833103994",
    META_APP_SECRET: "meta-app-secret",
    INSTAGRAM_WEBHOOK_VERIFY_TOKEN: "verify-token",
    INSTAGRAM_WEBHOOK_ADMIN_TOKEN: "admin-token",
  }
}

function commentPayload({
  mediaId = MEDIA_ID,
  commentId = COMMENT_ID,
  text = "  forecast! ",
  from = { id: "17900000000000001", username: "viewer" },
} = {}) {
  return {
    object: "instagram",
    entry: [
      {
        id: "17841425833103994",
        time: 1785400000000,
        changes: [
          {
            field: "comments",
            value: {
              from,
              id: commentId,
              text,
              media: {
                id: mediaId,
                media_product_type: "FEED",
              },
            },
          },
        ],
      },
    ],
  }
}

function signedWebhook(payload, secret = "meta-app-secret") {
  const body = JSON.stringify(payload)
  const digest = createHmac("sha256", secret).update(body).digest("hex")
  return new Request("https://worker.test/instagram/webhook", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Hub-Signature-256": `sha256=${digest}`,
    },
    body,
  })
}

async function registerRule(env) {
  return handleRequest(
    new Request("https://worker.test/admin/rules", {
      method: "POST",
      headers: {
        Authorization: "Bearer admin-token",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        media_id: MEDIA_ID,
        keyword: "FORECAST",
        promise: "A simple checklist for looking ahead.",
        reply: `Here is the checklist.\n\nFina can help:\n${APP_URL}`,
      }),
    }),
    env,
  )
}

test("serves the public privacy policy without application state", async () => {
  const response = await handleRequest(
    new Request("https://worker.test/privacy"),
    {},
  )
  const rejected = await handleRequest(
    new Request("https://worker.test/privacy", { method: "POST" }),
    {},
  )
  const html = await response.text()

  assert.equal(response.status, 200)
  assert.equal(rejected.status, 404)
  assert.match(response.headers.get("Content-Type"), /^text\/html/)
  assert.match(html, /Building Intent Social Publish/)
  assert.match(html, /Effective date: July 30, 2026/)
  assert.match(html, /Information We Receive/)
  assert.match(html, /How We Use Information/)
  assert.match(html, /Sharing and Service Providers/)
  assert.match(html, /Retention and Deletion/)
  assert.match(html, /buildingintent@gmail\.com/)
  assert.match(html, /privacycenter\.instagram\.com\/policy/)
  assert.match(html, /cloudflare\.com\/privacypolicy/)
  assert.doesNotMatch(html, /<script/i)
})

test("answers Meta verification only for the configured token", async () => {
  const env = environment()
  const accepted = await handleRequest(
    new Request(
      "https://worker.test/instagram/webhook" +
        "?hub.mode=subscribe&hub.verify_token=verify-token" +
        "&hub.challenge=123456",
    ),
    env,
  )
  const rejected = await handleRequest(
    new Request(
      "https://worker.test/instagram/webhook" +
        "?hub.mode=subscribe&hub.verify_token=wrong" +
        "&hub.challenge=123456",
    ),
    env,
  )

  assert.equal(accepted.status, 200)
  assert.equal(await accepted.text(), "123456")
  assert.equal(rejected.status, 403)
})

test("rejects an invalid X Hub signature before D1 access", async () => {
  const env = environment()
  const response = await handleRequest(
    signedWebhook(commentPayload(), "wrong-secret"),
    env,
  )

  assert.equal(response.status, 401)
  assert.equal(env.DB.prepareCalls, 0)
})

test("registers one authenticated media rule", async () => {
  const env = environment()
  const rejected = await handleRequest(
    new Request("https://worker.test/admin/rules", {
      method: "POST",
      headers: {
        Authorization: "Bearer wrong",
        "Content-Type": "application/json",
      },
      body: "{}",
    }),
    env,
  )
  const accepted = await registerRule(env)

  assert.equal(rejected.status, 401)
  assert.equal(accepted.status, 200)
  assert.deepEqual(env.DB.rules.get(MEDIA_ID), {
    media_id: MEDIA_ID,
    keyword: "FORECAST",
    promise: "A simple checklist for looking ahead.",
    reply: `Here is the checklist.\n\nFina can help:\n${APP_URL}`,
    enabled: 1,
  })
})

test("rejects a rule without a promise and App Store link", async () => {
  const env = environment()
  const response = await handleRequest(
    new Request("https://worker.test/admin/rules", {
      method: "POST",
      headers: {
        Authorization: "Bearer admin-token",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        media_id: MEDIA_ID,
        keyword: "FORECAST",
        promise: "",
        reply: "A message without the approved link.",
      }),
    }),
    env,
  )

  assert.equal(response.status, 400)
  assert.equal(env.DB.rules.size, 0)
})

test("sends the registered reply for any non self comment text", async () => {
  const env = environment()
  await registerRule(env)
  const requests = []
  const fetcher = async (url, options) => {
    requests.push({ url, options })
    return Response.json({
      recipient_id: "17900000000000001",
      message_id: "message-1",
    })
  }

  const response = await handleRequest(
    signedWebhook(commentPayload({ text: "This was useful!" })),
    env,
    fetcher,
  )

  assert.equal(response.status, 200)
  assert.equal(requests.length, 1)
  assert.equal(
    requests[0].url,
    "https://graph.instagram.com/v24.0/" +
      "17841425833103994/messages",
  )
  assert.equal(
    requests[0].options.headers.Authorization,
    "Bearer instagram-token",
  )
  assert.deepEqual(JSON.parse(requests[0].options.body), {
    recipient: { comment_id: COMMENT_ID },
    message: {
      text: `Here is the checklist.\n\nFina can help:\n${APP_URL}`,
    },
  })
  assert.equal(env.DB.deliveries.get(COMMENT_ID).status, "sent")
})

test("accepts Meta direct field comment payloads", async () => {
  const env = environment()
  await registerRule(env)
  const payload = commentPayload()
  const change = payload.entry[0].changes[0]
  payload.entry[0] = {
    id: payload.entry[0].id,
    time: payload.entry[0].time,
    field: change.field,
    value: change.value,
  }
  let sends = 0
  const fetcher = async () => {
    sends += 1
    return Response.json({ message_id: "message-1" })
  }

  const response = await handleRequest(
    signedWebhook(payload),
    env,
    fetcher,
  )

  assert.equal(response.status, 200)
  assert.equal(sends, 1)
})

test("ignores unknown media and self comments", async () => {
  const env = environment()
  await registerRule(env)
  let sends = 0
  const fetcher = async () => {
    sends += 1
    return Response.json({ message_id: "unexpected" })
  }
  const payloads = [
    commentPayload({ mediaId: "18000000000000999" }),
    commentPayload({
      from: {
        id: "17841425833103994",
        username: "buildingintent",
        self_ig_scoped_id: "17841425833103994",
      },
    }),
  ]

  for (const payload of payloads) {
    const response = await handleRequest(
      signedWebhook(payload),
      env,
      fetcher,
    )
    assert.equal(response.status, 200)
  }

  assert.equal(sends, 0)
  assert.equal(env.DB.deliveries.size, 0)
})

test("duplicate webhook delivery sends only one private reply", async () => {
  const env = environment()
  await registerRule(env)
  let sends = 0
  const fetcher = async () => {
    sends += 1
    return Response.json({ message_id: "message-1" })
  }
  const request = () => signedWebhook(commentPayload())

  assert.equal((await handleRequest(request(), env, fetcher)).status, 200)
  assert.equal((await handleRequest(request(), env, fetcher)).status, 200)
  assert.equal(sends, 1)
})

test("provider failure releases the comment for Meta retry", async () => {
  const env = environment()
  await registerRule(env)
  let sends = 0
  const fetcher = async () => {
    sends += 1
    if (sends === 1) {
      return new Response("private provider body", { status: 503 })
    }
    return Response.json({ message_id: "message-1" })
  }

  const failed = await handleRequest(
    signedWebhook(commentPayload()),
    env,
    fetcher,
  )
  assert.equal(failed.status, 500)
  assert.equal(env.DB.deliveries.has(COMMENT_ID), false)

  const retried = await handleRequest(
    signedWebhook(commentPayload()),
    env,
    fetcher,
  )
  assert.equal(retried.status, 200)
  assert.equal(sends, 2)
  assert.equal(env.DB.deliveries.get(COMMENT_ID).status, "sent")
})
