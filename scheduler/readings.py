"""Availability readings: which shifts someone can do, with optional date limits.

Text format, used in availability_review.csv:

    SAT-0900, SAT-1200 except 2026-11-14
    SAT-0900; WED-1700 only 2026-11-11, 2026-11-25
    none

Groups are separated by ";". "except" and "only" apply to the shifts in their own group.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import FrozenSet, Iterable, Optional, Sequence, Tuple

from .shifts import DAYS, Shift


class ReadingError(ValueError):
    """A confirmed reading that can't be understood. Message is for the coordinator."""


@dataclass(frozen=True)
class Group:
    shift_ids: FrozenSet[str]
    except_dates: FrozenSet[date] = frozenset()
    only_dates: Optional[FrozenSet[date]] = None   # None = every week

    @property
    def has_date_limits(self) -> bool:
        return bool(self.except_dates) or self.only_dates is not None


@dataclass(frozen=True)
class Reading:
    groups: Tuple[Group, ...] = ()

    @property
    def shift_ids(self) -> FrozenSet[str]:
        return frozenset(i for g in self.groups for i in g.shift_ids)

    def group_for(self, shift_id: str) -> Optional[Group]:
        return next((g for g in self.groups if shift_id in g.shift_ids), None)

    def allows(self, shift_id: str, on: date) -> bool:
        g = self.group_for(shift_id)
        if g is None or on in g.except_dates:
            return False
        return g.only_dates is None or on in g.only_dates

    def format(self, shifts: Sequence[Shift]) -> str:
        if not self.groups:
            return "none"
        order = {s.id: i for i, s in enumerate(shifts)}
        parts = []
        for g in self.groups:
            text = ", ".join(sorted(g.shift_ids, key=lambda i: (order.get(i, len(order)), i)))
            if g.except_dates:
                text += " except " + _dates_text(g.except_dates)
            if g.only_dates is not None:
                text += " only " + _dates_text(g.only_dates)
            parts.append(text)
        return "; ".join(parts)


def plain(shift_ids: Iterable[str]) -> Reading:
    """Every week, no date limits."""
    ids = frozenset(shift_ids)
    return Reading((Group(ids),)) if ids else Reading()


def _dates_text(dates: Iterable[date]) -> str:
    return ", ".join(d.isoformat() for d in sorted(dates))


def _parse_date(text: str) -> date:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ReadingError(f'"{text}" isn\'t a date. Write dates like 2026-11-14.')


_GROUP_RE = re.compile(r"^(.*?)(?:\s+(except|only)\b\s*(.*))?$", re.IGNORECASE)


def parse_reading(text, shifts: Sequence[Shift]) -> Reading:
    by_id = {s.id: s for s in shifts}
    t = " ".join(str(text or "").split())
    if not t:
        raise ReadingError("The reading is empty.")
    if t.lower() == "none":
        return Reading()

    groups, seen = [], set()
    for raw in t.split(";"):
        g = raw.strip()
        if not g:
            continue
        ids_text, kind, dates_text = _GROUP_RE.match(g).groups()
        ids = [i.upper() for i in re.split(r"[,\s]+", ids_text) if i]
        if not ids:
            raise ReadingError(f'"{g}" doesn\'t list any shift IDs.')
        for i in ids:
            if i not in by_id:
                raise ReadingError(f'Unknown shift ID "{i}". Shift IDs are: {", ".join(by_id)}.')
            if i in seen:
                raise ReadingError(f"{i} appears more than once.")
            seen.add(i)

        dates: FrozenSet[date] = frozenset()
        if kind:
            kind = kind.lower()
            parsed = [_parse_date(d.strip()) for d in dates_text.split(",") if d.strip()]
            if not parsed:
                raise ReadingError(f'"{kind}" needs at least one date after it.')
            days = sorted({by_id[i].day for i in ids}, key=DAYS.index)
            for d in parsed:
                if DAYS[d.weekday()] not in days:
                    raise ReadingError(
                        f"{d.isoformat()} is a {DAYS[d.weekday()]}, but {', '.join(ids)} "
                        f"{'is' if len(ids) == 1 else 'are'} on {' and '.join(days)}."
                    )
            dates = frozenset(parsed)
        groups.append(Group(
            frozenset(ids),
            except_dates=dates if kind == "except" else frozenset(),
            only_dates=dates if kind == "only" else None,
        ))
    if not groups:
        raise ReadingError("The reading is empty.")
    return Reading(tuple(groups))
