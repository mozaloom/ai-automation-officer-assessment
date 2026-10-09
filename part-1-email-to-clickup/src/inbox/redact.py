"""Keep personal data out of logs: addresses, phone numbers and long digit strings are masked, and text is truncated."""

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_DIGITS = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def redact(text: str, limit: int = 80) -> str:
    out = _DIGITS.sub("[number]", _EMAIL.sub("[email]", text or ""))
    return out if len(out) <= limit else out[: limit - 1] + "…"


def mask_address(address: str) -> str:
    name, _, domain = (address or "").partition("@")
    return f"{name[:1]}***@{domain}" if domain else "***"
