from __future__ import annotations

from urllib.parse import quote, unquote, unquote_plus

import requests
from fastapi import HTTPException


def _workflow_id_candidates(workflow_id: str) -> list[str]:
    raw = (workflow_id or "").strip()
    if not raw:
        return []

    out: list[str] = []

    def add(value: str) -> None:
        candidate = (value or "").strip()
        if candidate and candidate not in out:
            out.append(candidate)

    add(raw)
    decoded = unquote(raw)
    add(decoded)
    plus_decoded = unquote_plus(raw)
    add(plus_decoded)

    base_variants: list[str] = []
    for value in (raw, decoded, plus_decoded):
        v = (value or "").strip()
        if v and v not in base_variants:
            base_variants.append(v)

    for value in base_variants:
        if "+" in value:
            add(value.replace("+", " "))
        if " " in value:
            add(value.replace(" ", "+"))
        if " " in value:
            add(value.replace(" ", "_"))
        if "_" in value:
            add(value.replace("_", " "))

    ext_variants = list(out)
    for value in ext_variants:
        if value.lower().endswith(".json"):
            add(value[: -len(".json")])
        else:
            add(f"{value}.json")

    return out


def fetch_workflow_from_comfyui(comfy_url: str, workflow_id: str) -> tuple[str, dict]:
    base = (comfy_url or "").rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="ComfyUI URL not configured")

    candidates = _workflow_id_candidates(workflow_id)
    if not candidates:
        raise HTTPException(status_code=400, detail="workflow_id is required")

    for candidate in candidates:
        url = f"{base}/workflowui/workflows/{quote(candidate, safe='')}"
        try:
            response = requests.get(url, timeout=15)
        except (requests.ConnectionError, requests.Timeout) as e:
            raise HTTPException(status_code=502, detail=f"ComfyUI plugin unreachable: {e!s}") from e
        except requests.RequestException as e:
            raise HTTPException(status_code=502, detail=f"ComfyUI request failed: {e!s}") from e

        if response.status_code == 404:
            continue

        if not response.ok:
            raise HTTPException(
                status_code=502,
                detail=f"ComfyUI plugin returned HTTP {response.status_code} for workflow lookup",
            )

        try:
            data = response.json()
        except ValueError as e:
            raise HTTPException(status_code=502, detail="ComfyUI plugin returned invalid JSON") from e

        if not isinstance(data, dict):
            raise HTTPException(status_code=502, detail="ComfyUI plugin returned invalid response")

        graph = data.get("graph")
        if not isinstance(graph, dict) or not graph:
            raise HTTPException(status_code=502, detail="ComfyUI plugin did not return a valid workflow graph")

        name = data.get("name") or candidate or workflow_id or "Imported from ComfyUI"
        return (name.strip() or "Imported from ComfyUI"), graph

    raise HTTPException(status_code=404, detail=f'Workflow not found in ComfyUI plugin: "{workflow_id}"')
