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
            "Commands still to come: draft (Phases 3-5), approve (Phase 6). "
            "See docs/BUILD_PLAN.md."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="command")

    check = commands.add_parser(
        "check-input",
        help="Show what the tool understood from signups.xlsx",
        description="Read signups.xlsx and show what the tool understood for each volunteer. Changes nothing.",
    )
    check.add_argument("--file", type=Path, default=DEFAULT_SIGNUPS,
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
            from .check_input import format_report
            from .signups import read_signups
            print(format_report(read_signups(args.file)))
    except InputError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
