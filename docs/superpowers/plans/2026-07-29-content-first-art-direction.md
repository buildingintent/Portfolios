# Content-First Art Direction Implementation Plan

**Post-review note:** The final fix wave moved all pre-publication state and
scene data to ignored `.social-work/history.jsonl`, left tracked
`social/history.jsonl` published-only, and bound approvals to content,
render-ready draft, and ordered JPEG fingerprints. `social/README.md` is the
current operating contract.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require slide-by-slide content approval before image generation, then render each approved carousel as unique full-bleed art with scene-specific text placement before a separate final publication approval.

**Architecture:** Keep the existing JSONL helpers, Pillow renderer, R2 staging,
and Instagram publisher. Runtime state lives in ignored
`.social-work/history.jsonl`; tracked `social/history.jsonl` is published-only.
Split validation into content-only and render-ready phases, add explicit
content approval and rendered events, and replace the fixed illustration-card
renderer with full-bleed images plus per-slide text regions. The Codex prompt
remains the creative director; Python validates state and renders exact
approved copy.

**Tech Stack:** Python 3 standard library, Pillow, unittest, existing boto3 publisher, Codex built-in image generation

## Global Constraints

- Generate English content only.
- Present exact copy for every numbered slide and the Instagram caption before generating any image.
- Require exact `콘텐츠 승인` before image generation and exact `승인` before publication.
- Keep the final CTA slide logo-led and free of app screenshots.
- Fill every non-CTA slide at 1080×1350 with a full-bleed illustration.
- Art-direct every carousel and slide individually; do not rotate fixed visual templates.
- Keep one coherent illustration style within a carousel while varying scene composition.
- Render exact text deterministically; generated art must not contain final text, numbers, logos, app UI, bank screens, or account data.
- Keep `.env`, unpublished drafts, scene plans, rendered images, tokens, and presigned URLs out of Git.
- Do not create R2 objects or Instagram containers before final approval.
- Delete and verify the R2 draft prefix after every publication attempt.
- Add no dependency and no custom web UI.

---

### Task 1: Add the content approval gate

**Files:**
- Modify: `social/render.py:102-227,490-575`
- Modify: `social/publish.py:39-64,301-325,327-334,460-520`
- Test: `social/test_social.py:1-235,349-500`

**Interfaces:**
- Produces: `validate_content(draft: dict, project: dict, blocked_formats: set[str]) -> list[str]`
- Produces: `validate_content_file(draft_path: Path, config_path: Path = CONFIG_PATH, history_path: Path = HISTORY_PATH) -> list[str]`
- Produces in `social/render.py`: `latest_event(draft_id: str, events: list[dict]) -> dict | None`
- Produces: `record_content_state(draft: dict, state: str, history: Path) -> None`
- Produces: `assert_renderable(draft_id: str, events: list[dict]) -> None`
- Produces: `mark_rendered(draft: dict, history: Path) -> None`
- Changes: `validate_draft` validates render-only fields after calling `validate_content`
- Changes: `approve` accepts only the latest `rendered` event and records `approved` once
- Changes: `assert_publishable` accepts only `approved` and `publish_failed`
- CLI: `social/render.py record-content <draft.json>`
- CLI: `social/render.py approve-content <draft.json>`

- [ ] **Step 1: Write failing content-validation tests**

Add a helper that strips render-only fields and prove that exact slide copy is
valid before illustrations exist:

```python
from social.render import (
    assert_renderable,
    mark_rendered,
    record_content_state,
    validate_content,
)


def content_only_draft():
    draft = DraftValidationTests.valid_draft()
    draft.pop("art_direction", None)
    for slide in draft["slides"]:
        slide.pop("alt_text", None)
        slide.pop("illustration", None)
        slide.pop("scene", None)
        slide.pop("text_layout", None)
    return draft


def test_accepts_content_before_art_exists(self):
    self.assertEqual(
        validate_content(
            content_only_draft(),
            self.project(),
            set(),
        ),
        [],
    )


def test_render_ready_validation_still_requires_art_fields(self):
    errors = validate_draft(
        content_only_draft(),
        self.project(),
        set(),
    )
    self.assertIn(
        "slide 1 alt_text must be a non-empty string",
        errors,
    )
    self.assertIn(
        "illustration paths must stay inside the draft directory",
        errors,
    )
```

