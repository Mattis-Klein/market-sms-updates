import unittest
from unittest.mock import AsyncMock, patch

from market_updates.lottery import PowerballServiceError, get_powerball_summary, reset_powerball_cache_for_tests


class LotteryServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        reset_powerball_cache_for_tests()

    async def test_get_powerball_summary_uses_cache_within_ttl(self):
        payload = {
            "next_jackpot": "$100M",
            "cash_option": "$48M",
            "next_draw_date": "2026-06-17",
            "latest_draw_date": "2026-06-15",
            "white_numbers": "1 2 3 4 5",
            "powerball": "6",
            "power_play": "2X",
            "jackpot_winner_status": "N/A",
            "source": "Official Powerball",
            "fetched_at": "2026-06-16 10:00 UTC",
        }
        with patch("market_updates.lottery._fetch_powerball_summary_uncached", new=AsyncMock(return_value=payload)) as mocked:
            first = await get_powerball_summary()
            second = await get_powerball_summary()

        self.assertEqual(first["next_jackpot"], "$100M")
        self.assertEqual(second["next_jackpot"], "$100M")
        mocked.assert_awaited_once()

    async def test_get_powerball_summary_raises_service_error_on_fetch_failure(self):
        with patch(
            "market_updates.lottery._fetch_powerball_summary_uncached",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            with self.assertRaises(PowerballServiceError):
                await get_powerball_summary()


if __name__ == "__main__":
    unittest.main()
