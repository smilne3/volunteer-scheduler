"""Plain-English reasons for gaps: why a shift is short, or has no experienced person."""

from dataclasses import dataclass
from typing import List

from .settings import Settings
from .signups import SignupData, Volunteer
from .solver import Draft, is_experienced
from .week import Slot, clash


@dataclass(frozen=True)
class Gap:
    slot: Slot
    kind: str        # "short" or "no_experienced"
    text: str


def _when(slot: Slot) -> str:
    return f"{slot.date:%b} {slot.date.day}"


def _why_not(v: Volunteer, slot: Slot, draft: Draft, settings: Settings, by_id) -> str:
    """Why an available person isn't on this slot."""
    mine = [a for a in draft.assignments if a.email == v.email]
    for a in mine:
        other = Slot(by_id[a.shift_id], a.date)
        if other.shift.id != slot.shift.id and clash(slot, other, settings.allow_back_to_back_shifts):
            if other.shift.start < slot.shift.end and slot.shift.start < other.shift.end:
                return f"{v.name} is on {a.shift_id}, which overlaps"
            return f"{v.name} is on {a.shift_id} right before or after it, and back-to-back shifts are off"
    if len(mine) >= (v.max_per_week or 0):
        n = v.max_per_week
        return f"{v.name} is at their weekly limit ({n} shift{'s' if n != 1 else ''})"
    return f"{v.name} could take it but wasn't used. This shouldn't happen, so please report it"


def _also_mentioned(slot: Slot, data: SignupData, wanted) -> List[str]:
    """People who aren't available here but came close: date exceptions, unconfirmed, problems."""
    out = []
    for v in data.volunteers:
        if not wanted(v):
            continue
        sid, d = slot.shift.id, slot.date
        if v.status == "ready" and sid in v.reading.shift_ids and not v.reading.allows(sid, d):
            out.append(f"{v.name} can't do {_when(slot)}")
        elif v.status == "needs reading" and v.suggested is not None and v.suggested.allows(sid, d):
            out.append(f"{v.name}'s answer may include it but isn't confirmed yet")
        elif v.status == "problem" and sid in v.available.shift_ids:
            out.append(f"{v.name}'s sign-up has a problem (see check-input)")
        elif v.status == "ready" and v.reading.allows(sid, d) and (v.max_per_week or 0) == 0:
            out.append(f"{v.name} said 0 shifts a week")
    return out


def _sentence(parts: List[str]) -> str:
    return " ".join(p + "." for p in parts)


def explain_gaps(data: SignupData, settings: Settings, draft: Draft) -> List[Gap]:
    by_id = {s.id: s for s in data.shifts}
    gaps = []
    for slot in draft.slots:
        team = {a.email for a in draft.assignments if a.shift_id == slot.shift.id and a.date == slot.date}
        free = [v for v in draft.candidates if v.reading.allows(slot.shift.id, slot.date) and v.email not in team]

        short = slot.shift.needs - len(team)
        if short > 0:
            available = len(team) + len(free)
            head = (f"{slot.shift.id} ({_when(slot)}) is {short} short: "
                    + ("nobody is available" if available == 0
                       else f"{available} {'person is' if available == 1 else 'people are'} available"))
            parts = [_why_not(v, slot, draft, settings, by_id) for v in free]
            parts += _also_mentioned(slot, data, lambda v: True)
            gaps.append(Gap(slot, "short", _sentence([head] + parts)))

        if slot.shift.needs_experienced and not any(
                is_experienced(v, settings) for v in draft.candidates if v.email in team):
            exp_free = [v for v in free if is_experienced(v, settings)]
            head = f"{slot.shift.id} ({_when(slot)}) has no experienced volunteer"
            if not exp_free:
                head += ": no experienced person is available"
            parts = [_why_not(v, slot, draft, settings, by_id) for v in exp_free]
            parts += _also_mentioned(slot, data, lambda v: is_experienced(v, settings))
            gaps.append(Gap(slot, "no_experienced", _sentence([head] + parts)))
    return gaps