- [ ] **Step 2: Run the new validation tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  social.test_social.DraftValidationTests.test_accepts_content_before_art_exists \
  social.test_social.DraftValidationTests.test_render_ready_validation_still_requires_art_fields \
  -v
```

Expected: import or attribute failure because `validate_content` does not
exist.

- [ ] **Step 3: Split content and render-ready validation**

Move the existing project, format, caption, slide ordering, headline/body,
product-mention, and CTA checks into `validate_content`. Keep `alt_text`,
`illustration`, `text_layout`, and illustration-file checks in
`validate_draft`/`validate_file`.

Rename the current `validate_draft` implementation to `validate_content` and
change its per-slide required fields from
`("headline", "body", "alt_text")` to `("headline", "body")`. Remove the
non-CTA illustration-path check and the CTA illustration prohibition from that
renamed function. Then add this render-ready wrapper immediately below it:

```python
def validate_draft(
    draft: dict,
    project: dict,
    blocked_formats: set[str],
) -> list[str]:
    errors = validate_content(draft, project, blocked_formats)
    for index, slide in enumerate(draft.get("slides", []), start=1):
        if not isinstance(slide, dict):
            continue
        if not _non_empty_string(slide.get("alt_text")):
            errors.append(
                f"slide {index} alt_text must be a non-empty string"
            )
        if slide.get("kind") != "cta":
            if not _safe_illustration_path(slide.get("illustration")):
                errors.append(
                    "illustration paths must stay inside the draft directory"
                )
        elif "illustration" in slide:
            errors.append("CTA slide must not include an illustration")
    return list(dict.fromkeys(errors))
```

- [ ] **Step 4: Run validation tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest \
  social.test_social.DraftValidationTests -v
```

Expected: all `DraftValidationTests` pass.

- [ ] **Step 5: Write failing approval-transition tests**

Add real JSONL state tests:

```python
def test_content_must_be_approved_before_rendering(self):
    draft = {
        "draft_id": "d1",
        "project_id": "fina",
        "format_id": "what-happens-next",
    }
    record_content_state(draft, "content_drafted", self.history)

    with self.assertRaisesRegex(
        RuntimeError,
        "content approval required",
    ):
        assert_renderable("d1", read_events(self.history))

    record_content_state(draft, "content_approved", self.history)
    self.assertIsNone(
        assert_renderable("d1", read_events(self.history))
    )


def test_final_approval_requires_rendered_event(self):
    draft = {
        "draft_id": "d1",
        "project_id": "fina",
        "format_id": "what-happens-next",
    }
    record_content_state(draft, "content_drafted", self.history)
    record_content_state(draft, "content_approved", self.history)

    with self.assertRaisesRegex(
        RuntimeError,
        "rendered carousel required",
    ):
        approve(draft, self.history)

    mark_rendered(draft, self.history)
    approve(draft, self.history)
    approve(draft, self.history)
    self.assertEqual(
        [event["event"] for event in read_events(self.history)],
        [
            "content_drafted",
            "content_approved",
            "rendered",
            "approved",
        ],
    )


def test_publishable_states_exclude_preapproval_events(self):
    for state in (
        "content_drafted",
        "content_approved",
        "rendered",
    ):
        history = self.root / f"{state}.jsonl"
        append_event(
            history,
            {"draft_id": "d1", "event": state},
        )
        with self.assertRaisesRegex(
            RuntimeError,
            "not publishable",
        ):
            assert_publishable("d1", read_events(history))


def test_revision_and_hold_accept_every_pending_approval_stage(self):
    for state in (
        "drafted",
        "content_drafted",
        "content_approved",
        "rendered",
        "approved",
    ):
        history = self.root / f"terminal-{state}.jsonl"
        draft = {
            "draft_id": f"d-{state}",
            "project_id": "fina",
            "format_id": "what-happens-next",
        }
        append_event(history, {**draft, "event": state})
        record_terminal(draft, "revised", history)
        self.assertEqual(
            latest_event(draft["draft_id"], read_events(history))[
                "event"
            ],
            "revised",
        )
```

