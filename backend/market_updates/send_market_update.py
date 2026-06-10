from __future__ import annotations

import argparse
import asyncio

from .config import load_config
from .market_data import get_latest_quote
from .sms_sender import send_sms


async def run(symbols: list[str], recipients: list[str], dry_run: bool):
    config = load_config()
    lines = []
    for symbol in symbols:
        quote = await get_latest_quote(symbol)
        if quote.get("available"):
            lines.append(f"{quote['symbol']}: ${quote['price']:.2f}")
        else:
            lines.append(f"{symbol}: unavailable")

    body = "Market Update: " + " | ".join(lines)
    for to in recipients:
        if dry_run:
            print(f"DRY_RUN -> {to}: {body}")
            continue
        await send_sms(
            config.twilio_account_sid,
            config.twilio_auth_token,
            config.twilio_from_number,
            to,
            body,
        )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="AAPL,TSLA,NVDA")
    parser.add_argument("--to", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    recipients = [x.strip() for x in args.to.split(",") if x.strip()]
    asyncio.run(run([x.strip() for x in args.symbols.split(",")], recipients, args.dry_run))
