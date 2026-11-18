"""Last mile at the destination: jobs near the station, local buses at the station, and the wait for them.

I use straight-line rings, 800 m and 2 km, not a walking network. The 2 km ring stands in for a
short bus link to an employment area. Jobs are 2021 usual-place-of-work counts by census tract,
area-weighted into each ring.
"""

import geopandas as gpd
import pandas as pd

from . import census, config as C


def station_rings(stations, jobs_ct):
    dest = stations[~stations.in_toronto & stations.csd_code.notna()]
    out = dest[["station_id"]].copy()
    for radius, name in ((C.RING_NEAR_M, "jobs_800m"), (C.RING_FAR_M, "jobs_2km")):
        ring = gpd.GeoDataFrame(dest[["station_id"]], geometry=dest.geometry.buffer(radius), crs=C.CRS_METRIC)
        w = census.area_weight(ring, jobs_ct, ["jobs"], "station_id").rename(columns={"jobs": name})
        out = out.merge(w, on="station_id", how="left")
    return out.fillna({"jobs_800m": 0, "jobs_2km": 0})


def subdivision_coverage(stations, subdivisions, jobs_ct):
    """Share of a subdivision's tract jobs that sit within 2 km of any of its stations, inside the subdivision."""
    dest = stations[~stations.in_toronto & stations.csd_code.notna()]
    csd = subdivisions[subdivisions.csd_code.isin(dest.csd_code)][["csd_code", "geometry"]]
    total = census.area_weight(csd, jobs_ct, ["jobs"], "csd_code").rename(columns={"jobs": "csd_tract_jobs"})
    rings = (
        gpd.GeoDataFrame(dest[["csd_code"]], geometry=dest.geometry.buffer(C.RING_FAR_M), crs=C.CRS_METRIC)
        .dissolve(by="csd_code")
        .reset_index()
    )
    clipped = gpd.overlay(rings, csd, how="intersection", keep_geom_type=True)
    clipped = clipped.rename(columns={"csd_code_1": "csd_code"})[["csd_code", "geometry"]]
    near = census.area_weight(clipped, jobs_ct, ["jobs"], "csd_code").rename(columns={"jobs": "csd_jobs_2km"})
    out = total.merge(near, on="csd_code", how="left").fillna({"csd_jobs_2km": 0})
    out["jobs_2km_share"] = out.csd_jobs_2km / out.csd_tract_jobs
    return out


def wait_summary(waits):
    """Median and 90th percentile scheduled wait from an AM train arrival to the next local bus."""
    if waits.empty:
        return pd.DataFrame(columns=["station_id", "train_to_bus_wait_min", "train_to_bus_p90_min", "train_to_bus_n"])
    g = waits.groupby("station_id").wait_sec
    return pd.DataFrame(
        {
            "train_to_bus_wait_min": g.median() / 60,
            "train_to_bus_p90_min": g.quantile(0.9) / 60,
            "train_to_bus_n": g.size(),
        }
    ).reset_index()


def jobs_tracts(tracts, jobs):
    out = tracts.merge(jobs, on="ct_dguid", how="left")
    out["jobs"] = out["jobs"].fillna(0)
    return out