- [ ] **Step 6: Run transition tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  social.test_social.PublicationStateTests.test_content_must_be_approved_before_rendering \
  social.test_social.PublicationStateTests.test_final_approval_requires_rendered_event \
  social.test_social.PublicationStateTests.test_publishable_states_exclude_preapproval_events \
  social.test_social.PublicationStateTests.test_revision_and_hold_accept_every_pending_approval_stage \
  -v
```

Expected: import or transition failures because the new states are not
implemented.

- [ ] **Step 7: Implement the minimal state transitions**

Use the existing JSONL helpers and one latest-event lookup; do not add a
state-machine class.

```python
def latest_event(draft_id: str, events: list[dict]) -> dict | None:
    for event in reversed(events):
        if event.get("draft_id") == draft_id:
            return event
    return None


def _draft_event(draft: dict, event: str) -> dict:
    return {
        "draft_id": draft["draft_id"],
        "project_id": draft["project_id"],
        "format_id": draft["format_id"],
        "event": event,
    }


def record_content_state(
    draft: dict,
    state: str,
    history: Path,
) -> None:
    if state not in {"content_drafted", "content_approved"}:
        raise ValueError("invalid content state")
    latest = latest_event(draft["draft_id"], read_events(history))
    current = latest.get("event") if latest else None
    expected = (
        None if state == "content_drafted" else "content_drafted"
    )
    if current == state:
        return
    if current != expected:
        raise RuntimeError("invalid content state transition")
    append_event(history, _draft_event(draft, state))


def assert_renderable(draft_id: str, events: list[dict]) -> None:
    latest = latest_event(draft_id, events)
    if latest is None or latest.get("event") != "content_approved":
        raise RuntimeError("content approval required")


def mark_rendered(draft: dict, history: Path) -> None:
    events = read_events(history)
    latest = latest_event(draft["draft_id"], events)
    if latest and latest.get("event") == "rendered":
        return
    assert_renderable(draft["draft_id"], events)
    append_event(history, _draft_event(draft, "rendered"))
```

Place these functions in `social/render.py`. Remove the duplicate
`latest_event` definition from `social/publish.py` and import it from
`social.render` beside `append_event`, `load_json`, and `read_events`.

Change `approve` so `rendered` becomes `approved`; repeated `approved` and
the retry state `publish_failed` are no-ops. Every other latest state raises
`"rendered carousel required"`. Restrict `assert_publishable` safe states to
`{"approved", "publish_failed"}` and call it in `publish` immediately after
`approve`. Keep the existing protections for `publishing`, `published`,
`cleanup_failed`, and `cleanup_completed`.

Change `record_terminal` to accept `revised` or `held` only when the latest
event is one of:

```python
{
    "drafted",
    "content_drafted",
    "content_approved",
    "rendered",
    "approved",
}
```

This preserves the rejected pre-migration draft while allowing feedback at
either new approval gate. Update publication-flow test setup events from
`drafted` to `rendered`; `publish` records `approved` before provider
calls.

- [ ] **Step 8: Add content-state CLI commands**

In `social/render.py`, add:

```python
record_parser = subparsers.add_parser("record-content")
record_parser.add_argument("draft", type=Path)
approve_parser = subparsers.add_parser("approve-content")
approve_parser.add_argument("draft", type=Path)
```

`record-content` must call content-only validation and then record
`content_drafted`. `approve-content` must re-run content validation before
recording `content_approved`. Neither command may inspect or create image
files.

Add this file-level content validator and reuse it from both commands:

```python
def validate_content_file(
    draft_path: Path,
    config_path: Path = CONFIG_PATH,
    history_path: Path = HISTORY_PATH,
) -> list[str]:
    config = load_json(config_path)
    draft = load_json(draft_path)
    project = _project(config, draft.get("project_id", ""))
    errors = validate_content(
        draft,
        project,
        recent_published_formats(
            read_events(history_path),
            datetime.now(TIMEZONE),
        ),
    )
    if draft.get("format_id") not in config.get("formats", []):
        errors.append("format_id is not configured")
    return list(dict.fromkeys(errors))
