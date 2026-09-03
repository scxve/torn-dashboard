import unittest

import dashboard


class DashboardTests(unittest.TestCase):
    def test_format_duration(self):
        self.assertEqual(dashboard.format_duration(0), "READY")
        self.assertEqual(dashboard.format_duration(131), "00:02:11")
        self.assertEqual(dashboard.format_duration(90061), "1d 01:01")

    def test_time_until_ready(self):
        self.assertEqual(dashboard.time_until(0), "READY")

    def test_live_countdown(self):
        self.assertEqual(dashboard.live_countdown(325, 10), 315)
        self.assertEqual(dashboard.live_countdown(5, 10), 0)

    def test_compact_number(self):
        self.assertEqual(dashboard.compact_number(84_200_000, money=True), "$84.2M")
        self.assertEqual(dashboard.compact_number(3_700_000_000, money=True), "$3.7B")
        self.assertEqual(dashboard.compact_number(1247), "1.25K")

    def test_build_dashboard_from_current_v2_shape(self):
        state = dashboard.DashboardState(
            data={
                "profile": {"id": 123, "name": "Tester", "level": 53, "status": {"state": "Okay", "description": "Okay"}},
                "bars": {
                    "life": {"current": 100, "maximum": 100, "full_time": 0},
                    "energy": {"current": 120, "maximum": 150, "full_time": 300},
                    "nerve": {"current": 42, "maximum": 55, "full_time": 240},
                    "happy": {"current": 3960, "maximum": 5000, "full_time": 0},
                    "chain": {"current": 184, "max": 250, "timeout": 280},
                },
                "cooldowns": {"drug": 8321, "medical": 0, "booster": 0},
                "money": {
                    "wallet": 84_200_000,
                    "points": 1247,
                    "vault": 20_000_000,
                    "faction": {"money": 5_000_000, "points": 250},
                    "daily_networth": 947_680_000,
                    "city_bank": {"amount": 218_970_000, "until": 0},
                },
                "networth": {"total": 3_700_000_000},
                "travel": {"destination": "Torn", "method": None, "time_left": 0},
                "notifications": {"messages": 2, "events": 3, "awards": 1, "competition": 0},
            }
        )
        self.assertIsInstance(dashboard.build_dashboard(state, 10), dashboard.Layout)

    def test_compact_number_ignores_non_numeric_api_value(self):
        self.assertEqual(dashboard.compact_number({"money": 123}, money=True), "$0")


if __name__ == "__main__":
    unittest.main()
