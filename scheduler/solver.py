"""Drafting a week's schedule with a small optimization model (D10).

Hard rules are constraints, and availability is enforced by construction: a
(person, shift) choice only exists if that person is available on that date.
Goals are met in strict order by solving in stages, each stage locking in the
previous stage's best result:

  1. experienced cover   every shift gets the experienced people it needs (usually 1)
  2. coverage            fill as many slots as possible
  3. fair counts         spread shifts: a k-th shift for one person costs 2k-1, so
                         nobody gets a 2nd shift while someone available has none;
                         then, from approved past weeks, shifts go to people with
                         fewer recent shifts (fairness across weeks)
  4. preferences         as many preferred shifts as possible
  5. tie-break           fixed per-week order, so the same input gives the same draft

Settings can swap 3 and 4 (fair_counts_before_preferences = false).
"""

import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

import pulp

from .settings import Settings
from .signups import SignupData, Volunteer
from .week import Slot, clash, week_slots


@dataclass(frozen=True)
class Assignment:
    date: date
    shift_id: str
    email: str


@dataclass
class Draft:
    week_start: date
    slots: List[Slot]                 # open slots this week
    closed: List[Slot]                # slots on closed dates (not scheduled)
    assignments: List[Assignment]
    candidates: List[Volunteer]       # people who could be scheduled this week
    left_out: List[Volunteer] = field(default_factory=list)   # not ready (see check-input)


def is_experienced(v: Volunteer, settings: Settings) -> bool:
    return v.experienced or v.email in settings.extra_experienced_emails


