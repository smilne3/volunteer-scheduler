"""Plain-text view of a draft. Phase 5 replaces this with the one-page review page."""

from typing import List

from .checker import BROKEN, UNMET, Finding
from .settings import Settings
from .signups import SignupData
from .solver import Draft, is_experienced


def format_draft(data: SignupData, settings: Settings, draft: Draft, findings: List[Finding]) -> str:
    people = {v.email: v for v in data.volunteers}
    out = [f"DRAFT, NOT APPROVED: week of Monday {draft.week_start.isoformat()}", ""]

    for slot in draft.slots:
        team = [people[a.email] for a in draft.assignments
                if a.shift_id == slot.shift.id and a.date == slot.date]
        names = ", ".join(v.name + (" ★" if is_experienced(v, settings) else "") for v in team) or "(nobody)"
        out.append(f"  {slot.date:%a %b %d}  {slot.shift.id:<9} {len(team)}/{slot.shift.needs}  {names}")
    for slot in draft.closed:
        out.append(f"  {slot.date:%a %b %d}  {slot.shift.id:<9} CLOSED (closed_dates in settings)")
    out.append("  ★ experienced")
    out.append("")

    broken = [f for f in findings if f.level == BROKEN]
    unmet = [f for f in findings if f.level == UNMET]
    if broken:
        out.append(f"RULES BROKEN ({len(broken)}). This draft must not be used:")
        out.extend(f"  - {f.message}" for f in broken)
    else:
        out.append("CHECK: no rules broken.")
    if unmet:
        out.append(f"NEEDS ATTENTION ({len(unmet)}):")
        out.extend(f"  - {f.message}" for f in unmet)
    out.append("")

    scheduled = {a.email for a in draft.assignments}
    out.append(f"{len(scheduled)} of {len(draft.candidates)} ready volunteers are scheduled this week.")
    if draft.left_out:
        out.append(f"{len(draft.left_out)} people weren't considered because their sign-up needs attention. "
                   f"Run check-input for details.")
    out.extend(settings.notes)
    return "\n".join(out)
