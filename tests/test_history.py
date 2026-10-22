"""Phase 7: fairness across weeks, from approved weeks only."""

import os
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from builders import REAL_SHIFTS, TUE, WED, WEEK, make_data, make_person, make_shift, settings
from scheduler import commands
from scheduler.__main__ import data_folder
from scheduler.approval import write_marker
from scheduler.history import apply_experience_from_history, load_history
from scheduler.signups import read_signups
from scheduler.solver import schedule

PROJECT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "signups_fake.xlsx"
WEEKS = [date(2026, 11, 9) + timedelta(weeks=k) for k in range(4)]
NOW = datetime(2026, 10, 22, 16, 0)


@pytest.fixture
def folder(tmp_path):
    shutil.copy(FIXTURE, tmp_path / "signups.xlsx")
    return tmp_path


def run_week(folder, week, today=date(2026, 10, 22)):
    path = folder / "signups.xlsx"
    assert commands.draft(path, week.isoformat(), today, NOW, recheck=False, replace=False, open_page=False) == 0
    assert commands.approve(path, week.isoformat(), today, NOW, ask=lambda _: "yes") == 0


def scheduled(folder, week):
    import csv
    rows = csv.DictReader(open(folder / "weeks" / week.isoformat() / "assignments.csv", encoding="utf-8-sig"))
    return {r["email"] for r in rows if r["email"]}


# --- four weeks on the fake data --------------------------------------------------

@pytest.fixture(scope="module")
def four_weeks(tmp_path_factory):
    folder = tmp_path_factory.mktemp("four")
    shutil.copy(FIXTURE, folder / "signups.xlsx")
    for w in WEEKS:
        run_week(folder, w)
    data = read_signups(folder / "signups.xlsx")
    ready = {v.email for v in data.volunteers if v.status == "ready"}
    return folder, ready, [scheduled(folder, w) for w in WEEKS]


def test_people_who_waited_move_up_the_next_week(four_weeks):
    folder, ready, weeks = four_weeks
    waited_week1 = ready - weeks[0]
    assert len(waited_week1) == 6
    assert waited_week1 <= weeks[1]          # every one of them gets a shift in week 2


def test_nobody_waits_three_weeks_while_others_work_every_week(four_weeks):
    _, ready, weeks = four_weeks
    every_week = set.intersection(*weeks)
    for email in ready:
        streak = longest = 0
        for w in weeks:
            streak = 0 if email in w else streak + 1
            longest = max(longest, streak)
        assert not (longest >= 3 and every_week), email


def test_shifts_even_out_over_four_weeks(four_weeks):
    _, ready, weeks = four_weeks
    totals = [sum(email in w for w in weeks) for email in ready]
    assert max(totals) - min(totals) <= 1


def test_review_page_shows_weeks_since_last_shift(four_weeks):
    folder, _, _ = four_weeks
    page = (folder / "weeks" / WEEKS[1].isoformat() / "review.html").read_text()
    assert "(last shift last week)" in page
    assert "people with fewer shifts in approved weeks (Nov 9) were given shifts first" in page


# --- what counts as history ---------------------------------------------------------

