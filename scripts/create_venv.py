#!/usr/bin/env python3
"""Create a WorkflowUI virtualenv, including on filesystems without symlinks (exFAT)."""
from __future__ import annotations

import os
import shutil
import sys
import venv
from pathlib import Path


def _reexec_system_python() -> None:
    exe = os.path.realpath(sys.executable or "")
    if "AppImage" not in exe and "cursor" not in exe.lower():
        return
    for cand in ("/usr/bin/python3", "/usr/bin/python"):
        if os.path.isfile(cand):
            os.execv(cand, [cand, os.path.abspath(__file__), *sys.argv[1:]])


def _can_symlink(directory: Path) -> bool:
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / f".symlink-probe-{os.getpid()}"
    try:
        os.symlink("target", probe)
        probe.unlink()
        return True
    except OSError:
        return False
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass


class CompatEnvBuilder(venv.EnvBuilder):
    def ensure_directories(self, env_dir: str):
        orig = os.symlink

        def _safe_symlink(src, dst, target_is_directory=False, *, dir_fd=None):
            try:
                return orig(src, dst, target_is_directory, dir_fd=dir_fd)
            except OSError:
                if os.path.basename(dst) == "lib64":
                    return None
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                    return None
                raise

        os.symlink = _safe_symlink  # type: ignore[method-assign]
        try:
            return super().ensure_directories(env_dir)
        finally:
            os.symlink = orig  # type: ignore[method-assign]


def main() -> int:
    _reexec_system_python()
    if len(sys.argv) < 2:
        print("usage: create_venv.py <venv-dir>", file=sys.stderr)
        return 2
    venv_dir = Path(sys.argv[1]).expanduser().resolve()
    venv_dir.parent.mkdir(parents=True, exist_ok=True)
    use_symlinks = _can_symlink(venv_dir.parent)
    builder = CompatEnvBuilder(with_pip=True, symlinks=use_symlinks, clear=False, upgrade=False)
    builder.create(str(venv_dir))
    py = venv_dir / "bin" / "python"
    if not py.exists():
        py = venv_dir / "Scripts" / "python.exe"
    if not py.exists():
        print(f"venv created but python was not found in {venv_dir}", file=sys.stderr)
        return 1
    print(str(py))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
