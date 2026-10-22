"""Phase 5: the one-page review page and assignments.csv."""

import csv
import io
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, time
from pathlib import Path

import pytest
from openpyxl import load_workbook

from builders import REAL_SHIFTS, TUE, WED, WEEK, make_data, make_person, settings
from scheduler.checker import BROKEN, Finding, check
from scheduler.errors import InputError
from scheduler.reasons import explain_gaps
from scheduler.review_file import apply_reviews
from scheduler.review_page import (render_assignments_csv, render_review_page, time_range,
                                   write_week_files)
from scheduler.settings import load_settings
from scheduler.signups import read_signups
from scheduler.solver import schedule

PROJECT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "signups_fake.xlsx"
NOW = datetime(2026, 10, 22, 15, 30)
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def build(folder, week=WEEK):
    data = read_signups(folder / "signups.xlsx")
    review = apply_reviews(data, today=date(2026, 10, 22))
    s = load_settings(folder)
    draft = schedule(data, s, week)
    findings = check(data, s, week, draft.assignments)
    html = render_review_page(data, s, draft, findings, explain_gaps(data, s, draft), review, NOW)
    return data, s, draft, html


@pytest.fixture
def folder(tmp_path):
    shutil.copy(FIXTURE, tmp_path / "signups.xlsx")
    return tmp_path


def with_thursday_needing(folder, n):
    wb = load_workbook(folder / "signups.xlsx")
    assert wb["Shifts"]["B6"].value == "Thursday"
    wb["Shifts"]["D6"] = n
    wb.save(folder / "signups.xlsx")


# --- content ---------------------------------------------------------------

def test_sections_in_order_with_draft_banner(folder):
    _, _, _, html = build(folder)
    positions = [html.index(h) for h in ("DRAFT, NOT APPROVED", "1. Needs your attention", "2. The week",
                                         "3. Fairness", "4. Contact list")]
    assert positions == sorted(positions)
    assert "Nothing has been sent to anyone." in html


def test_fake_week_lists_unconfirmed_people_and_full_shifts(folder):
    _, _, _, html = build(folder)
    assert "Not scheduled: written availability not confirmed yet (11)." in html
    assert "Bailey Sample, Eli Fakename" in html
    assert 'class="bad"' not in html                      # no gaps, no broken rules
    assert "13 of 19</b> ready volunteers are scheduled" in html
    assert "Casey Placeholder ★ ♥" in html


def test_short_shift_is_red_and_at_the_top(folder):
    with_thursday_needing(folder, 8)
    _, _, _, html = build(folder, week=date(2026, 11, 23))
    gap = html.index('<li class="bad">THU-1500 (Nov 26) is 2 short')
    assert gap < html.index("2. The week")
    assert '<span class="open">2 open</span>' in html


def test_broken_rule_is_shown_first(folder):
    data, s, draft, _ = build(folder)
    bad = [Finding(BROKEN, "over_limit", "Casey Placeholder has 3 shifts but said at most 2 a week.")]
    html = render_review_page(data, s, draft, bad, [], None, NOW)
    assert "<b>Rule broken. Don't use this draft.</b> Casey Placeholder has 3 shifts" in html


def test_closed_dates_show_as_closed(folder):
    (folder / "settings.json").write_text('{"closed_dates": ["2026-11-26"]}')
    _, _, _, html = build(folder, week=date(2026, 11, 23))
    assert re.search(r'<tr class="closed"><td class="num">Thu Nov 26</td>', html)


def test_contact_list_has_only_scheduled_people(folder):
    data, _, draft, html = build(folder)
    contacts = html[html.index("4. Contact list"):]
    scheduled = {a.email for a in draft.assignments}
    for v in data.volunteers:
        if v.email in scheduled:
            assert v.email in contacts and v.phone in contacts
        else:
            assert v.email not in html and (not v.phone or v.phone not in html)


def test_form_text_is_escaped():
    sneaky = make_person("<script>alert(1)</script>", "TUE-1500", REAL_SHIFTS)
    sneaky.phone = "<b>555</b>"
    data = make_data([TUE], [sneaky])
    s = settings()
    draft = schedule(data, s, WEEK)
    html = render_review_page(data, s, draft, check(data, s, WEEK, draft.assignments),
                              explain_gaps(data, s, draft), None, NOW)
    assert "<script>alert" not in html and "<b>555</b>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


