"""Conversion between the API's 'YYYY-MM' strings and first-of-month dates."""
import re
from datetime import date

PERIOD_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
_PERIOD_RE = re.compile(PERIOD_PATTERN)


def parse_period(value: str) -> date:
    if not _PERIOD_RE.match(value):
        raise ValueError(f"Expected a YYYY-MM period, got {value!r}")
    return date(int(value[:4]), int(value[5:7]), 1)


def format_period(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def same_month_last_year(d: date) -> date:
    return date(d.year - 1, d.month, 1)
