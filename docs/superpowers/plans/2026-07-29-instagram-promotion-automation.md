# Instagram Promotion Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one English Instagram carousel draft at 8:00 AM America/Vancouver, present it in this Codex task for approval, and publish it immediately after `승인` using private R2 staging that is always cleaned up.

**Architecture:** Codex owns the creative loop: it selects the next app and unused storytelling format, writes the draft, generates text-free illustrations with the built-in image model, runs a deterministic Pillow renderer, and displays the result in chat. Two small Python programs enforce the trust boundaries: `render.py` validates and composes drafts, while `publish.py` records approval, stages JPEGs in R2, calls Instagram, prevents duplicate publication, and deletes staging objects in a `finally` path. Public configuration and non-secret publication history stay in Git; secrets and unpublished work do not.

**Tech Stack:** Python 3.11+, Pillow, boto3 for the S3-compatible R2 API, Python standard library (`argparse`, `json`, `urllib`, `unittest`, `unittest.mock`), Codex recurring automations, Codex image generation, Instagram API with Instagram Login.

**Global Constraints:**

- Keep the implementation to two production Python files and one test file.
- Do not add a web UI, database, queue, OpenAI API client, or generic provider abstraction.
- Never write credentials, access tokens, presigned URLs, or unpublished drafts into the repository.
- Never upload anything before explicit chat approval.
- Never automatically retry a draft whose last state is `publishing`; that state is intentionally treated as uncertain to prevent duplicate Instagram posts.
- R2 cleanup runs after every attempted upload, including Instagram failures, and an empty-prefix check is mandatory.
- Use only Apple-provided App Store badge artwork, without modification.
- Treat provider input and output as trust boundaries: validate files, JSON, HTTP status, response shape, and state transitions.

---

## Locked Public Configuration

Implement `social/projects.json` with these values:

```json
{
  "schedule": {
    "timezone": "America/Vancouver",
    "slots": ["08:00"]
  },
  "formats": [
    "ways-checklist",
    "mistake-fix",
    "signs-red-flags",
    "before-after",
    "myth-reality",
    "mini-story",
    "quiz-reveal",
    "what-happens-next",
    "do-this-not-that",
    "a-vs-b",
    "script-formula",
    "ranked-options",
    "three-levels",
    "contrarian-breakdown",
    "mini-case-study",
    "short-action-plan"
  ],
  "projects": [
    {
      "id": "say-better",
      "name": "Say Better",
      "active": true,
      "logo": "assets/say-better/logo.png",
      "app_store_url": "https://apps.apple.com/us/app/say-better/id6784318555",
      "positioning": "Polish everyday writing into clear, confident, professional English without leaving the place you are typing.",
      "audiences": [
        "English speakers communicating across languages",
        "People writing professional messages and email from a phone"
      ],
      "problems": [
        "A message is correct but sounds colder than intended",
        "A long phone-written email hides the main request",
        "A direct translation sounds unnatural in English",
        "The writer keeps rewriting because the tone feels uncertain",
        "A professional follow-up sounds either pushy or vague",
        "A short reply does not give the recipient enough context"
      ],
      "palette": {
        "background": "#F7F3EC",
        "accent": "#F05A3F",
        "ink": "#24211F"
      }
    },
    {
      "id": "fina",
      "name": "Fina",
      "active": true,
      "logo": "assets/fina/logo.png",
      "app_store_url": "https://apps.apple.com/us/app/fina-financial-companion/id6778169653",
      "positioning": "Forecast upcoming financial pressure and surface useful next steps before a money problem happens.",
      "audiences": [
        "People who want a clearer daily view of personal finances",
        "Households coordinating bills, budgets, and savings"
      ],
      "problems": [
        "Upcoming bills make a healthy balance misleading",
        "Small subscriptions quietly compress next month's budget",
        "A spending trend is noticed only after the category is over budget",
        "Shared household spending creates surprise cash-flow pressure",
        "Irregular expenses are treated like unexpected emergencies",
        "Saving goals compete with bills without a forward-looking view"
      ],
      "palette": {
        "background": "#F5F1E8",
        "accent": "#7A8F72",
        "ink": "#242621"
      },
      "claim_guardrail": "Never promise guaranteed outcomes or present carousel education as personalized financial, investment, tax, legal, or credit advice."
    }
  ]
}
```

