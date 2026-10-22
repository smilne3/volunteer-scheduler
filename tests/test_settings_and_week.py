"""Phase 3: settings.json and week handling."""

import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from builders import REAL_SHIFTS
from scheduler.errors import InputError
from scheduler.settings import Settings, load_settings
from scheduler.week import next_monday, parse_week, week_slots

PROJECT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "signups_fake.xlsx"


def write_settings(folder, values):
    (folder / "settings.json").write_text(json.dumps(values))
    return load_settings(folder)


def test_missing_settings_file_uses_defaults(tmp_path):
    s = load_settings(tmp_path)
    assert s == Settings()
    assert "defaults were used" in s.notes[0]


def test_example_settings_file_is_valid():
    s = load_settings_from_example()
    assert s.timezone == "America/New_York" and s.allow_back_to_back_shifts


def load_settings_from_example():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        shutil.copy(PROJECT / "settings.example.json", Path(d) / "settings.json")
        return load_settings(Path(d))


def test_settings_values_are_read(tmp_path):
    s = write_settings(tmp_path, {
        "closed_dates": ["2026-11-26"], "extra_experienced_emails": ["Pat@Example.com"],
        "allow_back_to_back_shifts": False, "timezone": "America/Chicago",
    })
    assert s.closed_dates == {date(2026, 11, 26)}
    assert s.extra_experienced_emails == {"pat@example.com"}
    assert s.allow_back_to_back_shifts is False and s.timezone == "America/Chicago"


@pytest.mark.parametrize("values, message", [
    ({"closed_date": []}, "unknown setting(s) closed_date"),
    ({"closed_dates": ["Nov 26"]}, '"Nov 26", which isn\'t a date'),
    ({"closed_dates": "2026-11-26"}, "closed_dates should be a list"),
    ({"timezone": "Eastern"}, 'timezone "Eastern" isn\'t a known timezone'),
    ({"allow_back_to_back_shifts": "false"}, "should be true or false (no quotes)"),
    ({"extra_experienced_emails": ["pat"]}, "list of email addresses"),
    ({"fairness_lookback_weeks": -1}, "whole number, 0 or more"),
])
def test_bad_settings_are_explained(tmp_path, values, message):
    with pytest.raises(InputError) as e:
        write_settings(tmp_path, values)
    assert message in str(e.value)


def test_settings_that_are_not_json(tmp_path):
    (tmp_path / "settings.json").write_text('{"closed_dates": [2026-11-26]}')
    with pytest.raises(InputError) as e:
        load_settings(tmp_path)
    assert "isn't valid JSON" in str(e.value)


def test_default_week_is_next_monday():
    assert next_monday(date(2026, 10, 22)) == date(2026, 10, 26)      # Thursday
    assert next_monday(date(2026, 10, 26)) == date(2026, 11, 2)       # a Monday: the following one
    assert parse_week(None, date(2026, 10, 22)) == date(2026, 10, 26)


@pytest.mark.parametrize("text, message", [
    ("2026-11-10", "is a Tuesday. Weeks start on Monday: use --week 2026-11-09"),
    ("next week", "isn't a date"),
])
def test_bad_week(text, message):
    with pytest.raises(InputError) as e:
        parse_week(text, date(2026, 10, 22))
    assert message in str(e.value)


def test_week_slots_are_dated_and_ordered():
    open_slots, closed = week_slots(REAL_SHIFTS, date(2026, 11, 23), frozenset({date(2026, 11, 26)}))
    assert [(s.shift.id, s.date.day) for s in open_slots] == [
        ("TUE-1500", 24), ("WED-1700", 25), ("SAT-0900", 28), ("SAT-1200", 28)]
    assert [(s.shift.id, s.date.day) for s in closed] == [("THU-1500", 26)]


def run(*args):
    return subprocess.run([sys.executable, "-m", "scheduler", *args], cwd=PROJECT, capture_output=True, text=True)


def test_draft_command(tmp_path):
    shutil.copy(FIXTURE, tmp_path / "signups.xlsx")
    result = run("draft", "--week", "2026-11-09", "--file", str(tmp_path / "signups.xlsx"))
    assert result.returncode == 0, result.stderr
    assert "DRAFT, NOT APPROVED: week of Monday 2026-11-09" in result.stdout
    assert "CHECK: no rules broken." in result.stdout
    assert "Sat Nov 14  SAT-0900  3/3" in result.stdout


def test_draft_with_closed_date(tmp_path):
    shutil.copy(FIXTURE, tmp_path / "signups.xlsx")
    (tmp_path / "settings.json").write_text('{"closed_dates": ["2026-11-26"]}')
    result = run("draft", "--week", "2026-11-23", "--file", str(tmp_path / "signups.xlsx"))
    assert result.returncode == 0, result.stderr
    assert "Thu Nov 26  THU-1500  CLOSED" in result.stdout


def test_draft_bad_week_is_plain_english(tmp_path):
    shutil.copy(FIXTURE, tmp_path / "signups.xlsx")
    result = run("draft", "--week", "2026-11-10", "--file", str(tmp_path / "signups.xlsx"))
    assert result.returncode == 1 and "use --week 2026-11-09" in result.stderr
    assert "Traceback" not in result.stderr
