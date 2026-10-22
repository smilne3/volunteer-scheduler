"""Small helpers for building made-up scheduling scenarios in tests."""

from datetime import date, datetime, time
from pathlib import Path
from typing import List

from scheduler.readings import parse_reading
from scheduler.settings import Settings
from scheduler.shifts import Shift
from scheduler.signups import BLANK, CLEAN, Answer, SignupData, Volunteer

WEEK = date(2026, 11, 9)   # a Monday


def make_shift(shift_id: str, day: str, start: int, end: int, needs: int, experienced: bool = False,
               name: str = "") -> Shift:
    return Shift(id=shift_id, name=name or f"{day} shift {shift_id}", day=day, start=time(start), end=time(end),
                 needs=needs, needs_experienced=experienced, row=0)


# The five real shifts, built directly so tests don't depend on the spreadsheet.
TUE = make_shift("TUE-1500", "Tuesday", 15, 17, 2, name="Tuesday Tutoring 3pm–5pm")
WED = make_shift("WED-1700", "Wednesday", 17, 19, 3, experienced=True, name="Wednesday Phone Bank 5pm–7pm")
THU = make_shift("THU-1500", "Thursday", 15, 17, 2, name="Thursday Tutoring 3pm–5pm")
SAT_AM = make_shift("SAT-0900", "Saturday", 9, 12, 3, experienced=True, name="Saturday Food Pantry 9am–12pm")
SAT_PM = make_shift("SAT-1200", "Saturday", 12, 15, 3, experienced=True, name="Saturday Food Pantry 12pm–3pm")
REAL_SHIFTS = [TUE, WED, THU, SAT_AM, SAT_PM]


def make_person(name: str, reading: str, shifts, limit: int = 1, experienced: bool = False,
                ready: bool = True) -> Volunteer:
    email = name.lower().replace(" ", ".") + "@example.com"
    parsed = parse_reading(reading, shifts)
    v = Volunteer(
        row=0, timestamp=datetime(2026, 10, 1), name=name, email=email, phone="",
        available=Answer(reading, CLEAN, parsed.shift_ids), preferred=Answer("", BLANK),
        max_per_week=limit, experienced=experienced,
    )
    if ready:
        v.reading, v.reading_source = parsed, "form"
    return v


def make_data(shifts, people: List[Volunteer]) -> SignupData:
    return SignupData(Path("signups.xlsx"), list(shifts), people, [], [], len(people))


def settings(**kwargs) -> Settings:
    return Settings(**kwargs)


def random_scenario(rng, shifts, n_people):
    people = []
    for i in range(n_people):
        ids = [s.id for s in shifts if rng.random() < 0.4] or [rng.choice(shifts).id]
        reading = ", ".join(ids)
        if all(i.startswith("SAT") for i in ids) and rng.random() < 0.3:
            reading += " except 2026-11-14"        # the Saturday in the test week
        people.append(make_person(f"R{i}", reading, shifts, limit=rng.randint(1, 3),
                                  experienced=rng.random() < 0.35))
    return make_data(shifts, people)