```

Dispatch the new commands before the existing `validate` and `render`
branches:

```python
if args.command in {"record-content", "approve-content"}:
    errors = validate_content_file(args.draft)
    if errors:
        for error in errors:
            print(error)
        return 2
    draft = load_json(args.draft)
    state = (
        "content_drafted"
        if args.command == "record-content"
        else "content_approved"
    )
    record_content_state(draft, state, HISTORY_PATH)
    print(f"recorded {state} for {draft['draft_id']}")
    return 0
```

- [ ] **Step 9: Run transition tests and the full suite**

Run:

```bash
.venv/bin/python -m unittest social/test_social.py -v
```

Expected: all tests pass with no warnings.

- [ ] **Step 10: Commit the content gate**

```bash
git add social/render.py social/publish.py social/test_social.py
git commit -m "feat: require content approval before rendering"
```

---

### Task 2: Render full-bleed art with per-slide text regions

**Files:**
- Modify: `social/render.py:91-99,180-227,240-365,416-458`
- Modify: `social/test_social.py:40-348`

**Interfaces:**
- Consumes: latest event must be `content_approved` before `render_file`
- Consumes: render-ready draft `art_direction: str`
- Consumes: non-CTA slide `illustration: str`
- Consumes: non-CTA slide `scene: str`
- Consumes: non-CTA slide `text_layout: dict[str, TextRegion]`
- Produces: full-bleed 1080×1350 JPEGs
- `TextRegion`: `{"box": [x1, y1, x2, y2], "font_size": int, "align": "left"|"center"|"right", "color": "#RRGGBB", "rotation": int}`

- [ ] **Step 1: Extend the render fixture with explicit text regions**

Give every non-CTA slide two independently placed regions:

```python
def text_layout(headline_y=80, body_y=350):
    return {
        "headline": {
            "box": [64, headline_y, 1016, headline_y + 230],
            "font_size": 78,
            "align": "left",
            "color": "#171512",
            "rotation": 0,
        },
        "body": {
            "box": [64, body_y, 900, body_y + 180],
            "font_size": 44,
            "align": "left",
            "color": "#171512",
            "rotation": 0,
        },
    }
```

Update `DraftValidationTests.valid_draft()` so each hook/content slide contains
`"scene": "A concise description of the unique visual composition"` and
`"text_layout": text_layout()`. Add a top-level
`"art_direction": "Hand-inked editorial illustration with warm paper texture"`.

- [ ] **Step 2: Write failing layout validation tests**

```python
def test_rejects_text_regions_outside_canvas(self):
    draft = self.valid_draft()
    draft["slides"][0]["text_layout"]["headline"]["box"] = [
        -1, 80, 800, 260,
    ]

    self.assertIn(
        "text region must stay inside the canvas",
        validate_draft(draft, self.project(), set()),
    )


def test_rejects_overlapping_headline_and_body_regions(self):
    draft = self.valid_draft()
    draft["slides"][0]["text_layout"]["body"]["box"] = [
        64, 100, 900, 260,
    ]

    self.assertIn(
        "headline and body text regions must not overlap",
        validate_draft(draft, self.project(), set()),
    )


