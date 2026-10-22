"""Phase 4: fair counts, preferences, tie-break, and reasons for gaps."""

import copy
import dataclasses
import random
import shutil
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from builders import (REAL_SHIFTS, SAT_AM, SAT_PM, TUE, WED, WEEK, make_data, make_person, make_shift,
                      random_scenario, settings)
from scheduler.checker import BROKEN, UNMET, check
from scheduler.reasons import explain_gaps
from scheduler.review_file import apply_reviews
from scheduler.signups import read_signups
from scheduler.solver import Assignment, schedule

PROJECT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "signups_fake.xlsx"


@pytest.fixture(scope="module")
def fake(tmp_path_factory):
    folder = tmp_path_factory.mktemp("fake")
    shutil.copy(FIXTURE, folder / "signups.xlsx")
    data = read_signups(folder / "signups.xlsx")
    apply_reviews(data, today=date(2026, 10, 22))
    return data


def no_experienced_count(findings):
    return sum(f.code == "no_experienced" for f in findings)


def unfair_swaps(data, s, week, assignments):
    """Shifts held by someone with 2+ shifts that an available person with 0 could take
    instead, without breaking a rule or losing experienced cover. Should be none."""
    counts = Counter(a.email for a in assignments)
    base = no_experienced_count(check(data, s, week, assignments))
    zero = [v for v in data.volunteers
            if v.status == "ready" and (v.max_per_week or 0) > 0 and counts[v.email] == 0]
    swaps = []
    for a in assignments:
        if counts[a.email] < 2:
            continue
        for z in zero:
            if not z.reading.allows(a.shift_id, a.date):
                continue
            swapped = [b for b in assignments if b != a] + [Assignment(a.date, a.shift_id, z.email)]
            findings = check(data, s, week, swapped)
            if not any(f.level == BROKEN for f in findings) and no_experienced_count(findings) <= base:
                swaps.append((a.shift_id, a.email, z.email))
    return swaps


# --- fair counts -----------------------------------------------------------------

def test_fake_week_spreads_shifts_one_each(fake):
    draft = schedule(fake, settings(), WEEK)
    counts = Counter(a.email for a in draft.assignments)
    assert len(draft.assignments) == 13 and set(counts.values()) == {1}
    assert check(fake, settings(), WEEK, draft.assignments) == []


@pytest.mark.parametrize("week", [WEEK, date(2026, 11, 16), date(2026, 11, 23), date(2026, 11, 30)])
def test_fake_weeks_have_no_unfair_swaps(fake, week):
    draft = schedule(fake, settings(), week)
    assert unfair_swaps(fake, settings(), week, draft.assignments) == []


@pytest.mark.parametrize("seed", range(40))
def test_random_scenarios_have_no_unfair_swaps(seed):
    rng = random.Random(500 + seed)
    data = random_scenario(rng, REAL_SHIFTS, rng.randint(3, 25))
    for v in data.volunteers:
        v.preferred_ids = frozenset(i for i in v.reading.shift_ids if rng.random() < 0.5)
    s = settings(allow_back_to_back_shifts=rng.random() < 0.5)
    draft = schedule(data, s, WEEK)
    assert not [f for f in check(data, s, WEEK, draft.assignments) if f.level == BROKEN]
    assert unfair_swaps(data, s, WEEK, draft.assignments) == []


def test_two_and_two_beats_three_and_one():
    """Four slots, two people who can each do all of them: 2 each, not 3 and 1."""
    shifts = [make_shift(f"SAT-{h:02d}00", "Saturday", h, h + 1, 1) for h in (9, 11, 13, 15)]
    ids = ", ".join(s.id for s in shifts)
    people = [make_person("Ann", ids, shifts, limit=3), make_person("Ben", ids, shifts, limit=3)]
    draft = schedule(make_data(shifts, people), settings(), WEEK)
    assert sorted(Counter(a.email for a in draft.assignments).values()) == [2, 2]


# --- preferences -----------------------------------------------------------------

def test_preferred_shift_is_given_when_there_is_a_choice():
    pam = make_person("Pam", "SAT-0900, SAT-1200", REAL_SHIFTS, experienced=True)
    pam.preferred_ids = frozenset({"SAT-1200"})
    quinn = make_person("Quinn", "SAT-0900, SAT-1200", REAL_SHIFTS, experienced=True)
    shifts = [make_shift("SAT-0900", "Saturday", 9, 12, 1), make_shift("SAT-1200", "Saturday", 12, 15, 1)]
    for week in (WEEK, date(2026, 11, 16), date(2026, 11, 23)):
        draft = schedule(make_data(shifts, [pam, quinn]), settings(), week)
        assert Assignment(week + (date(2026, 11, 14) - WEEK), "SAT-1200", pam.email) in draft.assignments


def test_preferences_never_cost_coverage_or_experienced_cover():
    """Vet prefers the shift that doesn't need them; they go where they're needed."""
    needs_exp = make_shift("WED-1700", "Wednesday", 17, 19, 1, experienced=True)
    other = make_shift("THU-1500", "Thursday", 15, 17, 1)
    vet = make_person("Vet", "WED-1700, THU-1500", [needs_exp, other], experienced=True)
    vet.preferred_ids = frozenset({"THU-1500"})
    new = make_person("New", "WED-1700, THU-1500", [needs_exp, other])
    draft = schedule(make_data([needs_exp, other], [vet, new]), settings(), WEEK)
    assert {(a.shift_id, a.email.split("@")[0]) for a in draft.assignments} == {("WED-1700", "vet"), ("THU-1500", "new")}


