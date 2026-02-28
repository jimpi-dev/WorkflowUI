import pytest
from services.manifest_parser import (
    parse_manifest,
    check_engine_compat,
    validate_manifest_for_install,
)


def test_parse_manifest_required_fields():
    p = parse_manifest({"manifest_version": "1.0", "engine_compat": "^1.2.0"})
    assert p.manifest_version == "1.0"
    assert p.engine_compat == "^1.2.0"
    assert p.app_version is None
    assert p.workflow_hash is None


def test_parse_manifest_optional_fields():
    p = parse_manifest({
        "manifest_version": "1.0",
        "engine_compat": "^1.0.0",
        "app_version": "2.1.0",
        "workflow_hash": "abc123",
    })
    assert p.app_version == "2.1.0"
    assert p.workflow_hash == "abc123"


def test_parse_manifest_unknown_fields_ignored():
    p = parse_manifest({
        "manifest_version": "1.0",
        "engine_compat": "^1.0.0",
        "unknown_key": "ignored",
    })
    assert p.manifest_version == "1.0"
    assert "unknown_key" in (p.raw or {})


def test_parse_manifest_not_dict():
    p = parse_manifest(None)
    assert p.manifest_version is None
    assert p.engine_compat is None
    p2 = parse_manifest("string")
    assert p2.manifest_version is None


def test_check_engine_compat_satisfied():
    p = parse_manifest({"engine_compat": "^1.2.0"})
    ok, err = check_engine_compat(p, "1.4.0")
    assert ok is True
    assert err is None


def test_check_engine_compat_major_mismatch():
    p = parse_manifest({"engine_compat": "^1.2.0"})
    ok, err = check_engine_compat(p, "2.0.0")
    assert ok is False
    assert "2.0.0" in (err or "")


def test_check_engine_compat_no_engine_compat():
    p = parse_manifest({"manifest_version": "1.0"})
    ok, err = check_engine_compat(p, "1.4.0")
    assert ok is True
    assert err is None


def test_validate_manifest_for_install_requires_manifest_version():
    p = parse_manifest({"engine_compat": "^1.0.0"})
    valid, err = validate_manifest_for_install(p, "1.4.0")
    assert valid is False
    assert "manifest_version" in (err or "")


def test_validate_manifest_for_install_requires_engine_compat():
    p = parse_manifest({"manifest_version": "1.0"})
    valid, err = validate_manifest_for_install(p, "1.4.0")
    assert valid is False
    assert "engine_compat" in (err or "")


def test_validate_manifest_for_install_ok():
    p = parse_manifest({"manifest_version": "1.0", "engine_compat": "^1.2.0"})
    valid, err = validate_manifest_for_install(p, "1.4.0")
    assert valid is True
    assert err is None


def test_validate_manifest_for_install_incompatible():
    p = parse_manifest({"manifest_version": "1.0", "engine_compat": "^1.2.0"})
    valid, err = validate_manifest_for_install(p, "2.0.0")
    assert valid is False
    assert err is not None
