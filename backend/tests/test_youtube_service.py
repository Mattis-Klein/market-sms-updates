import unittest
from unittest.mock import AsyncMock, patch

from market_updates.youtube_service import (
    LivecountsServiceError,
    _extract_count_from_html,
    _extract_count_from_stats_payload,
    get_channel_subscriber_count,
)


class YouTubeServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_extract_count_from_stats_payload_uses_follower_count(self):
        payload = {"success": True, "followerCount": 501237535}
        self.assertEqual(_extract_count_from_stats_payload(payload), 501237535)

    def test_extract_count_from_stats_payload_rejects_bad_payload(self):
        with self.assertRaises(LivecountsServiceError):
            _extract_count_from_stats_payload({"success": False, "followerCount": 10})

    def test_extract_count_from_html_handles_spaced_commas(self):
        html = "<div>5 0 1, 2 3 7, 5 3 5 Subscribers</div>"
        self.assertEqual(_extract_count_from_html(html), 501237535)

    async def test_get_channel_subscriber_count_prefers_stats(self):
        with patch(
            "market_updates.youtube_service._fetch_count_from_stats",
            new=AsyncMock(return_value=501237535),
        ) as stats_mock, patch(
            "market_updates.youtube_service._fetch_count_from_html",
            new=AsyncMock(return_value=500000000),
        ) as html_mock:
            result = await get_channel_subscriber_count("UCX6OQ3DkcsbYNE6H8uQQuVA")

        self.assertEqual(result, 501237535)
        stats_mock.assert_awaited_once()
        html_mock.assert_not_awaited()

    async def test_get_channel_subscriber_count_falls_back_to_html(self):
        with patch(
            "market_updates.youtube_service._fetch_count_from_stats",
            new=AsyncMock(side_effect=LivecountsServiceError("stats blocked")),
        ) as stats_mock, patch(
            "market_updates.youtube_service._fetch_count_from_html",
            new=AsyncMock(return_value=501237535),
        ) as html_mock:
            result = await get_channel_subscriber_count("UCX6OQ3DkcsbYNE6H8uQQuVA")

        self.assertEqual(result, 501237535)
        stats_mock.assert_awaited_once()
        html_mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
