"""Suggested readings for free-text answers like "Saturdays but not the 14th".

These are suggestions only. A person confirms availability readings before
they're used (D7). To keep confirming safe, a suggestion leaves out anything
uncertain ("maybe Sat", "every other week") and says why in the notes. Accepting
a suggestion can never add availability the person didn't clearly give.
"""

import re
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from typing import Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

from .readings import Group, Reading
from .shifts import DAYS, Shift
from .text import norm

DAY_WORDS = {
    "monday": 0, "mondays": 0, "mon": 0,
    "tuesday": 1, "tuesdays": 1, "tues": 1, "tue": 1,
    "wednesday": 2, "wednesdays": 2, "weds": 2, "wed": 2,
    "thursday": 3, "thursdays": 3, "thurs": 3, "thur": 3, "thu": 3,
    "friday": 4, "fridays": 4, "fri": 4,
    "saturday": 5, "saturdays": 5, "sats": 5, "sat": 5,
    "sunday": 6, "sundays": 6, "sun": 6,
}
_DAY = "|".join(sorted(DAY_WORDS, key=len, reverse=True))
_DAY_RE = re.compile(rf"\b({_DAY})\b")
_DAY_RANGE_RE = re.compile(rf"\b({_DAY})\s*(?:-|to|through|thru)\s*({_DAY})\b")
_WEEKDAYS_RE = re.compile(r"\bweekdays?\b")
_WEEKENDS_RE = re.compile(r"\bweekends?\b")

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_MONTH_DATE_RE = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b")
_SLASH_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
_NTH_RE = re.compile(r"\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b")

_CLOCK = r"(noon|\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
_AFTER_RE = re.compile(rf"\bafter\s+{_CLOCK}")
_BEFORE_RE = re.compile(rf"\bbefore\s+{_CLOCK}")

