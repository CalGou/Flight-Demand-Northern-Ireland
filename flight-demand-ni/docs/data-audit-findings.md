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

## Not yet resolved

- **Data freshness lag**: CAA updates roughly fortnightly and not every airport is submitted within that window each cycle — the most recent 1–2 months in any pull may be provisional/incomplete. Worth a completeness check once the ingestion script has actually run.
- **COVID-19 period (2020–2022)**: within scope (post-2015) but will need explicit handling per the parameters doc — flagging as an anomaly period rather than treating it as a normal seasonal pattern.
- The ingestion script hasn't been run end-to-end yet against live data (this environment's network access doesn't reach caa.co.uk) — first real run should happen on your machine, and is worth a quick manual sanity check against the March 2026 figures already confirmed above.
