"""Build the reverse commute tables, figures, and brief from the raw files. Run from the project root."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reverse.pipeline import run  # noqa: E402

if __name__ == "__main__":
    table, _stations, toronto, recs, meta = run()
    print(toronto.to_string(index=False))
    focus = table[table.quadrant.eq("mismatch")][
        ["csd_name", "station_name", "reverse_2021", "market_score", "rail_score", "last_mile_score", "primary_gap", "confidence"]
    ]
    print()
    print(focus.sort_values("market_score", ascending=False).to_string(index=False))
    print(f"\n{len(focus)} mismatches among {meta['n_destinations']} destinations, {len(recs)} recommendation rows")
