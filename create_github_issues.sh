
Cloud
/

















Create github issues · SH
#!/usr/bin/env bash
# Bulk-create the Flight Demand NI backlog as GitHub Issues + labels.
#
# Requires: GitHub CLI (`gh`) installed and authenticated (`gh auth login`),
# and an existing repo. Run this from your local machine, not from Claude.
#
# Usage:
#   REPO="your-github-username/flight-demand-ni" ./create_github_issues.sh
 
set -euo pipefail
 
if [ -z "${REPO:-}" ]; then
  echo "Set REPO first, e.g.: REPO=yourname/flight-demand-ni ./create_github_issues.sh"
  exit 1
fi
 
echo "Creating labels in $REPO..."
gh label create "data-audit"   --repo "$REPO" --color "0E8A16" --force
gh label create "cleaning-eda" --repo "$REPO" --color "1D76DB" --force
gh label create "baseline"     --repo "$REPO" --color "FBCA04" --force
gh label create "ml-models"    --repo "$REPO" --color "D93F0B" --force
gh label create "writeup"      --repo "$REPO" --color "5319E7" --force
gh label create "polish"       --repo "$REPO" --color "C5DEF5" --force
 
create_issue() {
  local label="$1"
  local title="$2"
  local body="$3"
  gh issue create --repo "$REPO" --label "$label" --title "$title" --body "$body"
}
 
# Epic 1: Data Audit
create_issue "data-audit" "Set up repo structure & environment" "Python env, requirements.txt, README skeleton."
create_issue "data-audit" "Pull CAA monthly airport data (BFS, BHD, LDY)" "Full available history from the UK CAA UK Airport Data tables."
create_issue "data-audit" "Determine per-airport data format consistency & earliest usable month" ""
create_issue "data-audit" "Document known anomalies/gaps" "COVID-19 period, suppressed values, format/table changes over the years."
create_issue "data-audit" "Record audit findings back into project parameters doc" "Finalise the actual start date (§3/§12 of the parameters doc)."
 
# Epic 2: Cleaning & EDA
create_issue "cleaning-eda" "Build ingestion script: raw CAA files -> tidy monthly panel" "Output: one row per airport x month."
create_issue "cleaning-eda" "Handle missing/suppressed values" "Document the treatment chosen."
create_issue "cleaning-eda" "Flag COVID-era anomaly period" "Explicit feature/exclusion flag for the structural break."
create_issue "cleaning-eda" "EDA: seasonality, trend, airport-to-airport comparison" ""
create_issue "cleaning-eda" "EDA: pre/post-COVID recovery pattern" ""
create_issue "cleaning-eda" "(If pursued) Source & merge supplementary features" "Economic, tourism, or weather data."
 
# Epic 3: Baseline & Statistical Models
create_issue "baseline" "Build evaluation harness" "Time-based train/test split + walk-forward (rolling-origin) validation."
create_issue "baseline" "Naive & seasonal-naive baseline models" ""
create_issue "baseline" "SARIMA/ETS (or Prophet) model per airport" ""
create_issue "baseline" "Compare baseline vs statistical models" "MAE/RMSE/MAPE."
 
# Epic 4: ML Models
create_issue "ml-models" "Feature engineering" "Lag features, rolling windows, calendar/seasonal features."
create_issue "ml-models" "XGBoost/LightGBM model per airport" ""
create_issue "ml-models" "Full model comparison table" "Baseline vs statistical vs ML."
create_issue "ml-models" "(Stretch) LSTM/temporal model" "Only if data volume justifies it."
 
# Epic 5: Write-up & Dashboard
create_issue "writeup" "Write README: methodology, findings, model comparison" ""
create_issue "writeup" "Produce final forecast outputs & charts per airport" ""
create_issue "writeup" "(Optional) Build Streamlit dashboard" ""
 
# Epic 6: Portfolio Polish
create_issue "polish" "Clean up repo for public visibility" "Licence, pinned dependencies, clear run instructions."
create_issue "polish" "Final proofread of write-up" ""
create_issue "polish" "Link finished project from CV / portfolio site" ""
 
echo "Done. Consider adding these to a GitHub Projects board and moving them through To Do / In Progress / Done."
 

