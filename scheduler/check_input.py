"""`check-input`: show what the tool understood from signups.xlsx."""

from typing import List, Optional

from .review_file import CONFIRMED, TO_REVIEW, ReviewResult
from .signups import NEEDS_READING, SignupData, Volunteer


def _fit(text: str, width: int) -> str:
    text = str(text)
    return text if len(text) <= width else text[: width - 1] + "…"


def _cell(v: Volunteer, shift_id: str) -> str:
    if v.reading is None:
        return "?" if v.available.status == NEEDS_READING else ""
    group = v.reading.group_for(shift_id)
    if group is None:
        return ""
    mark = "♥" if shift_id in v.preferred_ids else "✓"
    return mark + ("*" if group.has_date_limits else "")


def format_report(data: SignupData, review: Optional[ReviewResult] = None) -> str:
    out: List[str] = []
    add = out.append
    vols = data.volunteers
    shifts = data.shifts
    count = lambda status: sum(1 for v in vols if v.status == status)  # noqa: E731

    n_replaced = len(data.replaced)
    add(f"Read {data.path.name}: {data.response_rows} responses from {len(vols)} volunteers"
        + (f" ({n_replaced} older duplicate response{'s' if n_replaced != 1 else ''} replaced)"
           if n_replaced else "") + ".")
    if review and review.items:
        n_new = sum(i.is_new for i in review.items)
        add(f"Read {review.path.name}: {review.count(CONFIRMED)} confirmed, "
            f"{review.count(TO_REVIEW)} to review, {review.count('error')} with errors"
            + (f" ({n_new} new row{'s' if n_new != 1 else ''} added)" if n_new else "")
            + ".")
    add("")

    add("SHIFTS")
    add(f"  {'ID':<9} {'Shift':<34} {'Needs':>5}  Experienced person?")
    for s in shifts:
        add(f"  {s.id:<9} {_fit(s.name, 34):<34} {s.needs:>5}  {'no' if not s.experienced_needed else 'yes' if s.experienced_needed == 1 else s.experienced_needed}")
    add("")

    ids = [s.id for s in shifts]
    add("VOLUNTEERS   ✓ available   ♥ preferred   * with date limits   ? free text, not confirmed yet")
    add(f"  {'Row':>3}  {'Name':<20} {'Max':>3}  {'Exp':<3}  " + " ".join(f"{i:<8}" for i in ids) + "  Status")
    for v in vols:
        limit = "" if v.max_per_week is None else str(v.max_per_week)
        cells = " ".join(f"{_cell(v, i):^8}" for i in ids)
        status = v.status + (" (confirmed reading)" if v.reading_source == "confirmed" else "")
        add(f"  {v.row:>3}  {_fit(v.name, 20):<20} {limit:>3}  {'yes' if v.experienced else 'no':<3}  {cells}  {status}")
    add("")

    add(f"SUMMARY: {count('ready')} ready, {count('needs reading')} need reading, "
        f"{count('problem')} with problems, {count('no availability')} with no availability given"
        + (f", {count('no shifts')} confirmed as no shifts" if count("no shifts") else "") + ".")
    add("")

    if review:
        pending = [i for i in review.items if i.status != CONFIRMED]
        if pending:
            add(f"NEEDS READING ({len(pending)}). Not scheduled until a reading is confirmed:")
            for item in pending:
                v = item.volunteer
                add(f'  Row {v.row:>3}  {v.name}: "{v.available.raw}"')
                add(f"            suggested: {item.suggestion.reading.format(shifts)}")
                for n in item.suggestion.notes:
                    add(f"            note: {n}")
                if item.status.startswith("error"):
                    add(f'            YOUR CONFIRMED READING "{item.confirmed_text}" HAS AN ERROR: {item.status[7:]}')
            add(f"  To confirm: open {review.path.name}, copy the suggested reading (or write your own) into")
            add("  the confirmed_reading column, save it as CSV, and run check-input again.")
            add("")
        confirmed = [i for i in review.items if i.status == CONFIRMED]
        if confirmed:
            add(f"CONFIRMED READINGS ({len(confirmed)})")
            for item in confirmed:
                v = item.volunteer
                add(f'  Row {v.row:>3}  {v.name}: "{v.available.raw}"  ->  {v.reading.format(shifts)}')
            add("")
        if review.no_longer_apply:
            add(f"CONFIRMATIONS THAT NO LONGER APPLY ({len(review.no_longer_apply)}). "
                "The person's answer changed or they're no longer in the sheet:")
            for row in review.no_longer_apply:
                add(f'  {row.get("name") or row.get("email")}: "{row.get("answer", "")}" was confirmed as '
                    f'"{row.get("confirmed_reading")}"')
            add("")

        free_prefs = [v for v in vols if v.preferred.status == NEEDS_READING]
        if free_prefs:
            add(f"PREFERENCES IN FREE TEXT ({len(free_prefs)}). Read automatically, limited to their availability:")
            for v in free_prefs:
                if v.reading is None:
                    read_as = "(used once their availability is confirmed)"
                else:
                    read_as = ", ".join(i for i in ids if i in v.preferred_ids) or "none of their shifts"
                add(f'  Row {v.row:>3}  {v.name}: "{v.preferred.raw}"  ->  {read_as}')
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
    warnings = list(data.warnings) + ([review.warning] if review and review.warning else [])
    if noted or warnings:
        add("NOTES")
        for w in warnings:
            add(f"  {w}")
        for v, n in noted:
            add(f"  Row {v.row:>3}  {v.name}: {n}")
        add("")

    add("COVERAGE FROM READY VOLUNTEERS (every week; date limits not counted)")
    ready = [v for v in vols if v.status == "ready" and (v.max_per_week or 0) > 0]
    for s in shifts:
        can = [v for v in ready if s.id in v.reading.shift_ids]
        exp = sum(1 for v in can if v.experienced)
        flag = ""
        if len(can) < s.needs:
            flag = "  <- fewer people than needed"
        elif exp < s.experienced_needed:
            flag = "  <- no experienced person" if exp == 0 else f"  <- fewer than {s.experienced_needed} experienced"
        add(f"  {s.id:<9} needs {s.needs}: {len(can)} available ({exp} experienced){flag}")
    return "\n".join(out)
