"""Tests for ComfyUI PNG prompt/workflow chunk detection."""

import struct
import zlib

from services.comfyui_embedded_detect import (
    file_has_embedded_comfyui_metadata,
    png_has_comfyui_prompt_or_workflow,
)
from services.png_metadata import PNG_SIGNATURE


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return length + chunk_type + data + struct.pack(">I", crc)


def test_non_png_comfyui_not_applicable():
    assert file_has_embedded_comfyui_metadata(b"not a png") == (False, False)


def test_png_with_prompt_tex_detected():
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    tex = b"prompt\x00" + b'{"1":2}'
    png = PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"tEXt", tex) + _chunk(b"IEND", b"")
    assert png_has_comfyui_prompt_or_workflow(png) is True


def test_png_without_prompt_workflow_false():
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    tex = b"WorkflowUI\x00" + b'{"app":"x"}'
    png = PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"tEXt", tex) + _chunk(b"IEND", b"")
    assert png_has_comfyui_prompt_or_workflow(png) is False


def test_mp4_moov_with_comfyui_json_detected():
    from services.comfyui_embedded_detect import file_has_embedded_comfyui_metadata, mp4_moov_has_comfyui_metadata

    ftyp = struct.pack(">I4s4sI4s", 20, b"ftyp", b"isom", 1, b"isom")
    payload = b'{"prompt": {"1": {"class_type": "x"}}, "workflow": {"nodes": []}}'
    child = struct.pack(">I4s", 8 + len(payload), b"free") + payload
    moov_size = 8 + len(child)
    moov = struct.pack(">I4s", moov_size, b"moov") + child
    mp4 = ftyp + moov
    assert mp4_moov_has_comfyui_metadata(mp4) is True
    has, applicable = file_has_embedded_comfyui_metadata(mp4)
    assert applicable is True
    assert has is True
