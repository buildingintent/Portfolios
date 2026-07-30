# Instagram Comment DM Webhook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register one approved keyword and private reply for every promotional Instagram post, then send that post-specific help and App Store link once when a matching comment arrives.

**Architecture:** The existing Python publisher remains responsible for approvals, Instagram publication, and R2 cleanup. After Instagram returns the published media ID, it sends the approved `comment_rule` to one authenticated Cloudflare Worker administration endpoint. The Worker verifies Meta webhook signatures, looks up the media-specific rule in D1, claims each comment ID once, and calls Instagram Private Replies.

**Tech Stack:** Python 3.11 standard library and existing `unittest` suite, JavaScript ES modules on Cloudflare Workers, Cloudflare D1, Node 22 built-in test runner, Wrangler 4.115.0, Instagram API with Instagram Login.

## Global Constraints

- Keep the existing two approvals. `콘텐츠 승인` locks the keyword, public promise, and full private reply; `승인` publishes and registers that exact rule.
- Promotional captions contain the comment keyword and no raw App Store URL.
- The private reply delivers useful help first and contains the project's exact App Store URL as an optional next step.
- Audience-facing copy uses the installed `humanizer` skill and contains no hyphens, en dashes, or em dashes except inside an exact URL.
- Do not log tokens, signatures, webhook bodies, comment text, usernames, private replies, or provider response bodies.
- Secrets stay in ignored local `.env` files or Cloudflare Worker Secrets.
- Reject invalid Meta signatures and invalid administration credentials before reading or changing D1.
- Ignore unknown media, unrelated comments, another Instagram account, and self-comments.
- Match the whole normalized comment, case-insensitively, after removing only surrounding whitespace and punctuation.
- A successfully handled comment ID never sends a second private reply.
- Do not add a dashboard, queue, scheduled job, framework, or custom server.

---

### Task 1: Lock the Post-Specific Comment Rule in the Draft

**Files:**

- Modify: `social/test_social.py`
- Modify: `social/render.py`
- Modify: `social/PROMPT.md`

**Interfaces:**

- Consumes: existing draft dictionaries and `validate_content(draft, project, blocked_formats) -> list[str]`.
- Produces: required promotional draft field `comment_rule` with `keyword`, `promise`, and `reply` strings.

- [ ] **Step 1: Write failing draft validation tests**

Add these behaviors to `DraftValidationTests`:

```python
def test_accepts_post_specific_comment_rule_without_caption_url(self):
    draft = self.valid_draft()
    draft["caption"] = "Want the checklist? Comment FORECAST."
    draft["slides"][-1]["body"] = (
        "Comment FORECAST and we will send the checklist."
    )
    draft["comment_rule"] = {
        "keyword": "FORECAST",
        "promise": "A simple checklist for looking ahead.",
        "reply": (
            "Start with the bills you know are coming, then add normal "
            "weekly spending and leave room for irregular costs.\n\n"
            "If you want help seeing upcoming pressure, Fina can help:\n"
            "https://apps.apple.com/us/app/"
            "fina-financial-companion/id6778169653"
        ),
    }
    self.assertEqual(validate_draft(draft, self.project(), set()), [])

def test_rejects_missing_or_unapproved_comment_rule_copy(self):
    draft = self.valid_draft()
    draft["caption"] = "Comment FORECAST."
    draft["slides"][-1]["body"] = "Comment FORECAST."
    draft["comment_rule"] = {
        "keyword": "forecast please",
        "promise": "",
        "reply": "A useful message without the approved app link.",
    }
    errors = validate_draft(draft, self.project(), set())
    self.assertIn(
        "comment keyword must contain 2 to 20 uppercase ASCII letters or numbers",
        errors,
    )
    self.assertIn("comment promise must be a non-empty string", errors)
    self.assertIn(
        "private reply must contain the project's App Store URL",
        errors,
    )

def test_rejects_raw_app_store_url_in_promotional_caption(self):
    draft = self.valid_draft()
    draft["comment_rule"] = {
        "keyword": "FORECAST",
        "promise": "A simple checklist.",
        "reply": (
            "Here is the checklist.\n"
            "https://apps.apple.com/us/app/"
            "fina-financial-companion/id6778169653"
        ),
    }
    errors = validate_draft(draft, self.project(), set())
    self.assertIn(
        "caption must not contain the project's App Store URL",
        errors,
    )
```