Use this exact draft contract:

```json
{
  "draft_id": "2026-07-30-fina-01",
  "project_id": "fina",
  "format_id": "what-happens-next",
  "hook": "Your balance looks fine. Next Tuesday might not.",
  "caption": "A balance is a snapshot. Bills, subscriptions, and normal spending keep moving after you check it. A forward-looking view can help you notice pressure earlier and choose what to adjust. Find Fina through the link in our bio or on the App Store: https://apps.apple.com/us/app/fina-financial-companion/id6778169653",
  "slides": [
    {
      "kind": "hook",
      "headline": "Your balance looks fine.",
      "body": "Next Tuesday might not.",
      "illustration": "art-01.png",
      "alt_text": "An editorial illustration of a calm person looking at a balance while calendar pages and bills approach."
    },
    {
      "kind": "content",
      "headline": "Today",
      "body": "The account balance still includes money already spoken for.",
      "illustration": "art-02.png",
      "alt_text": "An editorial illustration of labeled envelopes sitting beside a bank balance."
    },
    {
      "kind": "content",
      "headline": "This weekend",
      "body": "Normal spending makes the available cushion smaller.",
      "illustration": "art-03.png",
      "alt_text": "An editorial illustration of everyday purchases reducing a small financial cushion."
    },
    {
      "kind": "content",
      "headline": "Next Tuesday",
      "body": "Two automatic payments arrive together.",
      "illustration": "art-04.png",
      "alt_text": "An editorial illustration of two bills landing on the same calendar date."
    },
    {
      "kind": "content",
      "headline": "The useful question",
      "body": "What will be left after what is already coming?",
      "illustration": "art-05.png",
      "alt_text": "An editorial illustration of a person looking ahead along a simple financial timeline."
    },
    {
      "kind": "cta",
      "headline": "See it coming with Fina.",
      "body": "Forecast upcoming pressure before it becomes a problem.",
      "alt_text": "Fina app logo with a message about forecasting upcoming financial pressure and a Download on the App Store badge."
    }
  ]
}
```

Use append-only JSON Lines events with this shape:

```json
{"draft_id":"2026-07-30-fina-01","project_id":"fina","format_id":"what-happens-next","event":"drafted","at":"2026-07-30T08:00:00-07:00"}
{"draft_id":"2026-07-30-fina-01","project_id":"fina","format_id":"what-happens-next","event":"approved","at":"2026-07-30T08:07:00-07:00"}
{"draft_id":"2026-07-30-fina-01","project_id":"fina","format_id":"what-happens-next","event":"publishing","at":"2026-07-30T08:07:02-07:00","container_id":"18000000000000000"}
{"draft_id":"2026-07-30-fina-01","project_id":"fina","format_id":"what-happens-next","event":"published","at":"2026-07-30T08:07:04-07:00","container_id":"18000000000000000","instagram_media_id":"18100000000000000"}
```

Allowed terminal/non-happy events are `revised`, `held`, `publish_failed`,
`cleanup_failed`, and `cleanup_completed`. A new revision receives a new draft
ID ending in `-02`, `-03`, and so on; the superseded draft receives `revised`.

---

### Task 1: Add Public Configuration, Approved Assets, and Draft Validation

**Files:**

- Modify: `.gitignore`
- Create: `social/requirements.txt`
- Create: `social/projects.json`
- Create: `social/history.jsonl`
- Create: `social/assets/fina/logo.png`
- Create: `social/assets/say-better/logo.png`
- Create: `social/assets/app-store-badge.svg`
- Create: `social/assets/app-store-badge.png`
- Create: `social/render.py`
- Test: `social/test_social.py`

- [ ] **Step 1: Add the failing configuration and draft validation tests**

Create `social/test_social.py` with `unittest`. Use `tempfile.TemporaryDirectory` and build fixture files inside the temporary directory so tests never depend on unpublished work.

Required test methods:

