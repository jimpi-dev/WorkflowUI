from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: str
    username: str
    password_hash: str
    role: str
    allow_all_apps: bool
    created_at: int
    disabled_at: int | None = None
    quick_runs_project_id: str | None = None