Update `valid_draft()` so its normal caption and CTA contain `FORECAST`, while its `comment_rule.reply` contains the exact Fina URL.
Replace the old `test_requires_exact_app_store_url_in_caption` with
`test_rejects_raw_app_store_url_in_promotional_caption`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  social.test_social.DraftValidationTests.test_accepts_post_specific_comment_rule_without_caption_url \
  social.test_social.DraftValidationTests.test_rejects_missing_or_unapproved_comment_rule_copy \
  social.test_social.DraftValidationTests.test_rejects_raw_app_store_url_in_promotional_caption \
  -v
```

Expected: failures because `validate_content` still requires the App Store URL in the caption and does not validate `comment_rule`.

- [ ] **Step 3: Implement the minimal draft validation**

In `validate_content`:

```python
comment_rule = draft.get("comment_rule")
if not isinstance(comment_rule, dict):
    errors.append("comment_rule must be an object")
else:
    keyword = comment_rule.get("keyword")
    promise = comment_rule.get("promise")
    reply = comment_rule.get("reply")
    if not isinstance(keyword, str) or not re.fullmatch(
        r"[A-Z][A-Z0-9]{1,19}", keyword
    ):
        errors.append(
            "comment keyword must contain 2 to 20 uppercase ASCII "
            "letters or numbers"
        )
    if not _non_empty_string(promise):
        errors.append("comment promise must be a non-empty string")
    if not _non_empty_string(reply):
        errors.append("private reply must be a non-empty string")
    elif project.get("app_store_url") not in reply:
        errors.append(
            "private reply must contain the project's App Store URL"
        )
    if isinstance(keyword, str):
        cta = draft.get("slides", [{}])[-1]
        cta_copy = " ".join(
            str(cta.get(field, "")) for field in ("headline", "body")
        )
        if keyword not in caption or keyword not in cta_copy:
            errors.append(
                "comment keyword must appear in the caption and CTA"
            )
```

Replace the old caption URL requirement with:

```python
if project.get("app_store_url") in caption:
    errors.append(
        "caption must not contain the project's App Store URL"
    )
