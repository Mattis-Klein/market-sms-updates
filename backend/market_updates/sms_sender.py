from __future__ import annotations

import httpx


def build_twilio_form_payload(from_number: str, to_number: str, body: str) -> dict:
    return {"From": from_number, "To": to_number, "Body": body}


async def send_sms(account_sid: str, auth_token: str, from_number: str, to_number: str, body: str) -> bool:
    if not account_sid or not auth_token or not from_number:
        return False
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = {"From": from_number, "To": to_number, "Body": body}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, data=data, auth=(account_sid, auth_token))
        return 200 <= resp.status_code < 300
