"""Tests for zkm.canonical value canonicalisers."""

from __future__ import annotations

from zkm.canonical import amount, email, iban, iso8601, phone


# ---------------------------------------------------------------------------
# iban
# ---------------------------------------------------------------------------


def test_iban_strips_spaces() -> None:
    assert iban("DE89 3704 0044 0532 0130 00") == "DE89370400440532013000"


def test_iban_strips_dashes() -> None:
    assert iban("CH56-0483-5012-3456-7800-9") == "CH5604835012345678009"


def test_iban_upcases() -> None:
    assert iban("de89370400440532013000") == "DE89370400440532013000"


def test_iban_already_canonical() -> None:
    assert iban("CH5604835012345678009") == "CH5604835012345678009"


# ---------------------------------------------------------------------------
# amount
# ---------------------------------------------------------------------------


def test_amount_chf_swiss_integer() -> None:
    assert amount("CHF 1'000.-") == ("1000.00", "CHF")


def test_amount_de_format_euro_suffix() -> None:
    assert amount("1.000,50 €") == ("1000.50", "EUR")


def test_amount_negative_usd() -> None:
    assert amount("-0.01 USD") == ("-0.01", "USD")


def test_amount_en_format_comma_thousands() -> None:
    assert amount("1,000.50 USD") == ("1000.50", "USD")


def test_amount_euro_prefix() -> None:
    assert amount("€ 42.99") == ("42.99", "EUR")


def test_amount_gbp_prefix() -> None:
    assert amount("£ 9.99") == ("9.99", "GBP")


def test_amount_no_decimal() -> None:
    assert amount("CHF 100") == ("100", "CHF")


def test_amount_swiss_apostrophe_with_decimal() -> None:
    assert amount("CHF 1'234.56") == ("1234.56", "CHF")


def test_amount_de_comma_only() -> None:
    # "50,00 €" — comma is decimal separator (2 digits after)
    assert amount("50,00 €") == ("50.00", "EUR")


def test_amount_crypto_btc() -> None:
    assert amount("0.001 BTC") == ("0.001", "BTC")


# ---------------------------------------------------------------------------
# email
# ---------------------------------------------------------------------------


def test_email_lowercases_domain() -> None:
    assert email("User@Example.COM") == "User@example.com"


def test_email_preserves_local_case() -> None:
    assert email("Alice.Bob@EXAMPLE.ORG") == "Alice.Bob@example.org"


def test_email_already_lowercase() -> None:
    assert email("user@example.com") == "user@example.com"


def test_email_no_at_sign() -> None:
    # Degenerate input: lowercase whole string
    assert email("NOTANEMAIL") == "notanemail"


# ---------------------------------------------------------------------------
# phone
# ---------------------------------------------------------------------------


def test_phone_strips_spaces() -> None:
    assert phone("+41 79 123 45 67") == "+41791234567"


def test_phone_strips_dashes_and_parens() -> None:
    assert phone("+49 (30) 123-456") == "+4930123456"


def test_phone_preserves_plus() -> None:
    result = phone("+1-800-555-0100")
    assert result.startswith("+")
    assert result == "+18005550100"


def test_phone_no_plus() -> None:
    assert phone("0791234567") == "0791234567"


def test_phone_strips_dots() -> None:
    assert phone("+1.800.555.0100") == "+18005550100"


# ---------------------------------------------------------------------------
# iso8601
# ---------------------------------------------------------------------------


def test_iso8601_bare_date_passthrough() -> None:
    assert iso8601("2026-05-08") == "2026-05-08"


def test_iso8601_european_dot_format() -> None:
    assert iso8601("08.05.2026") == "2026-05-08"


def test_iso8601_european_slash_format() -> None:
    assert iso8601("08/05/2026") == "2026-05-08"


def test_iso8601_datetime_with_timezone() -> None:
    result = iso8601("2026-05-08T14:30:00+02:00")
    assert result == "2026-05-08T14:30:00+02:00"


def test_iso8601_datetime_without_timezone() -> None:
    result = iso8601("2026-05-08T14:30:00")
    assert result == "2026-05-08T14:30:00"


def test_iso8601_unrecognised_passthrough() -> None:
    # Unknown format: returned unchanged
    assert iso8601("May 8 2026") == "May 8 2026"
