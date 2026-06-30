import hashlib
import json
import logging
import requests
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Response

from authz import require_user, ensure_run_access
from config import get_workflowui_embed_config
from services.comfyui_info import normalize_comfy_url as _normalize_comfy_url
from services.workflowui_metadata import (
    build_workflowui_metadata_payload,
    workflowui_metadata_to_json_string,
)
from services.png_metadata import inject_workflowui_chunk
from services.mp3_metadata import inject_workflowui_metadata as inject_workflowui_metadata_mp3
from services.mp4_metadata import inject_workflowui_metadata as inject_workflowui_metadata_mp4

from dependencies import COMFY_URL, INPUT_DATA_DIR, get_db, get_media_storage_service, get_run_queue_state, get_vault_input_repo
from services.vault_input_access import ensure_can_read_input_file
from services.media_storage_service import MediaStorageService
from services.video_thumbnail import get_or_create_video_thumbnail_webp_bytes

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_user)])

ALLOWED_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
ALLOWED_VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".mkv", ".mov"})
ALLOWED_AUDIO_EXTENSIONS = frozenset({".mp3", ".wav", ".ogg", ".flac", ".m4a"})
_INTEGER_BINDING_FIELDS = frozenset({
    "width", "height", "width_override", "height_override", "batch_size",
    "steps", "cfg", "seed", "noise_seed",
})


def _resolve_comfy_url_for_prompt(prompt_id: str, state, get_db_fn) -> str:
    with state.queue_lock:
        for rid, data in state.runs.items():
            if data.get("prompt_id") == prompt_id:
                return data.get("comfyui_url") or COMFY_URL
    run_repo = get_db_fn()[3]
    run = run_repo.get_run_by_prompt_id(prompt_id) if run_repo else None
    if run and run.comfyui_url:
        return _normalize_comfy_url(run.comfyui_url)
    return COMFY_URL


def _ensure_input_data_dir() -> Path:
    INPUT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return INPUT_DATA_DIR


def _content_hash_name(content: bytes, ext: str) -> str:
    h = hashlib.sha256(content).hexdigest()[:16]
    return f"{h}{ext}"


def _media_type_for_path(path: Path) -> str:
    suffix = (path.suffix or "").lower()
    if suffix in (".webp", ".jpeg", ".jpg", ".png", ".gif", ".bmp", ".ico"):
        return "image/" + ("jpeg" if suffix in (".jpeg", ".jpg") else "png" if suffix == ".png" else suffix[1:])
    if suffix in (".mp4", ".webm", ".ogg", ".mov"):
        return "video/" + ("mp4" if suffix == ".mp4" else "webm" if suffix == ".webm" else "ogg")
    if suffix in (".mp3", ".wav", ".ogg", ".m4a"):
        return "audio/" + ("mpeg" if suffix == ".mp3" else suffix[1:])
    return "application/octet-stream"


def _response_media_type(filename: str, reported: str | None, content: bytes) -> str:
    """
    Normalize Content-Type for proxied ComfyUI /view responses. Browsers reject <video> when
    the server sends application/octet-stream or a wrong MIME for MP4.
    """
    fn = (filename or "").lower()
    if fn.endswith(".png"):
        return "image/png"
    if fn.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if fn.endswith(".webp"):
        return "image/webp"
    if fn.endswith(".gif"):
        return "image/gif"
    if fn.endswith(".mp4"):
        return "video/mp4"
    if fn.endswith(".webm"):
        return "video/webm"
    if fn.endswith(".mov"):
        return "video/quicktime"
    if fn.endswith(".mkv"):
        return "video/x-matroska"
    if fn.endswith(".mp3"):
        return "audio/mpeg"
    if fn.endswith(".wav"):
        return "audio/wav"
    if fn.endswith(".flac"):
        return "audio/flac"
    if fn.endswith(".m4a"):
        return "audio/mp4"
    if fn.endswith(".ogg"):
        return "audio/ogg"
    if content and len(content) >= 12 and content[4:8] == b"ftyp":
        return "video/mp4"
    rep = (reported or "").split(";")[0].strip().lower()
    if rep and rep not in ("application/octet-stream", "binary/octet-stream", "text/plain"):
        return rep
    return "application/octet-stream"


