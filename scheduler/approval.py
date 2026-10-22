"""The APPROVED marker: when a week was approved, and a fingerprint of what was approved."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

MARKER = "APPROVED"
DRAFT, APPROVED, CHANGED = "draft", "approved", "changed since approval"


@dataclass(frozen=True)
class Approval:
    status: str                       # DRAFT, APPROVED or CHANGED
    approved_at: Optional[datetime] = None
    sequence: int = 0                 # how many times this week has been approved


def fingerprint(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def approval_status(week_dir: Path) -> Approval:
    marker = Path(week_dir) / MARKER
    if not marker.exists():
        return Approval(DRAFT)
    try:
        info = json.loads(marker.read_text())
        approved_at = datetime.fromisoformat(info["approved_at"])
        sequence = int(info.get("sequence", 1))
        expected = info["assignments_sha256"]
    except (ValueError, KeyError, TypeError):
        return Approval(CHANGED)      # unreadable marker: treat as needing approval again
    assignments = Path(week_dir) / "assignments.csv"
    if not assignments.exists() or fingerprint(assignments) != expected:
        return Approval(CHANGED, approved_at, sequence)
    return Approval(APPROVED, approved_at, sequence)


def write_marker(week_dir: Path, approved_at: datetime, sequence: int, filled: int, needed: int) -> None:
    info = {
        "approved_at": approved_at.isoformat(timespec="seconds"),
        "assignments_sha256": fingerprint(Path(week_dir) / "assignments.csv"),
        "sequence": sequence,
        "slots_filled": filled,
        "slots_needed": needed,
    }
    (Path(week_dir) / MARKER).write_text(json.dumps(info, indent=2) + "\n")
