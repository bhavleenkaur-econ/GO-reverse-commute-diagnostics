"""Fetch or copy every raw input. Files that already exist are skipped, so the script is safe to rerun.

`seed()` copies files from another folder, such as the GO station scorecard's data/raw, so the
292 MB flow table and the GTFS feeds are not downloaded twice.
"""

import shutil
import zipfile

import duckdb
import requests

from . import config as C

GO_GTFS = "https://assets.metrolinx.com/raw/upload/Documents/Metrolinx/Open%20Data/GO-GTFS.zip"
UP_GTFS = "https://assets.metrolinx.com/raw/upload/Documents/Metrolinx/Open%20Data/UP-GTFS.zip"

LOCAL_FEEDS = {
    "barrie": "mdb-3",
    "brampton": "mdb-1994",
    "burlington": "mdb-724",
    "durham": "mdb-726",
    "grt_bus": "mdb-3150",
    "grt_ion": "mdb-3151",
    "guelph": "mdb-3140",
    "hsr": "mdb-2618",
    "milton": "mdb-759",
    "miway": "mdb-730",
    "niagara": "tld-859",
    "oakville": "mdb-725",
    "ttc": "mdb-732",
    "yrt": "mdb-728",
}

STATCAN_2021 = {
    "t98100498.zip": "https://www150.statcan.gc.ca/n1/tbl/csv/98100498-eng.zip",
    "t98100459.zip": "https://www150.statcan.gc.ca/n1/tbl/csv/98100459-eng.zip",
}

# The 2016 tables are served from www12.statcan.gc.ca, which answers scripted requests with a
# browser security check. If the request is blocked, open the URL in a browser and save the zip
# under data/raw/census with the file name on the left.
STATCAN_2016 = {
    "98-400-X2016325_ENG_CSV.zip": (
        "https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/dt-td/"
        "CompDataDownload.cfm?LANG=E&PID=111332&OFT=CSV"
    ),
    "98-401-X2016055_eng_CSV.zip": (
        "https://www12.statcan.gc.ca/census-recensement/2016/dp-pd/prof/details/download-telecharger/"
        "comp/GetFile.cfm?Lang=E&FILETYPE=CSV&GEONO=055"
    ),
}

D4C = (
    "https://data.source.coop/dataforcanada/d4c-datapkg-statistical/processed/"
    "ca_statcan_2021A000011124_d4c-datapkg-statistical_{name}_2021_v0.1.0-beta.parquet"
)

# 2021 Census Profile characteristic IDs, from the official 98-401-X2021 numbering.
DA_CHARACTERISTICS = {
    1: "pop_2021",
    2593: "employed_total_pow",
    2594: "worked_at_home",
    2597: "usual_place_of_work",
}

SEED_FILES = [
    "GO-GTFS.zip",
    "UP-GTFS.zip",
    "census/t98100459.zip",
    "census/t98100498.zip",
    "census/csd_boundaries.parquet",
    "census/ct_boundaries.parquet",
    "census/da_boundaries.parquet",
    "census/da_profile.parquet",
]


def _get(url, dest, timeout=600):
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip   {dest.name}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": "reverse-commute"}) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.rename(dest)
    print(f"fetch  {dest.name}  {dest.stat().st_size / 1e6:.1f} MB")
    return dest


def seed(source):
    """Copy inputs from a folder laid out like data/raw, for example the scorecard's."""
    for rel in SEED_FILES:
        src, dest = source / rel, C.RAW / rel
        if dest.exists() or not src.exists():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        print(f"copy   {rel}")
    local = source / "local_gtfs"
    if local.exists():
        for src in local.glob("*.zip"):
            dest = C.RAW / "local_gtfs" / src.name
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                print(f"copy   local_gtfs/{src.name}")


def download_transit():
    _get(GO_GTFS, C.RAW / "GO-GTFS.zip")
    _get(UP_GTFS, C.RAW / "UP-GTFS.zip")
    for name, feed_id in LOCAL_FEEDS.items():
        _get(f"https://files.mobilitydatabase.org/{feed_id}/latest.zip", C.RAW / "local_gtfs" / f"{name}.zip")


def download_census():
    for fname, url in STATCAN_2021.items():
        _get(url, C.CENSUS_DIR / fname, timeout=1800)
    for fname, url in STATCAN_2016.items():
        dest = C.CENSUS_DIR / fname
        if dest.exists():
            print(f"skip   {fname}")
            continue
        try:
            _get(url, dest, timeout=1800)
            if not zipfile.is_zipfile(dest):
                dest.unlink()
                raise ValueError("not a zip")
        except (requests.HTTPError, ValueError):
            print(f"manual {fname}: open {url} in a browser and save the file to {dest}")


def _bbox_filter():
    b = C.STUDY_BBOX
    return (
        f"geom_bbox.xmax >= {b['xmin']} AND geom_bbox.xmin <= {b['xmax']} "
        f"AND geom_bbox.ymax >= {b['ymin']} AND geom_bbox.ymin <= {b['ymax']}"
    )


def download_geography():
    """Study-area rows of the 2021 boundary files and the dissemination-area profile values."""
    out = C.CENSUS_DIR
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    targets = {
        "da_boundaries.parquet": ("dissemination_areas_cartographic", "da_dguid, ct_dguid, csd_dguid, csd_name, cma_name"),
        "ct_boundaries.parquet": ("census_tracts_cartographic", "ct_dguid, cma_name"),
        "csd_boundaries.parquet": ("census_subdivisions_cartographic", "csd_dguid, csd_name, csd_type, cd_name"),
    }
    for fname, (name, cols) in targets.items():
        dest = out / fname
        if dest.exists():
            print(f"skip   {fname}")
            continue
        con.execute(
            f"""COPY (SELECT {cols}, ST_AsWKB(geom) AS geometry FROM read_parquet('{D4C.format(name=name)}')
                WHERE pr_dguid = '2021A000235' AND {_bbox_filter()})
                TO '{dest}' (FORMAT PARQUET)"""
        )
        print(f"fetch  {fname}")
    dest = out / "da_profile.parquet"
    if dest.exists():
        print("skip   da_profile.parquet")
        return
    select = ", ".join(f"count_total_{k} AS {v}" for k, v in DA_CHARACTERISTICS.items())
    con.execute(
        f"""COPY (SELECT da_dguid, {select} FROM read_parquet('{D4C.format(name="census_pop_dissemination_areas")}')
            WHERE da_dguid LIKE '2021S051235%') TO '{dest}' (FORMAT PARQUET)"""
    )
    print("fetch  da_profile.parquet")


def extract_gtfs():
    feeds = {"go": C.RAW / "GO-GTFS.zip", "up": C.RAW / "UP-GTFS.zip"}
    feeds.update({p.stem: p for p in sorted((C.RAW / "local_gtfs").glob("*.zip"))})
    for name, path in feeds.items():
        target = C.GTFS_DIR / name
        if (target / "stop_times.txt").exists():
            continue
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path) as z:
            z.extractall(target)
        print(f"unzip  {name}")


def download_all(seed_from=None):
    if seed_from is not None:
        seed(seed_from)
    download_transit()
    download_census()
    download_geography()
    extract_gtfs()
