from __future__ import annotations

import time
from typing import Any

import requests

WORKFLOWUI_PLUGIN_MIN_VERSION = "1.0.11"
COMFYUI_CAPABILITIES_TTL_SEC = 60
COMFYUI_STATUS_TTL_SEC = 2.5

_capabilities_cache: dict[str, Any] = {"result": None, "expires": 0.0}
_status_cache: dict[str, Any] = {"result": None, "expires": 0.0}


def normalize_comfy_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return "http://localhost:8188/"
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url.rstrip("/") + "/"


def _parse_version_parts(version_str: str) -> list[int]:
    if not version_str or not isinstance(version_str, str):
        return [0]
    parts: list[int] = []
    for segment in version_str.strip().split(".")[:8]:
        segment = segment.split("-")[0].split("+")[0].strip()
        try:
            parts.append(int(segment))
        except ValueError:
            parts.append(0)
    return parts if parts else [0]


def version_meets_minimum(installed: str, minimum: str) -> bool:
    a = _parse_version_parts(installed)
    b = _parse_version_parts(minimum)
    for i in range(max(len(a), len(b))):
        ai = a[i] if i < len(a) else 0
        bi = b[i] if i < len(b) else 0
        if ai > bi:
            return True
        if ai < bi:
            return False
    return True


def get_workflowui_plugin_status(comfy_url: str) -> tuple[bool, bool, bool]:
    base = normalize_comfy_url(comfy_url).rstrip("/")
    now = time.time()
    if _capabilities_cache.get("url") == base and _capabilities_cache["result"] is not None and now < _capabilities_cache["expires"]:
        c = _capabilities_cache["result"]
        return c["delete_supported"], c["plugin_available"], c["plugin_incompatible"]
    delete_supported = False
    plugin_available = False
    plugin_incompatible = False
    try:
        cap_res = requests.get(f"{base}/workflowui/media/capabilities", timeout=3)
        if cap_res.ok and cap_res.headers.get("content-type", "").startswith("application/json"):
            cap_data = cap_res.json()
            workflowui_plugin = cap_data.get("workflowui_plugin") if isinstance(cap_data, dict) else None
            if isinstance(cap_data, dict) and (workflowui_plugin is True or workflowui_plugin == "true"):
                delete_supported = bool(cap_data.get("delete") is True)
                try:
                    ver_res = requests.get(f"{base}/workflowui/version_info", timeout=3)
                    if ver_res.ok and ver_res.headers.get("content-type", "").startswith("application/json"):
                        ver_data = ver_res.json()
                        if isinstance(ver_data, dict):
                            raw_version = ver_data.get("workflowui_plugin_version")
                            if raw_version is not None:
                                installed = str(raw_version).strip() if not isinstance(raw_version, str) else raw_version.strip()
                                if installed:
                                    plugin_available = version_meets_minimum(installed, WORKFLOWUI_PLUGIN_MIN_VERSION)
                                    plugin_incompatible = not plugin_available
                                else:
                                    plugin_incompatible = True
                            else:
                                plugin_incompatible = True
                        else:
                            plugin_incompatible = True
                    else:
                        plugin_incompatible = True
                except Exception:
                    plugin_incompatible = True
    except Exception:
        pass
    _capabilities_cache["url"] = base
    _capabilities_cache["result"] = {
        "delete_supported": delete_supported,
        "plugin_available": plugin_available,
        "plugin_incompatible": plugin_incompatible,
    }
    _capabilities_cache["expires"] = now + COMFYUI_CAPABILITIES_TTL_SEC
    return delete_supported, plugin_available, plugin_incompatible


def get_comfyui_delete_supported(comfy_url: str) -> bool:
    delete_supported, _, _ = get_workflowui_plugin_status(comfy_url)
    return delete_supported


def get_run_remote_storage_bytes(comfy_url: str, images: list[dict]) -> int | None:
    """
    Return total bytes of the run's output files on ComfyUI (remote), using the
    WorkflowUI plugin's list endpoint. Returns None if plugin unavailable or request fails.
    """
    if not images or not isinstance(images, list):
        return None
    _, plugin_available, _ = get_workflowui_plugin_status(comfy_url)
    if not plugin_available:
        return None
    base = normalize_comfy_url(comfy_url).rstrip("/")
    # Group (filename, subfolder) by subfolder; only count outputs not deleted on remote
    by_subfolder: dict[str, set[str]] = {}
    for ent in images:
        if not isinstance(ent, dict) or ent.get("remote_deleted"):
            continue
        fn = (ent.get("filename") or "").strip()
        if not fn:
            continue
        sub = (ent.get("subfolder") or "").strip()
        by_subfolder.setdefault(sub, set()).add(fn)
    total = 0
    try:
        for subfolder, filenames in by_subfolder.items():
            params = {"type": "output", "subfolder": subfolder}
            r = requests.get(f"{base}/workflowui/media/list", params=params, timeout=10)
            if not r.ok or not r.headers.get("content-type", "").startswith("application/json"):
                return None
            data = r.json()
            if not isinstance(data, dict):
                return None
            files = data.get("files")
            if not isinstance(files, list):
                continue
            for f in files:
                if not isinstance(f, dict):
                    continue
                if (f.get("filename") or "").strip() not in filenames:
                    continue
                try:
                    total += int(f.get("size", 0) or 0)
                except (TypeError, ValueError):
                    pass
    except Exception:
        return None
    return total if total >= 0 else None


