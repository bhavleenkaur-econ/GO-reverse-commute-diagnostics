import duckdb
import pandas as pd
import pytest

from reverse import config as C
from reverse import flows, gtfs, mismatch

T = C.TORONTO_CODE


def test_classify_flows():
    df = pd.DataFrame(
        {
            "home_code": [T, T, T, "3521005", "3521005", "3521005"],
            "work_code": [T, "3521005", "9999999", T, "3521005", "3519038"],
            "workers": [10, 20, 30, 40, 50, 60],
        }
    )
    out = flows.classify(df, station_codes={T, "3521005", "3519038"})
    assert list(out.flow_class) == [
        "local", "reverse", "toronto_out_no_station", "inbound", "local", "suburb_to_suburb",
    ]


def test_match_years_lists_missing_code():
    out = flows.match_years(["3521005", "3519038"], ["3521005"])
    assert dict(zip(out.csd_code, out.in_2016)) == {"3521005": True, "3519038": False}


def _events(rows):
    cols = ["operator", "line", "trip_id", "day_type", "service_date", "station_id", "seq",
            "arr_sec", "dep_sec", "can_board", "can_alight"]
    return pd.DataFrame(rows, columns=cols)


@pytest.fixture
def con():
    db = duckdb.connect()
    ev = _events(
        [
            # Through Union: boards at Kipling and Union, alights at Oakville.
            ("go", "LW", "T1", "weekday", "2026-11-18", "KIP", 1, 25000, 25000, True, True),
            ("go", "LW", "T1", "weekday", "2026-11-18", "UN", 2, 26000, 26100, True, True),
            ("go", "LW", "T1", "weekday", "2026-11-18", "OAK", 3, 28000, 28000, True, True),
            # Ends at Union: only a back leg.
            ("go", "LW", "T2", "weekday", "2026-11-18", "OAK", 1, 30000, 30000, True, True),
            ("go", "LW", "T2", "weekday", "2026-11-18", "UN", 2, 32000, 32000, False, True),
            # No boarding at Union.
            ("go", "LW", "T3", "weekday", "2026-11-18", "UN", 1, 34000, 34000, False, True),
            ("go", "LW", "T3", "weekday", "2026-11-18", "OAK", 2, 36000, 36000, True, True),
            # No alighting at Oakville.
            ("go", "LW", "T4", "weekday", "2026-11-18", "UN", 1, 38000, 38000, True, True),
            ("go", "LW", "T4", "weekday", "2026-11-18", "OAK", 2, 40000, 40000, True, False),
        ]
    )
    db.register("ev", ev)
    db.execute("CREATE TABLE rail_events AS SELECT * FROM ev")
    stations = pd.DataFrame(
        {"station_id": ["KIP", "UN", "OAK"], "in_toronto": [True, True, False], "csd_code": [T, T, "3524001"]}
    )
    gtfs.register_station_sets(db, stations)
    return db


def test_reverse_pairs(con):
    pairs = gtfs.build_pairs(con)
    out = pairs[pairs.leg.eq("out")].sort_values("toronto_id")
    back = pairs[pairs.leg.eq("back")]
    assert set(zip(out.trip_id, out.toronto_id)) == {("T1", "KIP"), ("T1", "UN")}
    assert out.set_index("toronto_id").loc["UN", "ride_sec"] == 28000 - 26100
    assert list(zip(back.trip_id, back.dest_id, back.toronto_id)) == [("T2", "OAK", "UN")]
    assert not pairs.trip_id.isin(["T3", "T4"]).any()


def test_headway_fill():
    raw = pd.DataFrame(
        {
            "station_id": ["A", "B"],
            "am_arrival_headway_min": [30.0, None],
            "am_arrival_max_gap_min": [30.0, None],
            "am_gap_n": [5, 0],
            "am_union_headway_min": [30.0, None],
            "am_union_gap_n": [5, 0],
            "midday_max_gap_min": [60.0, None],
            "midday_gap_n": [4, 0],
            "pm_return_headway_min": [None, 20.0],
            "pm_gap_n": [0, 3],
            "first_arrival_sec": [25000, 60000],
            "last_return_sec": [80000, 30000],
            "am_arrivals": [6, 0],
            "pm_returns": [0, 4],
        }
    )
    out = gtfs.apply_fill(raw).set_index("station_id")
    assert out.loc["B", "am_arrival_headway_min"] == 180
    assert out.loc["B", "midday_max_gap_min"] == 330
    assert out.loc["A", "pm_return_headway_min"] == 180
    assert out.loc["A", "am_arrival_headway_min"] == 30
    assert out.loc["B", "weekday_span_hours"] == 0


def test_missing_band_gets_worst_rank():
    st = pd.DataFrame(
        {
            "am_arrival_headway_min": [15.0, 30.0, 180.0, 180.0],
            "pm_return_headway_min": [15.0, 30.0, 180.0, 180.0],
            "midday_max_gap_min": [30.0, 60.0, 330.0, 330.0],
            "weekday_span_hours": [18.0, 16.0, 0.0, 0.0],
        }
    )
    out = mismatch.station_supply(st)
    assert out.station_supply_score.iloc[2] == out.station_supply_score.iloc[3]
    assert out.station_supply_score.iloc[2] < out.station_supply_score.iloc[1] < out.station_supply_score.iloc[0]
    assert mismatch._pct_lower_better(st.am_arrival_headway_min).iloc[2] == 0


def _dest(n=8):
    return pd.DataFrame(
        {
            "csd_name": [f"D{i}" for i in range(n)],
            "reverse_2021": [100.0 * (i + 1) for i in range(n)],
            "toronto_share_of_jobs_2021": [0.01 * (i + 1) for i in range(n)],
            "station_supply_score": [10.0, 80.0, 20.0, 70.0, 30.0, 60.0, 5.0, 90.0],
            "jobs_2km_share": [0.2] * n,
            "am_bus_routes_best": [3] * n,
            "am_arrivals": [4, 4, 4, 4, 4, 4, 0, 0],
        }
    )


def test_quadrant_and_no_am_rule():
    out = mismatch.score(_dest()).set_index("csd_name")
    # D7 has the top market and the top rail rank, but no morning train.
    assert out.loc["D7", "quadrant"] == "mismatch"
    assert out.loc["D7", "threshold_class"] == "no AM arrival"
    assert out.loc["D5", "quadrant"] == "market and service"
    assert out.loc["D4", "quadrant"] == "mismatch"
    assert out.loc["D0", "quadrant"] == "market and service both thin"
    assert out.loc["D1", "quadrant"] == "service ahead of market"


def test_near_cut():
    scored = mismatch.score(_dest())
    m_cut = scored.attrs["market_median"]
    near = scored[(scored.market_score - m_cut).abs().le(C.NEAR_CUT_POINTS)]
    assert near.near_cut.all()


def test_confidence_label():
    assert mismatch.confidence_label(5, False, False) == "low"
    assert mismatch.confidence_label(20, True, False) == "medium"
    assert mismatch.confidence_label(20, False, True) == "medium"
    assert mismatch.confidence_label(20, False, False) == "high"


def test_clock_past_midnight():
    assert gtfs.clock(25 * 3600 + 5 * 60) == "01:05 next day"
    assert gtfs.clock(None) is None
