"""Detect WorkflowUI embedded JSON in output file bytes (PNG, MP3, MP4)."""

from __future__ import annotations

from services.mp3_metadata import read_workflowui_metadata as read_workflowui_metadata_mp3
from services.mp4_metadata import read_workflowui_metadata as read_workflowui_metadata_mp4
from services.png_metadata import read_workflowui_chunk


def file_has_embedded_workflowui_metadata(content: bytes, filename: str, type_param: str) -> bool:
    """
    Return True if the file bytes contain WorkflowUI embedded metadata
    (PNG tEXt chunk, MP3 TXXX, or MP4 WfUI box).
    """
    fn = (filename or "").lower()
    tp = (type_param or "output").strip().lower()
    if tp == "video" or any(fn.endswith(ext) for ext in (".mp4", ".webm", ".mkv", ".mov")):
        raw = read_workflowui_metadata_mp4(content)
        return bool(raw and raw.strip())
    if tp == "audio" or fn.endswith((".mp3", ".mpeg")):
        raw = read_workflowui_metadata_mp3(content)
        return bool(raw and raw.strip())
    raw = read_workflowui_chunk(content)
    return bool(raw and raw.strip())