@pytest.mark.parametrize("start, end, text", [
    (time(15), time(17), "3–5 pm"),
    (time(9), time(12), "9 am–12 pm"),
    (time(12), time(15), "12–3 pm"),
    (time(10, 30), time(13), "10:30 am–1 pm"),
])
def test_time_range(start, end, text):
    assert time_range(start, end) == text


# --- assignments.csv ---------------------------------------------------------

def rows(csv_bytes):
    return list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))


def test_assignments_csv_has_people_and_open_spots():
    one = make_person("Only One", "TUE-1500", REAL_SHIFTS)
    data = make_data([TUE, WED], [one])
    draft = schedule(data, settings(), WEEK)
    got = rows(render_assignments_csv(data, draft))
    assert [(r["date"], r["shift_id"], r["name"], r["email"]) for r in got] == [
        ("2026-11-10", "TUE-1500", "Only One", "only.one@example.com"),
        ("2026-11-10", "TUE-1500", "", ""),
        ("2026-11-11", "WED-1700", "", ""), ("2026-11-11", "WED-1700", "", ""), ("2026-11-11", "WED-1700", "", ""),
    ]


def test_fake_assignments_csv_has_13_people(folder):
    data, _, draft, _ = build(folder)
    assert len([r for r in rows(render_assignments_csv(data, draft)) if r["email"]]) == 13


# --- writing the week folder -----------------------------------------------------

def test_redrafting_keeps_hand_edits_unless_replace(folder):
    data, _, draft, html = build(folder)
    csv_bytes = render_assignments_csv(data, draft)
    week_dir = write_week_files(folder, draft, html, csv_bytes, replace=False, now=NOW)
    assert (week_dir / "review.html").exists()
    write_week_files(folder, draft, html, csv_bytes, replace=False, now=NOW)       # same content: fine

    edited = csv_bytes.replace(b"Lee Fictional", b"Gale Dummy")
    (week_dir / "assignments.csv").write_bytes(edited)
    with pytest.raises(InputError) as e:
        write_week_files(folder, draft, html, csv_bytes, replace=False, now=NOW)
    assert "may have your edits" in str(e.value) and "--replace" in str(e.value)
    assert (week_dir / "assignments.csv").read_bytes() == edited                    # untouched

    write_week_files(folder, draft, html, csv_bytes, replace=True, now=NOW)
    assert (week_dir / "assignments.csv").read_bytes() == csv_bytes
    assert (week_dir / "assignments-before-20261022-153000.csv").read_bytes() == edited


def test_approved_week_is_never_redrafted(folder):
    data, _, draft, html = build(folder)
    week_dir = folder / "weeks" / "2026-11-09"
    week_dir.mkdir(parents=True)
    (week_dir / "APPROVED").write_text("")
    with pytest.raises(InputError) as e:
        write_week_files(folder, draft, html, render_assignments_csv(data, draft), replace=True, now=NOW)
    assert "already approved" in str(e.value)


def test_draft_command_writes_the_week_folder(folder):
    out = subprocess.run([sys.executable, "-m", "scheduler", "draft", "--week", "2026-11-09", "--no-open",
                          "--file", str(folder / "signups.xlsx")], cwd=PROJECT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    week_dir = folder / "weeks" / "2026-11-09"
    assert f"Review page: {week_dir / 'review.html'}" in out.stdout
    assert (week_dir / "review.html").exists() and (week_dir / "assignments.csv").exists()


# --- fits on one printed page --------------------------------------------------------

def printed_pages(html_path: Path, tmp_path: Path) -> int:
    pdf = tmp_path / "page.pdf"
    subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", html_path.resolve().as_uri()],
                   capture_output=True, timeout=60)
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))


@pytest.mark.skipif(not CHROME.exists(), reason="needs Google Chrome to print to PDF")
@pytest.mark.parametrize("thursday_needs", [None, 8])
def test_prints_on_one_page(folder, tmp_path, thursday_needs):
    if thursday_needs:
        with_thursday_needing(folder, thursday_needs)
    week = date(2026, 11, 23)
    data, _, draft, html = build(folder, week)
    week_dir = write_week_files(folder, draft, html, render_assignments_csv(data, draft), replace=False, now=NOW)
    assert printed_pages(week_dir / "review.html", tmp_path) == 1