```python
class DraftValidationTests(unittest.TestCase):
    def test_accepts_valid_variable_length_draft(self):
        self.assertEqual(validate_draft(self.valid_draft(), self.project(), set()), [])

    def test_rejects_wrong_slide_order_and_count(self):
        draft = self.valid_draft()
        draft["slides"] = draft["slides"][:3]
        draft["slides"][0]["kind"] = "content"
        errors = validate_draft(draft, self.project(), set())
        self.assertIn("draft must contain 4 to 10 slides", errors)
        self.assertIn("first slide must be hook", errors)

    def test_rejects_product_mention_before_cta(self):
        draft = self.valid_draft()
        draft["slides"][1]["body"] = "Fina fixes this."
        self.assertIn("app name may appear only on the CTA slide", validate_draft(draft, self.project(), set()))

    def test_rejects_format_published_within_fourteen_days(self):
        errors = validate_draft(self.valid_draft(), self.project(), {"what-happens-next"})
        self.assertIn("format was published within the previous 14 days", errors)

    def test_requires_exact_app_store_url_in_caption(self):
        draft = self.valid_draft()
        draft["caption"] = "Read the carousel."
        self.assertIn("caption must contain the project's App Store URL", validate_draft(draft, self.project(), set()))
```

The fixture returned by `valid_draft()` must use the locked Fina draft contract above, reduced to four slides only where shorter setup makes the test clearer.

- [ ] **Step 2: Run the test and confirm the expected import failure**

Run:

```bash
python3 -m unittest social/test_social.py -v
```

Expected: `ModuleNotFoundError` because `social.render` does not exist yet.

- [ ] **Step 3: Add dependencies and public configuration**

Create `social/requirements.txt`:

```text
boto3>=1.34,<2
Pillow>=10.2,<12
```

Create `social/projects.json` from **Locked Public Configuration**. Create `social/history.jsonl` as an empty file.

Add these entries to `.gitignore`:

```gitignore
.venv/
.social-work/
social/*.local.json
social/*.local.env
```

Create the local environment and install the two runtime dependencies:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r social/requirements.txt
```

- [ ] **Step 4: Copy and verify the approved app logos**

Copy:

- `/home/cwsbr/personal/fina/apps/mobile/assets/fina-app-icon.png` to `social/assets/fina/logo.png`
- `/home/cwsbr/personal/say-better/app-store-listing/brand/app-icon-1024.png` to `social/assets/say-better/logo.png`

Verify both are square PNG files at least 512×512:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from PIL import Image

for path in (
    Path("social/assets/fina/logo.png"),
    Path("social/assets/say-better/logo.png"),
):
    with Image.open(path) as image:
        assert image.format == "PNG", path
        assert image.width == image.height >= 512, (path, image.size)
PY
```

- [ ] **Step 5: Download the Apple-provided badge and make a raster copy**

Download Apple's unmodified English black SVG:

```bash
curl -fsSL \
  https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg \
  -o social/assets/app-store-badge.svg
uvx --from cairosvg cairosvg \
  social/assets/app-store-badge.svg \
  -o social/assets/app-store-badge.png \
  --output-width 600
```

Verify the SVG title contains `Download_on_the_App_Store_Badge` and the PNG has transparency or an RGB/RGBA color mode. Do not redraw, recolor, crop, or add effects to the badge.

- [ ] **Step 6: Implement `render.py` configuration loading and validation**

Implement `load_json`, `read_events`, `recent_published_formats`, and
`validate_draft` with plain dictionaries; do not add dataclass/model layers.

Validation rules:

- `draft_id`, `project_id`, `format_id`, `hook`, `caption`, and `slides` are present and correctly typed.
- `format_id` is in configured formats and not in the prior 14 calendar days of `published` events.
- There are 4–10 slides.
- First slide is `hook`, last is `cta`, and every middle slide is `content`.
- Every slide has non-empty `headline`, `body`, and `alt_text`.
- Every non-CTA slide names an existing local PNG/JPEG illustration file.
- No non-CTA headline/body contains the project name, case-insensitively.
- The caption contains the project's exact App Store URL.
- The caption mentions the profile link using `link in bio`.
- Caption length is at most 2,200 characters.
- CTA has no `illustration` field and uses the configured app name.
- Reject paths that are absolute or contain `..`.

The CLI initially supports:

```bash
.venv/bin/python social/render.py validate .social-work/2026-07-30-fina-01/draft.json
```

It exits `0` with `draft valid` or exits `2` and prints only validation errors. It must not echo the caption, URLs, or full draft.

- [ ] **Step 7: Run validation tests**

Run:

```bash
.venv/bin/python -m unittest social/test_social.py -v
```

Expected: all `DraftValidationTests` pass.