def get_runs_remote_storage_bytes_deduplicated(comfy_url: str, groups: list[list[dict]]) -> list[int]:
    """
    Fallback when batch endpoint is unavailable: fetch list once per unique (subfolder),
    then compute each group's total from cached file sizes. Avoids one GET per run.
    Tries the list endpoint regardless of plugin version check so we get real sizes when
    the list API works (e.g. plugin has list but fails version_info).
    """
    if not groups:
        return []
    base = normalize_comfy_url(comfy_url).rstrip("/")
    # Build subfolder -> {filename: size} by fetching each subfolder list once
    cache: dict[str, dict[str, int]] = {}  # subfolder -> {filename: size}
    for group in groups:
        if not isinstance(group, list):
            continue
        for ent in group:
            if not isinstance(ent, dict) or ent.get("remote_deleted"):
                continue
            sub = (ent.get("subfolder") or "").strip()
            if sub not in cache:
                cache[sub] = {}
                try:
                    r = requests.get(
                        f"{base}/workflowui/media/list",
                        params={"type": "output", "subfolder": sub},
                        timeout=15,
                    )
                    if r.ok and r.headers.get("content-type", "").startswith("application/json"):
                        data = r.json()
                        if isinstance(data, dict) and isinstance(data.get("files"), list):
                            for f in data["files"]:
                                if isinstance(f, dict):
                                    fn = (f.get("filename") or "").strip()
                                    try:
                                        cache[sub][fn] = int(f.get("size", 0) or 0)
                                    except (TypeError, ValueError):
                                        pass
                except Exception:
                    pass
    # Sum size per group from cache
    result = []
    for group in groups:
        total = 0
        if not isinstance(group, list):
            result.append(0)
            continue
        for ent in group:
            if not isinstance(ent, dict) or ent.get("remote_deleted"):
                continue
            fn = (ent.get("filename") or "").strip()
            sub = (ent.get("subfolder") or "").strip()
            if fn and sub in cache:
                total += cache[sub].get(fn, 0)
        result.append(total)
    return result


def get_runs_remote_storage_bytes_batch(comfy_url: str, groups: list[list[dict]]) -> list[int] | None:
    """
    Return total bytes per group of output files on ComfyUI in one request, using the
    plugin's batch endpoint. Each group is a list of {"filename", "subfolder"} (e.g. one run's images).
    Returns list of sizes (one per group), or None if request fails.
    Always tries the batch request first (no plugin version check) so updated plugins work even if
    version_info is missing or cached as unavailable.
    """
    if not groups:
        return []
    base = normalize_comfy_url(comfy_url).rstrip("/")
    # Build payload: list of groups; each group is list of {subfolder, filename}, exclude remote_deleted
    payload_groups: list[list[dict]] = []
    for group in groups:
        if not isinstance(group, list):
            payload_groups.append([])
            continue
        entries = []
        for ent in group:
            if not isinstance(ent, dict) or ent.get("remote_deleted"):
                continue
            fn = (ent.get("filename") or "").strip()
            if not fn:
                continue
            entries.append({
                "subfolder": (ent.get("subfolder") or "").strip(),
                "filename": fn,
            })
        payload_groups.append(entries)
    try:
        r = requests.post(
            f"{base}/workflowui/media/batch_output_sizes",
            json={"groups": payload_groups},
            timeout=30,
        )
        if not r.ok or not r.headers.get("content-type", "").startswith("application/json"):
            return None
        data = r.json()
        if not isinstance(data, dict):
            return None
        sizes = data.get("sizes")
        if not isinstance(sizes, list) or len(sizes) != len(groups):
            return None
        return [int(x) if isinstance(x, (int, float)) and x >= 0 else 0 for x in sizes]
    except Exception:
        return None


