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

    def test_rejects_generic_ticket_seating_page(self):
        ok, reason = discovery.passes_current_event_gate(
            "Gulfport Dragway Tickets | Upcoming Events at Gulfport Dragway",
            "Most events provide options for different seating areas. "
            "Ticket prices vary for front row seats or mid row seats."
        )
        self.assertFalse(ok)

    def test_rejects_generic_ticket_information_page(self):
        ok, reason = discovery.passes_current_event_gate(
            "Gulfport Dragway Tickets - Gulfport Dragway Information - Gulfport Dragway Seating Chart",
            "Gulfport Dragway can accommodate up to 0 guests."
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

class DiscoveryOrdinalDateTests(unittest.TestCase):
    def test_extracts_ordinal_dates(self):
        dates = discovery.extract_month_day_dates(
            "Thursday June 4th and Friday June 5th, 2026"
        )
        self.assertEqual(len(dates), 2)
        self.assertEqual(dates[0].month, 6)
        self.assertEqual(dates[0].day, 4)
        self.assertEqual(dates[1].month, 6)
        self.assertEqual(dates[1].day, 5)

    def test_rejects_stale_ordinal_event_dates(self):
        ok, reason = discovery.passes_current_event_gate(
            "Upcoming Events – Holiday Raceway",
            "2026 SCHEDULE OF EVENTS. "
            "Thursday June 4th: Jake's Dragstrip. "
            "Friday June 5th: Holiday Raceway."
        )
        self.assertFalse(ok)
        self.assertIn("stale event date", reason)


if __name__ == "__main__":
    unittest.main()
