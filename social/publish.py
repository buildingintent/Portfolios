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
    append_event,
    latest_event,
    load_json,
    read_events,
    validate_file,
)


HISTORY_PATH = Path(__file__).resolve().parent / "history.jsonl"
META_API_VERSION = "v23.0"
R2_BUCKET = "building-intent-social"
REQUIRED_ENV = (
    "INSTAGRAM_USER_ID",
    "INSTAGRAM_ACCESS_TOKEN",
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
        **{name: environ[name] for name in REQUIRED_ENV},
        "META_API_VERSION": META_API_VERSION,
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


def approve(draft: dict, history: Path) -> None:
    events = read_events(history)
    latest = latest_event(draft["draft_id"], events)
    state = latest.get("event") if latest else None
    if state in {"approved", "publish_failed"}:
        return
    if state != "rendered":
        raise RuntimeError("rendered carousel required")
    append_event(history, _event(draft, "approved"))


def record_terminal(
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


def publish(
    draft: dict,
    files: list[Path],
    r2,
    instagram,
    history: Path,
) -> str:
    approve(draft, history)
    assert_publishable(draft["draft_id"], read_events(history))

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
                "published but staging cleanup failed"
            ) from None
        if original_error is None:
            raise cleanup_error
    if original_error is not None:
        raise original_error
    if not media_id:
        raise RuntimeError(
            "Instagram publish returned no media ID"
        )
    return media_id


def cleanup_only(draft_id: str, r2, history: Path) -> None:
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
        choices=("revised", "held"),
    )
    args = parser.parse_args()
    try:
        if args.record_state:
            if args.draft is None or args.rendered is not None:
                raise ValueError(
                    "--record-state requires one draft JSON path"
                )
            draft = load_json(args.draft)
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
            env = load_required_env(dict(os.environ))
            r2 = _r2(env)
            cleanup_only(args.cleanup_only, r2, HISTORY_PATH)
            print(f"cleaned R2 staging for {args.cleanup_only}")
            return 0
        if args.draft is None or args.rendered is None:
            raise ValueError("draft and rendered directory are required")
        errors = validate_file(args.draft)
        if errors:
            raise ValueError("\n".join(errors))
        draft = load_json(args.draft)
        files = verify_rendered(draft, args.rendered)
        approve(draft, HISTORY_PATH)
        env = load_required_env(dict(os.environ))
        r2 = _r2(env)
        instagram = Instagram(
            env["INSTAGRAM_USER_ID"],
            env["INSTAGRAM_ACCESS_TOKEN"],
            env["META_API_VERSION"],
        )
        media_id = publish(
            draft,
            files,
            r2,
            instagram,
            HISTORY_PATH,
        )
        print(f"published Instagram media {media_id}; R2 prefix empty")
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
