"""Command-line entry point: `python -m scheduler`."""

import argparse
import sys

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scheduler",
        description=(
            "Drafts a weekly volunteer shift calendar from signups.xlsx for a "
            "person to review. Never contacts anyone."
        ),
        epilog=(
            "Commands still to come: check-input (Phase 1), draft (Phases 3-5), "
            "approve (Phase 6). See docs/BUILD_PLAN.md."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
