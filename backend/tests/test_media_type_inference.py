import threading
from pathlib import Path
from unittest.mock import Mock

from routers import execution as execution_router
from services.run_executor import RunExecutor


def test_execution_outputs_classifies_output_webm_as_video(monkeypatch):
    history_payload = {
        "p1": {
            "outputs": {
                "10": {
                    "images": [
                        {"filename": "clip.webm", "subfolder": "", "type": "output"},
                        {"filename": "track.mp3", "subfolder": "", "type": "output"},
                    ]
                }
            }
        }
    }
    fake_response = Mock()
    fake_response.json.return_value = history_payload
    monkeypatch.setattr(execution_router.requests, "get", lambda *_args, **_kwargs: fake_response)

    state = type("State", (), {"queue_lock": threading.Lock(), "runs": {}})()
    db = (None, None, None, None, None, None, None)
    out = execution_router.get_outputs("p1", state=state, db=db, ctx=None)

    assert out["status"] == "done"
    assert [x["type"] for x in out["images"]] == ["video", "audio"]


def test_run_executor_classifies_output_webm_as_video(monkeypatch, tmp_path):
    executor = RunExecutor(default_comfy_url="http://localhost:8188/", input_data_dir=Path(tmp_path))

    prompt_response = Mock()
    prompt_response.ok = True
    prompt_response.json.return_value = {"prompt_id": "p2"}

    history_response = Mock()
    history_response.json.return_value = {
        "p2": {
            "outputs": {
                "7": {
                    "images": [
                        {"filename": "video_out.webm", "subfolder": "", "type": "output"},
                        {"filename": "audio_out.wav", "subfolder": "", "type": "output"},
                    ]
                }
            }
        }
    }

    monkeypatch.setattr("services.run_executor.requests.post", lambda *_args, **_kwargs: prompt_response)
    monkeypatch.setattr("services.run_executor.requests.get", lambda *_args, **_kwargs: history_response)

    prompt_id, outputs, _seed, _exec_time = executor.execute(
        {"prompt": {}, "payload": {"values": {}, "bindings": []}, "run_id": "run-1"},
        get_db=lambda: (None, None, None, None, None, None, None),
        is_cancelled=lambda _run_id: False,
    )

    assert prompt_id == "p2"
    assert [x["type"] for x in outputs] == ["video", "audio"]
