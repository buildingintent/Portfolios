# Instagram Promotion Workflow

This workflow starts only when the user says `오늘 루틴 시작`.

It prepares an English carousel and its post-specific comment keyword, waits
for content approval, generates the images, waits for final approval, publishes
to Instagram, and registers that post's approved private-reply rule.

```text
content and comment reply proposal
→ 콘텐츠 승인
→ image generation
→ final carousel review
→ 승인
→ Instagram publish
→ comment rule registration
```

When someone comments the exact keyword, a Cloudflare Worker looks up the rule
for that Instagram media ID and sends one private reply. The helpful content
comes first and the relevant App Store URL comes last.

## Local setup

From the repository root:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r social/requirements.txt
.venv/bin/python -m unittest social/test_social.py -v
```

Public app information is in `social/projects.json`. Add future apps there with
their logo, live App Store URL, positioning, audience problems, and palette.
There is no posting schedule in the code.

## Local secrets

The repository-root `.env` is ignored by Git and must have permission `600`.
The publisher requires these names:

```text
INSTAGRAM_USER_ID
INSTAGRAM_ACCESS_TOKEN
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
INSTAGRAM_WEBHOOK_ADMIN_URL
INSTAGRAM_WEBHOOK_ADMIN_TOKEN
```

`INSTAGRAM_WEBHOOK_ADMIN_URL` is the deployed Worker URL ending in
`/admin/rules`:

```text
https://building-intent-instagram-webhook.cwsbrian.workers.dev/admin/rules
```

The matching admin token is also stored as an encrypted Worker secret.

`R2_ACCESS_TOKEN` is not used by the publisher. The R2 bucket name is fixed as
`building-intent-social`. Never commit `.env`, paste its values into chat, or
print tokens and presigned URLs.

```bash
chmod 600 .env
uv run --env-file .env .venv/bin/python social/publish.py \
  .social-work/<draft-id>/draft.json \
  .social-work/<draft-id>/rendered
```

The R2 objects are deleted immediately after Instagram fetches them. Keep the
bucket private and retain its one-day lifecycle rule as crash protection.

## Approval and recovery

The proposed content review includes the slide copy, caption, comment keyword,
promise, and exact private reply. All of them are locked by `콘텐츠 승인`.
The caption contains the keyword but not a raw App Store URL.

```bash
.venv/bin/python social/render.py record-content .social-work/<draft-id>/draft.json
.venv/bin/python social/render.py approve-content .social-work/<draft-id>/draft.json
.venv/bin/python social/render.py render \
  .social-work/<draft-id>/draft.json \
  --output .social-work/<draft-id>/rendered
```

If Instagram publishing succeeds but Worker rule registration fails, do not
publish again. Retry only the registration:

```bash
uv run --env-file .env .venv/bin/python social/publish.py \
  --register-rule-only .social-work/<draft-id>/draft.json
```

`publishing` is intentionally blocked because Instagram may have accepted the
request without returning a safely recorded media ID. Reconcile that post
before retrying.

## Cloudflare Worker and D1

The Worker source is in `social/webhook`. It verifies Meta's request signature,
matches only the whole normalized keyword, ignores self-comments, and records
each comment ID before sending so webhook retries cannot send duplicates.

After logging in to Cloudflare:

```bash
cd social/webhook
npm install
npx wrangler d1 create building-intent-instagram
```

Copy the returned database ID into the `d1_databases` binding in
`wrangler.jsonc`, then run:

```bash
npx wrangler d1 execute building-intent-instagram \
  --remote --file schema.sql
npx wrangler secret put INSTAGRAM_ACCESS_TOKEN
npx wrangler secret put INSTAGRAM_USER_ID
npx wrangler secret put META_APP_SECRET
npx wrangler secret put INSTAGRAM_WEBHOOK_VERIFY_TOKEN
npx wrangler secret put INSTAGRAM_WEBHOOK_ADMIN_TOKEN
npm test
npx wrangler deploy
```

The Worker free plan currently allows 100,000 requests per day and 10 ms of CPU
time per HTTP request. D1 free usage currently includes 5 million rows read and
100,000 rows written per day, with a 500 MB limit per database. This design uses
one rule row per post and one delivery row per matching comment, not one Worker
route or code rule per post.

References:

* [Cloudflare Worker limits](https://developers.cloudflare.com/workers/platform/limits/)
* [Cloudflare D1 limits](https://developers.cloudflare.com/d1/platform/limits/)
* [Cloudflare Worker secrets](https://developers.cloudflare.com/workers/configuration/secrets/)

## Meta setup

The connected Instagram professional account needs:

```text
instagram_business_basic
instagram_business_content_publish
instagram_business_manage_comments
```

In the Meta app's Instagram API settings:

1. Set the callback URL to the deployed Worker URL ending in
   `/instagram/webhook`:

   ```text
   https://building-intent-instagram-webhook.cwsbrian.workers.dev/instagram/webhook
   ```
2. Enter the same value stored as `INSTAGRAM_WEBHOOK_VERIFY_TOKEN`.
3. Subscribe the account to the `comments` webhook field.
4. Generate a fresh access token containing the required permissions if the
   existing token predates the comments permission.

Meta allows one private reply to a commenter within seven days of the comment.
The system therefore sends the complete approved message in one response.

References:

* [Meta private replies](https://www.postman.com/meta/instagram/request/23987686-189d7215-22b3-403f-b2f5-a46c7e66a514)
* [Meta comment webhook](https://www.postman.com/meta/instagram/request/23987686-db99ce99-bf76-475c-8b76-718576c11cae)
* [Subscribe an Instagram account to webhooks](https://www.postman.com/meta/instagram/request/23987686-0223707a-7035-46a2-8015-1fdf7249278f)
