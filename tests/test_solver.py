"""Phase 3: the scheduler (hard rules, experienced cover, coverage)."""

import itertools
import random
import shutil
from datetime import date
from pathlib import Path

import pytest

from builders import (REAL_SHIFTS, SAT_AM, SAT_PM, TUE, WED, WEEK, make_data, make_person, make_shift,
                      random_scenario, settings)
from scheduler.checker import BROKEN, check
from scheduler.review_file import apply_reviews
from scheduler.signups import read_signups
from scheduler.solver import Assignment, schedule

FIXTURE = Path(__file__).parent / "fixtures" / "signups_fake.xlsx"


def on(draft, shift_id):
    return sorted(a.email.split("@")[0] for a in draft.assignments if a.shift_id == shift_id)


def broken(findings):
    return [f for f in findings if f.level == BROKEN]


# --- the fake data -------------------------------------------------------------

@pytest.fixture(scope="module")
def fake(tmp_path_factory):
    folder = tmp_path_factory.mktemp("fake")
    shutil.copy(FIXTURE, folder / "signups.xlsx")
    data = read_signups(folder / "signups.xlsx")
    apply_reviews(data, today=date(2026, 10, 22))
    return data


def test_fake_week_is_fully_staffed_and_breaks_no_rules(fake):
    draft = schedule(fake, settings(), WEEK)
    assert check(fake, settings(), WEEK, draft.assignments) == []   # nothing broken, nothing unmet
    assert len(draft.assignments) == 13


def test_only_ready_people_are_scheduled(fake):
    draft = schedule(fake, settings(), WEEK)
    ready = {v.email for v in fake.volunteers if v.status == "ready"}
    assert {a.email for a in draft.assignments} <= ready
    assert len(draft.left_out) == 11       # free text not confirmed yet


def test_same_input_same_draft(fake):
    assert schedule(fake, settings(), WEEK).assignments == schedule(fake, settings(), WEEK).assignments


# --- hard rules ----------------------------------------------------------------

def test_shortage_leaves_slot_empty_and_flagged():
    people = [make_person("Only One", "TUE-1500", REAL_SHIFTS, limit=3)]
    data = make_data([TUE], people)
    draft = schedule(data, settings(), WEEK)
    assert on(draft, "TUE-1500") == ["only.one"]
    findings = check(data, settings(), WEEK, draft.assignments)
    assert not broken(findings)
    assert [f.message for f in findings] == ["TUE-1500 (Tue Nov 10) has 1 of 2 people."]


def test_weekly_limit_is_never_exceeded_even_when_short():
    people = [make_person("Willing Will", "TUE-1500, WED-1700, SAT-0900, SAT-1200", REAL_SHIFTS, limit=1)]
    draft = schedule(make_data(REAL_SHIFTS, people), settings(), WEEK)
    assert len(draft.assignments) == 1


def test_never_overfilled():
    people = [make_person(f"P{i}", "TUE-1500", REAL_SHIFTS) for i in range(6)]
    draft = schedule(make_data([TUE], people), settings(), WEEK)
    assert len(on(draft, "TUE-1500")) == 2


def test_experienced_trap():
    """The only experienced person could do either shift; only one shift needs them."""
    needs_exp = make_shift("WED-1700", "Wednesday", 17, 19, 1, experienced=True)
    no_exp = make_shift("THU-1500", "Thursday", 15, 17, 1)
    shifts = [needs_exp, no_exp]
    people = [
        make_person("Vet Veteran", "WED-1700, THU-1500", shifts, limit=1, experienced=True),
        make_person("New Newbie", "WED-1700, THU-1500", shifts, limit=1),
    ]
    data = make_data(shifts, people)
    for week in (WEEK, date(2026, 11, 16), date(2026, 11, 23)):   # tie-break changes weekly
        draft = schedule(data, settings(), week)
        assert on(draft, "WED-1700") == ["vet.veteran"]
        assert on(draft, "THU-1500") == ["new.newbie"]
        assert check(data, settings(), week, draft.assignments) == []


def test_except_date_is_respected():
    people = [make_person("Bailey", "SAT-0900 except 2026-11-14", REAL_SHIFTS, experienced=True)]
    data = make_data([SAT_AM], people)
    assert schedule(data, settings(), WEEK).assignments == []                  # Sat Nov 14
    assert on(schedule(data, settings(), date(2026, 11, 16)), "SAT-0900") == ["bailey"]  # Sat Nov 21


