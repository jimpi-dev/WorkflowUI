"""Tests for ComfyUI capability and WorkflowUI plugin version helpers."""
from unittest.mock import patch, MagicMock

import pytest

from services import comfyui_info


def _clear_capabilities_cache():
    comfyui_info._capabilities_cache["result"] = None
    comfyui_info._capabilities_cache["expires"] = 0.0
    comfyui_info._capabilities_cache.pop("url", None)


# --- version_meets_minimum ---


def test_version_meets_minimum_below_returns_false():
    assert comfyui_info.version_meets_minimum("1.0.9", "1.0.10") is False
    assert comfyui_info.version_meets_minimum("1.0.0", "1.0.10") is False
    assert comfyui_info.version_meets_minimum("0.9.9", "1.0.10") is False


def test_version_meets_minimum_equal_returns_true():
    assert comfyui_info.version_meets_minimum("1.0.10", "1.0.10") is True


def test_version_meets_minimum_above_returns_true():
    assert comfyui_info.version_meets_minimum("1.0.11", "1.0.10") is True
    assert comfyui_info.version_meets_minimum("1.1.0", "1.0.10") is True
    assert comfyui_info.version_meets_minimum("2.0.0", "1.0.10") is True


def test_version_meets_minimum_uses_workflowui_min_constant():
    min_ver = comfyui_info.WORKFLOWUI_PLUGIN_MIN_VERSION
    assert comfyui_info.version_meets_minimum("1.0.10", min_ver) is True
    assert comfyui_info.version_meets_minimum("1.0.9", min_ver) is False


# --- get_workflowui_plugin_status ---


@patch.object(comfyui_info, "requests")
def test_get_workflowui_plugin_status_plugin_below_minimum_returns_incompatible(mock_requests):
    _clear_capabilities_cache()
    cap_res = MagicMock()
    cap_res.ok = True
    cap_res.headers = {"content-type": "application/json"}
    cap_res.json.return_value = {"workflowui_plugin": True, "delete": False}
    ver_res = MagicMock()
    ver_res.ok = True
    ver_res.headers = {"content-type": "application/json"}
    ver_res.json.return_value = {"workflowui_plugin_version": "1.0.9"}
    mock_requests.get.side_effect = [cap_res, ver_res]

    delete_supported, plugin_available, plugin_incompatible = comfyui_info.get_workflowui_plugin_status(
        "http://localhost:8188"
    )

    assert delete_supported is False
    assert plugin_available is False
    assert plugin_incompatible is True


@patch.object(comfyui_info, "requests")
def test_get_workflowui_plugin_status_plugin_meets_minimum_returns_available(mock_requests):
    _clear_capabilities_cache()
    cap_res = MagicMock()
    cap_res.ok = True
    cap_res.headers = {"content-type": "application/json"}
    cap_res.json.return_value = {"workflowui_plugin": True, "delete": True}
    ver_res = MagicMock()
    ver_res.ok = True
    ver_res.headers = {"content-type": "application/json"}
    ver_res.json.return_value = {"workflowui_plugin_version": "1.0.10"}
    mock_requests.get.side_effect = [cap_res, ver_res]

    delete_supported, plugin_available, plugin_incompatible = comfyui_info.get_workflowui_plugin_status(
        "http://localhost:8188"
    )

    assert delete_supported is True
    assert plugin_available is True
    assert plugin_incompatible is False


@patch.object(comfyui_info, "requests")
def test_get_workflowui_plugin_status_no_version_info_returns_incompatible(mock_requests):
    _clear_capabilities_cache()
    cap_res = MagicMock()
    cap_res.ok = True
    cap_res.headers = {"content-type": "application/json"}
    cap_res.json.return_value = {"workflowui_plugin": True}
    ver_res = MagicMock()
    ver_res.ok = True
    ver_res.headers = {"content-type": "application/json"}
    ver_res.json.return_value = {}
    mock_requests.get.side_effect = [cap_res, ver_res]

    _, plugin_available, plugin_incompatible = comfyui_info.get_workflowui_plugin_status("http://localhost:8188")

    assert plugin_available is False
    assert plugin_incompatible is True


