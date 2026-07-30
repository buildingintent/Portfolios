# Instagram Webhook Privacy Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve and deploy an accurate public privacy policy at the existing Instagram Webhook Worker's `/privacy` route.

**Architecture:** Add one static HTML response function and one GET route to the existing dependency-free Worker. Keep the page self-contained, test its externally visible disclosures, then deploy and verify the live URL.

**Tech Stack:** Cloudflare Workers JavaScript ES modules, Node built-in test runner, Wrangler

## Global Constraints

* Serve the page only for `GET /privacy`.
* Use no client-side JavaScript, cookies, analytics, third-party assets, framework, or new dependency.
* Use `buildingintent@gmail.com` as the public privacy contact.
* Describe only the data behavior implemented in `social/webhook/worker.js` and `social/webhook/schema.sql`.
* Do not claim legal certification or guaranteed regulatory compliance.

---

### Task 1: Add and Deploy the Privacy Policy

**Files:**
- Modify: `social/webhook/worker.test.js`
- Modify: `social/webhook/worker.js`

**Interfaces:**
- Consumes: `handleRequest(request: Request, env: object, fetcher?: Function): Promise<Response>`
- Produces: `GET /privacy -> Response` with HTTP 200 and `text/html; charset=utf-8`

- [ ] **Step 1: Write the failing route test**

Add this test to `social/webhook/worker.test.js`:

```js
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
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
cd social/webhook
node --test --test-name-pattern="serves the public privacy policy"
```

Expected: FAIL because the current catch-all route returns HTTP 404.

- [ ] **Step 3: Add the minimal self-contained page**

In `social/webhook/worker.js`, add a `privacyResponse()` function that returns
HTTP 200 with `Content-Type: text/html; charset=utf-8`. Its static English HTML
must include:

```html
<title>Privacy Policy | Building Intent Social Publish</title>
<h1>Privacy Policy</h1>
<p>Effective date: July 30, 2026</p>
<p>Building Intent Social Publish helps manage posts and respond when people
request a resource by commenting with a post-specific keyword.</p>
<h2>Information We Receive</h2>
<p>Meta may send us an Instagram comment ID, media ID, username, and comment
text when someone comments on content managed by Building Intent Social
Publish. We compare comment text with the keyword offered in that post. We do
not store the comment text or username.</p>
<h2>Information We Store</h2>
<p>We store the media-specific keyword and approved reply, comment IDs used to
prevent duplicate replies, delivery status, and Meta message IDs.</p>
<h2>How We Use Information</h2>
<p>We use this information to send the requested resource and relevant App
Store link, prevent duplicate messages, secure the service, and troubleshoot
delivery failures.</p>
<h2>Sharing and Service Providers</h2>
<p>Meta provides the Instagram platform and Cloudflare hosts this service and
its database. We do not sell personal information or share it for third-party
advertising.</p>
<h2>Retention and Deletion</h2>
<p>We keep stored identifiers and delivery records only as long as needed to
operate the service and prevent duplicate replies. To request access or
deletion, email buildingintent@gmail.com.</p>
<h2>Contact</h2>
<p>Email buildingintent@gmail.com with privacy questions.</p>
<h2>Changes to This Policy</h2>
<p>We may update this policy when the service or its data practices change. The
effective date above identifies the current version.</p>
```

Include readable inline CSS, a link to Meta's privacy policy at
`https://privacycenter.instagram.com/policy/`, and a link to Cloudflare's
privacy policy at `https://www.cloudflare.com/privacypolicy/`. Do not include a
script element or any remote asset.

Add this route before the existing Webhook routes:

```js
if (pathname === "/privacy" && request.method === "GET") {
  return privacyResponse()
}
```

- [ ] **Step 4: Run Worker tests and dry-run deployment**

Run:

```bash
cd social/webhook
npm test
npx wrangler deploy --dry-run
```

Expected: all 10 tests PASS and the D1 `env.DB` binding appears in the dry-run
output.

- [ ] **Step 5: Deploy and verify the public page**

Run:

```bash
cd social/webhook
npx wrangler deploy
curl --fail --silent \
  https://building-intent-instagram-webhook.cwsbrian.workers.dev/privacy \
  | grep -F "Building Intent Social Publish"
```

Expected: deployment succeeds and the live response contains the service name.

- [ ] **Step 6: Commit**

```bash
git add social/webhook/worker.js social/webhook/worker.test.js
git commit -m "feat: publish Instagram webhook privacy policy"
```
