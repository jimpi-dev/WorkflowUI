from __future__ import annotations

from io import BytesIO

from mutagen.id3 import ID3, TXXX
from mutagen.mp3 import MP3

WORKFLOWUI_TXXX_DESC = "WorkflowUI"


def read_workflowui_metadata(mp3_bytes: bytes) -> str | None:
    if not mp3_bytes or len(mp3_bytes) < 10:
        return None
    try:
        id3 = ID3(fileobj=BytesIO(mp3_bytes))
    except Exception:
        return None
    for frame in id3.getall("TXXX"):
        if getattr(frame, "desc", "") == WORKFLOWUI_TXXX_DESC and frame.text:
            value = frame.text[0].strip() if frame.text else ""
            return value if value else None
    return None


def inject_workflowui_metadata(mp3_bytes: bytes, json_string: str) -> bytes:
    if not mp3_bytes or len(mp3_bytes) < 10:
        return mp3_bytes
    try:
        buf = BytesIO(mp3_bytes)
        audio = MP3(fileobj=buf)
    except Exception:
        return mp3_bytes
    if audio.tags is None:
        audio.add_tags()
    for frame in list(audio.tags.getall("TXXX")):
        if getattr(frame, "desc", "") == WORKFLOWUI_TXXX_DESC:
            audio.tags.remove(frame)
    audio.tags.add(TXXX(encoding=3, desc=WORKFLOWUI_TXXX_DESC, text=[json_string]))
    buf.seek(0)
    audio.save(fileobj=buf)
    return buf.getvalue()
