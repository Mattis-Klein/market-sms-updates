from __future__ import annotations

import re
import httpx


LIVECOUNTS_URL = "https://livecounts.io/youtube-live-subscriber-counter"
LIVECOUNTS_STATS_URL = "https://api.livecounts.io/youtube-live-subscriber-counter/stats"
MRBEAST_CHANNEL_ID = "UCX6OQ3DkcsbYNE6H8uQQuVA"

LIVECOUNTS_API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://livecounts.io",
    "Referer": f"{LIVECOUNTS_URL}/{MRBEAST_CHANNEL_ID}",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "x-service": "Livecounts.io",
}


class LivecountsServiceError(Exception):
    pass


def format_subscriber_count(count: int) -> str:
    return f"{count:,}"


def _extract_count_from_stats_payload(payload: object) -> int:
    if not isinstance(payload, dict):
        raise LivecountsServiceError("stats response invalid")
    if not payload.get("success"):
        raise LivecountsServiceError("stats request not successful")

    value = payload.get("followerCount")
    if isinstance(value, bool):
        raise LivecountsServiceError("stats followerCount invalid")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise LivecountsServiceError("stats followerCount invalid") from exc


def _extract_count_from_html(html: str) -> int:
    # Find subscriber count in HTML: digits separated by spaces, with commas
    # Pattern matches sequences like "4 9 9, 8 5 2, 9 0 7"
    match = re.search(r'(\d[\s\d,]*\d)\s*Subscribers', html)
    if not match:
        raise LivecountsServiceError("subscriber count not found in page")

    count_str = match.group(1)
    # Remove all spaces and commas, keep only digits
    clean_count = re.sub(r'[\s,]', '', count_str)

    try:
        return int(clean_count)
    except (TypeError, ValueError) as exc:
        raise LivecountsServiceError("subscriber count invalid") from exc


async def _fetch_count_from_stats(client: httpx.AsyncClient, channel_id: str) -> int:
    stats_url = f"{LIVECOUNTS_STATS_URL}/{channel_id}"
    headers = dict(LIVECOUNTS_API_HEADERS)
    headers["Referer"] = f"{LIVECOUNTS_URL}/{channel_id}"
    try:
        resp = await client.get(stats_url, headers=headers)
        resp.raise_for_status()
        return _extract_count_from_stats_payload(resp.json())
    except (httpx.HTTPError, ValueError, LivecountsServiceError) as exc:
        raise LivecountsServiceError("livecounts stats request failed") from exc


async def _fetch_count_from_html(client: httpx.AsyncClient, channel_id: str) -> int:
    url = f"{LIVECOUNTS_URL}/{channel_id}"
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        return _extract_count_from_html(resp.text)
    except (httpx.HTTPError, LivecountsServiceError) as exc:
        raise LivecountsServiceError("livecounts html request failed") from exc


async def get_channel_subscriber_count(channel_id: str) -> int:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            return await _fetch_count_from_stats(client, channel_id)
        except LivecountsServiceError:
            return await _fetch_count_from_html(client, channel_id)
