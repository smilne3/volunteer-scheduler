"""Turning a week (Monday to Sunday) into dated shift slots."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import FrozenSet, List, Optional, Sequence, Tuple

from .errors import InputError
from .shifts import Shift


@dataclass(frozen=True)
class Slot:
    shift: Shift
    date: date

    @property
    def label(self) -> str:
        return f"{self.shift.id} ({self.date:%a %b} {self.date.day})"


def next_monday(today: date) -> date:
    return today + timedelta(days=7 - today.weekday())


def parse_week(text: Optional[str], today: date) -> date:
    """--week must be a Monday. Default: next week."""
    if not text:
        return next_monday(today)
    try:
        d = date.fromisoformat(text)
    except ValueError:
        raise InputError(f'--week "{text}" isn\'t a date. Use the Monday of the week, like 2026-11-09.')
    if d.weekday() != 0:
        monday = d - timedelta(days=d.weekday())
        raise InputError(f"--week {text} is a {d:%A}. Weeks start on Monday: use --week {monday.isoformat()}.")
    return d


def week_slots(shifts: Sequence[Shift], monday: date, closed: FrozenSet[date]) -> Tuple[List[Slot], List[Slot]]:
    """Returns (open slots, slots on closed dates), in date and time order."""
    slots = [Slot(s, monday + timedelta(days=s.weekday)) for s in shifts]
    slots.sort(key=lambda sl: (sl.date, sl.shift.start))
    return [s for s in slots if s.date not in closed], [s for s in slots if s.date in closed]


def clash(a: Slot, b: Slot, allow_back_to_back: bool) -> bool:
    """True if one person can't do both: they overlap, or touch when back-to-back isn't allowed."""
    if a.date != b.date or a is b:
        return False
    if a.shift.start < b.shift.end and b.shift.start < a.shift.end:
        return True
    touching = a.shift.end == b.shift.start or b.shift.end == a.shift.start
    return touching and not allow_back_to_back