def test_rejects_unsupported_text_region_values(self):
    draft = self.valid_draft()
    region = draft["slides"][0]["text_layout"]["headline"]
    region["align"] = "diagonal"
    region["font_size"] = 200
    region["color"] = "black"
    region["rotation"] = 45

    errors = validate_draft(draft, self.project(), set())
    self.assertIn("text alignment is invalid", errors)
    self.assertIn("text font size is invalid", errors)
    self.assertIn("text color must be #RRGGBB", errors)
    self.assertIn("text rotation must be between -12 and 12", errors)


def test_render_ready_draft_requires_art_direction_and_scene(self):
    draft = self.valid_draft()
    draft.pop("art_direction")
    draft["slides"][0].pop("scene")

    errors = validate_draft(draft, self.project(), set())
    self.assertIn(
        "art_direction must be a non-empty string",
        errors,
    )
    self.assertIn(
        "slide 1 scene must be a non-empty string",
        errors,
    )
```

- [ ] **Step 3: Run layout validation tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  social.test_social.DraftValidationTests.test_rejects_text_regions_outside_canvas \
  social.test_social.DraftValidationTests.test_rejects_overlapping_headline_and_body_regions \
  social.test_social.DraftValidationTests.test_rejects_unsupported_text_region_values \
  social.test_social.DraftValidationTests.test_render_ready_draft_requires_art_direction_and_scene \
  -v
```

Expected: assertions fail because `text_layout` is not validated.

- [ ] **Step 4: Implement compact text-region validation**

Add `_validate_text_region(region: Any) -> list[str]` and a rectangle-overlap
check. Enforce:

- integer box coordinates with `0 <= x1 < x2 <= 1080` and
  `0 <= y1 < y2 <= 1350`
- headline font size 52–104 and body font size 30–60
- alignment in `left`, `center`, `right`
- color matching `#[0-9A-Fa-f]{6}`
- integer rotation from -12 through 12
- non-overlapping headline and body boxes

Require `text_layout.headline` and `text_layout.body` on every non-CTA slide.
Do not require them on the CTA. Require one non-empty top-level
`art_direction` and one non-empty `scene` on every non-CTA slide during
render-ready validation only.

Use these helpers and append their returned errors from `validate_draft`:

```python
def _text_region_errors(
    region: Any,
    minimum_font: int,
    maximum_font: int,
) -> list[str]:
    if not isinstance(region, dict):
        return ["text region must be an object"]
    errors = []
    box = region.get("box")
    if (
        not isinstance(box, list)
        or len(box) != 4
        or any(type(value) is not int for value in box)
        or not (
            0 <= box[0] < box[2] <= CANVAS[0]
            and 0 <= box[1] < box[3] <= CANVAS[1]
        )
    ):
        errors.append("text region must stay inside the canvas")
    font_size = region.get("font_size")
    if (
        type(font_size) is not int
        or not minimum_font <= font_size <= maximum_font
    ):
        errors.append("text font size is invalid")
    if region.get("align") not in {"left", "center", "right"}:
        errors.append("text alignment is invalid")
    if not (
        isinstance(region.get("color"), str)
        and re.fullmatch(r"#[0-9A-Fa-f]{6}", region["color"])
    ):
        errors.append("text color must be #RRGGBB")
    rotation = region.get("rotation")
    if type(rotation) is not int or not -12 <= rotation <= 12:
        errors.append("text rotation must be between -12 and 12")
    return errors


def _boxes_overlap(first: list[int], second: list[int]) -> bool:
    return not (
        first[2] <= second[0]
        or second[2] <= first[0]
        or first[3] <= second[1]
        or second[3] <= first[1]
    )
```

After both regions pass box validation, call `_boxes_overlap` and append
`"headline and body text regions must not overlap"` when it returns true.

- [ ] **Step 5: Run layout validation tests and verify GREEN**

Run:

```bash
.venv/bin/python -m unittest \
  social.test_social.DraftValidationTests -v
```

Expected: all draft validation tests pass.

- [ ] **Step 6: Write failing full-bleed and variable-placement tests**

Use solid-color source art so the assertion is deterministic:

