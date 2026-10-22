"""Phase 2: suggested readings for free-text answers."""

from datetime import date
from pathlib import Path

import pytest

from scheduler.readings import parse_reading
from scheduler.signups import NEEDS_READING, read_signups
from scheduler.suggest import suggest

DATA = read_signups(Path(__file__).parent / "fixtures" / "signups_fake.xlsx")
SHIFTS = DATA.shifts
ANSWERED = date(2026, 10, 6)
TODAY = date(2026, 10, 22)
ALL = "TUE-1500, WED-1700, THU-1500, SAT-0900, SAT-1200"


def read(text, as_of=ANSWERED, prefs=False):
    s = suggest(text, SHIFTS, as_of=as_of, today=TODAY, for_preferences=prefs)
    return s.reading.format(SHIFTS), s.notes


# --- the 11 free-text answers in the fake data -------------------------------

FAKE_ANSWERS = {
    "Saturdays but not the 14th": "SAT-0900, SAT-1200 except 2026-11-14",
    "any weekday after 4": "WED-1700",                        # tutoring starts at 3
    "Tues/Thurs afternoons, I get out of class at 2:30": "TUE-1500, THU-1500",
    "Sat mornings only": "SAT-0900",
    "Whatever you need! I'm flexible": ALL,
    "Wed evenings, maybe Sat if my kid doesn't have a game": "WED-1700",
    "Thursdays. Not Nov 26 (Thanksgiving)": "THU-1500 except 2026-11-26",
    "Saturday Food Pantry 9am–12pm, and phone bank every other week": "SAT-0900",
    "Afternoons Tue–Thu, no weekends please": "TUE-1500, THU-1500",   # phone bank is 5pm
    "Phone bank only, can't do in-person right now": "WED-1700",
    "every other Saturday, either shift": "none",
}


def test_every_fake_free_text_answer_is_covered():
    free_text = {v.available.raw for v in DATA.volunteers if v.available.status == NEEDS_READING}
    assert free_text == set(FAKE_ANSWERS)


@pytest.mark.parametrize("answer, expected", FAKE_ANSWERS.items())
def test_fake_answers(answer, expected):
    assert read(answer)[0] == expected


@pytest.mark.parametrize("answer", FAKE_ANSWERS)
def test_every_suggestion_is_a_valid_reading(answer):
    text, _ = read(answer)
    assert parse_reading(text, SHIFTS).format(SHIFTS) == text


# --- uncertain parts are left out, with a note saying so -----------------------

def test_maybe_is_left_out_and_noted():
    _, notes = read("Wed evenings, maybe Sat if my kid doesn't have a game")
    assert any("uncertain" in n and "maybe sat" in n for n in notes)


def test_every_other_week_gives_both_date_options():
    _, notes = read("Saturday Food Pantry 9am–12pm, and phone bank every other week")
    hint = next(n for n in notes if n.startswith("To include it"))
    assert '"SAT-0900; WED-1700 only 2026-10-28, 2026-11-11, 2026-11-25, 2026-12-09"' in hint
    assert '"SAT-0900; WED-1700 only 2026-11-04, 2026-11-18, 2026-12-02, 2026-12-16"' in hint


def test_every_other_with_nothing_else_has_no_leading_semicolon():
    _, notes = read("every other Saturday, either shift")
    assert any('"SAT-0900, SAT-1200 only 2026-10-24,' in n for n in notes)


def test_may_the_month_is_not_a_hedge():
    assert read("Saturdays, not May 1")[0] == "SAT-0900, SAT-1200 except 2027-05-01"
    assert read("I may be able to do Saturdays")[0] == "none"


def test_time_words_that_drop_a_shift_say_so():
    _, notes = read("Afternoons Tue–Thu, no weekends please")
    assert any(n.startswith("Left out WED-1700") for n in notes)


def test_unreadable_answer_suggests_nothing():
    text, notes = read("ask me closer to the date")
    assert text == "none" and any("Not used" in n for n in notes)


# --- individual patterns -----------------------------------------------------

@pytest.mark.parametrize("answer, expected", [
    ("Tuesdays", "TUE-1500"),
    ("tue to thu", "TUE-1500, WED-1700, THU-1500"),
    ("Tuesday through Thursday", "TUE-1500, WED-1700, THU-1500"),
    ("weekends", "SAT-0900, SAT-1200"),
    ("weekdays", "TUE-1500, WED-1700, THU-1500"),
    ("anything but weekends", ALL.replace(", SAT-0900, SAT-1200", "")),
    ("evenings", "WED-1700"),
    ("mornings or afternoons", "TUE-1500, THU-1500, SAT-0900, SAT-1200"),
    ("after 4pm", "WED-1700"),
    ("after noon", "TUE-1500, WED-1700, THU-1500, SAT-1200"),
    ("before 1pm", "SAT-0900"),
    ("Saturdays, mornings only", "SAT-0900"),
    ("tutoring", "TUE-1500, THU-1500"),
    ("food pantry", "SAT-0900, SAT-1200"),
    ("pantry on saturday mornings", "SAT-0900"),
    ("any shift", ALL),
    ("Saturday Food Pantry 12pm–3pm", "SAT-1200"),
    ("Thursdays, not 11/26", "THU-1500 except 2026-11-26"),
    ("Thursdays except November 26th", "THU-1500 except 2026-11-26"),
    # Without a comma, "not"/"except" must only cover the date, not the Thursdays.
    ("Thursdays not Nov 26", "THU-1500 except 2026-11-26"),
    ("Saturdays except the 14th", "SAT-0900, SAT-1200 except 2026-11-14"),
    ("I can not do saturdays, tuesdays are fine", "TUE-1500"),
    ("weekdays, no tutoring", "WED-1700"),
])
def test_patterns(answer, expected):
    assert read(answer)[0] == expected


def test_the_nth_is_placed_on_their_shift_day_after_they_answered():
    # Answered after Nov 14, so the next Saturday the 14th is in August 2027.
    text, notes = read("Saturdays but not the 14th", as_of=date(2026, 11, 20))
    assert text == "SAT-0900, SAT-1200 except 2027-08-14"
    assert any("months after they answered" in n for n in notes)


def test_dates_on_days_they_dont_work_are_ignored():
    text, notes = read("Thursdays, not Nov 27")
    assert text == "THU-1500"
    assert any("2026-11-27 (a Friday)" in n for n in notes)


def test_month_day_already_past_means_next_year():
    # Answered 2026-10-06, so "Oct 2" means 2027-10-02, which is a Saturday.
    assert read("Saturdays, not Oct 2")[0] == "SAT-0900, SAT-1200 except 2027-10-02"


# --- preferences ---------------------------------------------------------------

@pytest.mark.parametrize("answer, expected", [
    ("Mornings if possible", "SAT-0900"),          # "if" doesn't drop preferences
    ("tutoring!!", "TUE-1500, THU-1500"),
    ("afternoon", "TUE-1500, THU-1500, SAT-1200"),
])
def test_preferences(answer, expected):
    assert read(answer, prefs=True)[0] == expected
