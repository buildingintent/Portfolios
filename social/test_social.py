import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from social.render import (
    load_json,
    read_events,
    recent_published_formats,
    validate_draft,
    validate_illustrations,
)


class DraftValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    @staticmethod
    def project():
        return {
            "id": "fina",
            "name": "Fina",
            "app_store_url": (
                "https://apps.apple.com/us/app/"
                "fina-financial-companion/id6778169653"
            ),
        }

    @staticmethod
    def valid_draft():
        return {
            "draft_id": "2026-07-30-fina-01",
            "project_id": "fina",
            "format_id": "what-happens-next",
            "hook": "Your balance looks fine. Next Tuesday might not.",
            "caption": (
                "A balance is a snapshot. Find Fina through the link in bio "
                "or on the App Store: "
                "https://apps.apple.com/us/app/"
                "fina-financial-companion/id6778169653"
            ),
            "slides": [
                {
                    "kind": "hook",
                    "headline": "Your balance looks fine.",
                    "body": "Next Tuesday might not.",
                    "illustration": "art-01.png",
                    "alt_text": "A person looking ahead at approaching bills.",
                },
                {
                    "kind": "content",
                    "headline": "Today",
                    "body": "Some of that balance is already spoken for.",
                    "illustration": "art-02.png",
                    "alt_text": "Envelopes beside a current balance.",
                },
                {
                    "kind": "content",
                    "headline": "Next Tuesday",
                    "body": "Two automatic payments arrive together.",
                    "illustration": "art-03.png",
                    "alt_text": "Two bills landing on one calendar date.",
                },
                {
                    "kind": "cta",
                    "headline": "See it coming with Fina.",
                    "body": "Forecast upcoming pressure before it becomes a problem.",
                    "alt_text": "Fina logo and a Download on the App Store badge.",
                },
            ],
        }

    def test_accepts_valid_variable_length_draft(self):
        self.assertEqual(
            validate_draft(self.valid_draft(), self.project(), set()),
            [],
        )

    def test_rejects_wrong_slide_order_and_count(self):
        draft = self.valid_draft()
        draft["slides"] = draft["slides"][:3]
        draft["slides"][0]["kind"] = "content"

        errors = validate_draft(draft, self.project(), set())

        self.assertIn("draft must contain 4 to 10 slides", errors)
        self.assertIn("first slide must be hook", errors)

    def test_rejects_product_mention_before_cta(self):
        draft = self.valid_draft()
        draft["slides"][1]["body"] = "Fina fixes this."

        self.assertIn(
            "app name may appear only on the CTA slide",
            validate_draft(draft, self.project(), set()),
        )

    def test_rejects_format_published_within_fourteen_days(self):
        errors = validate_draft(
            self.valid_draft(),
            self.project(),
            {"what-happens-next"},
        )

        self.assertIn(
            "format was published within the previous 14 days",
            errors,
        )

    def test_requires_exact_app_store_url_and_profile_link_in_caption(self):
        draft = self.valid_draft()
        draft["caption"] = "Read the carousel."

        errors = validate_draft(draft, self.project(), set())

        self.assertIn(
            "caption must contain the project's App Store URL",
            errors,
        )
        self.assertIn("caption must mention link in bio", errors)

    def test_rejects_unsafe_illustration_path(self):
        draft = self.valid_draft()
        draft["slides"][1]["illustration"] = "../private.png"

        self.assertIn(
            "illustration paths must stay inside the draft directory",
            validate_draft(draft, self.project(), set()),
        )

    def test_rejects_missing_illustration_file(self):
        draft = self.valid_draft()
        for filename in ("art-01.png", "art-02.png"):
            (self.root / filename).write_bytes(b"present")

        self.assertEqual(
            validate_illustrations(draft, self.root),
            ["missing illustration: art-03.png"],
        )

    def test_recent_formats_only_returns_recent_published_events(self):
        events = [
            {
                "event": "published",
                "format_id": "recent",
                "at": "2026-07-20T08:00:00-07:00",
            },
            {
                "event": "published",
                "format_id": "old",
                "at": "2026-07-01T08:00:00-07:00",
            },
            {
                "event": "drafted",
                "format_id": "not-published",
                "at": "2026-07-28T08:00:00-07:00",
            },
        ]
        now = datetime(
            2026,
            7,
            29,
            8,
            0,
            tzinfo=ZoneInfo("America/Vancouver"),
        )

        self.assertEqual(
            recent_published_formats(events, now),
            {"recent"},
        )

    def test_reads_blank_lines_and_rejects_non_object_json(self):
        history = self.root / "history.jsonl"
        history.write_text(
            '\n{"event":"drafted","draft_id":"d1"}\n',
            encoding="utf-8",
        )
        invalid = self.root / "invalid.json"
        invalid.write_text("[]", encoding="utf-8")

        self.assertEqual(
            read_events(history),
            [{"event": "drafted", "draft_id": "d1"}],
        )
        with self.assertRaisesRegex(ValueError, "JSON root must be an object"):
            load_json(invalid)

    def test_does_not_mutate_draft_during_validation(self):
        draft = self.valid_draft()
        before = copy.deepcopy(draft)

        validate_draft(draft, self.project(), set())

        self.assertEqual(draft, before)


if __name__ == "__main__":
    unittest.main()
