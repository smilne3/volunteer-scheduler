"""Guard for decision D5: the scheduler never emails, texts or contacts anyone.

Fails if any code in scheduler/ imports a module that can send email, make
network requests or reach an SMS service.
"""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "scheduler"

FORBIDDEN = {
    "smtplib", "imaplib", "poplib", "email", "socket", "ssl",
    "http", "urllib", "urllib3", "requests", "httpx", "aiohttp",
    "ftplib", "telnetlib", "xmlrpc",
    "twilio", "vonage", "plivo", "sinch", "boto3", "googleapiclient", "sendgrid",
}


def imported_top_level_modules(path: Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module.split(".")[0]


def test_no_messaging_or_network_imports():
    files = sorted(PACKAGE.rglob("*.py"))
    assert files, "found no code to check"
    problems = [
        f"{f.relative_to(PACKAGE.parent)}:{line} imports {mod}"
        for f in files
        for line, mod in imported_top_level_modules(f)
        if mod in FORBIDDEN
    ]
    assert not problems, "Messaging/network code is not allowed (D5):\n" + "\n".join(problems)
