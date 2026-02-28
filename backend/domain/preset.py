from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AppPreset:
    id: str
    app_id: str
    name: str
    description: str | None
    keys_json: str
    values_json: str
    created_at: int
