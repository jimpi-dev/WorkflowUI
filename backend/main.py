import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from logging_config import setup_logging

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dependencies import get_db, get_user_repo
from config import get_auth_config
from services.auth_service import parse_token
from authz import AUTH_COOKIE_NAME
from routers import config, runs, projects, comfyui, import_, apps, workflows, execution, auth, users


def _load_cors_origins() -> list[str]:
    raw = (os.environ.get("WORKFLOWUI_CORS_ORIGINS") or "").strip()
    if not raw:
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    return [o.strip() for o in raw.split(",") if o.strip()]


API_PREFIX = (os.environ.get("WORKFLOWUI_API_PREFIX") or "").strip()
if API_PREFIX and not API_PREFIX.startswith("/"):
    API_PREFIX = "/" + API_PREFIX
CANONICAL_API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure logging once on startup using central configuration
    setup_logging()
    yield


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _include_api_routes(prefix: str) -> None:
    app.include_router(config.router, prefix=prefix, tags=["config"])
    app.include_router(runs.router, prefix=prefix, tags=["runs"])
    app.include_router(projects.router, prefix=prefix, tags=["projects"])
    app.include_router(comfyui.router, prefix=prefix, tags=["comfyui"])
    app.include_router(import_.router, prefix=prefix, tags=["import"])
    app.include_router(apps.router, prefix=prefix, tags=["apps"])
    app.include_router(workflows.router, prefix=prefix, tags=["workflows"])
    app.include_router(execution.router, prefix=prefix, tags=["execution"])
    app.include_router(auth.router, prefix=prefix, tags=["auth"])
    app.include_router(users.router, prefix=prefix, tags=["users"])


_include_api_routes(API_PREFIX)
if API_PREFIX != CANONICAL_API_PREFIX:
    _include_api_routes(CANONICAL_API_PREFIX)

STATIC_DIR = Path(__file__).resolve().parent / "static"
_SPA_PATH_PREFIXES = ("app", "apps", "projects", "workflows", "import")


def _is_spa_document_request(path: str, sec_fetch_dest: str, sec_fetch_mode: str, accept: str) -> bool:
    path = (path or "").strip("/")
    if not path:
        return True

    is_spa_path = path in _SPA_PATH_PREFIXES or any(path.startswith(p + "/") for p in _SPA_PATH_PREFIXES)
    if not is_spa_path:
        return False

    # Signals that this is an actual browser page navigation, not API fetch().
    if sec_fetch_dest == "document" or sec_fetch_mode == "navigate" or "text/html" in (accept or ""):
        return True

    return False


class SPAFallbackMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method != "GET":
            return await call_next(request)
        req_path = request.url.path or ""
        if req_path.startswith(CANONICAL_API_PREFIX):
            return await call_next(request)
        if API_PREFIX and req_path.startswith(API_PREFIX):
            return await call_next(request)
        sec_fetch_dest = request.headers.get("sec-fetch-dest", "")
        sec_fetch_mode = request.headers.get("sec-fetch-mode", "")
        accept = request.headers.get("accept", "")
        path = (request.url.path or "").strip("/")
        if not _is_spa_document_request(path, sec_fetch_dest, sec_fetch_mode, accept):
            return await call_next(request)
        auth_cfg = get_auth_config()
        if auth_cfg.enabled and not (req_path.startswith("/login") or req_path.startswith("/_assets/")):
            token = request.cookies.get(AUTH_COOKIE_NAME)
            payload = parse_token(token) if token else None
            sub = payload.get("sub") if isinstance(payload, dict) else None
            user = get_user_repo().get_user_by_id(sub) if isinstance(sub, str) else None
            if user is None or user.disabled_at is not None:
                return RedirectResponse(url="/login", status_code=307)
        index_path = STATIC_DIR / "index.html"
        if not index_path.is_file():
            return await call_next(request)
        return FileResponse(index_path, media_type="text/html")


def _serve_static_or_spa(full_path: str):
    path_no_query = full_path.split("?")[0].lstrip("/")
    if not path_no_query:
        index_path = STATIC_DIR / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Not found")
    file_path = (STATIC_DIR / path_no_query).resolve()
    if not str(file_path).startswith(str(STATIC_DIR)):
        raise HTTPException(status_code=404, detail="Not found")
    if file_path.is_file():
        return FileResponse(file_path)
    if file_path.is_dir() and (file_path / "index.html").is_file():
        return FileResponse(file_path / "index.html")
    index_path = STATIC_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")


if STATIC_DIR.is_dir():
    app.add_middleware(SPAFallbackMiddleware)

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return _serve_static_or_spa(full_path)