def _fairness_vs_preference():
    s1 = make_shift("TUE-1500", "Tuesday", 15, 17, 1)
    s2 = make_shift("THU-1500", "Thursday", 15, 17, 1)
    keen = make_person("Keen", "TUE-1500, THU-1500", [s1, s2], limit=2)
    keen.preferred_ids = frozenset({"TUE-1500", "THU-1500"})
    other = make_person("Other", "THU-1500", [s1, s2])
    return make_data([s1, s2], [keen, other])


def test_fair_counts_come_before_preferences_by_default():
    draft = schedule(_fairness_vs_preference(), settings(), WEEK)
    assert Counter(a.email.split("@")[0] for a in draft.assignments) == {"keen": 1, "other": 1}


def test_setting_can_put_preferences_first():
    draft = schedule(_fairness_vs_preference(), settings(fair_counts_before_preferences=False), WEEK)
    assert Counter(a.email.split("@")[0] for a in draft.assignments) == {"keen": 2}


# --- tie-break ---------------------------------------------------------------------

def test_tie_break_is_repeatable_but_rotates_by_week():
    twins = [make_person(f"Twin {n}", "TUE-1500", REAL_SHIFTS) for n in "ABCD"]
    one_slot = make_shift("TUE-1500", "Tuesday", 15, 17, 1)
    data = make_data([one_slot], twins)
    weeks = [WEEK + (date(2026, 11, 16) - WEEK) * k for k in range(12)]
    picks = []
    for w in weeks:
        first = schedule(data, settings(), w).assignments
        assert schedule(data, settings(), w).assignments == first     # repeatable
        picks.append(first[0].email)
    assert len(set(picks)) >= 3                                          # rotates


# --- reasons for gaps ----------------------------------------------------------------

def gap_texts(data, s=None, week=WEEK):
    s = s or settings()
    return [g.text for g in explain_gaps(data, s, schedule(data, s, week))]


def test_reason_weekly_limit():
    busy = make_person("Busy Bee", "TUE-1500, WED-1700", REAL_SHIFTS, limit=1, experienced=True)
    texts = gap_texts(make_data([TUE, WED], [busy]))
    tue = next(t for t in texts if t.startswith("TUE-1500"))
    assert "is 2 short: 1 person is available" in tue
    assert "Busy Bee is at their weekly limit (1 shift)" in tue


def test_reason_back_to_back_off():
    sam = make_person("Sat Sam", "SAT-0900, SAT-1200", REAL_SHIFTS, limit=2, experienced=True)
    texts = gap_texts(make_data([SAT_AM, SAT_PM], [sam]), settings(allow_back_to_back_shifts=False))
    assert any("back-to-back shifts are off" in t for t in texts)


def test_reason_date_exception():
    bailey = make_person("Bailey Sample", "SAT-0900 except 2026-11-14", REAL_SHIFTS)
    texts = gap_texts(make_data([SAT_AM], [bailey]))
    assert texts[0].startswith("SAT-0900 (Nov 14) is 3 short: nobody is available.")
    assert "Bailey Sample can't do Nov 14." in texts[0]


def test_reason_names_unconfirmed_answers_that_may_include_the_shift(fake):
    # Fake data with Thursday tutoring needing 8 people, so it's short.
    data = copy.deepcopy(fake)
    data.shifts = [dataclasses.replace(s, needs=8) if s.id == "THU-1500" else s for s in data.shifts]
    text = next(t for t in gap_texts(data, week=date(2026, 11, 23)) if t.startswith("THU-1500"))
    assert "Harper Demo's answer may include it but isn't confirmed yet" in text
    assert "Sam Prototype" not in text        # "Thursdays. Not Nov 26": excluded that date


def test_reason_names_sign_ups_with_problems():
    lim = make_person("Lim Itless", "TUE-1500", REAL_SHIFTS)
    lim.problems.append('Most shifts per week is "two", which isn\'t a whole number.')
    text = gap_texts(make_data([TUE], [lim]))[0]
    assert "Lim Itless's sign-up has a problem (see check-input)" in text


def test_reason_no_experienced():
    new = make_person("New Person", "WED-1700", REAL_SHIFTS)
    texts = gap_texts(make_data([WED], [new]))
    assert any(t.startswith("WED-1700 (Nov 11) has no experienced volunteer: no experienced person is available")
               for t in texts)


@pytest.mark.parametrize("seed", range(25))
def test_every_unmet_goal_has_a_reason(seed):
    rng = random.Random(900 + seed)
    data = random_scenario(rng, REAL_SHIFTS, rng.randint(1, 10))
    s = settings(allow_back_to_back_shifts=rng.random() < 0.5)
    draft = schedule(data, s, WEEK)
    unmet = [f for f in check(data, s, WEEK, draft.assignments) if f.level == UNMET]
    gaps = explain_gaps(data, s, draft)
    assert len(gaps) == len(unmet)
    assert not any("shouldn't happen" in g.text for g in gaps)


# --- command line ------------------------------------------------------------------

def test_draft_shows_preferences_and_fairness(tmp_path):
    shutil.copy(FIXTURE, tmp_path / "signups.xlsx")
    out = subprocess.run([sys.executable, "-m", "scheduler", "draft", "--week", "2026-11-09",
                          "--file", str(tmp_path / "signups.xlsx")], cwd=PROJECT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "Casey Placeholder ★ ♥" in out.stdout
    assert "FAIRNESS: 13 of 19 ready volunteers are scheduled this week." in out.stdout
    assert "PREFERENCES: 13 of 13" in out.stdout
