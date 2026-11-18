"""Load GTFS feeds into DuckDB, split stations into Toronto origins and destinations, and build rides.

The SQL lives in sql/. Python loads files, fills placeholders, and does the spatial joins.
"""

import duckdb
import geopandas as gpd
import pandas as pd

from . import config as C

TABLES = ["stops", "routes", "trips", "stop_times", "calendar", "calendar_dates"]
EMPTY_SCHEMAS = {
    "calendar": "service_id VARCHAR, monday VARCHAR, tuesday VARCHAR, wednesday VARCHAR, thursday VARCHAR, "
    "friday VARCHAR, saturday VARCHAR, sunday VARCHAR, start_date VARCHAR, end_date VARCHAR",
    "calendar_dates": "service_id VARCHAR, date VARCHAR, exception_type VARCHAR",
}
STOP_TIME_COLS = ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence", "pickup_type", "drop_off_type"]


def sql(name, **params):
    text = (C.SQL / f"{name}.sql").read_text()
    return text.format(**params) if params else text


def connect():
    return duckdb.connect()


def _iso(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def clock(sec):
    if sec is None or sec != sec:
        return None
    sec = int(sec)
    suffix = ""
    if sec >= 24 * 3600:
        sec -= 24 * 3600
        suffix = " next day"
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}{suffix}"


def load_feed(con, name):
    """Create schema <name> with one VARCHAR table per GTFS file."""
    folder = C.GTFS_DIR / name
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {name}")
    for table in TABLES:
        path = folder / f"{table}.txt"
        if path.exists() and path.stat().st_size > 0:
            src = f"read_csv('{path}', all_varchar=true, header=true, normalize_names=false)"
            if table == "stop_times":
                cols = con.execute(f"SELECT * FROM {src} LIMIT 0").description
                have = {c[0].strip().lstrip("\ufeff") for c in cols}
                select = ", ".join(f'"{c}"' if c in have else f"NULL::VARCHAR AS {c}" for c in STOP_TIME_COLS)
                con.execute(f"CREATE OR REPLACE TABLE {name}.{table} AS SELECT {select} FROM {src}")
            else:
                con.execute(f"CREATE OR REPLACE TABLE {name}.{table} AS SELECT * FROM {src}")
            _strip_bom(con, name, table)
        elif table in EMPTY_SCHEMAS:
            con.execute(f"CREATE OR REPLACE TABLE {name}.{table} ({EMPTY_SCHEMAS[table]})")
    con.execute(sql("active_service_dates", s=name))


def _strip_bom(con, schema, table):
    cols = con.execute(f"SELECT * FROM {schema}.{table} LIMIT 0").description
    for (col, *_rest) in cols:
        clean = col.replace("\ufeff", "").strip()
        if clean != col:
            con.execute(f'ALTER TABLE {schema}.{table} RENAME COLUMN "{col}" TO {clean}')


def build_rail_events(con):
    load_feed(con, "go")
    load_feed(con, "up")
    con.execute(sql("rail_events", weekday=_iso(C.GO_WEEKDAY), saturday=_iso(C.GO_SATURDAY), sunday=_iso(C.GO_SUNDAY)))


def rail_stations(con, subdivisions):
    """GO and UP rail stations with their line, coordinates, and census subdivision."""
    stations = con.execute(
        """
        WITH pts AS (
            SELECT DISTINCT e.station_id, s.stop_name, s.stop_lat::DOUBLE AS lat, s.stop_lon::DOUBLE AS lon
            FROM rail_events e JOIN go.stops s ON s.stop_id = e.station_id
            UNION ALL
            SELECT DISTINCT e.station_id, s.stop_name, s.stop_lat::DOUBLE, s.stop_lon::DOUBLE
            FROM rail_events e JOIN up.stops s ON s.stop_id = e.station_id
            WHERE e.station_id NOT IN (SELECT stop_id FROM go.stops)
        ),
        lines AS (
            SELECT station_id, string_agg(DISTINCT line, ',' ORDER BY line) AS lines
            FROM rail_events GROUP BY station_id
        )
        SELECT pts.*, lines.lines FROM pts JOIN lines USING (station_id)
        """
    ).fetchdf()
    stations["station_name"] = (
        stations.stop_name.str.replace(r"^UP Express ", "", regex=True)
        .str.replace(r" GO/UP$| GO Centre$| GO$", "", regex=True)
        .str.replace("Pearson Airport", "Pearson Airport (UP)")
    )
    stations["line"] = stations.lines.map(_primary_line)
    stations["line_name"] = stations.line.map(C.LINE_NAMES)
    pts = gpd.GeoDataFrame(
        stations.drop(columns="stop_name"), geometry=gpd.points_from_xy(stations.lon, stations.lat), crs=C.CRS_WGS84
    ).to_crs(C.CRS_METRIC)
    hit = gpd.sjoin(pts, subdivisions[["csd_code", "csd_name", "geometry"]], predicate="within", how="left")
    hit = hit.drop(columns="index_right").drop_duplicates("station_id")
    hit["in_toronto"] = hit.csd_code.eq(C.TORONTO_CODE)
    return hit


def _primary_line(lines):
    parts = [p for p in str(lines).split(",") if p and p != "UP"]
    return parts[0] if parts else "UP"


def register_station_sets(con, stations):
    toronto = stations.loc[stations.in_toronto, ["station_id"]]
    dest = stations.loc[~stations.in_toronto & stations.csd_code.notna(), ["station_id"]]
    con.register("toronto_df", toronto)
    con.register("dest_df", dest)
    con.execute("CREATE OR REPLACE TABLE toronto_stations AS SELECT * FROM toronto_df")
    con.execute("CREATE OR REPLACE TABLE destination_stations AS SELECT * FROM dest_df")


