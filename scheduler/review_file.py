"""availability_review.csv: where the coordinator confirms free-text availability (D7).

One row per free-text answer. The tool fills in a suggested reading. The coordinator
copies it, or writes their own, into confirmed_reading. Blank = not confirmed, and
that person isn't scheduled.

Rows are matched by email plus the answer's letters and digits, not by timestamp.
Excel often rewrites dates and dashes when it saves a CSV. A new response with the
same answer keeps its confirmation. A different answer needs a new one.
"""

import csv
import io
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .errors import InputError
from .readings import ReadingError, parse_reading
from .signups import CLEAN, NEEDS_READING, SignupData, Volunteer
from .suggest import Suggestion, suggest
from .text import norm

FILE_NAME = "availability_review.csv"
COLUMNS = ["name", "email", "response_time", "answer", "suggested_reading", "notes",
           "confirmed_reading", "status"]
REQUIRED = ("email", "answer", "confirmed_reading")
TO_REVIEW, CONFIRMED = "to review", "confirmed"


@dataclass
class ReviewItem:
    volunteer: Volunteer
    suggestion: Suggestion
    confirmed_text: str
    status: str                 # TO_REVIEW, CONFIRMED, or "error: ..."
    is_new: bool


@dataclass
class ReviewResult:
    path: Path
    items: List[ReviewItem] = field(default_factory=list)
    no_longer_apply: List[Dict[str, str]] = field(default_factory=list)   # old confirmed rows
    preference_suggestions: Dict[int, Suggestion] = field(default_factory=dict)  # by sheet row
    written: bool = False
    warning: str = ""

    def count(self, status_prefix: str) -> int:
        return sum(1 for i in self.items if i.status.startswith(status_prefix))


def review_key(email: str, answer: str) -> str:
    return f"{(email or '').strip().lower()}|{re.sub(r'[^a-z0-9]', '', norm(answer))}"


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "mac_roman"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def read_review_file(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    text = _decode(path.read_bytes())
    reader = csv.DictReader(io.StringIO(text))
    headers = [norm(h).replace(" ", "_") for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        raise InputError(
            f"{path.name} is missing the column(s): {', '.join(missing)}. Restore the heading, or "
            f"delete the file to start over (that loses any confirmed readings in it)."
        )
    rows: Dict[str, Dict[str, str]] = {}
    for raw_row in reader:
        row = {norm(k).replace(" ", "_"): (v or "").strip() for k, v in raw_row.items() if k}
        key = review_key(row.get("email", ""), row.get("answer", ""))
        # If the same answer appears twice, a row with a confirmation wins.
        if key not in rows or (row.get("confirmed_reading") and not rows[key].get("confirmed_reading")):
            rows[key] = row
    return rows


def _render(rows: List[List[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")   # BOM so Excel opens it as UTF-8


def _write_atomic(path: Path, content: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".review-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.replace(tmp, path)
    except OSError as e:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise InputError(f"Couldn't save {path.name}: {e.strerror or e}.")


def apply_reviews(data: SignupData, today: date, path: Optional[Path] = None) -> ReviewResult:
    """Suggest readings, apply confirmed ones to volunteers, resolve preferences, update the file."""
    path = Path(path) if path else data.path.parent / FILE_NAME
    existing = read_review_file(path)
    result = ReviewResult(path)
    shifts = data.shifts

    out_rows = []
    for v in data.volunteers:
        if v.available.status != NEEDS_READING:
            continue
        as_of = v.timestamp.date() if v.timestamp else today
        suggestion = suggest(v.available.raw, shifts, as_of=as_of, today=today)
        old = existing.pop(review_key(v.email, v.available.raw), None)
        confirmed_text = (old or {}).get("confirmed_reading", "")
        status = TO_REVIEW
        v.reading, v.reading_source = None, ""
        if confirmed_text:
            try:
                v.reading = parse_reading(confirmed_text, shifts)
                v.reading_source = "confirmed"
                status = CONFIRMED
            except ReadingError as e:
                status = f"error: {e}"
        result.items.append(ReviewItem(v, suggestion, confirmed_text, status, is_new=old is None))
        out_rows.append([
            v.name, v.email, v.timestamp.strftime("%Y-%m-%d %H:%M:%S") if v.timestamp else "",
            v.available.raw, suggestion.reading.format(shifts), " | ".join(suggestion.notes),
            confirmed_text, status,
        ])

    result.no_longer_apply = [row for row in existing.values() if row.get("confirmed_reading")]

    # Preferences: free text is read automatically. A misread preference can't
    # break a rule, and preferences are always limited to confirmed availability.
    for v in data.volunteers:
        if v.reading is None:
            v.preferred_ids, v.preferred_source = frozenset(), ""
            continue
        if v.preferred.status == CLEAN:
            v.preferred_ids = v.preferred.shift_ids & v.reading.shift_ids
            v.preferred_source = "form"
        elif v.preferred.status == NEEDS_READING:
            as_of = v.timestamp.date() if v.timestamp else today
            s = suggest(v.preferred.raw, shifts, as_of=as_of, today=today, for_preferences=True)
            result.preference_suggestions[v.row] = s
            v.preferred_ids = s.reading.shift_ids & v.reading.shift_ids
            v.preferred_source = "suggested"

    if not out_rows and not path.exists():
        return result   # nothing to review; don't create an empty file
    content = _render(out_rows)
    if path.exists() and path.read_bytes() == content:
        return result
    if path.with_name("~$" + path.name).exists():
        result.warning = (f"{path.name} looks open in Excel, so it wasn't updated. Close it and run this "
                          f"again. Confirmed readings in the saved file were still used.")
        return result
    _write_atomic(path, content)
    result.written = True
    return result
