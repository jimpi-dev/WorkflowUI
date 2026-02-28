from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

from config import MediaStorageConfig, get_media_storage_config, get_workflowui_embed_config
from domain.project import Project
from domain.run import Run
from repositories.sqlite import SqliteProjectRepository, SqliteRunRepository, SqliteWorkflowAppRepository
from services.png_metadata import inject_workflowui_chunk
from services.mp3_metadata import inject_workflowui_metadata as inject_workflowui_metadata_mp3
from services.workflowui_metadata import build_workflowui_metadata_payload, workflowui_metadata_to_json_string

_RUN_LOCKS: dict[str, threading.Lock] = {}
_RUN_LOCKS_GUARD = threading.Lock()


def _get_run_lock(run_id: str) -> threading.Lock:
    with _RUN_LOCKS_GUARD:
        lock = _RUN_LOCKS.get(run_id)
        if lock is None:
            lock = threading.Lock()
            _RUN_LOCKS[run_id] = lock
        return lock


def _normalize_comfy_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return "http://localhost:8188/"
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url.rstrip("/") + "/"


def _format_run_date_ms(ms: int) -> str:
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(ms / 1000))
    except Exception:
        return time.strftime("%Y-%m-%d", time.gmtime())


def _effective_storage_mode(project: Project | None, config: MediaStorageConfig) -> str:
    if project and project.storage_mode == "local":
        return "local" if config.enabled else "remote"
    if project and project.storage_mode == "remote":
        return "remote"
    return "remote"


def _manual_save_allowed(project: Project | None) -> bool:
    if project and project.storage_mode == "remote":
        return False
    return True


