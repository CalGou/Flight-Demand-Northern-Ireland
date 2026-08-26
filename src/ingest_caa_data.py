"""
Ingest UK CAA monthly airport data (Table 09: passengers, Table 05: air
transport movements) for Belfast International (BFS), George Best Belfast
City (BHD), and City of Derry (LDY), from January 2015 to the present, into
a single tidy monthly panel.

Why 2015: the CAA publishes each month's data as its own page (one page per
month), and CSV downloads only go back to January 2015 -- earlier data
(1990-2014 and before) exists only as scanned PDF publications, not
machine-readable. Each monthly release CSV only covers that one period (a
"this_period" column, e.g. 202603 for March 2026) plus the *same* month a
year earlier as a year-on-year comparator ("last_period", e.g. 202503) --
not a running series and not the prior calendar month, despite the naming --
so building history still means pulling every monthly page individually.
We only ever keep this_period, so no double-counting risk from that
year-over-year pairing; run_build_panel.py's dedupe is just a safety net in
case CAA ever republishes a corrected figure for a period already pulled.

Usage:
    pip install requests beautifulsoup4
    python src/ingest_caa_data.py

Run this from your own machine -- the CAA site isn't reachable from every
sandboxed environment. It's polite-paced (a short delay between requests)
and caches each month's raw CSVs under data/raw/ so re-runs are cheap and
you're not hammering the CAA server on every retry.
"""

import csv
import io
import re
import time
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.caa.co.uk/data-and-analysis/uk-aviation-market/airports/uk-airport-data"
START_YEAR, START_MONTH = 2015, 1
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
REQUEST_DELAY_SECONDS = 1.5

# Airport names as they appear in CAA's "reporting_airport_name" column.
# Add variants here if a run turns up a spelling CAA has changed over time.
TARGET_AIRPORTS = {
    "BELFAST INTERNATIONAL": "BFS",
    "BELFAST CITY (GEORGE BEST)": "BHD",
    "CITY OF DERRY (EGLINTON)": "LDY",
}

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]


def month_page_url(year, month):
    return f"{BASE}/uk-airport-data-{year}/{MONTH_NAMES[month - 1]}-{year}/"


# Each month page lists ~20 tables x 2 formats (CSV + PDF) as separate
# download links, and each link's own visible text names its table and
# format, e.g. "Table 09 Terminal and Transit Passengers (CSV, 6 KB)". That
# means we can pick out just the 2 links we actually want *before*
# downloading anything, instead of fetching all ~40 and discarding 38 of
# them -- which is what was making full runs slow.
TARGET_LINK_MATCHERS = {
    "passengers": ("table 09", "csv"),
    "movements": ("table 05", "csv"),
}


def find_csv_links(page_html, page_url):
    """Return only the Table 09 (passengers) and Table 05 (movements) CSV
    download links on a month page, keyed by which table they are."""
    soup = BeautifulSoup(page_html, "html.parser")
    found = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/Documents/Download/" not in href:
            continue
        text = a.get_text(" ", strip=True).lower()
        for kind, (table_marker, format_marker) in TARGET_LINK_MATCHERS.items():
            if table_marker in text and format_marker in text:
                found[kind] = requests.compat.urljoin(page_url, href)
    return found


def classify_csv(content_bytes):
    """
    Work out whether a downloaded file is Table 09 (passengers), Table 05
    (movements), or something else -- by inspecting its header row, since
    the download URLs themselves don't say which table they are.
    """
    try:
        text = content_bytes.decode("utf-8-sig", errors="ignore")
    except Exception:
        return None
    first_line = text.splitlines()[0].lower() if text.splitlines() else ""
    if "terminal_pax" in first_line:
        return "passengers"
    if "atm" in first_line or "movement" in first_line:
        return "movements"
    return None


def canonical_period(year, month):
    """The panel's one true period format: YYYYMM, e.g. 201501."""
    return f"{year}{month:02d}"


# CAA's own column names drift across releases -- confirmed so far:
#   Table 09 (passengers): always "reporting_airport_name"
#   Table 05 (movements):  "reporting_airport_name" through Mar 2016,
#                           then "rpt_apt_name" (different name AND a
#                           different Reporting_Airport_Group_Name casing)
#                           from Apr 2016 onward. This is *the* reason
#                           movements data was silently empty for every
#                           month after Mar 2016 -- the airport-name lookup
#                           never matched, so every row was skipped as "not
#                           a target airport" rather than erroring loudly.
AIRPORT_NAME_COLUMNS = ["reporting_airport_name", "rpt_apt_name"]

# Column names actually seen for the period field across releases. None of
# these are trusted as the merge key any more (see below) -- kept only to
# recognise and exclude them so they don't leak into the movements table's
# "keep everything else" column copy.
PERIOD_COLUMNS = {"period", "this_period", "last_period", "reporting_period", "report_period"}


def find_airport_name(row):
    for col in AIRPORT_NAME_COLUMNS:
        val = (row.get(col) or "").strip()
        if val:
            return val
    return ""


