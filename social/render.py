#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "projects.json"
HISTORY_PATH = ROOT / "history.jsonl"
TIMEZONE = ZoneInfo("America/Vancouver")
CANVAS = (1080, 1350)
FONT = Path(
    "/usr/share/fonts/truetype/ubuntu/"
    "UbuntuSans[wdth,wght].ttf"
)
SAFE = (88, 88, 992, 1262)
BADGE = ROOT / "assets/app-store-badge.png"


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


def append_event(path: Path, event: dict) -> None:
    record = dict(event)
    record.setdefault("at", datetime.now(TIMEZONE).isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as history:
        history.write(json.dumps(record, separators=(",", ":")) + "\n")
        history.flush()
        os.fsync(history.fileno())


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


def _content_fingerprint(draft: dict) -> str:
    content = {
        key: value
        for key, value in draft.items()
        if key != "art_direction"
    }
    slides = content.get("slides")
    if isinstance(slides, list):
        content["slides"] = [
            {
                key: value
                for key, value in slide.items()
                if key not in {
                    "alt_text",
                    "illustration",
                    "scene",
                    "text_layout",
                }
            }
            if isinstance(slide, dict)
            else slide
            for slide in slides
        ]
    encoded = json.dumps(
        content,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _assert_approved_content(
    draft_id: str,
    events: list[dict],
    content_fingerprint: str,
) -> None:
    for event in reversed(events):
        if (
            event.get("draft_id") == draft_id
            and event.get("event") == "content_approved"
        ):
            if event.get("content_fingerprint") != content_fingerprint:
                raise RuntimeError("content approval does not match draft")
            return
    raise RuntimeError("content approval required")


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
    event = _draft_event(draft, state)
    if state == "content_approved":
        event["content_fingerprint"] = _content_fingerprint(draft)
    append_event(history, event)


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
    _assert_approved_content(
        draft["draft_id"],
        events,
        _content_fingerprint(draft),
    )
    event = _draft_event(draft, "rendered")
    event["art_direction"] = draft["art_direction"]
    event["scenes"] = [
        slide["scene"]
        for slide in draft["slides"]
        if slide["kind"] != "cta"
    ]
    append_event(history, event)


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


def validate_content(
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

    draft_id = draft.get("draft_id")
    if (
        isinstance(draft_id, str)
        and not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]*",
            draft_id,
        )
    ):
        errors.append(
            "draft_id may contain only letters, numbers, dots, "
            "dashes, and underscores"
        )

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
        for field in ("headline", "body"):
            if not _non_empty_string(slide.get(field)):
                errors.append(
                    f"slide {index + 1} {field} must be a non-empty string"
                )
        if expected_kind != "cta":
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


def validate_draft(
    draft: dict,
    project: dict,
    blocked_formats: set[str],
) -> list[str]:
    errors = validate_content(draft, project, blocked_formats)
    if not _non_empty_string(draft.get("art_direction")):
        errors.append("art_direction must be a non-empty string")
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
            if not _non_empty_string(slide.get("scene")):
                errors.append(
                    f"slide {index} scene must be a non-empty string"
                )
            layout = slide.get("text_layout")
            headline = layout.get("headline") if isinstance(layout, dict) else None
            body = layout.get("body") if isinstance(layout, dict) else None
            headline_errors = _text_region_errors(headline, 52, 104)
            body_errors = _text_region_errors(body, 30, 60)
            errors.extend(headline_errors)
            errors.extend(body_errors)
            if (
                isinstance(headline, dict)
                and isinstance(body, dict)
                and "text region must stay inside the canvas"
                not in headline_errors + body_errors
                and _boxes_overlap(headline["box"], body["box"])
            ):
                errors.append(
                    "headline and body text regions must not overlap"
                )
        elif "illustration" in slide:
            errors.append("CTA slide must not include an illustration")
    return list(dict.fromkeys(errors))


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


def _font(size: int, bold: bool = False):
    font = ImageFont.truetype(FONT, size)
    if bold:
        try:
            font.set_variation_by_name("Bold")
        except (AttributeError, OSError):
            pass
    return font


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    lines = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width:
            current = candidate
            continue
        if not current:
            raise ValueError("text does not fit safe area")
        lines.append(current)
        current = word
        if draw.textbbox((0, 0), current, font=font)[2] > max_width:
            raise ValueError("text does not fit safe area")
    if current:
        lines.append(current)
    return lines


def _text_height(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    spacing: int,
) -> int:
    heights = [
        draw.textbbox((0, 0), line, font=font)[3]
        for line in lines
    ]
    return sum(heights) + spacing * max(0, len(lines) - 1)


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    position: tuple[int, int],
    font: ImageFont.FreeTypeFont,
    fill: str,
    spacing: int,
) -> int:
    x, y = position
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += draw.textbbox((0, 0), line, font=font)[3] + spacing
    return y - spacing


def _place_full_bleed(canvas: Image.Image, source: Path) -> None:
    with Image.open(source) as opened:
        image = ImageOps.fit(
            opened.convert("RGB"),
            CANVAS,
            Image.Resampling.LANCZOS,
        )
    canvas.paste(image, (0, 0))


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
        draw.text((x, y), line, font=font, fill=region["color"])
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