```

Because `comment_rule` is included in the existing content fingerprint, content approval automatically locks all three fields.

- [ ] **Step 4: Update the operational content contract**

Change `social/PROMPT.md` so it:

- Starts only when the user sends `오늘 루틴 시작`.
- Shows `Comment keyword`, `Promise`, and `Private reply` during content approval and final review.
- Requires a useful reply first and the optional app link second.
- Removes every requirement and example that puts the raw App Store URL in the caption.
- Uses the exact `comment_rule` JSON shape above in both examples.

- [ ] **Step 5: Run the complete Python suite**

Run:

```bash
.venv/bin/python -m unittest social/test_social.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add social/render.py social/test_social.py social/PROMPT.md
git commit -m "feat: lock Instagram comment replies in drafts"
```

---

### Task 2: Receive Signed Comment Webhooks and Send One Private Reply

**Files:**

- Create: `social/webhook/package.json`
- Create: `social/webhook/package-lock.json`
- Create: `social/webhook/wrangler.jsonc`
- Create: `social/webhook/schema.sql`
- Create: `social/webhook/worker.js`
- Create: `social/webhook/worker.test.js`
- Modify: `.gitignore`

**Interfaces:**

- Consumes: Worker Secrets `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`, `META_APP_SECRET`, `INSTAGRAM_WEBHOOK_VERIFY_TOKEN`, and `INSTAGRAM_WEBHOOK_ADMIN_TOKEN`; D1 binding `DB`.
- Produces: `GET|POST /instagram/webhook` and authenticated `POST /admin/rules`.

- [ ] **Step 1: Create the Node test package and write failing Worker tests**

Create `package.json`:

```json
{
  "name": "building-intent-instagram-webhook",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test worker.test.js"
  },
  "devDependencies": {
    "wrangler": "4.115.0"
  }
}
```

Write tests using `node:test`, `node:assert/strict`, a stateful in-memory D1 fake, and a fake `fetch` only for the external Instagram boundary. Cover:

```javascript
test("answers Meta verification only for the configured token", async () => {})
test("rejects an invalid X Hub signature before D1 access", async () => {})
test("registers one authenticated media rule", async () => {})
test("sends the registered reply for a normalized exact keyword", async () => {})
test("ignores unknown media, unrelated text, and self comments", async () => {})
test("duplicate webhook delivery sends only one private reply", async () => {})
test("provider failure releases the comment for Meta retry", async () => {})
```

The realistic comment fixture is:

```javascript
{
  object: "instagram",
  entry: [{
    id: "17841425833103994",
    time: 1785400000000,
    changes: [{
      field: "comments",
      value: {
        from: { id: "17900000000000001", username: "viewer" },
        id: "17900000000000002",
        text: "  forecast! ",
        media: {
          id: "18000000000000001",
          media_product_type: "FEED"
        }
      }
    }]
  }]
}
```

- [ ] **Step 2: Run Worker tests and verify RED**

Run:

```bash
cd social/webhook
npm install
npm test
```

Expected: import failure because `worker.js` does not exist.

- [ ] **Step 3: Add the D1 schema**

Create `schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS rules (
  media_id TEXT PRIMARY KEY,
  keyword TEXT NOT NULL,
  promise TEXT NOT NULL,
  reply TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS deliveries (
  comment_id TEXT PRIMARY KEY,
  media_id TEXT NOT NULL,
  status TEXT NOT NULL,
  message_id TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 4: Implement the minimal Worker**

Export `normalizeKeyword(text)`, `verifySignature(rawBody, signature, secret)`, `handleRequest(request, env, fetcher = fetch)`, and the default Worker `{ fetch }`.

Required behavior:

```javascript
function normalizeKeyword(text) {
  return text
    .trim()
    .replace(/^[\p{P}\p{S}]+|[\p{P}\p{S}]+$/gu, "")
    .toUpperCase()
}
```

- Meta verification compares `hub.verify_token` and returns `hub.challenge`.
- Webhook POST reads the raw body once and verifies `X-Hub-Signature-256` with HMAC SHA-256 before JSON parsing or D1 access.
- Accept both official payload shapes: `entry.changes[]` and direct `entry.field` plus `entry.value`.
- Rule registration requires `Authorization: Bearer <admin token>`, a numeric media ID, a 2 to 20 character uppercase keyword, a non-empty promise, and a reply containing `https://apps.apple.com/`.
- D1 rule lookup uses `media_id` as the primary key.
- Claim a comment with `INSERT OR IGNORE`. Skip when no row changed.
- Send:

```json
{
  "recipient": {"comment_id": "comment-1"},
  "message": {"text": "the approved reply"}
}
```

to:

```text
https://graph.instagram.com/v24.0/<INSTAGRAM_USER_ID>/messages
```

with a Bearer access token.

- On provider success, update delivery status to `sent` and store `message_id`.
- On provider or network failure, delete the claim and return HTTP 500 so Meta can retry.
- Return HTTP 200 for valid but irrelevant or duplicate webhook events.

- [ ] **Step 5: Add Wrangler configuration and secret ignores**

Create `wrangler.jsonc` without the production D1 binding, which is added with
the real database ID in Task 4:

```jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "building-intent-instagram-webhook",
  "main": "worker.js",
  "compatibility_date": "2026-07-30"
}
```

Add to `.gitignore`:

```gitignore
social/webhook/.dev.vars*
social/webhook/.wrangler/
```

- [ ] **Step 6: Run Worker tests**

Run:

```bash
cd social/webhook
npm test
npx wrangler deploy --dry-run
```

Expected: every test passes and the dry-run build exits 0.

- [ ] **Step 7: Commit Task 2**

```bash
git add .gitignore social/webhook
git commit -m "feat: add Instagram comment webhook"
```

---

### Task 3: Register the Approved Rule After Instagram Publication

**Files:**

- Modify: `social/test_social.py`
- Modify: `social/publish.py`

**Interfaces:**

- Consumes: `draft["comment_rule"]`, Instagram `media_id`, `INSTAGRAM_WEBHOOK_ADMIN_URL`, and `INSTAGRAM_WEBHOOK_ADMIN_TOKEN`.
- Produces: `RuleRegistry.register(media_id: str, rule: dict) -> None` and `--register-rule-only <draft.json>` recovery.

- [ ] **Step 1: Write failing publisher integration tests**

Add a `FakeRuleRegistry` with `register(media_id, rule)` and tests:

```python
def test_success_registers_exact_approved_rule_after_publish(self):
    registry = FakeRuleRegistry()
    media_id = publish(
        self.draft,
        self.files,
        self.r2,
        self.instagram,
        self.history,
        public_history=self.public_history,
        rule_registry=registry,
    )
    self.assertEqual(
        registry.registrations,
        [("media-1", self.draft["comment_rule"])],
    )
    self.assertEqual(media_id, "media-1")

def test_rule_registration_failure_does_not_republish(self):
    registry = FakeRuleRegistry(fail=True)
    with self.assertRaisesRegex(
        RuntimeError,
        "published but comment rule registration failed",
    ):
        publish(
            self.draft,
            self.files,
            self.r2,
            self.instagram,
            self.history,
            public_history=self.public_history,
            rule_registry=registry,
        )
    self.assertEqual(self.instagram.publish_calls, 1)
    self.assertEqual(
        latest_event("d1", read_events(self.history))["event"],
        "rule_registration_failed",
    )
```

Also test that `RuleRegistry` sends the expected JSON, Bearer header, timeout, and generic errors without echoing a provider body.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  social.test_social.PublishFlowTests.test_success_registers_exact_approved_rule_after_publish \
  social.test_social.PublishFlowTests.test_rule_registration_failure_does_not_republish \
  -v
```

Expected: failures because `publish` has no `rule_registry` parameter and `RuleRegistry` does not exist.

- [ ] **Step 3: Implement the registry client**

Add:

```python
class RuleRegistry:
    def __init__(self, url, token, open_url=urlopen):
        self.url = url
        self.token = token
        self.open_url = open_url

    def register(self, media_id: str, rule: dict) -> None:
        payload = json.dumps(
            {"media_id": media_id, **rule},
            separators=(",", ":"),
        ).encode()
        request = Request(
            self.url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        # Require HTTP success and {"success": true}; expose no body.
```

Extend normal publish credential validation with:

```text
INSTAGRAM_WEBHOOK_ADMIN_URL
INSTAGRAM_WEBHOOK_ADMIN_TOKEN
```

Do not require these values for `--cleanup-only`.

- [ ] **Step 4: Register after publication without compromising publication state**

After recording the Instagram media ID and public history:

```python
try:
    rule_registry.register(media_id, draft["comment_rule"])
except Exception:
    append_event(
        history,
        _event(
            draft,
            "rule_registration_failed",
            instagram_media_id=media_id,
        ),
    )
    raise RuntimeError(
        "published but comment rule registration failed; "
        "run --register-rule-only with the approved draft"
    ) from None
append_event(
    history,
    _event(
        draft,
        "comment_rule_registered",
        instagram_media_id=media_id,
    ),
)
```

`--register-rule-only <draft.json>` finds the recorded published media ID,
uses `assert_approved_content` to prove the current `comment_rule` still
matches content approval, registers it, and never calls Instagram or R2.

- [ ] **Step 5: Run the complete local verification**

Run:

```bash
.venv/bin/python -m unittest social/test_social.py -v
.venv/bin/python -m compileall -q social
cd social/webhook && npm test && npx wrangler deploy --dry-run
```

Expected: all commands exit 0.

- [ ] **Step 6: Commit Task 3**

```bash
git add social/publish.py social/test_social.py
git commit -m "feat: register post comment rules"
```

---

### Task 4: Document and Deploy the Minimal Production Setup

**Files:**

- Modify: `social/README.md`
- Modify: `social/webhook/wrangler.jsonc`
- Modify: `docs/superpowers/specs/2026-07-29-instagram-promotion-automation-design.md`

**Interfaces:**

- Consumes: authenticated Wrangler session, the existing Instagram professional account and access token, Meta app secret, and locally generated verification and administration tokens.
- Produces: deployed Worker URL, D1 schema, Worker Secrets, and Meta `comments` subscription instructions.

- [ ] **Step 1: Update setup and operating documentation**

Document:

- `npm install`, D1 creation, schema application, Worker Secret creation, and deployment commands.
- Required local `.env` variable names without values.
- Meta callback path `/instagram/webhook`, verification token setup, `instagram_business_manage_comments`, and `comments` subscription.
- The approved content display now includes the keyword, promise, and full private reply.
- Recovery with `--register-rule-only`.
- Cloudflare free limits: 100,000 Worker requests per day; D1 5 million rows read per day, 100,000 rows written per day, and 500MB per free database.
- No Tailscale requirement and no raw App Store URL in promotional captions.

- [ ] **Step 2: Create D1 and deploy when Wrangler is authenticated**

Run:

```bash
cd social/webhook
npx wrangler whoami
npx wrangler d1 create building-intent-instagram
```

Add the returned public database ID to `wrangler.jsonc`:

```jsonc
"d1_databases": [{
  "binding": "DB",
  "database_name": "building-intent-instagram",
  "database_id": "<ID returned by wrangler d1 create>"
}]
```

Then run:

```bash
npx wrangler d1 execute building-intent-instagram \
  --remote --file schema.sql
npx wrangler deploy
```

If authentication is absent, stop before mutation and give the user the single
Wrangler login action required.

- [ ] **Step 3: Configure secrets without committing values**

Create two random 32-byte tokens locally: one webhook verification token and
one administration token. Add all five Worker Secrets through Wrangler:

```text
INSTAGRAM_ACCESS_TOKEN
INSTAGRAM_USER_ID
META_APP_SECRET
INSTAGRAM_WEBHOOK_VERIFY_TOKEN
INSTAGRAM_WEBHOOK_ADMIN_TOKEN
```

The local repository-root `.env` receives only:

```text
INSTAGRAM_WEBHOOK_ADMIN_URL
INSTAGRAM_WEBHOOK_ADMIN_TOKEN
```

Never print either value.

- [ ] **Step 4: Run deployed smoke checks**

Verify:

- Wrong verify token returns 403.
- Correct verification returns the exact challenge.
- Invalid webhook signature returns 401 and creates no D1 delivery.
- Authenticated registration of a disposable numeric media ID succeeds.
- D1 contains the disposable rule, then delete that rule.

Meta dashboard configuration and a real Instagram comment remain explicit
external checks because they require the live app permissions and user action.

- [ ] **Step 5: Mark the design revision implemented and run final verification**

Change the design status to `Implemented, external Meta verification pending`
when deployment succeeds, or `Implemented locally, deployment pending` when
Wrangler authentication or secrets are unavailable.

Run:

```bash
.venv/bin/python -m unittest social/test_social.py -v
.venv/bin/python -m compileall -q social
cd social/webhook
npm test
npx wrangler deploy --dry-run
git diff --check
git status --short
```

- [ ] **Step 6: Commit Task 4**

```bash
git add social/README.md social/webhook/wrangler.jsonc \
  docs/superpowers/specs/2026-07-29-instagram-promotion-automation-design.md
git commit -m "docs: add Instagram webhook operations"
```
