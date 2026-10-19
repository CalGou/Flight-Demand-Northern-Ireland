"""Tests for the parsing half of src/ingest_caa_data.py.

The fixtures reproduce the three CAA CSV schema variants found during the
data audit (docs/data-audit-findings.md). Nothing here touches the network.
"""

import pytest

from ingest_caa_data import canonical_period, rows_for_target_airports


@pytest.mark.parametrize("year, month, expected", [
    (2015, 1, "201501"),
    (2026, 12, "202612"),
])
def test_canonical_period_is_zero_padded_yyyymm(year, month, expected):
    assert canonical_period(year, month) == expected


def test_passengers_ignore_malformed_period_in_source_file():
    # Real case: the May 2016 Table 09, re-issued Feb 2017, says 2016005.
    csv_text = (
        "this_period,reporting_airport_name,total_pax_this_period,"
        "terminal_pax_this_period,transit_pax_this_period\n"
        "2016005,BELFAST INTERNATIONAL,450000,449000,1000\n"
        "2016005,HEATHROW,6000000,6000000,0\n"
    )

    rows = rows_for_target_airports(csv_text, "passengers", 2016, 5)

    assert len(rows) == 1  # Heathrow is not a target airport
    assert rows[0]["airport_code"] == "BFS"
    assert rows[0]["period"] == "201605"
    assert rows[0]["total_pax"] == "450000"


def test_movements_old_schema_airport_column():
    # Jan 2015 - Mar 2016 Table 05 releases use reporting_airport_name.
    csv_text = (
        "run_date,this_period,reporting_airport_name,mov_total_EU_atm\n"
        "01/04/2016,201603,CITY OF DERRY (EGLINTON),400\n"
    )

    rows = rows_for_target_airports(csv_text, "movements", 2016, 3)

    assert rows == [{
        "airport_code": "LDY",
        "airport_name": "CITY OF DERRY (EGLINTON)",
        "period": "201603",
        "run_date": "01/04/2016",
        "mov_total_EU_atm": "400",
    }]


def test_movements_new_schema_airport_column_and_housekeeping_dropped():
    # Apr 2016 onward: rpt_apt_name, re-cased group column, no period column.
    # This is the schema that was silently skipped before the audit fix.
    csv_text = (
        "rundate,Reporting_Airport_Group_Name,rpt_apt_name,mov_Total_EU_ATM\n"
        "01/05/2016,NORTHERN IRELAND,belfast city (george best),3000\n"
    )

    rows = rows_for_target_airports(csv_text, "movements", 2016, 4)

    assert len(rows) == 1
    row = rows[0]
    assert row["airport_code"] == "BHD"  # name match is case-insensitive
    assert row["period"] == "201604"
    assert row["mov_Total_EU_ATM"] == "3000"
    for housekeeping in ("rundate", "Reporting_Airport_Group_Name", "rpt_apt_name"):
        assert housekeeping not in row
