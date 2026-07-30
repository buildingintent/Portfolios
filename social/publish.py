#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import boto3
from PIL import Image

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from social.render import (
    HISTORY_PATH,
    PUBLIC_HISTORY_PATH,
    append_event,
    assert_approved_content,
    content_fingerprint,
    draft_lock,
    draft_fingerprint,
    latest_event,
    load_json,
    read_events,
    rendered_manifest,
    validate_file,
)


META_API_VERSION = "v23.0"
R2_BUCKET = "building-intent-social"
REQUIRED_ENV = (
    "INSTAGRAM_USER_ID",
    "INSTAGRAM_ACCESS_TOKEN",
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
)
R2_REQUIRED_ENV = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
)


def assert_publishable(draft_id: str, events: list[dict]) -> None:
    draft_events = [
        event for event in events if event.get("draft_id") == draft_id
    ]
    latest = latest_event(draft_id, draft_events)
    if latest is None:
        raise RuntimeError("draft is not publishable")

    state = latest.get("event")
    if state == "cleanup_failed":
        raise RuntimeError("cleanup only required")
    if state == "publishing":
        raise RuntimeError("manual reconciliation required")
    if any(event.get("event") == "published" for event in draft_events):
        raise RuntimeError("draft already published")
    if state == "cleanup_completed":
        resume_event = latest.get("resume_event")
        if resume_event == "publishing":
            raise RuntimeError("manual reconciliation required")
        if resume_event == "publish_failed":
            return
        raise RuntimeError("draft already published")
    if state in {"revised", "held"}:
        raise RuntimeError("draft is not publishable")
    if state not in {"approved", "publish_failed"}:
        raise RuntimeError("draft is not publishable")


def load_required_env(environ: dict[str, str]) -> dict[str, str]:
    missing = [name for name in REQUIRED_ENV if not environ.get(name)]
    if missing:
        raise ValueError(
            "missing required environment variables: "
            + ", ".join(missing)
        )
    return {
        **load_r2_env(environ),
        "INSTAGRAM_USER_ID": environ["INSTAGRAM_USER_ID"],
        "INSTAGRAM_ACCESS_TOKEN": environ["INSTAGRAM_ACCESS_TOKEN"],
        "META_API_VERSION": META_API_VERSION,
    }


def load_r2_env(environ: dict[str, str]) -> dict[str, str]:
    missing = [name for name in R2_REQUIRED_ENV if not environ.get(name)]
    if missing:
        raise ValueError(
            "missing required environment variables: "
            + ", ".join(missing)
        )
    return {
        **{name: environ[name] for name in R2_REQUIRED_ENV},
        "R2_BUCKET": R2_BUCKET,
    }


def make_r2_client(env: dict[str, str]):
    endpoint = (
        f"https://{env['R2_ACCOUNT_ID']}"
        ".r2.cloudflarestorage.com"
    )
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


class R2:
    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    @staticmethod
    def _prefix(draft_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", draft_id):
            raise ValueError("draft_id is unsafe for R2 staging")
        return f"{draft_id}/"

    def upload(self, draft_id: str, files: list[Path]) -> list[str]:
        prefix = self._prefix(draft_id)
        keys = []
        for path in files:
            key = prefix + path.name
            self.client.upload_file(
                str(path),
                self.bucket,
                key,
                ExtraArgs={
                    "ContentType": "image/jpeg",
                    "CacheControl": "no-store",
                },
            )
            keys.append(key)
        return keys

    def presign(self, keys: list[str]) -> list[str]:
        return [
            self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=3600,
            )
            for key in keys
        ]

    def _list_keys(self, prefix: str) -> list[str]:
        keys = []
        continuation = None
        while True:
            arguments = {
                "Bucket": self.bucket,
                "Prefix": prefix,
            }
            if continuation:
                arguments["ContinuationToken"] = continuation
            response = self.client.list_objects_v2(**arguments)
            keys.extend(
                item["Key"] for item in response.get("Contents", [])
            )
            if not response.get("IsTruncated"):
                return keys
            continuation = response.get("NextContinuationToken")
            if not continuation:
                raise RuntimeError(
                    "R2 listing was truncated without a continuation token"
                )

    def cleanup(self, draft_id: str) -> None:
        prefix = self._prefix(draft_id)
        keys = self._list_keys(prefix)
        for start in range(0, len(keys), 1000):
            batch = keys[start : start + 1000]
            self.client.delete_objects(
                Bucket=self.bucket,
                Delete={
                    "Objects": [{"Key": key} for key in batch],
                    "Quiet": True,
                },
            )
        remaining = self._list_keys(prefix)
        if remaining:
            raise RuntimeError("R2 staging prefix is not empty")


