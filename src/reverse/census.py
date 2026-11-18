"""Census inputs: commuting flows for 2016 and 2021, place-of-work status, jobs by tract, and boundaries.

Large source files are streamed and the Ontario rows are cached as Parquet in data/interim.
"""

import zipfile

import geopandas as gpd
import pandas as pd

from . import config as C


def _read_geo(name):
    df = pd.read_parquet(C.CENSUS_DIR / f"{name}.parquet")
    return gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkb(df.geometry), crs=C.CRS_WGS84).to_crs(C.CRS_METRIC)


def subdivisions():
    """2021 census subdivisions in the study area, with the seven-digit code and the flow-table name."""
    csd = _read_geo("csd_boundaries")
    csd["csd_code"] = csd.csd_dguid.str[-7:]
    csd["work_name"] = csd.csd_name + " (" + csd.csd_type + "), Ont."
    return csd


def tracts():
    return _read_geo("ct_boundaries")


def flows_2021():
    """Workers by census subdivision of residence and of work, Ontario homes only (table 98-10-0459).

    The source CSV is 2.2 GB, so I stream it and keep Ontario homes. The work subdivision
    is published only as a name, such as "Mississauga (CY), Ont.".
    """
    cache = C.INTERIM / "flows_2021.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    z = zipfile.ZipFile(C.CENSUS_DIR / "t98100459.zip")
    total = "Gender (3):Total - Gender[1]"
    parts = []
    reader = pd.read_csv(
        z.open("98100459.csv"), usecols=["GEO", "DGUID", "Place of work", total], dtype=str, chunksize=500_000
    )
    for chunk in reader:
        chunk = chunk[chunk.DGUID.str.startswith("2021A000535")]
        chunk = chunk.assign(workers=pd.to_numeric(chunk[total], errors="coerce").fillna(0))
        parts.append(chunk[chunk.workers > 0][["GEO", "DGUID", "Place of work", "workers"]])
    out = pd.concat(parts, ignore_index=True).rename(
        columns={"GEO": "home_name", "DGUID": "home_dguid", "Place of work": "work_name"}
    )
    out["home_code"] = out.home_dguid.str[-7:]
    C.INTERIM.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache)
    return out


def flows_2016():
    """2016 flows between census subdivisions, Ontario homes only (98-400-X2016325)."""
    cache = C.INTERIM / "flows_2016.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    z = zipfile.ZipFile(C.CENSUS_DIR / "98-400-X2016325_ENG_CSV.zip")
    names = [
        "year", "home_code", "home_level", "home_name", "home_gnr", "home_flag", "home_type", "home_alt",
        "work_code", "work_level", "work_name", "work_gnr", "work_flag", "work_type", "work_alt",
        "workers", "men", "women",
    ]
    df = pd.read_csv(
        z.open("98-400-X2016325_English_CSV_data.csv"), header=0, names=names, dtype=str, encoding="latin-1"
    )
    df = df[df.home_code.str.startswith("35")].copy()
    df["workers"] = pd.to_numeric(df.workers, errors="coerce").fillna(0)
    out = df[df.workers > 0][["home_code", "home_name", "work_code", "work_name", "work_type", "workers"]]
    C.INTERIM.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache)
    return out


POW_STATUS_2016 = {
    1920: "employed_total_pow",
    1921: "worked_at_home",
    1922: "worked_outside_canada",
    1923: "no_fixed_workplace",
    1924: "usual_place_of_work",
}


def place_of_work_2016():
    """Place-of-work status by Ontario census subdivision, 2016 Census Profile (98-401-X2016055).

    The profile CSV is 1.3 GB, so I stream it and keep five rows for each Ontario subdivision.
    """
    cache = C.INTERIM / "place_of_work_2016.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    z = zipfile.ZipFile(C.CENSUS_DIR / "98-401-X2016055_eng_CSV.zip")
    member = "Member ID: Profile of Census Divisions/Census Subdivisions (2247)"
    total = "Dim: Sex (3): Member ID: [1]: Total - Sex"
    parts = []
    reader = pd.read_csv(
        z.open("98-401-X2016055_English_CSV_data.csv"),
        usecols=["GEO_CODE (POR)", "GEO_LEVEL", member, total],
        dtype=str,
        encoding="latin-1",
        chunksize=1_000_000,
    )
    keep = {str(k) for k in POW_STATUS_2016}
    for chunk in reader:
        chunk = chunk[(chunk.GEO_LEVEL == "3") & chunk["GEO_CODE (POR)"].str.startswith("35") & chunk[member].isin(keep)]
        parts.append(chunk)
    df = pd.concat(parts, ignore_index=True)
    df["value"] = pd.to_numeric(df[total], errors="coerce")
    df["field"] = df[member].astype(int).map(POW_STATUS_2016)
    out = df.pivot_table(index="GEO_CODE (POR)", columns="field", values="value", aggfunc="first").reset_index()
    out = out.rename(columns={"GEO_CODE (POR)": "csd_code"})
    out.columns.name = None
    C.INTERIM.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache)
    return out


def place_of_work_2021():
    """Place-of-work status by census subdivision, summed from 2021 dissemination-area profile values."""
    profile = pd.read_parquet(C.CENSUS_DIR / "da_profile.parquet")
    da = pd.read_parquet(C.CENSUS_DIR / "da_boundaries.parquet", columns=["da_dguid", "csd_dguid"])
    cols = ["employed_total_pow", "worked_at_home", "usual_place_of_work"]
    joined = da.merge(profile[["da_dguid", *cols]], on="da_dguid", how="left")
    out = joined.groupby("csd_dguid", as_index=False)[cols].sum(min_count=1)
    out["csd_code"] = out.csd_dguid.str[-7:]
    return out.drop(columns="csd_dguid")


def jobs_by_ct():
    """Employed labour force with a usual place of work, by census tract of work (table 98-10-0498)."""
    z = zipfile.ZipFile(C.CENSUS_DIR / "t98100498.zip")
    df = pd.read_csv(z.open("98100498.csv"), dtype=str)
    total_col = next(c for c in df.columns if c.startswith("Employment income groups (18):Total"))
    df = df[df["Place of work status (3)"] == "Usual place of work"]
    out = df[["DGUID", total_col]].rename(columns={"DGUID": "ct_dguid", total_col: "jobs"})
    out["jobs"] = pd.to_numeric(out.jobs, errors="coerce").fillna(0)
    return out[out.ct_dguid.str.startswith("2021S0507")]


def area_weight(zones, units, value_cols, zone_id):
    """Apportion unit totals to zones by the share of each unit's area that falls inside the zone."""
    units = units.copy()
    units["unit_area"] = units.geometry.area
    pieces = gpd.overlay(zones[[zone_id, "geometry"]], units, how="intersection", keep_geom_type=True)
    w = pieces.geometry.area / pieces.unit_area
    out = pieces[[zone_id]].copy()
    for c in value_cols:
        out[c] = pieces[c].fillna(0) * w
    return out.groupby(zone_id, as_index=False).sum()
