"""Phase 2: the reading format the coordinator types into confirmed_reading."""

from datetime import date
from pathlib import Path

import pytest

from scheduler.readings import ReadingError, parse_reading, plain
from scheduler.signups import read_signups

SHIFTS = read_signups(Path(__file__).parent / "fixtures" / "signups_fake.xlsx").shifts


def fmt(text):
    return parse_reading(text, SHIFTS).format(SHIFTS)


@pytest.mark.parametrize("text, expected", [
    ("SAT-0900, SAT-1200", "SAT-0900, SAT-1200"),
    ("sat-1200 sat-0900", "SAT-0900, SAT-1200"),                       # any case, any order
    ("SAT-0900, SAT-1200 except 2026-11-14", "SAT-0900, SAT-1200 except 2026-11-14"),
    ("SAT-0900; WED-1700 only 2026-11-25, 2026-11-11", "SAT-0900; WED-1700 only 2026-11-11, 2026-11-25"),
    ("THU-1500 EXCEPT 11/26/2026", "THU-1500 except 2026-11-26"),      # US date style accepted
    ("none", "none"),
    ("  None ", "none"),
])
def test_valid_readings_round_trip(text, expected):
    assert fmt(text) == expected
    assert fmt(expected) == expected


@pytest.mark.parametrize("text, message", [
    ("", "empty"),
    ("SAT-1000", 'Unknown shift ID "SAT-1000"'),
    ("Saturdays", 'Unknown shift ID "SATURDAYS"'),
    ("SAT-0900 except 2026-11-13", "2026-11-13 is a Friday, but SAT-0900 is on Saturday"),
    ("SAT-0900, WED-1700 only 2026-11-12", "2026-11-12 is a Thursday, but SAT-0900, WED-1700 are on Wednesday and Saturday"),
    ("SAT-0900 except Nov 14", '"Nov 14" isn\'t a date'),
    ("SAT-0900 except", '"except" needs at least one date'),
    ("SAT-0900; SAT-0900 only 2026-11-14", "SAT-0900 appears more than once"),
])
def test_invalid_readings_explain_the_problem(text, message):
    with pytest.raises(ReadingError) as e:
        parse_reading(text, SHIFTS)
    assert message in str(e.value)


def test_except_dates_block_only_those_dates():
    r = parse_reading("SAT-0900, SAT-1200 except 2026-11-14", SHIFTS)
    assert not r.allows("SAT-0900", date(2026, 11, 14))
    assert r.allows("SAT-0900", date(2026, 11, 7))
    assert r.allows("SAT-1200", date(2026, 11, 21))
    assert not r.allows("WED-1700", date(2026, 11, 11))


def test_only_dates_allow_just_those_dates():
    r = parse_reading("SAT-0900; WED-1700 only 2026-11-11, 2026-11-25", SHIFTS)
    assert r.allows("WED-1700", date(2026, 11, 11))
    assert not r.allows("WED-1700", date(2026, 11, 18))
    assert r.allows("SAT-0900", date(2026, 11, 14))          # other group: every week


def test_none_allows_nothing():
    r = parse_reading("none", SHIFTS)
    assert r.shift_ids == frozenset()
    assert not r.allows("SAT-0900", date(2026, 11, 14))


def test_plain_reading_from_checkbox_answers():
    r = plain({"TUE-1500", "THU-1500"})
    assert r.format(SHIFTS) == "TUE-1500, THU-1500"
    assert not r.groups[0].has_date_limits
