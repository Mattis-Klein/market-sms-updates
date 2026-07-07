from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from .cache import CACHE
from .models import LiveDataResult, utc_now_iso


logger = logging.getLogger(__name__)

LEAGUE_MAP = {
    "NFL": "nfl",
    "NBA": "nba",
    "MLB": "mlb",
    "NHL": "nhl",
}

TEAM_ALIASES = {
    "yankees": ("MLB", "NYY"),
    "mets": ("MLB", "NYM"),
    "lakers": ("NBA", "LAL"),
    "knicks": ("NBA", "NYK"),
    "rangers": ("NHL", "NYR"),
    "jets": ("NFL", "NYJ"),
    "eagles": ("NFL", "PHI"),
}

AMBIGUOUS_TEAM_TERMS = {
    "giants": "Do you mean New York Giants football or San Francisco Giants baseball?",
}


def _safe_error(provider: str, message: str, raw_status: str = "error") -> LiveDataResult:
    return LiveDataResult(
        success=False,
        provider=provider,
        retrieved_at_utc=utc_now_iso(),
        source_timestamp_utc=None,
        is_live=False,
        is_delayed=False,
        delay_minutes=None,
        confidence="low",
        raw_status=raw_status,
        human_summary=message,
        safe_error=message,
    )


def _provider_settings(config) -> tuple[str, str, int, int, bool]:
    provider = (getattr(config, "sports_data_provider", "sportsdataio") or "sportsdataio").lower()
    cache_seconds = int(getattr(config, "sports_cache_seconds", 10) or 10)
    stale_after = int(getattr(config, "sports_stale_after_seconds", 45) or 45)
    require_timestamp = bool(getattr(config, "sports_require_provider_timestamp", True))

    if provider == "sportsdataio":
        key = getattr(config, "sportsdataio_api_key", "")
    elif provider == "sportradar":
        key = getattr(config, "sportradar_api_key", "")
    else:
        key = ""
    return provider, key, cache_seconds, stale_after, require_timestamp


def _resolve_team(league: str, team: str) -> tuple[str | None, str | None]:
    value = (team or "").strip()
    if not value:
        return None, "Please provide a team name."
    lowered = value.lower()
    if lowered in AMBIGUOUS_TEAM_TERMS:
        return None, AMBIGUOUS_TEAM_TERMS[lowered]
    if lowered in TEAM_ALIASES:
        alias_league, team_code = TEAM_ALIASES[lowered]
        if league and league.upper() != alias_league:
            return None, f"{value} is typically in {alias_league}. Please confirm league."
        return team_code, None
    return value.upper(), None


async def _fetch_games_sportsdataio(api_key: str, league: str, date_local: str) -> list[dict]:
    sport = LEAGUE_MAP.get((league or "").upper())
    if not sport:
        raise ValueError("unsupported_league")
    url = f"https://api.sportsdata.io/v3/{sport}/scores/json/GamesByDate/{date_local}"
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []


def _format_game_line(game: dict) -> str:
    away = game.get("AwayTeam") or game.get("away_team") or "Away"
    home = game.get("HomeTeam") or game.get("home_team") or "Home"
    away_score = game.get("AwayScore")
    home_score = game.get("HomeScore")
    status = str(game.get("Status") or game.get("status") or "scheduled").lower()

    if status in {"inprogress", "in progress", "active"}:
        period = game.get("Quarter") or game.get("Period") or ""
        clock = game.get("TimeRemainingMinutes") or game.get("Clock") or ""
        detail = f"Q{period} {clock}".strip()
    elif status in {"final", "complete", "closed"}:
        detail = "final"
    else:
        detail = "scheduled"

    if away_score is not None and home_score is not None:
        return f"{away} {away_score}, {home} {home_score}, {detail}"
    return f"{away} at {home}, {detail}"


