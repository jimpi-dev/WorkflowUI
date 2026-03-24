from dataclasses import dataclass
import os
from pathlib import Path


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    v = value.strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    return default


@dataclass(frozen=True)
class MediaStorageConfig:
    enabled: bool
    root_path: str
    delete_remote_after_save: bool


_MEDIA_STORAGE_CONFIG: MediaStorageConfig | None = None


def load_media_storage_config() -> MediaStorageConfig:
    enabled = _parse_bool(os.environ.get("MEDIA_STORAGE_ENABLED"), False)
    root_path = (os.environ.get("MEDIA_STORAGE_ROOT_PATH") or "media_storage").strip()
    delete_remote_after_save = _parse_bool(os.environ.get("MEDIA_STORAGE_DELETE_REMOTE"), False)
    return MediaStorageConfig(
        enabled=enabled,
        root_path=root_path,
        delete_remote_after_save=delete_remote_after_save,
    )


def get_media_storage_config() -> MediaStorageConfig:
    global _MEDIA_STORAGE_CONFIG
    if _MEDIA_STORAGE_CONFIG is None:
        _MEDIA_STORAGE_CONFIG = load_media_storage_config()
    return _MEDIA_STORAGE_CONFIG


def update_media_storage_config(
    *,
    enabled: bool | None = None,
    root_path: str | None = None,
    delete_remote_after_save: bool | None = None,
) -> MediaStorageConfig:
    global _MEDIA_STORAGE_CONFIG
    current = get_media_storage_config()
    _MEDIA_STORAGE_CONFIG = MediaStorageConfig(
        enabled=current.enabled if enabled is None else bool(enabled),
        root_path=current.root_path if root_path is None else str(root_path),
        delete_remote_after_save=(
            current.delete_remote_after_save
            if delete_remote_after_save is None
            else bool(delete_remote_after_save)
        ),
    )
    return _MEDIA_STORAGE_CONFIG

@dataclass(frozen=True)
class WorkflowUIEmbedConfig:
    embed_on_download: bool
    embed_on_save: bool


_WORKFLOWUI_EMBED_CONFIG: WorkflowUIEmbedConfig | None = None


def _load_workflowui_embed_env_from_file() -> None:
    if "WORKFLOWUI_EMBED_METADATA_ON_DOWNLOAD" in os.environ and "WORKFLOWUI_EMBED_METADATA_ON_SAVE" in os.environ:
        return
    try:
        root = Path(__file__).resolve().parent.parent
        env_path = root / ".env"
        if not env_path.is_file():
            return
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == "WORKFLOWUI_EMBED_METADATA_ON_DOWNLOAD" and key not in os.environ:
                    os.environ[key] = value
                if key == "WORKFLOWUI_EMBED_METADATA_ON_SAVE" and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


def load_workflowui_embed_config() -> WorkflowUIEmbedConfig:
    _load_workflowui_embed_env_from_file()
    embed_on_download = _parse_bool(os.environ.get("WORKFLOWUI_EMBED_METADATA_ON_DOWNLOAD"), False)
    embed_on_save = _parse_bool(os.environ.get("WORKFLOWUI_EMBED_METADATA_ON_SAVE"), False)
    return WorkflowUIEmbedConfig(embed_on_download=embed_on_download, embed_on_save=embed_on_save)


def get_workflowui_embed_config() -> WorkflowUIEmbedConfig:
    global _WORKFLOWUI_EMBED_CONFIG
    if _WORKFLOWUI_EMBED_CONFIG is None:
        _WORKFLOWUI_EMBED_CONFIG = load_workflowui_embed_config()
    return _WORKFLOWUI_EMBED_CONFIG


@dataclass(frozen=True)
class AuthConfig:
    enabled: bool
    secret: str
    token_ttl_seconds: int
    admin_username: str
    admin_password: str


_AUTH_CONFIG: AuthConfig | None = None


def load_auth_config() -> AuthConfig:
    enabled = _parse_bool(os.environ.get("WORKFLOWUI_AUTH_ENABLED"), False)
    secret = (os.environ.get("WORKFLOWUI_AUTH_SECRET") or "workflowui-dev-secret").strip()
    try:
        ttl = int((os.environ.get("WORKFLOWUI_AUTH_TOKEN_TTL_SECONDS") or "86400").strip())
    except ValueError:
        ttl = 86400
    admin_username = (os.environ.get("WORKFLOWUI_AUTH_ADMIN_USERNAME") or "admin").strip()
    admin_password = (os.environ.get("WORKFLOWUI_AUTH_ADMIN_PASSWORD") or "admin").strip()
    return AuthConfig(
        enabled=enabled,
        secret=secret or "workflowui-dev-secret",
        token_ttl_seconds=max(300, ttl),
        admin_username=admin_username or "admin",
        admin_password=admin_password or "admin",
    )


def get_auth_config() -> AuthConfig:
    global _AUTH_CONFIG
    if _AUTH_CONFIG is None:
        _AUTH_CONFIG = load_auth_config()
    return _AUTH_CONFIG
