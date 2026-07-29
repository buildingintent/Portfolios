#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "projects.json"
HISTORY_PATH = ROOT / "history.jsonl"
TIMEZONE = ZoneInfo("America/Vancouver")


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError(
                f"history line {line_number} must be a JSON object"
            )
        events.append(event)
    return events


def recent_published_formats(
    events: list[dict],
    now: datetime,
) -> set[str]:
    cutoff = now - timedelta(days=14)
    blocked = set()
    for event in events:
        if event.get("event") != "published":
            continue
        published_at = datetime.fromisoformat(event["at"])
        if published_at >= cutoff:
            blocked.add(event["format_id"])
    return blocked


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _mentions_app(text: str, app_name: str) -> bool:
    words = re.escape(app_name).replace(r"\ ", r"\s+")
    return re.search(
        rf"(?<!\w){words}(?!\w)",
        text,
        flags=re.IGNORECASE,
    ) is not None


def _safe_illustration_path(value: Any) -> bool:
    if not _non_empty_string(value):
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and path.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )


def validate_draft(
    draft: dict,
    project: dict,
    blocked_formats: set[str],
) -> list[str]:
    errors = []
    if not isinstance(draft, dict):
        return ["draft must be a JSON object"]

    for field in (
        "draft_id",
        "project_id",
        "format_id",
        "hook",
        "caption",
    ):
        if not _non_empty_string(draft.get(field)):
            errors.append(f"{field} must be a non-empty string")

    if draft.get("project_id") != project.get("id"):
        errors.append("project_id does not match the selected project")

    if draft.get("format_id") in blocked_formats:
        errors.append("format was published within the previous 14 days")

    caption = draft.get("caption")
    if isinstance(caption, str):
        if project.get("app_store_url") not in caption:
            errors.append(
                "caption must contain the project's App Store URL"
            )
        if "link in bio" not in caption.casefold():
            errors.append("caption must mention link in bio")
        if len(caption) > 2200:
            errors.append("caption must be at most 2200 characters")

    slides = draft.get("slides")
    if not isinstance(slides, list):
        return errors + ["slides must be an array"]
    if not 4 <= len(slides) <= 10:
        errors.append("draft must contain 4 to 10 slides")
    if not slides:
        return errors

    if not isinstance(slides[0], dict) or slides[0].get("kind") != "hook":
        errors.append("first slide must be hook")
    if not isinstance(slides[-1], dict) or slides[-1].get("kind") != "cta":
        errors.append("last slide must be cta")

    app_name = project.get("name", "")
    for index, slide in enumerate(slides):
        if not isinstance(slide, dict):
            errors.append(f"slide {index + 1} must be an object")
            continue
        expected_kind = (
            "hook"
            if index == 0
            else "cta"
            if index == len(slides) - 1
            else "content"
        )
        if slide.get("kind") != expected_kind:
            errors.append(
                f"slide {index + 1} must have kind {expected_kind}"
            )
        for field in ("headline", "body", "alt_text"):
            if not _non_empty_string(slide.get(field)):
                errors.append(
                    f"slide {index + 1} {field} must be a non-empty string"
                )
        if expected_kind != "cta":
            if not _safe_illustration_path(slide.get("illustration")):
                errors.append(
                    "illustration paths must stay inside the draft directory"
                )
            copy = " ".join(
                value
                for value in (
                    slide.get("headline"),
                    slide.get("body"),
                )
                if isinstance(value, str)
            )
            if app_name and _mentions_app(copy, app_name):
                errors.append(
                    "app name may appear only on the CTA slide"
                )
        else:
            if "illustration" in slide:
                errors.append("CTA slide must not include an illustration")
            copy = " ".join(
                value
                for value in (
                    slide.get("headline"),
                    slide.get("body"),
                )
                if isinstance(value, str)
            )
            if app_name and not _mentions_app(copy, app_name):
                errors.append("CTA slide must name the app")
    return list(dict.fromkeys(errors))


def validate_illustrations(draft: dict, draft_dir: Path) -> list[str]:
    errors = []
    for slide in draft.get("slides", []):
        if not isinstance(slide, dict) or slide.get("kind") == "cta":
            continue
        illustration = slide.get("illustration")
        if _safe_illustration_path(illustration):
            if not (draft_dir / illustration).is_file():
                errors.append(f"missing illustration: {illustration}")
    return errors


def _project(config: dict, project_id: str) -> dict:
    for project in config.get("projects", []):
        if project.get("id") == project_id:
            return project
    raise ValueError(f"unknown project_id: {project_id}")


def validate_file(draft_path: Path) -> list[str]:
    config = load_json(CONFIG_PATH)
    draft = load_json(draft_path)
    project = _project(config, draft.get("project_id", ""))
    errors = validate_draft(
        draft,
        project,
        recent_published_formats(
            read_events(HISTORY_PATH),
            datetime.now(TIMEZONE),
        ),
    )
    if draft.get("format_id") not in config.get("formats", []):
        errors.append("format_id is not configured")
    errors.extend(validate_illustrations(draft, draft_path.parent))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("draft", type=Path)
    args = parser.parse_args()

    if args.command == "validate":
        errors = validate_file(args.draft)
        if errors:
            for error in errors:
                print(error)
            return 2
        print("draft valid")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
