"""ComfyUI version metadata hashing for deduplication. No DB or FastAPI."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_comfyui_metadata_hash(version_info: dict[str, Any]) -> str:
    """Deterministic hash of full ComfyUI metadata (excluding fetched_at_ms).
    Same environment => same hash; any change in ComfyUI/plugins => new hash.
    """
    if not isinstance(version_info, dict):
        return hashlib.sha256(b"").hexdigest()
    canonical = {k: v for k, v in version_info.items() if k != "fetched_at_ms"}
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
