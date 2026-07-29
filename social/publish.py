#!/usr/bin/env python3
from social.render import append_event, read_events


def latest_event(draft_id: str, events: list[dict]) -> dict | None:
    for event in reversed(events):
        if event.get("draft_id") == draft_id:
            return event
    return None


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
        raise RuntimeError("draft already published")
    if state in {"revised", "held"}:
        raise RuntimeError("draft is not publishable")
    if state not in {"drafted", "approved", "publish_failed"}:
        raise RuntimeError("draft is not publishable")
