"""The one-page review page (review.html) and the editable assignments.csv for a week.

Everything shown comes from volunteers' form answers, so all text is HTML-escaped.
"""

import csv
import io
from collections import Counter
from datetime import datetime, time
from html import escape
from pathlib import Path
from typing import List, Optional

from .approval import APPROVED, CHANGED, DRAFT, Approval
from .checker import BROKEN, Finding
from .errors import InputError
from .reasons import Gap
from .review_file import CONFIRMED, ReviewResult
from .settings import Settings
from .signups import SignupData
from .solver import Draft, is_experienced

WEEKS_DIR = "weeks"
ASSIGNMENT_COLUMNS = ["date", "day", "shift_id", "shift", "name", "email"]


def _clock(t: time) -> str:
    return t.strftime("%-I:%M").replace(":00", "")


def time_range(start: time, end: time) -> str:
    s_ampm, e_ampm = start.strftime("%p").lower(), end.strftime("%p").lower()
    if s_ampm == e_ampm:
        return f"{_clock(start)}–{_clock(end)} {e_ampm}"
    return f"{_clock(start)} {s_ampm}–{_clock(end)} {e_ampm}"


def waited(history, email: str, week) -> str:
    """' (last shift 2 weeks ago)' for the fairness lines; '' when there's no history yet."""
    if not history or not history.last_shift:
        return ""
    n = history.weeks_waiting(email, week)
    if n is None:
        return " (no approved shifts yet)"
    return " (last shift last week)" if n == 1 else f" (last shift {n} weeks ago)"


def history_line(history) -> str:
    if not history or not history.lookback_weeks:
        return "Fairness across weeks is off (fairness_lookback_weeks is 0)."
    if not history.weeks_counted:
        return (f"No approved weeks in the last {history.lookback_weeks} weeks yet, so shifts are spread "
                f"within this week only.")
    weeks = ", ".join(f"{d:%b} {d.day}" for d in history.weeks_counted)
    return (f"After spreading this week's shifts evenly, people with fewer shifts in approved weeks "
            f"({weeks}) were given shifts first.")


def _day(d) -> str:
    return f"{d:%a %b} {d.day}"


CSS = """
:root { --ink:#1d1d1f; --muted:#5f6368; --line:#dcdce1; --bg:#ffffff; --panel:#f6f6f8;
        --bad:#b3261e; --bad-bg:#fdecea; --warn:#8a5a00; --warn-bg:#fff4dc; --ok:#1e6b35; --ok-bg:#e7f3ea; }
@media (prefers-color-scheme: dark) {
  :root { --ink:#ececf1; --muted:#a3a3ad; --line:#3a3a42; --bg:#16161a; --panel:#202026;
          --bad:#ff8a80; --bad-bg:#3a1d1b; --warn:#ffcc66; --warn-bg:#352b14; --ok:#8fd19e; --ok-bg:#1b3022; }
}
* { box-sizing: border-box; }
body { margin: 0 auto; max-width: 920px; padding: 24px 16px; background: var(--bg); color: var(--ink);
       font: 13px/1.45 -apple-system, "Helvetica Neue", Arial, sans-serif; }
.banner.approved { background: #1e6b35; }
.banner { background: #b3261e; color: #fff; font-weight: 700; font-size: 17px; letter-spacing: .04em;
          padding: 8px 12px; border-radius: 6px; }
h1 { font-size: 20px; margin: 12px 0 2px; }
.meta { color: var(--muted); font-size: 12px; margin: 0; }
h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .07em; color: var(--muted);
     margin: 18px 0 6px; padding-bottom: 3px; border-bottom: 1px solid var(--line); }
ul.items { list-style: none; margin: 0; padding: 0; }
ul.items li { padding: 6px 10px; border-radius: 6px; margin-bottom: 5px; }
li.bad { background: var(--bad-bg); color: var(--bad); }
li.warn { background: var(--warn-bg); color: var(--warn); }
li.ok { background: var(--ok-bg); color: var(--ok); }
li b { font-weight: 650; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; vertical-align: top; padding: 5px 6px; border-bottom: 1px solid var(--line); }
th { font-size: 11px; color: var(--muted); font-weight: 600; }
td.num { white-space: nowrap; font-variant-numeric: tabular-nums; }
.id { color: var(--muted); font-size: 11px; display: block; }
.open { color: var(--bad); font-weight: 650; }
tr.closed td { color: var(--muted); }
p.line { margin: 3px 0; }
.legend, footer { color: var(--muted); font-size: 11px; }
footer { margin-top: 16px; border-top: 1px solid var(--line); padding-top: 6px; }
@media (max-width: 600px) { .hide-narrow { display: none; } }
@page { size: letter; margin: 0.45in; }
@media print {
  :root { --ink:#000; --muted:#555; --line:#ccc; --bg:#fff; --panel:#fff;
          --bad:#b3261e; --bad-bg:#fdecea; --warn:#7a4f00; --warn-bg:#fff4dc; --ok:#1e6b35; --ok-bg:#e7f3ea; }
  body { padding: 0; max-width: none; font-size: 9.5px; line-height: 1.3; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .banner { font-size: 12px; padding: 4px 8px; }
  h1 { font-size: 15px; margin: 6px 0 0; }
  h2 { font-size: 9.5px; margin: 9px 0 3px; }
  th, td { padding: 2px 4px; }
  th { font-size: 8.5px; }
  ul.items li { padding: 3px 7px; margin-bottom: 3px; }
  .id { display: inline; font-size: 8.5px; margin-left: 3px; }
  p.line { margin: 1px 0; }
  .legend, footer { font-size: 8.5px; }
  footer { margin-top: 8px; }
  tr { break-inside: avoid; }
}
"""


