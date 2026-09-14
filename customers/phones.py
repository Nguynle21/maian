import re


def normalize_phone(raw):
    """'(281) 555-0100' and '+1 281.555.0100' both become '2815550100'.

    Anything that is not a 10-digit US number comes back as its bare digits, so
    nothing staff typed is lost. The record checklist flags it.
    """
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def is_us_phone(digits):
    return len(digits or "") == 10


def format_phone(digits):
    if is_us_phone(digits):
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return digits or ""
