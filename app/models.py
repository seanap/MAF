from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class WedgeDecision:
    use_wedge: bool
    reason: str
    mode: str
    override: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def canonical_key(torrent_id: str | int) -> str:
    return f"mam:torrent:{str(torrent_id).strip()}"
