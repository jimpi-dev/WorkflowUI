from __future__ import annotations

import struct
import zlib
from typing import Any

WORKFLOWUI_CHUNK_KEYWORD = "WorkflowUI"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk_type(b: bytes) -> str:
    return b.decode("ascii", errors="replace") if len(b) >= 4 else ""


def _crc(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def read_workflowui_chunk(png_bytes: bytes) -> str | None:
    if not png_bytes.startswith(PNG_SIGNATURE):
        return None
    pos = 8
    while pos + 12 <= len(png_bytes):
        length = struct.unpack(">I", png_bytes[pos : pos + 4])[0]
        chunk_type = png_bytes[pos + 4 : pos + 8]
        if pos + 12 + length > len(png_bytes):
            break
        data = png_bytes[pos + 8 : pos + 8 + length]
        if _chunk_type(chunk_type) == "tEXt":
            nul = data.find(b"\x00")
            if nul >= 0:
                keyword = data[:nul].decode("latin-1", errors="replace")
                if keyword == WORKFLOWUI_CHUNK_KEYWORD:
                    value = data[nul + 1 :].decode("utf-8", errors="replace")
                    return value if value.strip() else None
        pos += 12 + length
    return None


def inject_workflowui_chunk(png_bytes: bytes, json_string: str) -> bytes:
    if not png_bytes.startswith(PNG_SIGNATURE):
        return png_bytes
    pos = 8
    chunks_before_iend: list[tuple[bytes, bytes]] = []
    iend_chunk = None
    while pos + 12 <= len(png_bytes):
        length = struct.unpack(">I", png_bytes[pos : pos + 4])[0]
        chunk_type = png_bytes[pos + 4 : pos + 8]
        if pos + 12 + length > len(png_bytes):
            break
        chunk_data_with_type = png_bytes[pos + 4 : pos + 8 + length]
        crc = struct.unpack(">I", png_bytes[pos + 8 + length : pos + 12 + length])[0]
        full = png_bytes[pos : pos + 12 + length]
        if _chunk_type(chunk_type) == "IEND":
            iend_chunk = full
            break
        chunks_before_iend.append((chunk_type, full))
        pos += 12 + length
    if iend_chunk is None:
        return png_bytes
    value_bytes = json_string.encode("latin-1", errors="replace")
    keyword_bytes = WORKFLOWUI_CHUNK_KEYWORD.encode("ascii")
    text_data = keyword_bytes + b"\x00" + value_bytes
    length = len(text_data)
    chunk_with_type = b"tEXt" + text_data
    crc = _crc(chunk_with_type)
    new_chunk = struct.pack(">I", length) + chunk_with_type + struct.pack(">I", crc)
    return PNG_SIGNATURE + b"".join(c[1] for c in chunks_before_iend) + new_chunk + iend_chunk