class MediaStorageService:
    def __init__(
        self,
        run_repo: SqliteRunRepository,
        project_repo: SqliteProjectRepository,
        app_repo: SqliteWorkflowAppRepository,
        workflow_repo: Any = None,
    ) -> None:
        self._run_repo = run_repo
        self._project_repo = project_repo
        self._app_repo = app_repo
        self._workflow_repo = workflow_repo

    def auto_save_run(self, run_id: str) -> dict[str, Any] | None:
        config = get_media_storage_config()
        run = self._run_repo.get_run(run_id)
        if not run:
            return None
        project = self._project_repo.get_project(run.project_id)
        if _effective_storage_mode(project, config) != "local":
            return None
        return self._save_run_internal(run_id, None, manual=False)

    def save_run(self, run_id: str) -> dict[str, Any]:
        return self._save_run_internal(run_id, None, manual=True)

    def save_run_image(self, run_id: str, image_index: int) -> dict[str, Any]:
        return self._save_run_internal(run_id, image_index, manual=True)

    def delete_remote(
        self,
        run_id: str,
        image_index: int | None = None,
        image_indices: list[int] | None = None,
    ) -> dict[str, Any]:
        run = self._run_repo.get_run(run_id)
        if not run:
            logger.warning("delete_remote: run not found run_id=%s", run_id)
            return {"ok": False, "error": "Run not found"}
        images = json.loads(run.images_json) if run.images_json else []
        if not images:
            logger.warning("delete_remote: no images on run run_id=%s", run_id)
            return {"ok": False, "error": "No images on run"}
        if image_indices is not None:
            selected = self._select_images_by_indices(images, image_indices)
        else:
            selected = self._select_images(images, image_index)
        if not selected:
            return {"ok": False, "error": "No matching images to delete"}
        ok, explicit_error = self._delete_remote_images(run, selected)
        if ok:
            updated_run_ids = self._apply_remote_deletion_to_all_runs(selected)
            return {"ok": True, "remote_status": "deleted", "updated_run_ids": updated_run_ids}
        self._run_repo.update_run(run_id, remote_status="exists")
        return {
            "ok": False,
            "error": explicit_error or "Remote delete failed (ComfyUI unreachable, error, or image already deleted)",
            "remote_status": "exists",
        }

    def delete_local(
        self,
        run_id: str,
        image_index: int | None = None,
        image_indices: list[int] | None = None,
    ) -> dict[str, Any]:
        run = self._run_repo.get_run(run_id)
        if not run:
            return {"ok": False, "error": "Run not found"}
        lock = _get_run_lock(run_id)
        if not lock.acquire(blocking=False):
            return {"ok": False, "error": "Delete already in progress"}
        try:
            run = self._run_repo.get_run(run_id)
            if not run:
                return {"ok": False, "error": "Run not found"}
            run_dir = self._resolve_run_dir(run)
            if run_dir is None or not run_dir.exists():
                self._run_repo.update_run(run_id, local_storage_status="none", local_path=None)
                return {"ok": True, "local_storage_status": "none", "local_path": None}
            indices_to_delete: list[int]
            if image_indices is not None:
                indices_to_delete = image_indices
            elif image_index is not None:
                indices_to_delete = [image_index]
            else:
                self._delete_local_run_only(run_dir, run)
                images = json.loads(run.images_json) if run.images_json else []
                if images:
                    all_indices = list(range(len(images)))
                    media_updated = self._media_with_file_deleted(run, images, all_indices)
                    self._run_repo.update_run(run_id, media_json=json.dumps(media_updated), local_storage_status="none", local_path=None)
                else:
                    self._run_repo.update_run(run_id, local_storage_status="none", local_path=None)
                return {"ok": True, "local_storage_status": "none", "local_path": None}
            for idx in indices_to_delete:
                filename = self._resolve_saved_filename(run_dir, run, idx)
                if filename:
                    try:
                        (run_dir / filename).unlink(missing_ok=True)
                    except Exception:
                        pass
            images = json.loads(run.images_json) if run.images_json else []
            updated_run_ids_list: list[str] = []
            if images and indices_to_delete:
                media_updated = self._media_with_file_deleted(run, images, indices_to_delete)
                to_remove = [
                    i for i in indices_to_delete
                    if 0 <= i < len(images)
                    and isinstance(images[i], dict)
                    and images[i].get("remote_deleted")
                ]
                if to_remove:
                    to_remove_set = set(to_remove)
                    self._rewrite_metadata_after_removing_outputs(run_dir, run, to_remove)
                    new_images = [img for j, img in enumerate(images) if j not in to_remove_set]
                    new_media = [m for j, m in enumerate(media_updated) if j not in to_remove_set]
                    self._run_repo.update_run(
                        run_id,
                        images_json=json.dumps(new_images),
                        media_json=json.dumps(new_media) if new_media else None,
                    )
                    updated_run_ids_list = [run_id]
                else:
                    self._run_repo.update_run(run_id, media_json=json.dumps(media_updated))
            run = self._run_repo.get_run(run_id)
            if not run:
                return {"ok": True, "local_storage_status": "none", "local_path": None, "updated_run_ids": updated_run_ids_list}
            run_dir = self._resolve_run_dir(run)
            status = self._compute_local_storage_status_from_remaining(run)
            if status == "none":
                if run_dir and run_dir.exists():
                    meta_path = self._get_run_metadata_path(run_dir, run)
                    if meta_path:
                        try:
                            meta_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                    try:
                        if run_dir.exists() and not any(run_dir.iterdir()):
                            run_dir.rmdir()
                    except Exception:
                        pass
                self._run_repo.update_run(run_id, local_storage_status="none", local_path=None)
                return {"ok": True, "local_storage_status": "none", "local_path": None, "updated_run_ids": updated_run_ids_list}
            self._run_repo.update_run(run_id, local_storage_status=status, local_path=str(run_dir) if run_dir else None)
            return {"ok": True, "local_storage_status": status, "local_path": str(run_dir) if run_dir else None, "updated_run_ids": updated_run_ids_list}
        finally:
            lock.release()

    def delete_both(
        self,
        run_id: str,
        image_index: int | None = None,
        image_indices: list[int] | None = None,
    ) -> dict[str, Any]:
        local_result = self.delete_local(run_id, image_index=image_index, image_indices=image_indices)
        if not local_result.get("ok"):
            return local_result
        remote_result = self.delete_remote(
            run_id, image_index=image_index, image_indices=image_indices
        )
        return {
            "ok": True,
            "local_storage_status": local_result.get("local_storage_status"),
            "remote_status": remote_result.get("remote_status", "exists"),
            "updated_run_ids": remote_result.get("updated_run_ids", []),
        }

    def delete_run_full(self, run_id: str) -> dict[str, Any]:
        run = self._run_repo.get_run(run_id)
        if not run:
            return {"ok": False, "error": "Run not found"}
        images = json.loads(run.images_json) if run.images_json else []
        if images:
            self.delete_remote(run_id, None)
            self.delete_local(run_id, None)
        else:
            run_dir = self._resolve_run_dir(run)
            if run_dir and run_dir.exists():
                self._delete_local_run_only(run_dir, run)
                try:
                    run_dir.rmdir()
                except Exception:
                    pass
        deleted = self._run_repo.delete_run(run_id)
        if not deleted:
            return {"ok": False, "error": "Run not found or already deleted"}
        return {"ok": True, "deleted_run_id": run_id}

    def _save_run_internal(
        self,
        run_id: str,
        image_index: int | None,
        *,
        manual: bool,
    ) -> dict[str, Any]:
        config = get_media_storage_config()
        run = self._run_repo.get_run(run_id)
        if not run:
            return {"ok": False, "error": "Run not found"}
        project = self._project_repo.get_project(run.project_id)
        if manual and not _manual_save_allowed(project):
            return {"ok": False, "error": "Project storage mode blocks manual save"}
        if not manual:
            mode = _effective_storage_mode(project, config)
            if mode != "local":
                return {"ok": True, "skipped": True}

        if run.status != "done":
            return {"ok": False, "error": "Run not completed"}

        root = (config.root_path or "").strip()
        if not root:
            return {"ok": False, "error": "mediaStorage.rootPath is not configured"}

        lock = _get_run_lock(run_id)
        if not lock.acquire(blocking=False):
            return {"ok": False, "error": "Save already in progress"}

        try:
            run = self._run_repo.get_run(run_id)
            if not run:
                return {"ok": False, "error": "Run not found"}
            if run.local_storage_status == "saving":
                return {"ok": False, "error": "Save already in progress"}
            if run.local_storage_status == "saved" and image_index is None:
                return {
                    "ok": True,
                    "local_storage_status": run.local_storage_status,
                    "remote_status": run.remote_status,
                    "local_path": run.local_path,
                }

            self._run_repo.update_run(run_id, local_storage_status="saving")

            images = json.loads(run.images_json) if run.images_json else []
            if not images:
                self._run_repo.update_run(run_id, local_storage_status="failed")
                return {"ok": False, "error": "Run has no images"}

            selected = self._select_images(images, image_index)
            if not selected:
                self._run_repo.update_run(run_id, local_storage_status="failed")
                return {"ok": False, "error": "Image not found"}

            run_date = _format_run_date_ms(run.created_at)
            group_or_run_id = run.run_group_id or run.id
            run_dir = Path(root) / run.project_id / run_date / group_or_run_id
            run_dir.mkdir(parents=True, exist_ok=True)

            used_names: set[str] = {
                p.name for p in run_dir.iterdir()
                if p.is_file() and not (p.name.startswith("metadata.") and p.name.endswith(".json"))
            }

            saved_files = []
            errors = []
            for idx, img in selected:
                base_name = self._output_filename_with_run_index(run, idx, img)
                out_name = self._unique_filename_in_dir(run_dir, base_name, used_names)
                used_names.add(out_name)
                out_path = run_dir / out_name
                if out_path.exists():
                    saved_files.append(out_name)
                    continue
                try:
                    data = self._fetch_remote_image_bytes(run, img)
                    if self._should_embed_workflowui_metadata(run, img) and self._workflow_repo:
                        payload = build_workflowui_metadata_payload(
                            run.id,
                            self._run_repo,
                            self._workflow_repo,
                            self._app_repo,
                            self._project_repo,
                        )
                        if payload:
                            json_str = workflowui_metadata_to_json_string(payload)
                            view_type = (img.get("type") or "output").strip().lower()
                            if view_type == "audio":
                                data = inject_workflowui_metadata_mp3(data, json_str)
                            else:
                                data = inject_workflowui_chunk(data, json_str)
                    out_path.write_bytes(data)
                    saved_files.append(out_name)
                except Exception as e:
                    errors.append({"index": idx, "error": str(e)})

            metadata = self._build_metadata(run, project, selected, saved_files)
            meta_path = run_dir / f"metadata.{run.id}.json"
            meta_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )

            if not saved_files:
                status = "failed"
            elif image_index is not None:
                status = "partial" if run.local_storage_status != "saved" else "saved"
            elif len(saved_files) < len(selected):
                status = "partial"
            else:
                status = "saved"

            self._run_repo.update_run(
                run_id,
                local_storage_status=status,
                local_path=str(run_dir),
            )

            remote_status = run.remote_status
            if status == "saved" and config.delete_remote_after_save:
                deleted, _ = self._delete_remote_images(run, selected)
                remote_status = "deleted" if deleted else "exists"
                self._run_repo.update_run(run_id, remote_status=remote_status)

            return {
                "ok": status in {"saved", "partial"},
                "local_storage_status": status,
                "remote_status": remote_status,
                "local_path": str(run_dir),
                "saved_files": saved_files,
                "errors": errors,
            }
        finally:
            lock.release()

    def _select_images(self, images: list[dict], image_index: int | None) -> list[tuple[int, dict]]:
        if image_index is None:
            return list(enumerate(images))
        if image_index < 0 or image_index >= len(images):
            return []
        return [(image_index, images[image_index])]

    def _select_images_by_indices(self, images: list[dict], indices: list[int]) -> list[tuple[int, dict]]:
        out: list[tuple[int, dict]] = []
        for i in indices:
            if 0 <= i < len(images):
                out.append((i, images[i]))
        return out

    def _get_run_output_stem(self, run: Run) -> str:
        images = json.loads(run.images_json) if run.images_json else []
        if images and isinstance(images[0], dict):
            comfy_name = images[0].get("filename")
            if isinstance(comfy_name, str) and comfy_name.strip():
                stem = Path(comfy_name.strip()).stem
                if stem:
                    return stem
        return "output"

    def _output_filename_with_run_index(self, run: Run, index: int, img: dict) -> str:
        stem = self._get_run_output_stem(run)
        t = img.get("type") if isinstance(img, dict) else None
        ext = ".mp4" if t == "video" else (".mp3" if t == "audio" else ".png")
        return f"{stem}_{index + 1}{ext}"

    def _output_filename(self, run: Run, index: int, img: dict) -> str:
        comfy_name = img.get("filename") if isinstance(img, dict) else None
        t = img.get("type") if isinstance(img, dict) else None
        default_ext = ".mp4" if t == "video" else (".mp3" if t == "audio" else ".png")
        if isinstance(comfy_name, str) and comfy_name.strip():
            base = comfy_name.strip()
            if Path(base).suffix.lower():
                return base
            return f"{base}{default_ext}"
        seed = run.seed if run.seed is not None else "seed"
        return f"{run.id}_{seed}_{index + 1}{default_ext}"

    def _unique_filename_in_dir(self, run_dir: Path, base_name: str, used: set[str]) -> str:
        stem = Path(base_name).stem
        suffix = Path(base_name).suffix.lower()
        if not suffix:
            suffix = ".png"
        candidate = base_name
        n = 0
        while (run_dir / candidate).exists() or candidate in used:
            n += 1
            candidate = f"{stem}_{n}{suffix}"
        return candidate

    def _should_embed_workflowui_metadata(self, run: Run, img: dict) -> bool:
        embed_cfg = get_workflowui_embed_config()
        app = self._app_repo.get_app_by_id(run.app_id) if (run.app_id and self._app_repo) else None
        embed_effective = (
            bool(app.embed_workflowui_metadata_on_save)
            if (app is not None and getattr(app, "embed_workflowui_metadata_on_save", None) is not None)
            else embed_cfg.embed_on_save
        )
        if not embed_effective:
            return False
        view_type = (img.get("type") or "output").strip().lower()
        if view_type == "video":
            return False
        return view_type in ("audio", "image", "output")

    def _fetch_remote_image_bytes(self, run: Run, img: dict) -> bytes:
        comfy_url = _normalize_comfy_url(run.comfyui_url or "")
        view_type = img.get("type")
        if view_type in ("video", "audio"):
            view_type = "output"
        params = {
            "filename": img.get("filename"),
            "subfolder": img.get("subfolder"),
            "type": view_type,
        }
        res = requests.get(f"{comfy_url}/view", params=params, timeout=60)
        res.raise_for_status()
        return res.content

    def _deleted_outputs_log_path(self) -> Path:
        cfg = get_media_storage_config()
        root = (cfg.root_path or "").strip() or "media_storage"
        return Path(root) / "_deleted_outputs.jsonl"

    def _get_master_seed_from_run(self, run: Run) -> int | None:
        if not run.metadata_snapshot_json:
            return run.seed
        try:
            meta = json.loads(run.metadata_snapshot_json)
            if isinstance(meta, dict):
                ms = meta.get("master_seed") or meta.get("MasterSeed") or meta.get("seed")
                if isinstance(ms, (int, float)):
                    return int(ms)
                if run.seed is not None:
                    return run.seed
        except Exception:
            pass
        return run.seed

    def _append_deleted_output_log(
        self,
        run: Run,
        index: int,
        img: dict,
    ) -> None:
        log_path = self._deleted_outputs_log_path()
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            master_seed = self._get_master_seed_from_run(run)
            record = {
                "run_id": run.id,
                "project_id": run.project_id,
                "workflow_version_id": run.workflow_version_id,
                "app_id": run.app_id,
                "seed": run.seed,
                "master_seed": master_seed,
                "output_index": index,
                "filename": img.get("filename"),
                "subfolder": img.get("subfolder") or "",
                "type": (img.get("type") or "output").strip().lower(),
                "deleted_at_ts": int(time.time() * 1000),
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to append deleted_outputs log: %s", e)

    def _has_local_copy(self, run: Run, index: int) -> bool:
        run_dir = self._resolve_run_dir(run)
        if run_dir is None or not run_dir.exists():
            return False
        filename = self._resolve_saved_filename(run_dir, run, index)
        return filename is not None and (run_dir / filename).is_file()

    def _compute_local_storage_status_from_remaining(self, run: Run) -> str:
        images = json.loads(run.images_json) if run.images_json else []
        if not images:
            return "none"
        remaining_indices = [
            i
            for i, img in enumerate(images)
            if not (isinstance(img, dict) and img.get("remote_deleted"))
        ]
        if not remaining_indices:
            return "none"
        run_dir = self._resolve_run_dir(run)
        if run_dir is None or not run_dir.exists():
            return "none"
        saved_count = sum(1 for i in remaining_indices if self._has_local_copy(run, i))
        if saved_count == 0:
            return "none"
        if saved_count == len(remaining_indices):
            return "saved"
        return "partial"

    def get_local_image_path(
        self,
        run_id: str,
        filename: str,
        subfolder: str,
        type_str: str,
    ) -> Path | None:
        run = self._run_repo.get_run(run_id)
        if not run or not run.images_json:
            return None
        images = json.loads(run.images_json)
        if not isinstance(images, list):
            return None
        subfolder_n = (subfolder or "").strip()
        type_n = (type_str or "output").strip().lower()
        for index, ent in enumerate(images):
            if not isinstance(ent, dict):
                continue
            if (ent.get("filename") or "").strip() != (filename or "").strip():
                continue
            if (ent.get("subfolder") or "").strip() != subfolder_n:
                continue
            if (ent.get("type") or "output").strip().lower() != type_n:
                continue
            if not self._has_local_copy(run, index):
                return None
            run_dir = self._resolve_run_dir(run)
            if run_dir is None or not run_dir.exists():
                return None
            saved_name = self._resolve_saved_filename(run_dir, run, index)
            if saved_name is None:
                return None
            path = run_dir / saved_name
            return path if path.is_file() else None
        return None

    def _media_with_file_deleted(
        self, run: Run, images: list[dict], indices: list[int]
    ) -> list[dict]:
        media: list[dict] = []
        if run.media_json:
            try:
                raw = json.loads(run.media_json)
                if isinstance(raw, list):
                    media = [dict(e) if isinstance(e, dict) else {} for e in raw]
            except Exception:
                pass
        if not media and run.images_json:
            try:
                raw = json.loads(run.images_json)
                if isinstance(raw, list):
                    for e in raw:
                        if isinstance(e, dict):
                            m = {k: v for k, v in e.items()}
                            if "type" in m and "kind" not in m:
                                m["kind"] = m["type"]
                            media.append(m)
                        else:
                            media.append({})
            except Exception:
                pass
        if not media and images:
            for e in images:
                if isinstance(e, dict):
                    m = {k: v for k, v in e.items()}
                    if "type" in m and "kind" not in m:
                        m["kind"] = m["type"]
                    media.append(m)
                else:
                    media.append({})
        idx_set = set(indices)
        for i in idx_set:
            if 0 <= i < len(media):
                media[i] = {**media[i], "file_deleted": True}
        return media

    def _apply_remote_deletion_to_all_runs(self, selected: list[tuple[int, dict]]) -> list[str]:
        updated_run_ids: list[str] = []
        seen_files: set[tuple[str, str, str]] = set()
        for _idx, img in selected:
            key = (
                img.get("filename") or "",
                img.get("subfolder") or "",
                (img.get("type") or "output").strip().lower(),
            )
            if not key[0]:
                continue
            if key in seen_files:
                continue
            seen_files.add(key)
            filename, subfolder, typ = key
            runs_with_file = self._run_repo.list_runs_containing_image(filename, subfolder, typ)
            for r in runs_with_file:
                try:
                    images = json.loads(r.images_json) if r.images_json else []
                except Exception:
                    continue
                to_remove: list[int] = []
                to_mark: list[int] = []
                for i, ent in enumerate(images):
                    if not isinstance(ent, dict) or ent.get("remote_deleted"):
                        continue
                    if (ent.get("filename") or "") != filename:
                        continue
                    if (ent.get("subfolder") or "") != subfolder:
                        continue
                    if (ent.get("type") or "output").strip().lower() != typ:
                        continue
                    if self._has_local_copy(r, i):
                        to_mark.append(i)
                    else:
                        to_remove.append((i, ent))
                        self._append_deleted_output_log(r, i, ent)
                if not to_mark and not to_remove:
                    continue
                updated = list(images)
                for i in to_mark:
                    if 0 <= i < len(updated) and isinstance(updated[i], dict):
                        updated[i] = {**updated[i], "remote_deleted": True}
                for i, _ in sorted(to_remove, key=lambda x: x[0], reverse=True):
                    if 0 <= i < len(updated):
                        updated.pop(i)
                deleted_outputs = json.loads(r.deleted_outputs_json) if r.deleted_outputs_json else []
                master_seed = self._get_master_seed_from_run(r)
                for i, ent in to_remove:
                    deleted_outputs.append({
                        "output_index": i,
                        "seed": r.seed,
                        "master_seed": master_seed,
                        "filename": ent.get("filename"),
                        "subfolder": ent.get("subfolder") or "",
                        "type": (ent.get("type") or "output").strip().lower(),
                        "deleted_at_ts": int(time.time() * 1000),
                    })
                new_remote_status = "deleted" if (to_mark or to_remove) else None
                indices_deleted = [i for i, _ in to_remove]
                media_updated = self._media_with_file_deleted(r, images, indices_deleted)
                self._run_repo.update_run(
                    r.id,
                    images_json=json.dumps(updated),
                    media_json=json.dumps(media_updated) if media_updated else None,
                    remote_status=new_remote_status or r.remote_status,
                    deleted_outputs_json=json.dumps(deleted_outputs),
                )
                updated_run_ids.append(r.id)
        return updated_run_ids

    def _delete_remote_images(self, run: Run, selected: list[tuple[int, dict]]) -> tuple[bool, str | None]:
        comfy_url = _normalize_comfy_url(run.comfyui_url or "")
        base = comfy_url.rstrip("/")
        ok = True
        error_405: str | None = None
        for idx, img in selected:
            try:
                res = requests.post(
                    f"{base}/delete",
                    json={
                        "filename": img.get("filename"),
                        "subfolder": img.get("subfolder"),
                        "type": img.get("type"),
                    },
                    timeout=15,
                )
                res.raise_for_status()
            except requests.exceptions.HTTPError as e:
                ok = False
                if e.response is not None and e.response.status_code == 405:
                    error_405 = (
                        "ComfyUI does not support deleting output images via API (405 Method Not Allowed). "
                        "Delete files manually from ComfyUI's output folder if needed."
                    )
                    logger.warning(
                        "ComfyUI returned 405 for delete (run_id=%s). Vanilla ComfyUI has no delete API.",
                        run.id,
                    )
                else:
                    logger.warning(
                        "ComfyUI delete failed for run_id=%s index=%s filename=%s: %s",
                        run.id, idx, img.get("filename"), e,
                    )
            except Exception as e:
                ok = False
                logger.warning(
                    "ComfyUI delete failed for run_id=%s index=%s filename=%s: %s",
                    run.id, idx, img.get("filename"), e,
                )
        if error_405:
            return (False, error_405)
        return (ok, None)

    def _resolve_run_dir(self, run: Run) -> Path | None:
        if run.local_path:
            return Path(run.local_path)
        cfg = get_media_storage_config()
        root = (cfg.root_path or "").strip()
        if not root:
            return None
        run_date = _format_run_date_ms(run.created_at)
        group_or_run_id = run.run_group_id or run.id
        return Path(root) / run.project_id / run_date / group_or_run_id

    def _resolve_saved_filename(self, run_dir: Path, run: Run, index: int) -> str | None:
        for meta_name in (f"metadata.{run.id}.json", "metadata.json"):
            meta = run_dir / meta_name
            if not meta.is_file():
                continue
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                outputs = data.get("outputs") if isinstance(data, dict) else None
                if isinstance(outputs, list) and index < len(outputs):
                    for entry in outputs:
                        if isinstance(entry, dict) and entry.get("index") == index:
                            name = entry.get("filename")
                            if isinstance(name, str) and name:
                                return name
                    name = outputs[index].get("filename") if isinstance(outputs[index], dict) else None
                    if isinstance(name, str) and name:
                        return name
            except Exception:
                pass
        images = json.loads(run.images_json) if run.images_json else []
        if index < 0 or index >= len(images):
            return None
        return self._output_filename_with_run_index(run, index, images[index])

    def _get_run_metadata_path(self, run_dir: Path, run: Run) -> Path | None:
        for name in (f"metadata.{run.id}.json", "metadata.json"):
            p = run_dir / name
            if p.is_file():
                return p
        return None

    def _get_run_saved_filenames(self, run_dir: Path, run: Run) -> list[str]:
        meta_path = self._get_run_metadata_path(run_dir, run)
        if not meta_path:
            return []
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            outputs = data.get("outputs") if isinstance(data, dict) else None
            if not isinstance(outputs, list):
                return []
            return [
                (e.get("filename") or "")
                for e in outputs
                if isinstance(e, dict) and isinstance(e.get("filename"), str) and e.get("filename")
            ]
        except Exception:
            return []

    def _rewrite_metadata_after_removing_outputs(
        self, run_dir: Path, run: Run, indices_to_remove: list[int]
    ) -> None:
        if not indices_to_remove:
            return
        meta_path = self._get_run_metadata_path(run_dir, run)
        if not meta_path or not meta_path.is_file():
            return
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            outputs = data.get("outputs") if isinstance(data, dict) else []
            if not isinstance(outputs, list):
                return
            remove_set = set(indices_to_remove)
            kept = [e for e in outputs if isinstance(e, dict) and e.get("index") not in remove_set]
            for i, e in enumerate(kept):
                e = dict(e)
                e["index"] = i
                kept[i] = e
            data = dict(data)
            data["outputs"] = kept
            meta_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Could not rewrite metadata after removing outputs: %s", e)

    def _delete_local_run_only(self, run_dir: Path, run: Run) -> None:
        meta_path = self._get_run_metadata_path(run_dir, run)
        for fname in self._get_run_saved_filenames(run_dir, run):
            try:
                (run_dir / fname).unlink(missing_ok=True)
            except Exception:
                pass
        if meta_path:
            try:
                meta_path.unlink(missing_ok=True)
            except Exception:
                pass
        if run_dir.exists():
            try:
                remaining = list(run_dir.iterdir())
                if not remaining:
                    run_dir.rmdir()
            except Exception:
                pass

    def _build_metadata(
        self,
        run: Run,
        project: Project | None,
        selected: list[tuple[int, dict]],
        saved_files: list[str],
    ) -> dict[str, Any]:
        app = self._app_repo.get_app_by_id(run.app_id) if run.app_id else None
        return {
            "run_id": run.id,
            "project_id": run.project_id,
            "project_name": project.name if project else None,
            "app_id": run.app_id,
            "app_slug": app.slug if app else None,
            "workflow_version_id": run.workflow_version_id,
            "seed": run.seed,
            "created_at": run.created_at,
            "execution_time": run.execution_time,
            "prompt_id": run.prompt_id,
            "input_snapshot": json.loads(run.input_snapshot_json) if run.input_snapshot_json else None,
            "metadata_snapshot": json.loads(run.metadata_snapshot_json) if run.metadata_snapshot_json else None,
            "outputs": [
                {
                    "index": idx,
                    "source": img,
                    "filename": saved_files[i] if i < len(saved_files) else None,
                }
                for i, (idx, img) in enumerate(selected)
            ],
            "local_storage_status": run.local_storage_status,
            "remote_status": run.remote_status,
        }
