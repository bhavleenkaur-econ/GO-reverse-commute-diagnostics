"""Rank the reverse market against counter-peak supply, and name the larger gap at each mismatch.

Scores run from 0 to 100 and a higher score is better. Each input is a percentile rank among the
destination subdivisions, or among the destination stations for the station supply score.
"""

import numpy as np
import pandas as pd

from . import config as C
from .gtfs import clock


def _pct(values):
    return values.rank(method="average", pct=True) * 100


def _pct_lower_better(values):
    # Stations tied at the band-length fill have no usable train in that band. They share the
    # worst rank, rather than the middle of the tie, so a missing train cannot look average.
    return 100 - values.rank(method="max", pct=True) * 100


def _pct_higher_better(values):
    return values.rank(method="min", pct=True) * 100


def station_supply(stations):
    """Mean of four ranks. A short headway and a short gap score higher, and a longer span scores higher."""
    out = stations.copy()
    parts = [
        _pct_lower_better(out.am_arrival_headway_min),
        _pct_lower_better(out.pm_return_headway_min),
        _pct_lower_better(out.midday_max_gap_min),
        _pct_higher_better(out.weekday_span_hours),
    ]
    out["station_supply_score"] = pd.concat(parts, axis=1).mean(axis=1)
    return out


def best_station(stations):
    """The station in each subdivision with the highest supply score. Ties go to more AM arrivals, then more weekday arrivals."""
    ordered = stations.sort_values(
        ["csd_code", "station_supply_score", "am_arrivals", "weekday_arrivals", "station_id"],
        ascending=[True, False, False, False, True],
    )
    best = ordered.drop_duplicates("csd_code")
    others = ordered.groupby("csd_code").station_name.apply(lambda s: ", ".join(s.iloc[1:]))
    routes = stations.groupby("csd_code").am_bus_routes.max().rename("am_bus_routes_best")
    best = best.set_index("csd_code").join(others.rename("other_stations")).join(routes).reset_index()
    return best


def score(dest):
    out = dest.copy()
    out["market_score"] = pd.concat(
        [_pct(out.reverse_2021), _pct(out.toronto_share_of_jobs_2021)], axis=1
    ).mean(axis=1)
    out["rail_score"] = _pct(out.station_supply_score)
    out["last_mile_score"] = pd.concat(
        [_pct(out.jobs_2km_share), _pct(out.am_bus_routes_best.fillna(0))], axis=1
    ).mean(axis=1)
    m_cut = out.market_score.median()
    r_cut = out.rail_score.median()
    high = out.market_score >= m_cut
    # A reverse commuter cannot use a station that no train from Toronto reaches in the AM band,
    # so that destination sits on the thin-service side whatever its rank.
    out["no_am_arrival"] = out.am_arrivals.fillna(0).eq(0)
    strong = (out.rail_score >= r_cut) & ~out.no_am_arrival
    out["quadrant"] = np.select(
        [high & ~strong, high & strong, ~high & strong],
        ["mismatch", "market and service", "service ahead of market"],
        default="market and service both thin",
    )
    out["rail_gap"] = r_cut - out.rail_score
    market_near = (out.market_score - m_cut).abs().le(C.NEAR_CUT_POINTS)
    rail_near = (out.rail_score - r_cut).abs().le(C.NEAR_CUT_POINTS) & ~out.no_am_arrival
    out["near_cut"] = market_near | rail_near
    p40 = float(out.rail_score.quantile(0.40))
    p60 = float(out.rail_score.quantile(0.60))
    no_am = out.no_am_arrival
    below40 = out.rail_score < p40
    below50 = out.rail_score < r_cut
    below60 = out.rail_score < p60
    out["threshold_class"] = np.select(
        [high & no_am, high & below40, high & below50, high & below60],
        ["no AM arrival", "clear", "threshold-sensitive", "looser cut only"],
        default="not a mismatch",
    )
    out.attrs.update(
        {
            "market_median": float(m_cut),
            "rail_median": float(r_cut),
            "rail_p40": p40,
            "rail_p60": p60,
            "mismatch_no_am": sorted(out.loc[high & no_am, "csd_name"]),
            "mismatch_clear": sorted(out.loc[high & ~no_am & below40, "csd_name"]),
            "mismatch_threshold_sensitive": sorted(out.loc[high & ~no_am & below50 & ~below40, "csd_name"]),
            "mismatch_looser_only": sorted(out.loc[high & ~no_am & below60 & ~below50, "csd_name"]),
        }
    )
    return out


def confidence_label(primary_deficit, is_tie, near_cut):
    """Low when the larger gap is under 10 points. Medium for a tie or a destination near the cut."""
    if pd.isna(primary_deficit) or primary_deficit < C.LOW_DEFICIT:
        return "low"
    if is_tie or near_cut:
        return "medium"
    return "high"


