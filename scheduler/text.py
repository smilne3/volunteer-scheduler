"""Text cleanup shared by header and answer matching."""

import re

_DASHES = "‐‑‒–—―−"
_QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"'}


def norm(value) -> str:
    """Lowercase, one kind of dash and quote, single spaces, no spaces around dashes.

    So "Saturday Food Pantry 9am – 12pm" and "saturday food pantry 9am-12pm" match.
    """
    s = "" if value is None else str(value)
    s = s.strip().lower()
    for d in _DASHES:
        s = s.replace(d, "-")
    for fancy, plain in _QUOTES.items():
        s = s.replace(fancy, plain)
    s = re.sub(r"\s*-\s*", "-", s)
    return re.sub(r"\s+", " ", s)


def is_blank(value) -> bool:
    return value is None or str(value).strip() == ""