def _resolved_embed_on_download(app) -> bool:
    if getattr(app, "embed_workflowui_metadata_on_download", None) is not None:
        return bool(app.embed_workflowui_metadata_on_download)
    return get_workflowui_embed_config().embed_on_download


def _run_output_type_matches(stored_type: str, requested_type: str) -> bool:
    """
    Run JSON may use type \"output\" (folder) while ComfyUI history uses \"video\"/\"audio\"
    for the same file; clients may send either.
    """
    a = (stored_type or "output").strip().lower()
    b = (requested_type or "output").strip().lower()
    if a == b:
        return True
    if a in ("output", "video", "audio") and b in ("output", "video", "audio"):
        return True
    if a in ("output", "image") and b in ("output", "image"):
        return True
    return False


def _use_workflowui_plugin_media_view(type_str: str, filename: str) -> bool:
    """Use WorkflowUIPlugin /workflowui/media/view for images only; video/audio need ComfyUI /view (full file)."""
    t = (type_str or "output").strip().lower()
    if t in ("video", "audio"):
        return False
    fn = (filename or "").lower()
    for ext in (".mp4", ".webm", ".mkv", ".mov", ".mp3", ".wav", ".ogg", ".flac", ".m4a"):
        if fn.endswith(ext):
            return False
    return True


def _coerce_binding_value(field_path: str, value) -> Any:
    if value is None:
        return value
    last_part = field_path.split(".")[-1]
    if last_part in _INTEGER_BINDING_FIELDS:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return value
    if last_part in ("strength", "strength_model"):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return value


def apply_binding(node: dict, field_path: str, value):
    if "inputs" not in node or not isinstance(node["inputs"], dict):
        node["inputs"] = {}
    value = _coerce_binding_value(field_path, value)
    parts = field_path.split(".")
    if len(parts) == 1:
        node["inputs"][parts[0]] = value
        return
    if len(parts) == 2:
        group_key, sub_key = parts
        if group_key not in node["inputs"]:
            node["inputs"][group_key] = {}
        node["inputs"][group_key][sub_key] = _coerce_binding_value(sub_key, value)


def resolve_node(prompt: dict, node_id: str):
    if not isinstance(prompt, dict):
        return None
    if node_id in prompt:
        return prompt[node_id]
    parts = node_id.split(":")
    current = prompt
    for part in parts:
        if not isinstance(current, dict):
            return None
        if part in current:
            current = current[part]
            continue
        if "inputs" in current and part in current["inputs"]:
            current = current["inputs"][part]
            continue
        return None
    return current


@router.get("/outputs/{prompt_id}")
def get_outputs(prompt_id: str, state=Depends(get_run_queue_state), db=Depends(get_db), ctx=Depends(require_user)):
    run_repo = db[3]
    run = run_repo.get_run_by_prompt_id(prompt_id) if run_repo else None
    if run:
        ensure_run_access(run.id, ctx, run_repo)
    comfy_url = _resolve_comfy_url_for_prompt(prompt_id, state, get_db)
    res = requests.get(f"{comfy_url}/history/{prompt_id}")
    history = res.json()
    if prompt_id not in history:
        return {"status": "running"}

    def _output_type(raw_type: str, filename: str) -> str:
        if raw_type == "audio":
            return "audio"
        if raw_type == "video":
            return "video"
        if raw_type == "output" and filename:
            ext = Path(filename).suffix.lower()
            if ext in {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".opus"}:
                return "audio"
            if ext in {".mp4", ".webm", ".mkv", ".mov", ".avi", ".wmv", ".m4v", ".mpg", ".mpeg"}:
                return "video"
        return raw_type if raw_type else "image"

    outputs = []
    for node in history[prompt_id]["outputs"].values():
        if "images" in node:
            for img in node["images"]:
                raw = img.get("type", "image")
                outputs.append({
                    "filename": img["filename"],
                    "subfolder": img.get("subfolder", ""),
                    "type": _output_type(raw, img.get("filename", "")),
                })
        if "gifs" in node:
            for gif in node["gifs"]:
                outputs.append({
                    "filename": gif["filename"],
                    "subfolder": gif.get("subfolder", ""),
                    "type": "video",
                })
        if "audio" in node:
            for aud in node["audio"]:
                outputs.append({
                    "filename": aud["filename"],
                    "subfolder": aud.get("subfolder", ""),
                    "type": "audio",
                })
    return {"status": "done", "images": outputs}


