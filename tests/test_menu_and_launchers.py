"""Phase 8: the menu, the double-click launchers, and the how-to guide."""

import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from scheduler.errors import InputError
from scheduler.launchers import install_launchers
from scheduler.menu import GUIDE_NAME, MENU, parse_week_answer, run_menu

PROJECT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "signups_fake.xlsx"
TODAY = date(2026, 10, 22)            # a Thursday; next week starts Mon Oct 26


@pytest.fixture
def folder(tmp_path):
    shutil.copy(FIXTURE, tmp_path / "signups.xlsx")
    return tmp_path


class Session:
    """Scripted keystrokes for the menu, recording what it printed and opened."""

    def __init__(self, folder, answers):
        self.folder, self.answers, self.printed, self.opened, self.prompts = folder, list(answers), [], [], []

    def ask(self, prompt):
        self.prompts.append(prompt)
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)

    def run(self, capsys=None):
        code = run_menu(self.folder, TODAY, ask=self.ask, out=self.printed.append,
                        opener=lambda path, reveal=False: self.opened.append((Path(path).name, reveal)),
                        open_pages=False)
        self.output = "\n".join(self.printed) + (capsys.readouterr().out if capsys else "")
        return code


def test_a_full_week_from_the_menu(folder, capsys):
    s = Session(folder, ["1", "2", "", "4", "", "q"])
    assert s.run(capsys) == 0
    week = folder / "weeks" / "2026-10-26"
    assert (week / "calendar.ics").exists() and (week / "APPROVED").exists()
    assert ("calendar.ics", True) in s.opened                        # Finder shows the file to import
    assert "SUMMARY: 19 ready, 11 need reading" in s.output
    assert "To confirm typed answers, open availability_review.csv" in s.output


def test_existing_draft_is_kept_unless_you_type_yes(folder, capsys):
    Session(folder, ["2", "", "q"]).run()
    csv_path = folder / "weeks" / "2026-10-26" / "assignments.csv"
    edited = csv_path.read_text(encoding="utf-8-sig").replace("Lee Fictional", "lee fictional")
    csv_path.write_text(edited, encoding="utf-8-sig")

    s = Session(folder, ["2", "", "", "q"])
    s.run()
    assert "Kept the existing draft" in s.output
    assert csv_path.read_text(encoding="utf-8-sig") == edited

    Session(folder, ["2", "", "yes", "q"]).run()
    assert csv_path.read_text(encoding="utf-8-sig") != edited
    assert list((folder / "weeks" / "2026-10-26").glob("assignments-before-*.csv"))


def test_recheck_and_approve_default_to_the_latest_unapproved_week(folder):
    Session(folder, ["2", "11/16", "q"]).run()
    s = Session(folder, ["3", "", "q"])
    s.run()
    assert any("Press Return for Monday Nov 16" in p for p in s.prompts)
    assert "Weeks so far: Nov 16 (draft)" in s.output


def test_problems_are_shown_and_the_menu_carries_on(folder):
    s = Session(folder, ["4", "12/7", "9", "q"])           # no draft for Dec 7, then an unknown choice
    assert s.run() == 0
    assert "Problem: There's no draft for the week of 2026-12-07 yet." in s.output
    assert "Please type a number from 1 to 6, or q." in s.output


def test_open_folder_and_guide(folder):
    (folder / GUIDE_NAME).write_text("<!-- volunteer-scheduler guide -->")
    s = Session(folder, ["5", "6", "q"])
    s.run()
    assert s.opened == [(folder.name, False), (GUIDE_NAME, False)]


def test_end_of_input_quits_cleanly(folder):
    assert Session(folder, []).run() == 0
    assert Session(folder, ["2"]).run() == 0               # gives up at the week question


@pytest.mark.parametrize("text, expected", [
    ("", date(2026, 10, 26)),
    ("2026-11-16", date(2026, 11, 16)),
    ("11/16", date(2026, 11, 16)),
    ("11/18", date(2026, 11, 16)),                         # a Wednesday: that week's Monday
    ("11/16/2026", date(2026, 11, 16)),
    ("1/4", date(2027, 1, 4)),                             # early next year, not last January
    ("next week", None),
])
def test_week_answers(text, expected):
    assert parse_week_answer(text, date(2026, 10, 26), TODAY) == expected


# --- launchers, setup script and guide -------------------------------------------------

VENV = Path(sys.executable).parent.parent          # the environment running these tests
SCRIPTS = ["Volunteer Scheduler.command", "Draft next week.command", "Set up this Mac.command"]


def as_mac(home, extra=None):
    """Environment for running a launcher as if on a Mac whose home folder is `home`."""
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "PYTHONDONTWRITEBYTECODE": "1",
           "VOLUNTEER_SCHEDULER_NO_OPEN": "1"}
    env.update(extra or {})
    return env


def installed_here():
    """Point the launcher at this checkout and this environment, as setup would."""
    return {"VOLUNTEER_SCHEDULER_CODE": str(PROJECT), "VOLUNTEER_SCHEDULER_VENV": str(VENV)}