def render_review_page(data: SignupData, settings: Settings, draft: Draft, findings: List[Finding],
                       gaps: List[Gap], review: Optional[ReviewResult], generated: datetime,
                       approval: Approval = Approval(DRAFT), edited: bool = False,
                       history=None, promoted: Optional[List[str]] = None) -> str:
    e = escape
    week = draft.week_start.isoformat()
    if approval.status == APPROVED:
        at = approval.approved_at
        banner = ('<div class="banner approved">APPROVED '
                  f'{at:%b} {at.day} at {at:%-I:%M %p}. calendar.ics is ready to import.</div>')
    elif approval.status == CHANGED:
        banner = ('<div class="banner">CHANGED SINCE APPROVAL. calendar.ics is out of date: '
                  'approve again before sharing.</div>')
    else:
        banner = '<div class="banner">DRAFT, NOT APPROVED. Don\'t share this schedule yet.</div>'
    people = {v.email: v for v in data.volunteers}
    counts = Counter(a.email for a in draft.assignments)

    # 1. Problems first.
    items = []
    for f in findings:
        if f.level == BROKEN:
            items.append(("bad", f"<b>Rule broken. Don't use this draft.</b> {e(f.message)}"))
    for g in gaps:
        items.append(("bad", e(g.text)))
    if review:
        pending = [i for i in review.items if i.status != CONFIRMED]
        if pending:
            names = ", ".join(e(i.volunteer.name) for i in pending)
            errors = sum(1 for i in pending if i.status.startswith("error"))
            extra = f" {errors} of them {'has' if errors == 1 else 'have'} a mistake in confirmed_reading." if errors else ""
            items.append(("warn", f"<b>Not scheduled: written availability not confirmed yet ({len(pending)}).</b> "
                                  f"{names}. Confirm them in availability_review.csv.{extra}"))
        for row in review.no_longer_apply:
            items.append(("warn", f"<b>Confirmation no longer applies:</b> {e(row.get('name') or row.get('email', ''))} "
                                  f"sent a different answer."))
    for v in data.volunteers:
        for p in v.problems:
            items.append(("warn", f"<b>Sign-up problem, not scheduled:</b> {e(v.name)}: {e(p)}"))
    for r in data.replaced:
        v = people.get(r.email)
        items.append(("warn", f"<b>More than one response:</b> {e(v.name if v else r.email)}. The newest one "
                              f"(row {r.new_row}) was used."))
    for n in list(settings.notes) + (list(history.skipped) if history else []):
        items.append(("warn", e(n)))
    if not items:
        items.append(("ok", "Nothing needs your attention. Every shift is staffed and no rules are broken."))
    attention = "\n".join(f'<li class="{cls}">{text}</li>' for cls, text in items)

    # 2. The week.
    rows = []
    slots = sorted([(s, False) for s in draft.slots] + [(s, True) for s in draft.closed],
                   key=lambda p: (p[0].date, p[0].shift.start))
    for slot, closed in slots:
        sh = slot.shift
        shift_cell = f"{e(sh.name)} <span class=\"id\">{e(sh.id)}</span>"
        if closed:
            rows.append(f'<tr class="closed"><td class="num">{_day(slot.date)}</td><td>{shift_cell}</td>'
                        f'<td class="num hide-narrow">{time_range(sh.start, sh.end)}</td><td class="num">–</td>'
                        f'<td>Closed (closed_dates in settings)</td></tr>')
            continue
        team = [people[a.email] for a in draft.assignments if a.shift_id == sh.id and a.date == slot.date]
        names = [e(v.name) + (" ★" if is_experienced(v, settings) else "") + (" ♥" if sh.id in v.preferred_ids else "")
                 for v in team]
        open_n = sh.needs - len(team)
        if open_n > 0:
            names.append(f'<span class="open">{open_n} open</span>')
        rows.append(f'<tr><td class="num">{_day(slot.date)}</td><td>{shift_cell}</td>'
                    f'<td class="num hide-narrow">{time_range(sh.start, sh.end)}</td>'
                    f'<td class="num">{len(team)}/{sh.needs}</td><td>{", ".join(names)}</td></tr>')
    week_table = "\n".join(rows)

    # 3. Fairness.
    fair = [f"<p class=\"line\"><b>{len(counts)} of {len(draft.candidates)}</b> ready volunteers are scheduled this week.</p>"]
    multi = sorted((people[em].name, n) for em, n in counts.items() if n > 1)
    fair.append("<p class=\"line\">More than one shift: "
                + (", ".join(f"{e(name)} ({n})" for name, n in multi) if multi else "nobody") + ".</p>")
    waiting = [v for v in draft.candidates if v.email not in counts]
    fair.append(f"<p class=\"line\">Available but not scheduled ({len(waiting)}): "
                + (", ".join(e(v.name) + e(waited(history, v.email, draft.week_start)) for v in waiting)
                   if waiting else "nobody") + ".</p>")
    fair.append(f"<p class=\"line\">{e(history_line(history))}</p>")
    if promoted:
        fair.append("<p class=\"line\">Counted as experienced because they've worked an approved shift: "
                    + ", ".join(e(n) for n in promoted) + ".</p>")
    with_prefs = [people[em] for em in counts if people[em].preferred_ids]
    got = [v for v in with_prefs
           if any(a.shift_id in v.preferred_ids for a in draft.assignments if a.email == v.email)]
    if with_prefs:
        fair.append(f"<p class=\"line\">{len(got)} of {len(with_prefs)} scheduled people with a preference "
                    f"got a shift they preferred.</p>")

    # 4. Contacts: scheduled people only.
    contact_rows = []
    for em in sorted(counts, key=lambda em: people[em].name.lower()):
        v = people[em]
        theirs = ", ".join(f"{a.date:%a} {a.shift_id}" for a in draft.assignments if a.email == em)
        contact_rows.append(f"<tr><td>{e(v.name)}</td><td>{e(theirs)}</td>"
                            f"<td class=\"num\">{e(v.phone)}</td><td>{e(v.email)}</td></tr>")
    contacts = "\n".join(contact_rows) or '<tr><td colspan="4">Nobody is scheduled.</td></tr>'

    week_label = f"{draft.week_start:%A, %B} {draft.week_start.day}, {draft.week_start.year}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Draft schedule, week of {draft.week_start:%b} {draft.week_start.day}</title>
