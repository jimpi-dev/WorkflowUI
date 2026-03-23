"""Tests for MP4 WorkflowUI metadata inject/read."""
from __future__ import annotations

import struct

import pytest

from services.mp4_metadata import (
    inject_workflowui_metadata,
    read_workflowui_metadata,
)


def _minimal_mp4_bytes() -> bytes:
    """Build minimal valid MP4: ftyp + moov with one dummy child box."""
    ftyp = struct.pack(">I4s4sI4s", 20, b"ftyp", b"isom", 1, b"isom")
    # moov: header 8 + one child (12 bytes: size 12, type "test", 4 bytes payload)
    child = struct.pack(">I4s", 12, b"test") + b"\x00\x00\x00\x00"
    moov_size = 8 + len(child)
    moov = struct.pack(">I4s", moov_size, b"moov") + child
    return ftyp + moov


def test_read_workflowui_metadata_returns_none_when_no_metadata():
    mp4 = _minimal_mp4_bytes()
    assert read_workflowui_metadata(mp4) is None


def test_inject_and_read_round_trip():
    mp4 = _minimal_mp4_bytes()
    payload = '{"v":1,"run_id":"abc","workflow":{"name":"Test"}}'
    injected = inject_workflowui_metadata(mp4, payload)
    assert injected != mp4
    assert len(injected) > len(mp4)
    out = read_workflowui_metadata(injected)
    assert out == payload


def test_inject_twice_overwrites():
    mp4 = _minimal_mp4_bytes()
    first = inject_workflowui_metadata(mp4, '{"a":1}')
    second = inject_workflowui_metadata(first, '{"b":2}')
    assert read_workflowui_metadata(second) == '{"b":2}'


def test_read_returns_none_for_empty_or_tiny_input():
    assert read_workflowui_metadata(b"") is None
    assert read_workflowui_metadata(b"x" * 10) is None


def test_read_returns_none_for_non_mp4():
    # No ftyp/moov
    assert read_workflowui_metadata(b"\x00\x00\x00\x08free\x00\x00\x00\x00") is None


def test_inject_returns_unchanged_for_empty_or_invalid():
    mp4 = _minimal_mp4_bytes()
    assert inject_workflowui_metadata(mp4, "") is mp4
    assert inject_workflowui_metadata(b"", '{"x":1}') == b""
    assert inject_workflowui_metadata(b"tooshort", '{"x":1}') == b"tooshort"