def test_install_writes_the_scripts_and_the_guide(folder):
    written = install_launchers(folder)
    assert sorted(p.name for p in written) == sorted(SCRIPTS + [GUIDE_NAME])
    for name in SCRIPTS:
        path = folder / name
        assert os.access(path, os.X_OK)
        assert path.read_text().startswith("#!/bin/bash\n")
    assert "-m scheduler menu" in (folder / "Volunteer Scheduler.command").read_text()
    assert "-m scheduler draft" in (folder / "Draft next week.command").read_text()
    assert "git clone" in (folder / "Set up this Mac.command").read_text()


def test_scripts_are_the_same_on_every_mac(folder, tmp_path):
    """No usernames or paths, so a shared folder works for everyone and reinstalling never breaks a Mac."""
    install_launchers(folder)
    first = {name: (folder / name).read_bytes() for name in SCRIPTS}
    for content in first.values():
        assert b"/Users/" not in content and str(Path.home()).encode() not in content
    install_launchers(folder)
    assert {name: (folder / name).read_bytes() for name in SCRIPTS} == first


def test_install_never_overwrites_someone_elses_file(folder):
    (folder / "Set up this Mac.command").write_text("#!/bin/bash\necho mine\n")
    with pytest.raises(InputError) as e:
        install_launchers(folder)
    assert "wasn't made by this tool" in str(e.value)
    assert (folder / "Set up this Mac.command").read_text() == "#!/bin/bash\necho mine\n"
    assert not (folder / "Volunteer Scheduler.command").exists()      # nothing half-written


def test_install_needs_the_data_folder(tmp_path):
    with pytest.raises(InputError):
        install_launchers(tmp_path / "missing")


def test_a_mac_without_the_scheduler_is_told_to_run_setup(folder, tmp_path):
    install_launchers(folder)
    result = subprocess.run(["bash", str(folder / "Volunteer Scheduler.command")], input="\n",
                            capture_output=True, text=True, env=as_mac(tmp_path / "other-mac"), timeout=30)
    assert result.returncode == 1
    assert "isn't set up on this Mac yet" in result.stdout and "Set up this Mac.command" in result.stdout


def test_the_launcher_uses_the_folder_it_is_in(tmp_path):
    odd = tmp_path / "Volunteer's Shared Folder"
    odd.mkdir()
    shutil.copy(FIXTURE, odd / "signups.xlsx")
    install_launchers(odd)
    subprocess.run(["bash", str(odd / "Volunteer Scheduler.command")], input="2\n11/9\nq\n", cwd="/",
                   capture_output=True, text=True, env=as_mac(tmp_path / "home", installed_here()), timeout=180)
    assert (odd / "weeks" / "2026-11-09" / "review.html").exists()


def test_setup_updates_an_existing_install(folder, tmp_path):
    """Run the setup script against a local copy of this repo and this environment (no downloads)."""
    code = tmp_path / "home" / "code" / "volunteer-scheduler"
    subprocess.run(["git", "clone", "-q", str(PROJECT), str(code)], check=True, capture_output=True)
    install_launchers(folder)
    result = subprocess.run(["bash", str(folder / "Set up this Mac.command")], input="\n", cwd="/",
                            capture_output=True, text=True, timeout=300,
                            env=as_mac(tmp_path / "home", {"VOLUNTEER_SCHEDULER_CODE": str(code),
                                                           "VOLUNTEER_SCHEDULER_VENV": str(VENV)}))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Updating the scheduler" in result.stdout and "All set" in result.stdout


def test_setup_refuses_to_install_into_icloud(folder, tmp_path):
    home = tmp_path / "home"
    install_launchers(folder)
    icloud = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "code"
    result = subprocess.run(["bash", str(folder / "Set up this Mac.command")], input="\n", cwd="/",
                            capture_output=True, text=True, timeout=30,
                            env=as_mac(home, {"VOLUNTEER_SCHEDULER_CODE": str(icloud)}))
    assert result.returncode == 1 and "can't be installed inside iCloud Drive" in result.stdout


def test_guide_matches_the_menu():
    guide = (PROJECT / "scheduler" / "guide.html").read_text()
    assert guide.splitlines()[1] == "<!-- volunteer-scheduler guide -->"
    text = re.sub(r"<[^>]+>", "", guide)                    # the words, without HTML tags
    for number, label in re.findall(r"^  (\d)  (.+)$", MENU, flags=re.M):
        first_words = " ".join(label.split()[:3]).rstrip(",")
        if number in "1234":
            assert f"{number}, {first_words}" in text, (number, first_words)
    for phrase in ("Download Now", "Import &amp; export", "confirmed_reading", "Nobody gets an invitation"):
        assert phrase in guide


def test_excel_lock_files_are_ignored(folder):
    (folder / "~$signups.xlsx").write_bytes(b"lock")
    (folder / "weeks").mkdir()
    (folder / "weeks" / "~$assignments.csv").write_bytes(b"lock")
    s = Session(folder, ["1", "2", "", "q"])
    assert s.run() == 0
    assert (folder / "weeks" / "2026-10-26" / "review.html").exists()