```python
def test_content_art_is_full_bleed(self):
    slide = self.valid_draft()["slides"][0]
    output = render_slide(
        slide,
        self.project(),
        1,
        4,
        self.work_dir,
        self.output_dir / "01.jpg",
    )

    with Image.open(output) as image:
        for point in ((0, 0), (1079, 0), (0, 1349), (1079, 1349)):
            pixel = image.getpixel(point)
            self.assertLess(
                sum(abs(channel - expected) for channel, expected in zip(
                    pixel,
                    (215, 231, 208),
                )),
                30,
            )


def test_text_moves_with_scene_layout(self):
    first = self.valid_draft()["slides"][0]
    second = copy.deepcopy(first)
    second["text_layout"] = text_layout(
        headline_y=720,
        body_y=980,
    )

    first_path = render_slide(
        first,
        self.project(),
        1,
        4,
        self.work_dir,
        self.output_dir / "first.jpg",
    )
    second_path = render_slide(
        second,
        self.project(),
        1,
        4,
        self.work_dir,
        self.output_dir / "second.jpg",
    )

    with Image.open(first_path) as a, Image.open(second_path) as b:
        self.assertNotEqual(a.tobytes(), b.tobytes())
```

- [ ] **Step 7: Run render tests and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  social.test_social.RenderTests.test_content_art_is_full_bleed \
  social.test_social.RenderTests.test_text_moves_with_scene_layout \
  -v
```

Expected: full-bleed corner assertion fails because the current renderer places
art inside a rounded card.

- [ ] **Step 8: Replace the fixed card renderer**

Replace `_place_illustration` with a full-canvas fit:

```python
def _place_full_bleed(canvas: Image.Image, source: Path) -> None:
    with Image.open(source) as opened:
        image = ImageOps.fit(
            opened.convert("RGB"),
            CANVAS,
            Image.Resampling.LANCZOS,
        )
    canvas.paste(image, (0, 0))
```

Add `_draw_text_region(canvas, text, region, bold)`. It must:

1. wrap text to the region width;
2. reject content taller than the region;
3. honor left/center/right alignment;
4. draw onto a transparent layer;
5. rotate the layer around its center only when `rotation != 0`;
6. reject a rotated result that leaves the canvas;
7. composite onto the full-bleed illustration.

Use this implementation:

```python
def _draw_text_region(
    canvas: Image.Image,
    text: str,
    region: dict,
    bold: bool,
) -> None:
    x1, y1, x2, y2 = region["box"]
    width = x2 - x1
    height = y2 - y1
    font = _font(region["font_size"], bold=bold)
    spacing = max(4, round(region["font_size"] * 0.16))
    probe = ImageDraw.Draw(canvas)
    lines = wrap_text(probe, text, font, width)
    if _text_height(probe, lines, font, spacing) > height:
        raise ValueError("text does not fit text region")

    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    y = 0
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        line_width = box[2] - box[0]
        x = {
            "left": 0,
            "center": (width - line_width) // 2,
            "right": width - line_width,
        }[region["align"]]
        draw.text(
            (x, y),
            line,
            font=font,
            fill=region["color"],
        )
        y += box[3] - box[1] + spacing

    rotation = region["rotation"]
    if rotation:
        layer = layer.rotate(
            rotation,
            resample=Image.Resampling.BICUBIC,
            expand=True,
        )
        paste_x = x1 + (width - layer.width) // 2
        paste_y = y1 + (height - layer.height) // 2
        if (
            paste_x < 0
            or paste_y < 0
            or paste_x + layer.width > CANVAS[0]
            or paste_y + layer.height > CANVAS[1]
        ):
            raise ValueError("rotated text leaves the canvas")
    else:
        paste_x, paste_y = x1, y1
    canvas.paste(layer, (paste_x, paste_y), layer)
