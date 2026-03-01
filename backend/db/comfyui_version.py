from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_comfyui_metadata_hash(version_info: dict[str, Any]) -> str:
    if not isinstance(version_info, dict):
        return hashlib.sha256(b"").hexdigest()
    excluded = ("fetched_at_ms", "system_stats")
    canonical = {k: v for k, v in version_info.items() if k not in excluded}
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
