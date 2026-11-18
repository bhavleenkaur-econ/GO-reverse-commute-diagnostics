"""Write the narrative notebook. It reads the tables produced by scripts/run_analysis.py."""

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks"
OUT.mkdir(exist_ok=True)

SETUP = """import sys
from pathlib import Path
ROOT = Path.cwd().resolve()
if not (ROOT / "src").exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
import pandas as pd
from IPython.display import Image, display
pd.set_option("display.max_colwidth", 120)
pd.set_option("display.width", 160)
from reverse.pipeline import load
table, stations, toronto, recs, meta = load()
FIG = ROOT / "reports" / "figures"
"""


def md(text):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text):
    return nbf.v4.new_code_cell(text.strip())


cells = [
    md("""
# Reverse commuting from Toronto, and whether GO serves it

I walk through the analysis in one notebook, in the order I did the work. Each section reads the tables written by `scripts/run_analysis.py`, so every number shown here comes from the run.

## 1. Objective and inputs

My objective is to find where Toronto residents who work in the suburbs are numerous, and where the GO and UP timetable does not get them to work in the morning and home in the evening. I cannot observe ridership. Station boardings and PRESTO are not on the open-data page, so I measured the market from the Census commuting flows and the service from the published timetable.

I first assembled the inputs and recorded each one in `data/SOURCES.md`.
"""),
    code(SETUP + """
print((ROOT / "data" / "SOURCES.md").read_text())
"""),
    md("""
## 2. The reverse market, 2016 to 2021

I first classified every flow between census subdivisions. A reverse commute is a Toronto home and a usual workplace in a subdivision with a GO or UP station. A Toronto home with a workplace in a subdivision without a station is kept apart, so it does not inflate the market. The 2021 file names the workplace without a code, so I matched names to the 2021 boundary file. I then set the 2016 flows beside 2021 as context, because work from home changed the denominator between the two counts.
"""),
    code("""
show = toronto.copy()
show["reverse_share_of_usual_pow"] = show.reverse / show.usual_place_of_work
show.round(3)
"""),
    code("""
cols = ["csd_name", "reverse_2016", "reverse_2021", "reverse_change_pct", "inbound_2016", "inbound_2021",
        "inbound_change_pct", "toronto_share_of_jobs_2021", "wfh_share_2016", "wfh_share_2021"]
display(table.sort_values("reverse_2021", ascending=False)[cols].round(3).head(12))
display(Image(FIG / "flow_change.png"))
"""),
    md("""
The 2021 Census was taken during a lockdown, so I read the 2021 counts as a floor on the in-person market and the 2016 counts as the pre-pandemic pattern. Neither is a forecast.

## 3. Counter-peak supply

I then built every one-seat ride that boards at a Toronto station and gets off at a destination station, and the reverse for the trip home. The Census places a home only at the subdivision level, so a rider can board at any Toronto station. For each destination station I measured the arrival headway from 06:30 to 09:30, the longest midday gap, the return headway toward Toronto from 15:30 to 18:30, and the span. A band with fewer than two trains gets the band length as its headway.
"""),
    code("""
cols = ["station_name", "line_name", "csd_name", "first_arrival_clock", "am_arrivals", "am_arrival_headway_min",
        "midday_max_gap_min", "pm_return_headway_min", "last_return_clock", "weekday_span_hours", "station_supply_score"]
stations.sort_values(["line_name", "station_supply_score"], ascending=[True, False])[cols].round(1)
"""),
    code("""
display(Image(FIG / "timetable_strip.png"))
"""),
    md("""
The strip shows the pattern the scores summarise. Some lines run trains out of Toronto all day. Others run only toward Union in the morning and away from it in the evening, so a reverse commuter has no train in either direction when it is needed.

## 4. The last mile

A train that arrives on time still has to reach the workplace. I drew 800 m and 2 km straight-line rings around each destination station, put the 2021 jobs by census tract of work into them, and measured the share of each subdivision's jobs within 2 km of any of its stations. I then counted the local bus routes leaving each station in the AM band and the scheduled wait from a train to the next bus.
"""),
    code("""
cols = ["csd_name", "station_name", "jobs_800m", "jobs_2km", "jobs_2km_share", "am_bus_routes_best", "train_to_bus_wait_min"]
display(table.sort_values("jobs_2km_share", ascending=False)[cols].round(2))
display(Image(FIG / "jobs_coverage.png"))
"""),
    md("""
## 5. Market against service

Only after those tables were complete did I score the destinations. Every score is a percentile rank from 0 to 100, and higher is better. The market score combines the number of Toronto residents working in the municipality with their share of its jobs. The rail score ranks the best station in each municipality. A destination above the market median and below the rail median is a mismatch.

A relative rank cannot flag a gap that most destinations share. In my first run, Vaughan and Markham sat above the rail median with no train from Toronto arriving between 06:30 and 09:30. I then added a rule: a destination with no morning arrival sits on the thin-service side at any rank.
"""),
    code("""
cols = ["csd_name", "station_name", "market_score", "rail_score", "last_mile_score", "no_am_arrival", "quadrant",
        "near_cut", "threshold_class"]
display(table.sort_values("market_score", ascending=False)[cols].round(1))
display(Image(FIG / "quadrant.png"))
"""),
    code("""
for key in ["market_median", "rail_median", "rail_p40", "rail_p60", "mismatch_no_am", "mismatch_clear",
            "mismatch_threshold_sensitive", "mismatch_looser_only", "reference_n"]:
    print(f"{key}: {meta[key]}")
"""),
    md("""
## 6. Which gap to act on

For each mismatch I compared the rail and last-mile scores with the destinations that have both a strong market and strong service. When no train arrives in the morning band, the timetable is the binding gap, because nothing at the station end can be used without a train. Otherwise the larger deficit is the gap. I set the supporting evidence next to the evidence that cuts against it.
"""),
    code("""
evidence = pd.read_csv(ROOT / "reports" / "evidence.csv")
for r in evidence.itertuples():
    print(f"{r.csd_name}: {r.primary_label}, confidence {r.confidence}")
    print(f"  Supporting: {r.supporting_evidence}")
    print(f"  Against: {r.contradictory_evidence}")
    print()
"""),
    code("""
recs[["csd_name", "best_station", "primary_gap", "confidence", "action", "owner", "kpi"]]
"""),
    md("""
## 7. Constraints

The 2021 flow is set beside a 2026 timetable, and the 2021 count was taken during a lockdown. Statistics Canada rounds counts at random to a multiple of 5. The flow table places homes only at the subdivision level. The last mile uses straight-line rings, and bus waits are scheduled. The TTC subway reaches Vaughan Metropolitan Centre and is outside a GO-only analysis, so a GO gap is not the same as a transit gap. The full brief is in `reports/executive_brief.md`, and the map of flows is `reports/flow_map.html`.
"""),
]

book = nbf.v4.new_notebook()
book.cells = cells
book.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
nbf.write(book, OUT / "reverse_commute.ipynb")
print(OUT / "reverse_commute.ipynb")