- [ ] **Step 8: Commit Task 1**

```bash
git add .gitignore social
git commit -m "feat: add social draft contract"
```

---

### Task 2: Render Phone-Readable Carousel JPEGs

**Files:**

- Modify: `social/render.py`
- Modify: `social/test_social.py`

- [ ] **Step 1: Add failing renderer tests**

Add `RenderTests` covering one content slide and one CTA slide:

```python
class RenderTests(unittest.TestCase):
    def test_render_outputs_numbered_1080_by_1350_jpegs(self):
        outputs = render_draft(self.valid_draft(), self.project(), self.work_dir, self.output_dir)
        self.assertEqual([path.name for path in outputs], ["01.jpg", "02.jpg", "03.jpg", "04.jpg"])
        for path in outputs:
            with Image.open(path) as image:
                self.assertEqual(image.size, (1080, 1350))
                self.assertEqual(image.format, "JPEG")

    def test_cta_uses_logo_and_badge_without_illustration(self):
        output = render_slide(
            self.valid_draft()["slides"][-1],
            self.project(),
            4,
            4,
            self.work_dir,
            self.output_dir / "04.jpg",
        )
        self.assertEqual(output.name, "04.jpg")

    def test_rejects_copy_that_cannot_fit_safe_area(self):
        draft = self.valid_draft()
        draft["slides"][1]["headline"] = "word " * 80
        with self.assertRaisesRegex(ValueError, "text does not fit"):
            render_draft(draft, self.project(), self.work_dir, self.output_dir)
```

- [ ] **Step 2: Run the renderer tests and confirm they fail**

Run:

```bash
.venv/bin/python -m unittest social.test_social.RenderTests -v
```

Expected: import errors for `render_draft` and `render_slide`.

- [ ] **Step 3: Implement deterministic composition**

Add the constants `CANVAS`, `FONT`, and `SAFE`:

```python
CANVAS = (1080, 1350)
FONT = Path("/usr/share/fonts/truetype/ubuntu/UbuntuSans[wdth,wght].ttf")
SAFE = (88, 88, 992, 1262)
```

Implement `wrap_text`, `render_slide`, and `render_draft` using only Pillow:

- Convert every source image to RGB before compositing.
- Fit generated illustration into a fixed upper region without stretching.
- Put headline/body in a fixed lower safe region with at least 72 px outer margin.
- Use the configured background/accent/ink colors.
- Use the same layout, spacing, and line weights across one carousel.
- Render slide number as `1/6`, `2/6`, and so on.
- Use `draw.textbbox` to wrap and measure before drawing.
- Reject any headline/body whose final bounding box exceeds its safe region; never shrink below 42 px body or 64 px headline text.
- CTA uses the local app logo, one positioning sentence from the draft, and the unmodified App Store badge with at least one-quarter badge-height clear space.
- Save JPEG at quality 92, subsampling 0, with no EXIF metadata.

Extend the CLI:

```bash
.venv/bin/python social/render.py render \
  .social-work/2026-07-30-fina-01/draft.json \
  --output .social-work/2026-07-30-fina-01/rendered
```

On success:

1. Write ordered `01.jpg` through `10.jpg`.
2. Append a `drafted` event only if no event exists for that draft ID.
3. Print the output directory and file count, not the caption or illustration prompts.

- [ ] **Step 4: Run the complete local test**

Run:

```bash
.venv/bin/python -m unittest social/test_social.py -v
.venv/bin/python -m compileall -q social
```

Expected: all tests pass and compilation exits `0`.

- [ ] **Step 5: Render and visually inspect the locked Fina example**

Place the locked example JSON and five text-free test illustrations in `.social-work/2026-07-30-fina-01/`, run the renderer, and inspect all six JPEGs at phone size.

Acceptance:

- No cropped or overflowing text.
- No generated lettering inside illustrations.
- All content slides are useful without mentioning Fina.
- Only the final slide contains the Fina logo and App Store badge.
- Badge remains legible and visually subordinate to the CTA.

- [ ] **Step 6: Commit Task 2**

```bash
git add social/render.py social/test_social.py
git commit -m "feat: render Instagram carousels"
```

---

### Task 3: Add Approval State and Duplicate-Publish Protection

**Files:**

- Create: `social/publish.py`
- Modify: `social/test_social.py`

