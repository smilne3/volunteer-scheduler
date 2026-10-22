"""Phase 6: re-checking edits, approving, and the calendar file."""

import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

from builders import REAL_SHIFTS, SAT_AM, SAT_PM, TUE, WEEK, make_data, make_person, settings
from scheduler import commands
from scheduler.approval import APPROVED, CHANGED, DRAFT, approval_status
from scheduler.assignments_file import read_assignments
from scheduler.calendar_file import event_titles, render_ics
from scheduler.errors import InputError
from scheduler.signups import read_signups
from scheduler.solver import Assignment, draft_from, schedule

PROJECT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "signups_fake.xlsx"
TODAY = date(2026, 10, 22)
NOW = datetime(2026, 10, 22, 16, 0)
W = "2026-11-09"


@pytest.fixture
def folder(tmp_path):
    shutil.copy(FIXTURE, tmp_path / "signups.xlsx")
    return tmp_path


def week_dir(folder, week=W):
    return folder / "weeks" / week


def do_draft(folder, week=W, recheck=False):
    return commands.draft(folder / "signups.xlsx", week, TODAY, NOW, recheck=recheck, replace=False, open_page=False)


def do_approve(folder, answer=None, week=W):
    asked = []

    def ask(prompt):
        asked.append(prompt)
        if answer is None:
            raise EOFError
        return answer
    code = commands.approve(folder / "signups.xlsx", week, TODAY, NOW, ask=ask)
    return code, asked


def edit_csv(folder, change, week=W):
    path = week_dir(folder, week) / "assignments.csv"
    text = path.read_text(encoding="utf-8-sig")
    path.write_text(change(text), encoding="utf-8-sig")


def drop_rows_with(needle):
    return lambda text: "".join(l for l in text.splitlines(True) if needle not in l)


# --- approve -------------------------------------------------------------------

def test_clean_week_approves_without_asking(folder, capsys):
    do_draft(folder)
    code, asked = do_approve(folder)
    assert code == 0 and asked == []
    d = week_dir(folder)
    assert (d / "calendar.ics").exists()
    assert approval_status(d).status == APPROVED
    assert "APPROVED Oct 22 at 4:00 PM. calendar.ics is ready to import." in (d / "review.html").read_text()
    out = capsys.readouterr().out
    assert "Import & export" in out and "Nothing was sent to anyone." in out


def test_broken_edit_is_refused(folder, capsys):
    do_draft(folder)
    edit_csv(folder, lambda t: t.replace("Lee Fictional,lee.fictional@example.com", "Gale Dummy,gale.dummy@example.com"))
    code, asked = do_approve(folder, answer="yes")
    assert code == 2 and asked == []
    assert not (week_dir(folder) / "calendar.ics").exists()
    assert not (week_dir(folder) / "APPROVED").exists()
    assert "Gale Dummy on TUE-1500 (Tue Nov 10): they aren't available then." in capsys.readouterr().out


def test_unreadable_row_is_refused(folder):
    do_draft(folder)
    edit_csv(folder, lambda t: t.replace("lee.fictional@example.com", "lee@nowhere.example"))
    code, _ = do_approve(folder, answer="yes")
    assert code == 2 and not (week_dir(folder) / "calendar.ics").exists()


@pytest.mark.parametrize("answer, approved", [("no", False), ("", False), (None, False), ("yes", True), (" YES ", True)])
def test_gaps_need_a_typed_yes(folder, answer, approved):
    do_draft(folder)
    edit_csv(folder, drop_rows_with("lee.fictional"))           # Tuesday now 1 short
    code, asked = do_approve(folder, answer=answer)
    assert asked == ["Type yes to approve it anyway: "]
    assert (code == 0) == approved
    assert (week_dir(folder) / "calendar.ics").exists() == approved


def test_already_approved_and_unchanged_is_a_no_op(folder):
    do_draft(folder)
    do_approve(folder)
    ics = (week_dir(folder) / "calendar.ics").read_bytes()
    code, asked = do_approve(folder)
    assert code == 0 and asked == []
    assert (week_dir(folder) / "calendar.ics").read_bytes() == ics


def test_change_after_approval_needs_approving_again(folder):
    do_draft(folder)
    do_approve(folder)
    edit_csv(folder, drop_rows_with("lee.fictional"))
    assert approval_status(week_dir(folder)).status == CHANGED
    do_draft(folder, recheck=True)
    assert "CHANGED SINCE APPROVAL" in (week_dir(folder) / "review.html").read_text()
    code, _ = do_approve(folder, answer="yes")
    assert code == 0
    status = approval_status(week_dir(folder))
    assert status.status == APPROVED and status.sequence == 2
    assert b"SEQUENCE:2" in (week_dir(folder) / "calendar.ics").read_bytes()


def test_approve_without_a_draft(folder):
    with pytest.raises(InputError) as e:
        do_approve(folder)
    assert "no draft for the week of 2026-11-09 yet" in str(e.value)