def make_week(folder, monday, rows, approve=True):
    """Write weeks/<monday>/assignments.csv with (day offset, shift_id, email) rows."""
    d = folder / "weeks" / monday.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    lines = ["date,day,shift_id,shift,name,email"]
    lines += [f"{(monday + timedelta(days=off)).isoformat()},,{sid},,,{email}" for off, sid, email in rows]
    (d / "assignments.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if approve:
        write_marker(d, datetime(2026, 10, 1, 12, 0).astimezone(), 1, len(rows), len(rows))
    return d


ALEX, LEE = "alex.example@example.com", "lee.fictional@example.com"


def test_only_approved_unchanged_weeks_in_the_window_count(folder):
    data = read_signups(folder / "signups.xlsx")
    target = date(2026, 11, 30)
    make_week(folder, date(2026, 11, 23), [(5, "SAT-0900", ALEX)])                    # 1 week before: counts
    make_week(folder, date(2026, 11, 2), [(5, "SAT-0900", ALEX)])                     # 4 weeks before: counts
    make_week(folder, date(2026, 10, 26), [(5, "SAT-0900", ALEX)])                    # 5 weeks before: too old
    make_week(folder, date(2026, 11, 16), [(1, "TUE-1500", LEE)], approve=False)      # not approved
    changed = make_week(folder, date(2026, 11, 9), [(1, "TUE-1500", LEE)])
    (changed / "assignments.csv").write_text((changed / "assignments.csv").read_text() + "\n")  # edited later
    make_week(folder, date(2026, 12, 7), [(1, "TUE-1500", LEE)])                      # after the target week
    (folder / "weeks" / "notes").mkdir()                                                # not a week folder
    h = load_history(folder, data, target, 4, today=date(2026, 11, 1))
    assert h.recent == {ALEX: 2}
    assert h.weeks_counted == [date(2026, 11, 2), date(2026, 11, 23)]
    assert LEE not in h.last_shift
    assert h.last_shift[ALEX] == date(2026, 11, 28)
    assert any("2026-11-09 was changed after approval" in n for n in h.skipped)
    assert h.weeks_waiting(ALEX, target) == 1


def test_lookback_zero_turns_off_fairness_across_weeks(folder):
    data = read_signups(folder / "signups.xlsx")
    make_week(folder, date(2026, 11, 23), [(5, "SAT-0900", ALEX)])
    h = load_history(folder, data, date(2026, 11, 30), 0, today=date(2026, 11, 1))
    assert h.recent == {}


def test_worked_means_an_approved_shift_before_today(folder):
    data = read_signups(folder / "signups.xlsx")
    make_week(folder, date(2026, 11, 9), [(1, "TUE-1500", LEE), (5, "SAT-0900", ALEX)])
    h = load_history(folder, data, date(2026, 11, 16), 4, today=date(2026, 11, 12))   # Tue done, Sat not yet
    assert h.worked == {LEE}


# --- the solver uses history, but never ahead of the within-week rule ---------------

def test_fewer_recent_shifts_go_first():
    twins = [make_person(f"Twin {n}", "TUE-1500", REAL_SHIFTS) for n in "AB"]
    data = make_data([make_shift("TUE-1500", "Tuesday", 15, 17, 1)], twins)
    for k in range(6):
        week = WEEK + timedelta(weeks=k)
        got = schedule(data, settings(), week, recent={"twin.a@example.com": 2}).assignments
        assert [a.email for a in got] == ["twin.b@example.com"]


def test_within_week_spread_comes_before_history():
    shifts = [make_shift("TUE-1500", "Tuesday", 15, 17, 1), make_shift("THU-1500", "Thursday", 15, 17, 1)]
    busy = make_person("Busy", "TUE-1500, THU-1500", shifts, limit=2)
    fresh = make_person("Fresh", "TUE-1500, THU-1500", shifts, limit=2)
    got = schedule(make_data(shifts, [busy, fresh]), settings(), WEEK, recent={busy.email: 5}).assignments
    assert sorted(a.email.split("@")[0] for a in got) == ["busy", "fresh"]


def test_history_never_costs_experienced_cover():
    vet = make_person("Vet", "WED-1700", REAL_SHIFTS, experienced=True)
    new = make_person("New", "WED-1700", REAL_SHIFTS)
    one = make_shift("WED-1700", "Wednesday", 17, 19, 1, experienced=True)
    got = schedule(make_data([one], [vet, new]), settings(), WEEK, recent={vet.email: 4}).assignments
    assert [a.email for a in got] == [vet.email]


# --- count_approved_shifts_as_experience -------------------------------------------

def test_worked_shift_counts_as_experience_when_turned_on(folder):
    (folder / "settings.json").write_text('{"count_approved_shifts_as_experience": true}')
    run_week(folder, WEEKS[0])
    worked_week1 = scheduled(folder, WEEKS[0])
    path = folder / "signups.xlsx"
    commands.draft(path, WEEKS[1].isoformat(), date(2026, 11, 15), NOW, recheck=False, replace=False, open_page=False)
    page = (folder / "weeks" / WEEKS[1].isoformat() / "review.html").read_text()
    assert "Counted as experienced because they've worked an approved shift:" in page
    data = read_signups(path)
    h = load_history(folder, data, WEEKS[1], 4, today=date(2026, 11, 15))
    promoted = apply_experience_from_history(data, h)
    assert promoted and all(v.experienced for v in data.volunteers if v.email in worked_week1)


def test_experience_setting_is_off_by_default(folder):
    run_week(folder, WEEKS[0])
    commands.draft(folder / "signups.xlsx", WEEKS[1].isoformat(), date(2026, 11, 15), NOW,
                   recheck=False, replace=False, open_page=False)
    assert "Counted as experienced" not in (folder / "weeks" / WEEKS[1].isoformat() / "review.html").read_text()


# --- where the data lives ----------------------------------------------------------

def test_data_folder_default_and_override(monkeypatch, tmp_path):
    monkeypatch.delenv("VOLUNTEER_SCHEDULER_DATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert data_folder() == tmp_path / "volunteer-scheduler"
    monkeypatch.setenv("VOLUNTEER_SCHEDULER_DATA", str(tmp_path / "elsewhere"))
    assert data_folder() == tmp_path / "elsewhere"


def test_commands_use_the_data_folder_without_file(folder):
    env = {**os.environ, "VOLUNTEER_SCHEDULER_DATA": str(folder)}
    out = subprocess.run([sys.executable, "-m", "scheduler", "draft", "--week", "2026-11-09", "--no-open"],
                         cwd=PROJECT, capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    assert (folder / "weeks" / "2026-11-09" / "review.html").exists()
