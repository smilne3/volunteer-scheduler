"""Reading form responses into Volunteer objects.

Checkbox answers that exactly match shift names become shift IDs. Anything else is
kept as free text marked "needs reading", and never trusted automatically (D7).
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional

from .errors import InputError
from .shifts import Shift, read_shifts
from .text import is_blank, norm
from .workbook import find_columns, get_sheet, open_workbook

SHEET = "Form Responses 1"
COLUMNS = {
    "timestamp": "Timestamp",
    "name": "Full name",
    "email": "Email address",
    "available": "Which shifts are you available for?",
    "preferred": "Which shifts would you prefer?",
    "max_per_week": "What is the most shifts you'd like per week?",
    "experienced": "Have you volunteered with us before?",
}
OPTIONAL_COLUMNS = {"phone": "Phone number"}

BLANK, CLEAN, NEEDS_READING = "blank", "clean", "needs reading"

# Text that looks like a form shift option: starts with a day, ends with a time range.
_LOOKS_LIKE_SHIFT = re.compile(
    r"^(mon|tue|wed|thu|fri|sat|sun)[a-z]*\b.*\d{1,2}(:\d{2})?\s*(am|pm)?-\d{1,2}(:\d{2})?\s*(am|pm)$"
)
_TIMESTAMP_FORMATS = ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S")


@dataclass(frozen=True)
class Answer:
    """One answer to a "which shifts" question."""
    raw: str                         # the original text, "" if blank
    status: str                      # BLANK, CLEAN or NEEDS_READING
    shift_ids: FrozenSet[str] = frozenset()   # set only when CLEAN


@dataclass
class Volunteer:
    row: int
    timestamp: Optional[datetime]
    name: str
    email: str
    phone: str
    available: Answer
    preferred: Answer
    max_per_week: Optional[int]
    experienced: bool
    problems: List[str] = field(default_factory=list)  # stop this person being scheduled
    notes: List[str] = field(default_factory=list)     # worth knowing, don't block

    @property
    def status(self) -> str:
        if self.problems:
            return "problem"
        if self.available.status == NEEDS_READING:
            return "needs reading"
        if self.available.status == BLANK:
            return "no availability"
        return "ready"


@dataclass
class Replaced:
    email: str
    old_row: int
    new_row: int


@dataclass
class SignupData:
    path: Path
    shifts: List[Shift]
    volunteers: List[Volunteer]       # one per person, newest response
    replaced: List[Replaced]          # older responses that were dropped
    warnings: List[str]
    response_rows: int                # non-blank response rows read


def parse_answer(value, shift_ids_by_name: Dict[str, str]):
    """Returns (Answer, shift-like parts that matched no shift name)."""
    if is_blank(value):
        return Answer("", BLANK), []
    raw = str(value).strip()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    ids = [shift_ids_by_name.get(norm(p)) for p in parts]
    if parts and all(ids):
        return Answer(raw, CLEAN, frozenset(ids)), []
    unknown = [p for p, i in zip(parts, ids) if i is None and _LOOKS_LIKE_SHIFT.match(norm(p))]
    return Answer(raw, NEEDS_READING), unknown


def _parse_limit(value, v: Volunteer):
    if is_blank(value):
        v.problems.append("No answer for the most shifts per week.")
        return None
    n = value
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    if isinstance(n, str) and n.strip().isdigit():
        n = int(n.strip())
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        v.problems.append(f'Most shifts per week is "{value}", which isn\'t a whole number.')
        return None
    if n == 0:
        v.notes.append("Said 0 shifts per week, so won't be scheduled.")
    return n


def _parse_timestamp(value, v: Volunteer):
    if isinstance(value, datetime):
        return value
    if not is_blank(value):
        for fmt in _TIMESTAMP_FORMATS:
            try:
                return datetime.strptime(str(value).strip(), fmt)
            except ValueError:
                pass
    v.notes.append("Timestamp is missing or unreadable.")
    return None


def read_signups(path: Path) -> SignupData:
    wb = open_workbook(path)
    try:
        shifts = read_shifts(wb)
        ws = get_sheet(wb, SHEET)
        cols = find_columns(ws, SHEET, COLUMNS, OPTIONAL_COLUMNS)
        rows = list(ws.iter_rows(min_row=2, values_only=True))
    finally:
        wb.close()

    by_name = {norm(s.name): s.id for s in shifts}
    unknown_labels = defaultdict(set)   # shift-like text -> rows it appeared in
    volunteers: List[Volunteer] = []
    for row_num, row in enumerate(rows, start=2):
        cell = lambda key: row[cols[key]] if key in cols and cols[key] < len(row) else None  # noqa: E731
        if all(is_blank(cell(k)) for k in COLUMNS):
            continue

        available, unknown_a = parse_answer(cell("available"), by_name)
        preferred, unknown_p = parse_answer(cell("preferred"), by_name)
        for label in unknown_a + unknown_p:
            unknown_labels[label].add(row_num)

        email = "" if is_blank(cell("email")) else str(cell("email")).strip().lower()
        name = "" if is_blank(cell("name")) else " ".join(str(cell("name")).split())
        v = Volunteer(
            row=row_num, timestamp=None, name=name or email or f"(row {row_num})",
            email=email,
            phone="" if is_blank(cell("phone")) else str(cell("phone")).strip(),
            available=available, preferred=preferred,
            max_per_week=None, experienced=False,
        )
        v.timestamp = _parse_timestamp(cell("timestamp"), v)
        v.max_per_week = _parse_limit(cell("max_per_week"), v)
        if "@" not in email:
            v.problems.append("No usable email address, so this response can't be matched to a person.")
        if not name:
            v.notes.append("No name given.")
        exp = norm(cell("experienced"))
        if exp in ("yes", "y"):
            v.experienced = True
        elif exp not in ("no", "n"):
            v.notes.append(f'"Volunteered before?" answer is "{cell("experienced") or ""}", so counted as not experienced.')
        if available.status == BLANK:
            v.notes.append("Didn't say which shifts they can do.")
        if available.status == CLEAN and preferred.status == CLEAN:
            extra = sorted(preferred.shift_ids - available.shift_ids)
            if extra:
                v.notes.append(f"Prefers {', '.join(extra)} but didn't mark it as available, so that preference is ignored.")
        volunteers.append(v)

    # Shift names that several people picked must be real form options missing
    # from the Shifts sheet. That would silently drop a whole shift, so stop.
    missing_options = {label: rows_ for label, rows_ in unknown_labels.items() if len(rows_) >= 2}
    if missing_options:
        listed = "\n".join(
            f'  - "{label}" (rows {", ".join(map(str, sorted(r)))})' for label, r in sorted(missing_options.items())
        )
        known = "\n".join(f'  - "{s.name}"' for s in shifts)
        raise InputError(
            f"These shift names appear in several form answers but aren't in the Shifts sheet:\n{listed}\n"
            f"Shifts sheet has:\n{known}\n"
            f"Add the missing shift to the Shifts sheet, or fix its name so it matches the form exactly."
        )
    warnings = []
    for label, rows_ in sorted(unknown_labels.items()):
        r = next(iter(rows_))
        warnings.append(
            f'Row {r} mentions "{label}", which looks like a shift but isn\'t in the Shifts sheet. '
            f"Treated as free text."
        )

    # Same email more than once: keep the newest response.
    groups = defaultdict(list)
    for v in volunteers:
        groups[v.email if "@" in v.email else f"row:{v.row}"].append(v)
    kept, replaced = [], []
    for group in groups.values():
        if len(group) == 1:
            kept.append(group[0])
            continue
        if all(v.timestamp for v in group):
            newest = max(group, key=lambda v: (v.timestamp, v.row))
        else:
            newest = max(group, key=lambda v: v.row)
            newest.notes.append("Duplicate responses without timestamps; kept the lowest one in the sheet.")
        kept.append(newest)
        replaced.extend(Replaced(newest.email, v.row, newest.row) for v in group if v is not newest)

    kept.sort(key=lambda v: v.row)
    replaced.sort(key=lambda r: r.old_row)
    return SignupData(Path(path), shifts, kept, replaced, warnings, len(volunteers))