def test_only_dates_are_respected():
    people = [make_person("Val", "WED-1700 only 2026-11-11", REAL_SHIFTS)]
    data = make_data([WED], people)
    assert on(schedule(data, settings(), WEEK), "WED-1700") == ["val"]
    assert schedule(data, settings(), date(2026, 11, 16)).assignments == []


def test_closed_date_has_no_shifts():
    people = [make_person(f"P{i}", "SAT-0900, SAT-1200, TUE-1500", REAL_SHIFTS, limit=2, experienced=True)
              for i in range(8)]
    data = make_data([TUE, SAT_AM, SAT_PM], people)
    s = settings(closed_dates=frozenset({date(2026, 11, 14)}))
    draft = schedule(data, s, WEEK)
    assert {a.shift_id for a in draft.assignments} == {"TUE-1500"}
    assert [sl.shift.id for sl in draft.closed] == ["SAT-0900", "SAT-1200"]
    assert check(data, s, WEEK, draft.assignments) == []          # closed slots aren't "unfilled"


@pytest.mark.parametrize("allowed, expected_count", [(True, 2), (False, 1)])
def test_back_to_back_setting(allowed, expected_count):
    people = [make_person("Sat Sam", "SAT-0900, SAT-1200", REAL_SHIFTS, limit=2, experienced=True)]
    s = settings(allow_back_to_back_shifts=allowed)
    data = make_data([SAT_AM, SAT_PM], people)
    draft = schedule(data, s, WEEK)
    assert len(draft.assignments) == expected_count
    assert not broken(check(data, s, WEEK, draft.assignments))


def test_overlapping_shifts_are_never_both_given():
    a = make_shift("SAT-0900", "Saturday", 9, 12, 1)
    b = make_shift("SAT-1100", "Saturday", 11, 13, 1)
    people = [make_person("Busy Bee", "SAT-0900, SAT-1100", [a, b], limit=2)]
    draft = schedule(make_data([a, b], people), settings(), WEEK)
    assert len(draft.assignments) == 1


def test_people_not_ready_are_never_scheduled():
    people = [make_person("Unconfirmed", "TUE-1500", REAL_SHIFTS, limit=2, ready=False)]
    draft = schedule(make_data([TUE], people), settings(), WEEK)
    assert draft.assignments == [] and [v.name for v in draft.left_out] == ["Unconfirmed"]


def test_extra_experienced_emails_count_as_experienced():
    people = [make_person("Long Timer", "WED-1700", REAL_SHIFTS)]
    data = make_data([WED], people)
    draft = schedule(data, settings(), WEEK)
    assert any(f.code == "no_experienced" for f in check(data, settings(), WEEK, draft.assignments))
    s = settings(extra_experienced_emails=frozenset({"long.timer@example.com"}))
    assert not any(f.code == "no_experienced" for f in check(data, s, WEEK, draft.assignments))


# --- the checker catches every kind of broken rule ------------------------------

def _checker_case(code):
    sat_ok = make_person("Sat Ok", "SAT-0900, SAT-1200", REAL_SHIFTS, limit=2, experienced=True)
    one = make_person("Limit One", "TUE-1500, WED-1700", REAL_SHIFTS, limit=1)
    tue = make_person("Tue Only", "TUE-1500", REAL_SHIFTS)
    unready = make_person("Not Ready", "TUE-1500", REAL_SHIFTS, ready=False)
    overlap_a = make_shift("FRI-0900", "Friday", 9, 12, 1)
    overlap_b = make_shift("FRI-1100", "Friday", 11, 13, 1)
    friday = make_person("Fri Fan", "FRI-0900, FRI-1100", [overlap_a, overlap_b], limit=2)
    shifts = REAL_SHIFTS + [overlap_a, overlap_b]
    data = make_data(shifts, [sat_ok, one, tue, unready, friday])
    tue_d, wed_d, fri_d, sat_d = (date(2026, 11, d) for d in (10, 11, 13, 14))
    A = Assignment
    s = settings()
    cases = {
        "not_available": [A(wed_d, "WED-1700", tue.email)],
        "over_limit": [A(tue_d, "TUE-1500", one.email), A(wed_d, "WED-1700", one.email)],
        "overlap": [A(fri_d, "FRI-0900", friday.email), A(fri_d, "FRI-1100", friday.email)],
        "not_ready": [A(tue_d, "TUE-1500", unready.email)],
        "unknown_person": [A(tue_d, "TUE-1500", "stranger@example.com")],
        "unknown_shift": [A(tue_d, "TUE-0800", tue.email)],
        "wrong_week": [A(date(2026, 11, 17), "TUE-1500", tue.email)],
        "wrong_day": [A(wed_d, "TUE-1500", tue.email)],
        "duplicate": [A(tue_d, "TUE-1500", tue.email), A(tue_d, "TUE-1500", tue.email)],
    }
    if code == "overfilled":
        # Two different people on a 1-person shift.
        other = make_person("Fri Two", "FRI-0900", [overlap_a, overlap_b])
        data = make_data(shifts, [sat_ok, one, tue, unready, friday, other])
        cases["overfilled"] = [A(fri_d, "FRI-0900", friday.email), A(fri_d, "FRI-0900", other.email)]
    if code == "closed_date":
        s = settings(closed_dates=frozenset({sat_d}))
        cases["closed_date"] = [A(sat_d, "SAT-0900", sat_ok.email)]
    if code == "back_to_back":
        s = settings(allow_back_to_back_shifts=False)
        cases["back_to_back"] = [A(sat_d, "SAT-0900", sat_ok.email), A(sat_d, "SAT-1200", sat_ok.email)]
    return data, s, cases[code]


