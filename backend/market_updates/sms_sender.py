from __future__ import annotations

import httpx


def classify_twilio_failure(status_code: int, response_text: str) -> str:
    text = (response_text or "").lower()
    if status_code in {429, 500, 502, 503, 504}:
        return "temporary"
    if "21610" in text or "opted out" in text:
        return "permanent"
    if "21211" in text or "invalid" in text:
        return "permanent"
    if 400 <= status_code < 500:
        return "permanent"
    return "temporary"


def build_twilio_form_payload(from_number: str, to_number: str, body: str) -> dict:
    return {"From": from_number, "To": to_number, "Body": body}


async def send_sms(account_sid: str, auth_token: str, from_number: str, to_number: str, body: str) -> bool:
    result = await send_sms_with_result(account_sid, auth_token, from_number, to_number, body)
    return bool(result["ok"])


async def send_sms_with_result(account_sid: str, auth_token: str, from_number: str, to_number: str, body: str) -> dict:
    if not account_sid or not auth_token or not from_number:
        return {"ok": False, "error_type": "permanent", "status_code": 0, "error": "missing_credentials"}
    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = {"From": from_number, "To": to_number, "Body": body}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(url, data=data, auth=(account_sid, auth_token))
        except httpx.TimeoutException:
            return {"ok": False, "error_type": "temporary", "status_code": 0, "error": "timeout"}
        except httpx.HTTPError:
            return {"ok": False, "error_type": "temporary", "status_code": 0, "error": "network_error"}

        if 200 <= resp.status_code < 300:
            return {"ok": True, "error_type": "none", "status_code": resp.status_code, "error": ""}

        failure_type = classify_twilio_failure(resp.status_code, resp.text)
        return {
            "ok": False,
            "error_type": failure_type,
            "status_code": resp.status_code,
            "error": (resp.text or "").strip()[:500],
        }