```

Use `slide["text_layout"]["headline"]` and
`slide["text_layout"]["body"]` in `_render_content`. Keep `_render_cta`
logo-led and unchanged except for any shared helper signature updates.

Render the slide number in a small contrast pill after content rendering so it
remains readable without imposing a content template.

```python
number_box = draw.textbbox((0, 0), number, font=number_font)
pill = (
    CANVAS[0] - 126,
    CANVAS[1] - 84,
    CANVAS[0] - 28,
    CANVAS[1] - 28,
)
draw.rounded_rectangle(pill, radius=28, fill="#171512")
draw.text(
    (
        pill[0] + (pill[2] - pill[0] - number_box[2]) // 2,
        pill[1] + 8,
    ),
    number,
    font=number_font,
    fill="#FFFFFF",
)
```

- [ ] **Step 9: Make `render_file` enforce the content gate**

Before rendering:

```python
assert_renderable(draft["draft_id"], read_events(history_path))
```

After every JPEG is successfully written:

```python
mark_rendered(draft, history_path)
```

Remove the old automatic `drafted` event from `render_file`.
Extend `mark_rendered` in this task so the append-only event preserves the
visual decisions that future runs must avoid repeating:

```python
event = _draft_event(draft, "rendered")
event["art_direction"] = draft["art_direction"]
event["scenes"] = [
    slide["scene"]
    for slide in draft["slides"]
    if slide["kind"] != "cta"
]
append_event(history, event)
```

Update `test_render_file_records_drafted_only_once` to
`test_render_file_records_visual_plan_once` and assert one `rendered` event
containing the exact `art_direction` and ordered `scenes`.

- [ ] **Step 10: Run render tests and full suite**

Run:

```bash
.venv/bin/python -m unittest social/test_social.py -v
```

Expected: all tests pass with 1080×1350 JPEGs, no EXIF, full-bleed content art,
and the unchanged CTA branding.

- [ ] **Step 11: Commit the renderer**

```bash
git add social/render.py social/test_social.py
git commit -m "feat: art direct full-bleed social slides"
```

---

### Task 3: Rewrite the daily contract around two approvals

**Files:**
- Modify: `social/PROMPT.md:1-173`
- Modify: `social/README.md:1-114`
- Test: `social/test_social.py:953-1017`

**Interfaces:**
- Consumes: `social/render.py record-content <draft.json>`
- Consumes: `social/render.py approve-content <draft.json>`
- Consumes: `social/render.py render <draft.json> --output <directory>`
- Consumes: `social/publish.py <draft.json> <rendered-directory>`
- Produces: a recurring-task instruction that stops once for content approval and once for final approval

- [ ] **Step 1: Write a failing contract test**

Add a test that reads the prompt as user-facing behavior:

```python
def test_prompt_requires_content_approval_before_image_generation(self):
    prompt = (
        Path(__file__).with_name("PROMPT.md")
        .read_text(encoding="utf-8")
    )
    content_gate = prompt.index("콘텐츠 승인")
    image_generation = prompt.index("## Generate illustrations")
    final_gate = prompt.index("Exact `승인`")

    self.assertLess(content_gate, image_generation)
    self.assertLess(image_generation, final_gate)
    self.assertIn(
        "Do not generate images before content approval.",
        prompt,
    )
    self.assertIn("Slide 1", prompt)
    self.assertIn("Caption", prompt)
```

- [ ] **Step 2: Run the contract test and verify RED**

Run:

```bash
.venv/bin/python -m unittest \
  social.test_social.PublishFlowTests.test_prompt_requires_content_approval_before_image_generation \
  -v