def build_pairs(con):
    con.execute(sql("reverse_pairs"))
    return con.execute("SELECT * FROM reverse_pairs").fetchdf()


def counter_peak(con):
    raw = con.execute(
        sql(
            "counter_peak",
            am0=C.AM_ARRIVE[0], am1=C.AM_ARRIVE[1], md0=C.MIDDAY[0], md1=C.MIDDAY[1],
            pm0=C.PM_RETURN[0], pm1=C.PM_RETURN[1],
        )
    ).fetchdf()
    return apply_fill(raw.rename(columns={"dest_id": "station_id"}))


def apply_fill(service):
    """Fill a headway or gap with the band length when the band has fewer than two trains.

    One train has no gap. Using the length of the band ranks a single train as infrequent
    rather than as a missing value. A station with no train in a band gets the same value.
    """
    out = service.copy()
    am = (C.AM_ARRIVE[1] - C.AM_ARRIVE[0]) / 60
    md = (C.MIDDAY[1] - C.MIDDAY[0]) / 60
    pm = (C.PM_RETURN[1] - C.PM_RETURN[0]) / 60
    for value, count, window in (
        ("am_arrival_headway_min", "am_gap_n", am),
        ("am_arrival_max_gap_min", "am_gap_n", am),
        ("am_union_headway_min", "am_union_gap_n", am),
        ("midday_max_gap_min", "midday_gap_n", md),
        ("pm_return_headway_min", "pm_gap_n", pm),
    ):
        if value not in out.columns:
            out[value] = pd.NA
        if count not in out.columns:
            out[count] = 0
        thin = out[count].fillna(0).lt(1) | out[value].isna()
        out[value] = out[value].astype("float64")
        out.loc[thin, value] = window
    span = (out.last_return_sec - out.first_arrival_sec) / 3600
    out["weekday_span_hours"] = span.where(span > 0, 0).fillna(0)
    for col in ("saturday_span_hours", "sunday_span_hours"):
        if col not in out.columns:
            out[col] = 0
        out[col] = out[col].astype("float64").fillna(0).clip(lower=0)
    out["weekend_span_hours"] = (out.saturday_span_hours + out.sunday_span_hours) / 2
    out["first_arrival_clock"] = out.first_arrival_sec.map(clock)
    out["last_return_clock"] = out.last_return_sec.map(clock)
    for col in ("am_arrivals", "weekday_arrivals", "pm_returns", "weekday_returns"):
        if col in out.columns:
            out[col] = out[col].fillna(0)
    return out


def build_feeders(con, stations):
    """Load each local feed, link stops within the feeder radius of a destination station, build local_events."""
    con.execute(
        """CREATE OR REPLACE TABLE local_events (agency VARCHAR, station_id VARCHAR, stop_id VARCHAR,
           route_id VARCHAR, trip_id VARCHAR, arr_sec INT, dep_sec INT, can_alight BOOLEAN, can_board BOOLEAN)"""
    )
    dest = stations[~stations.in_toronto & stations.csd_code.notna()]
    feed_dates, links = [], []
    for agency in C.LOCAL_AGENCIES:
        load_feed(con, agency)
        row = con.execute(sql("representative_weekday", s=agency, target=_iso(C.GO_WEEKDAY))).fetchone()
        date, trips = (row[0], row[1]) if row else (None, 0)
        feed_dates.append({"agency": agency, "representative_weekday": date, "trips_that_day": trips})
        cols = {c[0] for c in con.execute(f"SELECT * FROM {agency}.stops LIMIT 0").description}
        stop_filter = "AND coalesce(location_type, '0') IN ('0', '')" if "location_type" in cols else ""
        stops = con.execute(
            f"""SELECT stop_id, stop_lat::DOUBLE AS lat, stop_lon::DOUBLE AS lon FROM {agency}.stops
                WHERE stop_lat IS NOT NULL AND stop_lat <> '' {stop_filter}"""
        ).fetchdf()
        g = gpd.GeoDataFrame(stops, geometry=gpd.points_from_xy(stops.lon, stops.lat), crs=C.CRS_WGS84).to_crs(C.CRS_METRIC)
        near = gpd.sjoin_nearest(
            g, dest[["station_id", "geometry"]], how="inner", max_distance=C.FEEDER_RADIUS_M, distance_col="dist_m"
        )
        near["agency"] = agency
        links.append(near[["agency", "stop_id", "station_id", "dist_m"]])
    feeder_stops = pd.concat(links, ignore_index=True)
    con.register("feeder_stops_df", feeder_stops)
    con.execute("CREATE OR REPLACE TABLE feeder_stops AS SELECT * FROM feeder_stops_df")
    for row in feed_dates:
        if row["representative_weekday"] is None:
            continue
        con.execute(sql("local_events", agency=row["agency"], s=row["agency"], date=row["representative_weekday"]))
    return pd.DataFrame(feed_dates), feeder_stops


def train_to_bus(con):
    con.execute(
        sql("train_to_bus", am0=C.AM_ARRIVE[0], am1=C.AM_ARRIVE[1], min_transfer=C.MIN_TRANSFER_S, cap=C.WAIT_CAP_MIN * 60)
    )
    return con.execute("SELECT * FROM train_to_bus").fetchdf()


def am_bus_departures(con):
    """Local departures within the feeder radius in the AM arrival band, and how many routes they use."""
    return con.execute(
        f"""SELECT station_id, count(*) AS am_bus_departures, count(DISTINCT agency || ':' || route_id) AS am_bus_routes,
                   mode(agency) AS main_agency
            FROM local_events WHERE can_board AND dep_sec BETWEEN {C.AM_ARRIVE[0]} AND {C.AM_ARRIVE[1]}
            GROUP BY station_id"""
    ).fetchdf()
