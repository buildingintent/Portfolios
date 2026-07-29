# Daily Instagram Carousel Contract

Create one English Instagram carousel draft for the 8:00 AM
America/Vancouver slot. Present it in this Codex task and stop for approval.
Never publish automatically.

## Before drafting

1. Read `social/projects.json` and `social/history.jsonl`.
2. Stop and report any latest `cleanup_failed` or `publishing` event. Do not
   draft while publication state is unresolved.
3. Select the active project whose latest `published` event is oldest. If no
   project has been published, use config order: Say Better, then Fina.
4. Exclude every format with a `published` event in the previous 14 days.
5. If no format remains eligible, stop and ask to expand the format library.

## Choose the story

Choose one configured audience problem and the format that explains it most
naturally. Slide count follows the story and must be 4–10 including hook and
CTA.

Available structures:

- `ways-checklist`: hook, one useful action per slide, CTA.
- `mistake-fix`: familiar mistake, consequence, better alternative, CTA.
- `signs-red-flags`: hook, one recognizable sign per slide, CTA.
- `before-after`: situation, old approach, improved approach, reason, CTA.
- `myth-reality`: claim/correction pairs, takeaway, CTA.
- `mini-story`: person, problem, consequence, insight, CTA.
- `quiz-reveal`: choice, reveal, explanation, CTA.
- `what-happens-next`: a forward-looking sequence, especially useful for Fina.
- `do-this-not-that`: paired behaviors and concise reasons.
- `a-vs-b`: two approaches compared against one concrete goal.
- `script-formula`: reusable wording or decision framework with examples.
- `ranked-options`: transparent ranking with one criterion per slide.
- `three-levels`: basic, better, and strongest responses to one problem.
- `contrarian-breakdown`: defensible counterpoint, evidence, limit, takeaway.
- `mini-case-study`: clearly labeled hypothetical situation, decision, result.
- `short-action-plan`: a small sequence readers can follow over several days.

Reject the idea and choose again when its hook, promise, or central example is
substantially similar to a recently published post, even if the format differs.

## Write the carousel

- English only.
- Make the hook specific, credible, and understandable without the caption.
- Every non-CTA slide must be useful without mentioning the app.
- Mention the app only on the final CTA slide.
- Keep each slide focused on one idea and readable on a phone.
- The final slide uses the configured app logo, app name, one positioning
  sentence, and the official App Store badge. It contains no app screenshot.
- Caption must accurately summarize the slides, contain `link in bio`, and
  include the project's exact App Store URL.
- Write meaningful alt text for every slide.
- For Fina, never promise guaranteed outcomes or present education as
  personalized financial, investment, tax, legal, or credit advice.

Save this contract as `.social-work/{draft_id}/draft.json`:

```json
{
  "draft_id": "2026-07-30-fina-01",
  "project_id": "fina",
  "format_id": "what-happens-next",
  "hook": "Your balance looks fine. Next Tuesday might not.",
  "caption": "A balance is a snapshot. Find Fina through the link in bio or on the App Store: https://apps.apple.com/us/app/fina-financial-companion/id6778169653",
  "slides": [
    {
      "kind": "hook",
      "headline": "Your balance looks fine.",
      "body": "Next Tuesday might not.",
      "illustration": "art-01.png",
      "alt_text": "A person looking ahead at approaching bills."
    },
    {
      "kind": "content",
      "headline": "Today",
      "body": "Some of that balance is already spoken for.",
      "illustration": "art-02.png",
      "alt_text": "Envelopes beside a current balance."
    },
    {
      "kind": "content",
      "headline": "Next Tuesday",
      "body": "Two automatic payments arrive together.",
      "illustration": "art-03.png",
      "alt_text": "Two bills landing on one calendar day."
    },
    {
      "kind": "cta",
      "headline": "See it coming with Fina.",
      "body": "Forecast upcoming pressure before it becomes a problem.",
      "alt_text": "Fina logo and a Download on the App Store badge."
    }
  ]
}
```

Use local date plus project ID and a two-digit revision number for `draft_id`.
A revision gets `-02`, then `-03`.

## Generate illustrations

Use the built-in Codex image model, not an image API or SDK.

Generate one text-free editorial illustration per non-CTA slide:

- One coherent art direction, palette, line weight, and character treatment
  across the carousel.
- Warm editorial illustration with subtle texture and clear subjects.
- Leave visual breathing room; the renderer places copy separately.
- No text, letters, numbers, logos, app UI, phone UI, bank screens, financial
  account data, watermark, or identifiable Apple device.
- Do not imply that fictional amounts or accounts belong to a real person.

Save sources beside `draft.json` using the exact filenames in the draft.

## Render and inspect

Run:

```bash
.venv/bin/python social/render.py render \
  .social-work/2026-07-30-fina-01/draft.json \
  --output .social-work/2026-07-30-fina-01/rendered
```

Use the current draft ID, not the example ID. Inspect every rendered JPEG.
Regenerate or rewrite before showing the draft if there is generated lettering,
awkward cropping, unreadable copy, overflow, incorrect branding, or unsupported
claims.

## Present and wait

Send to this Codex task:

1. Project, format, draft ID, and slide count.
2. Every rendered image in order.
3. Caption.
4. Ordered alt text.
5. A short request for `승인`, revision feedback, or `보류`.

Do not create R2 objects or Instagram containers at this stage.

## Handle the reply

- Exact `승인`: publish the newest non-terminal draft with:

  ```bash
  .venv/bin/python social/publish.py \
    .social-work/2026-07-30-fina-01/draft.json \
    .social-work/2026-07-30-fina-01/rendered
  ```

  Use the current draft ID. Report the Instagram media ID and confirm the R2
  prefix is empty.

- Revision feedback: run
  `.venv/bin/python social/publish.py --record-state revised
  .social-work/{draft_id}/draft.json`, create the next revision ID, regenerate,
  render, and present it again. Do not publish.
- `보류`: run
  `.venv/bin/python social/publish.py --record-state held
  .social-work/{draft_id}/draft.json` and do not publish.
- If multiple drafts await a decision, require the displayed draft ID with
  approval.
- If publication reports `cleanup_failed`, run
  `.venv/bin/python social/publish.py --cleanup-only {draft_id}` before any
  new draft.
- If publication stops in `publishing`, do not retry. Report the container ID
  and require manual Instagram reconciliation to avoid a duplicate post.
