import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

TW_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TW_DIR))

import discovery


class DiscoveryQualityGateTests(unittest.TestCase):

    def future_date(self, days=14):
        d = datetime.now(timezone.utc) + timedelta(days=days)
        return f"{d.strftime('%B')} {d.day}, {d.year}"

    def test_rejects_no_schedule_page(self):
        ok, reason = discovery.passes_current_event_gate(
            "Holiday Raceway",
            "No race schedule entered yet."
        )
        self.assertFalse(ok)

    def test_rejects_stale_2025_result(self):
        ok, reason = discovery.passes_current_event_gate(
            "No Problem Raceway 2025 Schedule",
            "NHRA Lucas Oil Drag Racing Series schedule for 2025."
        )
        self.assertFalse(ok)

    def test_rejects_generic_facebook_profile(self):
        ok, reason = discovery.passes_current_event_gate(
            "Montgomery International Dragway | Montgomery AL | Facebook",
            "Race track · Montgomery, Alabama."
        )
        self.assertFalse(ok)

    def test_rejects_generic_thefoat_ticket_page(self):
        ok, reason = discovery.passes_current_event_gate(
            "Montgomery International Dragway - Tickets - TheFOAT",
            "Buy tickets for Montgomery International Dragway."
        )
        self.assertFalse(ok)

    def test_allows_cancellation(self):
        ok, reason = discovery.passes_current_event_gate(
            "Gulfport Dragway race canceled",
            "Saturday's race has been canceled due to rain."
        )
        self.assertTrue(ok)

    def test_allows_registration_opening(self):
        ok, reason = discovery.passes_current_event_gate(
            "Registration now open at Gulfport Dragway",
            "Registration is now open for the upcoming bracket race."
        )
        self.assertTrue(ok)

    def test_allows_rescheduled_event(self):
        ok, reason = discovery.passes_current_event_gate(
            "Swamp Bottom Dragstrip race rescheduled",
            "The event has been rescheduled due to weather."
        )
        self.assertTrue(ok)

    def test_allows_future_dated_race(self):
        date = self.future_date()
        ok, reason = discovery.passes_current_event_gate(
            "Upcoming race at Holiday Raceway",
            f"Bracket race scheduled for {date}. Gates open at 3 PM."
        )
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
