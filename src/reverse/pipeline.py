"""Run the reverse commute analysis from the raw files and write every table the notebook and brief use."""

import json

import pandas as pd

from . import census, config as C, flows, gtfs, lastmile, mismatch


def run(save=True, outputs=True):
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    C.REPORTS.mkdir(parents=True, exist_ok=True)
    subdivisions = census.subdivisions()

    con = gtfs.connect()
    gtfs.build_rail_events(con)
    stations = gtfs.rail_stations(con, subdivisions)
    gtfs.register_station_sets(con, stations)
    pairs = gtfs.build_pairs(con)
    supply = gtfs.counter_peak(con)
    feed_dates, _links = gtfs.build_feeders(con, stations)
    waits = gtfs.train_to_bus(con)
    buses = gtfs.am_bus_departures(con)

    jobs_ct = lastmile.jobs_tracts(census.tracts(), census.jobs_by_ct())
    rings = lastmile.station_rings(stations, jobs_ct)
    coverage = lastmile.subdivision_coverage(stations, subdivisions, jobs_ct)

    dest_stations = stations[~stations.in_toronto & stations.csd_code.notna()].drop(columns="geometry")
    dest_stations = (
        dest_stations.merge(supply, on="station_id", how="left")
        .merge(rings, on="station_id", how="left")
        .merge(lastmile.wait_summary(waits), on="station_id", how="left")
        .merge(buses, on="station_id", how="left")
    )
    dest_stations["am_bus_departures"] = dest_stations.am_bus_departures.fillna(0)
    dest_stations["am_bus_routes"] = dest_stations.am_bus_routes.fillna(0)
    dest_stations = mismatch.station_supply(dest_stations)

    f21 = flows.attach_work_code_2021(census.flows_2021(), subdivisions)
    f16 = census.flows_2016()
    pow21, pow16 = census.place_of_work_2021(), census.place_of_work_2016()
    codes = set(stations.csd_code.dropna())
    dest, c21, c16 = flows.destinations(f21, f16, codes, subdivisions, pow21, pow16)
    toronto = flows.toronto_summary(c21, c16, pow21, pow16)

    best = mismatch.best_station(dest_stations)
    keep = [
        "csd_code", "station_id", "station_name", "line_name", "other_stations", "station_supply_score",
        "am_arrivals", "am_arrival_headway_min", "am_union_headway_min", "midday_max_gap_min",
        "pm_return_headway_min", "pm_returns", "first_arrival_sec", "first_arrival_clock", "last_return_clock", "weekday_span_hours",
        "weekend_span_hours", "ride_nearest_min", "ride_union_min", "train_to_bus_wait_min",
        "am_bus_routes_best", "jobs_800m", "jobs_2km",
    ]
    table = dest.merge(best[keep], on="csd_code", how="inner").merge(
        coverage[["csd_code", "csd_tract_jobs", "csd_jobs_2km", "jobs_2km_share"]], on="csd_code", how="left"
    )
    table = mismatch.diagnose(mismatch.score(table))
    recs = mismatch.recommendations(table)
    evidence = mismatch.evidence_frame(table)

    meta = dict(table.attrs)
    meta.update(
        {
            "weekday": C.GO_WEEKDAY,
            "saturday": C.GO_SATURDAY,
            "sunday": C.GO_SUNDAY,
            "n_destinations": int(len(table)),
            "n_destination_stations": int(len(dest_stations)),
            "n_toronto_stations": int(stations.in_toronto.sum()),
            "unmatched_2016": sorted(table.loc[~table.in_2016.fillna(False), "csd_name"]),
            "stations_outside_study_area": sorted(stations.loc[stations.csd_code.isna(), "station_name"]),
            "reverse_total_2021": float(toronto.loc[toronto.year.eq(2021), "reverse"].iloc[0]),
        }
    )
    if save:
        table.to_csv(C.PROCESSED / "destinations.csv", index=False)
        dest_stations.to_csv(C.PROCESSED / "destination_stations.csv", index=False)
        pairs.to_parquet(C.PROCESSED / "reverse_pairs.parquet", index=False)
        toronto.to_csv(C.PROCESSED / "toronto_summary.csv", index=False)
        flow_change = table[
            ["csd_name", "reverse_2016", "reverse_2021", "reverse_change", "reverse_change_pct",
             "inbound_2016", "inbound_2021", "inbound_change_pct", "jobs_2016", "jobs_2021",
             "wfh_share_2016", "wfh_share_2021", "in_2016"]
        ].sort_values("reverse_2021", ascending=False)
        flow_change.to_csv(C.PROCESSED / "flow_change.csv", index=False)
        feed_dates.to_csv(C.PROCESSED / "feeder_service_dates.csv", index=False)
        recs.to_csv(C.PROCESSED / "recommendations.csv", index=False)
        evidence.to_csv(C.REPORTS / "evidence.csv", index=False)
        (C.PROCESSED / "run_meta.json").write_text(json.dumps(meta, indent=2, default=float))
        if outputs:
            from . import brief, viz

            viz.all_figures(table, pairs, subdivisions, stations)
            brief.write(table, recs, toronto, meta)
    return table, dest_stations, toronto, recs, meta


def load():
    table = pd.read_csv(C.PROCESSED / "destinations.csv", dtype={"csd_code": str})
    stations = pd.read_csv(C.PROCESSED / "destination_stations.csv", dtype={"csd_code": str})
    toronto = pd.read_csv(C.PROCESSED / "toronto_summary.csv")
    recs = pd.read_csv(C.PROCESSED / "recommendations.csv")
    meta = json.loads((C.PROCESSED / "run_meta.json").read_text())
    return table, stations, toronto, recs, meta
