"""Checks that the tools the scheduler depends on work on this machine."""

import subprocess
import sys
from pathlib import Path

import pulp

from scheduler.solver import _solver

PROJECT = Path(__file__).resolve().parent.parent


def test_solver_runs():
    # Tiny problem with a known answer: best is x=1, y=3, total 7.
    problem = pulp.LpProblem("smoke", pulp.LpMaximize)
    x = problem.add_variable("x", 0, 3, cat="Integer")
    y = problem.add_variable("y", 0, 3, cat="Integer")
    problem += x + 2 * y
    problem += x + y <= 4
    status = problem.solve(_solver())
    assert pulp.LpStatus[status] == "Optimal"
    assert pulp.value(problem.objective) == 7


def test_native_solver_is_used():
    # CBC (PuLP's bundled solver) is Intel-only on macOS; HiGHS also runs on Apple-chip Macs.
    assert _solver().name == "HiGHS", "highspy isn't installed: run pip install -r requirements.txt"


def test_cli_help_runs():
    result = subprocess.run(
        [sys.executable, "-m", "scheduler", "--help"],
        cwd=PROJECT, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "Never contacts anyone" in result.stdout
