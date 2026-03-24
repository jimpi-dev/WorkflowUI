import time

from fastapi import APIRouter, Depends, HTTPException, Response

from authz import AUTH_COOKIE_NAME, get_request_context, require_user
from config import get_auth_config
from dependencies import get_user_repo
from services.auth_service import build_login_token, ensure_admin_user, verify_password

router = APIRouter()


@router.post("/auth/login")
def login(body: dict, response: Response):
    cfg = get_auth_config()
    if not cfg.enabled:
        raise HTTPException(status_code=400, detail="Authentication is disabled")
    user_repo = get_user_repo()
    ensure_admin_user(user_repo)
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or not password:
        raise HTTPException(status_code=400, detail="username and password are required")
    user = user_repo.get_user_by_username(username)
    if not user or user.disabled_at is not None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = build_login_token(user)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=cfg.token_ttl_seconds,
        path="/",
    )
    return {"ok": True, "user": {"id": user.id, "username": user.username, "role": user.role, "allow_all_apps": user.allow_all_apps}}


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(ctx=Depends(get_request_context)):
    cfg = get_auth_config()
    if not cfg.enabled:
        return {"enabled": False, "authenticated": False, "user": None}
    if ctx.user is None:
        return {"enabled": True, "authenticated": False, "user": None}
    u = ctx.user
    return {
        "enabled": True,
        "authenticated": True,
        "user": {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "allow_all_apps": u.allow_all_apps,
            "disabled_at": u.disabled_at,
            "now": int(time.time()),
        },
    }
