from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from .cache import CACHE
from .models import LiveDataResult, utc_now_iso


logger = logging.getLogger(__name__)

SPORTS_PROVIDER_FAILURE_MESSAGE = "I couldn't get reliable live sports data right now. Please try again shortly."
UNSUPPORTED_LEAGUE_MESSAGE = "I don't have reliable live scores for that league right now."

LEAGUE_MAP = {
    "NFL": "nfl",
    "NBA": "nba",
    "MLB": "mlb",
    "NHL": "nhl",
}

THE_ODDS_LEAGUE_ALIASES = {
    "NFL": "americanfootball_nfl",
    "NBA": "basketball_nba",
    "MLB": "baseball_mlb",
    "NHL": "icehockey_nhl",
}

TEAM_ALIASES = {
    "yankees": ("MLB", "yankees"),
    "mets": ("MLB", "mets"),
    "lakers": ("NBA", "lakers"),
    "knicks": ("NBA", "knicks"),
    "rangers": ("NHL", "rangers"),
    "jets": ("NFL", "jets"),
    "eagles": ("NFL", "eagles"),
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
    elif provider == "theoddsapi":
        key = getattr(config, "the_odds_api_key", "")
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
    return lowered, None


def _parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return None


def _format_et(dt: datetime) -> str:
    try:
        et = dt.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        # Fallback keeps output stable in minimal environments lacking tz database.
        et = dt.astimezone(timezone(timedelta(hours=-5)))
    return et.strftime("%I:%M %p ET").lstrip("0")


def _event_teams(event: dict) -> tuple[str, str]:
    home = str(event.get("home_team") or event.get("HomeTeam") or "Home").strip()
    away = str(event.get("away_team") or event.get("AwayTeam") or "Away").strip()
    return home, away


def _score_lookup(event: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in event.get("scores") or []:
        name = str(item.get("name") or "").strip().lower()
        score = str(item.get("score") or "").strip()
        if name:
            out[name] = score
    return out


def _event_matches_team(event: dict, team_token: str) -> bool:
    if not team_token:
        return False
    home, away = _event_teams(event)
    token = team_token.lower().strip()
    return token in home.lower() or token in away.lower()


def _event_matches_opponent(event: dict, opponent: str) -> bool:
    if not opponent:
        return True
    home, away = _event_teams(event)
    token = opponent.lower().strip()
    return token in home.lower() or token in away.lower()


def _resolve_odds_sport_key(league: str, sports: list[dict]) -> str | None:
    league_code = (league or "").strip().upper()
    candidate = THE_ODDS_LEAGUE_ALIASES.get(league_code)
    if not candidate:
        return None

    available = {str(item.get("key") or "").strip() for item in sports}
    return candidate if candidate in available else None


def _latest_source_timestamp(events: list[dict]) -> datetime | None:
    latest: datetime | None = None
    for event in events:
        ts = _parse_iso_utc(str(event.get("last_update") or "")) or _parse_iso_utc(str(event.get("commence_time") or ""))
        if ts and (latest is None or ts > latest):
            latest = ts
    return latest


def _score_or_dash(value: str | None) -> str:
    return value if value else "-"


def _format_odds_event_line(event: dict, now_utc: datetime) -> tuple[str, str]:
    home, away = _event_teams(event)
    score_map = _score_lookup(event)
    home_score = _score_or_dash(score_map.get(home.lower()))
    away_score = _score_or_dash(score_map.get(away.lower()))
    commence = _parse_iso_utc(str(event.get("commence_time") or ""))
    completed = bool(event.get("completed"))

    if completed:
        return f"{away} {away_score}, {home} {home_score}, final.", "final"

    has_numeric_scores = home_score != "-" or away_score != "-"
    if has_numeric_scores and commence and commence <= now_utc:
        return f"{away} {away_score}, {home} {home_score}, in progress.", "live"

    if commence:
        return f"{away} vs {home}, {_format_et(commence)}", "upcoming"
    return f"{away} vs {home}, scheduled", "upcoming"


def _build_odds_summary(league: str, events: list[dict]) -> tuple[str, str]:
    now_utc = datetime.now(UTC)
    live_or_final: list[str] = []
    upcoming: list[str] = []

    for event in events:
        line, state = _format_odds_event_line(event, now_utc)
        if state in {"live", "final"}:
            live_or_final.append(line)
        else:
            upcoming.append(line)

    if live_or_final:
        return live_or_final[0], "live_or_final"

    league_name = (league or "sports").upper()
    lines = [f"{league_name} games today:"]
    for idx, line in enumerate(upcoming[:3], start=1):
        lines.append(f"{idx}. {line}")
    return "\n".join(lines), "upcoming"


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


async def _fetch_theodds_sports(api_key: str) -> list[dict]:
    url = "https://api.the-odds-api.com/v4/sports"
    params = {"apiKey": api_key}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []


async def _fetch_theodds_scores(api_key: str, sport_key: str, days_from: int = 2) -> list[dict]:
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores"
    params = {"apiKey": api_key, "daysFrom": max(1, int(days_from))}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
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
    if provider not in {"sportsdataio", "sportradar", "theoddsapi"}:
        return _safe_error("sports", SPORTS_PROVIDER_FAILURE_MESSAGE, "unsupported_provider")
    if not api_key:
        return _safe_error(provider, SPORTS_PROVIDER_FAILURE_MESSAGE, "missing_api_key")

    cache_key = f"sports:scores:{provider}:{league}:{date_local}"
    cached, stale = CACHE.get(cache_key)
    if isinstance(cached, LiveDataResult) and not stale and not cached.safe_error:
        return cached

    try:
        if provider == "sportsdataio":
            games = await _fetch_games_sportsdataio(api_key, league, date_local)
            result = _result_from_games(provider, league, games, require_timestamp=require_timestamp)
        elif provider == "theoddsapi":
            sports_cache_key = "sports:theoddsapi:sports-list"
            sports_catalog, sports_stale = CACHE.get(sports_cache_key)
            if not isinstance(sports_catalog, list) or sports_stale:
                sports_catalog = await _fetch_theodds_sports(api_key)
                CACHE.set(sports_cache_key, sports_catalog, max(cache_seconds, 60), max(stale_after, 60))

            sport_key = _resolve_odds_sport_key(league, sports_catalog)
            if not sport_key:
                result = _safe_error(provider, UNSUPPORTED_LEAGUE_MESSAGE, "unsupported_league")
                CACHE.set(cache_key, result, cache_seconds, stale_after, is_error=True)
                return result

            events = await _fetch_theodds_scores(api_key, sport_key)
            if not events:
                result = _safe_error(provider, SPORTS_PROVIDER_FAILURE_MESSAGE, "no_games")
                CACHE.set(cache_key, result, cache_seconds, stale_after, is_error=True)
                return result

            source_ts = _latest_source_timestamp(events)
            if require_timestamp and source_ts is None:
                result = _safe_error(provider, SPORTS_PROVIDER_FAILURE_MESSAGE, "missing_timestamp")
                CACHE.set(cache_key, result, cache_seconds, stale_after, is_error=True)
                return result

            summary_body, _ = _build_odds_summary(league, events)
            updated_label = _format_et(source_ts or datetime.now(UTC))
            result = LiveDataResult(
                success=True,
                provider=provider,
                retrieved_at_utc=utc_now_iso(),
                source_timestamp_utc=source_ts.isoformat() if source_ts else None,
                is_live=True,
                is_delayed=False,
                delay_minutes=None,
                confidence="high",
                raw_status="ok",
                human_summary=f"{summary_body}\n\nUpdated: {updated_label}\nSource: The Odds API",
                data={"league": (league or "").upper(), "games": len(events), "sport_key": sport_key},
            )
        else:
            return _safe_error(provider, SPORTS_PROVIDER_FAILURE_MESSAGE, "sportradar_not_configured")

        CACHE.set(cache_key, result, cache_seconds, stale_after, is_error=not result.success)
        logger.info(
            "live_data.sports scores",
            extra={"provider": provider, "league": league.upper(), "success": result.success, "games": result.data.get("games", 0)},
        )
        return result
    except ValueError:
        result = _safe_error(provider, UNSUPPORTED_LEAGUE_MESSAGE, "unsupported_league")
    except httpx.TimeoutException:
        result = _safe_error(provider, SPORTS_PROVIDER_FAILURE_MESSAGE, "timeout")
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if provider == "theoddsapi" and status == 422:
            result = _safe_error(provider, UNSUPPORTED_LEAGUE_MESSAGE, "unsupported_league")
        else:
            result = _safe_error(provider, SPORTS_PROVIDER_FAILURE_MESSAGE, f"http_{status}")
    except Exception:
        result = _safe_error(provider, SPORTS_PROVIDER_FAILURE_MESSAGE, "exception")

    CACHE.set(cache_key, result, cache_seconds, stale_after, is_error=True)
    return result


async def get_game_status(config, league: str, team: str, opponent: str, date_local: str) -> LiveDataResult:
    team_code, prompt = _resolve_team(league, team)
    if prompt:
        provider = (getattr(config, "sports_data_provider", "sportsdataio") or "sportsdataio")
        return _safe_error(provider, prompt, "ambiguous_team")

    provider, api_key, _, _, _ = _provider_settings(config)
    if provider == "theoddsapi":
        if not api_key:
            return _safe_error(provider, SPORTS_PROVIDER_FAILURE_MESSAGE, "missing_api_key")
        sports = await _fetch_theodds_sports(api_key)
        sport_key = _resolve_odds_sport_key(league, sports)
        if not sport_key:
            return _safe_error(provider, UNSUPPORTED_LEAGUE_MESSAGE, "unsupported_league")
        events = await _fetch_theodds_scores(api_key, sport_key)
        filtered = [e for e in events if _event_matches_team(e, team_code or "") and _event_matches_opponent(e, opponent)]
        if not filtered:
            return _safe_error(provider, SPORTS_PROVIDER_FAILURE_MESSAGE, "no_team_game")
        source_ts = _latest_source_timestamp(filtered)
        line, _ = _format_odds_event_line(filtered[0], datetime.now(UTC))
        updated = _format_et(source_ts or datetime.now(UTC))
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
            human_summary=f"{line}\n\nUpdated: {updated}\nSource: The Odds API",
            data={"league": league.upper(), "team": team_code, "sport_key": sport_key},
        )

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

    provider_name, api_key, _, _, _ = _provider_settings(config)
    if provider_name == "theoddsapi":
        if not api_key:
            return _safe_error(provider_name, SPORTS_PROVIDER_FAILURE_MESSAGE, "missing_api_key")
        sports = await _fetch_theodds_sports(api_key)
        sport_key = _resolve_odds_sport_key(league, sports)
        if not sport_key:
            return _safe_error(provider_name, UNSUPPORTED_LEAGUE_MESSAGE, "unsupported_league")
        events = await _fetch_theodds_scores(api_key, sport_key)
        filtered = [e for e in events if _event_matches_team(e, team_code or "")]
        if not filtered:
            return _safe_error(provider_name, SPORTS_PROVIDER_FAILURE_MESSAGE, "no_team_schedule")

        lines = []
        for idx, event in enumerate(filtered[:3], start=1):
            line, _ = _format_odds_event_line(event, datetime.now(UTC))
            lines.append(f"{idx}. {line}")
        source_ts = _latest_source_timestamp(filtered)
        updated = _format_et(source_ts or datetime.now(UTC))
        return LiveDataResult(
            success=True,
            provider=provider_name,
            retrieved_at_utc=utc_now_iso(),
            source_timestamp_utc=source_ts.isoformat() if source_ts else None,
            is_live=True,
            is_delayed=False,
            delay_minutes=None,
            confidence="high",
            raw_status="ok",
            human_summary=f"{team_code.upper()} schedule:\n" + "\n".join(lines) + f"\n\nUpdated: {updated}\nSource: The Odds API",
            data={"team": team_code, "league": league.upper(), "sport_key": sport_key},
        )

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
