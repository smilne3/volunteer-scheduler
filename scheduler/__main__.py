"""Command-line entry point: `python -m scheduler`."""

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

from . import __version__
from .errors import InputError

DATA_ENV = "VOLUNTEER_SCHEDULER_DATA"


def data_folder() -> Path:
    """Where signups.xlsx, settings.json and weeks/ live. The code lives elsewhere (not in iCloud)."""
    return Path(os.environ.get(DATA_ENV) or Path.home() / "volunteer-scheduler").expanduser()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scheduler",
        description=(
            "Drafts a weekly volunteer shift calendar from signups.xlsx for a "
            "person to review. Never contacts anyone."
        ),
        epilog=("Weekly steps: check-input, draft, (edit and draft --recheck), approve. Or run 'menu' for a "
                "numbered menu. See README.md."),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="command")

    def file_arg(p):
        p.add_argument("--file", type=Path, default=None,
                       help=f"sign-up spreadsheet to read (default: signups.xlsx in ${DATA_ENV}, "
                            f"or in ~/volunteer-scheduler if that isn't set)")

    def week_arg(p, verb):
        p.add_argument("--week", help=f"Monday of the week to {verb}, like 2026-11-09 (default: next week)")

    check = commands.add_parser(
        "check-input",
        help="Show what the tool understood from signups.xlsx",
        description=(
            "Read signups.xlsx and show what the tool understood for each volunteer. Never changes "
            "signups.xlsx. Creates or updates availability_review.csv next to it, where free-text "
            "availability is confirmed."
        ),
    )
    file_arg(check)

    draft = commands.add_parser(
        "draft",
        help="Draft a week's schedule, or re-check your edits to it",
        description=(
            "Draft a week's schedule, check it against every rule, and write weeks/<week>/review.html "
            "(opened in your browser) and weeks/<week>/assignments.csv. With --recheck, check your "
            "edited assignments.csv instead and refresh the review page. Contacts no one."
        ),
    )
    week_arg(draft, "draft")
    draft.add_argument("--recheck", action="store_true",
                       help="check your edited assignments.csv instead of drafting a new schedule")
    draft.add_argument("--replace", action="store_true",
                       help="replace an existing assignments.csv for that week (the old one is kept as a copy)")
    draft.add_argument("--no-open", action="store_true", help="don't open the review page in the browser")
    file_arg(draft)

    approve = commands.add_parser(
        "approve",
        help="Approve a week and write its Google Calendar file",
        description=(
            "Check the week's assignments.csv against every rule. If nothing is broken, write "
            "weeks/<week>/calendar.ics for importing into Google Calendar. Asks you to type yes if any "
            "shift is short. Contacts no one."
        ),
    )
    week_arg(approve, "approve")
    file_arg(approve)

    commands.add_parser(
        "menu",
        help="A numbered menu for the weekly steps (what the double-click launcher opens)",
        description="Show a numbered menu for checking sign-ups, drafting, re-checking, and approving. Uses the "
                    "data folder ($VOLUNTEER_SCHEDULER_DATA or ~/volunteer-scheduler).",
    )
    commands.add_parser(
        "install-launchers",
        help="Put double-click launchers and the how-to guide in the data folder",
        description='Write "Volunteer Scheduler.command", "Draft next week.command", "Set up this Mac.command" '
                    'and "How to use the scheduler.html" into the data folder. They work on any Mac. Safe to run again.',
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    from . import commands
    today, now = date.today(), datetime.now()
    if getattr(args, "file", None) is None:
        args.file = data_folder() / "signups.xlsx"
    try:
        if args.command == "check-input":
            return commands.check_input(args.file, today)
        if args.command == "draft":
            return commands.draft(args.file, args.week, today, now, recheck=args.recheck,
                                  replace=args.replace, open_page=not args.no_open)
        if args.command == "approve":
            return commands.approve(args.file, args.week, today, now, ask=input)
        if args.command == "menu":
            from .menu import open_in_finder, run_menu
            quiet = bool(os.environ.get("VOLUNTEER_SCHEDULER_NO_OPEN"))   # for tests: don't open windows
            return run_menu(data_folder(), today, opener=(lambda *a, **k: None) if quiet else open_in_finder,
                            open_pages=not quiet)
        if args.command == "install-launchers":
            from .launchers import SETUP_NAME, install_launchers
            for path in install_launchers(data_folder()):
                print(f"Wrote {path}")
            print(f'On any other Mac that can see this folder, double-click "{SETUP_NAME}" once.')
            print('Then double-click "Volunteer Scheduler.command" to start.')
            return 0
    except InputError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
