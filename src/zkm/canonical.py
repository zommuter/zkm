"""Shared value canonicalisers for structured entity types.

Imported by extractors AND the redactor — must be pure (no I/O, no deps beyond stdlib).

Types where canonicalisation is undefined or lossy (person, org, place, email local-part)
have no entry here; callers treat the raw value as canonical for those.

Standards referenced:
    iban      — ISO 13616
    amount    — ISO 4217 (fiat), crypto_ticker (crypto)
    email     — RFC 5321 (domain case-insensitive; local-part case-sensitive, not normalised)
    phone     — ITU-T E.164
    iso8601   — ISO 8601
    openpgp   — RFC 4880 (v4 SHA-1 fingerprint) / RFC 9580 (v6)
"""

from __future__ import annotations

import re
from datetime import date, datetime

# ---------------------------------------------------------------------------
# IBAN — ISO 13616
# ---------------------------------------------------------------------------

_IBAN_STRIP = re.compile(r"[\s\-]")

_FP_SEP = re.compile(r"[\s:]")
_HEX_RE = re.compile(r"^[0-9A-F]+$")


def iban(s: str) -> str:
    """Normalise IBAN to uppercase with no spaces (ISO 13616).

    "DE89 3704 0044 0532 0130 00" → "DE89370400440532013000"
    """
    return _IBAN_STRIP.sub("", s).upper()


# ---------------------------------------------------------------------------
# Amount — period-decimal with separate currency code
# ---------------------------------------------------------------------------

# Multi-character symbols must appear before single-char alternatives.
_SYMBOL_MAP: dict[str, str] = {
    "SFr.": "CHF",
    "SFr": "CHF",
    "Fr.": "CHF",
    "Fr": "CHF",
    "€": "EUR",
    "£": "GBP",
    "$": "USD",
    "¥": "JPY",
}

# Ordered longest-first so greedy prefix matching works correctly.
_SYMBOL_KEYS = sorted(_SYMBOL_MAP, key=len, reverse=True)


def _sym_to_code(sym: str) -> str:
    return _SYMBOL_MAP.get(sym, sym)


def _strip_currency(s: str) -> tuple[str, str]:
    """Remove currency symbol/code from start or end; return (number_str, code)."""
    # Prefix: symbol then whitespace then number
    for sym in _SYMBOL_KEYS:
        if s.startswith(sym):
            rest = s[len(sym):].strip()
            return rest, _sym_to_code(sym)
    # Prefix: uppercase code then whitespace
    m = re.match(r"^([A-Z]{2,4})\s+", s)
    if m:
        rest = s[m.end():]
        return rest, m.group(1)
    # Suffix: number then whitespace then symbol or code
    for sym in _SYMBOL_KEYS:
        if s.endswith(sym):
            rest = s[: -len(sym)].strip()
            return rest, _sym_to_code(sym)
    m = re.search(r"\s+([A-Z]{2,4})$", s)
    if m:
        rest = s[: m.start()]
        return rest, m.group(1)
    return s, ""


def _normalise_number(s: str) -> str:
    """Convert a number string (without currency) to period-decimal, no grouping."""
    s = s.strip()
    # Swiss/German integer convention: "1000.-" means "1000.00"
    integer_form = False
    if s.endswith(".-"):
        s = s[:-2]
        integer_form = True

    # Remove Swiss thousands apostrophe
    s = s.replace("'", "")

    if "," in s and "." in s:
        # Determine which is the decimal separator by position of last occurrence.
        if s.rfind(",") > s.rfind("."):
            # DE/CH: 1.000,50 → thousands='.', decimal=','
            s = s.replace(".", "").replace(",", ".")
        else:
            # EN: 1,000.50 → thousands=',', decimal='.'
            s = s.replace(",", "")
    elif "," in s:
        # Only comma present.
        last_part = s.rsplit(",", 1)[1]
        if len(last_part) <= 2:
            # Decimal comma: "1000,50" → "1000.50"
            s = s.replace(",", ".", 1)
            # Remove any remaining grouping commas before the decimal
            parts = s.split(".")
            parts[0] = parts[0].replace(",", "")
            s = ".".join(parts)
        else:
            # Thousands comma: "1,000" → "1000"
            s = s.replace(",", "")

    if integer_form:
        s = s + ".00"

    return s


