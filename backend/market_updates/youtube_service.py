from __future__ import annotations

import re
import httpx


LIVECOUNTS_URL = "https://livecounts.io/youtube-live-subscriber-counter"
MRBEAST_CHANNEL_ID = "UCX6OQ3DkcsbYNE6H8uQQuVA"


class LivecountsServiceError(Exception):
    pass


def format_subscriber_count(count: int) -> str:
    return f"{count:,}"


async def get_channel_subscriber_count(channel_id: str) -> int:
    url = f"{LIVECOUNTS_URL}/{channel_id}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except httpx.HTTPError as exc:
        raise LivecountsServiceError("livecounts request failed") from exc

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