def diagnose(scored):
    """Compare each mismatch with the destinations that have both a strong market and strong service."""
    out = scored.copy()
    ref = out[out.quadrant.eq("market and service")]
    ref_rail = ref.rail_score.median()
    ref_lm = ref.last_mile_score.median()
    out["deficit_rail"] = ref_rail - out.rail_score
    out["deficit_last_mile"] = ref_lm - out.last_mile_score
    focus = out.quadrant.eq("mismatch")
    # Without a morning arrival nothing downstream of the train can be used, so the timetable is
    # the binding gap and the last mile is reported as the next constraint.
    binding = focus & out.no_am_arrival
    primary = np.where(binding | (out.deficit_rail >= out.deficit_last_mile), "rail", "last_mile")
    out["primary_gap"] = np.where(focus, primary, None)
    big = out[["deficit_rail", "deficit_last_mile"]].max(axis=1)
    small = out[["deficit_rail", "deficit_last_mile"]].min(axis=1)
    out["primary_deficit"] = np.where(focus, np.where(binding, out.deficit_rail, big), np.nan)
    out["is_tie"] = focus & ~binding & (big - small).lt(C.TIE_MARGIN)
    out["confidence"] = None
    out.loc[focus, "confidence"] = [
        ("medium" if r.near_cut else "high")
        if r.no_am_arrival
        else confidence_label(r.primary_deficit, bool(r.is_tie), bool(r.near_cut))
        for r in out.loc[focus].itertuples()
    ]
    out.loc[focus, "supporting_evidence"] = [_support(r) for r in out.loc[focus].itertuples()]
    out.loc[focus, "contradictory_evidence"] = [_contradict(r) for r in out.loc[focus].itertuples()]
    out.attrs.update(scored.attrs)
    out.attrs["reference_n"] = int(len(ref))
    out.attrs["reference_rail"] = float(ref_rail) if pd.notna(ref_rail) else None
    out.attrs["reference_last_mile"] = float(ref_lm) if pd.notna(ref_lm) else None
    return out


def _n(value, digits=0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if number != number:
        return "n/a"
    return f"{number:,.{digits}f}"


def rail_fact(r):
    return (
        f"at {r.station_name}, the best station, the first train from Toronto arrives at {r.first_arrival_clock or 'no time'}, "
        f"{_n(r.am_arrivals)} trains arrive from 06:30 to 09:30, the longest midday gap is {_n(r.midday_max_gap_min)} minutes, "
        f"and the last train back to Toronto leaves at {r.last_return_clock or 'no time'}"
    )


def last_mile_fact(r):
    wait = (
        f" and the median wait from an AM train to a bus is {_n(r.train_to_bus_wait_min)} minutes"
        if pd.notna(r.train_to_bus_wait_min)
        else ""
    )
    return (
        f"{_n(100 * r.jobs_2km_share)}% of the municipality's jobs sit within 2 km of a station, "
        f"the station with the most local service has {_n(r.am_bus_routes_best)} bus routes leaving in the AM band{wait}"
    )


def _support(r):
    if r.primary_gap == "rail" and r.no_am_arrival:
        return f"No train from Toronto reaches the municipality between 06:30 and 09:30: {rail_fact(r)}."
    if r.primary_gap == "rail":
        return f"The larger gap is the counter-peak timetable: {rail_fact(r)}."
    return f"The larger gap is the station-to-workplace link: {last_mile_fact(r)}."


def _contradict(r):
    other = "last_mile" if r.primary_gap == "rail" else "rail"
    gap = r.deficit_last_mile if other == "last_mile" else r.deficit_rail
    label = {"rail": "counter-peak timetable", "last_mile": "station-to-workplace link"}[other]
    fact = last_mile_fact(r) if other == "last_mile" else rail_fact(r)
    if gap <= 0:
        return f"The {label} sits {abs(gap):.0f} points above the reference destinations: {fact}."
    return f"The {label} is also behind, by {gap:.0f} points: {fact}."


ACTIONS = {
    "rail": {
        "action": "Add counter-peak trains from Toronto that arrive before 09:00, and a return after 17:00, before adding peak trips toward Union.",
        "owner": "Metrolinx service planning",
        "kpi": "First arrival from Toronto, AM arrival headway, and last departure back to Toronto",
    },
    "last_mile": {
        "action": "Link the station to the employment areas with the municipal operator, timed to the trains from Toronto.",
        "owner": "Municipal transit operator, with Metrolinx",
        "kpi": "Share of jobs within 2 km reached by a timed bus, and the AM train-to-bus wait",
    },
}


def recommendations(diagnosed):
    rows = []
    for r in diagnosed[diagnosed.quadrant.eq("mismatch")].sort_values("market_score", ascending=False).itertuples():
        a = ACTIONS[r.primary_gap]
        rows.append(
            {
                "csd_name": r.csd_name,
                "best_station": r.station_name,
                "primary_gap": C.CONSTRAINT_LABELS[r.primary_gap],
                "confidence": r.confidence,
                "reverse_2021": r.reverse_2021,
                "action": a["action"],
                "owner": a["owner"],
                "kpi": a["kpi"],
            }
        )
    return pd.DataFrame(rows)


def evidence_frame(diagnosed):
    keep = [
        "csd_name", "station_name", "reverse_2021", "toronto_share_of_jobs_2021", "market_score", "rail_score",
        "last_mile_score", "no_am_arrival", "threshold_class", "near_cut", "primary_gap", "deficit_rail", "deficit_last_mile",
        "is_tie", "confidence", "supporting_evidence", "contradictory_evidence",
    ]
    out = diagnosed[diagnosed.quadrant.eq("mismatch")][keep].sort_values("market_score", ascending=False).copy()
    out["primary_label"] = out.primary_gap.map(C.CONSTRAINT_LABELS)
    return out


__all__ = ["station_supply", "best_station", "score", "diagnose", "recommendations", "evidence_frame", "clock"]
