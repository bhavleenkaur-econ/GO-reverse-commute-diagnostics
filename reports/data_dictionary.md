# Data dictionary

Times are in minutes unless the name ends in `_sec` (seconds after midnight) or `_hours`. Scores run from 0 to 100, and higher is better.

## data/processed/destinations.csv

One row per destination census subdivision with a GO or UP station outside Toronto.

| Column | Meaning |
| --- | --- |
| csd_code, csd_name, csd_type | 2021 census subdivision |
| reverse_2021, reverse_2016 | Toronto residents with a usual workplace in the subdivision |
| inbound_2021, inbound_2016 | Subdivision residents with a usual workplace in Toronto |
| jobs_2021, jobs_2016 | Workers with a usual workplace in the subdivision, from any home |
| resident_workers_2021, resident_workers_2016 | Subdivision residents with a usual place of work anywhere |
| in_2016 | The 2021 code has a 2016 match |
| toronto_share_of_jobs_2021, toronto_share_of_jobs_2016 | reverse divided by jobs |
| reverse_share_two_way_2021 | reverse divided by reverse plus inbound |
| reverse_change, reverse_change_pct, inbound_change_pct | 2016 to 2021 change |
| wfh_share_2021, wfh_share_2016 | Share of employed subdivision residents who worked at home |
| station_id, station_name, line_name | Best station in the subdivision |
| other_stations | The other stations in the subdivision |
| station_supply_score | Best station's supply score, ranked among all destination stations |
| am_arrivals | Trains from Toronto arriving 06:30 to 09:30 |
| am_arrival_headway_min, am_union_headway_min | Median arrival gap in the AM band, from any Toronto station and from Union only |
| midday_max_gap_min | Longest gap between arrivals, 09:30 to 15:00 |
| pm_return_headway_min, pm_returns | Median gap and count of departures toward Toronto, 15:30 to 18:30 |
| first_arrival_sec, first_arrival_clock | First weekday arrival from Toronto |
| last_return_clock | Last weekday departure back to Toronto |
| weekday_span_hours, weekend_span_hours | First arrival to last return, zero when the last return comes first |
| ride_nearest_min, ride_union_min | Shortest scheduled ride from any Toronto station, and from Union |
| train_to_bus_wait_min | Median scheduled wait from an AM train to the next local bus |
| am_bus_routes_best | Most local routes leaving in the AM band at any station in the subdivision |
| jobs_800m, jobs_2km | Jobs in straight-line rings around the best station |
| csd_tract_jobs, csd_jobs_2km, jobs_2km_share | Subdivision jobs, jobs within 2 km of any of its stations, and the share |
| market_score, rail_score, last_mile_score | Percentile scores |
| no_am_arrival | The best station gets no train from Toronto in the AM band |
| quadrant | mismatch, market and service, service ahead of market, or market and service both thin |
| rail_gap | Rail median minus rail score |
| near_cut | Within 5 points of the market or rail median |
| threshold_class | no AM arrival, clear, threshold-sensitive, looser cut only, or not a mismatch |
| deficit_rail, deficit_last_mile | Reference median minus the score |
| primary_gap, primary_deficit, is_tie, confidence | Gap I would act on, for mismatches only |
| supporting_evidence, contradictory_evidence | Generated text from the row |

## data/processed/destination_stations.csv

One row per destination station. It has the same service and last-mile columns as above, plus `am_arrival_max_gap_min`, the gap counts `am_gap_n`, `midday_gap_n`, and `pm_gap_n`, `weekday_arrivals`, `weekday_returns`, `last_return_sec`, the Saturday and Sunday spans, `train_to_bus_p90_min`, `train_to_bus_n`, `am_bus_departures`, `am_bus_routes`, and `main_agency`.

## data/processed/reverse_pairs.parquet

One row per one-seat ride between a Toronto station and a destination station: `leg` (out or back), `operator`, `line`, `trip_id`, `day_type`, `toronto_id`, `dest_id`, `board_sec`, `alight_sec`, `ride_sec`.

## data/processed/toronto_summary.csv

One row per Census year for Toronto residents: `employed`, `worked_at_home`, `wfh_share`, `usual_place_of_work`, `work_in_toronto`, `reverse`, and `toronto_out_no_station`. `inbound` counts Ontario residents of every other subdivision with a usual workplace in Toronto. Both flow files cover Ontario homes only.

## Other outputs

- `flow_change.csv`: the 2016 and 2021 columns from destinations.csv, sorted by reverse_2021.
- `feeder_service_dates.csv`: the representative weekday and trip count for each local feed.
- `recommendations.csv`: one row per mismatch with the action, owner, and KPI.
- `run_meta.json`: medians, percentile cuts, threshold lists, dates, and counts.
- `reports/evidence.csv`: the competing-explanations table.