@router.post("/upload_image")
def upload_image(
    image: UploadFile = File(..., alias="image"),
    app_id: str | None = None,
    db=Depends(get_db),
    ctx=Depends(require_user),
):
    if app_id:
        _, _, app_repo, _, _, _, _ = db
        app = app_repo.get_app_by_id(app_id) if app_repo else None
        comfy_url = _normalize_comfy_url(app.comfyui_url or COMFY_URL) if app else COMFY_URL
    else:
        comfy_url = COMFY_URL
    if not image.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    ext = Path(image.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image format. Use: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}",
        )
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    try:
        content = image.file.read()
        _ensure_input_data_dir()
        hash_name = _content_hash_name(content, ext)
        local_path = INPUT_DATA_DIR / hash_name
        if not local_path.exists():
            with open(local_path, "wb") as f:
                f.write(content)
        files = {"image": (hash_name, content, image.content_type)}
        res = requests.post(
            f"{comfy_url.rstrip('/')}/upload/image",
            files=files,
            timeout=60,
        )
        res.raise_for_status()
        data = res.json()
        owner_id = ctx.user.id if (ctx.auth_enabled and ctx.user) else None
        get_vault_input_repo().record_upload(hash_name, owner_id)
        return {
            "name": hash_name,
            "subfolder": data.get("subfolder", ""),
            "type": data.get("type", "input"),
        }
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"ComfyUI upload failed: {e!s}")
    finally:
        image.file.close()


@router.post("/upload_media")
def upload_media(
    file: UploadFile = File(..., alias="file"),
    type: str = "image",
    app_id: str | None = None,
    db=Depends(get_db),
    ctx=Depends(require_user),
):
    """Upload image, video, or audio to ComfyUI input folder. Use type=image|video|audio."""
    if app_id:
        _, _, app_repo, _, _, _, _ = db
        app = app_repo.get_app_by_id(app_id) if app_repo else None
        comfy_url = _normalize_comfy_url(app.comfyui_url or COMFY_URL) if app else COMFY_URL
    else:
        comfy_url = COMFY_URL
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    ext = Path(file.filename).suffix.lower()
    media_type = (type or "image").lower()
    if media_type == "image":
        allowed = ALLOWED_IMAGE_EXTENSIONS
        content_prefix = "image/"
    elif media_type == "video":
        allowed = ALLOWED_VIDEO_EXTENSIONS
        content_prefix = "video/"
    elif media_type == "audio":
        allowed = ALLOWED_AUDIO_EXTENSIONS
        content_prefix = "audio/"
    else:
        raise HTTPException(status_code=400, detail="type must be image, video, or audio")
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported {media_type} format. Use: {', '.join(sorted(allowed))}",
        )
    if file.content_type and not file.content_type.startswith(content_prefix) and not file.content_type.startswith("application/"):
        raise HTTPException(status_code=400, detail=f"File must be a {media_type} file")
    try:
        content = file.file.read()
        _ensure_input_data_dir()
        hash_name = _content_hash_name(content, ext)
        local_path = INPUT_DATA_DIR / hash_name
        if not local_path.exists():
            with open(local_path, "wb") as f:
                f.write(content)
        mime = file.content_type or "application/octet-stream"
        files = {"image": (hash_name, content, mime)}
        res = requests.post(
            f"{comfy_url.rstrip('/')}/upload/image",
            files=files,
            timeout=60,
        )
        res.raise_for_status()
        data = res.json()
        if media_type == "image":
            owner_id = ctx.user.id if (ctx.auth_enabled and ctx.user) else None
            get_vault_input_repo().record_upload(hash_name, owner_id)
        return {
            "name": hash_name,
            "subfolder": data.get("subfolder", ""),
            "type": data.get("type", "input"),
        }
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"ComfyUI upload failed: {e!s}")
    finally:
        file.file.close()


