"""`check-input`: show what the tool understood from signups.xlsx."""

from typing import List

from .signups import CLEAN, NEEDS_READING, SignupData, Volunteer


def _fit(text: str, width: int) -> str:
    text = str(text)
    return text if len(text) <= width else text[: width - 1] + "…"


def _cell(v: Volunteer, shift_id: str) -> str:
    if v.available.status == NEEDS_READING:
        return "?"
    if v.available.status != CLEAN or shift_id not in v.available.shift_ids:
        return ""
    if v.preferred.status == CLEAN and shift_id in v.preferred.shift_ids:
        return "♥"
    return "✓"


def format_report(data: SignupData) -> str:
    out: List[str] = []
    add = out.append
    vols = data.volunteers
    count = lambda status: sum(1 for v in vols if v.status == status)  # noqa: E731

    add(f"Read {data.path.name}: {data.response_rows} responses from {len(vols)} volunteers"
        + (f" ({len(data.replaced)} older duplicate response{'s' if len(data.replaced) != 1 else ''} replaced)"
           if data.replaced else "") + ".")
    add("")

    add("SHIFTS")
    add(f"  {'ID':<9} {'Shift':<34} {'Needs':>5}  Experienced person?")
    for s in data.shifts:
        add(f"  {s.id:<9} {_fit(s.name, 34):<34} {s.needs:>5}  {'yes' if s.needs_experienced else 'no'}")
    add("")

    ids = [s.id for s in data.shifts]
    add("VOLUNTEERS   ✓ available   ♥ available and preferred   ? free text, needs reading")
    add(f"  {'Row':>3}  {'Name':<20} {'Max':>3}  {'Exp':<3}  " + " ".join(f"{i:<8}" for i in ids) + "  Status")
    for v in vols:
        limit = "" if v.max_per_week is None else str(v.max_per_week)
        cells = " ".join(f"{_cell(v, i):^8}" for i in ids)
        add(f"  {v.row:>3}  {_fit(v.name, 20):<20} {limit:>3}  {'yes' if v.experienced else 'no':<3}  {cells}  {v.status}")
    add("")

    add(f"SUMMARY: {count('ready')} ready, {count('needs reading')} need reading, "
        f"{count('problem')} with problems, {count('no availability')} with no availability given.")
    add("")

    needs = [v for v in vols if v.status == "needs reading"]
    if needs:
        add(f"NEEDS READING ({len(needs)}). Not scheduled until the coordinator confirms a reading (Phase 2):")
        for v in needs:
            add(f'  Row {v.row:>3}  {v.name}: "{v.available.raw}"')
        add("")

    free_prefs = [v for v in vols if v.preferred.status == NEEDS_READING]
    if free_prefs:
        add(f"PREFERENCES IN FREE TEXT ({len(free_prefs)}). These don't block scheduling:")
        for v in free_prefs:
            add(f'  Row {v.row:>3}  {v.name}: "{v.preferred.raw}"')
        add("")

    problems = [v for v in vols if v.problems]
    if problems:
        add(f"PROBLEMS ({len(problems)}). These people can't be scheduled until the spreadsheet is fixed:")
        for v in problems:
            for p in v.problems:
                add(f"  Row {v.row:>3}  {v.name}: {p}")
        add("")

    if data.replaced:
        add("DUPLICATES. Older responses replaced by the same person's newer one:")
        for r in data.replaced:
            add(f"  Row {r.old_row:>3} replaced by row {r.new_row}  ({r.email})")
        add("")

    noted = [(v, n) for v in vols for n in v.notes]
    if noted or data.warnings:
        add("NOTES")
        for w in data.warnings:
            add(f"  {w}")
        for v, n in noted:
            add(f"  Row {v.row:>3}  {v.name}: {n}")
        add("")

    add("COVERAGE FROM READY VOLUNTEERS ONLY (before free text is read)")
    ready = [v for v in vols if v.status == "ready" and (v.max_per_week or 0) > 0]
    for s in data.shifts:
        can = [v for v in ready if s.id in v.available.shift_ids]
        exp = sum(1 for v in can if v.experienced)
        flag = ""
        if len(can) < s.needs:
            flag = "  <- fewer people than needed"
        elif s.needs_experienced and exp == 0:
            flag = "  <- no experienced person"
        add(f"  {s.id:<9} needs {s.needs}: {len(can)} available ({exp} experienced){flag}")
    return "\n".join(out)
