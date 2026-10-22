"""Double-click launchers, the setup script, and the how-to guide, written into the data folder.

The files are identical on every Mac: they contain no usernames or paths. Each one uses
the folder it sits in as the data folder, and looks for the scheduler in the home folder
of whichever Mac runs it. So a shared iCloud folder works for everyone, and re-installing
on one Mac never breaks another.
"""

from pathlib import Path
from typing import List

from .errors import InputError
from .menu import GUIDE_NAME

MARK = "# volunteer-scheduler launcher"
GUIDE_MARK = "<!-- volunteer-scheduler guide -->"
SETUP_NAME = "Set up this Mac.command"
REPO = "https://github.com/smilne3/volunteer-scheduler.git"

# Where the scheduler lives on each Mac. Never inside iCloud Drive (decision D13).
_LOCATIONS = """CODE="${VOLUNTEER_SCHEDULER_CODE:-$HOME/code/volunteer-scheduler}"
VENV="${VOLUNTEER_SCHEDULER_VENV:-$HOME/.venvs/volunteer-scheduler}"
HERE="$(cd "$(dirname "$0")" && pwd)\""""

_LAUNCHER = """#!/bin/bash
{mark}. Made by "python -m scheduler install-launchers"; safe to delete and remake.
# Works on any Mac where "Set up this Mac.command" has been run once.
{locations}
export VOLUNTEER_SCHEDULER_DATA="$HERE"
if [ ! -d "$CODE/scheduler" ] || [ ! -x "$VENV/bin/python" ]; then
  echo "The scheduler isn't set up on this Mac yet."
  echo "Double-click \\"Set up this Mac.command\\" in this folder once, then try again."
  read -r -p "Press Return to close this window. "
  exit 1
fi
cd "$CODE" && "$VENV/bin/python" -m scheduler {command}
echo
read -r -p "Done. Press Return to close this window. "
"""

_SETUP = """#!/bin/bash
{mark}. Made by "python -m scheduler install-launchers"; safe to delete and remake.
# Sets up the scheduler on this Mac, or updates it if it's already here. Safe to run again.
REPO="{repo}"
{locations}

finish() {{
  [ -n "$1" ] && echo "$1"
  echo
  read -r -p "Press Return to close this window. "
  exit "${{2:-0}}"
}}

case "$CODE" in
  "$HOME/Library/Mobile Documents/"*) finish "The scheduler can't be installed inside iCloud Drive ($CODE)." 1 ;;
esac

echo "Setting up the volunteer scheduler on this Mac."
echo "It goes in $CODE, outside iCloud. The first time takes a few minutes."
echo

# 1. Apple's free command line tools provide git and Python.
if ! xcode-select -p >/dev/null 2>&1; then
  echo "This Mac needs Apple's free command line tools first."
  echo "A window will ask to install them: click Install and wait for it to finish."
  echo "Then double-click \\"Set up this Mac.command\\" again."
  xcode-select --install >/dev/null 2>&1
  finish "" 1
fi

# 2. Get the scheduler, or update it.
if [ -d "$CODE/.git" ]; then
  echo "Updating the scheduler..."
  if ! git -C "$CODE" pull --ff-only -q 2>/dev/null; then
    # This copy and GitHub's have split, usually because GitHub's history was rewritten. Switch to GitHub's, keeping the old version on a backup branch,
    # but only if this copy is on main and has no unsaved edits.
    if [ "$(git -C "$CODE" branch --show-current)" = main ] \\
       && [ -z "$(git -C "$CODE" status --porcelain --untracked-files=no)" ] \\
       && git -C "$CODE" fetch -q origin main 2>/dev/null; then
      git -C "$CODE" branch -q -f "backup-$(date +%Y%m%d-%H%M%S)" HEAD
      git -C "$CODE" reset -q --hard origin/main
      echo "(Updated. The old version is kept on a backup branch.)"
    else
      echo "(Couldn't update, so the version already here is kept.)"
    fi
  fi
elif [ -e "$CODE" ]; then
  finish "$CODE already exists but isn't the scheduler. Move it aside, then try again." 1
else
  echo "Downloading the scheduler..."
  mkdir -p "$(dirname "$CODE")"
  git clone -q "$REPO" "$CODE" || finish "The download didn't work. Check the internet connection and try again." 1
fi

# 3. Its own Python environment, with what it needs.
if [ ! -x "$VENV/bin/python" ]; then
  echo "Creating its Python environment..."
  python3 -m venv "$VENV" || finish "Couldn't create the Python environment." 1
  "$VENV/bin/python" -m pip install -q --upgrade pip >/dev/null 2>&1
fi
echo "Installing what it needs..."
"$VENV/bin/python" -m pip install -q -r "$CODE/requirements.txt" \\
  || finish "Installing didn't work. Check the internet connection and try again." 1

# 4. Check it runs.
if (cd "$CODE" && "$VENV/bin/python" -m scheduler --version >/dev/null 2>&1); then
  echo
  echo "All set. Double-click \\"Volunteer Scheduler.command\\" to start."
  echo "To get updates later, double-click \\"Set up this Mac.command\\" again."
  finish ""
else
  finish "Something went wrong: the scheduler installed but doesn't start." 1
fi
"""

LAUNCHERS = {
    "Volunteer Scheduler.command": _LAUNCHER.format(mark=MARK, locations=_LOCATIONS, command="menu"),
    "Draft next week.command": _LAUNCHER.format(mark=MARK, locations=_LOCATIONS, command="draft"),
    SETUP_NAME: _SETUP.format(mark=MARK, locations=_LOCATIONS, repo=REPO),
}


def _ours(path: Path, mark: str) -> bool:
    try:
        return mark in path.read_text(encoding="utf-8", errors="replace")[:400]
    except OSError:
        return False


def install_launchers(folder: Path) -> List[Path]:
    folder = Path(folder)
    if not folder.is_dir():
        raise InputError(f"The data folder {folder} doesn't exist. Create it (or set VOLUNTEER_SCHEDULER_DATA) first.")
    targets = [(folder / name, MARK) for name in LAUNCHERS] + [(folder / GUIDE_NAME, GUIDE_MARK)]
    for path, mark in targets:
        if path.exists() and not _ours(path, mark):
            raise InputError(f'"{path.name}" already exists in {folder} and wasn\'t made by this tool, so it was left alone.')

    written = []
    for name, script in LAUNCHERS.items():
        path = folder / name
        if not path.exists() or path.read_text(encoding="utf-8") != script:
            path.write_text(script, encoding="utf-8")
        path.chmod(0o755)
        written.append(path)
    guide = folder / GUIDE_NAME
    source = (Path(__file__).parent / "guide.html").read_text(encoding="utf-8")
    if not guide.exists() or guide.read_text(encoding="utf-8") != source:
        guide.write_text(source, encoding="utf-8")
    written.append(guide)
    return written
