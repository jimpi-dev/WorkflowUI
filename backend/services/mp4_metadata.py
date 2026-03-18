from __future__ import annotations

import struct
from typing import Optional


WORKFLOWUI_BOX_TYPE = b"WfUI"


def _read_u32(buf: bytes, offset: int) -> Optional[int]:
    if offset + 4 > len(buf):
        return None
    return struct.unpack(">I", buf[offset : offset + 4])[0]


def _iter_boxes(buf: bytes, start: int, end: int):
    """Yield (offset, size, box_type) for each top-level box between start and end."""
    pos = start
    while pos + 8 <= end and pos + 8 <= len(buf):
        size = _read_u32(buf, pos)
        if size is None or size < 8:
            break
        box_type = buf[pos + 4 : pos + 8]
        yield pos, size, box_type
        # Prevent infinite loops on malformed sizes.
        if size == 0:
            break
        pos += size


def _find_moov_range(buf: bytes) -> tuple[int, int] | None:
    """Return (offset, size) for the moov box, or None."""
    for off, size, btype in _iter_boxes(buf, 0, len(buf)):
        if btype == b"moov":
            if off + size <= len(buf):
                return off, size
            return None
    return None


def read_workflowui_metadata(mp4_bytes: bytes) -> str | None:
    """
    Read WorkflowUI metadata JSON from an MP4 byte buffer.

    The payload is stored in a dedicated 'WfUI' box under 'moov'.
    """
    if not mp4_bytes or len(mp4_bytes) < 16:
        return None
    moov = _find_moov_range(mp4_bytes)
    if not moov:
        return None
    moov_off, moov_size = moov
    moov_end = moov_off + moov_size
    # Skip the moov header (size + type).
    inner_start = moov_off + 8
    for off, size, btype in _iter_boxes(mp4_bytes, inner_start, moov_end):
        if btype != WORKFLOWUI_BOX_TYPE:
            continue
        data_start = off + 8
        data_end = off + size
        if data_end > len(mp4_bytes) or data_start > data_end:
            continue
        try:
            raw = mp4_bytes[data_start:data_end]
            text = raw.decode("utf-8", errors="replace").strip()
            return text or None
        except Exception:
            continue
    return None


def inject_workflowui_metadata(mp4_bytes: bytes, json_string: str) -> bytes:
    """
    Inject or replace WorkflowUI metadata JSON into an MP4 byte buffer.

    This function is conservative: on any structural error it returns the
    original bytes unchanged rather than risk corrupting the file.
    """
    if not mp4_bytes or len(mp4_bytes) < 16 or not json_string:
        return mp4_bytes
    try:
        moov = _find_moov_range(mp4_bytes)
        if not moov:
            return mp4_bytes
        moov_off, moov_size = moov
        moov_end = moov_off + moov_size
        if moov_end > len(mp4_bytes):
            return mp4_bytes

        # Split the file into three parts: before moov, moov box, after moov.
        before = mp4_bytes[:moov_off]
        moov_box = bytearray(mp4_bytes[moov_off:moov_end])
        after = mp4_bytes[moov_end:]

        # Remove any existing WorkflowUI box(es) within moov.
        inner_start = 8  # skip moov header
        inner_end = len(moov_box)
        new_children = bytearray()
        pos = inner_start
        while pos + 8 <= inner_end:
            size = _read_u32(moov_box, pos)
            if size is None or size < 8 or pos + size > inner_end:
                break
            btype = moov_box[pos + 4 : pos + 8]
            if btype != WORKFLOWUI_BOX_TYPE:
                new_children.extend(moov_box[pos : pos + size])
            pos += size

        # Build new WorkflowUI box with UTF-8 JSON payload.
        payload = json_string.encode("utf-8", errors="replace")
        box_size = 8 + len(payload)
        if box_size > 0xFFFFFFFF:
            # Too large; don't modify the file.
            return mp4_bytes
        wf_box = struct.pack(">I4s", box_size, WORKFLOWUI_BOX_TYPE) + payload

        # Rebuild moov with updated children and size.
        new_children.extend(wf_box)
        total_size = 8 + len(new_children)
        if total_size > 0xFFFFFFFF:
            return mp4_bytes
        new_moov = bytearray()
        new_moov.extend(struct.pack(">I4s", total_size, b"moov"))
        new_moov.extend(new_children)

        return bytes(before + new_moov + after)
    except Exception:
        return mp4_bytes

