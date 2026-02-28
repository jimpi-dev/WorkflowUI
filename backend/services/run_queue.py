from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from typing import Any, Callable

from services.comfyui_info import fetch_comfyui_version_info, is_comfyui_unreachable_error
from services.run_executor import (
    RunExecutor,
    build_slim_metadata_snapshot,
    used_node_class_types_from_prompt,
)

logger = logging.getLogger(__name__)


def queue_run(
    run_queue: list,
    runs: dict,
    queue_lock: threading.Lock,
    worker_busy: list[bool],
    job: dict,
    default_comfy_url: str,
    executor: RunExecutor,
    get_db: Callable[[], Any],
    get_media_service: Callable[[], Any],
) -> dict:
    run_id = job.get("run_id") or str(uuid.uuid4())
    job["run_id"] = run_id
    payload = job.get("payload") or {}
    bindings = payload.get("bindings", [])
    values = payload.get("values", {})
    seed = None
    for b in bindings:
        if b.get("field") in ("seed", "noise_seed"):
            raw = values.get(b.get("key"), 0)
            seed = int(raw) if raw and int(raw) != 0 else None
            break
    job["seed"] = seed
    with queue_lock:
        queue_position = len(run_queue) + 1
        run_queue.append(job)
        runs[run_id] = {
            "status": "queued",
            "queue_position": queue_position,
            "comfyui_url": job.get("comfyui_url") or default_comfy_url,
        }
    start_worker(run_queue, runs, queue_lock, worker_busy, executor, get_db, get_media_service)
    return {"run_id": run_id, "queue_position": queue_position}


def start_worker(
    run_queue: list,
    runs: dict,
    queue_lock: threading.Lock,
    worker_busy: list[bool],
    executor: RunExecutor | None,
    get_db: Callable[[], Any] | None,
    get_media_service: Callable[[], Any] | None,
) -> None:
    with queue_lock:
        if worker_busy[0]:
            return
        worker_busy[0] = True
    t = threading.Thread(
        target=_worker_loop,
        args=(run_queue, runs, queue_lock, worker_busy, executor, get_db, get_media_service),
        daemon=True,
    )
    t.start()


def _worker_loop(
    run_queue: list,
    runs: dict,
    queue_lock: threading.Lock,
    worker_busy: list[bool],
    executor: RunExecutor | None,
    get_db: Callable[[], Any] | None,
    get_media_service: Callable[[], Any] | None,
) -> None:
    if not executor or not get_db or not get_media_service:
        worker_busy[0] = False
        return

    def is_cancelled(run_id: str) -> bool:
        with queue_lock:
            return runs.get(run_id, {}).get("status") == "cancelled"

    while True:
        with queue_lock:
            if not run_queue:
                worker_busy[0] = False
                return
            job = run_queue.pop(0)
            run_id = job["run_id"]
            for i, q in enumerate(run_queue):
                rid = q["run_id"]
                if rid in runs:
                    runs[rid]["queue_position"] = i + 1
            runs[run_id]["status"] = "running"

        comfy_url = job.get("comfyui_url") or (runs.get(run_id, {}).get("comfyui_url"))
        if not comfy_url:
            comfy_url = "http://localhost:8188/"
        comfyui_version_info = fetch_comfyui_version_info(comfy_url)
        run_repo = get_db()[3]
        comfyui_version_id = run_repo.get_or_create_comfyui_version(comfyui_version_info) if run_repo else None

        try:
            prompt_id, images, resolved_seed, execution_time_sec = executor.execute(job, get_db, is_cancelled)
            with queue_lock:
                runs[run_id]["status"] = "done"
                runs[run_id]["prompt_id"] = prompt_id
                runs[run_id]["images"] = images
                runs[run_id]["seed"] = resolved_seed
                runs[run_id]["execution_time"] = execution_time_sec
            if run_repo:
                run_entity = run_repo.get_run(run_id)
                if run_entity and comfyui_version_id:
                    slim_metadata = build_slim_metadata_snapshot(run_entity, comfyui_version_id)
                    media = []
                    if images:
                        for ent in images:
                            kind = ent.get("type", "image") if isinstance(ent, dict) else "image"
                            media.append({
                                "filename": ent.get("filename", "") if isinstance(ent, dict) else "",
                                "subfolder": ent.get("subfolder", "") if isinstance(ent, dict) else "",
                                "kind": kind,
                            })
                    run_repo.update_run(
                        run_id,
                        status="done",
                        prompt_id=prompt_id,
                        seed=resolved_seed,
                        images_json=json.dumps(images) if images else None,
                        media_json=json.dumps(media) if media else None,
                        execution_time=execution_time_sec,
                        remote_status="exists",
                        metadata_snapshot_json=slim_metadata,
                        comfyui_version_id=comfyui_version_id,
                    )
                try:
                    get_media_service().auto_save_run(run_id)
                except Exception as e:
                    logger.warning("Media storage auto-save error: %s", e)
        except Exception as e:
            err_msg = str(e).encode("utf-8", errors="replace").decode("utf-8")
            logger.exception("Queue worker error: %s", err_msg)
            if is_comfyui_unreachable_error(e):
                with queue_lock:
                    if runs.get(run_id, {}).get("status") == "cancelled":
                        pass
                    else:
                        runs[run_id]["status"] = "queued"
                        runs[run_id]["comfyui_unreachable_warning"] = "ComfyUI endpoint is not reachable."
                        run_queue.append(job)
                        for i, q in enumerate(run_queue):
                            rid = q["run_id"]
                            if rid in runs:
                                runs[rid]["queue_position"] = i + 1
                time.sleep(3)
                start_worker(run_queue, runs, queue_lock, worker_busy, executor, get_db, get_media_service)
                continue
            with queue_lock:
                if runs.get(run_id, {}).get("status") != "cancelled":
                    runs[run_id]["status"] = "error"
                    runs[run_id]["error"] = err_msg
            run_entity = run_repo.get_run(run_id) if run_repo else None
            if run_entity and run_repo and comfyui_version_id:
                slim_metadata = build_slim_metadata_snapshot(run_entity, comfyui_version_id)
                with queue_lock:
                    final = runs.get(run_id, {}).get("status", "error")
                if final != "cancelled":
                    run_repo.update_run(run_id, status="error", error=err_msg, metadata_snapshot_json=slim_metadata, comfyui_version_id=comfyui_version_id)
                else:
                    run_repo.update_run(run_id, status="cancelled", error="Cancelled", metadata_snapshot_json=slim_metadata, comfyui_version_id=comfyui_version_id)

        with queue_lock:
            if not run_queue:
                worker_busy[0] = False
                return