def test_approved_week_is_not_redrafted(folder):
    do_draft(folder)
    do_approve(folder)
    with pytest.raises(InputError) as e:
        do_draft(folder)
    assert "--recheck" in str(e.value)


def test_unreadable_marker_counts_as_changed(folder):
    do_draft(folder)
    do_approve(folder)
    (week_dir(folder) / "APPROVED").write_text("not json")
    assert approval_status(week_dir(folder)).status == CHANGED


# --- recheck --------------------------------------------------------------------

def test_recheck_reports_broken_edits_and_refreshes_the_page(folder):
    do_draft(folder)
    edit_csv(folder, lambda t: t.replace("Lee Fictional,lee.fictional@example.com", "Gale Dummy,gale.dummy@example.com"))
    assert do_draft(folder, recheck=True) == 2
    page = (week_dir(folder) / "review.html").read_text()
    assert "Rule broken. Don't use this draft." in page and "your edited assignments.csv" in page


def test_recheck_gap_reason_groups_free_people(folder, capsys):
    do_draft(folder)
    edit_csv(folder, drop_rows_with("lee.fictional"))
    do_draft(folder, recheck=True)
    out = capsys.readouterr().out
    assert "Available and free: " in out and "shouldn't happen" not in out


# --- reading assignments.csv ------------------------------------------------------

def test_read_back_what_draft_wrote(folder):
    do_draft(folder)
    data = read_signups(folder / "signups.xlsx")
    assignments, problems = read_assignments(week_dir(folder) / "assignments.csv", data)
    assert problems == [] and len(assignments) == 13


@pytest.mark.parametrize("row, problem", [
    ("2026-11-10,Tue,TUE-1500,,Lee Fictional,", None),                       # name only: matched
    ("11/10/26,Tue,TUE-1500,,lee fictional,", None),                          # Excel-style date, any case
    ("2026-11-10,Tue,,Tuesday Tutoring 3pm–5pm,Lee Fictional,", None),       # shift name instead of ID
    ("Nov 10,Tue,TUE-1500,,Lee Fictional,", "isn't a date"),
    ("2026-11-10,Tue,TUE-9999,,Lee Fictional,", 'shift_id "TUE-9999"'),
    ("2026-11-10,Tue,TUE-1500,,Lee Fictionl,", "doesn't match a volunteer's name"),
    ("2026-11-10,Tue,TUE-1500,,Someone,someone@else.example", "isn't a volunteer in the sign-ups"),
])
def test_hand_typed_rows(folder, row, problem):
    data = read_signups(folder / "signups.xlsx")
    path = folder / "assignments.csv"
    path.write_text("date,day,shift_id,shift,name,email\n" + row + "\n,,,,,\n", encoding="utf-8")
    assignments, problems = read_assignments(path, data)
    if problem is None:
        assert problems == [] and assignments == [Assignment(date(2026, 11, 10), "TUE-1500", "lee.fictional@example.com")]
    else:
        assert len(problems) == 1 and problem in problems[0] and assignments == []


def test_assignments_saved_by_excel_in_windows_encoding(folder):
    data = read_signups(folder / "signups.xlsx")
    path = folder / "assignments.csv"
    path.write_bytes("date,day,shift_id,shift,name,email\r\n2026-11-14,Sat,SAT-0900,Saturday Food Pantry 9am–12pm,"
                     "Alex Example,alex.example@example.com\r\n".encode("cp1252"))
    assignments, problems = read_assignments(path, data)
    assert problems == [] and len(assignments) == 1


def test_missing_column(folder):
    data = read_signups(folder / "signups.xlsx")
    (folder / "assignments.csv").write_text("date,shift_id,name\n")
    with pytest.raises(InputError) as e:
        read_assignments(folder / "assignments.csv", data)
    assert "missing the column(s): email" in str(e.value)


# --- the calendar file -------------------------------------------------------------

def ics_for(data, s=None, week=WEEK, approved_at=datetime(2026, 10, 22, 20, 0).astimezone(), sequence=1,
            assignments=None):
    s = s or settings()
    d = schedule(data, s, week) if assignments is None else draft_from(data, s, week, assignments)
    return render_ics(data, s, d, approved_at, sequence)


def unfold(raw: bytes):
    return raw.decode("utf-8").replace("\r\n ", "").split("\r\n")


def events(raw: bytes):
    out, cur = [], None
    for line in unfold(raw):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            out.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            k, v = line.split(":", 1)
            cur[k] = v
    return out


@pytest.fixture(scope="module")
def fake_data(tmp_path_factory):
    from scheduler.review_file import apply_reviews
    folder = tmp_path_factory.mktemp("cal")
    shutil.copy(FIXTURE, folder / "signups.xlsx")
    data = read_signups(folder / "signups.xlsx")
    apply_reviews(data, today=TODAY)
    return data