def is_comfyui_unreachable_error(e: Exception) -> bool:
    if isinstance(e, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(e, requests.RequestException):
        msg = str(e).lower()
        if "connection" in msg or "timed out" in msg or "refused" in msg:
            return True
    return False


def fetch_comfyui_version_info(comfy_url: str) -> dict[str, Any]:
    base = normalize_comfy_url(comfy_url).rstrip("/")
    out: dict[str, Any] = {"fetched_at_ms": int(time.time() * 1000), "comfyui_base_url": base}
    try:
        r = requests.get(f"{base}/system_stats", timeout=10)
        r.raise_for_status()
        out["system_stats"] = r.json()
    except Exception as e:
        out["system_stats_error"] = str(e)
    try:
        r = requests.get(f"{base}/features", timeout=5)
        r.raise_for_status()
        out["features"] = r.json()
    except Exception as e:
        out["features_error"] = str(e)
    try:
        r = requests.get(f"{base}/object_info", timeout=15)
        r.raise_for_status()
        obj = r.json()
        out["object_info_node_classes"] = sorted(obj.keys()) if isinstance(obj, dict) else []
    except Exception as e:
        out["object_info_error"] = str(e)
    try:
        r = requests.get(f"{base}/workflowui/version_info", timeout=10)
        r.raise_for_status()
        out["workflowui_plugin_version_info"] = r.json()
    except Exception as e:
        out["workflowui_plugin_version_info_error"] = str(e)
    return out


def fetch_comfyui_status_system_stats(comfy_url: str) -> dict[str, Any] | None:
    base = normalize_comfy_url(comfy_url).rstrip("/")
    try:
        r = requests.get(f"{base}/system_stats", timeout=5)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    out: dict[str, Any] = {}
    devices = data.get("devices") if isinstance(data.get("devices"), list) else []
    vram_used_gb = vram_total_gb = gpu_percent = None
    for d in devices:
        if not isinstance(d, dict):
            continue
        total = d.get("vram_total") or d.get("total_memory")
        free = d.get("vram_free") or d.get("free_memory")
        used = d.get("vram_used") or (total - free if isinstance(total, (int, float)) and isinstance(free, (int, float)) else None)
        if total is not None or used is not None:
            if vram_total_gb is None and total is not None:
                vram_total_gb = (total / (1024**3)) if isinstance(total, (int, float)) else None
            if vram_used_gb is None and used is not None:
                vram_used_gb = (used / (1024**3)) if isinstance(used, (int, float)) else None
            elif vram_used_gb is None and total is not None and free is not None:
                try:
                    t, f = float(total), float(free)
                    vram_used_gb = (t - f) / (1024**3)
                except (TypeError, ValueError):
                    pass
        if gpu_percent is None:
            u = d.get("utilization") or d.get("gpu_utilization") or d.get("gpu_percent")
            if isinstance(u, (int, float)) and 0 <= float(u) <= 100:
                gpu_percent = float(u)
        if vram_used_gb is not None and vram_total_gb is not None and gpu_percent is not None:
            break
    if vram_used_gb is not None:
        out["vram_used_gb"] = round(vram_used_gb, 2)
    if vram_total_gb is not None:
        out["vram_total_gb"] = round(vram_total_gb, 2)
    if gpu_percent is not None:
        out["gpu_percent"] = round(gpu_percent, 1)
    elif vram_used_gb is not None and vram_total_gb is not None and vram_total_gb > 0:
        out["gpu_percent"] = round(100.0 * vram_used_gb / vram_total_gb, 1)
    sys_info = data.get("system", data) if isinstance(data.get("system"), dict) else data
    if isinstance(sys_info, dict):
        ram = sys_info.get("ram") or sys_info.get("ram_used")
        if isinstance(ram, (int, float)):
            out["ram_used_gb"] = round(ram / (1024**3), 2)
        cpu = sys_info.get("cpu_percent") or sys_info.get("cpu_utilization")
        if isinstance(cpu, (int, float)):
            out["cpu_percent"] = round(float(cpu), 1)
    if isinstance(data, dict) and "cpu_percent" not in out:
        cpu = data.get("cpu_percent") or data.get("cpu_utilization")
        if isinstance(cpu, (int, float)):
            out["cpu_percent"] = round(float(cpu), 1)
    if "cpu_percent" not in out:
        try:
            import psutil
            out["cpu_percent"] = round(psutil.cpu_percent(interval=None) or 0, 1)
        except Exception:
            pass
    return out if out else None


def get_cached_status(comfy_url: str) -> tuple[dict[str, Any] | None, float]:
    return _status_cache.get("result"), _status_cache.get("expires", 0.0)


def set_cached_status(stats: dict[str, Any] | None, ttl_sec: float = COMFYUI_STATUS_TTL_SEC) -> None:
    import time as _t
    _status_cache["result"] = stats
    _status_cache["expires"] = _t.time() + ttl_sec
