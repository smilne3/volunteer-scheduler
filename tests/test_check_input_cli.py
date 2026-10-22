"""Phase 1: the `check-input` command."""

import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "signups_fake.xlsx"


def run(*args):
    return subprocess.run([sys.executable, "-m", "scheduler", *args],
                          cwd=PROJECT, capture_output=True, text=True)


def test_check_input_on_fake_data():
    result = run("check-input", "--file", str(FIXTURE))
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "30 responses from 30 volunteers" in out
    assert "SUMMARY: 19 ready, 11 need reading, 0 with problems" in out
    assert 'Bailey Sample: "Saturdays but not the 14th"' in out
    assert "THU-1500  needs 2: 6 available (3 experienced)" in out


def test_check_input_error_is_plain_english(tmp_path):
    result = run("check-input", "--file", str(tmp_path / "nope.xlsx"))
    assert result.returncode == 1
    assert result.stderr.startswith("Error: Can't find")
    assert "Traceback" not in result.stderr
