"""Classify commuting flows and build the destination table for 2021, with 2016 beside it.

Reverse means a Toronto home and a usual workplace in a subdivision with a GO or UP station.
Inbound means a home outside Toronto and a usual workplace in Toronto.
"""

import numpy as np
import pandas as pd

from . import config as C

FLOW_CLASSES = ["inbound", "reverse", "local", "suburb_to_suburb", "toronto_out_no_station"]


def classify(flows, station_codes, toronto=C.TORONTO_CODE):
    """Add flow_class to a frame with home_code, work_code and workers.

    A Toronto home and a workplace with no GO or UP station is kept apart from the
    reverse flow, so the reverse total counts only places a GO train could reach.
    """
    out = flows.copy()
    home_t = out.home_code.eq(toronto)
    work_t = out.work_code.eq(toronto)
    same = out.home_code.eq(out.work_code)
    has_station = out.work_code.isin(set(station_codes))
    out["flow_class"] = np.select(
        [same, ~home_t & work_t, home_t & has_station, home_t, ~home_t & ~work_t],
        ["local", "inbound", "reverse", "toronto_out_no_station", "suburb_to_suburb"],
        default="suburb_to_suburb",
    )
    return out


def attach_work_code_2021(flows, subdivisions):
    """2021 work subdivisions are published as names. I match them to codes in the study area."""
    lookup = subdivisions.drop_duplicates("work_name").set_index("work_name").csd_code
    out = flows.copy()
    out["work_code"] = out.work_name.map(lookup)
    out.loc[out.work_name.eq(C.TORONTO_WORK_NAME), "work_code"] = C.TORONTO_CODE
    return out


def match_years(codes_2021, codes_2016):
    """Which 2021 destination codes have a 2016 counterpart. A missing code is listed, not filled."""
    have = set(codes_2016)
    return pd.DataFrame({"csd_code": list(codes_2021), "in_2016": [c in have for c in codes_2021]})


def _by_destination(classified, year):
    reverse = classified[classified.flow_class.eq("reverse")].groupby("work_code").workers.sum()
    inbound = classified[classified.flow_class.eq("inbound")].groupby("home_code").workers.sum()
    jobs = classified[classified.work_code.notna()].groupby("work_code").workers.sum()
    residents = classified.groupby("home_code").workers.sum()
    return pd.DataFrame(
        {
            f"reverse_{year}": reverse,
            f"inbound_{year}": inbound,
            f"jobs_{year}": jobs,
            f"resident_workers_{year}": residents,
        }
    )


def destinations(flows21, flows16, station_codes, subdivisions, pow21, pow16):
    """One row per destination subdivision with a GO or UP station."""
    c21 = classify(flows21, station_codes)
    c16 = classify(flows16, station_codes)
    d21 = _by_destination(c21, 2021)
    d16 = _by_destination(c16, 2016)
    codes = sorted(set(station_codes) - {C.TORONTO_CODE})
    names = subdivisions.drop_duplicates("csd_code").set_index("csd_code")
    out = pd.DataFrame({"csd_code": codes})
    out["csd_name"] = out.csd_code.map(names.csd_name)
    out["csd_type"] = out.csd_code.map(names.csd_type)
    out = out.merge(d21, left_on="csd_code", right_index=True, how="left")
    out = out.merge(d16, left_on="csd_code", right_index=True, how="left")
    out = out.merge(match_years(codes, c16.work_code.dropna().unique()), on="csd_code", how="left")
    for col in [c for c in out.columns if c.startswith(("reverse_", "inbound_", "jobs_", "resident_workers_"))]:
        out[col] = out[col].fillna(0)
    out["toronto_share_of_jobs_2021"] = np.where(out.jobs_2021 > 0, out.reverse_2021 / out.jobs_2021, np.nan)
    out["toronto_share_of_jobs_2016"] = np.where(out.jobs_2016 > 0, out.reverse_2016 / out.jobs_2016, np.nan)
    two_way = out.reverse_2021 + out.inbound_2021
    out["reverse_share_two_way_2021"] = np.where(two_way > 0, out.reverse_2021 / two_way, np.nan)
    out["reverse_change"] = out.reverse_2021 - out.reverse_2016
    out["reverse_change_pct"] = np.where(out.reverse_2016 > 0, out.reverse_change / out.reverse_2016, np.nan)
    out["inbound_change_pct"] = np.where(
        out.inbound_2016 > 0, (out.inbound_2021 - out.inbound_2016) / out.inbound_2016, np.nan
    )
    out = out.merge(_wfh(pow21, "2021"), on="csd_code", how="left").merge(_wfh(pow16, "2016"), on="csd_code", how="left")
    return out, c21, c16


def _wfh(pow_status, year):
    df = pow_status[["csd_code", "employed_total_pow", "worked_at_home"]].copy()
    df[f"wfh_share_{year}"] = df.worked_at_home / df.employed_total_pow
    return df[["csd_code", f"wfh_share_{year}"]]


def toronto_summary(c21, c16, pow21, pow16):
    """Totals on the Toronto side, for the context chapter."""
    rows = []
    for year, frame, pow_status in (("2016", c16, pow16), ("2021", c21, pow21)):
        home = frame[frame.home_code.eq(C.TORONTO_CODE)]
        t = pow_status[pow_status.csd_code.eq(C.TORONTO_CODE)].iloc[0]
        rows.append(
            {
                "year": int(year),
                "employed": float(t.employed_total_pow),
                "worked_at_home": float(t.worked_at_home),
                "wfh_share": float(t.worked_at_home / t.employed_total_pow),
                "usual_place_of_work": float(home.workers.sum()),
                "work_in_toronto": float(home[home.flow_class.eq("local")].workers.sum()),
                "reverse": float(home[home.flow_class.eq("reverse")].workers.sum()),
                "toronto_out_no_station": float(home[home.flow_class.eq("toronto_out_no_station")].workers.sum()),
                "inbound": float(frame[frame.flow_class.eq("inbound")].workers.sum()),
            }
        )
    return pd.DataFrame(rows)