class Instagram:
    def __init__(
        self,
        user_id: str,
        access_token: str,
        api_version: str,
        open_url=urlopen,
        sleep=time.sleep,
    ):
        self.base_url = f"https://graph.instagram.com/{api_version}"
        self.user_path = f"/{user_id}"
        self.access_token = access_token
        self.open_url = open_url
        self.sleep = sleep

    def _request(
        self,
        method: str,
        path: str,
        form: dict | None = None,
    ) -> dict:
        data = urlencode(form).encode() if form is not None else None
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": (
                    "application/x-www-form-urlencoded"
                ),
            },
        )
        try:
            with self.open_url(request, timeout=30) as response:
                try:
                    payload = json.loads(response.read())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    raise RuntimeError(
                        "Instagram returned invalid JSON"
                    ) from None
        except HTTPError as error:
            raise RuntimeError(
                f"Instagram request failed with HTTP {error.code}"
            ) from None
        except URLError:
            raise RuntimeError("Instagram request failed") from None
        if not isinstance(payload, dict):
            raise RuntimeError("Instagram returned invalid JSON")
        return payload

    @staticmethod
    def _id(payload: dict) -> str:
        value = payload.get("id")
        if not isinstance(value, str) or not value:
            raise RuntimeError("Instagram response did not contain an ID")
        return value

    def create_child(self, image_url: str) -> str:
        return self._id(
            self._request(
                "POST",
                f"{self.user_path}/media",
                {
                    "image_url": image_url,
                    "is_carousel_item": "true",
                },
            )
        )

    def wait_until_ready(self, container_id: str) -> None:
        for attempt in range(150):
            payload = self._request(
                "GET",
                f"/{container_id}?fields=status_code",
            )
            status = payload.get("status_code")
            if status == "FINISHED":
                return
            if status in {"ERROR", "EXPIRED"}:
                raise RuntimeError(
                    f"Instagram container ended with status {status}"
                )
            if attempt < 149:
                self.sleep(2)
        raise RuntimeError("Instagram container timed out")

    def create_carousel(
        self,
        child_ids: list[str],
        caption: str,
    ) -> str:
        return self._id(
            self._request(
                "POST",
                f"{self.user_path}/media",
                {
                    "media_type": "CAROUSEL",
                    "children": json.dumps(
                        child_ids,
                        separators=(",", ":"),
                    ),
                    "caption": caption,
                },
            )
        )

    def publish_carousel(self, container_id: str) -> str:
        return self._id(
            self._request(
                "POST",
                f"{self.user_path}/media_publish",
                {"creation_id": container_id},
            )
        )


def _event(draft: dict, event: str, **details) -> dict:
    return {
        "draft_id": draft["draft_id"],
        "project_id": draft["project_id"],
        "format_id": draft["format_id"],
        "event": event,
        **details,
    }


def _assert_render_record(
    draft: dict,
    files: list[Path],
    event: dict,
) -> None:
    if event.get("draft_fingerprint") != draft_fingerprint(draft):
        raise RuntimeError("rendered carousel does not match draft")
    if event.get("rendered_files") != rendered_manifest(files):
        raise RuntimeError("rendered carousel does not match files")


def _latest_event_named(
    draft_id: str,
    events: list[dict],
    name: str,
) -> dict | None:
    for event in reversed(events):
        if (
            event.get("draft_id") == draft_id
            and event.get("event") == name
        ):
            return event
    return None


def approve(
    draft: dict,
    files: list[Path],
    history: Path,
) -> None:
    with draft_lock(history, draft["draft_id"]):
        _approve_locked(draft, files, history)


def _approve_locked(
    draft: dict,
    files: list[Path],
    history: Path,
) -> None:
    events = read_events(history)
    latest = latest_event(draft["draft_id"], events)
    state = latest.get("event") if latest else None
    if state in {"approved", "publish_failed"} or (
        state == "cleanup_completed"
        and latest.get("resume_event") == "publish_failed"
    ):
        approved = _latest_event_named(
            draft["draft_id"],
            events,
            "approved",
        )
        if approved is None:
            raise RuntimeError("rendered carousel required")
        _assert_render_record(draft, files, approved)
        return
    if state != "rendered":
        raise RuntimeError("rendered carousel required")
    _assert_render_record(draft, files, latest)
    append_event(
        history,
        _event(
            draft,
            "approved",
            draft_fingerprint=latest["draft_fingerprint"],
            rendered_files=latest["rendered_files"],
        ),
    )


