"""settings.json: loaded from the same folder as signups.xlsx. Missing file = defaults."""

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import FrozenSet, List

from .errors import InputError

FILE_NAME = "settings.json"


@dataclass(frozen=True)
class Settings:
    timezone: str = "America/New_York"
    closed_dates: FrozenSet[date] = frozenset()
    extra_experienced_emails: FrozenSet[str] = frozenset()
    fair_counts_before_preferences: bool = True
    allow_back_to_back_shifts: bool = True
    fairness_lookback_weeks: int = 4
    count_approved_shifts_as_experience: bool = False
    notes: List[str] = field(default_factory=list, compare=False, hash=False)


_BOOLS = ("fair_counts_before_preferences", "allow_back_to_back_shifts", "count_approved_shifts_as_experience")
_KNOWN = ("timezone", "closed_dates", "extra_experienced_emails", "fairness_lookback_weeks") + _BOOLS


def load_settings(folder: Path) -> Settings:
    path = Path(folder) / FILE_NAME
    if not path.exists():
        return Settings(notes=[f"No {FILE_NAME} found, so defaults were used. "
                               f"Copy settings.example.json to {FILE_NAME} to change them."])
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise InputError(f"{FILE_NAME} isn't valid JSON (line {e.lineno}): {e.msg}. "
                         f"Compare it with settings.example.json.")
    if not isinstance(raw, dict):
        raise InputError(f"{FILE_NAME} should be a {{ ... }} list of settings.")

    errors = []
    unknown = sorted(set(raw) - set(_KNOWN))
    if unknown:
        errors.append(f"unknown setting(s) {', '.join(unknown)}. Known settings: {', '.join(_KNOWN)}.")

    values = {}
    tz = raw.get("timezone", Settings.timezone)
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(str(tz))
        values["timezone"] = str(tz)
    except Exception:
        errors.append(f'timezone "{tz}" isn\'t a known timezone, e.g. "America/New_York".')

    closed = raw.get("closed_dates", [])
    if not isinstance(closed, list):
        errors.append('closed_dates should be a list like ["2026-11-26"].')
    else:
        parsed = set()
        for d in closed:
            try:
                parsed.add(date.fromisoformat(str(d)))
            except ValueError:
                errors.append(f'closed_dates has "{d}", which isn\'t a date like 2026-11-26.')
        values["closed_dates"] = frozenset(parsed)

    emails = raw.get("extra_experienced_emails", [])
    if not isinstance(emails, list) or not all(isinstance(e, str) and "@" in e for e in emails):
        errors.append('extra_experienced_emails should be a list of email addresses.')
    else:
        values["extra_experienced_emails"] = frozenset(e.strip().lower() for e in emails)

    for key in _BOOLS:
        if key in raw:
            if not isinstance(raw[key], bool):
                errors.append(f"{key} should be true or false (no quotes).")
            else:
                values[key] = raw[key]

    weeks = raw.get("fairness_lookback_weeks", Settings.fairness_lookback_weeks)
    if not isinstance(weeks, int) or isinstance(weeks, bool) or weeks < 0:
        errors.append("fairness_lookback_weeks should be a whole number, 0 or more.")
    else:
        values["fairness_lookback_weeks"] = weeks

    if errors:
        raise InputError(f"Problems in {FILE_NAME}:\n" + "\n".join(f"  - {e}" for e in errors))
    return Settings(**values)
