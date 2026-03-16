import json
import time
from unittest.mock import patch, MagicMock

import pytest
import requests

from conftest import SAMPLE_WORKFLOW_GRAPH
from services.comfyui_info import WORKFLOWUI_PLUGIN_MIN_VERSION
from services.mp4_metadata import inject_workflowui_metadata, read_workflowui_metadata
from tests.test_mp4_metadata import _minimal_mp4_bytes


def test_get_workflow_definitions_empty(client):
    r = client.get("/workflow-definitions")
    assert r.status_code == 200
    assert r.json() == []


def test_get_config_returns_workflowui_plugin_incompatible_when_plugin_below_minimum(client):
    with patch("routers.config.get_workflowui_plugin_status", return_value=(False, False, True)):
        r = client.get("/config")
    assert r.status_code == 200
    data = r.json()
    assert data.get("workflowuiPluginAvailable") is False
    assert data.get("workflowuiPluginIncompatible") is True
    assert data.get("workflowuiPluginMinVersion") == WORKFLOWUI_PLUGIN_MIN_VERSION


def test_import_preview_success(client):
    r = client.post(
        "/import/preview",
        json={"name": "TestWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    assert r.status_code == 200
    data = r.json()
    assert "graph_hash" in data
    assert "detected_inputs" in data
    assert "detected_outputs" in data
    assert data["is_new_workflow"] is True


def test_import_preview_missing_name(client):
    r = client.post("/import/preview", json={"graph": SAMPLE_WORKFLOW_GRAPH})
    assert r.status_code == 400


def test_import_preview_invalid_graph(client):
    r = client.post("/import/preview", json={"name": "A", "graph": {}})
    assert r.status_code == 400


def test_import_success(client):
    r = client.post(
        "/import",
        json={"name": "ImportedWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == 1
    assert "workflow_id" in data
    assert "workflow_version_id" in data
    assert "detected_inputs" in data


def test_import_duplicate_returns_409(client):
    client.post(
        "/import",
        json={"name": "DupWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    r = client.post(
        "/import",
        json={"name": "DupWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    assert r.status_code == 409
    detail = r.json().get("detail", {})
    msg = detail.get("message", str(detail))
    assert "duplicate" in msg.lower()


def test_get_workflow_definitions_after_import(client):
    client.post(
        "/import",
        json={"name": "ListedWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    r = client.get("/workflow-definitions")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["name"] == "ListedWorkflow"


def test_get_workflow_version_detail(client):
    imp = client.post(
        "/import",
        json={"name": "VerWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    version_id = imp.json()["workflow_version_id"]
    r = client.get(f"/workflow-versions/{version_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == version_id
    assert data["version"] == 1
    assert "detected_inputs" in data


def test_get_workflow_version_not_found(client):
    r = client.get("/workflow-versions/nonexistent-id")
    assert r.status_code == 404


def test_get_workflow_definition_detail(client):
    imp = client.post(
        "/import",
        json={"name": "DefWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    workflow_id = imp.json()["workflow_id"]
    r = client.get(f"/workflow-definitions/{workflow_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "DefWorkflow"
    assert len(data["versions"]) == 1
    assert data["versions"][0]["version"] == 1


def test_get_workflow_definition_not_found(client):
    r = client.get("/workflow-definitions/nonexistent-id")
    assert r.status_code == 404


def test_post_projects_success(client):
    r = client.post(
        "/projects",
        json={"name": "My Project", "description": "Desc"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "My Project"
    assert "id" in data


def test_post_projects_requires_name(client):
    r = client.post("/projects", json={})
    assert r.status_code == 400


def test_get_projects_list(client):
    client.post("/projects", json={"name": "P1"})
    r = client.get("/projects")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    assert "run_count" in items[0]


def test_get_project_detail(client):
    create = client.post("/projects", json={"name": "DetailProj"})
    project_id = create.json()["id"]
    r = client.get(f"/projects/{project_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "DetailProj"
    assert "run_count" in data
    assert "apps_used" in data


def test_get_project_runs_empty(client):
    create = client.post("/projects", json={"name": "RunsProj"})
    project_id = create.json()["id"]
    r = client.get(f"/projects/{project_id}/runs")
    assert r.status_code == 200
    data = r.json()
    assert data == {"runs": [], "total": 0}


def test_get_project_runs_stats(client):
    r = client.get("/projects/nonexistent-id/runs/stats")
    assert r.status_code == 404
    create = client.post("/projects", json={"name": "StatsProj"})
    project_id = create.json()["id"]
    r = client.get(f"/projects/{project_id}/runs/stats")
    assert r.status_code == 200
    data = r.json()
    assert "total_runs" in data
    assert "total_generations" in data
    assert data["total_runs"] == 0
    assert data["total_generations"] == 0


def test_move_runs_to_project_success(client):
    import dependencies

    imp = client.post(
        "/import",
        json={"name": "MoveWF", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    version_id = imp.json()["workflow_version_id"]
    source_proj = client.post("/projects", json={"name": "SourceProj"})
    source_id = source_proj.json()["id"]
    target_proj = client.post("/projects", json={"name": "TargetProj"})
    target_id = target_proj.json()["id"]

    run_repo = dependencies.get_db()[3]
    created_at = int(time.time() * 1000)
    run1 = run_repo.create_run(
        id="move-run-1",
        project_id=source_id,
        workflow_version_id=version_id,
        app_id=None,
        status="done",
        created_at=created_at,
    )
    run2 = run_repo.create_run(
        id="move-run-2",
        project_id=source_id,
        workflow_version_id=version_id,
        app_id=None,
        status="done",
        created_at=created_at + 1,
    )

    r = client.post(
        f"/projects/{source_id}/runs/move",
        json={"run_ids": [run1.id, run2.id], "target_project_id": target_id},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["moved"] == 2

    source_runs = client.get(f"/projects/{source_id}/runs")
    assert source_runs.status_code == 200
    assert len(source_runs.json()["runs"]) == 0

    target_runs = client.get(f"/projects/{target_id}/runs")
    assert target_runs.status_code == 200
    target_run_ids = [x["id"] for x in target_runs.json()["runs"]]
    assert run1.id in target_run_ids
    assert run2.id in target_run_ids


def test_move_runs_to_project_target_same_as_source_returns_400(client):
    create = client.post("/projects", json={"name": "SameProj"})
    project_id = create.json()["id"]
    r = client.post(
        f"/projects/{project_id}/runs/move",
        json={"run_ids": ["any-run-id"], "target_project_id": project_id},
    )
    assert r.status_code == 400
    assert "different" in (r.json().get("detail") or "").lower()


def test_move_runs_to_project_empty_run_ids_returns_400(client):
    create = client.post("/projects", json={"name": "EmptyRunsProj"})
    project_id = create.json()["id"]
    r = client.post(
        f"/projects/{project_id}/runs/move",
        json={"run_ids": [], "target_project_id": "other-project-id"},
    )
    assert r.status_code == 400


def test_move_runs_to_project_source_not_found_returns_404(client):
    r = client.post(
        "/projects/nonexistent-source/runs/move",
        json={"run_ids": ["run-1"], "target_project_id": "some-target-id"},
    )
    assert r.status_code == 404


def test_move_runs_to_project_target_not_found_returns_404(client):
    import dependencies

    imp = client.post("/import", json={"name": "MoveNF", "graph": SAMPLE_WORKFLOW_GRAPH})
    version_id = imp.json()["workflow_version_id"]
    source_proj = client.post("/projects", json={"name": "SourceNF"})
    source_id = source_proj.json()["id"]

    run_repo = dependencies.get_db()[3]
    run = run_repo.create_run(
        id="move-nf-run",
        project_id=source_id,
        workflow_version_id=version_id,
        app_id=None,
        status="done",
        created_at=int(time.time() * 1000),
    )

    r = client.post(
        f"/projects/{source_id}/runs/move",
        json={"run_ids": [run.id], "target_project_id": "nonexistent-target"},
    )
    assert r.status_code == 404


def test_move_runs_to_project_run_not_in_source_returns_400(client):
    import dependencies

    imp = client.post("/import", json={"name": "MoveOther", "graph": SAMPLE_WORKFLOW_GRAPH})
    version_id = imp.json()["workflow_version_id"]
    source_proj = client.post("/projects", json={"name": "SourceOther"})
    source_id = source_proj.json()["id"]
    other_proj = client.post("/projects", json={"name": "OtherProj"})
    other_id = other_proj.json()["id"]

    run_repo = dependencies.get_db()[3]
    run = run_repo.create_run(
        id="move-other-run",
        project_id=other_id,
        workflow_version_id=version_id,
        app_id=None,
        status="done",
        created_at=int(time.time() * 1000),
    )

    r = client.post(
        f"/projects/{source_id}/runs/move",
        json={"run_ids": [run.id], "target_project_id": other_id},
    )
    assert r.status_code == 400
    assert "does not belong" in (r.json().get("detail") or "").lower()


def test_post_apps_success(client):
    imp = client.post(
        "/import",
        json={"name": "AppWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    version_id = imp.json()["workflow_version_id"]
    r = client.post(
        "/apps",
        json={
            "workflow_version_id": version_id,
            "slug": "my-app",
            "title": "My App",
            "ui_config": {},
            "is_public": True,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "my-app"
    assert data["title"] == "My App"


def test_post_apps_requires_slug_title(client):
    imp = client.post(
        "/import",
        json={"name": "A", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    r = client.post(
        "/apps",
        json={"workflow_version_id": imp.json()["workflow_version_id"], "slug": "x"},
    )
    assert r.status_code == 400


def test_get_app_by_slug(client):
    imp = client.post(
        "/import",
        json={"name": "SlugWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    version_id = imp.json()["workflow_version_id"]
    client.post(
        "/apps",
        json={
            "workflow_version_id": version_id,
            "slug": "slug-app",
            "title": "Slug App",
            "ui_config": {},
        },
    )
    r = client.get("/app/slug-app")
    assert r.status_code == 200
    data = r.json()
    assert "workflow_version" in data
    assert "app" in data
    assert data["app"]["slug"] == "slug-app"
    assert "detected_inputs" in data["workflow_version"]


def test_get_app_by_slug_not_found(client):
    r = client.get("/app/nonexistent-slug")
    assert r.status_code == 404


def test_delete_app_success(client):
    imp = client.post(
        "/import",
        json={"name": "DelWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    client.post(
        "/apps",
        json={
            "workflow_version_id": imp.json()["workflow_version_id"],
            "slug": "to-delete",
            "title": "To Delete",
            "is_public": False,
        },
    )
    r = client.delete("/apps/to-delete")
    assert r.status_code == 204
    r2 = client.get("/app/to-delete")
    assert r2.status_code == 404


def test_delete_app_not_found(client):
    r = client.delete("/apps/nonexistent-slug")
    assert r.status_code == 404


def test_get_apps_public(client):
    imp = client.post(
        "/import",
        json={"name": "PubWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    client.post(
        "/apps",
        json={
            "workflow_version_id": imp.json()["workflow_version_id"],
            "slug": "public-app",
            "title": "Public App",
            "is_public": True,
        },
    )
    r = client.get("/apps/public")
    assert r.status_code == 200
    apps = r.json()
    assert any(a["slug"] == "public-app" for a in apps)


def _fake_comfy_responses(prompt_id: str = "test-prompt-id"):

    def post_mock(url, **kwargs):
        if "/prompt" in url:
            res = MagicMock()
            res.raise_for_status = MagicMock()
            res.json.return_value = {"prompt_id": prompt_id}
            return res
        raise NotImplementedError(url)

    def get_mock(url, **kwargs):
        if "/history/" in url:
            res = MagicMock()
            res.raise_for_status = MagicMock()
            res.json.return_value = {
                prompt_id: {
                    "outputs": {
                        "7": {
                            "images": [
                                {"filename": "out.png", "subfolder": "", "type": "output"}
                            ]
                        }
                    }
                }
            }
            return res
        if "/system_stats" in url or "/features" in url or "/object_info" in url or "/workflowui/version_info" in url:
            res = MagicMock()
            res.raise_for_status = MagicMock()
            res.json.return_value = {} if "/object_info" not in url else {"SaveImage": {}, "KSampler": {}, "CLIPTextEncode": {}}
            res.headers = {}
            return res
        raise NotImplementedError(url)

    return post_mock, get_mock


def test_post_run_requires_project_id(client):
    r = client.post(
        "/run",
        json={"workflow_version_id": "v1", "values": {}, "bindings": []},
    )
    assert r.status_code == 400


def test_post_run_requires_app_or_version(client):
    create = client.post("/projects", json={"name": "Proj"})
    project_id = create.json()["id"]
    r = client.post(
        "/run",
        json={
            "project_id": project_id,
            "values": {},
            "bindings": [],
        },
    )
    assert r.status_code == 400


def test_post_run_versioned_queued_and_status(client):
    import dependencies

    imp = client.post(
        "/import",
        json={"name": "RunWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    version_id = imp.json()["workflow_version_id"]
    proj = client.post("/projects", json={"name": "RunProj"})
    project_id = proj.json()["id"]

    mock_executor = MagicMock()
    mock_executor.execute.return_value = (
        "test-prompt-id",
        [{"filename": "out.png", "subfolder": "", "type": "output"}],
        12345,
        1.0,
    )

    with patch(
        "services.run_queue.fetch_comfyui_version_info",
        return_value={"comfyui_base_url": "http://localhost:8188/", "object_info_node_classes": []},
    ), patch.object(dependencies, "_executor", mock_executor):
        r = client.post(
            "/run",
            json={
                "project_id": project_id,
                "workflow_version_id": version_id,
                "values": {},
                "bindings": [],
            },
        )
    assert r.status_code == 200
    data = r.json()
    run_id = data["run_id"]
    assert "queue_position" in data

    time.sleep(0.2)
    for _ in range(20):
        status_r = client.get(f"/run/{run_id}/status")
        assert status_r.status_code == 200
        st = status_r.json()
        if st.get("status") == "done":
            assert "images" in st
            break
        if st.get("status") == "error":
            pytest.fail(f"Run failed: {st.get('error')}")
    else:
        pytest.fail("Run did not complete within 20 polls")


def test_get_run_detail(client):
    imp = client.post(
        "/import",
        json={"name": "DetailRunWF", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    version_id = imp.json()["workflow_version_id"]
    proj = client.post("/projects", json={"name": "DetailRunProj"})
    project_id = proj.json()["id"]

    post_mock, get_mock = _fake_comfy_responses()
    with patch("requests.post", side_effect=post_mock), patch(
        "requests.get", side_effect=get_mock
    ):
        run_r = client.post(
            "/run",
            json={
                "project_id": project_id,
                "workflow_version_id": version_id,
                "values": {},
                "bindings": [],
            },
        )
    run_id = run_r.json()["run_id"]
    for _ in range(20):
        st = client.get(f"/run/{run_id}/status").json()
        if st.get("status") == "done":
            break
        if st.get("status") == "error":
            break

    r = client.get(f"/runs/{run_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == run_id
    assert data["project_id"] == project_id
    assert "workflow_version_id" in data
    assert "status" in data


def test_get_run_detail_not_found(client):
    r = client.get("/runs/nonexistent-run-id")
    assert r.status_code == 404


def test_cancel_run_not_found(client):
    r = client.post("/runs/nonexistent-run-id/cancel")
    assert r.status_code == 404


def test_cancel_queued_or_running_run(client):
    imp = client.post(
        "/import",
        json={"name": "CancelWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    version_id = imp.json()["workflow_version_id"]
    proj = client.post("/projects", json={"name": "CancelProj"})
    project_id = proj.json()["id"]

    post_mock, base_get_mock = _fake_comfy_responses()

    def delayed_get_mock(url, **kwargs):
        if "/history/" in url:
            time.sleep(0.5)
        return base_get_mock(url, **kwargs)

    with patch("requests.post", side_effect=post_mock), patch(
        "requests.get", side_effect=delayed_get_mock
    ):
        run_r = client.post(
            "/run",
            json={
                "project_id": project_id,
                "workflow_version_id": version_id,
                "values": {},
                "bindings": [],
            },
        )
    run_id = run_r.json()["run_id"]
    cancel_r = client.post(f"/runs/{run_id}/cancel")
    assert cancel_r.status_code == 200
    assert cancel_r.json() == {"ok": True, "status": "cancelled"}

    status_r = client.get(f"/run/{run_id}/status")
    assert status_r.status_code == 200
    assert status_r.json().get("status") == "cancelled"
    time.sleep(0.6)


def test_cancel_run_invalid_status(client):
    imp = client.post(
        "/import",
        json={"name": "DoneCancelWF", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    version_id = imp.json()["workflow_version_id"]
    proj = client.post("/projects", json={"name": "DoneCancelProj"})
    project_id = proj.json()["id"]

    post_mock, get_mock = _fake_comfy_responses()
    with patch("requests.post", side_effect=post_mock), patch(
        "requests.get", side_effect=get_mock
    ):
        run_r = client.post(
            "/run",
            json={
                "project_id": project_id,
                "workflow_version_id": version_id,
                "values": {},
                "bindings": [],
            },
        )
    run_id = run_r.json()["run_id"]
    for _ in range(50):
        st = client.get(f"/run/{run_id}/status").json()
        if st.get("status") == "done":
            break
        if st.get("status") == "error":
            break
        time.sleep(0.1)
    else:
        pytest.fail("Run did not complete within 50 polls")

    r = client.post(f"/runs/{run_id}/cancel")
    assert r.status_code == 400
    assert "cannot be cancelled" in r.json().get("detail", "").lower()


def test_get_workflows_list(client):
    r = client.get("/workflows")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_workflow_file_not_found(client):
    r = client.get("/workflow/nonexistent-file-id")
    assert r.status_code == 404


def test_get_stable_cascade_models_returns_stage_b_and_stage_c(client):
    mock_object_info = {
        "StableCascade_CheckpointLoader": {
            "input": {
                "required": {
                    "key_opt_b": [["stage_b_1.safetensors", "stage_b_2.safetensors"]],
                    "key_opt_c": [["stage_c_1.safetensors", "stage_c_2.safetensors"]],
                },
                "optional": {},
            }
        }
    }
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = mock_object_info

    with patch("routers.comfyui.requests.get", return_value=mock_response) as mock_get:
        r = client.get("/stable_cascade_models")
    assert r.status_code == 200
    data = r.json()
    assert "stage_b" in data
    assert "stage_c" in data
    assert data["stage_b"] == ["stage_b_1.safetensors", "stage_b_2.safetensors"]
    assert data["stage_c"] == ["stage_c_1.safetensors", "stage_c_2.safetensors"]
    mock_get.assert_called_once()
    call_url = mock_get.call_args[0][0]
    assert "object_info" in call_url


def test_get_stable_cascade_models_returns_empty_when_object_info_fails(client):
    with patch("routers.comfyui.requests.get", side_effect=requests.RequestException("Connection refused")):
        r = client.get("/stable_cascade_models")
    assert r.status_code == 200
    data = r.json()
    assert data["stage_b"] == []
    assert data["stage_c"] == []


def test_get_upscale_models_returns_list_from_loader_nodes(client):
    mock_object_info = {
        "UpscaleModelLoader": {
            "input": {
                "required": {"model_name": [["4x-UltraSharp.pth", "RealESRGAN_x4plus.pth"]]},
                "optional": {},
            }
        },
        "ESRGANLoader": {
            "input": {
                "required": {"model_name": [["BSRGAN.pth", "4x-UltraSharp.pth"]]},
                "optional": {},
            }
        },
    }
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = mock_object_info

    with patch("routers.comfyui.requests.get", return_value=mock_response) as mock_get:
        r = client.get("/upscale_models")
    assert r.status_code == 200
    data = r.json()
    assert "upscale_models" in data
    models = data["upscale_models"]
    assert "4x-UltraSharp.pth" in models
    assert "RealESRGAN_x4plus.pth" in models
    assert "BSRGAN.pth" in models
    assert models == sorted(models)
    mock_get.assert_called_once()
    call_url = mock_get.call_args[0][0]
    assert "object_info" in call_url


def test_get_upscale_models_returns_empty_when_object_info_fails(client):
    with patch("routers.comfyui.requests.get", side_effect=requests.RequestException("Connection refused")):
        r = client.get("/upscale_models")
    assert r.status_code == 200
    data = r.json()
    assert data["upscale_models"] == []


def test_get_upscale_methods_returns_list_from_object_info(client):
    mock_object_info = {
        "ImageScale": {
            "input": {
                "required": {
                    "upscale_method": [["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]],
                },
                "optional": {},
            }
        },
        "LatentUpscaleBy": {
            "input": {
                "required": {
                    "upscale_method": [["nearest-exact", "bilinear", "lanczos"]],
                },
                "optional": {},
            }
        },
    }
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = mock_object_info

    with patch("routers.comfyui.requests.get", return_value=mock_response) as mock_get:
        r = client.get("/upscale_methods")
    assert r.status_code == 200
    data = r.json()
    assert "upscale_methods" in data
    methods = data["upscale_methods"]
    assert "nearest-exact" in methods
    assert "bilinear" in methods
    assert "lanczos" in methods
    assert "bicubic" in methods
    assert "area" in methods
    assert methods == sorted(methods)
    mock_get.assert_called_once()
    call_url = mock_get.call_args[0][0]
    assert "object_info" in call_url


def test_get_upscale_methods_returns_default_when_object_info_fails(client):
    with patch("routers.comfyui.requests.get", side_effect=requests.RequestException("Connection refused")):
        r = client.get("/upscale_methods")
    assert r.status_code == 200
    data = r.json()
    assert "upscale_methods" in data
    assert data["upscale_methods"] == ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]


def test_get_upscale_methods_returns_default_when_no_node_has_upscale_method(client):
    mock_object_info = {"SaveImage": {"input": {"required": {}, "optional": {}}}}
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = mock_object_info

    with patch("routers.comfyui.requests.get", return_value=mock_response):
        r = client.get("/upscale_methods")
    assert r.status_code == 200
    data = r.json()
    assert data["upscale_methods"] == ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]


def test_is_comfyui_unreachable_error_connection_error():
    from services.comfyui_info import is_comfyui_unreachable_error
    assert is_comfyui_unreachable_error(requests.ConnectionError()) is True


def test_is_comfyui_unreachable_error_timeout():
    from services.comfyui_info import is_comfyui_unreachable_error
    assert is_comfyui_unreachable_error(requests.Timeout()) is True


def test_is_comfyui_unreachable_error_request_exception_with_message():
    from services.comfyui_info import is_comfyui_unreachable_error
    e = requests.RequestException("Connection refused")
    assert is_comfyui_unreachable_error(e) is True
    e2 = requests.RequestException("Request timed out")
    assert is_comfyui_unreachable_error(e2) is True
    e3 = requests.RequestException("connection reset by peer")
    assert is_comfyui_unreachable_error(e3) is True


def test_is_comfyui_unreachable_error_false_for_other():
    from services.comfyui_info import is_comfyui_unreachable_error
    assert is_comfyui_unreachable_error(ValueError("bad")) is False
    assert is_comfyui_unreachable_error(requests.HTTPError("500")) is False
    e = requests.RequestException("Invalid JSON response")
    assert is_comfyui_unreachable_error(e) is False


def test_comfyui_unreachable_keeps_run_queued_with_warning(client):
    import dependencies

    imp = client.post(
        "/import",
        json={"name": "UnreachableWF", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    version_id = imp.json()["workflow_version_id"]
    proj = client.post("/projects", json={"name": "UnreachableProj"})
    project_id = proj.json()["id"]

    mock_executor = MagicMock()
    mock_executor.execute.side_effect = requests.ConnectionError("Connection refused")

    with patch(
        "services.run_queue.fetch_comfyui_version_info",
        return_value={"comfyui_base_url": "http://localhost:8188/", "object_info_node_classes": []},
    ), patch.object(dependencies, "_executor", mock_executor), patch(
        "time.sleep", return_value=None
    ):
        r = client.post(
            "/run",
            json={
                "project_id": project_id,
                "workflow_version_id": version_id,
                "values": {},
                "bindings": [],
            },
        )
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    for _ in range(50):
        status_r = client.get(f"/run/{run_id}/status")
        assert status_r.status_code == 200
        st = status_r.json()
        if st.get("status") == "queued" and st.get("comfyui_unreachable_warning"):
            break
        if st.get("status") == "error":
            pytest.fail(f"Run should stay queued with warning, not error: {st.get('error')}")
        time.sleep(0.05)
    else:
        pytest.fail("Run did not become queued with comfyui_unreachable_warning within polls")

    assert "ComfyUI endpoint is not reachable" in st.get("comfyui_unreachable_warning", "")

    list_r = client.get(f"/projects/{project_id}/runs")
    assert list_r.status_code == 200
    runs_list = list_r.json().get("runs", [])
    run_item = next((x for x in runs_list if x["id"] == run_id), None)
    assert run_item is not None
    assert run_item.get("status") == "queued"
    assert "ComfyUI endpoint is not reachable" in (run_item.get("comfyui_unreachable_warning") or "")


def test_retry_run_not_found(client):
    r = client.post("/runs/nonexistent-run-id/retry")
    assert r.status_code == 404


def test_retry_run_success(client):
    imp = client.post(
        "/import",
        json={"name": "RetryWF", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    version_id = imp.json()["workflow_version_id"]
    proj = client.post("/projects", json={"name": "RetryProj"})
    project_id = proj.json()["id"]

    def post_raise_connection(_url, **kwargs):
        raise requests.ConnectionError("Connection refused")

    def get_mock(url, **kwargs):
        res = MagicMock()
        res.raise_for_status = MagicMock()
        res.json.return_value = {}
        res.headers = {}
        return res

    with patch("requests.post", side_effect=post_raise_connection), patch(
        "requests.get", side_effect=get_mock
    ):
        run_r = client.post(
            "/run",
            json={
                "project_id": project_id,
                "workflow_version_id": version_id,
                "values": {},
                "bindings": [],
            },
        )
        run_id = run_r.json()["run_id"]
        for _ in range(80):
            st = client.get(f"/run/{run_id}/status").json()
            if st.get("status") == "queued" and st.get("comfyui_unreachable_warning"):
                break
            time.sleep(0.1)
        else:
            pytest.fail("Run did not get queued with warning")

        retry_r = client.post(f"/runs/{run_id}/retry")
        assert retry_r.status_code == 200
        data = retry_r.json()
        assert data.get("ok") is True
        assert data.get("status") == "queued"
        assert data.get("queue_position") == 1

        status_after = client.get(f"/run/{run_id}/status").json()
        assert status_after.get("comfyui_unreachable_warning") is None


def test_retry_run_not_queued(client):
    imp = client.post(
        "/import",
        json={"name": "DoneRetryWF", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    version_id = imp.json()["workflow_version_id"]
    proj = client.post("/projects", json={"name": "DoneRetryProj"})
    project_id = proj.json()["id"]

    post_mock, get_mock = _fake_comfy_responses()
    with patch("requests.post", side_effect=post_mock), patch(
        "requests.get", side_effect=get_mock
    ):
        run_r = client.post(
            "/run",
            json={
                "project_id": project_id,
                "workflow_version_id": version_id,
                "values": {},
                "bindings": [],
            },
        )
        run_id = run_r.json()["run_id"]
        for _ in range(30):
            st = client.get(f"/run/{run_id}/status").json()
            if st.get("status") == "done":
                break
            if st.get("status") == "error":
                pytest.fail(f"Run failed: {st.get('error')}")
            time.sleep(0.1)
        else:
            pytest.fail("Run did not complete within 30 polls")

    r = client.post(f"/runs/{run_id}/retry")
    assert r.status_code == 400
    assert "not queued" in r.json().get("detail", "").lower()


def _workflowui_payload(workflow_name: str, graph: dict, app_slug: str = "dropped-app", input_snapshot=None):
    return {
        "workflow": {"name": workflow_name, "graph": graph},
        "app": {"slug": app_slug, "title": app_slug, "ui_config": {}},
        "input_snapshot": input_snapshot,
    }


def test_import_from_workflowui_payload_open_existing_app_by_hash(client):
    import main

    imp = client.post(
        "/import",
        json={"name": "HashWorkflow", "graph": SAMPLE_WORKFLOW_GRAPH},
    )
    assert imp.status_code == 200
    version_id = imp.json()["workflow_version_id"]
    app_r = client.post(
        "/apps",
        json={
            "workflow_version_id": version_id,
            "slug": "hash-app",
            "title": "Hash App",
            "ui_config": {},
        },
    )
    assert app_r.status_code == 200
    assert app_r.json()["slug"] == "hash-app"

    apps_before = client.get("/apps").json()
    assert len(apps_before) == 1

    import dependencies
    from routers import import_ as import_router
    payload = _workflowui_payload("OtherName", SAMPLE_WORKFLOW_GRAPH, "other-slug", {"values": {"seed": 999}})
    db = dependencies.get_db()
    out = import_router._import_from_workflowui_payload(payload, db)

    assert out["action"] == "open"
    assert out["app_slug"] == "hash-app"
    assert out.get("input_snapshot") == {"values": {"seed": 999}}

    apps_after = client.get("/apps").json()
    assert len(apps_after) == 1


def test_import_from_workflowui_payload_restored_when_hash_is_new(client):
    import dependencies
    from routers import import_ as import_router
    other_graph = {**SAMPLE_WORKFLOW_GRAPH, "99": {"class_type": "EmptyLatentImage", "inputs": {"width": 512}}}
    payload = _workflowui_payload("NewGraphWorkflow", other_graph, "new-app")
    db = dependencies.get_db()
    out = import_router._import_from_workflowui_payload(payload, db)

    assert out["action"] == "restored"
    assert "app_slug" in out
    assert out["app_slug"]
    assert out.get("workflow_id")
    assert out.get("workflow_version_id")

    apps = client.get("/apps").json()
    assert len(apps) >= 1
    assert any(a["slug"] == out["app_slug"] for a in apps)


def test_import_from_file_mp4_with_workflowui_metadata(client):
    """POST /import/from-file with an MP4 containing WorkflowUI metadata restores or opens the app."""
    other_graph = {**SAMPLE_WORKFLOW_GRAPH, "99": {"class_type": "EmptyLatentImage", "inputs": {"width": 512}}}
    payload = _workflowui_payload("Mp4ImportWorkflow", other_graph, "mp4-import-app")
    mp4_bytes = _minimal_mp4_bytes()
    mp4_with_meta = inject_workflowui_metadata(mp4_bytes, json.dumps(payload, separators=(",", ":")))
    assert read_workflowui_metadata(mp4_with_meta) is not None
    r = client.post(
        "/import/from-file",
        files={"file": ("output.mp4", mp4_with_meta, "video/mp4")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("action") in ("open", "restored")
    assert data.get("app_slug") or data.get("resolved_slug")
    if data["action"] == "restored":
        assert "workflow_id" in data
        assert "workflow_version_id" in data


def test_run_table_diagnostics(client):
    r = client.get("/config/diagnostics/run-table")
    assert r.status_code == 200
    data = r.json()
    assert "row_count" in data
    assert "columns" in data
    assert "total_bytes" in data
    assert isinstance(data["row_count"], int)
    assert isinstance(data["columns"], dict)
    assert isinstance(data["total_bytes"], (int, float))
    for col_name, entry in data["columns"].items():
        assert "bytes" in entry
        assert "searchable" in entry
        assert isinstance(entry["bytes"], (int, float))
        assert isinstance(entry["searchable"], bool)
