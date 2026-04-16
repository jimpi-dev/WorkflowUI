from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Cookie, Depends, HTTPException, Request

from config import get_auth_config
from dependencies import get_db, get_user_repo
from domain.user import User
from services.auth_service import parse_token


AUTH_COOKIE_NAME = "workflowui_auth"


@dataclass(frozen=True)
class RequestContext:
    user: User | None
    auth_enabled: bool


def _get_user_from_cookie(token: str | None) -> User | None:
    if not token:
        return None
    payload = parse_token(token)
    if not payload:
        return None
    sub = payload.get("sub")
    if not isinstance(sub, str):
        return None
    user = get_user_repo().get_user_by_id(sub)
    if not user or user.disabled_at is not None:
        return None
    return user


def get_request_context(
    request: Request,
    auth_cookie: str | None = Cookie(default=None, alias=AUTH_COOKIE_NAME),
) -> RequestContext:
    cfg = get_auth_config()
    if not cfg.enabled:
        return RequestContext(user=None, auth_enabled=False)
    user = _get_user_from_cookie(auth_cookie)
    return RequestContext(user=user, auth_enabled=True)


def require_user(ctx: RequestContext = Depends(get_request_context)) -> RequestContext:
    if ctx.auth_enabled and ctx.user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return ctx


def require_admin(ctx: RequestContext = Depends(require_user)) -> RequestContext:
    if ctx.user is None or ctx.user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return ctx


def ensure_project_access(project_id: str, ctx: RequestContext, project_repo: Any) -> None:
    proj = project_repo.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    owner = getattr(proj, "owner_user_id", None)
    if ctx.auth_enabled:
        if ctx.user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if owner != ctx.user.id:
            raise HTTPException(status_code=404, detail="Project not found")
    else:
        if owner is not None:
            raise HTTPException(status_code=404, detail="Project not found")


def ensure_run_access(run_id: str, ctx: RequestContext, run_repo: Any) -> Any:
    run = run_repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    owner = getattr(run, "owner_user_id", None)
    if ctx.auth_enabled:
        if ctx.user is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        if owner != ctx.user.id:
            raise HTTPException(status_code=404, detail="Run not found")
    else:
        if owner is not None:
            raise HTTPException(status_code=404, detail="Run not found")
    return run


def user_can_access_app(app_id: str | None, ctx: RequestContext) -> bool:
    if app_id is None:
        return True
    if not ctx.auth_enabled:
        return True
    if ctx.user is None:
        return False
    if ctx.user.allow_all_apps:
        return True
    allowed = set(get_user_repo().list_user_app_ids(ctx.user.id))
    return app_id in allowed
