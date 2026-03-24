import time
import uuid

from fastapi import APIRouter, Depends, HTTPException

from authz import require_admin
from dependencies import get_db, get_user_repo
from services.auth_service import hash_password

router = APIRouter()


@router.get("/admin/users")
def list_users(_=Depends(require_admin)):
    user_repo = get_user_repo()
    users = user_repo.list_users()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "allow_all_apps": u.allow_all_apps,
            "disabled_at": u.disabled_at,
            "created_at": u.created_at,
            "allowed_app_ids": user_repo.list_user_app_ids(u.id),
        }
        for u in users
    ]


@router.post("/admin/users")
def create_user(body: dict, _=Depends(require_admin)):
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    role = (body.get("role") or "user").strip().lower()
    allow_all_apps = bool(body.get("allow_all_apps", False))
    if role not in {"admin", "user"}:
        raise HTTPException(status_code=400, detail="role must be admin or user")
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")
    user_repo = get_user_repo()
    if user_repo.get_user_by_username(username):
        raise HTTPException(status_code=409, detail="username already exists")
    user = user_repo.create_user(
        user_id=str(uuid.uuid4()),
        username=username,
        password_hash=hash_password(password),
        role=role,
        allow_all_apps=allow_all_apps,
        created_at=int(time.time() * 1000),
    )
    app_ids = body.get("allowed_app_ids")
    if isinstance(app_ids, list) and not allow_all_apps:
        user_repo.set_user_app_access(user.id, [str(a) for a in app_ids if a])
    return {"id": user.id}


@router.patch("/admin/users/{user_id}")
def patch_user(user_id: str, body: dict, _=Depends(require_admin)):
    user_repo = get_user_repo()
    current = user_repo.get_user_by_id(user_id)
    if not current:
        raise HTTPException(status_code=404, detail="User not found")
    role = body.get("role")
    if role is not None:
        role = str(role).strip().lower()
        if role not in {"admin", "user"}:
            raise HTTPException(status_code=400, detail="role must be admin or user")
    password_hash = None
    if body.get("password"):
        password_hash = hash_password(str(body.get("password")))
    allow_all_apps = body.get("allow_all_apps")
    disabled_at = body.get("disabled_at", None) if "disabled_at" in body else None
    updated = user_repo.update_user(
        user_id,
        password_hash=password_hash,
        role=role,
        allow_all_apps=bool(allow_all_apps) if allow_all_apps is not None else None,
        disabled_at=disabled_at,
        set_disabled_at=("disabled_at" in body),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    if "allowed_app_ids" in body:
        app_ids = body.get("allowed_app_ids")
        if isinstance(app_ids, list) and not updated.allow_all_apps:
            user_repo.set_user_app_access(user_id, [str(a) for a in app_ids if a])
        elif updated.allow_all_apps:
            user_repo.set_user_app_access(user_id, [])
    return {"ok": True}


@router.get("/admin/apps")
def list_apps_for_assignment(_=Depends(require_admin), db=Depends(get_db)):
    _, _, app_repo, _, _, _, _ = db
    apps = app_repo.list_all_apps()
    return [{"id": a.id, "slug": a.slug, "title": a.title} for a in apps]