def assert_approved_render(
    draft: dict,
    files: list[Path],
    events: list[dict],
) -> None:
    approved = _latest_event_named(
        draft["draft_id"],
        events,
        "approved",
    )
    if approved is None:
        raise RuntimeError("final approval required")
    _assert_render_record(draft, files, approved)


def record_terminal(
    draft: dict,
    state: str,
    history: Path,
) -> None:
    with draft_lock(history, draft["draft_id"]):
        _record_terminal_locked(draft, state, history)


def _record_terminal_locked(
    draft: dict,
    state: str,
    history: Path,
) -> None:
    if state not in {"revised", "held"}:
        raise ValueError("manual state must be revised or held")
    latest = latest_event(draft["draft_id"], read_events(history))
    if latest is None or latest.get("event") not in {
        "drafted",
        "content_drafted",
        "content_approved",
        "rendered",
        "approved",
    }:
        raise RuntimeError("draft is not publishable")
    append_event(history, _event(draft, state))


def record_image_revision(draft: dict, history: Path) -> None:
    with draft_lock(history, draft["draft_id"]):
        _record_image_revision_locked(draft, history)


def _record_image_revision_locked(draft: dict, history: Path) -> None:
    events = read_events(history)
    latest = latest_event(draft["draft_id"], events)
    state = latest.get("event") if latest else None
    if state == "image_revised":
        assert_approved_content(
            draft["draft_id"],
            events,
            content_fingerprint(draft),
        )
        return
    if state not in {"rendered", "approved"}:
        raise RuntimeError("rendered carousel required")
    assert_approved_content(
        draft["draft_id"],
        events,
        content_fingerprint(draft),
    )
    append_event(history, _event(draft, "image_revised"))


def publish(
    draft: dict,
    files: list[Path],
    r2,
    instagram,
    history: Path,
    public_history: Path | None = None,
) -> str:
    with draft_lock(history, draft["draft_id"]):
        return _publish_locked(
            draft,
            files,
            r2,
            instagram,
            history,
            public_history,
        )


def _publish_locked(
    draft: dict,
    files: list[Path],
    r2,
    instagram,
    history: Path,
    public_history: Path | None,
) -> str:
    if public_history is not None and any(
        event.get("draft_id") == draft["draft_id"]
        and event.get("event") == "published"
        for event in read_events(public_history)
    ):
        raise RuntimeError("draft already published")
    events = read_events(history)
    latest = latest_event(draft["draft_id"], events)
    if latest is None or latest.get("event") != "rendered":
        assert_publishable(draft["draft_id"], events)
    _approve_locked(draft, files, history)
    assert_publishable(draft["draft_id"], read_events(history))
    assert_approved_render(draft, files, read_events(history))

    media_id = None
    original_error = None
    cleanup_error = None
    cleanup_needed = True
    try:
        keys = r2.upload(draft["draft_id"], files)
        urls = r2.presign(keys)
        child_ids = [
            instagram.create_child(url) for url in urls
        ]
        for child_id in child_ids:
            instagram.wait_until_ready(child_id)
        parent_id = instagram.create_carousel(
            child_ids,
            draft["caption"],
        )
        instagram.wait_until_ready(parent_id)
        append_event(
            history,
            _event(
                draft,
                "publishing",
                container_id=parent_id,
            ),
        )
        media_id = instagram.publish_carousel(parent_id)
        append_event(
            history,
            _event(
                draft,
                "published",
                container_id=parent_id,
                instagram_media_id=media_id,
            ),
        )
        if public_history is not None:
            append_event(
                public_history,
                _event(
                    draft,
                    "published",
                    instagram_media_id=media_id,
                ),
            )
    except Exception as error:
        original_error = error
        state = latest_event(
            draft["draft_id"],
            read_events(history),
        ).get("event")
        if state not in {"publishing", "published"}:
            append_event(history, _event(draft, "publish_failed"))
    finally:
        if cleanup_needed:
            try:
                r2.cleanup(draft["draft_id"])
            except Exception as error:
                cleanup_error = error
                current = latest_event(
                    draft["draft_id"],
                    read_events(history),
                )
                resume_event = current.get("event")
                details = {"resume_event": resume_event}
                if media_id:
                    details["instagram_media_id"] = media_id
                append_event(
                    history,
                    _event(draft, "cleanup_failed", **details),
                )

    if cleanup_error is not None:
        if media_id:
            raise RuntimeError(
                "published but staging cleanup failed; "
                f"run --cleanup-only {draft['draft_id']}"
            ) from None
        if original_error is not None:
            raise RuntimeError(
                "publication failed and staging cleanup failed; "
                f"run --cleanup-only {draft['draft_id']}"
            ) from None
        raise RuntimeError(
            "staging cleanup failed; "
            f"run --cleanup-only {draft['draft_id']}"
        ) from None
    if original_error is not None:
        raise original_error
    if not media_id:
        raise RuntimeError(
            "Instagram publish returned no media ID"
        )
    return media_id


