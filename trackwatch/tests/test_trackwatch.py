#!/usr/bin/env python3
"""TrackWatch V0.1 test suite. Stdlib unittest, no network access.

    python3 trackwatch/tests/test_trackwatch.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

TW_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TW_DIR))

import classifier   # noqa: E402
import detector      # noqa: E402
import normalizer    # noqa: E402
import review_queue as rq  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class NormalizerTests(unittest.TestCase):
    def test_strips_script_style_and_nav_keeps_content(self):
        text = normalizer.html_to_text(_read("fixture_before.html"))
        self.assertNotIn("tracking pixel", text)
        self.assertNotIn("console.log", text)
        self.assertNotIn("Home", text)       # nav link text
        self.assertNotIn("Contact", text)    # nav link text
        self.assertIn("Gates 4 PM", text)
        self.assertIn("Saturday Test & Tune", text)
        self.assertIn("Copyright 2025", text)  # footer text is kept — just not nav


class ClassifierTests(unittest.TestCase):
    def setUp(self):
        self.clf = classifier.get_classifier()

    def test_cancellation_and_schedule_change_is_meaningful(self):
        before = normalizer.html_to_text(_read("fixture_before.html"))
        after = normalizer.html_to_text(_read("fixture_after.html"))
        before_ex, after_ex = detector.changed_excerpt(before, after)
        result = self.clf.classify(before, after, before_ex + "\n" + after_ex)
        self.assertTrue(result.is_meaningful)
        self.assertEqual(result.change_type, "possible_cancellation")
        self.assertGreater(result.confidence, 0.5)
        self.assertIn("cancelled", result.keywords)

    def test_copyright_year_change_is_not_meaningful(self):
        before = normalizer.html_to_text(_read("fixture_meaningless_before.html"))
        after = normalizer.html_to_text(_read("fixture_meaningless_after.html"))
        before_ex, after_ex = detector.changed_excerpt(before, after)
        result = self.clf.classify(before, after, before_ex + "\n" + after_ex)
        self.assertFalse(result.is_meaningful)
        self.assertEqual(result.change_type, "low_value")

    def test_identical_text_has_no_excerpt_at_all(self):
        before = normalizer.html_to_text(_read("fixture_before.html"))
        before_ex, after_ex = detector.changed_excerpt(before, before)
        self.assertEqual(before_ex, "")
        self.assertEqual(after_ex, "")


class DetectorHashTests(unittest.TestCase):
    def test_hash_is_stable_and_change_sensitive(self):
        a = detector.content_hash("Saturday Test & Tune\nGates 4 PM")
        b = detector.content_hash("Saturday Test & Tune\nGates 4 PM")
        c = detector.content_hash("Sunday Test & Tune\nGates 2 PM")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_hash_ignores_case_and_extra_whitespace(self):
        a = detector.content_hash("Hello   World")
        b = detector.content_hash("hello world")
        self.assertEqual(a, b)


class CompareWithSiteDataTests(unittest.TestCase):
    def test_flags_day_of_week_conflict(self):
        track = {"race_days": "Saturday nights, January through December.", "phone": "228-863-4408"}
        notes = detector.compare_with_site_data(track, "Racing moves to Sunday this week, gates at 2pm.")
        self.assertTrue(any("Sunday" in n for n in notes))

    def test_no_conflict_when_day_matches(self):
        track = {"race_days": "Saturday nights, January through December.", "phone": "228-863-4408"}
        notes = detector.compare_with_site_data(track, "Saturday racing moves up an hour this week.")
        self.assertEqual(notes, [])

    def test_flags_phone_conflict(self):
        track = {"race_days": "Saturday nights.", "phone": "228-863-4408"}
        notes = detector.compare_with_site_data(track, "Call us now at 228-555-1212 for details.")
        self.assertTrue(any("228-555-1212" in n for n in notes))


class ReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._orig_dir = rq.REVIEW_DIR
        rq.REVIEW_DIR = Path(self.tmp.name)
        for status in rq.STATUSES:
            (rq.REVIEW_DIR / status).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        rq.REVIEW_DIR = self._orig_dir
        self.tmp.cleanup()

    def test_create_list_approve_roundtrip(self):
        rec = rq.create_detection(
            track_slug="test-track", source_id="official-site",
            source_url="https://example.com", change_type="possible_cancellation",
            confidence=0.8, summary="test", before_excerpt="a", after_excerpt="b",
            keywords=["cancelled"], source_hash_before="x", source_hash_after="y",
        )
        pending = rq.list_detections("pending")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], rec["id"])
        self.assertEqual(pending[0]["status"], "pending")

        rq.set_status(rec["id"], "approved")
        self.assertEqual(rq.list_detections("pending"), [])
        approved = rq.list_detections("approved")
        self.assertEqual(len(approved), 1)
        self.assertEqual(approved[0]["status"], "approved")
        self.assertIsNotNone(approved[0]["reviewed_at"])

    def test_ignore_roundtrip(self):
        rec = rq.create_detection(
            track_slug="test-track", source_id="official-site",
            source_url="https://example.com", change_type="possible_update",
            confidence=0.5, summary="test", before_excerpt="a", after_excerpt="b",
            keywords=[], source_hash_before="x", source_hash_after="y",
        )
        rq.set_status(rec["id"], "ignored")
        self.assertEqual(rq.list_detections("ignored")[0]["status"], "ignored")
        self.assertEqual(rq.counts(), {"pending": 0, "approved": 0, "ignored": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
