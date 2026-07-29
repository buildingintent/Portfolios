# Instagram Promotion Automation Design

**Status:** Approved design  
**Date:** 2026-07-29  
**Initial projects:** Say Better and Fina

## Goal

Create one English Instagram carousel draft every day at 8:00 AM
America/Vancouver time. Codex generates the content and illustrations, sends
the completed slides and caption to this Codex task, and publishes through the
Instagram API immediately after explicit chat approval.

The system must be safe to keep in this public repository. No credential,
access token, generated presigned URL, or unpublished draft is committed.

## Confirmed Product Decisions

- Use one Instagram account and rotate active projects fairly.
- Start with one post per day. Additional daily slots can be added later.
- Generate English content only.
- Require explicit approval in this Codex task. `승인` publishes the latest
  pending draft; revision feedback regenerates it without publishing.
- Publish immediately after approval.
- Use editorial illustrations similar to the supplied reference.
- Do not depend on app UI screenshots.
- Use the app logo, app name, official App Store badge, and a short CTA only on
  the final slide.
- Include the App Store URL in the caption and mention the profile link.
- Keep educational slides focused on recognizable audience problems. The app
  appears only as the final bridge to a solution.
- Do not reuse the same storytelling format within 14 days.

## Audience and Positioning

### Say Better

Primary users:

- English speakers who communicate with people in other languages.
- People who write professional messages and emails from their phones.
- People who want to polish wording quickly so it is clearer and more
  professional.

Content should focus on cross-language clarity, tone, confidence, concise
mobile writing, and professional communication.

### Fina

Primary users struggle with overspending, inconsistent budgets, subscriptions,
unclear cash flow, and shared financial planning.

Fina's central message is that it does more than record a problem afterward: it
forecasts upcoming financial pressure and gives useful guidance before the
problem happens. Marketing copy must not promise guaranteed financial outcomes
or present generic carousel content as personalized financial advice.

## Architecture

The system has three stages and no custom web UI or database.

### 1. Daily draft

A Codex recurring automation wakes this task at 8:00 AM America/Vancouver.
Codex:

1. Reads the active project profiles and publication history.
2. Chooses the least recently promoted eligible project.
3. Selects a relatable problem, hook, storytelling format, and resulting slide
   count.
4. Uses the Codex image model to create text-free editorial illustrations.
5. Uses the already-installed Pillow library to compose English copy, slide
   numbering, and branding at 1080×1350.
6. Validates the draft and sends ordered slides, caption, and alt text to this
   task.

### 2. Chat approval

The draft remains local and private until approval.

- `승인` publishes the latest pending draft.
- Revision feedback creates a new revision and invalidates the prior one.
- `보류` leaves the draft unpublished.
- If multiple daily slots are added later, approvals use the displayed draft
  ID to remove ambiguity.

No R2 upload or Instagram container is created before approval.

### 3. Immediate publication

After approval:

1. Upload the approved JPEGs to a dedicated private R2 staging bucket.
2. Generate one-hour presigned GET URLs.
3. Create an Instagram carousel child container for each URL.
4. Wait for every child container to finish.
5. Create the parent carousel and publish it exactly once.
6. Record the Instagram media ID and publication history.
7. Delete every R2 object and verify that the draft prefix is empty.

Instagram's image publishing endpoint requires `image_url`; Meta fetches the
image from that URL. Presigned R2 URLs satisfy this without making the bucket
public.

## Content Engine

Slide count is an output of the chosen hook and format, not a fixed template.
V1 uses 4–10 slides, including the hook and CTA.

The initial library contains 16 storytelling formats:

| Format | Typical length | Shape |
| --- | ---: | --- |
| Ways / checklist | N + 2 | Hook, one action per slide, CTA |
| Mistake → fix | 5–9 | Familiar mistake, consequence, better alternative |
| Signs / red flags | N + 2 | Hook, one recognizable sign per slide, CTA |
| Before → after | 5–7 | Situation, old approach, improved approach, reason, CTA |
| Myth → reality | 6–10 | Claim and correction pairs, takeaway, CTA |
| Mini story | 5–8 | Person, problem, consequence, insight, app bridge |
| Quiz → reveal | 4–7 | Choice, reveal, explanation, CTA |
| What happens next | 6–10 | A forecasted sequence, especially suited to Fina |
| Do this, not that | 5–9 | Paired behaviors with a concise reason |
| A versus B | 5–8 | Two approaches compared against one concrete goal |
| Script / formula | 4–8 | Reusable wording or decision framework, then examples |
| Ranked options | 5–10 | A transparent ranking with one criterion per slide |
| One problem, three levels | 6–9 | Basic, better, and strongest responses to one problem |
| Contrarian breakdown | 5–8 | A defensible counterpoint, evidence, limit, and takeaway |
| Mini case study | 5–9 | Clearly labeled hypothetical situation, decision, result |
| Short action plan | 6–10 | A small sequence readers can follow over several days |

Selection rules:

- A format used in the previous 14 days is ineligible.
- Before adding more daily slots, expand the library so it still contains at
  least 14 days of eligible structures at the new posting frequency.
- The planner compares the proposed hook, promise, and example with recent
  history and rejects a close repetition.
- Every non-CTA slide must provide value without mentioning the product.
- Claims must be supported by the slide content.
- The caption must match the approved slides and may not introduce unsupported
  claims.

The initial schedule contains one 8:00 AM slot. Future frequency increases are
made by adding explicit schedule slots, rather than changing the content
engine.

## Visual System

### Generated illustration

The Codex image model produces illustration only:

- No generated text, numbers, logos, bank screens, transaction data, or app UI.
- One coherent art direction per carousel: shared palette, line weight,
  character treatment, and scene vocabulary.
