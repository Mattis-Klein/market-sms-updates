from __future__ import annotations

from .allowlist import normalize_phone_number


POWERBALL_ONLY_PROFILE = "powerball_only"

USER_PROFILES = {
    normalize_phone_number("+17184733934"): POWERBALL_ONLY_PROFILE,
}

KEYWORD_PROFILES = {
    POWERBALL_ONLY_PROFILE: {
        "allowed_keywords": {
            "MENU",
            "CHECK",
            "LOTTO",
            "GUIDE",
            "POWERBALL",
            "PB",
            "JACKPOT",
            "NUMBERS",
        },
        "menu_type": "powerball",
    }
}


def get_user_profile(phone_number: str) -> str | None:
    return USER_PROFILES.get(normalize_phone_number(phone_number))


def get_keyword_profile(profile_name: str) -> dict | None:
    return KEYWORD_PROFILES.get(profile_name)