def cleanup_only(draft_id: str, r2, history: Path) -> None:
    with draft_lock(history, draft_id):
        _cleanup_only_locked(draft_id, r2, history)


def _cleanup_only_locked(draft_id: str, r2, history: Path) -> None:
    latest = latest_event(draft_id, read_events(history))
    if latest is None or latest.get("event") != "cleanup_failed":
        raise RuntimeError("cleanup-only requires cleanup_failed state")
    r2.cleanup(draft_id)
    event = {
        "draft_id": draft_id,
        "event": "cleanup_completed",
        "resume_event": latest.get("resume_event"),
    }
    for field in (
        "project_id",
        "format_id",
        "instagram_media_id",
    ):
        if field in latest:
            event[field] = latest[field]
    append_event(history, event)


def verify_rendered(
    draft: dict,
    rendered_dir: Path,
) -> list[Path]:
    files = sorted(rendered_dir.glob("*.jpg"))
    expected_names = [
        f"{index:02}.jpg"
        for index in range(1, len(draft["slides"]) + 1)
    ]
    if [path.name for path in files] != expected_names:
        raise ValueError(
            "rendered JPEGs must exactly match the draft slide order"
        )
    for path in files:
        with Image.open(path) as image:
            if image.format != "JPEG" or image.size != (1080, 1350):
                raise ValueError(
                    f"{path.name} must be 1080x1350 JPEG"
                )
    return files


def _r2(env: dict[str, str]) -> R2:
    return R2(make_r2_client(env), env["R2_BUCKET"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", nargs="?", type=Path)
    parser.add_argument("rendered", nargs="?", type=Path)
    parser.add_argument("--cleanup-only", metavar="DRAFT_ID")
    parser.add_argument(
        "--record-state",
        choices=("revised", "held", "image-revised"),
    )
    args = parser.parse_args()
    try:
        if args.record_state:
            if args.draft is None or args.rendered is not None:
                raise ValueError(
                    "--record-state requires one draft JSON path"
                )
            draft = load_json(args.draft)
            if args.record_state == "image-revised":
                record_image_revision(draft, HISTORY_PATH)
            else:
                record_terminal(
                    draft,
                    args.record_state,
                    HISTORY_PATH,
                )
            print(
                f"recorded {args.record_state} for "
                f"{draft['draft_id']}"
            )
            return 0
        if args.cleanup_only:
            env = load_r2_env(dict(os.environ))
            r2 = _r2(env)
            cleanup_only(args.cleanup_only, r2, HISTORY_PATH)
            print(f"cleaned R2 staging for {args.cleanup_only}")
            return 0
        if args.draft is None or args.rendered is None:
            raise ValueError("draft and rendered directory are required")
        draft_id = load_json(args.draft).get("draft_id")
        if not isinstance(draft_id, str):
            raise ValueError("draft_id must be a string")
        with draft_lock(HISTORY_PATH, draft_id):
            errors = validate_file(args.draft)
            if errors:
                raise ValueError("\n".join(errors))
            draft = load_json(args.draft)
            if draft.get("draft_id") != draft_id:
                raise RuntimeError("draft changed while acquiring lock")
            files = verify_rendered(draft, args.rendered)
            env = load_required_env(dict(os.environ))
            r2 = _r2(env)
            instagram = Instagram(
                env["INSTAGRAM_USER_ID"],
                env["INSTAGRAM_ACCESS_TOKEN"],
                env["META_API_VERSION"],
            )
            media_id = _publish_locked(
                draft,
                files,
                r2,
                instagram,
                HISTORY_PATH,
                PUBLIC_HISTORY_PATH,
            )
        print(f"published Instagram media {media_id}; R2 prefix empty")
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
