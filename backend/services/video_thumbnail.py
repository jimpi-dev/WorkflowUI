from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import requests

from config import get_media_storage_config

logger = logging.getLogger(__name__)

_THUMB_SEMAPHORE = threading.Semaphore(
    max(1, int(os.environ.get("WORKFLOWUI_VIDEO_THUMB_MAX_CONCURRENT", "2")))
)
_THUMB_LOCKS_GUARD = threading.Lock()
_THUMB_LOCKS: dict[str, threading.Lock] = {}


def _get_thumb_lock(key: str) -> threading.Lock:
    with _THUMB_LOCKS_GUARD:
        lock = _THUMB_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _THUMB_LOCKS[key] = lock
        return lock


def _format_run_date_ms(ms: int) -> str:
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(ms / 1000))
    except Exception:
        return time.strftime("%Y-%m-%d", time.gmtime())


def _resolve_run_dir_for_cache(run_entity: Any) -> Path | None:
    cfg = get_media_storage_config()
    root = (cfg.root_path or "").strip()
    if not root:
        return None
    run_date = _format_run_date_ms(getattr(run_entity, "created_at", 0) or 0)
    group_or_run_id = getattr(run_entity, "run_group_id", None) or getattr(run_entity, "id", None)
    project_id = getattr(run_entity, "project_id", None)
    if not project_id or not group_or_run_id:
        return None
    return Path(root) / str(project_id) / run_date / str(group_or_run_id)


def thumb_cache_path(
    *,
    run_entity: Any,
    output_index: int,
    input_video_path: Path | None,
) -> Path | None:
    if input_video_path is not None:
        # Example: `output_1.mp4` -> `output_1.thumb.webp`
        return input_video_path.with_suffix(".thumb.webp")
    run_dir = _resolve_run_dir_for_cache(run_entity)
    if run_dir is None:
        return None
    # output_index is 0-based; keep cache name stable with UI ordering.
    return run_dir / f"thumb_{output_index + 1}.webp"


def _ffmpeg_executable() -> str | None:
    return shutil.which("ffmpeg")


def _try_comfy_view_preview_bytes(
    *,
    comfy_url: str,
    filename: str,
    subfolder: str,
    view_type: str,
    timeout: int = 120,
) -> bytes | None:
    """Ask ComfyUI for a preview image (no local ffmpeg). Comfy may still use ffmpeg on its host."""
    url = comfy_url.rstrip("/") + "/view"
    base_params: dict[str, str] = {
        "filename": filename,
        "subfolder": subfolder or "",
        "type": view_type,
    }
    for preview_val in ("webp", "true", "1"):
        params = {**base_params, "preview": preview_val}
        try:
            res = requests.get(url, params=params, timeout=timeout)
            if res.ok and res.content and len(res.content) > 32:
                return res.content
        except requests.RequestException as e:
            logger.warning("ComfyUI /view preview request failed (preview=%s): %s", preview_val, e)
            break
    logger.warning("ComfyUI /view preview failed for filename=%s", filename)
    return None