def test_ics_structure_follows_the_format(fake_data):
    raw = ics_for(fake_data)
    assert raw.startswith(b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\n") and raw.endswith(b"END:VCALENDAR\r\n")
    lines = raw.split(b"\r\n")[:-1]
    assert all(len(line) <= 75 for line in lines)                 # folded at 75 octets
    assert b"\n" not in raw.replace(b"\r\n", b"")                  # CRLF only
    raw.decode("utf-8")                                            # folding never split a character
    evs = events(raw)
    assert len(evs) == 5
    for ev in evs:
        for key in ("UID", "DTSTAMP", "DTSTART", "DTEND", "SUMMARY", "SEQUENCE"):
            assert key in ev
        assert re.fullmatch(r"\d{8}T\d{6}Z", ev["DTSTART"])
    assert len({ev["UID"] for ev in evs}) == 5


def test_ics_never_invites_or_contains_contact_details(fake_data):
    raw = ics_for(fake_data)
    text = "\n".join(unfold(raw))
    for forbidden in ("ATTENDEE", "ORGANIZER", "mailto:", "VALARM"):
        assert forbidden not in text
    for v in fake_data.volunteers:
        assert v.email not in text
        if v.phone:
            assert v.phone not in text


def test_ics_titles_and_names(fake_data):
    titles = event_titles(fake_data.shifts)
    assert titles == {"TUE-1500": "Tutoring", "WED-1700": "Phone Bank", "THU-1500": "Tutoring",
                      "SAT-0900": "Food Pantry (AM)", "SAT-1200": "Food Pantry (PM)"}
    summaries = [ev["SUMMARY"] for ev in events(ics_for(fake_data))]
    assert "Food Pantry (AM): Alex\\, Indy\\, Uma" in summaries


@pytest.mark.parametrize("week, shift_id, utc", [
    (WEEK, "TUE-1500", "20261110T200000Z"),                    # EST: 3pm = 20:00 UTC
    (date(2026, 10, 26), "SAT-0900", "20261031T130000Z"),     # still EDT on Oct 31: 9am = 13:00 UTC
    (WEEK, "SAT-0900", "20261114T140000Z"),                   # after DST ends Nov 1: 9am = 14:00 UTC
])
def test_ics_times_convert_to_utc_across_daylight_saving(fake_data, week, shift_id, utc):
    ev = next(e for e in events(ics_for(fake_data, week=week)) if shift_id in e["UID"])
    assert ev["DTSTART"] == utc


def test_ics_uses_the_timezone_setting(fake_data):
    ev = next(e for e in events(ics_for(fake_data, s=settings(timezone="America/Chicago"))) if "TUE-1500" in e["UID"])
    assert ev["DTSTART"] == "20261110T210000Z"


def test_ics_open_spots_shared_first_names_and_escaping():
    p1 = make_person("Sam Smith", "SAT-0900", REAL_SHIFTS, experienced=True)
    p2 = make_person("Sam Jones", "SAT-0900", REAL_SHIFTS)
    p3 = make_person("Kim Lee, Jr; III", "SAT-1200", REAL_SHIFTS)
    data = make_data([SAT_AM, SAT_PM, TUE], [p1, p2, p3])
    sat = date(2026, 11, 14)
    evs = {e["UID"].split("-", 3)[3].split("@")[0]: e for e in events(ics_for(
        data, assignments=[Assignment(sat, "SAT-0900", p1.email), Assignment(sat, "SAT-0900", p2.email),
                           Assignment(sat, "SAT-1200", p3.email)]))}
    assert evs["SAT-0900"]["SUMMARY"] == "Food Pantry (AM): Sam Jones\\, Sam Smith (1 open)"
    assert evs["SAT-1200"]["SUMMARY"] == "Food Pantry (PM): Kim (2 open)"
    assert "Kim Lee\\, Jr\\; III" in evs["SAT-1200"]["DESCRIPTION"]
    assert evs["TUE-1500"]["SUMMARY"] == "Tutoring: nobody yet (2 open)"


def test_ics_skips_closed_dates(fake_data):
    evs = events(ics_for(fake_data, s=settings(closed_dates=frozenset({date(2026, 11, 14)}))))
    assert not any("SAT" in e["UID"] for e in evs) and len(evs) == 3


def test_ics_uid_is_stable_and_sequence_counts_approvals(fake_data):
    a, b = events(ics_for(fake_data, sequence=1)), events(ics_for(fake_data, sequence=2))
    assert [e["UID"] for e in a] == [e["UID"] for e in b]
    assert {e["SEQUENCE"] for e in b} == {"2"}


# --- command line -------------------------------------------------------------------

def test_approve_command_line(folder):
    run = lambda *a, **kw: subprocess.run([sys.executable, "-m", "scheduler", *a, "--file", str(folder / "signups.xlsx")],  # noqa: E731
                                          cwd=PROJECT, capture_output=True, text=True, **kw)
    assert run("draft", "--week", W, "--no-open").returncode == 0
    result = run("approve", "--week", W, input="")
    assert result.returncode == 0, result.stderr
    marker = json.loads((week_dir(folder) / "APPROVED").read_text())
    assert marker["slots_filled"] == 13 and marker["sequence"] == 1
