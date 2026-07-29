# Instagram Promotion Workflow

This workflow creates one English carousel draft every day at 8:00 AM
America/Vancouver, shows it in Codex for approval, and publishes only after
`승인`.

It starts with Say Better and Fina, rotating by the least recent successful
publication. Generated illustrations and unpublished drafts stay outside Git.
Approved JPEGs are briefly exposed through private Cloudflare R2 presigned URLs
because Instagram must fetch each image from a URL. The objects are deleted and
the prefix is verified empty after every success or failure.

## 1. Install locally

From the repository root:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r social/requirements.txt
.venv/bin/python -m unittest social/test_social.py -v
```

`uv` is used because it creates the environment without requiring the
OS-specific `python3-venv` package.

Public configuration is in `projects.json`. Add future apps there with their
logo, live App Store URL, positioning, audience problems, and palette. Add
explicit schedule slots only when more than one daily post is needed.

## 2. Connect Instagram

This is a one-time setup in Meta:

1. Create the Instagram account that will publish the carousels.
2. Convert it to a Professional account.
3. Create a Meta developer app.
4. Add **Instagram API with Instagram Login**.
5. Request only:
   - `instagram_business_basic`
   - `instagram_business_content_publish`
6. Authorize the professional account you own.
7. Record the Instagram professional user ID and long-lived access token.
8. Record the token's expiry and renewal procedure.

Instagram Login is used so a Facebook Page is not required. Start
`META_API_VERSION` at `v23.0`, which matches Meta's verified publishing example,
and check Meta's currently supported versions during setup.

References:

- [Instagram API with Instagram Login](https://www.postman.com/meta/instagram/folder/23987686-98bfade9-3736-4738-8b4a-f56d6534f6de)
- [Create an image container](https://www.postman.com/meta/instagram/request/23987686-f4b5a72d-a125-4080-8968-93de1a549e68)
- [Publish a container](https://www.postman.com/meta/instagram/request/23987686-299b176b-90aa-4d8a-b6cf-e6028fc69de5)

## 3. Create private R2 staging

In Cloudflare:

1. Create a new R2 bucket named `portfolio-social-staging`.
2. Keep the public development URL and custom domains disabled.
3. Create an R2 API token with object read/write access scoped only to this
   bucket.
4. Add a lifecycle rule that expires every object after one day.

The runtime still deletes objects immediately. The lifecycle rule is only crash
protection.

References:

- [R2 presigned URLs](https://developers.cloudflare.com/r2/api/s3/presigned-urls/)
- [Delete R2 objects](https://developers.cloudflare.com/r2/objects/delete-objects/)
- [R2 lifecycle rules](https://developers.cloudflare.com/r2/buckets/object-lifecycles/)

## 4. Store secrets outside Git

Prefer Codex-managed secrets for the recurring automation.

For local testing, create
`/home/cwsbr/.config/portfolio-social/credentials.json` with permission `600`.
The file must contain these keys:

- `IG_USER_ID`
- `IG_ACCESS_TOKEN`
- `META_API_VERSION`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET`

`R2_BUCKET` must be `portfolio-social-staging`. Never place this file, an
`.env`, tokens, or presigned URLs inside the repository. Never paste secret
values into a Codex chat.

Create the protected empty file, then fill it in with a local editor:

```bash
mkdir -p /home/cwsbr/.config/portfolio-social
install -m 600 /dev/null \
  /home/cwsbr/.config/portfolio-social/credentials.json
```

To run a local publication without sourcing the credentials file:

```bash
.venv/bin/python - <<'PY'
import json
import os
import subprocess
from pathlib import Path

credentials = json.loads(
    Path("/home/cwsbr/.config/portfolio-social/credentials.json")
    .read_text(encoding="utf-8")
)
command = [
    ".venv/bin/python",
    "social/publish.py",
    ".social-work/2026-07-30-fina-01/draft.json",
    ".social-work/2026-07-30-fina-01/rendered",
]
raise SystemExit(
    subprocess.call(command, env={**os.environ, **credentials})
)
PY
```

Use the approved draft's real path. The credentials JSON is parsed as data and
is never executed by the shell.

## Daily operation

The recurring Codex task follows `PROMPT.md`:

1. Select the least-recently published active project and an eligible format.
2. Write educational, problem-led content.
3. Generate text-free editorial illustrations with the built-in image model.
4. Render and inspect 1080×1350 JPEGs.
5. Show slides, caption, and alt text in chat.
6. Wait for `승인`.
7. Publish once, then delete and verify the R2 prefix.

`publishing` is an intentionally blocked state. It means the publish request may
have succeeded without a safely recorded media ID, so automatic retry could
create a duplicate. Reconcile that container in Instagram before continuing.