- [ ] **Step 1: Add failing state-machine tests**

Add `PublicationStateTests`:

```python
class PublicationStateTests(unittest.TestCase):
    def test_published_draft_cannot_publish_twice(self):
        append_event(self.history, {"draft_id": "d1", "event": "published", "instagram_media_id": "m1"})
        with self.assertRaisesRegex(RuntimeError, "already published"):
            assert_publishable("d1", read_events(self.history))

    def test_uncertain_publishing_state_blocks_automatic_retry(self):
        append_event(self.history, {"draft_id": "d1", "event": "publishing", "container_id": "c1"})
        with self.assertRaisesRegex(RuntimeError, "manual reconciliation required"):
            assert_publishable("d1", read_events(self.history))

    def test_revised_or_held_draft_cannot_publish(self):
        for event in ("revised", "held"):
            history = self.temp_dir / f"{event}.jsonl"
            append_event(history, {"draft_id": "d1", "event": event})
            with self.assertRaisesRegex(RuntimeError, "not publishable"):
                assert_publishable("d1", read_events(history))
```

- [ ] **Step 2: Run and confirm the import failure**

Run:

```bash
.venv/bin/python -m unittest social.test_social.PublicationStateTests -v
```

Expected: `ModuleNotFoundError` for `social.publish`.

- [ ] **Step 3: Implement append-only state handling**

Implement `append_event`, `latest_event`, and `assert_publishable`.

Rules:

- Open history with append mode and flush plus `os.fsync` after each event.
- Add an RFC 3339 America/Vancouver timestamp when `at` is absent.
- Only `drafted`, `approved`, and `publish_failed` may begin a safe publish attempt.
- `published` raises `already published`.
- `publishing` raises `manual reconciliation required`; never call Meta automatically from this state.
- `revised` and `held` raise `not publishable`.
- `cleanup_failed` with an `instagram_media_id` permits cleanup-only recovery, never another Meta publish.
- `cleanup_completed` and any earlier `published` event raise `already published`,
  even when they are not the latest event.
- The CLI accepts a concrete draft path and rendered directory:

```bash
.venv/bin/python social/publish.py \
  .social-work/2026-07-30-fina-01/draft.json \
  .social-work/2026-07-30-fina-01/rendered
```

Before any network call, it reruns draft validation, verifies ordered JPEG count and dimensions, checks state, and appends `approved`.

The CLI also accepts cleanup-only recovery:

```bash
.venv/bin/python social/publish.py \
  --cleanup-only 2026-07-30-fina-01
```

This path is allowed only when the latest event is `cleanup_failed`. It removes
and verifies the R2 prefix, appends `cleanup_completed`, and never constructs an
Instagram client.

- [ ] **Step 4: Run state tests**

Run:

```bash
.venv/bin/python -m unittest social.test_social.PublicationStateTests -v
```

Expected: all state-machine tests pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add social/publish.py social/test_social.py
git commit -m "feat: guard social publication state"
```

---

### Task 4: Stage in R2, Publish One Carousel, and Always Clean Up

**Files:**

- Modify: `social/publish.py`
- Modify: `social/test_social.py`

- [ ] **Step 1: Add failing provider-flow tests with local fakes**

Add `PublishFlowTests`. Use one fake R2 client and one fake Instagram client; do not make network requests.

Required cases:

```python
class PublishFlowTests(unittest.TestCase):
    def test_success_publishes_once_and_cleans_prefix(self):
        media_id = publish(self.draft, self.files, self.r2, self.instagram, self.history)
        self.assertEqual(media_id, "media-1")
        self.assertEqual(self.instagram.publish_calls, 1)
        self.assertEqual(self.r2.remaining_keys, [])

    def test_child_failure_skips_parent_and_cleans_prefix(self):
        self.instagram.fail_at = "child"
        with self.assertRaises(RuntimeError):
            publish(self.draft, self.files, self.r2, self.instagram, self.history)
        self.assertEqual(self.instagram.parent_calls, 0)
        self.assertEqual(self.instagram.publish_calls, 0)
        self.assertEqual(self.r2.remaining_keys, [])

    def test_parent_failure_cleans_prefix(self):
        self.instagram.fail_at = "parent"
        with self.assertRaises(RuntimeError):
            publish(self.draft, self.files, self.r2, self.instagram, self.history)
        self.assertEqual(self.instagram.publish_calls, 0)
        self.assertEqual(self.r2.remaining_keys, [])

    def test_publish_failure_leaves_uncertain_state_and_cleans_prefix(self):
        self.instagram.fail_at = "publish"
        with self.assertRaises(RuntimeError):
            publish(self.draft, self.files, self.r2, self.instagram, self.history)
        self.assertEqual(latest_event(self.draft["draft_id"], read_events(self.history))["event"], "publishing")
        self.assertEqual(self.r2.remaining_keys, [])

    def test_cleanup_failure_is_recorded_after_success(self):
        self.r2.fail_cleanup = True
        with self.assertRaisesRegex(RuntimeError, "published but staging cleanup failed"):
            publish(self.draft, self.files, self.r2, self.instagram, self.history)
        events = read_events(self.history)
        self.assertTrue(any(event["event"] == "published" for event in events))
        self.assertEqual(events[-1]["event"], "cleanup_failed")
        self.assertEqual(self.instagram.publish_calls, 1)

    def test_cleanup_only_never_calls_instagram(self):
        append_event(self.history, cleanup_failed_event(self.draft, "media-1"))
        cleanup_only(self.draft["draft_id"], self.r2, self.history)
        self.assertEqual(self.instagram.publish_calls, 0)
        self.assertEqual(read_events(self.history)[-1]["event"], "cleanup_completed")
