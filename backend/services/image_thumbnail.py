from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from services.video_thumbnail import _THUMB_SEMAPHORE, _get_thumb_lock, thumb_cache_path

logger = logging.getLogger(__name__)

_DEFAULT_WIDTH = 480


def _ffmpeg_executable() -> str | None:
    return shutil.which("ffmpeg")


def _resize_image_to_webp(*, input_path: Path, output_path: Path, width: int = _DEFAULT_WIDTH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-vf",
        f"scale='min({width},iw)':-1",
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
        raise RuntimeError(
            f"ffmpeg image thumbnail failed: {(proc.stderr or proc.stdout or '').strip() or proc.returncode}"
        )


def get_or_create_image_thumbnail_webp_bytes(
    *,
    run_entity: Any,
    output_index: int,
    input_image_path: Path,
    width: int = _DEFAULT_WIDTH,
) -> bytes:
    """Return cached WebP thumbnail bytes for a local raster image output."""
    if not input_image_path.is_file():
        raise FileNotFoundError(str(input_image_path))

    thumb_path = thumb_cache_path(
        run_entity=run_entity,
        output_index=output_index,
        input_video_path=input_image_path,
    )
    if thumb_path is None:
        raise RuntimeError("Thumbnail cache path not available (missing media storage root path)")

    lock = _get_thumb_lock(str(thumb_path))
    with lock:
        if thumb_path.is_file() and thumb_path.stat().st_size > 0:
            return thumb_path.read_bytes()

        if not _ffmpeg_executable():
            raise RuntimeError(
                "Image thumbnails require ffmpeg in PATH to resize local files, "
                "or fetch from ComfyUI with preview=webp when not stored locally."
            )

        with _THUMB_SEMAPHORE:
            if thumb_path.is_file() and thumb_path.stat().st_size > 0:
                return thumb_path.read_bytes()
            _resize_image_to_webp(input_path=input_image_path, output_path=thumb_path, width=width)
            if not thumb_path.is_file() or thumb_path.stat().st_size == 0:
                raise RuntimeError("Image thumbnail extraction produced an empty file")
            return thumb_path.read_bytes()
