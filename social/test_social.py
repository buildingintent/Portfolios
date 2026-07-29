import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs
from zoneinfo import ZoneInfo

from PIL import Image

from social.render import (
    assert_renderable,
    load_json,
    latest_event,
    mark_rendered,
    read_events,
    record_content_state,
    recent_published_formats,
    render_draft,
    render_file,
    render_slide,
    validate_content,
    validate_draft,
    validate_illustrations,
)
from social.publish import (
    Instagram,
    R2,
    approve,
    append_event,
    assert_publishable,
    cleanup_only,
    load_required_env,
    publish,
    record_terminal,
    verify_rendered,
)


def content_only_draft():
    draft = DraftValidationTests.valid_draft()
    draft.pop("art_direction", None)
    for slide in draft["slides"]:
        slide.pop("alt_text", None)
        slide.pop("illustration", None)
        slide.pop("scene", None)
        slide.pop("text_layout", None)
    return draft


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

    def test_accepts_content_before_art_exists(self):
        self.assertEqual(
            validate_content(
                content_only_draft(),
                self.project(),
                set(),
            ),
            [],
        )

    def test_render_ready_validation_still_requires_art_fields(self):
        errors = validate_draft(
            content_only_draft(),
            self.project(),
            set(),
        )

        self.assertIn(
            "slide 1 alt_text must be a non-empty string",
            errors,
        )
        self.assertIn(
            "illustration paths must stay inside the draft directory",
            errors,
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

    def test_rejects_draft_id_that_is_unsafe_for_staging(self):
        draft = self.valid_draft()
        draft["draft_id"] = "../fina"

        self.assertIn(
            "draft_id may contain only letters, numbers, dots, dashes, and underscores",
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


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.work_dir = Path(self.temp_dir.name)
        self.output_dir = self.work_dir / "rendered"
        for index, color in enumerate(
            ("#D7E7D0", "#F0C9A8", "#C9D9EA"),
            start=1,
        ):
            Image.new("RGB", (900, 700), color).save(
                self.work_dir / f"art-{index:02}.png"
            )

    @staticmethod
    def project():
        project = DraftValidationTests.project()
        project.update(
            {
                "logo": "assets/fina/logo.png",
                "positioning": (
                    "Forecast upcoming financial pressure before it "
                    "becomes a problem."
                ),
                "palette": {
                    "background": "#F5F1E8",
                    "accent": "#7A8F72",
                    "ink": "#242621",
                },
            }
        )
        return project

    @staticmethod
    def valid_draft():
        return DraftValidationTests.valid_draft()

    def test_render_outputs_numbered_1080_by_1350_jpegs(self):
        outputs = render_draft(
            self.valid_draft(),
            self.project(),
            self.work_dir,
            self.output_dir,
        )

        self.assertEqual(
            [path.name for path in outputs],
            ["01.jpg", "02.jpg", "03.jpg", "04.jpg"],
        )
        for path in outputs:
            with Image.open(path) as image:
                self.assertEqual(image.size, (1080, 1350))
                self.assertEqual(image.format, "JPEG")
                self.assertEqual(dict(image.getexif()), {})

    def test_cta_uses_logo_and_badge_without_illustration(self):
        output = render_slide(
            self.valid_draft()["slides"][-1],
            self.project(),
            4,
            4,
            self.work_dir,
            self.output_dir / "04.jpg",
        )

        with Image.open(output) as image:
            colors = image.resize((108, 135)).getcolors(maxcolors=20_000)
        self.assertEqual(output.name, "04.jpg")
        self.assertGreater(len(colors), 10)

    def test_rejects_copy_that_cannot_fit_safe_area(self):
        draft = self.valid_draft()
        draft["slides"][1]["headline"] = "word " * 80

        with self.assertRaisesRegex(ValueError, "text does not fit"):
            render_draft(
                draft,
                self.project(),
                self.work_dir,
                self.output_dir,
            )

    def test_render_file_records_rendered_only_once(self):
        draft_path = self.work_dir / "draft.json"
        draft_path.write_text(
            json.dumps(self.valid_draft()),
            encoding="utf-8",
        )
        config_path = self.work_dir / "projects.json"
        config_path.write_text(
            json.dumps(
                {
                    "formats": ["what-happens-next"],
                    "projects": [self.project()],
                }
            ),
            encoding="utf-8",
        )
        history_path = self.work_dir / "history.jsonl"
        draft = self.valid_draft()
        record_content_state(draft, "content_drafted", history_path)
        record_content_state(draft, "content_approved", history_path)

        for _ in range(2):
            render_file(
                draft_path,
                self.output_dir,
                config_path=config_path,
                history_path=history_path,
            )

        events = read_events(history_path)
        self.assertEqual(
            [event["event"] for event in events],
            ["content_drafted", "content_approved", "rendered"],
        )
        self.assertEqual(events[-1]["draft_id"], "2026-07-30-fina-01")


class PublicationStateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.history = self.root / "history.jsonl"

    def test_published_draft_cannot_publish_twice(self):
        append_event(
            self.history,
            {
                "draft_id": "d1",
                "event": "published",
                "instagram_media_id": "m1",
            },
        )

        with self.assertRaisesRegex(RuntimeError, "already published"):
            assert_publishable("d1", read_events(self.history))

    def test_uncertain_publishing_state_blocks_automatic_retry(self):
        append_event(
            self.history,
            {
                "draft_id": "d1",
                "event": "publishing",
                "container_id": "c1",
            },
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "manual reconciliation required",
        ):
            assert_publishable("d1", read_events(self.history))

    def test_revised_or_held_draft_cannot_publish(self):
        for state in ("revised", "held"):
            history = self.root / f"{state}.jsonl"
            append_event(
                history,
                {"draft_id": "d1", "event": state},
            )
            with self.assertRaisesRegex(RuntimeError, "not publishable"):
                assert_publishable("d1", read_events(history))

    def test_cleanup_failure_requires_cleanup_only(self):
        append_event(
            self.history,
            {
                "draft_id": "d1",
                "event": "published",
                "instagram_media_id": "m1",
            },
        )
        append_event(
            self.history,
            {
                "draft_id": "d1",
                "event": "cleanup_failed",
                "instagram_media_id": "m1",
            },
        )

        with self.assertRaisesRegex(RuntimeError, "cleanup only required"):
            assert_publishable("d1", read_events(self.history))

    def test_only_safe_states_can_start_publish(self):
        for state in ("approved", "publish_failed"):
            history = self.root / f"{state}.jsonl"
            append_event(
                history,
                {"draft_id": "d1", "event": state},
            )
            self.assertIsNone(
                assert_publishable("d1", read_events(history))
            )

    def test_missing_draft_history_is_not_publishable(self):
        with self.assertRaisesRegex(RuntimeError, "not publishable"):
            assert_publishable("d1", [])

    def test_latest_event_returns_only_requested_draft(self):
        events = [
            {"draft_id": "d1", "event": "drafted"},
            {"draft_id": "d2", "event": "published"},
            {"draft_id": "d1", "event": "approved"},
        ]

        self.assertEqual(
            latest_event("d1", events),
            {"draft_id": "d1", "event": "approved"},
        )

    def test_content_must_be_approved_before_rendering(self):
        draft = {
            "draft_id": "d1",
            "project_id": "fina",
            "format_id": "what-happens-next",
        }
        record_content_state(draft, "content_drafted", self.history)

        with self.assertRaisesRegex(
            RuntimeError,
            "content approval required",
        ):
            assert_renderable("d1", read_events(self.history))

        record_content_state(draft, "content_approved", self.history)
        self.assertIsNone(
            assert_renderable("d1", read_events(self.history))
        )

    def test_final_approval_requires_rendered_event(self):
        draft = {
            "draft_id": "d1",
            "project_id": "fina",
            "format_id": "what-happens-next",
        }
        record_content_state(draft, "content_drafted", self.history)
        record_content_state(draft, "content_approved", self.history)

        with self.assertRaisesRegex(
            RuntimeError,
            "rendered carousel required",
        ):
            approve(draft, self.history)

        mark_rendered(draft, self.history)
        approve(draft, self.history)
        approve(draft, self.history)
        self.assertEqual(
            [event["event"] for event in read_events(self.history)],
            [
                "content_drafted",
                "content_approved",
                "rendered",
                "approved",
            ],
        )

    def test_publishable_states_exclude_preapproval_events(self):
        for state in (
            "content_drafted",
            "content_approved",
            "rendered",
        ):
            history = self.root / f"{state}.jsonl"
            append_event(
                history,
                {"draft_id": "d1", "event": state},
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "not publishable",
            ):
                assert_publishable("d1", read_events(history))

    def test_revision_and_hold_accept_every_pending_approval_stage(self):
        for state in (
            "drafted",
            "content_drafted",
            "content_approved",
            "rendered",
            "approved",
        ):
            history = self.root / f"terminal-{state}.jsonl"
            draft = {
                "draft_id": f"d-{state}",
                "project_id": "fina",
                "format_id": "what-happens-next",
            }
            append_event(history, {**draft, "event": state})
            record_terminal(draft, "revised", history)
            self.assertEqual(
                latest_event(draft["draft_id"], read_events(history))[
                    "event"
                ],
                "revised",
            )

    def test_approval_is_recorded_once_before_publication(self):
        draft = {
            "draft_id": "d1",
            "project_id": "fina",
            "format_id": "what-happens-next",
        }
        append_event(
            self.history,
            {
                **draft,
                "event": "rendered",
            },
        )

        approve(draft, self.history)
        approve(draft, self.history)

        events = read_events(self.history)
        self.assertEqual(
            [event["event"] for event in events],
            ["rendered", "approved"],
        )

    def test_revision_and_hold_are_recorded_as_terminal_states(self):
        draft = {
            "draft_id": "d1",
            "project_id": "fina",
            "format_id": "what-happens-next",
        }
        append_event(
            self.history,
            {**draft, "event": "drafted"},
        )

        record_terminal(draft, "revised", self.history)

        self.assertEqual(
            latest_event("d1", read_events(self.history))["event"],
            "revised",
        )
        with self.assertRaisesRegex(RuntimeError, "not publishable"):
            record_terminal(draft, "held", self.history)

    def test_only_revision_or_hold_can_be_recorded_manually(self):
        draft = {
            "draft_id": "d1",
            "project_id": "fina",
            "format_id": "what-happens-next",
        }
        append_event(
            self.history,
            {**draft, "event": "drafted"},
        )

        with self.assertRaisesRegex(
            ValueError,
            "manual state must be revised or held",
        ):
            record_terminal(draft, "published", self.history)


class FakeR2:
    def __init__(self):
        self.remaining_keys = []
        self.fail_cleanup = False
        self.cleanup_calls = 0

    def upload(self, draft_id, files):
        self.remaining_keys = [
            f"{draft_id}/{path.name}" for path in files
        ]
        return list(self.remaining_keys)

    @staticmethod
    def presign(keys):
        return [
            f"https://staging.invalid/image-{index}.jpg"
            for index, _key in enumerate(keys, start=1)
        ]

    def cleanup(self, draft_id):
        self.cleanup_calls += 1
        if self.fail_cleanup:
            raise RuntimeError("cleanup failed")
        prefix = f"{draft_id}/"
        self.remaining_keys = [
            key for key in self.remaining_keys
            if not key.startswith(prefix)
        ]


class FakeInstagram:
    def __init__(self):
        self.fail_at = None
        self.parent_calls = 0
        self.publish_calls = 0

    def create_child(self, image_url):
        if self.fail_at == "child":
            raise RuntimeError("child failed")
        return f"child-{image_url.rsplit('-', 1)[-1]}"

    @staticmethod
    def wait_until_ready(container_id):
        return None

    def create_carousel(self, child_ids, caption):
        self.parent_calls += 1
        if self.fail_at == "parent":
            raise RuntimeError("parent failed")
        return "parent-1"

    def publish_carousel(self, container_id):
        self.publish_calls += 1
        if self.fail_at == "publish":
            raise RuntimeError("publish failed")
        return "media-1"


class FakeS3Client:
    def __init__(self):
        self.uploads = []
        self.presigns = []
        self.deleted = []
        self.list_calls = 0

    def upload_file(self, filename, bucket, key, ExtraArgs):
        self.uploads.append((filename, bucket, key, ExtraArgs))

    def generate_presigned_url(
        self,
        operation,
        Params,
        ExpiresIn,
    ):
        self.presigns.append((operation, Params, ExpiresIn))
        return f"https://r2.invalid/{Params['Key']}"

    def list_objects_v2(self, **kwargs):
        self.list_calls += 1
        if self.list_calls == 1:
            return {
                "Contents": [{"Key": "d1/01.jpg"}],
                "IsTruncated": True,
                "NextContinuationToken": "page-2",
            }
        if self.list_calls == 2:
            self.assert_continuation(kwargs, "page-2")
            return {
                "Contents": [{"Key": "d1/02.jpg"}],
                "IsTruncated": False,
            }
        return {"Contents": [], "IsTruncated": False}

    @staticmethod
    def assert_continuation(kwargs, expected):
        if kwargs.get("ContinuationToken") != expected:
            raise AssertionError("continuation token was not forwarded")

    def delete_objects(self, Bucket, Delete):
        self.deleted.extend(item["Key"] for item in Delete["Objects"])


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode()
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.payload


class PublishFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.history = self.root / "history.jsonl"
        self.files = [
            self.root / "01.jpg",
            self.root / "02.jpg",
        ]
        self.draft = {
            "draft_id": "d1",
            "project_id": "fina",
            "format_id": "what-happens-next",
            "caption": "Approved caption",
        }
        append_event(
            self.history,
            {
                "draft_id": "d1",
                "project_id": "fina",
                "format_id": "what-happens-next",
                "event": "rendered",
            },
        )
        self.r2 = FakeR2()
        self.instagram = FakeInstagram()

    def test_success_publishes_once_and_cleans_prefix(self):
        media_id = publish(
            self.draft,
            self.files,
            self.r2,
            self.instagram,
            self.history,
        )

        self.assertEqual(media_id, "media-1")
        self.assertEqual(self.instagram.publish_calls, 1)
        self.assertEqual(self.r2.remaining_keys, [])
        self.assertEqual(
            latest_event("d1", read_events(self.history))["event"],
            "published",
        )

    def test_child_failure_skips_parent_and_cleans_prefix(self):
        self.instagram.fail_at = "child"

        with self.assertRaisesRegex(RuntimeError, "child failed"):
            publish(
                self.draft,
                self.files,
                self.r2,
                self.instagram,
                self.history,
            )

        self.assertEqual(self.instagram.parent_calls, 0)
        self.assertEqual(self.instagram.publish_calls, 0)
        self.assertEqual(self.r2.remaining_keys, [])
        self.assertEqual(
            latest_event("d1", read_events(self.history))["event"],
            "publish_failed",
        )

    def test_parent_failure_cleans_prefix(self):
        self.instagram.fail_at = "parent"

        with self.assertRaisesRegex(RuntimeError, "parent failed"):
            publish(
                self.draft,
                self.files,
                self.r2,
                self.instagram,
                self.history,
            )

        self.assertEqual(self.instagram.publish_calls, 0)
        self.assertEqual(self.r2.remaining_keys, [])

    def test_publish_failure_leaves_uncertain_state_and_cleans_prefix(self):
        self.instagram.fail_at = "publish"

        with self.assertRaisesRegex(RuntimeError, "publish failed"):
            publish(
                self.draft,
                self.files,
                self.r2,
                self.instagram,
                self.history,
            )

        self.assertEqual(
            latest_event("d1", read_events(self.history))["event"],
            "publishing",
        )
        self.assertEqual(self.r2.remaining_keys, [])

    def test_cleanup_failure_is_recorded_after_success(self):
        self.r2.fail_cleanup = True

        with self.assertRaisesRegex(
            RuntimeError,
            "published but staging cleanup failed",
        ):
            publish(
                self.draft,
                self.files,
                self.r2,
                self.instagram,
                self.history,
            )

        events = read_events(self.history)
        self.assertTrue(
            any(event["event"] == "published" for event in events)
        )
        self.assertEqual(events[-1]["event"], "cleanup_failed")
        self.assertEqual(events[-1]["resume_event"], "published")
        self.assertEqual(self.instagram.publish_calls, 1)

    def test_cleanup_only_never_calls_instagram(self):
        self.r2.fail_cleanup = True
        with self.assertRaisesRegex(
            RuntimeError,
            "published but staging cleanup failed",
        ):
            publish(
                self.draft,
                self.files,
                self.r2,
                self.instagram,
                self.history,
            )
        self.r2.fail_cleanup = False
        prior_publish_calls = self.instagram.publish_calls

        cleanup_only("d1", self.r2, self.history)

        self.assertEqual(
            self.instagram.publish_calls,
            prior_publish_calls,
        )
        self.assertEqual(
            latest_event("d1", read_events(self.history))["event"],
            "cleanup_completed",
        )

    def test_cleanup_after_pre_publish_failure_allows_safe_retry(self):
        self.instagram.fail_at = "child"
        self.r2.fail_cleanup = True
        with self.assertRaisesRegex(RuntimeError, "child failed"):
            publish(
                self.draft,
                self.files,
                self.r2,
                self.instagram,
                self.history,
            )
        self.r2.fail_cleanup = False

        cleanup_only("d1", self.r2, self.history)

        self.assertIsNone(
            assert_publishable("d1", read_events(self.history))
        )

    def test_r2_uses_expiring_get_urls_and_cleans_every_page(self):
        client = FakeS3Client()
        r2 = R2(client, "building-intent-social")

        keys = r2.upload("d1", self.files)
        urls = r2.presign(keys)
        r2.cleanup("d1")

        self.assertEqual(keys, ["d1/01.jpg", "d1/02.jpg"])
        self.assertEqual(
            client.uploads[0][3],
            {
                "ContentType": "image/jpeg",
                "CacheControl": "no-store",
            },
        )
        self.assertEqual(len(urls), 2)
        self.assertTrue(
            all(call[0] == "get_object" for call in client.presigns)
        )
        self.assertTrue(
            all(call[2] == 3600 for call in client.presigns)
        )
        self.assertEqual(
            client.deleted,
            ["d1/01.jpg", "d1/02.jpg"],
        )

    def test_instagram_sends_expected_carousel_requests(self):
        responses = iter(
            [
                {"id": "child-1"},
                {"status_code": "IN_PROGRESS"},
                {"status_code": "FINISHED"},
                {"id": "parent-1"},
                {"id": "media-1"},
            ]
        )
        requests = []
        sleeps = []

        def open_url(request, timeout):
            requests.append(request)
            return FakeHTTPResponse(next(responses))

        instagram = Instagram(
            "user-1",
            "secret-token",
            "v23.0",
            open_url=open_url,
            sleep=sleeps.append,
        )

        child = instagram.create_child("https://r2.invalid/01.jpg")
        instagram.wait_until_ready(child)
        parent = instagram.create_carousel(
            [child, "child-2"],
            "Approved caption",
        )
        media = instagram.publish_carousel(parent)

        child_form = parse_qs(requests[0].data.decode())
        parent_form = parse_qs(requests[3].data.decode())
        self.assertEqual(child_form["is_carousel_item"], ["true"])
        self.assertEqual(
            child_form["image_url"],
            ["https://r2.invalid/01.jpg"],
        )
        self.assertEqual(parent_form["media_type"], ["CAROUSEL"])
        self.assertEqual(
            json.loads(parent_form["children"][0]),
            ["child-1", "child-2"],
        )
        self.assertEqual(
            requests[0].full_url,
            "https://graph.instagram.com/v23.0/user-1/media",
        )
        self.assertEqual(
            requests[1].full_url,
            (
                "https://graph.instagram.com/v23.0/"
                "child-1?fields=status_code"
            ),
        )
        authorization = requests[0].headers["Authorization"]
        self.assertTrue(authorization.startswith("Bearer "))
        self.assertEqual(
            authorization.removeprefix("Bearer "),
            "secret-token",
        )
        self.assertEqual(sleeps, [2])
        self.assertEqual(media, "media-1")

    def test_missing_credentials_are_rejected_before_network_access(self):
        with self.assertRaisesRegex(
            ValueError,
            "INSTAGRAM_USER_ID.*R2_SECRET_ACCESS_KEY",
        ):
            load_required_env({})

    def test_current_secret_names_build_runtime_configuration(self):
        secrets = {
            "INSTAGRAM_USER_ID": "ig-user",
            "R2_ACCOUNT_ID": "account",
            "R2_ACCESS_KEY_ID": "access",
            "R2_SECRET_ACCESS_KEY": "secret",
            "INSTAGRAM_ACCESS_TOKEN": "token",
        }

        self.assertEqual(
            load_required_env(secrets),
            {
                **secrets,
                "META_API_VERSION": "v23.0",
                "R2_BUCKET": "building-intent-social",
            },
        )

    def test_instagram_invalid_json_does_not_echo_response_body(self):
        def open_url(request, timeout):
            return FakeHTTPResponse(b"private-provider-body")

        instagram = Instagram(
            "user-1",
            "secret-token",
            "v23.0",
            open_url=open_url,
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "^Instagram returned invalid JSON$",
        ) as raised:
            instagram.create_child("https://r2.invalid/01.jpg")
        self.assertNotIn(
            "private-provider-body",
            str(raised.exception),
        )

    def test_rendered_files_require_exact_order_and_dimensions(self):
        rendered = self.root / "rendered"
        rendered.mkdir()
        for filename in ("01.jpg", "02.jpg"):
            Image.new("RGB", (1080, 1350), "white").save(
                rendered / filename
            )
        draft = {"slides": [{}, {}]}

        self.assertEqual(
            [path.name for path in verify_rendered(draft, rendered)],
            ["01.jpg", "02.jpg"],
        )

        Image.new("RGB", (100, 100), "white").save(
            rendered / "02.jpg"
        )
        with self.assertRaisesRegex(
            ValueError,
            "02.jpg must be 1080x1350 JPEG",
        ):
            verify_rendered(draft, rendered)

    def test_publish_script_runs_from_repository_root(self):
        repository = Path(__file__).resolve().parent.parent
        isolated_repository = self.root / "repository"
        shutil.copytree(
            repository / "social",
            isolated_repository / "social",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        draft_dir = isolated_repository / "draft"
        rendered_dir = draft_dir / "rendered"
        draft_dir.mkdir()
        rendered_dir.mkdir()
        draft = DraftValidationTests.valid_draft()
        (draft_dir / "draft.json").write_text(
            json.dumps(draft),
            encoding="utf-8",
        )
        for index in range(1, 4):
            Image.new("RGB", (900, 700), "white").save(
                draft_dir / f"art-{index:02}.png"
            )
        for index in range(1, 5):
            Image.new("RGB", (1080, 1350), "white").save(
                rendered_dir / f"{index:02}.jpg"
            )
        append_event(
            isolated_repository / "social" / "history.jsonl",
            {
                "draft_id": draft["draft_id"],
                "project_id": draft["project_id"],
                "format_id": draft["format_id"],
                "event": "rendered",
            },
        )

        result = subprocess.run(
            [
                sys.executable,
                "social/publish.py",
                "draft/draft.json",
                "draft/rendered",
            ],
            cwd=isolated_repository,
            env={},
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "missing required environment variables",
            result.stdout,
        )
        self.assertNotIn("ModuleNotFoundError", result.stderr)
        self.assertEqual(
            read_events(
                isolated_repository / "social" / "history.jsonl"
            )[-1]["event"],
            "approved",
        )


if __name__ == "__main__":
    unittest.main()