def _result_from_games(provider: str, league: str, games: list[dict], require_timestamp: bool) -> LiveDataResult:
    if not games:
        return _safe_error(provider, f"I don't see a live {league} game right now.", "no_games")

    source_ts = None
    for game in games:
        raw = game.get("DateTimeUTC") or game.get("DateTime")
        if raw:
            try:
                source_ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(UTC)
                break
            except Exception:
                continue

    if require_timestamp and source_ts is None:
        return _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "missing_timestamp")

    lines = [_format_game_line(g) for g in games[:3]]
    updated = source_ts.astimezone().strftime("%I:%M %p ET") if source_ts else "Unknown"
    summary = (
        f"{league.upper()} scores:\n\n"
        + "\n".join(f"{idx + 1}. {line}" for idx, line in enumerate(lines))
        + f"\n\nUpdated: {updated}\nSource: {provider.title()}"
    )

    return LiveDataResult(
        success=True,
        provider=provider,
        retrieved_at_utc=utc_now_iso(),
        source_timestamp_utc=source_ts.isoformat() if source_ts else None,
        is_live=True,
        is_delayed=False,
        delay_minutes=None,
        confidence="high",
        raw_status="ok",
        human_summary=summary,
        data={"league": league.upper(), "games": len(games)},
    )


async def get_live_sports_scores(config, league: str, date_local: str) -> LiveDataResult:
    provider, api_key, cache_seconds, stale_after, require_timestamp = _provider_settings(config)
    if provider not in {"sportsdataio", "sportradar"}:
        return _safe_error("sports", "I couldn't get reliable live data right now. Please try again shortly.", "unsupported_provider")
    if not api_key:
        return _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "missing_api_key")

    cache_key = f"sports:scores:{provider}:{league}:{date_local}"
    cached, stale = CACHE.get(cache_key)
    if isinstance(cached, LiveDataResult) and not stale and not cached.safe_error:
        return cached

    try:
        if provider == "sportsdataio":
            games = await _fetch_games_sportsdataio(api_key, league, date_local)
        else:
            return _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "sportradar_not_configured")

        result = _result_from_games(provider, league, games, require_timestamp=require_timestamp)
        CACHE.set(cache_key, result, cache_seconds, stale_after, is_error=not result.success)
        logger.info(
            "live_data.sports scores",
            extra={"provider": provider, "league": league.upper(), "success": result.success, "games": result.data.get("games", 0)},
        )
        return result
    except ValueError:
        result = _safe_error(provider, f"Unsupported league: {league}", "unsupported_league")
    except httpx.TimeoutException:
        result = _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "timeout")
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        result = _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", f"http_{status}")
    except Exception:
        result = _safe_error(provider, "I couldn't get reliable live data right now. Please try again shortly.", "exception")

    CACHE.set(cache_key, result, cache_seconds, stale_after, is_error=True)
    return result


async def get_game_status(config, league: str, team: str, opponent: str, date_local: str) -> LiveDataResult:
    team_code, prompt = _resolve_team(league, team)
    if prompt:
        provider = (getattr(config, "sports_data_provider", "sportsdataio") or "sportsdataio")
        return _safe_error(provider, prompt, "ambiguous_team")

    scores = await get_live_sports_scores(config, league, date_local)
    if not scores.success:
        return scores

    # Since provider payload is normalized to summary-only lines, return score summary for now.
    if opponent:
        return LiveDataResult(
            success=True,
            provider=scores.provider,
            retrieved_at_utc=scores.retrieved_at_utc,
            source_timestamp_utc=scores.source_timestamp_utc,
            is_live=scores.is_live,
            is_delayed=scores.is_delayed,
            delay_minutes=scores.delay_minutes,
            confidence=scores.confidence,
            raw_status=scores.raw_status,
            human_summary=scores.human_summary,
            data={"team": team_code, "opponent": opponent.upper()},
        )
    return scores


async def get_team_schedule(config, league: str, team: str, date_local: str) -> LiveDataResult:
    team_code, prompt = _resolve_team(league, team)
    provider = (getattr(config, "sports_data_provider", "sportsdataio") or "sportsdataio")
    if prompt:
        return _safe_error(provider, prompt, "ambiguous_team")

    scores = await get_live_sports_scores(config, league, date_local)
    if not scores.success:
        return scores

    return LiveDataResult(
        success=True,
        provider=scores.provider,
        retrieved_at_utc=scores.retrieved_at_utc,
        source_timestamp_utc=scores.source_timestamp_utc,
        is_live=scores.is_live,
        is_delayed=scores.is_delayed,
        delay_minutes=scores.delay_minutes,
        confidence=scores.confidence,
        raw_status=scores.raw_status,
        human_summary=f"{team_code} schedule around {date_local}:\n{scores.human_summary}",
        data={"team": team_code, "league": league.upper()},
    )
