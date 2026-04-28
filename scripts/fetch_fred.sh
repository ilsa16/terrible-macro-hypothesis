#!/usr/bin/env bash
# Fetch FRED series used by the U.S. corporate debt dashboard.
#
# Modes:
#   - If FRED_API_KEY is set (via .env or env var), use the official JSON API
#     (full history, no date cap).
#   - Otherwise fall back to the public fredgraph.csv endpoint, which caps
#     *daily* series at ~3 years.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${SCRIPT_DIR}/.."
OUT_DIR="${ROOT}/data/fred"
mkdir -p "${OUT_DIR}"

# load .env if present
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

START=${START:-2005-01-01}
SERIES=(
  # Aggregate nonfinancial corporate debt (quarterly, back to 1945)
  BCNSDODNS
  # ICE BofA daily effective yields — FRED only retains ~3yr rolling
  BAMLC0A0CMEY
  BAMLC0A4CBBBEY
  BAMLH0A0HYM2EY
  BAMLC0A4CBBB
  # Moody's seasoned Aaa/Baa corporate bond yields (daily, since 1983/1986)
  # Used as long-history IG/BBB cost-of-debt proxy when ICE series are too short
  DAAA
  DBAA
  # Monthly versions go back to 1919 (useful for very long history)
  AAA
  BAA
)

fetch_api() {
  local sid="$1"
  local url="https://api.stlouisfed.org/fred/series/observations?series_id=${sid}&api_key=${FRED_API_KEY}&file_type=json&observation_start=${START}"
  curl -sSL --max-time 60 "${url}" -o "${OUT_DIR}/${sid}_api.json"
  python3.11 - "${sid}" "${OUT_DIR}" <<'PY'
import json, sys
sid, out_dir = sys.argv[1], sys.argv[2]
with open(f"{out_dir}/{sid}_api.json") as f:
    d = json.load(f)
obs = d.get("observations", [])
with open(f"{out_dir}/{sid}_raw.csv", "w") as f:
    f.write(f"observation_date,{sid}\n")
    for o in obs:
        if o["value"] != ".":
            f.write(f"{o['date']},{o['value']}\n")
PY
  rm -f "${OUT_DIR}/${sid}_api.json"
}

fetch_csv_fallback() {
  local sid="$1"
  local url="https://fred.stlouisfed.org/graph/fredgraph.csv?id=${sid}&cosd=${START}"
  curl -sSL --max-time 60 "${url}" -o "${OUT_DIR}/${sid}_raw.csv"
}

if [[ -n "${FRED_API_KEY:-}" ]]; then
  MODE="api"
else
  MODE="csv (3yr cap)"
fi
echo "mode: ${MODE}; start: ${START}"
echo

for S in "${SERIES[@]}"; do
  echo "== ${S} =="
  if [[ "${MODE}" == "api" ]]; then
    fetch_api "${S}"
  else
    fetch_csv_fallback "${S}"
  fi
  LINES=$(wc -l < "${OUT_DIR}/${S}_raw.csv")
  FIRST=$(sed -n '2p' "${OUT_DIR}/${S}_raw.csv" | cut -d, -f1)
  LAST=$(tail -1 "${OUT_DIR}/${S}_raw.csv" | cut -d, -f1)
  echo "  rows=${LINES} range=${FIRST}..${LAST}"
done

echo
echo "done -> ${OUT_DIR}"