_HEDGE_RE = re.compile(
    r"\b(maybe|possibly|perhaps|might|if|sometimes|depends|depending|probably|hopefully|"
    r"occasionally|some|may)\b|\bevery other\b|\balternat\w*"
)
_EVERY_OTHER_RE = re.compile(r"\bevery other\b|\balternat\w*|\bbiweekly\b")
_NEGATION_RE = re.compile(
    r"\b(not|no|never|except|cannot|can't|cant|won't|wont|unable|don't|dont|doesn't|isn't|aren't)\b"
)
_FLEXIBLE_RE = re.compile(r"\b(flexible|whatever|anything|anytime|whenever|wherever|any time|any shifts?|all shifts?)\b")
_FILLER = {"and", "or", "please", "thanks", "thank you", "ok"}
_PROGRAM_STOPWORDS = {"shift", "shifts", "with", "from", "the", "and"}
_TIME_RANGE_IN_NAME = re.compile(r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*-\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?")

Predicate = Callable[[Shift], bool]


@dataclass
class Suggestion:
    reading: Reading
    notes: List[str] = field(default_factory=list)


def _clock(text: str) -> Optional[time]:
    text = text.strip()
    if text == "noon":
        return time(12)
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if not m:
        return None
    hour, minute, ampm = int(m[1]), int(m[2] or 0), m[3]
    if minute > 59:
        return None
    if ampm == "am":
        hour = 0 if hour == 12 else hour
    elif ampm == "pm":
        hour = hour if hour == 12 else hour + 12
    elif 1 <= hour <= 7:
        hour += 12          # "after 4" means 4pm; 8-12 are read as written
    return time(hour, minute) if hour <= 23 else None


def _fmt_clock(t: time) -> str:
    return t.strftime("%-I:%M %p").replace(":00 ", " ").lower()


def _days(clause: str) -> Set[int]:
    days = set()
    for a, b in _DAY_RANGE_RE.findall(clause):
        start, end = DAY_WORDS[a], DAY_WORDS[b]
        days.update(range(start, end + 1) if start <= end else list(range(start, 7)) + list(range(0, end + 1)))
    days.update(DAY_WORDS[w] for w in _DAY_RE.findall(clause))
    if _WEEKDAYS_RE.search(clause):
        days.update(range(0, 5))
    if _WEEKENDS_RE.search(clause):
        days.update((5, 6))
    return days


def _time_filter(clause: str) -> Tuple[List[str], Optional[Predicate]]:
    """Time-of-day words combine with "or"; "after"/"before" combine with "and"."""
    labels, periods, limits = [], [], []
    if re.search(r"\bmornings?\b", clause):
        labels.append("mornings")
        periods.append(lambda s: s.start < time(12))
    if re.search(r"\bafternoons?\b", clause):
        labels.append("afternoons")
        periods.append(lambda s: time(12) <= s.start < time(17))
    if re.search(r"\b(evenings?|nights?)\b", clause):
        labels.append("evenings")
        periods.append(lambda s: s.start >= time(17))
    for m in _AFTER_RE.finditer(clause):
        t = _clock(m[1])
        if t:
            labels.append(f"starting at {_fmt_clock(t)} or later")
            limits.append(lambda s, t=t: s.start >= t)
    for m in _BEFORE_RE.finditer(clause):
        t = _clock(m[1])
        if t:
            labels.append(f"ending by {_fmt_clock(t)}")
            limits.append(lambda s, t=t: s.end <= t)
    if not periods and not limits:
        return [], None
    return labels, lambda s: (not periods or any(p(s) for p in periods)) and all(f(s) for f in limits)


def _programs(shifts: Sequence[Shift]) -> Dict[str, FrozenSet[str]]:
    """'saturday food pantry 9am-12pm' -> program 'food pantry'. Program -> shift IDs."""
    out: Dict[str, Set[str]] = {}
    for s in shifts:
        p = _TIME_RANGE_IN_NAME.sub(" ", norm(s.name))
        p = _DAY_RE.sub(" ", p)
        p = " ".join(re.findall(r"[a-z]+", p))
        if p:
            out.setdefault(p, set()).add(s.id)
    return {p: frozenset(ids) for p, ids in out.items()}


def _mentions_program(clause: str, program: str) -> bool:
    if program in clause:
        return True
    words = re.findall(r"[a-z]+", clause)
    stems = [w[:5] for w in re.findall(r"[a-z]+", program) if len(w) >= 4 and w not in _PROGRAM_STOPWORDS]
    return any(w.startswith(stem) for stem in stems for w in words)


def _take_dates(clause: str, as_of: date):
    """Pull dates out of the clause. Returns (dates, nth-of-month numbers, notes, clause without dates)."""
    dates, notes = [], []

    def resolve(month: int, day: int, year: Optional[int], said: str):
        try:
            d = date(year or as_of.year, month, day)
            if year is None and d < as_of:
                d = date(as_of.year + 1, month, day)
            dates.append(d)
        except ValueError:
            notes.append(f'"{said}" isn\'t a real date, so it was left out.')
        return " "

    clause = _MONTH_DATE_RE.sub(lambda m: resolve(MONTHS[m[1]], int(m[2]), None, m[0]), clause)

    def slash(m):
        year = int(m[3]) if m[3] else None
        if year is not None and year < 100:
            year += 2000
        return resolve(int(m[1]), int(m[2]), year, m[0])

    clause = _SLASH_DATE_RE.sub(slash, clause)
    nths = [int(n) for n in _NTH_RE.findall(clause)]
    clause = _NTH_RE.sub(" ", clause)
    return dates, nths, notes, " ".join(clause.split())


def _pick(shifts, days: Set[int], programs: Set[FrozenSet[str]], pred: Optional[Predicate]) -> Set[str]:
    in_programs = frozenset().union(*programs) if programs else None
    return {
        s.id for s in shifts
        if (not days or s.weekday in days)
        and (in_programs is None or s.id in in_programs)
        and (pred is None or pred(s))
    }


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _every_other_hint(ids: Set[str], shifts: Sequence[Shift], today: date, base: Reading) -> Optional[str]:
    by_id = {s.id: s for s in shifts}
    weekdays = {by_id[i].weekday for i in ids}
    if len(weekdays) != 1:
        return None
    wd = weekdays.pop()
    first = today + timedelta(days=(wd - today.weekday()) % 7)
    weeks = [first + timedelta(weeks=k) for k in range(8)]
    ids_text = Reading((Group(frozenset(ids)),)).format(shifts)
    prefix = "" if not base.groups else f"{base.format(shifts)}; "
    a = ", ".join(d.isoformat() for d in weeks[0::2])
    b = ", ".join(d.isoformat() for d in weeks[1::2])
    return (f'To include it, confirm "{prefix}{ids_text} only {a}" '
            f'or, for the other weeks, "{prefix}{ids_text} only {b}".')


def suggest(answer: str, shifts: Sequence[Shift], as_of: date, today: Optional[date] = None,
            for_preferences: bool = False) -> Suggestion:
    """as_of: when they answered (for "the 14th"). today: for "every other week" date lists."""
    today = today or as_of
    notes: List[str] = []
    programs = _programs(shifts)
    all_ids = {s.id for s in shifts}

    text = norm(answer).replace("a.m.", "am").replace("p.m.", "pm")
    text = re.sub(r"[()\"\[\]]", " ", text)

    selected: Set[str] = set()
    excluded: Set[str] = set()
    filters: List[Predicate] = []
    except_dates: List[date] = []
    except_nths: List[int] = []
    every_other: List[Set[str]] = []
    has_selector = False

    # A full shift name, like a checkbox option, counts as that exact shift.
    for s in shifts:
        if norm(s.name) in text:
            selected.add(s.id)
            has_selector = True
            text = text.replace(norm(s.name), " ")

    # "anything but weekends" means "anything except weekends".
    text = re.sub(r"\b(anything|everything|any|all)\s+but\b", r"\1, except", text)
    # Start a new clause at "except"/"not"/"no", so in "Thursdays except Nov 26"
    # the exception covers only the date, not the Thursdays.
    for raw in re.split(r"[,;.!?]+|\bbut\b|(?=\b(?:except|not|no)\b)", text):
        clause = " ".join(raw.split())
        if not clause or clause in _FILLER:
            continue
        dates, nths, date_notes, rest = _take_dates(clause, as_of)
        notes.extend(date_notes)
        days = _days(rest)
        progs = {ids for p, ids in programs.items() if _mentions_program(rest, p)}
        time_labels, pred = _time_filter(rest)
        flexible = bool(_FLEXIBLE_RE.search(rest))
        understood = bool(days or progs or pred or dates or nths or flexible)

        if not for_preferences and _HEDGE_RE.search(rest):
            notes.append(f'Left out because it sounds uncertain: "{clause}".')
            if _EVERY_OTHER_RE.search(rest) and (days or progs):
                every_other.append(_pick(shifts, days, progs, pred))
            continue

        if _NEGATION_RE.search(rest):
            except_dates.extend(dates)
            except_nths.extend(nths)
            if days or progs or pred:
                excluded |= _pick(shifts, days, progs, pred)
            if not understood:
                notes.append(f'Not used: "{clause}".')
            continue

        if flexible:
            selected |= all_ids
            has_selector = True
            notes.append("Read as any shift.")
        elif days or progs:
            picked = _pick(shifts, days, progs, pred)
            dropped = _pick(shifts, days, progs, None) - picked
            if dropped:
                names = ", ".join(sorted(dropped, key=lambda i: [s.id for s in shifts].index(i)))
                notes.append(f'Left out {names}: "{clause}" means {" or ".join(time_labels)} only.')
            selected |= picked
            has_selector = True
        elif pred:
            filters.append(pred)
            notes.append(f"Limited to {' or '.join(time_labels)}.")
        elif dates or nths:
            notes.append(f'Not used: "{clause}". Dates only count after "not" or "except".')
        else:
            notes.append(f'Not used: "{clause}".')

    by_id = {s.id: s for s in shifts}
    if filters and not has_selector:
        selected = set(all_ids)
    for f in filters:
        selected = {i for i in selected if f(by_id[i])}
    selected -= excluded

    if for_preferences:
        return Suggestion(Reading((Group(frozenset(selected)),)) if selected else Reading(), list(dict.fromkeys(notes)))

    # Dates they can't make, kept only if they fall on one of their shift days.
    their_days = {by_id[i].weekday for i in selected}
    blocked: Set[date] = set()
    for n in except_nths:
        found = None
        for k in range(13):
            y, m = divmod(as_of.month - 1 + k, 12)
            try:
                d = date(as_of.year + y, m + 1, n)
            except ValueError:
                continue
            if d >= as_of and d.weekday() in their_days:
                found = d
                break
        if found:
            blocked.add(found)
            note = f'Read "the {_ordinal(n)}" as {DAYS[found.weekday()]} {found.isoformat()}.'
            if (found - as_of).days > 60:
                note += " That's months after they answered, so check what they meant."
            notes.append(note)
        else:
            notes.append(f'Couldn\'t match "the {_ordinal(n)}" to one of their shift days, so it was left out.')
    for d in except_dates:
        if d.weekday() in their_days:
            blocked.add(d)
        else:
            notes.append(f"Mentions {d.isoformat()} (a {DAYS[d.weekday()]}), which isn't one of their shift days, so it was ignored.")

    reading = Reading((Group(frozenset(selected), frozenset(blocked)),)) if selected else Reading()
    for ids in every_other:
        hint = _every_other_hint(ids - selected, shifts, today, reading) if ids - selected else None
        if hint:
            notes.append(hint)
    if not reading.groups and not notes:
        notes.append("Couldn't find any shifts in this answer.")
    return Suggestion(reading, list(dict.fromkeys(notes)))