def load_run_output_content_bytes(
    filename: str,
    subfolder: str,
    type: str,
    run_id: str | None,
    *,
    preview: str | None,
    state,
    service: MediaStorageService,
    db,
    ctx,
) -> tuple[bytes, str]:
    """Load raw bytes for GET /image (local or ComfyUI) without WorkflowUI embed injection."""
    req_type = (type or "").strip().lower()
    if ctx.auth_enabled and not run_id and req_type != "input":
        raise HTTPException(status_code=400, detail="run_id is required")
    if not run_id and req_type == "input":
        # Input uploads are stored locally under INPUT_DATA_DIR by hashed filename.
        # Keep strict path checks to avoid traversal.
        if not filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid input filename")
        base_dir = INPUT_DATA_DIR.resolve()
        input_path = (INPUT_DATA_DIR / filename).resolve()
        if not str(input_path).startswith(str(base_dir)) or not input_path.is_file():
            raise HTTPException(status_code=404, detail="Input media file not found")
        if ctx.auth_enabled:
            run_repo = db[3]
            if run_repo is not None:
                ensure_can_read_input_file(ctx, filename.strip(), get_vault_input_repo(), run_repo)
        return input_path.read_bytes(), _media_type_for_path(input_path)
    is_video_thumbnail_preview = (
        (preview or "").strip().lower() == "webp"
        and (type or "").strip().lower() == "video"
    )
    content: bytes | None
    media_type: str
    if run_id:
        run_entity = ensure_run_access(run_id, ctx, db[3])
        entries = []
        try:
            if run_entity.media_json:
                entries = json.loads(run_entity.media_json)
            elif run_entity.images_json:
                entries = json.loads(run_entity.images_json)
        except Exception:
            entries = []
        matched_ent = None
        matched_index: int | None = None
        for idx, ent in enumerate(entries if isinstance(entries, list) else []):
            if not isinstance(ent, dict):
                continue
            ent_type = (ent.get("type") or ent.get("kind") or "output").strip().lower()
            req_type = (type or "output").strip().lower()
            if not _run_output_type_matches(ent_type, req_type):
                continue
            if (ent.get("filename") or "") == (filename or "") and (ent.get("subfolder") or "") == (subfolder or ""):
                matched_ent = ent
                matched_index = idx
                break
        if not matched_ent:
            raise HTTPException(status_code=404, detail="Image not found")
        if is_video_thumbnail_preview:
            if matched_index is None:
                raise HTTPException(status_code=404, detail="Video preview not found")
            # Always pass Comfy base URL so thumbnails can fall back to ComfyUI /view?preview=webp when ffmpeg is unavailable.
            comfy_url = None
            with state.queue_lock:
                if run_id in state.runs and state.runs[run_id].get("comfyui_url"):
                    comfy_url = state.runs[run_id]["comfyui_url"]
            if comfy_url is None:
                run_repo = get_db()[3]
                run = run_repo.get_run(run_id) if run_repo else None
                comfy_url = _normalize_comfy_url(run.comfyui_url or COMFY_URL) if run and run.comfyui_url else COMFY_URL
        stored_for_local = (matched_ent.get("type") or matched_ent.get("kind") or "output").strip().lower()
        local_path = service.get_local_image_path(run_id, filename, subfolder or "", stored_for_local)
        if is_video_thumbnail_preview:
            input_video_path = local_path if local_path is not None and local_path.is_file() else None
            thumb_bytes = get_or_create_video_thumbnail_webp_bytes(
                run_entity=run_entity,
                output_index=matched_index,
                filename=filename,
                subfolder=subfolder or "",
                comfy_url=comfy_url,
                view_type="output",
                input_video_path=input_video_path,
            )
            assert thumb_bytes is not None
            return thumb_bytes, "image/webp"

        if local_path is not None and local_path.is_file():
            logger.info("GET /image: serving from local storage %s", local_path)
            media_type = _media_type_for_path(local_path)
            content = local_path.read_bytes()
        else:
            content = None
    else:
        content = None
    if content is None:
        if run_id:
            with state.queue_lock:
                if run_id in state.runs and state.runs[run_id].get("comfyui_url"):
                    comfy_url = state.runs[run_id]["comfyui_url"]
                else:
                    comfy_url = None
            if comfy_url is None:
                run_repo = get_db()[3]
                run = run_repo.get_run(run_id) if run_repo else None
                comfy_url = _normalize_comfy_url(run.comfyui_url or COMFY_URL) if run and run.comfyui_url else COMFY_URL
        else:
            comfy_url = COMFY_URL
        comfy_type = "output" if type in ("image", "video", "audio") else type
        params: dict[str, str] = {"filename": filename, "subfolder": subfolder, "type": comfy_type}
        if preview:
            params["preview"] = preview
        base = comfy_url.rstrip("/")
        # Plugin view often returns a preview image for video; use ComfyUI /view for real media bytes.
        use_plugin_view = _use_workflowui_plugin_media_view(type or "", filename or "")
        plugin_view_url = f"{base}/workflowui/media/view"
        res = None
        if use_plugin_view:
            try:
                res = requests.get(plugin_view_url, params=params, timeout=60)
                if res.ok:
                    logger.info("GET /image: served via WorkflowUIPlugin view (%s?filename=%s)", plugin_view_url, filename)
                    content = res.content
                    media_type = res.headers.get("content-type") or "image/png"
                else:
                    res = None
            except requests.RequestException as e:
                logger.info("GET /image: WorkflowUIPlugin view not available (%s), using ComfyUI /view", e)
                res = None
        if res is None or not res.ok:
            comfy_view_url = f"{base}/view"
            try:
                res = requests.get(comfy_view_url, params=params, timeout=60)
            except requests.RequestException as e:
                logger.warning("ComfyUI /view request failed: %s", e)
                raise HTTPException(status_code=502, detail=f"Failed to fetch from ComfyUI: {e!s}")
            if not res.ok:
                raise HTTPException(status_code=res.status_code, detail=f"ComfyUI returned {res.status_code}")
            content = res.content
            media_type = _response_media_type(filename or "", res.headers.get("content-type"), content)
    assert content is not None
    return content, media_type


