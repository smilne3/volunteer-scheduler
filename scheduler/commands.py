"""What each command does. __main__.py only parses arguments."""

import webbrowser
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, List

from .approval import APPROVED, approval_status, write_marker
from .assignments_file import read_assignments
from .calendar_file import render_ics
from .check_input import format_report
from .checker import BROKEN, UNMET, Finding, check
from .draft_report import format_draft
from .errors import InputError
from .history import History, apply_experience_from_history, load_history
from .reasons import explain_gaps
from .review_file import ReviewResult, apply_reviews
from .review_page import WEEKS_DIR, render_assignments_csv, render_review_page, write_week_files
from .settings import Settings, load_settings
from .signups import SignupData, read_signups
from .solver import Draft, draft_from, schedule
from .week import parse_week

IMPORT_STEPS = """To add it to Google Calendar (on a computer):
  1. Open Google Calendar, click the gear, then Settings.
  2. Choose Import & export, then Import.
  3. Select calendar.ics, choose your volunteer-shifts calendar (not your personal one), and click Import.
  If you already imported this week before, delete that week's shift events first, so they aren't duplicated.
Nothing was sent to anyone. Tell volunteers about their shifts yourself."""


@dataclass
class Loaded:
    week: date
    week_dir: Path
    settings: Settings
    data: SignupData
    review: ReviewResult
    history: History
    promoted: List[str]            # counted as experienced because of approved shifts


def _load(signups: Path, week_text, today: date) -> Loaded:
    week = parse_week(week_text, today)
    settings = load_settings(signups.parent)
    data = read_signups(signups)
    review = apply_reviews(data, today=today)
    history = load_history(signups.parent, data, week, settings.fairness_lookback_weeks, today)
    promoted = apply_experience_from_history(data, history) if settings.count_approved_shifts_as_experience else []
    return Loaded(week, signups.parent / WEEKS_DIR / week.isoformat(), settings, data, review, history, promoted)


def _from_file(ld: Loaded):
    """The week as it stands in assignments.csv: (draft, findings). Unreadable rows count as broken."""
    assignments, problems = read_assignments(ld.week_dir / "assignments.csv", ld.data)
    draft = draft_from(ld.data, ld.settings, ld.week, assignments)
    findings = [Finding(BROKEN, "unreadable_row", p) for p in problems]
    findings += check(ld.data, ld.settings, ld.week, draft.assignments)
    return draft, findings


def _page(ld: Loaded, draft: Draft, findings: List[Finding], now: datetime, edited: bool) -> str:
    return render_review_page(ld.data, ld.settings, draft, findings,
                              explain_gaps(ld.data, ld.settings, draft, edited=edited), ld.review,
                              generated=now, approval=approval_status(ld.week_dir), edited=edited,
                              history=ld.history, promoted=ld.promoted)


def check_input(signups: Path, today: date) -> int:
    data = read_signups(signups)
    review = apply_reviews(data, today=today)
    print(format_report(data, review))
    return 0


def draft(signups: Path, week_text, today: date, now: datetime, recheck: bool, replace: bool,
          open_page: bool) -> int:
    ld = _load(signups, week_text, today)
    if recheck:
        result, findings = _from_file(ld)
        (ld.week_dir / "review.html").write_text(_page(ld, result, findings, now, edited=True), encoding="utf-8")
        folder = ld.week_dir
    else:
        result = schedule(ld.data, ld.settings, ld.week, recent=ld.history.recent)
        findings = check(ld.data, ld.settings, ld.week, result.assignments)
        folder = write_week_files(signups.parent, result, _page(ld, result, findings, now, edited=False),
                                  render_assignments_csv(ld.data, result), replace=replace, now=now)
    status = approval_status(folder).status
    print(format_draft(ld.data, ld.settings, result, findings, status=status, edited=recheck,
                       history=ld.history, promoted=ld.promoted))
    print(f"Review page: {folder / 'review.html'}")
    print(f"Editable draft: {folder / 'assignments.csv'}")
    if open_page:
        webbrowser.open((folder / "review.html").resolve().as_uri())
    return 2 if any(f.level == BROKEN for f in findings) else 0


def approve(signups: Path, week_text, today: date, now: datetime, ask: Callable[[str], str]) -> int:
    ld = _load(signups, week_text, today)
    if not (ld.week_dir / "assignments.csv").exists():
        raise InputError(f"There's no draft for the week of {ld.week.isoformat()} yet. "
                         f"Run: python -m scheduler draft --week {ld.week.isoformat()}")
    result, findings = _from_file(ld)
    week = ld.week.isoformat()

    broken = [f for f in findings if f.level == BROKEN]
    if broken:
        print(f"NOT APPROVED. The week of {week} breaks {len(broken)} rule{'s' if len(broken) != 1 else ''}:")
        print("\n".join(f"  - {f.message}" for f in broken))
        print(f"Fix assignments.csv, check it with: python -m scheduler draft --week {week} --recheck")
        return 2

    current = approval_status(ld.week_dir)
    if current.status == APPROVED:
        print(f"The week of {week} is already approved and unchanged. calendar.ics is up to date:")
        print(f"  {ld.week_dir / 'calendar.ics'}")
        return 0

    gaps = explain_gaps(ld.data, ld.settings, result, edited=True)
    unmet = [f for f in findings if f.level == UNMET]
    if unmet:
        print(f"The week of {week} has {len(unmet)} gap{'s' if len(unmet) != 1 else ''}:")
        print("\n".join(f"  - {g.text}" for g in gaps) if gaps else "\n".join(f"  - {f.message}" for f in unmet))
        try:
            answer = ask("Type yes to approve it anyway: ")
        except EOFError:
            answer = ""
        if answer.strip().lower() != "yes":
            print("Not approved.")
            return 1

    approved_at = now.astimezone()
    sequence = current.sequence + 1
    filled = len(result.assignments)
    needed = sum(s.shift.needs for s in result.slots)
    (ld.week_dir / "calendar.ics").write_bytes(render_ics(ld.data, ld.settings, result, approved_at, sequence))
    write_marker(ld.week_dir, approved_at, sequence, filled, needed)    # last: approval is complete
    (ld.week_dir / "review.html").write_text(_page(ld, result, findings, now, edited=True), encoding="utf-8")

    print(f"APPROVED: week of {week} ({filled} of {needed} spots filled).")
    print(f"Calendar file: {ld.week_dir / 'calendar.ics'}")
    print(f"Review page: {ld.week_dir / 'review.html'}")
    print(IMPORT_STEPS)
    return 0
