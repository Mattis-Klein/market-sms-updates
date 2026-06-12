from __future__ import annotations

import httpx


YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
MRBEAST_CHANNEL_ID = "UCX6OQ3DkcsbYNE6H8uQQuVA"


class YouTubeServiceError(Exception):
    pass


def format_subscriber_count(count: int) -> str:
    return f"{count:,}"


async def get_channel_subscriber_count(channel_id: str, api_key: str) -> int:
    if not api_key:
        raise YouTubeServiceError("missing api key")

    params = {"part": "statistics", "id": channel_id, "key": api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(YOUTUBE_CHANNELS_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        raise YouTubeServiceError("youtube request failed") from exc

    items = payload.get("items") or []
    if not items:
        raise YouTubeServiceError("channel not found")

    statistics = items[0].get("statistics") or {}
    raw_count = statistics.get("subscriberCount")
    if raw_count is None:
        raise YouTubeServiceError("subscriber count missing")

    try:
        return int(raw_count)
    except (TypeError, ValueError) as exc:
        raise YouTubeServiceError("subscriber count invalid") from exc
