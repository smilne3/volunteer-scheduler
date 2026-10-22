"""Plain-text view of a draft. Phase 5 adds the one-page review page."""

from collections import Counter
from typing import List

from .checker import BROKEN, UNMET, Finding
from .reasons import explain_gaps
from .settings import Settings
from .signups import SignupData
from .solver import Draft, is_experienced


def format_draft(data: SignupData, settings: Settings, draft: Draft, findings: List[Finding],
                 status: str = "draft", edited: bool = False) -> str:
    people = {v.email: v for v in data.volunteers}
    label = {"draft": "DRAFT, NOT APPROVED", "approved": "APPROVED",
             "changed since approval": "CHANGED SINCE APPROVAL, approve again"}[status]
    out = [f"{label}: week of Monday {draft.week_start.isoformat()}"
           + (" (from your edited assignments.csv)" if edited else ""), ""]

    for slot in draft.slots:
        team = [people[a.email] for a in draft.assignments
                if a.shift_id == slot.shift.id and a.date == slot.date]
        names = ", ".join(
            v.name + (" ★" if is_experienced(v, settings) else "") + (" ♥" if slot.shift.id in v.preferred_ids else "")
            for v in team) or "(nobody)"
        out.append(f"  {slot.date:%a %b %d}  {slot.shift.id:<9} {len(team)}/{slot.shift.needs}  {names}")
    for slot in draft.closed:
        out.append(f"  {slot.date:%a %b %d}  {slot.shift.id:<9} CLOSED (closed_dates in settings)")
    out.append("  ★ experienced   ♥ a shift they preferred")
    out.append("")

    broken = [f for f in findings if f.level == BROKEN]
    if broken:
        out.append(f"RULES BROKEN ({len(broken)}). This draft must not be used:")
        out.extend(f"  - {f.message}" for f in broken)
    else:
        out.append("CHECK: no rules broken.")
    gaps = explain_gaps(data, settings, draft, edited=edited)
    unmet = [f for f in findings if f.level == UNMET]
    if gaps or unmet:
        out.append(f"NEEDS ATTENTION ({max(len(gaps), len(unmet))}):")
        out.extend(f"  - {g.text}" for g in gaps)
        if len(gaps) != len(unmet):           # shouldn't happen; show the checker's view too
            out.extend(f"  - {f.message}" for f in unmet)
    out.append("")

    counts = Counter(a.email for a in draft.assignments)
    out.append(f"FAIRNESS: {len(counts)} of {len(draft.candidates)} ready volunteers are scheduled this week.")
    multi = [(people[e].name, n) for e, n in counts.items() if n > 1]
    if multi:
        out.append("  More than one shift: " + ", ".join(f"{name} ({n})" for name, n in sorted(multi)))
    waiting = [v.name for v in draft.candidates if v.email not in counts]
    if waiting:
        out.append(f"  Available but not scheduled ({len(waiting)}): " + ", ".join(waiting))

    with_prefs = [people[e] for e in counts if people[e].preferred_ids]
    got = [v for v in with_prefs
           if any(a.shift_id in v.preferred_ids for a in draft.assignments if a.email == v.email)]
    if with_prefs:
        out.append(f"PREFERENCES: {len(got)} of {len(with_prefs)} scheduled people with a preference "
                   f"got a shift they preferred.")
    out.append("")
    if draft.left_out:
        out.append(f"{len(draft.left_out)} people weren't considered because their sign-up needs attention. "
                   f"Run check-input for details.")
    out.extend(settings.notes)
    return "\n".join(out)
