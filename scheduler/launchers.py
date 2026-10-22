"""Double-click launchers and the how-to guide, written into the data folder (Phase 8)."""

import shlex
from pathlib import Path
from typing import List

from .errors import InputError
from .menu import GUIDE_NAME

MARK = "# volunteer-scheduler launcher"
GUIDE_MARK = "<!-- volunteer-scheduler guide -->"

_SCRIPT = """#!/bin/bash
{mark}. Made by "python -m scheduler install-launchers"; safe to delete and remake.
export VOLUNTEER_SCHEDULER_DATA={data}
cd {code} 2>/dev/null || {{
  echo "Can't find the scheduler's code at {code_text}."
  echo "Ask whoever set this up to install it again (see the README)."
  read -r -p "Press Return to close this window. "
  exit 1
}}
{python} -m scheduler {command}
echo
read -r -p "Done. Press Return to close this window. "
"""

LAUNCHERS = {
    "Volunteer Scheduler.command": "menu",
    "Draft next week.command": "draft",
}


def _ours(path: Path, mark: str) -> bool:
    try:
        return mark in path.read_text(encoding="utf-8", errors="replace")[:400]
    except OSError:
        return False


def install_launchers(folder: Path, code_dir: Path, python: Path) -> List[Path]:
    folder = Path(folder)
    if not folder.is_dir():
        raise InputError(f"The data folder {folder} doesn't exist. Create it (or set VOLUNTEER_SCHEDULER_DATA) first.")
    written = []
    for name, command in LAUNCHERS.items():
        path = folder / name
        if path.exists() and not _ours(path, MARK):
            raise InputError(f'"{name}" already exists in {folder} and wasn\'t made by this tool, so it was left alone.')
        path.write_text(_SCRIPT.format(
            mark=MARK, data=shlex.quote(str(folder)), code=shlex.quote(str(code_dir)), code_text=code_dir,
            python=shlex.quote(str(python)), command=command), encoding="utf-8")
        path.chmod(0o755)
        written.append(path)

    guide = folder / GUIDE_NAME
    if guide.exists() and not _ours(guide, GUIDE_MARK):
        raise InputError(f'"{GUIDE_NAME}" already exists in {folder} and wasn\'t made by this tool, so it was left alone.')
    source = Path(__file__).parent / "guide.html"
    guide.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    written.append(guide)
    return written