def _extract_first_frame_to_webp(
    *,
    input_path: Path,
    output_path: Path,
    width: int = 480,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Extract first decodable frame at/near t=0; scale down for lightweight previews.
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-ss",
        "0",
        "-i",
        str(input_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={int(width)}:-2",
        "-an",
        "-c:v",
        "libwebp",
        "-q:v",
        "75",
        str(output_path),
    ]

    ffmpeg_exe = _ffmpeg_executable()
    if not ffmpeg_exe:
        raise FileNotFoundError("ffmpeg")
    cmd[0] = ffmpeg_exe
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg thumbnail extraction failed: {proc.stderr.strip() or proc.stdout.strip()}")


def _download_comfyui_video_to_temp(
    *,
    comfy_url: str,
    filename: str,
    subfolder: str,
    view_type: str,
    timeout: int = 120,
) -> Path:
    # Use a temp file so we don't load large videos into memory.
    fd, tmp_path_str = tempfile.mkstemp(prefix="workflowui_video_thumb_", suffix=".input")
    os.close(fd)
    tmp_path = Path(tmp_path_str)

    url = comfy_url.rstrip("/") + "/view"
    params = {"filename": filename, "subfolder": subfolder, "type": view_type}
    try:
        with requests.get(url, params=params, stream=True, timeout=timeout) as res:
            res.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
        return tmp_path
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def get_or_create_video_thumbnail_webp_bytes(
    *,
    run_entity: Any,
    output_index: int,
    filename: str,
    subfolder: str,
    comfy_url: str | None,
    view_type: str,
    input_video_path: Path | None,
    width: int = 480,
) -> bytes:
    thumb_path = thumb_cache_path(
        run_entity=run_entity,
        output_index=output_index,
        input_video_path=input_video_path,
    )
    if thumb_path is None:
        raise RuntimeError("Thumbnail cache path not available (missing media storage root path)")

    lock = _get_thumb_lock(str(thumb_path))
    with lock:
        if thumb_path.is_file() and thumb_path.stat().st_size > 0:
            return thumb_path.read_bytes()

        # No ffmpeg in container: ComfyUI can still serve a raster preview from /view.
        if not _ffmpeg_executable() and comfy_url:
            preview = _try_comfy_view_preview_bytes(
                comfy_url=comfy_url,
                filename=filename,
                subfolder=subfolder,
                view_type=view_type,
            )
            if preview:
                thumb_path.parent.mkdir(parents=True, exist_ok=True)
                thumb_path.write_bytes(preview)
                return preview
            logger.warning(
                "ffmpeg not installed and ComfyUI did not return a preview; install ffmpeg in the WorkflowUI image "
                "or ensure ComfyUI can serve /view?preview=webp for this output."
            )

        if not _ffmpeg_executable():
            raise RuntimeError(
                "Video thumbnails require ffmpeg in PATH, or a working ComfyUI /view?preview=webp for this file."
            )

        with _THUMB_SEMAPHORE:
            if input_video_path is not None and input_video_path.is_file():
                try:
                    _extract_first_frame_to_webp(input_path=input_video_path, output_path=thumb_path, width=width)
                except FileNotFoundError:
                    if comfy_url:
                        preview = _try_comfy_view_preview_bytes(
                            comfy_url=comfy_url,
                            filename=filename,
                            subfolder=subfolder,
                            view_type=view_type,
                        )
                        if preview:
                            thumb_path.parent.mkdir(parents=True, exist_ok=True)
                            thumb_path.write_bytes(preview)
                            return preview
                    raise
                except RuntimeError:
                    if comfy_url:
                        preview = _try_comfy_view_preview_bytes(
                            comfy_url=comfy_url,
                            filename=filename,
                            subfolder=subfolder,
                            view_type=view_type,
                        )
                        if preview:
                            thumb_path.parent.mkdir(parents=True, exist_ok=True)
                            thumb_path.write_bytes(preview)
                            return preview
                    raise
            else:
                if not comfy_url:
                    raise RuntimeError("Cannot generate remote video thumbnail: missing comfy_url")
                tmp_path: Path | None = None
                try:
                    tmp_path = _download_comfyui_video_to_temp(
                        comfy_url=comfy_url,
                        filename=filename,
                        subfolder=subfolder,
                        view_type=view_type,
                    )
                    _extract_first_frame_to_webp(input_path=tmp_path, output_path=thumb_path, width=width)
                except FileNotFoundError:
                    preview = _try_comfy_view_preview_bytes(
                        comfy_url=comfy_url,
                        filename=filename,
                        subfolder=subfolder,
                        view_type=view_type,
                    )
                    if preview:
                        thumb_path.parent.mkdir(parents=True, exist_ok=True)
                        thumb_path.write_bytes(preview)
                        return preview
                    raise
                except RuntimeError:
                    preview = _try_comfy_view_preview_bytes(
                        comfy_url=comfy_url,
                        filename=filename,
                        subfolder=subfolder,
                        view_type=view_type,
                    )
                    if preview:
                        thumb_path.parent.mkdir(parents=True, exist_ok=True)
                        thumb_path.write_bytes(preview)
                        return preview
                    raise
                finally:
                    if tmp_path is not None:
                        tmp_path.unlink(missing_ok=True)

        if not thumb_path.is_file() or thumb_path.stat().st_size <= 0:
            raise RuntimeError("Video thumbnail extraction produced an empty file")

        return thumb_path.read_bytes()

