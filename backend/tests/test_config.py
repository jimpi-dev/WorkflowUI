import os

import pytest

import config


@pytest.fixture(autouse=True)
def reset_media_storage_config():
    config._MEDIA_STORAGE_CONFIG = None
    yield
    config._MEDIA_STORAGE_CONFIG = None


def test_parse_bool_true_values():
    for v in ("1", "true", "True", "YES", "on", "ON"):
        assert config._parse_bool(v) is True
        assert config._parse_bool(v, default=False) is True


def test_parse_bool_false_values():
    for v in ("0", "false", "FALSE", "no", "off"):
        assert config._parse_bool(v) is False
        assert config._parse_bool(v, default=False) is False
        assert config._parse_bool(v, default=True) is False


def test_parse_bool_none_returns_default():
    assert config._parse_bool(None) is False
    assert config._parse_bool(None, default=True) is True
    assert config._parse_bool(None, default=False) is False


def test_parse_bool_unknown_returns_default():
    assert config._parse_bool("unknown") is False
    assert config._parse_bool("unknown", default=True) is True
    assert config._parse_bool("  ") is False


def test_load_media_storage_config_defaults(monkeypatch):
    monkeypatch.delenv("MEDIA_STORAGE_ENABLED", raising=False)
    monkeypatch.delenv("MEDIA_STORAGE_ROOT_PATH", raising=False)
    monkeypatch.delenv("MEDIA_STORAGE_DELETE_REMOTE", raising=False)
    c = config.load_media_storage_config()
    assert c.enabled is False
    assert c.root_path == "media_storage"
    assert c.delete_remote_after_save is False


def test_load_media_storage_config_from_env(monkeypatch):
    monkeypatch.setenv("MEDIA_STORAGE_ENABLED", "true")
    monkeypatch.setenv("MEDIA_STORAGE_ROOT_PATH", " /custom/path ")
    monkeypatch.setenv("MEDIA_STORAGE_DELETE_REMOTE", "1")
    c = config.load_media_storage_config()
    assert c.enabled is True
    assert c.root_path == "/custom/path"
    assert c.delete_remote_after_save is True


def test_get_media_storage_config_caches(monkeypatch):
    monkeypatch.setenv("MEDIA_STORAGE_ROOT_PATH", "first")
    c1 = config.get_media_storage_config()
    monkeypatch.setenv("MEDIA_STORAGE_ROOT_PATH", "second")
    c2 = config.get_media_storage_config()
    assert c1.root_path == "first"
    assert c2.root_path == "first"


def test_update_media_storage_config(monkeypatch):
    monkeypatch.setenv("MEDIA_STORAGE_ENABLED", "false")
    monkeypatch.setenv("MEDIA_STORAGE_ROOT_PATH", "media_storage")
    config.get_media_storage_config()
    updated = config.update_media_storage_config(enabled=True, root_path="/new/root")
    assert updated.enabled is True
    assert updated.root_path == "/new/root"
    assert updated.delete_remote_after_save is False
    assert config.get_media_storage_config().root_path == "/new/root"


def test_media_storage_config_frozen():
    c = config.MediaStorageConfig(enabled=True, root_path="x", delete_remote_after_save=False)
    with pytest.raises(AttributeError):
        c.enabled = False
