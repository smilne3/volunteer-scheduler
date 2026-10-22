"""calendar.ics for importing into Google Calendar.

One event per shift. Names only: no ATTENDEE, ORGANIZER, email addresses, phone
numbers or reminders, so importing can't invite or notify anyone (D5).
Times are converted to UTC from settings.timezone.
"""

import re
from datetime import datetime, timezone
from typing import Dict, List
from zoneinfo import ZoneInfo

from .disclosure import ai_note
from .settings import Settings
from .shifts import Shift
from .signups import SignupData
from .solver import Draft, is_experienced
from .suggest import _DAY_RE, _TIME_RANGE_IN_NAME
from .text import norm

PRODID = "-//volunteer-scheduler//EN"


def _program(shift: Shift) -> str:
    p = _TIME_RANGE_IN_NAME.sub(" ", norm(shift.name))
    p = _DAY_RE.sub(" ", p)
    words = re.findall(r"[a-z]+", p)
    return " ".join(w.capitalize() for w in words) or shift.name


def event_titles(shifts: List[Shift]) -> Dict[str, str]:
    """'Saturday Food Pantry 9am–12pm' -> 'Food Pantry (AM)' when there are two on Saturday."""
    titles = {}
    for s in shifts:
        siblings = [o for o in shifts if o.weekday == s.weekday and _program(o) == _program(s)]
        title = _program(s)
        if len(siblings) > 1:
            halves = {o.id: "AM" if o.start.hour < 12 else "PM" for o in siblings}
            if len(set(halves.values())) == len(siblings):
                title += f" ({halves[s.id]})"
            else:
                title += f" ({s.start.strftime('%-I:%M %p').replace(':00', '').lower()})"
        titles[s.id] = title
    return titles


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _fold(line: str) -> bytes:
    """Lines longer than 75 octets continue on the next line after a space (RFC 5545)."""
    raw = line.encode("utf-8")
    out, start, limit = [], 0, 75
    while len(raw) - start > limit:
        cut = start + limit
        while (raw[cut] & 0xC0) == 0x80:     # don't split a multi-byte character
            cut -= 1
        out.append(raw[start:cut])
        start, limit = cut, 74               # continuation lines lose one octet to the space
    out.append(raw[start:])
    return b"\r\n ".join(out) + b"\r\n"


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def render_ics(data: SignupData, settings: Settings, draft: Draft, approved_at: datetime, sequence: int) -> bytes:
    tz = ZoneInfo(settings.timezone)
    people = {v.email: v for v in data.volunteers}
    titles = event_titles(data.shifts)
    stamp = _utc(approved_at.astimezone() if approved_at.tzinfo is None else approved_at)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]

    for slot in draft.slots:
        sh = slot.shift
        team = sorted((people[a.email] for a in draft.assignments
                       if a.shift_id == sh.id and a.date == slot.date), key=lambda v: v.name.lower())
        firsts = [v.name.split()[0] for v in team]
        names = firsts if len(set(firsts)) == len(firsts) else [v.name for v in team]
        open_n = sh.needs - len(team)
        summary = f"{titles[sh.id]}: {', '.join(names) if names else 'nobody yet'}"
        if open_n > 0:
            summary += f" ({open_n} open)"

        desc = [f"{sh.name} ({sh.id})", f"People ({len(team)} of {sh.needs}):"]
        desc += [f"- {v.name}" + (" (experienced)" if is_experienced(v, settings) else "") for v in team]
        if open_n > 0:
            desc.append(f"Open spots: {open_n}")
        desc.append(f"Approved {approved_at:%b} {approved_at.day}, {approved_at:%Y}. "
                    f"Nobody was invited or notified.")
        desc.append(ai_note(approved=True))

        start = datetime.combine(slot.date, sh.start, tzinfo=tz)
        end = datetime.combine(slot.date, sh.end, tzinfo=tz)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{draft.week_start.isoformat()}-{sh.id}@volunteer-scheduler",
            f"SEQUENCE:{sequence}",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_utc(start)}",
            f"DTEND:{_utc(end)}",
            f"SUMMARY:{_escape(summary)}",
            f"DESCRIPTION:{_escape(chr(10).join(desc))}",
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return b"".join(_fold(line) for line in lines)
