"""
Ingest UK CAA monthly airport data (Table 09: passengers, Table 05: air
transport movements) for Belfast International (BFS), George Best Belfast
City (BHD), and City of Derry (LDY), from January 2015 to the present, into
a single tidy monthly panel.

Why 2015: the CAA publishes each month's data as its own page (one page per
month), and CSV downloads only go back to January 2015 -- earlier data
(1990-2014 and before) exists only as scanned PDF publications, not
machine-readable. Each monthly release CSV contains only that month and the
prior month (a "this_period" / "last_period" pair), not a running series, so
building history means pulling every monthly page rather than one bulk file.

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


def find_csv_links(page_html, page_url):
    """Return every CAA document-download link found on a month page."""
    soup = BeautifulSoup(page_html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/Documents/Download/" in href:
            links.append(requests.compat.urljoin(page_url, href))
    return links


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


def rows_for_target_airports(csv_text, kind, period):
    reader = csv.DictReader(io.StringIO(csv_text))
    out = []
    for row in reader:
        name = (row.get("reporting_airport_name") or "").strip().upper()
        if name not in TARGET_AIRPORTS:
            continue
        this_period = row.get("this_period") or row.get("period") or period
        record = {
            "airport_code": TARGET_AIRPORTS[name],
            "airport_name": name,
            "period": this_period,
        }
        if kind == "passengers":
            record["total_pax"] = row.get("total_pax_this_period")
            record["terminal_pax"] = row.get("terminal_pax_this_period")
            record["transit_pax"] = row.get("transit_pax_this_period")
        else:
            # Column names for Table 05 vary by release; keep everything
            # that isn't an obvious housekeeping field so nothing is lost,
            # and rename the most likely ATM total column if present.
            for k, v in row.items():
                if k not in ("rundate", "reporting_airport_group_name", "reporting_airport_name"):
                    record[k] = v
        out.append(record)
    return out


def fetch(url):
    resp = requests.get(url, timeout=30, headers={"User-Agent": "flight-demand-ni-research/1.0"})
    resp.raise_for_status()
    return resp


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

        for link in find_csv_links(page.text, page_url):
            raw_cache_path = RAW_DIR / f"{cache_name}_{abs(hash(link)) % 100000}.csv"
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

            kind = classify_csv(content)
            if kind is None:
                continue  # not one of the two tables we want (or a PDF)

            text = content.decode("utf-8-sig", errors="ignore")
            rows = rows_for_target_airports(text, kind, cache_name)
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
    print(
        "\nNext: dedupe on (airport_code, period) -- consecutive months' files "
        "overlap by one period -- then join the two tables into the final "
        "tidy monthly panel."
    )


if __name__ == "__main__":
    main()
