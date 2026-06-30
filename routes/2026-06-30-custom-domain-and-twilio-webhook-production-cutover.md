# 2026-06-30 - custom domain and Twilio webhook production cutover

## Summary
- Completed production custom-domain routing for Market SMS Assistant.
- Completed Twilio inbound SMS webhook cutover to custom domain.
- Confirmed Render custom domains are verified with certificates issued.

## Completed DNS changes (Namecheap)
- Removed parking record:
  - `CNAME www -> parkingpage.namecheap.com`
- Removed old root redirect:
  - `URL Redirect @ -> old www redirect`
- Configured active records:
  - `ALIAS @ -> market-sms-updates.onrender.com` (TTL 5 min)
  - `CNAME www -> market-sms-updates.onrender.com` (TTL Automatic)

## Completed Render domain configuration
- Web service: `market-sms-updates`
- Verified custom domains:
  - `yeshivachill.com`
  - `www.yeshivachill.com`
- Certificates issued and HTTPS active.
- `www.yeshivachill.com` redirects to `yeshivachill.com`.
- Render subdomain remains enabled: `https://market-sms-updates.onrender.com`.

## Completed Twilio inbound configuration
- Incoming message primary method: Webhook
- URL: `https://yeshivachill.com/api/market-updates/sms`
- HTTP method: `POST`
- Backup webhook: blank

## Verification next step
- Send SMS keyword: `MENU`
- Validate health endpoints:
  - `https://yeshivachill.com/health`
  - `https://yeshivachill.com/health/ready`
