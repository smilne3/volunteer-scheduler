"""The line at the bottom of every schedule saying how it was made.

A draft hasn't been checked by staff yet, so only an approved schedule says it was.
"""

DRAFTED = "Drafted with AI from the sign-up form"


def ai_note(approved: bool) -> str:
    if approved:
        return f"{DRAFTED} and checked by staff."
    return f"{DRAFTED}. Not yet checked by staff."
