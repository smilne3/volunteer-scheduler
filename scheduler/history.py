"""Shift history from approved weeks, for fairness across weeks (Phase 7).

Only weeks whose APPROVED marker still matches their assignments.csv count. A week
edited after approval is skipped until it's approved again.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Set

from .approval import APPROVED, CHANGED, approval_status
from .assignments_file import read_assignments
from .review_page import WEEKS_DIR
from .signups import SignupData


@dataclass
class History:
    lookback_weeks: int = 0
    weeks_counted: List[date] = field(default_factory=list)    # approved weeks inside the lookback
    skipped: List[str] = field(default_factory=list)           # notes about weeks not counted
    recent: Dict[str, int] = field(default_factory=dict)       # email -> shifts in the lookback
    last_shift: Dict[str, date] = field(default_factory=dict)  # email -> latest approved shift before this week
    worked: Set[str] = field(default_factory=set)              # emails with an approved shift before today

    def weeks_waiting(self, email: str, week: date):
        """Whole weeks since their last approved shift, or None if they've never had one."""
        last = self.last_shift.get(email)
        if last is None:
            return None
        return (week - (last - timedelta(days=last.weekday()))).days // 7


def load_history(base: Path, data: SignupData, week: date, lookback_weeks: int, today: date) -> History:
    history = History(lookback_weeks=lookback_weeks)
    weeks_root = Path(base) / WEEKS_DIR
    if not weeks_root.is_dir():
        return history
    window_start = week - timedelta(weeks=lookback_weeks)
    recent = Counter()
    for folder in sorted(weeks_root.iterdir()):
        try:
            monday = date.fromisoformat(folder.name)
        except ValueError:
            continue
        if monday.weekday() != 0 or monday >= week or not folder.is_dir():
            continue
        status = approval_status(folder).status
        if status == CHANGED:
            history.skipped.append(f"The week of {monday.isoformat()} was changed after approval, so it isn't "
                                   f"counted in fairness until it's approved again.")
            continue
        if status != APPROVED:
            continue
        assignments, _ = read_assignments(folder / "assignments.csv", data)   # unknown people: ignored
        for a in assignments:
            if a.email not in history.last_shift or a.date > history.last_shift[a.email]:
                history.last_shift[a.email] = a.date
            if a.date < today:
                history.worked.add(a.email)
            if monday >= window_start:
                recent[a.email] += 1
        if monday >= window_start:
            history.weeks_counted.append(monday)
    history.recent = dict(recent)
    return history


def apply_experience_from_history(data: SignupData, history: History) -> List[str]:
    """For count_approved_shifts_as_experience: anyone who has worked an approved shift is experienced."""
    promoted = []
    for v in data.volunteers:
        if not v.experienced and v.email in history.worked:
            v.experienced = True
            promoted.append(v.name)
    return promoted
