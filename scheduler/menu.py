"""A numbered menu, so the coordinator never has to type a command (Phase 8).

Opened by double-clicking "Volunteer Scheduler.command" in the data folder.
"""

import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from . import commands
from .approval import APPROVED, approval_status
from .errors import InputError
from .review_page import WEEKS_DIR
from .week import next_monday

GUIDE_NAME = "How to use the scheduler.html"
MENU = """
Volunteer Scheduler   (data folder: {folder})
  1  Check the sign-ups
  2  Draft a week
  3  Re-check a week after editing its assignments.csv
  4  Approve a week (makes the Google Calendar file)
  5  Open the data folder
  6  Open the how-to guide
  q  Quit
"""


def open_in_finder(path: Path, reveal: bool = False) -> None:
    subprocess.run(["open", "-R", str(path)] if reveal else ["open", str(path)], check=False)


def _label(d: date) -> str:
    return f"Monday {d:%b} {d.day}"


def known_weeks(folder: Path) -> List[Tuple[date, str]]:
    root = folder / WEEKS_DIR
    weeks = []
    if root.is_dir():
        for d in sorted(root.iterdir()):
            try:
                monday = date.fromisoformat(d.name)
            except ValueError:
                continue
            if d.is_dir() and (d / "assignments.csv").exists():
                weeks.append((monday, approval_status(d).status))
    return weeks


def parse_week_answer(text: str, default: date, today: date) -> Optional[date]:
    """'' -> default; '2026-11-16' or '11/16' -> that date, moved back to its Monday. None if unreadable."""
    text = text.strip()
    if not text:
        return default
    d = None
    try:
        d = date.fromisoformat(text)
    except ValueError:
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%m/%d"):
            try:
                parsed = datetime.strptime(text, fmt).date()
            except ValueError:
                continue
            if fmt == "%m/%d":
                parsed = parsed.replace(year=today.year)
                if parsed < today - timedelta(days=180):
                    parsed = parsed.replace(year=today.year + 1)
            d = parsed
            break
    if d is None:
        return None
    return d - timedelta(days=d.weekday())


def run_menu(folder: Path, today: date, ask: Callable[[str], str] = input, out: Callable[[str], None] = print,
             opener: Callable[..., None] = open_in_finder, open_pages: bool = True) -> int:
    signups = folder / "signups.xlsx"

    def get(prompt: str) -> Optional[str]:
        try:
            return ask(prompt)
        except EOFError:
            return None

    def pick_week(default: date) -> Optional[date]:
        weeks = known_weeks(folder)
        if weeks:
            out("Weeks so far: " + ", ".join(f"{d:%b} {d.day} ({status})" for d, status in weeks[-6:]))
        for _ in range(3):
            answer = get(f"Which week? Press Return for {_label(default)}, or type its date (like 11/16): ")
            if answer is None:
                return None
            week = parse_week_answer(answer, default, today)
            if week is not None:
                if answer.strip() and week.isoformat() != answer.strip():
                    out(f"Using the week of {_label(week)}.")
                return week
            out("That isn't a date I can read. Try something like 11/16.")
        return None

    def latest_unapproved(default: date) -> date:
        pending = [d for d, status in known_weeks(folder) if status != APPROVED]
        return pending[-1] if pending else default

    while True:
        out(MENU.format(folder=folder))
        choice = get("Choose 1-6, or q to quit: ")
        if choice is None or choice.strip().lower() in ("q", "quit", "exit"):
            return 0
        choice = choice.strip()
        now = datetime.now()
        try:
            if choice == "1":
                commands.check_input(signups, today)
                review = folder / "availability_review.csv"
                if review.exists():
                    out(f"To confirm typed answers, open {review.name} in this folder (option 5).")
            elif choice == "2":
                week = pick_week(next_monday(today))
                if week is None:
                    continue
                replace = False
                week_dir = folder / WEEKS_DIR / week.isoformat()
                if (week_dir / "assignments.csv").exists() and approval_status(week_dir).status != APPROVED:
                    answer = get("There's already a draft for that week, maybe with your edits. Type yes to make a "
                                 "fresh one (the old one is kept as a copy), or press Return to keep it: ")
                    if (answer or "").strip().lower() != "yes":
                        out("Kept the existing draft. To check your edits to it, choose 3.")
                        continue
                    replace = True
                commands.draft(signups, week.isoformat(), today, now, recheck=False, replace=replace,
                               open_page=open_pages)
            elif choice == "3":
                week = pick_week(latest_unapproved(next_monday(today)))
                if week is not None:
                    commands.draft(signups, week.isoformat(), today, now, recheck=True, replace=False,
                                   open_page=open_pages)
            elif choice == "4":
                week = pick_week(latest_unapproved(next_monday(today)))
                if week is not None:
                    code = commands.approve(signups, week.isoformat(), today, now, ask=lambda p: get(p) or "")
                    calendar = folder / WEEKS_DIR / week.isoformat() / "calendar.ics"
                    if code == 0 and calendar.exists():
                        opener(calendar, reveal=True)
            elif choice == "5":
                opener(folder)
            elif choice == "6":
                guide = folder / GUIDE_NAME
                if guide.exists():
                    opener(guide)
                else:
                    out("The guide isn't in this folder. Ask whoever set this up to run install-launchers again.")
            else:
                out("Please type a number from 1 to 6, or q.")
        except InputError as e:
            out(f"Problem: {e}")