def rows_for_target_airports(csv_text, kind, year, month):
    # We already know, unambiguously, which month this file is for -- it's
    # the page we requested. CAA's own period field has turned out to be
    # unreliable in two different ways (missing entirely on Table 05, and
    # outright malformed -- e.g. "2016005" instead of "201605" -- on some
    # re-published Table 09 releases), so rather than keep patching around
    # each new way it can be wrong, just use the known-correct value
    # directly instead of trusting anything the file itself says.
    period = canonical_period(year, month)
    reader = csv.DictReader(io.StringIO(csv_text))
    out = []
    for row in reader:
        name = find_airport_name(row).upper()
        if name not in TARGET_AIRPORTS:
            continue
        record = {
            "airport_code": TARGET_AIRPORTS[name],
            "airport_name": name,
            "period": period,
        }
        if kind == "passengers":
            record["total_pax"] = row.get("total_pax_this_period")
            record["terminal_pax"] = row.get("terminal_pax_this_period")
            record["transit_pax"] = row.get("transit_pax_this_period")
        else:
            # Column names for Table 05 vary by release; keep everything
            # that isn't an obvious housekeeping field so nothing is lost.
            # Matched case-insensitively since casing itself has drifted
            # between releases (e.g. Reporting_Airport_Group_Name).
            excluded_lower = {"rundate"} | {c.lower() for c in AIRPORT_NAME_COLUMNS} | {
                "reporting_airport_group_name",
            } | {c.lower() for c in PERIOD_COLUMNS}
            for k, v in row.items():
                if (k or "").strip().lower() not in excluded_lower:
                    record[k] = v
        out.append(record)
    return out


def fetch(url, retries=3, backoff=3.0):
    """
    GET with retries. CAA's server intermittently returns 502s or resets the
    connection under repeated requests -- neither is a real "this file
    doesn't exist" signal, so it's worth a couple of retries before giving
    up, rather than dropping the month/table on the first hiccup.
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=30, headers={"User-Agent": "flight-demand-ni-research/1.0"})
            if resp.status_code in (502, 503, 504) and attempt < retries:
                time.sleep(backoff * attempt)
                continue
            resp.raise_for_status()
            return resp
        except requests.exceptions.ConnectionError as e:
            last_exc = e
            if attempt < retries:
                time.sleep(backoff * attempt)
                continue
            raise
        except requests.exceptions.HTTPError as e:
            last_exc = e
            if e.response is not None and e.response.status_code in (502, 503, 504) and attempt < retries:
                time.sleep(backoff * attempt)
                continue
            raise
    raise last_exc


def month_range(start_year, start_month, end_date):
    y, m = start_year, start_month
    while (y, m) <= (end_date.year, end_date.month):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    pax_rows, mov_rows = [], []
    today = date.today()

    for year, month in month_range(START_YEAR, START_MONTH, today):
        page_url = month_page_url(year, month)
        cache_name = f"{year}-{month:02d}"
        try:
            page = fetch(page_url)
        except requests.HTTPError as e:
            print(f"skip {cache_name}: page not available ({e})")
            continue
        except requests.RequestException as e:
            print(f"skip {cache_name}: request failed ({e})")
            continue

        links_by_kind = find_csv_links(page.text, page_url)
        for kind, link in links_by_kind.items():
            # Stable, kind-based cache filename -- lets a re-run skip
            # straight past anything already pulled, and makes the raw/
            # folder legible (one passengers + one movements file per month)
            # instead of an opaque hash per link.
            raw_cache_path = RAW_DIR / f"{cache_name}_{kind}.csv"
            if raw_cache_path.exists():
                content = raw_cache_path.read_bytes()
            else:
                try:
                    file_resp = fetch(link)
                except requests.RequestException as e:
                    print(f"  skip link {link}: {e}")
                    continue
                content = file_resp.content
                raw_cache_path.write_bytes(content)
                time.sleep(REQUEST_DELAY_SECONDS)

            # classify_csv is a cheap sanity check that we actually got the
            # table we asked for (link text can't be trusted 100%), not the
            # primary filter -- that's now done before downloading.
            if classify_csv(content) != kind:
                print(f"  warning: {cache_name} {kind} link didn't look like a {kind} file after download -- check {raw_cache_path}")
                continue

            text = content.decode("utf-8-sig", errors="ignore")
            rows = rows_for_target_airports(text, kind, year, month)
            if kind == "passengers":
                pax_rows.extend(rows)
            else:
                mov_rows.extend(rows)

        print(f"done {cache_name}: {len(pax_rows)} pax rows, {len(mov_rows)} movement rows so far")

    def write_csv(path, rows):
        if not rows:
            print(f"no rows collected for {path.name} -- nothing written")
            return
        fieldnames = sorted({k for r in rows for k in r.keys()})
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {len(rows)} rows to {path}")

    write_csv(PROCESSED_DIR / "passengers_monthly_raw.csv", pax_rows)
    write_csv(PROCESSED_DIR / "movements_monthly_raw.csv", mov_rows)
    print("\nNext: run src/build_panel.py to join these into the tidy monthly panel.")


if __name__ == "__main__":
    main()
