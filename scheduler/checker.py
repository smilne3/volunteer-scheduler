"""The checker: verifies any list of assignments against every rule.

Deliberately separate from the solver and shares none of its rule code, so a
solver bug can't slip past it (D10). Used on drafts now and on hand-edited
drafts in Phase 6.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List

from .settings import Settings
from .signups import SignupData

BROKEN, UNMET = "broken", "unmet"


@dataclass(frozen=True)
class Finding:
    level: str       # BROKEN = a hard rule is broken; UNMET = a goal isn't met
    code: str
    message: str


def _when(d: date) -> str:
    return f"{d:%a %b} {d.day}"


def check(data: SignupData, settings: Settings, week_start: date, assignments: Iterable) -> List[Finding]:
    findings: List[Finding] = []
    broken = lambda code, msg: findings.append(Finding(BROKEN, code, msg))  # noqa: E731
    unmet = lambda code, msg: findings.append(Finding(UNMET, code, msg))    # noqa: E731

    shifts = {s.id: s for s in data.shifts}
    people = {v.email: v for v in data.volunteers}
    week_end = week_start + timedelta(days=6)
    experienced = lambda v: v.experienced or v.email in settings.extra_experienced_emails  # noqa: E731

    seen = set()
    per_person = defaultdict(list)     # email -> [(date, shift)]
    per_slot = defaultdict(list)       # (date, shift_id) -> [volunteer]
    for a in assignments:
        shift, v = shifts.get(a.shift_id), people.get(a.email)
        if shift is None:
            broken("unknown_shift", f'"{a.shift_id}" isn\'t a shift in the Shifts sheet.')
            continue
        if v is None:
            broken("unknown_person", f"{a.email} isn't a volunteer in the sign-ups.")
            continue
        where = f"{v.name} on {shift.id} ({_when(a.date)})"
        if not week_start <= a.date <= week_end:
            broken("wrong_week", f"{where}: that date isn't in the week of {week_start.isoformat()}.")
            continue
        if a.date.weekday() != shift.weekday:
            broken("wrong_day", f"{where}: {shift.id} is on {shift.day}s, not {a.date:%A}s.")
            continue
        if (a.date, a.shift_id, a.email) in seen:
            broken("duplicate", f"{where} is listed twice.")
            continue
        seen.add((a.date, a.shift_id, a.email))
        if a.date in settings.closed_dates:
            broken("closed_date", f"{where}: {a.date.isoformat()} is a closed date.")
        if v.status != "ready" or v.reading is None:
            broken("not_ready", f"{where}: they can't be scheduled yet ({v.status}).")
        elif not v.reading.allows(shift.id, a.date):
            broken("not_available", f"{where}: they aren't available then.")
        per_person[v.email].append((a.date, shift))
        per_slot[(a.date, shift.id)].append(v)

    for email, items in per_person.items():
        v = people[email]
        limit = v.max_per_week or 0
        if len(items) > limit:
            broken("over_limit", f"{v.name} has {len(items)} shifts but said at most {limit} a week.")
        for i, (d1, s1) in enumerate(items):
            for d2, s2 in items[i + 1:]:
                if d1 != d2:
                    continue
                if s1.start < s2.end and s2.start < s1.end:
                    broken("overlap", f"{v.name} is on {s1.id} and {s2.id} on {_when(d1)}, which overlap.")
                elif (s1.end == s2.start or s2.end == s1.start) and not settings.allow_back_to_back_shifts:
                    broken("back_to_back", f"{v.name} is on {s1.id} and {s2.id} back to back on {_when(d1)}, "
                                           f"and back-to-back shifts are turned off in settings.")

    for s in data.shifts:
        d = week_start + timedelta(days=s.weekday)
        if d in settings.closed_dates:
            continue
        team = per_slot.get((d, s.id), [])
        if len(team) > s.needs:
            broken("overfilled", f"{s.id} ({_when(d)}) has {len(team)} people but needs {s.needs}.")
        elif len(team) < s.needs:
            unmet("unfilled", f"{s.id} ({_when(d)}) has {len(team)} of {s.needs} people.")
        if s.needs_experienced and not any(experienced(v) for v in team):
            unmet("no_experienced", f"{s.id} ({_when(d)}) has no experienced volunteer.")
    return findings