@patch.object(comfyui_info, "requests")
def test_get_workflowui_plugin_status_capabilities_returns_string_true_still_detects_plugin(mock_requests):
    """When capabilities returns workflowui_plugin as string 'true' (e.g. some serializers), we still detect plugin."""
    _clear_capabilities_cache()
    cap_res = MagicMock()
    cap_res.ok = True
    cap_res.headers = {"content-type": "application/json"}
    cap_res.json.return_value = {"workflowui_plugin": "true", "delete": False}
    ver_res = MagicMock()
    ver_res.ok = True
    ver_res.headers = {"content-type": "application/json"}
    ver_res.json.return_value = {"workflowui_plugin_version": "1.0.10"}
    mock_requests.get.side_effect = [cap_res, ver_res]

    _, plugin_available, plugin_incompatible = comfyui_info.get_workflowui_plugin_status("http://localhost:8188")

    assert plugin_available is True
    assert plugin_incompatible is False


@patch.object(comfyui_info, "requests")
def test_get_workflowui_plugin_status_version_as_number_coerced_to_string(mock_requests):
    """When version_info returns workflowui_plugin_version as number, we coerce to string and parse."""
    _clear_capabilities_cache()
    cap_res = MagicMock()
    cap_res.ok = True
    cap_res.headers = {"content-type": "application/json"}
    cap_res.json.return_value = {"workflowui_plugin": True}
    ver_res = MagicMock()
    ver_res.ok = True
    ver_res.headers = {"content-type": "application/json"}
    ver_res.json.return_value = {"workflowui_plugin_version": 1.0}  # number, not string
    mock_requests.get.side_effect = [cap_res, ver_res]

    _, plugin_available, plugin_incompatible = comfyui_info.get_workflowui_plugin_status("http://localhost:8188")

    # "1.0" < "1.0.10" so incompatible
    assert plugin_available is False
    assert plugin_incompatible is True


@patch.object(comfyui_info, "requests")
def test_get_workflowui_plugin_status_capabilities_fail_returns_not_incompatible_until_fetched(mock_requests):
    _clear_capabilities_cache()
    mock_requests.get.side_effect = Exception("connection refused")

    delete_supported, plugin_available, plugin_incompatible = comfyui_info.get_workflowui_plugin_status(
        "http://localhost:8188"
    )

    assert delete_supported is False
    assert plugin_available is False
    assert plugin_incompatible is False


@patch.object(comfyui_info, "get_workflowui_plugin_status")
def test_get_run_remote_storage_bytes_plugin_unavailable_returns_none(mock_status):
    mock_status.return_value = (False, False, True)  # delete, available, incompatible
    result = comfyui_info.get_run_remote_storage_bytes(
        "http://localhost:8188/",
        [{"filename": "out.png", "subfolder": "", "type": "output"}],
    )
    assert result is None


@patch.object(comfyui_info, "requests")
@patch.object(comfyui_info, "get_workflowui_plugin_status")
def test_get_run_remote_storage_bytes_sums_matching_files(mock_status, mock_requests):
    _clear_capabilities_cache()
    mock_status.return_value = (True, True, False)  # plugin available
    list_res = MagicMock()
    list_res.ok = True
    list_res.headers = {"content-type": "application/json"}
    list_res.json.return_value = {
        "type": "output",
        "subfolder": "",
        "files": [
            {"filename": "a.png", "size": 1000, "mtime": 0},
            {"filename": "b.png", "size": 2000, "mtime": 0},
        ],
    }
    mock_requests.get.return_value = list_res
    images = [
        {"filename": "a.png", "subfolder": "", "type": "output"},
        {"filename": "b.png", "subfolder": "", "type": "output"},
    ]
    result = comfyui_info.get_run_remote_storage_bytes("http://localhost:8188/", images)
    assert result == 3000
