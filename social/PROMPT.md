# Daily Instagram Carousel Contract

Create one English Instagram carousel only when the user sends the exact
command `오늘 루틴 시작`. Use two approvals: content approval before any art
exists, then final approval before publication. Never publish automatically.

## Before drafting

1. Read `social/projects.json`, recent local `rendered` events in
   `.social-work/history.jsonl`, and published events in
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
- Run the installed `humanizer` skill in embedded mode on every headline,
  body, caption, and hashtag before presenting it. Read the result aloud,
  prefer plain words people naturally use, vary sentence rhythm, keep concrete
  details, and remove corporate jargon, filler, generic motivational
  language, and formulaic AI phrasing.
- Do not use hyphens, en dashes, or em dashes in written copy or text shown
  inside an image. Rewrite the sentence with natural punctuation instead.
  Exact required URLs are the only exception.
- The CTA contains the configured logo, app name, one positioning sentence,
  one outcome-specific comment keyword, and the official App Store badge.
  Never use an app screenshot.
- The CTA and caption promise one specific piece of useful help and ask for
  the same keyword. The final prose line of the caption, immediately before
  the hashtags, must follow this pattern: `Comment KEYWORD and I will send you
  SPECIFIC USEFUL ITEM, along with a link to APP NAME.` Adapt the useful item
  to the post. Do not put the raw App Store URL in the caption or mention a
  bio or profile link. Put 5–8 specific, relevant English hashtags on the
  final line and avoid generic reach-bait tags.
- The keyword tells people what to comment, but the Worker sends the approved
  reply for any non-self comment on that registered post.
- Add `comment_rule` with the approved uppercase `keyword`, the public
  `promise`, and the complete private `reply`. The reply must deliver the
  promised method, formula, or checklist first. Offer the app as an optional
  next step and put the exact App Store URL last.
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
  "caption": "A balance is a snapshot. It does not show what is about to leave your account.\n\nComment FORECAST and I will send you a simple checklist, along with a link to Fina.\n\n#cashflow #budgetplanning #moneyhabits #personalfinance #financialplanning",
  "comment_rule": {
    "keyword": "FORECAST",
    "promise": "A simple checklist for looking ahead.",
    "reply": "Start with the bills you know are coming, then add normal weekly spending and leave room for irregular costs.\n\nIf you want help seeing upcoming pressure, Fina can help:\nhttps://apps.apple.com/us/app/fina-financial-companion/id6778169653"
  },
  "slides": [
    {"kind": "hook", "headline": "Your balance looks fine.", "body": "Next Tuesday might not."},
    {"kind": "content", "headline": "Today", "body": "Some of that balance is already spoken for."},
    {"kind": "content", "headline": "Next Tuesday", "body": "Two automatic payments arrive together."},
    {"kind": "cta", "headline": "See it coming with Fina.", "body": "Comment FORECAST and we will send a simple checklist for looking ahead."}
  ]
}
```

Run:

```bash
.venv/bin/python social/render.py record-content .social-work/<draft-id>/draft.json
```

## Present content and wait

Send to this Codex task: project, topic, format, draft ID, total slide count,
every `Slide N` headline and body (from `Slide 1` through the CTA), `Caption`,
`Comment keyword`, `Promise`, and the complete `Private reply`. Then stop. The exact phrase
`콘텐츠 승인` is the only permission to continue. Do not generate images before content approval.

## Generate illustrations

After exact `콘텐츠 승인`, run:

```bash
.venv/bin/python social/render.py approve-content .social-work/<draft-id>/draft.json
```

### Fixed visual identity

Keep these elements consistent across every app and every post:

- Use the same warm ivory background, `#FBF2E8`, with only a very subtle
  matte paper texture. Do not switch to pure white or an app-specific
  background.
- Match the rounded, hand-lettered typography in
  `social/assets/style/typography-reference.png`. Keep its friendly black-ink
  stroke, spacing, and hierarchy; reject typography that feels digital,
  corporate, or visibly AI-generated.
- Reuse the same fictional family shown in
  `social/assets/style/family-reference.png`: powder-blue dad, muted-coral
  mom, dusty-pink daughter, and pale-sky-blue son. Preserve their rounded
  proportions, two ear bumps, simple faces, black outlines, and relative
  sizes. Cast one or more family members according to the story instead of
  inventing app-specific mascots.
- Keep the illustration language simple: slightly imperfect black ink,
  matte pastel fills, restrained detail, and generous negative space.

Only the theme accent changes by project. Read `palette.accent` from
`social/projects.json` and use it sparingly for highlighted words and
meaningful props. Say Better uses coral; Fina uses sage. The app accent must
never recolor the family or replace the fixed background.

Create a fresh art direction for this carousel and a different,
content-specific scene plan for each non-CTA slide. Read recent `rendered`
history events and reject any substantially similar `art_direction` or scenes.
Add top-level `art_direction`. Add `scene`, `illustration`, and `text_layout`
to every non-CTA slide, and add meaningful `alt_text` to every slide including
the CTA.

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

## Render-ready draft shape

Each non-CTA `text_layout` has `headline` and `body` regions. A region uses
integer `box` coordinates `[x1, y1, x2, y2]` inside the 48 px safe inset,
avoids the slide-number rectangle `[954, 1266, 1052, 1322]`, and does not
overlap the other region after rotation. Headline `font_size` is 52–104; body
is 30–60.
`align` is `left`, `center`, or `right`; `color` and `background` are
`#RRGGBB` values with at least 4.5:1 contrast; and integer `rotation` is
-12 through 12. The background is the deterministic contrast treatment for
that scene-specific region, not a fixed carousel template.

