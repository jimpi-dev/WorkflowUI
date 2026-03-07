"""
ComfyUI workflow conversion: UI format → API format via a convert endpoint on ComfyUI.

We try, in order:
  1. WorkflowUIPlugin: POST /workflowui/workflowconverter/convert (plugin's workflow_converter.py)
  2. Seth extension:   POST /workflow/convert (Workflow to API Converter Endpoint)

When available, we use it at import time and optionally at run time so the stored/executed
prompt matches ComfyUI's own "Save (API)" output and avoids conversion differences (e.g. OOM).
"""

from __future__ import annotations

import logging
import requests

logger = logging.getLogger(__name__)


def _strip_null_bytes(obj):
    """Recursively remove null bytes from all string keys and values. Prevents 'source code string cannot contain null bytes' in plugin converter."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key = k
            if isinstance(k, str) and ("\x00" in k or "\u0000" in k):
                key = k.replace("\x00", "").replace("\u0000", "")
            out[key] = _strip_null_bytes(v)
        return out
    if isinstance(obj, list):
        return [_strip_null_bytes(v) for v in obj]
    if isinstance(obj, str):
        if "\x00" in obj or "\u0000" in obj:
            return obj.replace("\x00", "").replace("\u0000", "")
        return obj
    return obj


def is_api_format_prompt(p: dict) -> bool:
    """True if p looks like ComfyUI API prompt: { node_id: { class_type, inputs } }."""
    if not p or not isinstance(p, dict):
        return False
    for v in p.values():
        if isinstance(v, dict) and ("class_type" in v or "inputs" in v):
            return True
    return False


def _try_convert(base: str, workflow: dict, path: str) -> dict | None:
    """POST workflow to base + path; return API prompt dict or None."""
    url = f"{base}{path}"
    try:
        res = requests.post(url, json=workflow, timeout=15)
        logger.info(
            "Workflow convert: %s -> status=%s",
            path, res.status_code,
        )
        if not res.ok:
            err_detail = ""
            try:
                data = res.json()
                if isinstance(data, dict):
                    err_detail = data.get("error", "")
                    trace = data.get("traceback") or data.get("detail", "")
                    if isinstance(trace, str) and trace:
                        logger.warning(
                            "Workflow convert %s 500 traceback: %s",
                            path, trace[:1500] if len(trace) > 1500 else trace,
                        )
            except Exception:
                pass
            if not err_detail and res.text:
                err_detail = res.text[:500]
            if err_detail:
                logger.warning("Workflow convert %s failed (status=%s): %s", path, res.status_code, err_detail)
            else:
                logger.warning("Workflow convert %s failed: status=%s (body: %s)", path, res.status_code, res.text[:500] if res.text else "")
            return None
        data = res.json()
        if isinstance(data, dict) and "error" in data:
            logger.warning("Workflow convert %s returned error: %s", path, data.get("error", ""))
            return None
        if is_api_format_prompt(data):
            logger.info("Workflow convert: %s returned API format (%s nodes)", path, len(data))
            return data
        logger.warning("Workflow convert %s response is not API format (no class_type/inputs)", path)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("Workflow convert %s request failed: %s", path, e)
        return None


def convert_workflow_via_comfy(comfy_url: str, workflow: dict) -> dict | None:
    """POST workflow to a ComfyUI convert endpoint; return API-format prompt or None.

    Tries WorkflowUIPlugin /workflowui/workflowconverter/convert first, then /workflow/convert.
    Returns None if comfy_url is missing, workflow is not UI format, all attempts fail,
    or the response is not valid API format.
    """
    if not comfy_url or not isinstance(workflow, dict):
        logger.debug("Workflow convert skipped: missing comfy_url or invalid workflow")
        return None
    nodes = workflow.get("nodes")
    if not nodes or not isinstance(nodes, list):
        logger.debug("Workflow convert skipped: workflow has no 'nodes' list (already API or invalid)")
        return None
    base = comfy_url.rstrip("/")
    num_ui_nodes = len(nodes)
    num_links = len(workflow.get("links") or [])
    node_types = []
    for n in nodes:
        if isinstance(n, dict):
            t = n.get("type") or n.get("class_type")
            if t is not None:
                node_types.append(str(t))
    node_types_set = sorted(set(node_types))
    has_custom = any("workflow_ui" in t.lower() or "WorkflowUI" in t for t in node_types_set)
    logger.info(
        "Workflow convert: attempting conversion (UI format: %s nodes, %s links) -> %s",
        num_ui_nodes, num_links, base,
    )
    logger.info(
        "Workflow convert: node types in workflow (%s): %s (contains WorkflowUI/custom: %s)",
        len(node_types_set), node_types_set[:30] if len(node_types_set) > 30 else node_types_set, has_custom,
    )
    workflow = _strip_null_bytes(workflow)
    result = _try_convert(base, workflow, "/workflowui/workflowconverter/convert")
    if result is not None:
        logger.info(
            "Workflow convert: SUCCESS via /workflowui/workflowconverter/convert, API format has %s nodes",
            len(result),
        )
        return result
    result = _try_convert(base, workflow, "/workflow/convert")
    if result is not None:
        logger.info(
            "Workflow convert: SUCCESS via /workflow/convert, API format has %s nodes",
            len(result),
        )
        return result
    logger.warning(
        "Workflow convert: FAILED (no endpoint responded with API format). "
        "Tried /workflowui/workflowconverter/convert and /workflow/convert.",
    )
    return None
