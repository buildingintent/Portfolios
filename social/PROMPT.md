# Daily Instagram Carousel Contract

Create one English Instagram carousel for the 8:00 AM America/Vancouver slot.
Use two approvals: content approval before any art exists, then final approval
before publication. Never publish automatically.

## Before drafting

1. Read `social/projects.json` and recent `rendered` and publication events in
   `social/history.jsonl`.
2. Stop and report any latest `cleanup_failed` or `publishing` event. Do not
   draft while publication state is unresolved.
3. Select the active project whose latest `published` event is oldest. If none
   has been published, use config order: Say Better, then Fina.
4. Exclude formats published in the previous 14 days. If none remains, stop
   and ask to expand the format library.
5. Select a configured audience problem, a non-similar hook, a format that
   explains it naturally, and 4–10 slides including hook and CTA. Reject an
   idea substantially similar to a recent post even if its format differs.

Available structures: `ways-checklist`, `mistake-fix`, `signs-red-flags`,
`before-after`, `myth-reality`, `mini-story`, `quiz-reveal`,
`what-happens-next`, `do-this-not-that`, `a-vs-b`, `script-formula`,
`ranked-options`, `three-levels`, `contrarian-breakdown`, `mini-case-study`,
and `short-action-plan`.

## Draft content only

- English only. Make the hook specific, credible, and understandable without
  the caption. Keep every non-CTA slide useful without mentioning the app;
  mention it only on the CTA.
- The CTA contains the configured logo, app name, one positioning sentence,
  and the official App Store badge—never an app screenshot.
- The caption accurately summarizes the slides, includes `link in bio`, and
  contains the project's exact App Store URL.
- Write a meaningful plan for every slide. For Fina, do not promise outcomes
  or present education as personalized financial, investment, tax, legal, or
  credit advice.

Save `.social-work/{draft_id}/draft.json`, using the local date, project ID,
and a two-digit revision (`-02`, then `-03`) for `draft_id`. At this stage,
each slide has only `kind`, `headline`, and `body`; omit `illustration`,
`alt_text`, `scene`, and `text_layout`, and omit top-level `art_direction`.

```json
{
  "draft_id": "2026-07-30-fina-01",
  "project_id": "fina",
  "format_id": "what-happens-next",
  "hook": "Your balance looks fine. Next Tuesday might not.",
  "caption": "A balance is a snapshot. Find Fina through the link in bio or on the App Store: https://apps.apple.com/us/app/fina-financial-companion/id6778169653",
  "slides": [
    {"kind": "hook", "headline": "Your balance looks fine.", "body": "Next Tuesday might not."},
    {"kind": "content", "headline": "Today", "body": "Some of that balance is already spoken for."},
    {"kind": "content", "headline": "Next Tuesday", "body": "Two automatic payments arrive together."},
    {"kind": "cta", "headline": "See it coming with Fina.", "body": "Forecast upcoming pressure before it becomes a problem."}
  ]
}
```

Run:

```bash
.venv/bin/python social/render.py record-content .social-work/<draft-id>/draft.json
```

## Present content and wait

Send to this Codex task: project, topic, format, draft ID, total slide count,
every `Slide N` headline and body (from `Slide 1` through the CTA), and
`Caption`. Then stop. The exact phrase
`콘텐츠 승인` is the only permission to continue. Do not generate images before content approval.

## Generate illustrations

After exact `콘텐츠 승인`, run:

```bash
.venv/bin/python social/render.py approve-content .social-work/<draft-id>/draft.json
```

Create a fresh art direction for this carousel and a different,
content-specific scene plan for each non-CTA slide. Read recent `rendered`
history events and reject any substantially similar `art_direction` or scenes.
Add top-level `art_direction`, and add `scene`, `illustration`, `alt_text`, and
`text_layout` to every non-CTA slide.

Use the built-in Codex image model, not an image API or SDK. Generate
full-bleed, text-free art beside `draft.json` using each slide's exact
illustration filename.

- Do not use fixed composition templates. One carousel shares art style,
  palette, character treatment, and texture, but every slide gets its own
  content-specific composition.
- Dialogue bubbles must belong to a depicted speaker. Intentionally position
  blank notes, signs, speech bubbles, and environmental text surfaces around
  the matching `text_layout` box.
- Reject generic startup-art decoration, fake lettering, malformed anatomy,
  and meaningless props. Never include text, letters, numbers, logos, app UI,
  phone UI, bank screens, financial account data, watermarks, or identifiable
  Apple devices. Do not imply fictional amounts or accounts are real.

## Render, inspect, and wait

Run:

```bash
.venv/bin/python social/render.py render .social-work/<draft-id>/draft.json --output .social-work/<draft-id>/rendered
```

Inspect every rendered JPEG. Regenerate or revise affected slides for generated
lettering, awkward cropping, unreadable or overflowing copy, incorrect
branding, unsupported claims, or art that conflicts with its text layout.

Present the completed carousel in order, plus project, format, draft ID, total
slides, Caption, and ordered alt text. Stop. Exact `승인` publishes; revision
feedback changes only affected slides; copy changes return to a new content
revision and require `콘텐츠 승인` again. Do not create R2 objects or Instagram
containers before final approval.

## Handle the final reply

- Exact `승인`: publish the newest non-terminal draft with:

  ```bash
  uv run --env-file .env .venv/bin/python social/publish.py \
    .social-work/<draft-id>/draft.json \
    .social-work/<draft-id>/rendered
  ```

  Report the Instagram media ID and confirm the R2 prefix is empty.
- Revision feedback: run `.venv/bin/python social/publish.py --record-state
  revised .social-work/<draft-id>/draft.json`, update only the affected
  rendered slides, and present it again. Copy changes create the next revision
  ID and restart at content approval. Do not publish.
- `보류`: run `.venv/bin/python social/publish.py --record-state held
  .social-work/<draft-id>/draft.json` and do not publish.
- If multiple drafts await a decision, require the displayed draft ID with the
  approval.
- If publication reports `cleanup_failed`, run `uv run --env-file .env
  .venv/bin/python social/publish.py --cleanup-only <draft-id>` before any new
  draft. If it stops in `publishing`, do not retry: report the container ID and
  require manual Instagram reconciliation to avoid a duplicate post.
