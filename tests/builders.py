"""Small helpers for building made-up scheduling scenarios in tests."""

from datetime import date, datetime, time
from pathlib import Path
from typing import List

from scheduler.readings import parse_reading
from scheduler.settings import Settings
from scheduler.shifts import Shift
from scheduler.signups import BLANK, CLEAN, Answer, SignupData, Volunteer

WEEK = date(2026, 11, 9)   # a Monday


def make_shift(shift_id: str, day: str, start: int, end: int, needs: int, experienced: bool = False) -> Shift:
    return Shift(id=shift_id, name=f"{day} shift {shift_id}", day=day, start=time(start), end=time(end),
                 needs=needs, needs_experienced=experienced, row=0)


# The five real shifts, built directly so tests don't depend on the spreadsheet.
TUE = make_shift("TUE-1500", "Tuesday", 15, 17, 2)
WED = make_shift("WED-1700", "Wednesday", 17, 19, 3, experienced=True)
THU = make_shift("THU-1500", "Thursday", 15, 17, 2)
SAT_AM = make_shift("SAT-0900", "Saturday", 9, 12, 3, experienced=True)
SAT_PM = make_shift("SAT-1200", "Saturday", 12, 15, 3, experienced=True)
REAL_SHIFTS = [TUE, WED, THU, SAT_AM, SAT_PM]


def make_person(name: str, reading: str, shifts, limit: int = 1, experienced: bool = False,
                ready: bool = True) -> Volunteer:
    email = name.lower().replace(" ", ".") + "@example.com"
    v = Volunteer(
        row=0, timestamp=datetime(2026, 10, 1), name=name, email=email, phone="",
        available=Answer(reading, CLEAN), preferred=Answer("", BLANK),
        max_per_week=limit, experienced=experienced,
    )
    if ready:
        v.reading, v.reading_source = parse_reading(reading, shifts), "form"
    return v


def make_data(shifts, people: List[Volunteer]) -> SignupData:
    return SignupData(Path("signups.xlsx"), list(shifts), people, [], [], len(people))


def settings(**kwargs) -> Settings:
    return Settings(**kwargs)
