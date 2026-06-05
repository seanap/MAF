from __future__ import annotations

from typing import Any

from .models import WedgeDecision

FREE_KEYS = (
    "is_freeleech",
    "freeleech",
    "is_vip_freeleech",
    "is_personal_freeleech",
    "is_sitewide_freeleech",
    "is_fl_vip",
)


def _coerce_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"1", "true", "yes", "y", "free", "vip", "personal", "sitewide", "fl"}:
            return True
        if s in {"0", "false", "no", "n", "none", "normal", ""}:
            return False
    return None


def decide_wedge(
    metadata: dict[str, Any] | None,
    *,
    mode: str = "smart",
    unknown_fallback: bool = True,
    override: bool | None = None,
) -> WedgeDecision:
    mode = (mode or "smart").strip().lower()
    metadata = metadata or {}

    if override is not None:
        return WedgeDecision(bool(override), "forced" if override else "forced_off", mode, override)
    if mode == "never":
        return WedgeDecision(False, "mode_never", mode, override)
    if mode == "always":
        return WedgeDecision(True, "mode_always", mode, override)

    seen = []
    for key in FREE_KEYS:
        if key in metadata:
            seen.append(_coerce_bool(metadata.get(key)))
    if any(v is True for v in seen):
        return WedgeDecision(False, "already_free", "smart", override)
    if any(v is False for v in seen):
        return WedgeDecision(True, "normal_non_free", "smart", override)
    return WedgeDecision(bool(unknown_fallback), "unknown_metadata", "smart", override)