```json
{
  "draft_id": "2026-07-30-fina-01",
  "project_id": "fina",
  "format_id": "what-happens-next",
  "hook": "Your balance looks fine. Next Tuesday might not.",
  "caption": "A balance is a snapshot. Want a simple way to look ahead? Comment FORECAST and we will send it. #cashflow #budgetplanning #moneyhabits #personalfinance #financialplanning",
  "comment_rule": {
    "keyword": "FORECAST",
    "promise": "A simple checklist for looking ahead.",
    "reply": "Start with the bills you know are coming, then add normal weekly spending and leave room for irregular costs.\n\nIf you want help seeing upcoming pressure, Fina can help:\nhttps://apps.apple.com/us/app/fina-financial-companion/id6778169653"
  },
  "art_direction": "Hand-inked editorial scenes on warm paper with sage accents",
  "slides": [
    {
      "kind": "hook",
      "headline": "Your balance looks fine.",
      "body": "Next Tuesday might not.",
      "illustration": "art-01.png",
      "scene": "A kitchen calendar occupies the left foreground while a person studies it from the right.",
      "alt_text": "A person looking ahead at approaching bills on a kitchen calendar.",
      "text_layout": {
        "headline": {"box": [64, 80, 1016, 310], "font_size": 78, "align": "left", "color": "#171512", "background": "#FFFDF8", "rotation": 0},
        "body": {"box": [64, 350, 900, 530], "font_size": 44, "align": "left", "color": "#171512", "background": "#FFFDF8", "rotation": 0}
      }
    },
    {
      "kind": "content",
      "headline": "Today",
      "body": "Some of that balance is already spoken for.",
      "illustration": "art-02.png",
      "scene": "Labeled envelopes form a diagonal path below a floating balance card.",
      "alt_text": "Envelopes beside a current balance.",
      "text_layout": {
        "headline": {"box": [64, 120, 760, 350], "font_size": 78, "align": "left", "color": "#171512", "background": "#FFFDF8", "rotation": 0},
        "body": {"box": [64, 470, 900, 650], "font_size": 44, "align": "left", "color": "#171512", "background": "#FFFDF8", "rotation": 0}
      }
    },
    {
      "kind": "content",
      "headline": "Next Tuesday",
      "body": "Two automatic payments arrive together.",
      "illustration": "art-03.png",
      "scene": "Two paper bill notices converge on one Tuesday square in a large wall calendar.",
      "alt_text": "Two bills landing on one calendar date.",
      "text_layout": {
        "headline": {"box": [64, 670, 1016, 900], "font_size": 78, "align": "left", "color": "#171512", "background": "#FFFDF8", "rotation": 0},
        "body": {"box": [64, 960, 900, 1140], "font_size": 44, "align": "left", "color": "#171512", "background": "#FFFDF8", "rotation": 0}
      }
    },
    {
      "kind": "cta",
      "headline": "See it coming with Fina.",
      "body": "Comment FORECAST and we will send a simple checklist for looking ahead.",
      "alt_text": "Fina logo and a Download on the App Store badge."
    }
  ]
}
```

## Render, inspect, and wait

Run:

```bash
.venv/bin/python social/render.py render .social-work/<draft-id>/draft.json --output .social-work/<draft-id>/rendered
```

Inspect every rendered JPEG. Regenerate or revise affected slides for generated
lettering, awkward cropping, unreadable or overflowing copy, incorrect
branding, unsupported claims, or art that conflicts with its text layout.

Present the completed carousel in order, plus project, format, draft ID, total
slides, Caption, Comment keyword, Promise, the complete Private reply, and
ordered alt text. Stop. Exact `승인` publishes; revision feedback changes only
affected slides; copy changes return to a new content revision and require
`콘텐츠 승인` again. Do not create R2 objects or Instagram containers before
final approval.

## Handle the final reply

- Exact `승인`: publish the newest non-terminal draft with:

  ```bash
  uv run --env-file .env .venv/bin/python social/publish.py \
    .social-work/<draft-id>/draft.json \
    .social-work/<draft-id>/rendered
  ```

  Report the Instagram media ID and confirm the R2 prefix is empty.
- Image-only feedback: run `.venv/bin/python social/publish.py --record-state
  image-revised .social-work/<draft-id>/draft.json`, update only the affected
  art or layout, rerender the same draft, and present the fresh carousel.
- Copy feedback: run `.venv/bin/python social/publish.py --record-state revised
  .social-work/<draft-id>/draft.json`, create the next revision ID, and restart
  at content approval. Do not publish.
- `보류`: run `.venv/bin/python social/publish.py --record-state held
  .social-work/<draft-id>/draft.json` and do not publish.
- If multiple drafts await a decision, require the displayed draft ID with the
  approval.
- If publication reports `cleanup_failed`, run `uv run --env-file .env
  .venv/bin/python social/publish.py --cleanup-only <draft-id>` before any new
  draft; this command requires only the R2 credentials. If it stops in
  `publishing`, do not retry: report the container ID and require manual
  Instagram reconciliation to avoid a duplicate post.
