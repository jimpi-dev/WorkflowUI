import hashlib
import json


def _canonicalize(obj: dict | list | str | int | float | bool | None):
    if isinstance(obj, dict):
        return {k: _canonicalize(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_canonicalize(v) for v in obj]
    return obj


def graph_hash(graph: dict) -> str:
    canonical = _canonicalize(graph)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
