"""Reading the Shifts sheet into Shift objects with short IDs like SAT-0900."""

import re
from dataclasses import dataclass
from datetime import time
from typing import List, Optional, Tuple

from .errors import InputError
from .text import is_blank, norm
from .workbook import find_columns, get_sheet

SHEET = "Shifts"
COLUMNS = {
    "name": "Shift",
    "day": "Day",
    "time": "Time",
    "needs": "People needed",
    "experienced": "Needs at least one experienced volunteer?",
}

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_DAY_LOOKUP = {**{d.lower(): d for d in DAYS}, **{d[:3].lower(): d for d in DAYS}}

YES = {"yes", "y", "true"}
NO = {"no", "n", "false"}

_TIME_RANGE = re.compile(
    r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\s*(?:-|to)\s*"
    r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)$"
)


@dataclass(frozen=True)
class Shift:
    id: str              # e.g. "SAT-0900": day + start time, unique
    name: str            # exactly as written in the Shifts sheet (and on the form)
    day: str             # "Saturday"
    start: time
    end: time
    needs: int
    needs_experienced: bool
    row: int             # row in the Shifts sheet, for messages

    @property
    def weekday(self) -> int:
        return DAYS.index(self.day)


def _to_24h(hour: int, minute: int, meridiem: str) -> Optional[time]:
    if not 1 <= hour <= 12 or not 0 <= minute <= 59:
        return None
    if meridiem.startswith("a"):
        hour = 0 if hour == 12 else hour
    else:
        hour = 12 if hour == 12 else hour + 12
    return time(hour, minute)


def parse_time_range(value) -> Optional[Tuple[time, time]]:
    """'9:00 AM – 12:00 PM' -> (09:00, 12:00). Returns None if unreadable."""
    m = _TIME_RANGE.match(norm(value))
    if not m:
        return None
    h1, m1, ap1, h2, m2, ap2 = m.groups()
    end = _to_24h(int(h2), int(m2 or 0), ap2)
    if end is None:
        return None
    if ap1:
        start = _to_24h(int(h1), int(m1 or 0), ap1)
    else:
        # "3-5pm" means 3pm; "9-12pm" means 9am. Use the end's am/pm unless that
        # would put the start after the end.
        start = _to_24h(int(h1), int(m1 or 0), ap2)
        if start is not None and start >= end:
            start = _to_24h(int(h1), int(m1 or 0), "pm" if ap2.startswith("a") else "am")
    if start is None or start >= end:
        return None
    return start, end


def read_shifts(wb) -> List[Shift]:
    ws = get_sheet(wb, SHEET)
    cols = find_columns(ws, SHEET, COLUMNS)

    shifts: List[Shift] = []
    errors: List[str] = []
    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        cell = lambda key: row[cols[key]] if cols[key] < len(row) else None  # noqa: E731
        details = {k: cell(k) for k in ("day", "time", "needs", "experienced")}
        if all(is_blank(v) for v in details.values()):
            continue  # blank row or a note written in the Shift column only
        name = cell("name")
        missing = [COLUMNS[k] for k in ("name", "day", "time", "needs", "experienced") if is_blank(cell(k))]
        if missing:
            errors.append(f"Row {row_num}: missing {', '.join(missing)}.")
            continue

        name = str(name).strip()
        row_errors = []
        if "," in name:
            row_errors.append(
                f'shift name "{name}" contains a comma. The form joins answers with commas, '
                f"so shift names can't contain one."
            )
        day = _DAY_LOOKUP.get(norm(details["day"]))
        if day is None:
            row_errors.append(f'Day "{details["day"]}" isn\'t a day of the week.')
        times = parse_time_range(details["time"])
        if times is None:
            row_errors.append(
                f'Time "{details["time"]}" isn\'t readable. Write it like "9:00 AM – 12:00 PM", '
                f"with the end after the start."
            )
        needs = details["needs"]
        if isinstance(needs, float) and needs.is_integer():
            needs = int(needs)
        if isinstance(needs, str) and needs.strip().isdigit():
            needs = int(needs.strip())
        if not isinstance(needs, int) or isinstance(needs, bool) or needs < 1:
            row_errors.append(f'People needed "{details["needs"]}" must be a whole number, 1 or more.')
        exp = norm(details["experienced"])
        if exp not in YES | NO:
            row_errors.append(f'"Needs at least one experienced volunteer?" is "{details["experienced"]}"; use Yes or No.')

        if row_errors:
            errors.extend(f"Row {row_num} ({name}): {e}" for e in row_errors)
            continue
        start, end = times
        shifts.append(Shift(
            id=f"{day[:3].upper()}-{start:%H%M}",
            name=name, day=day, start=start, end=end,
            needs=needs, needs_experienced=exp in YES, row=row_num,
        ))

    seen_ids, seen_names = {}, {}
    for s in shifts:
        if s.id in seen_ids:
            errors.append(
                f"Rows {seen_ids[s.id]} and {s.row} are both {s.day} shifts starting at "
                f"{s.start:%-I:%M %p}. Each shift needs a different day or start time."
            )
        seen_ids.setdefault(s.id, s.row)
        if norm(s.name) in seen_names:
            errors.append(f'Rows {seen_names[norm(s.name)]} and {s.row} have the same shift name "{s.name}".')
        seen_names.setdefault(norm(s.name), s.row)

    if not shifts and not errors:
        errors.append("No shifts found. Add one row per shift under the headings.")
    if errors:
        raise InputError(
            f'Problems in the "{SHEET}" sheet:\n' + "\n".join(f"  - {e}" for e in errors)
        )
    return sorted(shifts, key=lambda s: (s.weekday, s.start))