```

- [ ] **Step 2: Run and confirm provider-flow tests fail**

Run:

```bash
.venv/bin/python -m unittest social.test_social.PublishFlowTests -v
```

Expected: import or attribute errors for the unimplemented clients and `publish`.

- [ ] **Step 3: Implement the R2 client**

Use boto3 directly:

```python
def make_r2_client(env: dict[str, str]):
    endpoint = f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
```

Required environment variables:

```text
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET
IG_USER_ID
IG_ACCESS_TOKEN
META_API_VERSION
```

Require `R2_BUCKET` to equal `building-intent-social`. Reject missing/empty values before upload.

Implement `upload_images`, `presign_images`, and `cleanup_prefix`.

Rules:

- Keys are `draft_id/01.jpg`, `draft_id/02.jpg`, and so on.
- Upload with `ContentType="image/jpeg"` and `CacheControl="no-store"`.
- Generate GET URLs with `ExpiresIn=3600`.
- Never print or store returned URLs.
- Cleanup lists the prefix, deletes all returned keys in batches, lists again, and raises if anything remains.
- Pagination must be handled for listing even though V1 has at most ten images.

- [ ] **Step 4: Implement the Instagram client with `urllib`**

Use `urllib.parse.urlencode`, `urllib.request.Request`, and `urllib.request.urlopen`; do not add `requests`.

Endpoints:

```text
POST https://graph.instagram.com/v23.0/{IG_USER_ID}/media
GET  https://graph.instagram.com/v23.0/{CONTAINER_ID}?fields=status_code
POST https://graph.instagram.com/v23.0/{IG_USER_ID}/media_publish
```

Use `META_API_VERSION` in place of `v23.0`, with `v23.0` documented as the verified initial value.

Implement an `Instagram` class with four methods:

- `create_child(image_url) -> str`
- `wait_until_ready(container_id) -> None`
- `create_carousel(child_ids, caption) -> str`
- `publish_carousel(container_id) -> str`

Flow:

1. Create each child with `image_url` and `is_carousel_item=true`.
2. Poll `status_code` every two seconds for up to five minutes.
3. Accept only `FINISHED`; fail on `ERROR`, `EXPIRED`, or timeout.
4. Create parent with `media_type=CAROUSEL`, JSON-encoded `children`, and approved caption.
5. Poll parent until `FINISHED`.
6. Append `publishing` with the parent container ID and flush it **before** `/media_publish`.
7. Call `/media_publish` once.
8. Require a non-empty media ID, append `published`, and only then report success.

Send the token only in the `Authorization` header, using the `Bearer` scheme.
Exceptions may include HTTP status and a short stable reason, but must not
include request headers, form data, response bodies, captions, tokens, or
presigned URLs.

- [ ] **Step 5: Implement one orchestration function with mandatory cleanup**

Use this control shape:

```python
def publish(draft, files, r2, instagram, history):
    uploaded = False
    media_id = None
    try:
        keys = r2.upload(draft["draft_id"], files)
        uploaded = True
        urls = r2.presign(keys)
        child_ids = [instagram.create_child(url) for url in urls]
        for child_id in child_ids:
            instagram.wait_until_ready(child_id)
        parent_id = instagram.create_carousel(child_ids, draft["caption"])
        instagram.wait_until_ready(parent_id)
        append_event(history, publishing_event(draft, parent_id))
        media_id = instagram.publish_carousel(parent_id)
        append_event(history, published_event(draft, parent_id, media_id))
        return media_id
    finally:
        if uploaded:
            cleanup_and_record_failure(r2, draft, history, media_id)