def amount(s: str) -> tuple[str, str]:
    """Parse a DE/CH/EN amount string to (decimal_str, currency_code).

    decimal_str uses period as decimal separator with no grouping separators.
    currency_code is the ISO 4217 code for fiat or the ticker for crypto.

    Examples:
        "CHF 1'000.-"  → ("1000.00", "CHF")
        "1.000,50 €"   → ("1000.50", "EUR")
        "-0.01 USD"    → ("-0.01", "USD")
    """
    s = s.strip()

    # Extract leading sign before currency/number.
    sign = ""
    if s.startswith("-"):
        sign = "-"
        s = s[1:].strip()
    elif s.startswith("+"):
        s = s[1:].strip()

    num_str, code = _strip_currency(s)

    # Sign may also appear between currency prefix and number.
    num_str = num_str.strip()
    if num_str.startswith("-"):
        sign = "-"
        num_str = num_str[1:].strip()
    elif num_str.startswith("+"):
        num_str = num_str[1:].strip()

    normalised = _normalise_number(num_str)
    return sign + normalised, code


# ---------------------------------------------------------------------------
# Email — RFC 5321 (domain case-insensitive; local-part preserved)
# ---------------------------------------------------------------------------


def email(s: str) -> str:
    """Normalise email: preserve local-part case, lowercase domain (RFC 5321).

    "User@Example.COM" → "User@example.com"
    """
    s = s.strip()
    if "@" not in s:
        return s.lower()
    local, _, domain = s.partition("@")
    return f"{local}@{domain.lower()}"


# ---------------------------------------------------------------------------
# Phone — ITU-T E.164 basic
# ---------------------------------------------------------------------------

_PHONE_STRIP = re.compile(r"[^\d]")


def phone(s: str) -> str:
    """Normalise phone number to E.164 basic form (strip formatting, keep leading +).

    "+41 79 123 45 67" → "+41791234567"
    """
    s = s.strip()
    has_plus = s.startswith("+")
    digits = _PHONE_STRIP.sub("", s)
    return ("+" if has_plus else "") + digits


# ---------------------------------------------------------------------------
# ISO 8601 date/datetime
# ---------------------------------------------------------------------------

_EU_DATE_RE = re.compile(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})$")


def iso8601(s: str) -> str:
    """Normalise a date or datetime string to ISO 8601.

    Accepts ISO 8601 input, plus European DD.MM.YYYY / DD/MM/YYYY.
    Returns YYYY-MM-DD for bare dates; full isoformat string for datetimes.

    "08.05.2026"              → "2026-05-08"
    "2026-05-08T14:30:00+02:00" → "2026-05-08T14:30:00+02:00"
    """
    s = s.strip()
    # Bare date (YYYY-MM-DD)
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        pass
    # Full datetime (with optional time and timezone)
    try:
        return datetime.fromisoformat(s).isoformat()
    except ValueError:
        pass
    # European DD.MM.YYYY or DD/MM/YYYY
    m = _EU_DATE_RE.match(s)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return s


# ---------------------------------------------------------------------------
# OpenPGP fingerprint — RFC 4880 (v4, 40 hex chars) / RFC 9580 (v6, 64 hex chars)
# ---------------------------------------------------------------------------


def fingerprint(s: str) -> tuple[str, str | None, bool]:
    """Normalise an OpenPGP fingerprint to uppercase hex with no separators.

    Returns (canonical, standard, valid):
      - valid=True  → canonical is uppercase hex, standard is "openpgp-v4" (40) or "openpgp-v6" (64)
      - valid=False → canonical is the stripped raw input, standard is None

    Accepts common formatting variants:
      "AB:CD:EF:…"      (colon-separated GPG output)
      "0xABCD…"         (0x prefix)
      "ab cd ef …"      (space-separated)

    "4F1C 5A3B …" (40 hex chars) → ("4F1C5A3B…", "openpgp-v4", True)
    "AB:CD:…"    (64 hex chars) → ("ABCD…",     "openpgp-v6", True)
    "not-a-key"              → ("not-a-key",    None,         False)
    """
    stripped = _FP_SEP.sub("", s.strip()).upper()
    if stripped.startswith("0X"):
        stripped = stripped[2:]
    if _HEX_RE.match(stripped):
        if len(stripped) == 40:
            return stripped, "openpgp-v4", True
        if len(stripped) == 64:
            return stripped, "openpgp-v6", True
    return s.strip(), None, False
