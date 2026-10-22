"""Command-line entry point: `python -m scheduler`."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .errors import InputError

PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_SIGNUPS = PROJECT / "signups.xlsx"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scheduler",
        description=(
            "Drafts a weekly volunteer shift calendar from signups.xlsx for a "
            "person to review. Never contacts anyone."
        ),
        epilog=(
            "Commands still to come: approve (Phase 6). "
            "See docs/BUILD_PLAN.md."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="command")

    check = commands.add_parser(
        "check-input",
        help="Show what the tool understood from signups.xlsx",
        description=(
            "Read signups.xlsx and show what the tool understood for each volunteer. Never changes "
            "signups.xlsx. Creates or updates availability_review.csv next to it, where free-text "
            "availability is confirmed."
        ),
    )
    check.add_argument("--file", type=Path, default=DEFAULT_SIGNUPS,
                       help="sign-up spreadsheet to read (default: signups.xlsx in the project folder)")

    draft = commands.add_parser(
        "draft",
        help="Draft a week's schedule",
        description=(
            "Draft a week's schedule, check it against every rule, and write weeks/<week>/review.html "
            "(opened in your browser) and weeks/<week>/assignments.csv. Contacts no one."
        ),
    )
    draft.add_argument("--week", help="Monday of the week to draft, like 2026-11-09 (default: next week)")
    draft.add_argument("--no-open", action="store_true", help="don't open the review page in the browser")
    draft.add_argument("--replace", action="store_true",
                       help="replace an existing assignments.csv for that week (the old one is kept as a copy)")
    draft.add_argument("--file", type=Path, default=DEFAULT_SIGNUPS,
                       help="sign-up spreadsheet to read (default: signups.xlsx in the project folder)")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "check-input":
            from datetime import date

            from .check_input import format_report
            from .review_file import apply_reviews
            from .signups import read_signups
            data = read_signups(args.file)
            review = apply_reviews(data, today=date.today())
            print(format_report(data, review))
        elif args.command == "draft":
            from datetime import date, datetime

            from .checker import BROKEN, check
            from .draft_report import format_draft
            from .reasons import explain_gaps
            from .review_file import apply_reviews
            from .review_page import render_assignments_csv, render_review_page, write_week_files
            from .settings import load_settings
            from .signups import read_signups
            from .solver import schedule
            from .week import parse_week
            week = parse_week(args.week, date.today())
            settings = load_settings(args.file.parent)
            data = read_signups(args.file)
            review = apply_reviews(data, today=date.today())
            result = schedule(data, settings, week)
            findings = check(data, settings, week, result.assignments)
            now = datetime.now()
            html = render_review_page(data, settings, result, findings, explain_gaps(data, settings, result),
                                      review, generated=now)
            folder = write_week_files(args.file.parent, result, html, render_assignments_csv(data, result),
                                      replace=args.replace, now=now)
            print(format_draft(data, settings, result, findings))
            print(f"Review page: {folder / 'review.html'}")
            print(f"Editable draft: {folder / 'assignments.csv'}")
            if not args.no_open:
                import webbrowser
                webbrowser.open((folder / "review.html").resolve().as_uri())
            if any(f.level == BROKEN for f in findings):
                return 2
    except InputError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
