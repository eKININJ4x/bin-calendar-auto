import unittest
from bin_schedule import parse_dates, build_calendar

class CalendarTests(unittest.TestCase):
    def test_deduplicate_and_reminders(self):
        response = {"results": [
            {"bin_name": "Grey Bin (Non-Recyclable)", "nextcollection": "Tuesday 10 November 2026",
             "futurecollections": ["Tuesday 10 November 2026", "Tuesday 24 November 2026"]},
            {"bin_name": "Brown Bin (Recycling)", "nextcollection": "Tuesday 10 November 2026",
             "futurecollections": []},
        ]}
        events = parse_dates(response)
        self.assertEqual(len(events), 3)
        calendar = build_calendar(events, stamp="20261107T000000Z")
        self.assertEqual(calendar.count("BEGIN:VEVENT"), 5)
        self.assertIn("DTSTART;VALUE=DATE:20261110", calendar)
        self.assertIn("DTSTART;TZID=Europe/London:20261109T180000", calendar)
        self.assertIn("SUMMARY:Put bins out: Brown Bin\\, Grey Bin", calendar)
        self.assertEqual(calendar, build_calendar(events, stamp="20261107T000000Z"))

    def test_empty_or_invalid_fails_safe(self):
        with self.assertRaises(ValueError):
            parse_dates({"results": []})
        with self.assertRaises(ValueError):
            parse_dates({"results": [{"bin_name": "Grey", "nextcollection": "invalid"}]})

if __name__ == "__main__":
    unittest.main()
