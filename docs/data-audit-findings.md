# Data Audit Findings

Covers Epic 1 tickets: locating the CAA tables, confirming per-airport format consistency, and setting the project's actual historical start date.

## Source confirmed

The UK CAA's "UK Airport Data" publishes monthly, per-airport statistics as two relevant tables:

- **Table 09 — Terminal and Transit Passengers**: `reporting_airport_name`, `total_pax_this_period`, `terminal_pax_this_period`, `transit_pax_this_period`, plus the prior period's figures and percent change.
- **Table 05 — Air Transport Movements**: the equivalent for flight movements.

Both are published as CSV (and PDF) on a page per calendar month, e.g. `caa.co.uk/.../uk-airport-data-2026/march-2026/`. Verified against the March 2026 release, which contains current rows for all three target airports:

- `BELFAST INTERNATIONAL`
- `BELFAST CITY (GEORGE BEST)`
- `CITY OF DERRY (EGLINTON)`

## Start date: January 2015

CAA's site structure itself draws the line: individual month/year pages with CSV downloads exist from **January 2015** onward. Everything before that (1990–2014, and earlier archives back to 1973) is described by CAA as "scanned copies of paper publications" — not machine-readable, and out of scope for a clean pipeline without manual OCR/transcription work that isn't worth it for this project.

Checked the January 2015 release directly to confirm the schema hasn't drifted: it has the same Table 09/Table 05 CSV structure as March 2026, so the full **January 2015 → present** window (132+ months) should be usable with one ingestion script rather than needing separate handling per era.

This resolves the open question in the parameters doc — updating §3/§12 there to fix January 2015 as the confirmed start date, rather than "TBD."

## A structural quirk worth flagging

Each month's CSV isn't a running time series — it contains only that month (`this_period`) and the prior month (`last_period`), not all history. So building the full monthly panel means pulling every monthly release since Jan 2015 individually (roughly 132 pages × 2 tables), not one bulk download. `src/ingest_caa_data.py` handles this: it walks every month page, downloads and caches the raw CSVs, and keeps only `this_period` from each release (the `last_period` column is redundant with the next release's `this_period` and would otherwise duplicate every row).

## Known discontinuity (informational, doesn't affect the 2015+ window)

CAA's own notes flag a June 2001 methodology change (air taxi movements excluded, domestic passenger collection method changed) that breaks comparability with pre-2001 data. Since the working window starts in 2015, this doesn't require any handling now — noted here in case the project scope is ever extended back into the scanned-PDF era.

## Ingestion script: run successfully (25 Aug 2026)

Ran end-to-end on Callum's machine: 408 passenger rows and 2,051 movement rows collected for Jan 2015–Jun 2026 (Jul/Aug 2026 correctly 404 — not published yet). A handful of individual downloads failed with `502 Bad Gateway` or a reset connection — CAA's server being flaky under repeated requests, not a real gap. Fixed properly rather than by re-running manually: `fetch()` now retries transient 502/503/504 and connection errors up to 3 times with backoff before giving up.

Also corrected a wrong assumption from the original design: `last_period` in the CAA CSVs isn't the prior calendar month, it's the same month a year earlier (year-on-year comparator). Doesn't affect the pipeline since only `this_period` is ever used, but worth knowing if extending the script later.

**Speed fix (25 Aug 2026):** the original script downloaded every table on each month's page (~40 files: ~20 tables x CSV+PDF) just to inspect and discard 38 of them, plus a 1.5s pause after each one -- roughly 5,500 downloads for a full run, which is why it was slow. Each download link's own visible text names its table and format (e.g. "Table 09 Terminal and Transit Passengers (CSV, 6 KB)"), so `find_csv_links` now filters to just the 2 wanted links *before* downloading anything. Full run should now be more like ~280 downloads (2 x 138 months) -- a few minutes, not hours.

Added `src/build_panel.py`, which joins the two raw extracts into `data/processed/monthly_panel.csv` (dedupes on airport+period as a safety net, then reports any (airport, period) combos still missing pax or movement figures — thanks to `ingest_caa_data.py`'s raw-file caching, a re-run only retries what actually failed, no need to redo the whole pull).

## Two real data-quality bugs, found and fixed (25–26 Aug 2026)

The first full run on Callum's machine came back with 45 missing passenger combos and 414 missing movement combos (basically the entire movements table). Root-caused both directly against the actual raw files rather than guessing:

**Table 05 (movements) has never shared Table 09's column names, and changed again partway through.** Jan 2015–Mar 2016 releases use `reporting_airport_name`; every release from **April 2016 onward** renamed it to `rpt_apt_name` (and re-cased `Reporting_Airport_Group_Name` along the way). The ingestion script only ever recognised the old name, so every movements row from April 2016 to the present was silently skipped as "not a target airport" — not missing from CAA's data, just never matched. This is the real explanation for the movements gap, not a network/retry issue.

**Some re-published passenger releases contain a genuinely malformed period value straight from CAA.** E.g. the May 2016 passengers table, re-issued 23 Feb 2017, has `this_period=2016005` (should be `201605`) baked directly into CAA's own CSV — not something the script mangled.

Fix for both, applied at once rather than patched piecemeal: `rows_for_target_airports` now (a) checks the airport-name field under both known column names, and (b) no longer trusts the source file's own period field at all — since the script already knows unambiguously which month's page produced each row, it uses that directly (`canonical_period(year, month)`) instead. Verified against synthetic fixtures reproducing all three real column-schema variants seen so far (old-style movements, new-style movements, malformed-period passengers) before shipping.

## Final result (26 Aug 2026)

Re-ran end-to-end after the fix: **414 rows, 138 months × 3 airports, zero missing passenger or movement data across the full Jan 2015–Jun 2026 range, zero malformed periods.** Spot-checked BFS March 2026 (532,799 total passengers) against the figure independently confirmed earlier in the audit — matches exactly.

One cosmetic follow-up for the cleaning stage (Epic 2), not a bug: the movement metric columns are differently-cased across the two schema eras (e.g. `mov_total_EU_atm` for the 15 old-schema months vs `mov_Total_EU_ATM` for the 123 new-schema months) — same underlying data, just needs normalising into one column name.

## Not yet resolved

- **Data freshness lag**: CAA updates roughly fortnightly and not every airport is submitted within that window each cycle — the most recent 1–2 months in any pull may be provisional/incomplete.
- **COVID-19 period (2020–2022)**: within scope (post-2015) but will need explicit handling per the parameters doc — flagging as an anomaly period rather than treating it as a normal seasonal pattern.
- Movement column name normalisation across the Apr-2016 schema boundary (see above).