def _resized_asset(path: Path, width: int) -> Image.Image:
    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _render_content(
    canvas: Image.Image,
    slide: dict,
    project: dict,
    work_dir: Path,
) -> None:
    _place_full_bleed(canvas, work_dir / slide["illustration"])
    _draw_text_region(
        canvas,
        slide["headline"],
        slide["text_layout"]["headline"],
        bold=True,
    )
    _draw_text_region(
        canvas,
        slide["body"],
        slide["text_layout"]["body"],
        bold=False,
    )


def _render_cta(
    canvas: Image.Image,
    slide: dict,
    project: dict,
) -> None:
    palette = project["palette"]
    draw = ImageDraw.Draw(canvas)
    logo = _resized_asset(ROOT / project["logo"], 252)
    canvas.paste(logo, (SAFE[0], 132), logo)

    headline_font = _font(82, bold=True)
    body_font = _font(48)
    max_width = SAFE[2] - SAFE[0]
    headline = wrap_text(
        draw,
        slide["headline"],
        headline_font,
        max_width,
    )
    if _text_height(draw, headline, headline_font, 8) > 210:
        raise ValueError("text does not fit safe area")
    next_y = _draw_lines(
        draw,
        headline,
        (SAFE[0], 482),
        headline_font,
        palette["ink"],
        8,
    )
    body = wrap_text(draw, slide["body"], body_font, max_width)
    if _text_height(draw, body, body_font, 10) > 188:
        raise ValueError("text does not fit safe area")
    body_bottom = _draw_lines(
        draw,
        body,
        (SAFE[0], next_y + 36),
        body_font,
        palette["ink"],
        10,
    )

    badge = _resized_asset(BADGE, 360)
    badge_y = max(body_bottom + badge.height // 4, 932)
    if badge_y + badge.height > 1194:
        raise ValueError("text does not fit safe area")
    canvas.paste(badge, (SAFE[0], badge_y), badge)


def render_slide(
    slide: dict,
    project: dict,
    index: int,
    total: int,
    work_dir: Path,
    output_path: Path,
) -> Path:
    palette = project["palette"]
    canvas = Image.new(
        "RGB",
        CANVAS,
        ImageColor.getrgb(palette["background"]),
    )
    if slide["kind"] == "cta":
        _render_cta(canvas, slide, project)
    else:
        _render_content(canvas, slide, project, work_dir)

    draw = ImageDraw.Draw(canvas)
    number_font = _font(34, bold=True)
    number = f"{index}/{total}"
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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(
        output_path,
        "JPEG",
        quality=92,
        subsampling=0,
        exif=b"",
    )
    return output_path


def render_draft(
    draft: dict,
    project: dict,
    work_dir: Path,
    output_dir: Path,
) -> list[Path]:
    outputs = []
    total = len(draft["slides"])
    for index, slide in enumerate(draft["slides"], start=1):
        outputs.append(
            render_slide(
                slide,
                project,
                index,
                total,
                work_dir,
                output_dir / f"{index:02}.jpg",
            )
        )
    return outputs


def _project(config: dict, project_id: str) -> dict:
    for project in config.get("projects", []):
        if project.get("id") == project_id:
            return project
    raise ValueError(f"unknown project_id: {project_id}")


def validate_file(
    draft_path: Path,
    config_path: Path = CONFIG_PATH,
    history_path: Path = HISTORY_PATH,
) -> list[str]:
    config = load_json(config_path)
    draft = load_json(draft_path)
    project = _project(config, draft.get("project_id", ""))
    errors = validate_draft(
        draft,
        project,
        recent_published_formats(
            read_events(history_path),
            datetime.now(TIMEZONE),
        ),
    )
    if draft.get("format_id") not in config.get("formats", []):
        errors.append("format_id is not configured")
    errors.extend(validate_illustrations(draft, draft_path.parent))
    return errors


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


def render_file(
    draft_path: Path,
    output_dir: Path,
    config_path: Path = CONFIG_PATH,
    history_path: Path = HISTORY_PATH,
) -> list[Path]:
    config = load_json(config_path)
    draft = load_json(draft_path)
    project = _project(config, draft.get("project_id", ""))
    errors = validate_file(draft_path, config_path, history_path)
    if errors:
        raise ValueError("\n".join(errors))
    events = read_events(history_path)
    latest = latest_event(draft["draft_id"], events)
    if latest is None or latest.get("event") != "rendered":
        assert_renderable(draft["draft_id"], events)
    _assert_approved_content(
        draft["draft_id"],
        events,
        _content_fingerprint(draft),
    )
    outputs = render_draft(
        draft,
        project,
        draft_path.parent,
        output_dir,
    )
    mark_rendered(draft, history_path)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("draft", type=Path)
    record_parser = subparsers.add_parser("record-content")
    record_parser.add_argument("draft", type=Path)
    approve_parser = subparsers.add_parser("approve-content")
    approve_parser.add_argument("draft", type=Path)
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("draft", type=Path)
    render_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

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
    if args.command == "validate":
        errors = validate_file(args.draft)
        if errors:
            for error in errors:
                print(error)
            return 2
        print("draft valid")
        return 0
    if args.command == "render":
        try:
            outputs = render_file(args.draft, args.output)
        except ValueError as error:
            print(error)
            return 2
        print(f"rendered {len(outputs)} slides to {args.output}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