- Composition leaves predictable safe areas for copy.
- Illustrations must not reproduce private user data or imply a real financial
  account.

### Deterministic composition

Pillow composes all exact elements:

- Canvas: 1080×1350 JPEG.
- Typeface: installed Ubuntu Sans.
- Text, numbering, logo, CTA, and App Store badge are rendered from approved
  source assets.
- Copy is short enough to remain readable on a phone.
- Contrast and text bounds are validated before the draft is shown.
- Each slide receives meaningful alt text.

Brand palettes start from the approved logos:

- Fina: warm off-white, sage, and charcoal.
- Say Better: warm off-white, orange-red, and charcoal.

The final CTA slide contains no app screenshot. It uses the approved app logo,
app name, official App Store badge, and one positioning sentence.

Approved logo sources:

- Fina:
  `/home/cwsbr/personal/fina/apps/mobile/assets/fina-app-icon.png`
- Say Better:
  `/home/cwsbr/personal/say-better/app-store-listing/brand/app-icon-1024.png`

Implementation copies reviewed logo assets into this public repository; it
does not read the private repositories at runtime.

## Repository Data

The implementation should remain small:

- `social/README.md` — setup and operating instructions.
- `social/projects.json` — public project profiles, schedule slots, logo paths,
  positioning, audience problems, and App Store URLs.
- `social/PROMPT.md` — content and image-generation rules used by Codex.
- `social/render.py` — deterministic Pillow composition and validation.
- `social/publish.py` — R2 staging, Instagram publication, cleanup, and history.
- `social/history.jsonl` — append-only, non-secret draft and publication
  history.
- `social/assets/` — approved logos and the official App Store badge.

Unpublished drafts and rendered output live in an ignored local work directory.
The App Store URLs are entered during initial setup because neither private
repository currently contains a verified public product URL.

## Instagram Setup

Initial setup includes:

1. Create the Instagram account and convert it to a Professional account.
2. Create a Meta developer app.
3. Use Instagram API with Instagram Login and request only
   `instagram_business_basic` and
   `instagram_business_content_publish`.
4. Complete the login flow for the owned professional account.
5. Verify the account ID and test publishing with a disposable carousel.
6. Store the resulting credentials outside the repository.

The Instagram Login path is preferred because it does not require linking a
Facebook Page and requests fewer unrelated permissions.

## R2 Setup and Cleanup

Create a new private bucket named `building-intent-social`. Do not reuse any
backup bucket.

- Issue an R2 API token restricted to object read/write on this bucket.
- Keep public bucket access and custom domains disabled.
- Use one prefix per draft, such as `<draft-id>/01.jpg`.
- Generate one-hour presigned GET URLs only after approval.
- Delete the entire draft prefix after success or failure.
- List the prefix after deletion; non-empty results are cleanup failures.
- Add a one-day object lifecycle rule as crash protection. Runtime deletion
  remains mandatory and the lifecycle is only the final safety net.

## Secrets

The public repository contains variable names and setup instructions only.
Actual values live outside the repository in a permission-restricted local
configuration file or Codex-managed secret environment.

Required secrets:

- Instagram access token and professional account ID.
- Meta app credentials needed during authentication or token maintenance.
- R2 account ID, bucket-scoped access key ID, and secret access key.

Rules:

- Never place secrets in `.env` inside this repository.
- Never print authorization headers, tokens, presigned URLs, or provider
  response bodies containing credentials.
- Parse any local credential file as data; do not execute it with `source`.
- Validate required values before any upload.

## Idempotency and Failure Handling

Every draft has a unique ID and one state:

`drafted → approved → publishing → published`

or

`drafted → revised/held`

Publication records the final Instagram media ID before reporting success.
Retries inspect history first:

- A published draft is never published again.
- A partial child-container failure never creates a parent carousel.
- A parent container is published once.
- If Instagram publication succeeds but R2 deletion fails, only cleanup is
  retried.
- Cleanup runs in a `finally` path after any R2 upload.
- Failed cleanup is reported in this task and retried before the next draft.
- An expired or rejected Instagram token blocks publication and produces a
  setup alert; the approved draft remains available for retry.

## Verification

Keep verification proportional to the small implementation:

1. One runnable test file covers rendering bounds and the publication state
   machine with provider calls replaced by local fakes.
2. The failure-path check proves that R2 cleanup runs after a child-container,
   parent-container, or publish failure.
3. The idempotency check proves that a recorded Instagram media ID prevents a
   second publish call.
4. Setup concludes with one explicitly approved end-to-end test carousel on
   the new professional account, followed by verification that the R2 prefix is
   empty.

## Out of Scope for V1

- A web dashboard, database, multi-user approval system, or analytics UI.
- Reels, Stories, ads, comments, and direct-message automation.
- Automatic posting without explicit chat approval.
- App UI screenshot capture.
- More than one daily slot until additional project volume requires it.
- Performance analytics changing future content; publication history is kept
  so this can be added later when there is enough data.

## Primary References

- [Meta: create an image container](https://www.postman.com/meta/instagram/request/23987686-f4b5a72d-a125-4080-8968-93de1a549e68)
- [Meta: publish a container](https://www.postman.com/meta/instagram/request/23987686-299b176b-90aa-4d8a-b6cf-e6028fc69de5)
- [Meta: Instagram API with Instagram Login](https://www.postman.com/meta/instagram/folder/23987686-98bfade9-3736-4738-8b4a-f56d6534f6de)
- [Cloudflare R2 presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/)
- [Cloudflare R2 object deletion](https://developers.cloudflare.com/r2/objects/delete-objects/)
- [Cloudflare R2 object lifecycle rules](https://developers.cloudflare.com/r2/buckets/object-lifecycles/)