def _tie_break(week: date, email: str, shift_id: str) -> int:
    digest = hashlib.sha256(f"{week.isoformat()}|{email}|{shift_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 1000 + 1


def _solver():
    """HiGHS runs natively on Intel and Apple-chip Macs. PuLP's bundled CBC is
    Intel-only on macOS (Apple-chip Macs need Rosetta for it), so it's only the
    fallback. gapRel=0: each stage must find the true best, or drafts could differ
    between runs."""
    highs = pulp.HiGHS(msg=False, gapRel=0)
    if highs.available():
        return highs
    return pulp.PULP_CBC_CMD(msg=False)


def _solve(problem: pulp.LpProblem) -> None:
    status = problem.solve(_solver())
    if pulp.LpStatus[status] != "Optimal":
        raise RuntimeError(f"Scheduler couldn't finish (solver status: {pulp.LpStatus[status]}).")


def _people(data: SignupData):
    candidates = [v for v in data.volunteers if v.status == "ready" and (v.max_per_week or 0) > 0]
    left_out = [v for v in data.volunteers if v.status in ("needs reading", "problem")]
    return candidates, left_out


def draft_from(data: SignupData, settings: Settings, week_start: date, assignments) -> Draft:
    """A Draft built from given assignments (e.g. a hand-edited assignments.csv)."""
    slots, closed = week_slots(data.shifts, week_start, settings.closed_dates)
    candidates, left_out = _people(data)
    ordered = sorted(assignments, key=lambda a: (a.date, a.shift_id, a.email))
    return Draft(week_start, slots, closed, ordered, candidates, left_out)


def schedule(data: SignupData, settings: Settings, week_start: date, recent: Optional[Dict[str, int]] = None) -> Draft:
    """recent: email -> approved shifts in the lookback window (from history.load_history)."""
    recent = recent or {}
    slots, closed = week_slots(data.shifts, week_start, settings.closed_dates)
    candidates, left_out = _people(data)

    # Choices only for pairs where the person is available that date (hard rule 1).
    pairs: List[Tuple[Volunteer, Slot]] = [
        (v, s) for v in candidates for s in slots if v.reading.allows(s.shift.id, s.date)
    ]
    problem = pulp.LpProblem("week", pulp.LpMaximize)
    x: Dict[Tuple[str, str], pulp.LpVariable] = {}
    for n, (v, s) in enumerate(pairs):
        x[(v.email, s.shift.id)] = problem.add_variable(f"x{n}", 0, 1, cat="Binary")

    def chosen(email=None, shift_id=None):
        return [var for (e, i), var in x.items()
                if (email is None or e == email) and (shift_id is None or i == shift_id)]

    for v in candidates:                                         # rule 2: weekly limit
        if chosen(email=v.email):
            problem += pulp.lpSum(chosen(email=v.email)) <= v.max_per_week
        for a in slots:                                          # rule 3: no clashes
            for b in slots:
                if a.shift.id < b.shift.id and clash(a, b, settings.allow_back_to_back_shifts):
                    va, vb = x.get((v.email, a.shift.id)), x.get((v.email, b.shift.id))
                    if va is not None and vb is not None:
                        problem += va + vb <= 1
    for s in slots:                                              # rule 4: never overfill
        if chosen(shift_id=s.shift.id):
            problem += pulp.lpSum(chosen(shift_id=s.shift.id)) <= s.shift.needs
    # Rule 5 (closed dates): closed slots have no choices at all.

    experienced = {v.email for v in candidates if is_experienced(v, settings)}
    prefs = {v.email: v.preferred_ids for v in candidates}
    covered = {}      # shift id -> experienced people counted toward its need (capped at the need)
    for n, s in enumerate(slots):
        if s.shift.experienced_needed:
            covered[s.shift.id] = problem.add_variable(f"cover{n}", 0, s.shift.experienced_needed, cat="Integer")
            problem += covered[s.shift.id] <= pulp.lpSum(
                var for (e, i), var in x.items() if i == s.shift.id and e in experienced)

    if not x:
        return Draft(week_start, slots, closed, [], candidates, left_out)

    # Stage 1: experienced cover.
    cover_total = pulp.lpSum(covered.values())
    if covered:
        problem.setObjective(cover_total)
        _solve(problem)
        problem += cover_total >= round(pulp.value(cover_total))
    # Stage 2: coverage.
    filled = pulp.lpSum(x.values())
    problem.setObjective(filled)
    _solve(problem)
    problem += filled >= round(pulp.value(filled))

    # Fair counts: load[p, k] = 1 if p gets at least k shifts. Costs rise with k
    # (1, 3, 5, ...), i.e. the sum of squared shift counts.
    load_cost = []
    for v in candidates:
        mine = chosen(email=v.email)
        if not mine:
            continue
        levels = [problem.add_variable(f"load{len(load_cost)}_{k}", 0, 1, cat="Binary")
                  for k in range(1, min(v.max_per_week, len(mine)) + 1)]
        problem += pulp.lpSum(levels) == pulp.lpSum(mine)
        load_cost.extend((2 * k - 1) * lv for k, lv in enumerate(levels, start=1))
    unfairness = pulp.lpSum(load_cost)
    preferred = pulp.lpSum(var for (e, i), var in x.items() if i in prefs.get(e, ()))

    already_had = pulp.lpSum(recent.get(e, 0) * var for (e, i), var in x.items())

    def stage_fairness():
        problem.setObjective(-unfairness)
        _solve(problem)
        problem.addConstraint(unfairness <= round(pulp.value(unfairness) or 0))
        if any(recent.get(e, 0) for (e, _i) in x):
            problem.setObjective(-already_had)        # across weeks: fewer recent shifts first
            _solve(problem)
            problem.addConstraint(already_had <= round(pulp.value(already_had) or 0))

    def stage_preferences():
        problem.setObjective(preferred)
        _solve(problem)
        problem.addConstraint(preferred >= round(pulp.value(preferred) or 0))

    stages = [stage_fairness, stage_preferences]
    for stage in stages if settings.fair_counts_before_preferences else reversed(stages):
        stage()

    # Stage 5: tie-break, so the result is the same every time for this week.
    problem.setObjective(pulp.lpSum(_tie_break(week_start, e, i) * var for (e, i), var in x.items()))
    _solve(problem)

    slot_date = {s.shift.id: s.date for s in slots}
    assignments = sorted(
        (Assignment(slot_date[i], i, e) for (e, i), var in x.items() if var.value() > 0.5),
        key=lambda a: (a.date, a.shift_id, a.email),
    )
    return Draft(week_start, slots, closed, assignments, candidates, left_out)
