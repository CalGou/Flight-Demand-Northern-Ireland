from datetime import date

import pytest

from app.periods import format_period, parse_period, same_month_last_year


def test_round_trip():
    assert parse_period("2026-03") == date(2026, 3, 1)
    assert format_period(date(2015, 1, 1)) == "2015-01"


@pytest.mark.parametrize("bad", ["2026-13", "2026-00", "202603", "26-03", "2026-3", ""])
def test_rejects_malformed_periods(bad):
    with pytest.raises(ValueError):
        parse_period(bad)


def test_same_month_last_year():
    assert same_month_last_year(date(2026, 1, 1)) == date(2025, 1, 1)
