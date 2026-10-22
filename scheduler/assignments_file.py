"""Reading a (possibly hand-edited) weeks/<Monday>/assignments.csv back in."""

import csv
import io
from datetime import date, datetime
from pathlib import Path
from typing import List, Tuple

from .errors import InputError
from .review_file import _decode
from .signups import SignupData
from .solver import Assignment
from .text import is_blank, norm

REQUIRED = ("date", "shift_id", "name", "email")
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y")


def _date(text: str):
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return None


def read_assignments(path: Path, data: SignupData) -> Tuple[List[Assignment], List[str]]:
    """Returns (assignments, problems). Rows with no name and no email are open spots."""
    path = Path(path)
    if not path.exists():
        raise InputError(f"Can't find {path}. Run draft for that week first.")
    reader = csv.DictReader(io.StringIO(_decode(path.read_bytes())))
    headers = [norm(h).replace(" ", "_") for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        raise InputError(f"{path.name} is missing the column(s): {', '.join(missing)}. "
                         f"Restore the heading(s), or draft the week again with --replace.")

    by_email = {v.email: v for v in data.volunteers}
    by_name = {}
    for v in data.volunteers:
        by_name.setdefault(norm(v.name), []).append(v)
    shift_ids = {s.id for s in data.shifts}
    shift_by_name = {norm(s.name): s.id for s in data.shifts}

    assignments, problems = [], []
    for row_num, raw in enumerate(reader, start=2):
        row = {norm(k).replace(" ", "_"): (v or "").strip() for k, v in raw.items() if k}
        name, email = row.get("name", ""), row.get("email", "").lower()
        if is_blank(name) and is_blank(email):
            continue                                   # an open spot
        where = f"Row {row_num} of {path.name}"
        d = _date(row.get("date", ""))
        if d is None:
            problems.append(f'{where}: "{row.get("date", "")}" isn\'t a date like 2026-11-14.')
            continue
        sid = row.get("shift_id", "").upper()
        if not sid and norm(row.get("shift", "")) in shift_by_name:
            sid = shift_by_name[norm(row["shift"])]
        if sid not in shift_ids:
            problems.append(f'{where}: shift_id "{row.get("shift_id", "")}" isn\'t one of {", ".join(sorted(shift_ids))}.')
            continue
        if not email:
            matches = by_name.get(norm(name), [])
            if len(matches) != 1:
                problems.append(
                    f'{where}: no email, and "{name}" ' +
                    ("matches more than one volunteer. Add their email." if matches
                     else "doesn't match a volunteer's name. Add their email or fix the spelling."))
                continue
            email = matches[0].email
        elif email not in by_email:
            problems.append(f'{where}: {email} isn\'t a volunteer in the sign-ups.')
            continue
        assignments.append(Assignment(d, sid, email))
    return assignments, problems