@router.get("/image")
def get_image(
    filename: str,
    subfolder: str,
    type: str,
    run_id: str | None = None,
    preview: str | None = None,
    embed_workflowui_metadata: str | None = None,
    state=Depends(get_run_queue_state),
    service=Depends(get_media_storage_service),
    db=Depends(get_db),
    ctx=Depends(require_user),
):
    logger.info("GET /image filename=%s subfolder=%s type=%s run_id=%s preview=%s embed=%s", filename, subfolder, type, run_id, preview, embed_workflowui_metadata)
    content, media_type = load_run_output_content_bytes(
        filename, subfolder, type, run_id, preview=preview, state=state, service=service, db=db, ctx=ctx
    )
    if run_id and embed_workflowui_metadata and str(embed_workflowui_metadata).strip() in ("1", "true", "yes"):
        _, _, app_repo, run_repo, _, _, _ = get_db()
        run = run_repo.get_run(run_id) if run_repo else None
        app = app_repo.get_app_by_id(run.app_id) if (run and run.app_id and app_repo) else None
        embed_effective = _resolved_embed_on_download(app) if app else get_workflowui_embed_config().embed_on_download
        if embed_effective:
            _, workflow_repo, app_repo, run_repo, project_repo, _, _ = get_db()
            payload = build_workflowui_metadata_payload(run_id, run_repo, workflow_repo, app_repo, project_repo)
            if payload:
                json_str = workflowui_metadata_to_json_string(payload)
                if content.startswith(b"\x89PNG\r\n\x1a\n"):
                    content = inject_workflowui_chunk(content, json_str)
                elif type == "audio" and (content[:3] == b"ID3" or (len(content) >= 2 and content[0] == 0xFF and (content[1] & 0xE0) == 0xE0)):
                    content = inject_workflowui_metadata_mp3(content, json_str)
                elif type == "video":
                    content = inject_workflowui_metadata_mp4(content, json_str)
    return Response(content=content, media_type=media_type)
