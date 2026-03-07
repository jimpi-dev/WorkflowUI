from __future__ import annotations

import json
import logging
import os
import random
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import requests

from services.comfyui_info import normalize_comfy_url
from services.workflow_analyzer import _workflow_ui_link_widget_order
from services.workflow_convert import convert_workflow_via_comfy

logger = logging.getLogger(__name__)

MAX_SEED = 1125899906842624
COMFYUI_INT_MAX = 2147483647

WIDGET_ORDER: dict[str, list[str]] = {
    "WorkflowUILink": _workflow_ui_link_widget_order(),
    "WorkflowUI Link": _workflow_ui_link_widget_order(),
    "EmptyLatentImage": ["width", "height", "batch_size"],
    "EmptySD3LatentImage": ["width", "height", "batch_size"],
    "SDXLEmptyLatentSizePicker+": ["resolution", "batch_size", "width_override", "height_override"],
    "KSampler": ["seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
    "DiffusionModelLoader": ["unet_name", "weight_dtype"],
    "LoadDiffusionModel": ["unet_name", "weight_dtype"],
    "StableCascadeCheckpointLoader": ["key_opt_b", "key_opt_c", "cache_mode"],
    "StableCascade_CheckpointLoader": ["key_opt_b", "key_opt_c", "cache_mode"],
    "SD3CheckpointLoader": ["ckpt_name", "shift"],
    "SD3LoadCheckpoint": ["ckpt_name", "shift"],
}

DIMENSION_FIELDS = frozenset({"width", "height", "width_override", "height_override", "batch_size"})
INTEGER_BINDING_FIELDS = frozenset({
    "width", "height", "width_override", "height_override", "batch_size",
    "steps", "cfg", "seed", "noise_seed",
})


def _resolve_seed(raw_value: Any) -> int:
    raw = int(raw_value) if raw_value not in (None, "") else 0
    if raw == 0:
        return random.randint(0, MAX_SEED)
    return min(raw, MAX_SEED)


_OUTPUT_NODE_TYPES = frozenset({
    "SaveImage", "Save Image", "Save Image (api)", "SaveImageNode",
    "PreviewImage", "Preview Image",
    "SaveImageWebp", "Save Image (WebP)",
    "SaveAnimatedWEBP", "Save Animated WEBP",
    "SaveAnimatedPNG", "Save Animated PNG",
})


def _build_link_map(links: list[Any]) -> dict[int | str, tuple[str, int]]:
    """Build link_id -> (origin_node_id, origin_slot). Uses _parse_link for array/object link format."""
    result: dict[int | str, tuple[str, int]] = {}
    if not isinstance(links, list):
        return result
    for link in links:
        parsed = _parse_link(link)
        if parsed is None:
            continue
        origin_id, _target_id, origin_slot, link_id = parsed
        result[link_id] = (origin_id, origin_slot)
    return result


def _parse_link(link: Any) -> tuple[str, str, int, int | str] | None:
    """Parse a link (array or object) into (origin_id, target_id, origin_slot, link_id). Returns None if invalid."""
    if isinstance(link, (list, tuple)) and len(link) >= 6:
        link_id, origin_id, origin_slot, target_id, _target_slot, _ = (
            link[0], link[1], link[2], link[3], link[4], link[5]
        )
        try:
            return (str(origin_id), str(target_id), int(origin_slot), link_id)
        except (TypeError, ValueError):
            return None
    if isinstance(link, dict) and "origin_id" in link and "target_id" in link:
        try:
            oid = str(link["origin_id"])
            tid = str(link["target_id"])
            slot = int(link.get("origin_slot", 0))
            lid = link.get("id", (oid, tid))
            return (oid, tid, slot, lid)
        except (TypeError, ValueError, KeyError):
            return None
    return None


def _dependency_map(links: list[Any]) -> dict[str, set[str]]:
    """Build target_id -> set(origin_id) so we can traverse backward from output nodes.
    Supports link format: array [link_id, origin_id, origin_slot, target_id, target_slot, type] or
    object { id, origin_id, origin_slot, target_id, target_slot, type }."""
    dep: dict[str, set[str]] = {}
    if not isinstance(links, list):
        return dep
    for link in links:
        parsed = _parse_link(link)
        if parsed is None:
            continue
        origin_id, target_id, _origin_slot, _link_id = parsed
        dep.setdefault(target_id, set()).add(origin_id)
    return dep


def _required_node_ids_from_ui(nodes: list[Any], links: list[Any]) -> set[str] | None:
    """Set of node IDs that must run: those reachable backward from output nodes (SaveImage, etc.).
    Returns None if no output nodes found (caller should not filter)."""
    if not isinstance(nodes, list) or not nodes:
        return None
    dep = _dependency_map(links) if isinstance(links, list) else {}
    id_to_type: dict[str, str] = {}
    id_to_mode: dict[str, int] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        nid = node.get("id")
        if nid is None:
            continue
        sid = str(nid)
        id_to_type[sid] = (node.get("type") or node.get("class_type") or "") or ""
        id_to_mode[sid] = node.get("mode", 0)
    output_ids = [
        nid for nid, ct in id_to_type.items()
        if ct in _OUTPUT_NODE_TYPES and id_to_mode.get(nid, 0) != 4
    ]
    if not output_ids:
        return None
    required: set[str] = set()
    queue = list(output_ids)
    while queue:
        nid = queue.pop()
        if nid in required:
            continue
        required.add(nid)
        for origin_id in dep.get(nid, ()):
            queue.append(origin_id)
    return required


def _inputs_from_ui_node(
    node: dict,
    class_type: str,
    link_map: dict[int | str, tuple[str, int]],
) -> dict[str, Any]:
    """Build API-style inputs dict from a UI-format node (inputs array + optional widgets_values).
    ComfyUI 0.4: node.inputs is an array of { name, type, link? }. Resolve links to [origin_id, origin_slot];
    for inputs with no link, take values from widgets_values by order."""
    inputs: dict[str, Any] = {}
    node_inputs = node.get("inputs")
    widgets_values = node.get("widgets_values") or node.get("widgetsValues")
    widget_order = WIDGET_ORDER.get(class_type)

    if isinstance(widgets_values, list) and widget_order:
        for idx, field in enumerate(widget_order):
            if idx < len(widgets_values):
                inputs[field] = widgets_values[idx]

    if isinstance(node_inputs, list):
        widget_only_names: list[str] = []
        for inp in node_inputs:
            if not isinstance(inp, dict):
                continue
            name = inp.get("name")
            if not name or not isinstance(name, str):
                continue
            link = inp.get("link")
            if link is not None:
                conn = link_map.get(link)
                if conn is not None:
                    inputs[name] = [conn[0], conn[1]]
            else:
                widget_only_names.append(name)
        for idx, name in enumerate(widget_only_names):
            if name not in inputs and isinstance(widgets_values, list) and idx < len(widgets_values):
                inputs[name] = widgets_values[idx]
    elif isinstance(node_inputs, dict):
        for k, v in node_inputs.items():
            if k not in inputs:
                inputs[k] = v
    return inputs


def prompt_to_api_format(prompt: dict) -> dict:
    if not isinstance(prompt, dict):
        return prompt
    nodes = prompt.get("nodes")
    if not isinstance(nodes, list):
        return prompt
    links = prompt.get("links")
    link_map = _build_link_map(links) if isinstance(links, list) else {}
    required_ids = _required_node_ids_from_ui(nodes, links)
    out: dict[str, dict] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("mode") == 4:
            continue
        nid = node.get("id")
        if nid is None:
            continue
        node_id = str(nid)
        if required_ids is not None and node_id not in required_ids:
            continue
        class_type = node.get("type") or node.get("class_type")
        if not class_type:
            continue
        inputs = _inputs_from_ui_node(node, class_type, link_map)
        out[node_id] = {"class_type": class_type, "inputs": inputs}
    _normalize_workflow_ui_link_inputs(out)
    _ensure_saveimage_defaults(out)
    _ensure_only_referenced_nodes_in_prompt(out)
    return out if out else prompt


def _ensure_only_referenced_nodes_in_prompt(prompt: dict) -> None:
    """Remove any input value that references a node not in the prompt (dangling ref).
    Ensures we only send nodes that shall be loaded and that every [node_id, slot] ref exists."""
    if not isinstance(prompt, dict):
        return
    valid_ids = frozenset(prompt.keys())
    for node in prompt.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for key, value in list(inputs.items()):
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                try:
                    ref_id = str(value[0])
                    if ref_id not in valid_ids:
                        del inputs[key]
                        logger.warning(
                            "Dropped input %s -> [%s, ...] (node %s not in prompt)",
                            key, ref_id, ref_id,
                        )
                except (TypeError, ValueError):
                    pass


def _ensure_saveimage_defaults(prompt: dict) -> None:
    """Ensure SaveImage nodes have required filename_prefix so ComfyUI validation passes."""
    save_types = ("SaveImage", "Save Image", "Save Image (api)", "SaveImageNode")
    for node in (prompt or {}).values():
        if not isinstance(node, dict) or node.get("class_type") not in save_types:
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        if not inputs.get("filename_prefix"):
            inputs["filename_prefix"] = "ComfyUI"


def _normalize_workflow_ui_link_inputs(prompt: dict) -> None:
    """Coerce WorkflowUILink node inputs so unused slots pass ComfyUI validation (INT/BOOLEAN)."""
    for node in (prompt or {}).values():
        if not isinstance(node, dict):
            continue
        if node.get("class_type") not in ("WorkflowUILink", "WorkflowUI Link"):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for key, value in list(inputs.items()):
            if key.startswith("input_number_"):
                if value in (None, ""):
                    inputs[key] = 0
                else:
                    try:
                        n = int(float(value))
                        inputs[key] = max(0, min(n, COMFYUI_INT_MAX))
                    except (TypeError, ValueError):
                        inputs[key] = 0
            elif key.startswith("input_boolean_"):
                if value in (False, 0, "false", "0", "", None):
                    inputs[key] = False
                else:
                    inputs[key] = True
            elif key.startswith("input_image_") or key.startswith("input_video_") or key.startswith("input_audio_"):
                if not isinstance(value, str) or value in (None, "false", "0"):
                    inputs[key] = ""


def resolve_node(prompt: dict, node_id: str) -> dict | None:
    if not isinstance(prompt, dict):
        return None
    if node_id in prompt:
        return prompt[node_id]
    parts = node_id.split(":")
    current = prompt
    for part in parts:
        if not isinstance(current, dict):
            return None
        if part in current:
            current = current[part]
            continue
        if "inputs" in current and part in current["inputs"]:
            current = current["inputs"][part]
            continue
        return None
    return current


def _coerce_binding_value(field_path: str, value: Any) -> Any:
    last_part = field_path.split(".")[-1]
    if (
        last_part in INTEGER_BINDING_FIELDS
        or last_part.endswith("_int")
        or last_part.endswith("_number")
        or last_part.startswith("input_number_")
    ):
        if value in (None, ""):
            return 0
        try:
            n = int(float(value))
            if last_part.startswith("input_number_"):
                n = max(0, min(n, COMFYUI_INT_MAX))
            elif last_part in ("seed", "noise_seed"):
                n = max(0, min(n, MAX_SEED))
            return n
        except (TypeError, ValueError):
            return 0
    if last_part.startswith("input_boolean_"):
        if isinstance(value, bool):
            return value
        if value in (True, 1, "true", "1"):
            return True
        if value in (False, 0, "false", "0", "", None):
            return False
        return bool(value)
    if last_part in ("strength", "strength_model"):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return value


def apply_binding(node: dict, field_path: str, value: Any) -> None:
    if "inputs" not in node or not isinstance(node["inputs"], dict):
        node["inputs"] = {}
    value = _coerce_binding_value(field_path, value)
    parts = field_path.split(".")
    if len(parts) == 1:
        node["inputs"][parts[0]] = value
        return
    if len(parts) == 2:
        group_key, sub_key = parts
        if group_key not in node["inputs"]:
            node["inputs"][group_key] = {}
        node["inputs"][group_key][sub_key] = _coerce_binding_value(sub_key, value)


def used_node_class_types_from_prompt(prompt: dict) -> list[str]:
    if not isinstance(prompt, dict):
        return []
    seen: set[str] = set()
    for node in prompt.values():
        if isinstance(node, dict):
            ct = node.get("class_type")
            if ct and isinstance(ct, str):
                seen.add(ct)
    return sorted(seen)


def upload_file_to_comfy(comfy_url: str, file_path: Path, content_type: str) -> str:
    with open(file_path, "rb") as f:
        content = f.read()
    name = file_path.name
    files = {"image": (name, content, content_type)}
    res = requests.post(
        f"{normalize_comfy_url(comfy_url).rstrip('/')}/upload/image",
        files=files,
        timeout=60,
    )
    res.raise_for_status()
    data = res.json()
    return data.get("name") or name


def merge_comfyui_version_into_metadata(run_entity: Any, comfyui_version_info: dict) -> str:
    current = {}
    if run_entity.metadata_snapshot_json:
        try:
            current = json.loads(run_entity.metadata_snapshot_json)
        except Exception:
            pass
    if not isinstance(current, dict):
        current = {}
    current["ComfyUI-VersionInfo"] = comfyui_version_info
    return json.dumps(current)


def build_slim_metadata_snapshot(run_entity: Any, comfyui_version_id: str) -> str:
    current: dict = {}
    if run_entity.metadata_snapshot_json:
        try:
            current = json.loads(run_entity.metadata_snapshot_json)
        except Exception:
            pass
    if not isinstance(current, dict):
        current = {}
    current.pop("ComfyUI-VersionInfo", None)
    current["comfyui_version_id"] = comfyui_version_id
    return json.dumps(current)


class RunExecutor:
    def __init__(self, default_comfy_url: str, input_data_dir: Path):
        self._default_comfy_url = default_comfy_url
        self._input_data_dir = input_data_dir

    def _job_comfy_url(self, job: dict) -> str:
        return (normalize_comfy_url(job.get("comfyui_url") or self._default_comfy_url)).rstrip("/")

    def execute(
        self,
        job: dict,
        get_db: Callable[[], Any],
        is_cancelled: Callable[[str], bool],
    ) -> tuple[str, list[dict], int | None, float]:
        prompt = job.get("prompt")
        if prompt is None:
            workflow_id = job.get("workflow_id")
            if not workflow_id:
                raise ValueError("job must have prompt or workflow_id")
            with open(f"workflows/{workflow_id}.json", "r", encoding="utf-8") as f:
                prompt = json.load(f)
        comfy_url = self._job_comfy_url(job)
        if isinstance(prompt, dict) and prompt.get("nodes") is not None:
            logger.info(
                "Run: prompt is UI format (%s nodes, %s links), calling workflow convert endpoint",
                len(prompt.get("nodes", [])), len(prompt.get("links", [])),
            )
            api_prompt = convert_workflow_via_comfy(comfy_url, prompt)
            if api_prompt is not None:
                prompt = api_prompt
                logger.info(
                    "Run: workflow convert SUCCESS — using API format (%s nodes) for execution.",
                    len(prompt),
                )
            else:
                logger.warning(
                    "Run: workflow convert FAILED or unavailable — using built-in UI→API conversion (possible OOM).",
                )
                prompt = prompt_to_api_format(prompt)
        else:
            prompt = prompt_to_api_format(prompt)
            if isinstance(prompt, dict):
                logger.debug("Run: prompt was already API format or converted via built-in; %s nodes", len(prompt))
        if isinstance(prompt, dict):
            _normalize_workflow_ui_link_inputs(prompt)
        job["prompt"] = prompt
        payload = job.get("payload") or {}
        values = dict(payload.get("values") or {})
        default_inputs_applied = job.get("default_inputs_applied")
        if isinstance(default_inputs_applied, dict):
            for k, v in default_inputs_applied.items():
                if k not in values:
                    values[k] = v
        else:
            default_inputs = job.get("default_inputs") or {}
            if isinstance(default_inputs, dict):
                for k, v in default_inputs.items():
                    if k not in values:
                        values[k] = v
        payload = dict(payload)
        payload["values"] = values
        bindings = payload.get("bindings", [])

        seed = None
        for b in bindings:
            if b.get("field") in ("seed", "noise_seed"):
                raw = values.get(b["key"], 0)
                seed = _resolve_seed(raw)
                break

        comfy_url = self._job_comfy_url(job)
        input_from_run = job.get("input_from_run")
        parent_run_id = input_from_run.get("run_id") if isinstance(input_from_run, dict) else None
        input_key_from_run = input_from_run.get("input_key") if isinstance(input_from_run, dict) else None
        parent_run = None
        parent_media_entry = None
        if parent_run_id and input_key_from_run and isinstance(input_from_run, dict):
            run_repo = get_db()[3]
            parent_run = run_repo.get_run(parent_run_id) if run_repo else None
            if parent_run:
                output_index = input_from_run.get("output_index")
                if output_index is not None:
                    media_list = None
                    if parent_run.media_json:
                        try:
                            media_list = json.loads(parent_run.media_json)
                        except json.JSONDecodeError:
                            pass
                    if not media_list and parent_run.images_json:
                        try:
                            media_list = json.loads(parent_run.images_json)
                        except json.JSONDecodeError:
                            pass
                    if isinstance(media_list, list) and 0 <= output_index < len(media_list):
                        ent = media_list[output_index]
                        if isinstance(ent, dict) and not ent.get("file_deleted"):
                            parent_media_entry = ent

        mime_by_ext = {
            **{".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"},
            **{".mp4": "video/mp4", ".webm": "video/webm", ".mkv": "video/x-matroska", ".mov": "video/quicktime"},
            **{".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".flac": "audio/flac", ".m4a": "audio/mp4"},
        }
        def _is_media_upload_field(f: str) -> bool:
            if f == "image":
                return True
            return f.startswith("input_image_") or f.startswith("input_video_") or f.startswith("input_audio_")

        for b in bindings:
            field = b.get("field")
            if not field or not _is_media_upload_field(field):
                continue
            key = b.get("key")
            if not key:
                continue
            value = values.get(key)
            if not isinstance(value, str) or not value.strip():
                continue
            if key == input_key_from_run and parent_run and parent_media_entry:
                parent_comfy = normalize_comfy_url(parent_run.comfyui_url or self._default_comfy_url)
                filename = parent_media_entry.get("filename") or value.strip()
                subfolder = (parent_media_entry.get("subfolder") or "").strip()
                typ = (parent_media_entry.get("type") or parent_media_entry.get("kind") or "output").strip().lower()
                comfy_type = "output" if typ in ("image", "video", "audio") else typ
                try:
                    view_url = f"{parent_comfy.rstrip('/')}/view"
                    view_params = {"filename": filename, "subfolder": subfolder, "type": comfy_type}
                    res = requests.get(view_url, params=view_params, timeout=60)
                    res.raise_for_status()
                    content = res.content
                    ext = Path(filename).suffix.lower() or ".png"
                    mime = mime_by_ext.get(ext, "image/png")
                    files = {"image": (filename, content, mime)}
                    upload_res = requests.post(f"{comfy_url.rstrip('/')}/upload/image", files=files, timeout=60)
                    upload_res.raise_for_status()
                    upload_data = upload_res.json()
                    uploaded_name = upload_data.get("name") or filename
                    values[key] = uploaded_name
                    payload["values"] = values
                    logger.info("Send-to-App: fetched image from parent run %s, uploaded as %s", parent_run_id, uploaded_name)
                except requests.RequestException as e:
                    logger.warning("Send-to-App: fetch/upload from parent run failed: %s", e)
                    raise RuntimeError(f"Failed to use image from previous run: {e!s}") from e
                continue
            local_path = self._input_data_dir / value.strip()
            if local_path.is_file():
                ext = local_path.suffix.lower()
                mime = mime_by_ext.get(ext, "application/octet-stream")
                try:
                    upload_file_to_comfy(comfy_url, local_path, mime)
                except requests.RequestException as e:
                    logger.warning("Re-upload input image %s to ComfyUI failed: %s", value, e)

        for b in bindings:
            key = b.get("key")
            node_id = str(b["nodeId"]) if b.get("nodeId") is not None else None
            field_path = b.get("field")
            if not key or node_id is None or not field_path:
                continue
            node = resolve_node(prompt, node_id)
            if not node:
                continue
            value = values.get(key)
            if value is None and field_path in DIMENSION_FIELDS:
                node_inputs = node.get("inputs") or {}
                value = node_inputs.get(field_path)
            if field_path in ("seed", "noise_seed") and seed is not None:
                value = seed
            if value is None:
                continue
            if field_path in DIMENSION_FIELDS and value is not None:
                try:
                    value = int(float(value))
                except (TypeError, ValueError):
                    pass
            apply_binding(node, field_path, value)

        exec_start = time.time()
        base_url = comfy_url.rstrip("/")
        res = requests.post(
            f"{base_url}/prompt",
            json={"prompt": prompt, "client_id": str(uuid.uuid4())},
        )
        if not res.ok:
            try:
                err_body = res.text
                if res.headers.get("content-type", "").startswith("application/json"):
                    err_body = res.json()
                logger.error(
                    "ComfyUI /prompt failed: status=%s url=%s body=%s",
                    res.status_code,
                    res.url,
                    err_body,
                )
            except Exception:
                logger.error(
                    "ComfyUI /prompt failed: status=%s url=%s body=%s",
                    res.status_code,
                    res.url,
                    res.text[:500] if res.text else "",
                )
            res.raise_for_status()
        prompt_id = res.json()["prompt_id"]

        run_id = job.get("run_id")

        def output_type(raw_type: str, filename: str) -> str:
            if raw_type == "audio":
                return "audio"
            if raw_type == "video":
                return "video"
            if raw_type == "output" and filename:
                lower = filename.lower()
                if any(lower.endswith(ext) for ext in (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".webm")):
                    return "audio"
            return raw_type if raw_type else "image"

        while True:
            if run_id and is_cancelled(run_id):
                raise RuntimeError("Cancelled")
            hist_res = requests.get(f"{base_url}/history/{prompt_id}")
            history = hist_res.json()
            if prompt_id not in history:
                time.sleep(1.5)
                continue
            outputs = []
            for nid, node in history[prompt_id]["outputs"].items():
                idx = 0
                if "images" in node:
                    for img in node["images"]:
                        raw = img.get("type", "image")
                        outputs.append({
                            "filename": img["filename"],
                            "subfolder": img.get("subfolder", ""),
                            "type": output_type(raw, img.get("filename", "")),
                            "nodeId": nid,
                            "outputIndex": idx,
                        })
                        idx += 1
                if "gifs" in node:
                    for gif in node["gifs"]:
                        outputs.append({
                            "filename": gif["filename"],
                            "subfolder": gif.get("subfolder", ""),
                            "type": "video",
                            "nodeId": nid,
                            "outputIndex": idx,
                        })
                        idx += 1
                if "audio" in node:
                    for aud in node["audio"]:
                        outputs.append({
                            "filename": aud["filename"],
                            "subfolder": aud.get("subfolder", ""),
                            "type": "audio",
                            "nodeId": nid,
                            "outputIndex": idx,
                        })
                        idx += 1
            execution_time_sec = round(time.time() - exec_start, 1)
            return (prompt_id, outputs, seed, execution_time_sec)