```

Preserve the original publication exception if cleanup also fails, while appending `cleanup_failed`. If Instagram already returned a media ID, cleanup failure must produce the explicit result `published but staging cleanup failed` and expose only that media ID.

- [ ] **Step 6: Run all tests and a no-network CLI check**

Run:

```bash
.venv/bin/python -m unittest social/test_social.py -v
.venv/bin/python -m compileall -q social
env -u IG_ACCESS_TOKEN -u R2_SECRET_ACCESS_KEY \
  .venv/bin/python social/publish.py \
  .social-work/2026-07-30-fina-01/draft.json \
  .social-work/2026-07-30-fina-01/rendered
```

Expected:

- All tests pass.
- Compilation exits `0`.
- CLI exits before network access and reports the names of missing variables only.

- [ ] **Step 7: Commit Task 4**

```bash
git add social/publish.py social/test_social.py
git commit -m "feat: publish and clean Instagram carousels"
```

---

### Task 5: Define the Codex Creative/Approval Loop and Complete External Setup

**Files:**

- Create: `social/PROMPT.md`
- Create: `social/README.md`
- Modify: `README.md`
- Verify: `social/projects.json`
- Verify: `social/history.jsonl`

- [ ] **Step 1: Write `social/PROMPT.md` as an executable operating contract**

It must instruct each 8:00 AM automation run to:

1. Read `social/projects.json` and `social/history.jsonl`.
2. Stop and report any unresolved `cleanup_failed` or `publishing` event before drafting.
3. Choose the active project with the oldest last `published` event; break the initial tie by config order, so Say Better is first and Fina is second.
4. Exclude formats published in the prior 14 days.
5. Pick one listed audience problem, then choose a format whose natural slide count is 4–10.
6. Write English-only copy where every non-CTA slide is useful without the app.
7. Apply Fina's claim guardrail.
8. Generate one text-free editorial illustration per non-CTA slide with the Codex image model. Use a coherent palette and reserve safe copy space. Prohibit logos, UI, financial account data, and lettering in generated art.
9. Save the draft and source illustrations only under `.social-work/{draft_id}/`.
10. Run `render.py render`.
11. Inspect every rendered slide before presenting it.
12. Append `drafted` through the renderer, then send ordered images, caption, alt text, project, format, and draft ID into this task.
13. Wait. Do not upload to R2.

Approval behavior:

- Exact user message `승인` publishes the newest non-terminal draft by running `publish.py`.
- Revision feedback appends `revised`, creates the next revision ID, regenerates, and presents it again.
- `보류` appends `held`.
- If more than one draft is awaiting a decision, require the displayed draft ID with approval.
- After publication, report the Instagram media ID and confirm the R2 prefix is empty.
- Every caption must include the exact App Store URL and the words `link in bio`.

- [ ] **Step 2: Write `social/README.md` for a first-time non-technical setup**

Document only these four sections:

1. **Install locally**
   - Create `.venv` in the repository.
   - Install `social/requirements.txt`.
   - Confirm tests pass.
2. **Connect Instagram**
   - Create/convert the Instagram account to Professional.
   - Create a Meta developer app.
   - Select Instagram API with Instagram Login.
   - Request `instagram_business_basic` and `instagram_business_content_publish`.
   - Authorize only the owned professional account.
   - Obtain the Instagram professional user ID and long-lived access token.
   - Record token expiry and renewal procedure.
3. **Create private R2 staging**
   - Create private bucket `building-intent-social`.
   - Disable public development URL and custom domains.
   - Create an object read/write token scoped only to that bucket.
   - Add a lifecycle rule deleting objects after one day.
4. **Store secrets outside Git**
   - Use Codex-managed automation secrets when available.
   - For local testing, use a permission-`600` file at `/home/cwsbr/.config/portfolio-social/credentials.json`.
   - Read that JSON as data and export values only for the current process; never `source` it.
   - Include key names only, never example secret values.

Add a warning that `META_API_VERSION` starts at `v23.0`, must be checked against Meta's currently supported versions during setup, and can be changed without code edits.

- [ ] **Step 3: Link the social system from the portfolio README**

Add one sentence under the project list:

```markdown
The repository also contains the public-safe [Instagram promotion workflow](social/README.md) used to draft and publish rotating educational carousels for these products.
```

- [ ] **Step 4: Run the complete repository verification**

Run:

```bash
.venv/bin/python -m unittest social/test_social.py -v
.venv/bin/python -m compileall -q social
git grep -nE \
  '(IG_ACCESS_TOKEN=.+|R2_SECRET_ACCESS_KEY=.+|R2_ACCESS_KEY_ID=.+|X-Amz-Signature=|Bearer [A-Za-z0-9])' \
  -- . ':!docs/superpowers/plans'
