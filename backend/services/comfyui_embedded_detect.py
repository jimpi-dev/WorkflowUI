"""Detect ComfyUI-style embedded metadata (PNG text chunks; MP4 moov metadata from VHS/ffmpeg)."""

from __future__ import annotations

import struct
import zlib

from services.mp4_metadata import _find_moov_range
from services.png_metadata import PNG_SIGNATURE

# ComfyUI Save Image / standard PNG embedding uses these tEXt / zTXt / iTXt keywords.
COMFYUI_PNG_KEYWORDS = frozenset({"prompt", "workflow"})


def _tchunk_keyword_value(data: bytes, chunk_type: bytes) -> list[tuple[str, str]]:
    """Parse tEXt, zTXt, or iTXt chunk data into (keyword, value) pairs."""
    out: list[tuple[str, str]] = []
    if chunk_type == b"tEXt":
        nul = data.find(b"\x00")
        if nul < 0:
            return out
        keyword = data[:nul].decode("latin-1", errors="replace")
        value = data[nul + 1 :].decode("latin-1", errors="replace").strip()
        out.append((keyword, value))
        return out
    if chunk_type == b"zTXt":
        nul = data.find(b"\x00")
        if nul < 0 or nul + 2 > len(data):
            return out
        keyword = data[:nul].decode("latin-1", errors="replace")
        comp_method = data[nul + 1]
        compressed = data[nul + 2 :]
        if comp_method != 0:
            return out
        try:
            raw = zlib.decompress(compressed)
            value = raw.decode("utf-8", errors="replace").strip()
        except Exception:
            return out
        out.append((keyword, value))
        return out
    if chunk_type == b"iTXt":
        nul = data.find(b"\x00")
        if nul < 0 or nul + 3 > len(data):
            return out
        keyword = data[:nul].decode("latin-1", errors="replace")
        pos = nul + 1
        comp_flag = data[pos]
        pos += 1
        comp_method = data[pos]
        pos += 1
        j = data.find(b"\x00", pos)
        if j < 0:
            return out
        pos = j + 1
        k = data.find(b"\x00", pos)
        if k < 0:
            return out
        pos = k + 1
        text_bytes = data[pos:]
        if comp_flag == 0:
            value = text_bytes.decode("utf-8", errors="replace").strip()
        else:
            if comp_method != 0:
                return out
            try:
                value = zlib.decompress(text_bytes).decode("utf-8", errors="replace").strip()
            except Exception:
                return out
        out.append((keyword, value))
        return out
    return out


def mp4_moov_has_comfyui_metadata(mp4_bytes: bytes) -> bool:
    """
    True if the moov box embeds ComfyUI-style JSON (VideoHelperSuite save_metadata, etc.).

    Scans the moov subtree only (metadata lives there, not in mdat samples).
    Typical embeds include top-level \"prompt\" and \"workflow\" keys; some MP4s only
    embed \"prompt\" plus graph keys like \"class_type\" / \"nodes\".
    """
    moov = _find_moov_range(mp4_bytes)
    if not moov:
        return False
    off, size = moov
    moov_data = mp4_bytes[off : off + size]
    if b'"prompt"' not in moov_data:
        return False
    if b'"workflow"' in moov_data:
        return True
    if b'"class_type"' in moov_data or b'"nodes"' in moov_data:
        return True
    return False


def png_has_comfyui_prompt_or_workflow(png_bytes: bytes) -> bool:
    """True if PNG has non-empty ComfyUI-style prompt or workflow text chunk."""
    if not png_bytes.startswith(PNG_SIGNATURE):
        return False
    pos = 8
    while pos + 12 <= len(png_bytes):
        length = struct.unpack(">I", png_bytes[pos : pos + 4])[0]
        chunk_type = png_bytes[pos + 4 : pos + 8]
        if pos + 12 + length > len(png_bytes):
            break
        data = png_bytes[pos + 8 : pos + 8 + length]
        if chunk_type in (b"tEXt", b"zTXt", b"iTXt"):
            for keyword, value in _tchunk_keyword_value(data, chunk_type):
                if keyword in COMFYUI_PNG_KEYWORDS and value:
                    return True
        pos += 12 + length
    return False


def file_has_embedded_comfyui_metadata(content: bytes) -> tuple[bool, bool]:
    """
    Return (has_comfyui_meta, check_applicable).

    - PNG: ComfyUI Save Image tEXt/zTXt/iTXt keywords prompt / workflow.
    - MP4 (and similar ISO BMFF with moov): embedded JSON in moov (e.g. VideoHelperSuite).
    """
    if content.startswith(PNG_SIGNATURE):
        return (png_has_comfyui_prompt_or_workflow(content), True)
    if _find_moov_range(content) is not None:
        return (mp4_moov_has_comfyui_metadata(content), True)
    return (False, False)
