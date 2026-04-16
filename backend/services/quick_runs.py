from __future__ import annotations

import time
import uuid

from db.migrate import QUICK_RUNS_PROJECT_ID, QUICK_RUNS_PROJECT_NAME
from domain.user import User
from repositories.sqlite import SqliteProjectRepository, SqliteUserRepository


def ensure_quick_runs_project_for_user(
    user: User | None,
    *,
    auth_enabled: bool,
    project_repo: SqliteProjectRepository,
    user_repo: SqliteUserRepository,
) -> str:
    """
    Resolve and ensure the Quick runs project ID for the current mode/user.

    - auth disabled: use the global default project ID
    - auth enabled: each user gets their own project, tracked on user_account.quick_runs_project_id
    """
    if not auth_enabled or user is None:
        return QUICK_RUNS_PROJECT_ID

    now = int(time.time() * 1000)
    current = user_repo.get_user_by_id(user.id)
    if current is None:
        return QUICK_RUNS_PROJECT_ID

    quick_id = (current.quick_runs_project_id or "").strip()
    if not quick_id:
        quick_id = str(uuid.uuid4())
        user_repo.update_user(
            current.id,
            quick_runs_project_id=quick_id,
            set_quick_runs_project_id=True,
        )

    project = project_repo.get_project(quick_id)
    if project is None:
        project_repo.create_project(
            quick_id,
            QUICK_RUNS_PROJECT_NAME,
            "Runs from Just generate - no project needed.",
            now,
            now,
            owner_user_id=current.id,
        )
    elif getattr(project, "owner_user_id", None) != current.id:
        # Keep one distinct Quick runs project per user.
        quick_id = str(uuid.uuid4())
        user_repo.update_user(
            current.id,
            quick_runs_project_id=quick_id,
            set_quick_runs_project_id=True,
        )
        project_repo.create_project(
            quick_id,
            QUICK_RUNS_PROJECT_NAME,
            "Runs from Just generate - no project needed.",
            now,
            now,
            owner_user_id=current.id,
        )
    return quick_id