git status --short
```

Expected:

- Tests and compilation pass.
- Secret scan has no matches.
- Only intended Task 5 files are modified.

- [ ] **Step 5: Commit Task 5**

```bash
git add README.md social/README.md social/PROMPT.md
git commit -m "docs: add social automation runbook"
```

- [ ] **Step 6: Complete the external setup checkpoint with the user**

Do not fabricate credentials or silently broaden permissions. Guide the user through Meta and Cloudflare dashboards, then verify:

- Instagram account is Professional.
- Only `instagram_business_basic` and `instagram_business_content_publish` are authorized.
- Both App Store URLs resolve:
  - `https://apps.apple.com/us/app/say-better/id6784318555`
  - `https://apps.apple.com/us/app/fina-financial-companion/id6778169653`
- R2 bucket is private and has the one-day lifecycle rule.
- Credentials file is outside the repository and mode `600`.
- `publish.py` can validate credentials without printing their values.

- [ ] **Step 7: Create the recurring Codex automation**

Create one recurring automation attached to this task:

- Name: `Daily Instagram carousel draft`
- Time: `08:00`
- Timezone: `America/Vancouver`
- Frequency: daily
- Prompt: follow `social/PROMPT.md` exactly and stop after presenting the draft for approval.

Do not create a second schedule until project volume requires more than one daily post. When that happens, add explicit slots to `projects.json` and expand the format library enough to preserve the 14-day no-repeat rule at the new posting frequency.

- [ ] **Step 8: Run one explicitly approved end-to-end test**

Generate a fresh Say Better draft, show all slides and caption in this task, and wait for explicit `승인`.

After approval verify:

1. Exactly one Instagram carousel exists with the approved slide order and caption.
2. The returned media ID is recorded once in `social/history.jsonl`.
3. The R2 draft prefix lists zero objects.
4. A second invocation for the same draft exits with `already published` before any upload.
5. No unpublished draft or secret appears in `git status` or Git history.

- [ ] **Step 9: Final review and commit any test-history record**

Publication history is intentionally public-safe. If the end-to-end test adds only non-secret event lines, commit them:

```bash
git add social/history.jsonl
git commit -m "chore: record Instagram publishing smoke test"
```

If the test did not publish, do not create an empty commit.

---

## Final Acceptance Checklist

- [ ] Daily 8:00 AM America/Vancouver automation creates one draft and does not auto-publish.
- [ ] Say Better and Fina rotate by least-recent publication.
- [ ] English-only carousel structure and count vary with the hook.
- [ ] A published format cannot recur within 14 days.
- [ ] Non-CTA slides contain no app promotion.
- [ ] CTA uses the confirmed logo and unmodified official App Store badge.
- [ ] Caption contains the correct live App Store URL.
- [ ] `승인` publishes the newest pending draft immediately.
- [ ] Revision feedback invalidates the old draft before regeneration.
- [ ] Duplicate and uncertain publication states block automatic retry.
- [ ] R2 objects are deleted and the prefix is verified empty after success and failure.
- [ ] One-day R2 lifecycle remains enabled as crash protection.
- [ ] Secrets and unpublished drafts are absent from Git.
