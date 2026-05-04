from __future__ import annotations

from fastapi import HTTPException

from authz import RequestContext
from repositories.sqlite import SqliteRunRepository
from repositories.vault_input_repository import SqliteVaultInputRepository


def can_read_input_file(
    ctx: RequestContext,
    filename: str,
    vault_repo: SqliteVaultInputRepository,
    run_repo: SqliteRunRepository,
) -> bool:
    if not ctx.auth_enabled:
        return True
    if ctx.user is None:
        return False
    if ctx.user.role == "admin":
        return True
    row = vault_repo.get(filename)
    if row is None:
        return run_repo.user_run_references_input_filename(ctx.user.id, filename)
    if row.owner_user_id is None:
        return run_repo.user_run_references_input_filename(ctx.user.id, filename)
    return row.owner_user_id == ctx.user.id


def ensure_can_read_input_file(
    ctx: RequestContext,
    filename: str,
    vault_repo: SqliteVaultInputRepository,
    run_repo: SqliteRunRepository,
) -> None:
    if not can_read_input_file(ctx, filename, vault_repo, run_repo):
        raise HTTPException(status_code=404, detail="Input media file not found")


def can_delete_vault_input(
    ctx: RequestContext,
    filename: str,
    vault_repo: SqliteVaultInputRepository,
) -> bool:
    if not ctx.auth_enabled:
        return True
    if ctx.user is None:
        return False
    if ctx.user.role == "admin":
        return True
    row = vault_repo.get(filename)
    if row is None:
        return False
    return row.owner_user_id == ctx.user.id
