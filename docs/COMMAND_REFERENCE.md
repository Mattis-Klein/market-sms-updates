# Command Reference

Date: 2026-06-16

## Top-Level Entry

- `MENU`: shows numbered navigation.

Top-level menu numbers now return guidance prompts (not immediate execution), for example:
- `3` -> guidance for symbol lookup (`SYMBOL <query>`).

## Market Data Commands

- `CHECK <ticker1 ticker2 ...>`
  - Example: `CHECK AAPL TSLA ^GSPC`
  - Returns latest price and day delta.

- `DATECHECK YYYY-MM-DD <ticker1 ticker2 ...>`
  - Example: `DATECHECK 2026-01-15 AAPL`
  - Returns historical close on/before requested date.

- Direct ticker message
  - Examples: `AAPL`, `$AAPL`, `AAPL?`, `(TSLA)`, `BTC-USD`
  - Returns latest quote directly.

## Symbol Discovery Commands

- `SYMBOL <name or phrase>`
  - Example: `SYMBOL S&P`
  - Returns matching tickers with names.

- `TICKER <query>` / `LOOKUP <query>` / `FIND <query>`
  - Legacy/alternative discovery commands.

- `TICKERS`
  - Returns supported symbol catalog snapshot.

## BEAST Commands

- `BEAST`
- `@mrbeast`

Both return the current MrBeast subscriber count.

## Reminder Commands

- `REMIND`
  - Starts reminder wizard.

Reminder wizard numeric options:
- `1` PRICE
- `2` ONCE
- `3` DAILY
- `4` INTERVAL

- `LIST`
  - Lists active/known reminders.

- `CANCELREMINDER <index>`
  - Example: `CANCELREMINDER 1`

## Feedback and Control

- `FEEDBACK <message>`
- `STOP`

## Access and Invite Behavior

For non-allowlisted numbers:
- `REQUEST ACCESS`
- `INVITE`
- `ACCESS`
- `@MARKET`

These create/update invite requests and notify approver flow.

## Approver Commands

When sender is approver number:
- `PENDING`
- `YES <id>`
- `NO <id>`

## Powerball-Only Profile Commands

Profile sender:
- `+17184733934` (normalized from either `+17184733934` or `7184733934`)

Allowed commands for this profile:
- `MENU`
- `CHECK`
- `LOTTO`
- `GUIDE`
- `POWERBALL`
- `PB`
- `JACKPOT`
- `NUMBERS`

Profile routing behavior:
- `MENU`, `CHECK`, `LOTTO`: returns Powerball-only menu.
- `GUIDE`: returns simple usage instructions.
- `POWERBALL`, `PB`: returns full Powerball update.
- `JACKPOT`: returns jackpot-only update.
- `NUMBERS`: returns latest winning numbers-only update.
- Unknown or blocked keywords: returns restricted-profile fallback.

Reserved keyword note:
- `HELP` is intentionally not used as an app keyword for this profile.