<style>{CSS}</style>
</head>
<body>
{banner}
<h1>Volunteer schedule: week of {week_label}</h1>
<p class="meta">{"Checked" if edited else "Drafted"} {generated:%b} {generated.day}, {generated:%Y at %-I:%M %p} from {e(data.path.name)}{" and your edited assignments.csv" if edited else ""}. Nothing has been sent to anyone.</p>

<h2>1. Needs your attention</h2>
<ul class="items">
{attention}
</ul>

<h2>2. The week</h2>
<table>
<thead><tr><th>Day</th><th>Shift</th><th class="hide-narrow">Time</th><th>Filled</th><th>People</th></tr></thead>
<tbody>
{week_table}
</tbody>
</table>
<p class="legend">★ experienced &nbsp; ♥ a shift they preferred</p>

<h2>3. Fairness</h2>
{"".join(fair)}

<h2>4. Contact list (scheduled people only)</h2>
<table>
<thead><tr><th>Name</th><th>Shifts</th><th>Phone</th><th>Email</th></tr></thead>
<tbody>
{contacts}
</tbody>
</table>

<footer>To change who's on a shift, edit assignments.csv in this folder, then run
<code>python -m scheduler draft --week {week} --recheck</code>. When it looks right, run
<code>python -m scheduler approve --week {week}</code>.</footer>
</body>
</html>
"""


def render_assignments_csv(data: SignupData, draft: Draft) -> bytes:
    """One row per person per shift, plus a row with blank name/email for each open spot."""
    people = {v.email: v for v in data.volunteers}
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(ASSIGNMENT_COLUMNS)
    for slot in draft.slots:
        sh = slot.shift
        team = [a for a in draft.assignments if a.shift_id == sh.id and a.date == slot.date]
        for a in sorted(team, key=lambda a: people[a.email].name.lower()):
            w.writerow([slot.date.isoformat(), f"{slot.date:%a}", sh.id, sh.name, people[a.email].name, a.email])
        for _ in range(sh.needs - len(team)):
            w.writerow([slot.date.isoformat(), f"{slot.date:%a}", sh.id, sh.name, "", ""])
    return buf.getvalue().encode("utf-8-sig")


def write_week_files(base: Path, draft: Draft, html: str, assignments_csv: bytes,
                     replace: bool, now: datetime) -> Path:
    folder = Path(base) / WEEKS_DIR / draft.week_start.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "APPROVED").exists():
        raise InputError(
            f"The week of {draft.week_start.isoformat()} is already approved, so it wasn't redrafted. To change it, "
            f"edit its assignments.csv, run draft --week {draft.week_start.isoformat()} --recheck, then approve again."
        )
    target = folder / "assignments.csv"
    if target.exists() and target.read_bytes() != assignments_csv:
        if not replace:
            raise InputError(
                f"{WEEKS_DIR}/{draft.week_start.isoformat()}/assignments.csv already exists and differs from this "
                f"new draft. It may have your edits. To replace it with a fresh draft, run again with --replace. "
                f"The old file will be kept as a copy."
            )
        target.rename(folder / f"assignments-before-{now:%Y%m%d-%H%M%S}.csv")
    target.write_bytes(assignments_csv)
    (folder / "review.html").write_text(html, encoding="utf-8")
    return folder
