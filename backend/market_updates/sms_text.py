from __future__ import annotations

import re

CONTINUATION_PREFIX = "[CONTINUATION_REMAINDER]"

_URL_PATTERN = re.compile(r"(https?://\S+|www\.\S+)", flags=re.IGNORECASE)


def sanitize_sms_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove fenced code markers and inline backticks while keeping readable content.
    cleaned = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", cleaned)
    cleaned = cleaned.replace("```", "")
    cleaned = cleaned.replace("`", "")

    # Strip markdown headings.
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", cleaned, flags=re.MULTILINE)

    # Keep anchor text while dropping markdown link URL.
    cleaned = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r"\1", cleaned)

    # Convert star bullets to dash bullets for plain SMS readability.
    cleaned = re.sub(r"^\s*\*\s+", "- ", cleaned, flags=re.MULTILINE)

    # Remove common markdown emphasis markers.
    cleaned = cleaned.replace("**", "")
    cleaned = cleaned.replace("__", "")
    cleaned = re.sub(r"(?<!\S)\*(?=\S)|(?<=\S)\*(?!\S)", "", cleaned)
    cleaned = re.sub(r"(?<!\S)_(?=\S)|(?<=\S)_(?!\S)", "", cleaned)

    # Remove citation artifacts from tool outputs.
    cleaned = re.sub(r"【[^】]*†[^】]*】", "", cleaned)
    cleaned = re.sub(r"\[\d+\]", "", cleaned)

    # Remove remaining URLs, including bare source links.
    cleaned = _URL_PATTERN.sub("", cleaned)

    # Remove horizontal rules and decorative markdown punctuation.
    cleaned = re.sub(r"^\s*([-_*])\1{2,}\s*$", "", cleaned, flags=re.MULTILINE)

    # Keep SMS-safe printable ASCII plus line breaks.
    cleaned = "".join(ch if ch == "\n" or 32 <= ord(ch) <= 126 else " " for ch in cleaned)

    # Clean trailing markdown list punctuation and excess spacing.
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n[ \t]+", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def fit_sms_with_more(text: str, max_chars: int) -> tuple[str, str]:
    body = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    body = body.strip()

    if len(body) <= max_chars:
        return body, ""

    marker = "Reply MORE for the rest."
    reserve = len(marker) + 1
    limit = max(40, max_chars - reserve)

    clipped = body[:limit].rstrip()
    if " " in clipped and len(body) > limit:
        clipped = clipped.rsplit(" ", 1)[0].rstrip()

    remainder = body[len(clipped) :].lstrip()
    if not remainder:
        return clipped[:max_chars].rstrip(), ""

    return f"{clipped}\n{marker}", remainder
