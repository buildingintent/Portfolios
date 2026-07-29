#!/usr/bin/env python3
import argparse
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


def _place_illustration(
    canvas: Image.Image,
    source: Path,
    box: tuple[int, int, int, int],
) -> None:
    x1, y1, x2, y2 = box
    with Image.open(source) as opened:
        image = ImageOps.fit(
            opened.convert("RGB"),
            (x2 - x1, y2 - y1),
            Image.Resampling.LANCZOS,
        )
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, image.width, image.height),
        radius=44,
        fill=255,
    )
    canvas.paste(image, (x1, y1), mask)


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
    palette = project["palette"]
    draw = ImageDraw.Draw(canvas)
    _place_illustration(
        canvas,
        work_dir / slide["illustration"],
        (SAFE[0], 104, SAFE[2], 724),
    )
    headline_font = _font(76, bold=True)
    body_font = _font(46)
    max_width = SAFE[2] - SAFE[0]
    headline = wrap_text(
        draw,
        slide["headline"],
        headline_font,
        max_width,
    )
    if _text_height(draw, headline, headline_font, 8) > 196:
        raise ValueError("text does not fit safe area")
    next_y = _draw_lines(
        draw,
        headline,
        (SAFE[0], 782),
        headline_font,
        palette["ink"],
        8,
    )
    body = wrap_text(draw, slide["body"], body_font, max_width)
    if _text_height(draw, body, body_font, 10) > 190:
        raise ValueError("text does not fit safe area")
    body_bottom = _draw_lines(
        draw,
        body,
        (SAFE[0], next_y + 34),
        body_font,
        palette["ink"],
        10,
    )
    if body_bottom > 1194:
        raise ValueError("text does not fit safe area")


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
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (SAFE[0], 52, SAFE[0] + 112, 66),
        radius=7,
        fill=palette["accent"],
    )
    if slide["kind"] == "cta":
        _render_cta(canvas, slide, project)
    else:
        _render_content(canvas, slide, project, work_dir)

    number_font = _font(34, bold=True)
    number = f"{index}/{total}"
    number_box = draw.textbbox((0, 0), number, font=number_font)
    draw.text(
        (SAFE[2] - (number_box[2] - number_box[0]), 1230),
        number,
        font=number_font,
        fill=palette["ink"],
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
    outputs = render_draft(
        draft,
        project,
        draft_path.parent,
        output_dir,
    )
    if not any(
        event.get("draft_id") == draft["draft_id"]
        for event in read_events(history_path)
    ):
        append_event(
            history_path,
            {
                "draft_id": draft["draft_id"],
                "project_id": draft["project_id"],
                "format_id": draft["format_id"],
                "event": "drafted",
            },
        )
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("draft", type=Path)
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("draft", type=Path)
    render_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

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