```

Expected: failure because the current prompt generates images before its only
approval.

- [ ] **Step 3: Rewrite `social/PROMPT.md`**

Use this exact operational order:

1. Select project, problem, hook, format, and slide count.
2. Save content-only JSON with `kind`, `headline`, and `body`; omit
   `illustration`, `alt_text`, and `text_layout`.
3. Run `social/render.py record-content`.
4. Present project, topic, format, total, every `Slide N` headline/body, and
   `Caption`.
5. Stop. The exact phrase `콘텐츠 승인` is the only permission to continue.
6. Run `social/render.py approve-content`.
7. Create a fresh art direction for this carousel and a different scene plan
   for each slide.
8. Add top-level `art_direction`, plus `scene`, `illustration`, `alt_text`, and
   `text_layout` to non-CTA slides.
9. Generate full-bleed, text-free art with the built-in image model.
10. Render, inspect, and present the completed carousel.
11. Stop. Exact `승인` publishes; revision feedback changes only affected
    slides; copy changes return to a new content revision.

The image section must say:

- no fixed composition templates;
- read recent `rendered` history events and reject substantially similar
  `art_direction` or `scenes`;
- dialogue bubbles must belong to a depicted speaker;
- blank notes, signs, speech bubbles, and environmental text surfaces must be
  intentionally positioned around the matching `text_layout` box;
- one carousel shares art style, palette, character treatment, and texture;
- each slide receives a content-specific composition;
- reject generic startup-art decoration, fake lettering, malformed anatomy,
  and meaningless props.

- [ ] **Step 4: Update `social/README.md`**

Replace the single approval sequence under “Daily operation” with:

```text
content proposal
→ 콘텐츠 승인
→ scene planning and image generation
→ completed carousel
→ 승인
→ R2 staging
→ Instagram publish
→ verified R2 cleanup
```

Document the three local commands:

```bash
.venv/bin/python social/render.py record-content .social-work/<draft-id>/draft.json
.venv/bin/python social/render.py approve-content .social-work/<draft-id>/draft.json
.venv/bin/python social/render.py render .social-work/<draft-id>/draft.json --output .social-work/<draft-id>/rendered
```

State explicitly that the content proposal directory must contain no generated
image before `콘텐츠 승인`.

- [ ] **Step 5: Run the contract test and full suite**

Run:

```bash
.venv/bin/python -m unittest social/test_social.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit the contract**

```bash
git add social/PROMPT.md social/README.md social/test_social.py
git commit -m "docs: split content and carousel approvals"
```

---

### Task 4: Verify the first content-only handoff

**Files:**
- Modify locally only: `.social-work/<new-draft-id>/draft.json`
- Modify runtime history: `.social-work/history.jsonl`

**Interfaces:**
- Consumes: completed Tasks 1–3
- Produces: the first content-only approval message in this Codex task

- [ ] **Step 1: Mark the rejected rendered draft as revised**

Use its existing draft JSON:

```bash
.venv/bin/python social/publish.py --record-state revised \
  .social-work/2026-07-29-say-better-01/draft.json
```

Expected: latest event for `2026-07-29-say-better-01` is `revised`.

- [ ] **Step 2: Create the next content-only revision**

Write `.social-work/2026-07-29-say-better-02/draft.json` with:

- `draft_id`, `project_id`, `format_id`, `hook`, and `caption`;
- 4–10 slides containing only `kind`, `headline`, and `body`;
- Say Better mentioned only on the CTA;
- the exact Say Better App Store URL and `link in bio` in the caption.

Do not create or copy any `art-*.png`, rendered directory, alt text, or
`text_layout`.

- [ ] **Step 3: Record the proposal and prove no image exists**

Run:

```bash
.venv/bin/python social/render.py record-content \
  .social-work/2026-07-29-say-better-02/draft.json
find .social-work/2026-07-29-say-better-02 \
  -maxdepth 1 -type f ! -name draft.json -print
```

Expected: the record command succeeds and `find` prints nothing.

- [ ] **Step 4: Run the full regression suite**

Run:

```bash
.venv/bin/python -m unittest social/test_social.py -v
git diff --check
```

Expected: all tests pass and `git diff --check` prints nothing.

- [ ] **Step 5: Present content and stop**

Send the project, topic, format, total slide count, numbered slide
headline/body pairs, and caption to this Codex task. Ask for exact
`콘텐츠 승인`, revision feedback, or `보류`.

Do not generate any image, run `approve-content`, render, stage to R2, or call
Instagram in this task.
