from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class LiveDataResult:
    success: bool
    provider: str
    retrieved_at_utc: str
    source_timestamp_utc: str | None
    is_live: bool
    is_delayed: bool
    delay_minutes: int | None
    confidence: str
    raw_status: str
    human_summary: str
    safe_error: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_tool_output(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "provider": self.provider,
            "retrieved_at_utc": self.retrieved_at_utc,
            "source_timestamp_utc": self.source_timestamp_utc,
            "is_live": self.is_live,
            "is_delayed": self.is_delayed,
            "delay_minutes": self.delay_minutes,
            "confidence": self.confidence,
            "raw_status": self.raw_status,
            "human_summary": self.human_summary,
            "safe_error": self.safe_error,
            "data": self.data,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
