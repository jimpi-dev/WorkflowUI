import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from authz import RequestContext, require_user
from dependencies import INPUT_DATA_DIR, get_vault_input_repo
from repositories.vault_input_repository import SqliteVaultInputRepository
from routers.execution import ALLOWED_IMAGE_EXTENSIONS, _ensure_input_data_dir
from services.vault_input_access import can_delete_vault_input

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_user)])


def _safe_input_filename(name: str) -> bool:
    if not name or "/" in name or "\\" in name:
        return False
    ext = Path(name).suffix.lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS


def _list_disk_images() -> list[tuple[str, int, int]]:
    """Return (filename, size_bytes, mtime_ms) for image files under INPUT_DATA_DIR."""
    _ensure_input_data_dir()
    base = INPUT_DATA_DIR.resolve()
    out: list[tuple[str, int, int]] = []
    try:
        for p in INPUT_DATA_DIR.iterdir():
            if not p.is_file():
                continue
            if p.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
                continue
            rp = p.resolve()
            if not str(rp).startswith(str(base)):
                continue
            st = p.stat()
            out.append((p.name, int(st.st_size), int(st.st_mtime * 1000)))
    except OSError as e:
        logger.warning("Vault list: cannot scan input dir: %s", e)
    out.sort(key=lambda x: x[2], reverse=True)
    return out


@router.get("/vault/inputs")
def list_vault_inputs(
    ctx: RequestContext = Depends(require_user),
    vault_repo: SqliteVaultInputRepository = Depends(get_vault_input_repo),
):
    """List input images stored for WorkflowUI (hashed uploads under INPUT_DATA_DIR), scoped by auth context."""
    disk = _list_disk_images()
    disk_names = {d[0] for d in disk}
    disk_meta = {name: (sz, mt) for name, sz, mt in disk}

    if not ctx.auth_enabled:
        rows = {r.filename: r for r in vault_repo.list_all_rows()}
        items = []
        for name, size, mtime in disk:
            row = rows.get(name)
            items.append(
                {
                    "filename": name,
                    "size_bytes": size,
                    "mtime_ms": mtime,
                    "uploaded_at": row.uploaded_at if row else None,
                    "owner_user_id": row.owner_user_id if row else None,
                    "can_delete": True,
                }
            )
        return {"items": items}

    assert ctx.user is not None
    if ctx.user.role == "admin":
        rows = {r.filename: r for r in vault_repo.list_all_rows()}
        items = []
        for name, size, mtime in disk:
            row = rows.get(name)
            items.append(
                {
                    "filename": name,
                    "size_bytes": size,
                    "mtime_ms": mtime,
                    "uploaded_at": row.uploaded_at if row else None,
                    "owner_user_id": row.owner_user_id if row else None,
                    "can_delete": True,
                }
            )
        for name, row in rows.items():
            if name not in disk_names:
                items.append(
                    {
                        "filename": name,
                        "size_bytes": None,
                        "mtime_ms": None,
                        "uploaded_at": row.uploaded_at,
                        "owner_user_id": row.owner_user_id,
                        "can_delete": True,
                    }
                )
        items.sort(key=lambda x: (x.get("mtime_ms") or 0, x.get("uploaded_at") or 0), reverse=True)
        return {"items": items}

    rows = vault_repo.list_rows_for_owner(ctx.user.id)
    items = []
    for row in rows:
        if row.filename not in disk_meta:
            items.append(
                {
                    "filename": row.filename,
                    "size_bytes": None,
                    "mtime_ms": None,
                    "uploaded_at": row.uploaded_at,
                    "owner_user_id": row.owner_user_id,
                    "can_delete": True,
                }
            )
            continue
        size, mtime = disk_meta[row.filename]
        items.append(
            {
                "filename": row.filename,
                "size_bytes": size,
                "mtime_ms": mtime,
                "uploaded_at": row.uploaded_at,
                "owner_user_id": row.owner_user_id,
                "can_delete": True,
            }
        )
    return {"items": items}


@router.delete("/vault/inputs/{filename}")
def delete_vault_input(
    filename: str,
    ctx: RequestContext = Depends(require_user),
    vault_repo: SqliteVaultInputRepository = Depends(get_vault_input_repo),
):
    if not _safe_input_filename(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not can_delete_vault_input(ctx, filename, vault_repo):
        raise HTTPException(status_code=403, detail="Not allowed to delete this file")

    base = INPUT_DATA_DIR.resolve()
    path = (INPUT_DATA_DIR / filename).resolve()
    if not str(path).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if path.is_file():
        try:
            path.unlink()
        except OSError as e:
            logger.warning("Vault delete: unlink failed %s: %s", path, e)
            raise HTTPException(status_code=500, detail="Failed to delete file") from e
    vault_repo.delete_row(filename)
    return {"ok": True, "filename": filename}
