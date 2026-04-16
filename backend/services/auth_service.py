from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any

from config import get_auth_config
from domain.user import User
from repositories.sqlite import SqliteUserRepository


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - (len(data) % 4)) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = 260000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64url_encode(salt)}${_b64url_encode(dk)}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        algo, iterations_s, salt_s, hash_s = hashed.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_s)
        salt = _b64url_decode(salt_s)
        expected = _b64url_decode(hash_s)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_token(payload: dict[str, Any]) -> str:
    cfg = get_auth_config()
    body = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
    sig = hmac.new(cfg.secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url_encode(sig)}"


def parse_token(token: str) -> dict[str, Any] | None:
    cfg = get_auth_config()
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(cfg.secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        provided = _b64url_decode(sig)
        if not hmac.compare_digest(expected, provided):
            return None
        payload = json.loads(_b64url_decode(body))
        if not isinstance(payload, dict):
            return None
        exp = payload.get("exp")
        if not isinstance(exp, int) or exp < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def ensure_admin_user(user_repo: SqliteUserRepository) -> User:
    cfg = get_auth_config()
    existing = user_repo.get_user_by_username(cfg.admin_username)
    if existing:
        return existing
    return user_repo.create_user(
        user_id=str(uuid.uuid4()),
        username=cfg.admin_username,
        password_hash=hash_password(cfg.admin_password),
        role="admin",
        allow_all_apps=True,
        created_at=int(time.time() * 1000),
    )


def build_login_token(user: User) -> str:
    cfg = get_auth_config()
    now = int(time.time())
    payload = {
        "sub": user.id,
        "role": user.role,
        "iat": now,
        "exp": now + cfg.token_ttl_seconds,
    }
    return create_token(payload)
