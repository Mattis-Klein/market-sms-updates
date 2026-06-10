# Route History - MENU Command Reserved Keyword Update

Date: 2026-06-10

Summary:
- Updated app command design to use MENU as the primary help/description keyword.
- Removed app-owned HELP routing from command handling.
- Added CANCELREMINDER <index> as a safe reminder-cancel keyword.
- Updated command documentation text to MENU-first wording.

HTTP routes:
- No route changes.
- Twilio webhook remains POST /api/market-updates/sms.
- Admin and feedback routes unchanged.