@pytest.mark.parametrize("code", [
    "not_available", "over_limit", "overlap", "back_to_back", "overfilled", "closed_date",
    "not_ready", "unknown_person", "unknown_shift", "wrong_week", "wrong_day", "duplicate",
])
def test_checker_catches(code):
    data, s, assignments = _checker_case(code)
    codes = [f.code for f in broken(check(data, s, WEEK, assignments))]
    assert code in codes


def test_checker_reports_unmet_goals():
    data = make_data([WED], [make_person("New", "WED-1700", REAL_SHIFTS)])
    findings = check(data, settings(), WEEK, [Assignment(date(2026, 11, 11), "WED-1700", "new@example.com")])
    assert {f.code for f in findings} == {"unfilled", "no_experienced"}
    assert not broken(findings)


# --- random scenarios: solver output always passes the checker -----------------

@pytest.mark.parametrize("seed", range(40))
def test_random_scenarios_never_break_rules(seed):
    rng = random.Random(seed)
    data = random_scenario(rng, REAL_SHIFTS, rng.randint(2, 25))
    s = settings(allow_back_to_back_shifts=rng.random() < 0.5,
                 closed_dates=frozenset({date(2026, 11, 12)}) if rng.random() < 0.3 else frozenset())
    draft = schedule(data, s, WEEK)
    assert not broken(check(data, s, WEEK, draft.assignments))


# --- brute force: on tiny cases the solver finds the best possible result -------

def score(data, s, assignments):
    """(experienced-cover count, slots filled) for a rule-abiding assignment list."""
    findings = check(data, s, WEEK, assignments)
    if broken(findings):
        return None
    covered = sum(1 for sh in data.shifts if sh.needs_experienced) - \
        sum(1 for f in findings if f.code == "no_experienced")
    return covered, len(assignments)


@pytest.mark.parametrize("seed", range(12))
def test_solver_matches_brute_force_on_tiny_cases(seed):
    rng = random.Random(1000 + seed)
    shifts = [make_shift("TUE-1500", "Tuesday", 15, 17, rng.randint(1, 2), experienced=rng.random() < 0.5),
              make_shift("SAT-0900", "Saturday", 9, 12, rng.randint(1, 2), experienced=True),
              make_shift("SAT-1200", "Saturday", 12, 15, rng.randint(1, 2), experienced=rng.random() < 0.5)]
    data = random_scenario(rng, shifts, 4)
    s = settings(allow_back_to_back_shifts=rng.random() < 0.5)
    dates = {"TUE-1500": date(2026, 11, 10), "SAT-0900": date(2026, 11, 14), "SAT-1200": date(2026, 11, 14)}
    options = [Assignment(dates[sh.id], sh.id, v.email) for v in data.volunteers for sh in shifts
               if v.reading.allows(sh.id, dates[sh.id])]
    best = max(
        (sc for r in range(len(options) + 1) for combo in itertools.combinations(options, r)
         if (sc := score(data, s, list(combo))) is not None),
    )
    draft = schedule(data, s, WEEK)
    assert score(data, s, draft.assignments) == best
