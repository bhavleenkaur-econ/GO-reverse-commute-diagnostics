-- Counter-peak timetable at each destination station, from the one-seat rides in reverse_pairs.
-- An arrival is one trip that reaches the destination after boarding at any Toronto station.
-- A return is one trip that leaves the destination and later stops at a Toronto station.
-- A gap counts in a band only when both ends of the gap fall inside the band.
WITH arrivals AS (
    SELECT dest_id, day_type, trip_id,
           min(alight_sec) AS arr_sec,
           min(ride_sec) AS ride_nearest_sec,
           min(CASE WHEN toronto_id = 'UN' THEN ride_sec END) AS ride_union_sec,
           bool_or(toronto_id = 'UN') AS via_union
    FROM reverse_pairs WHERE leg = 'out'
    GROUP BY ALL
),
returns AS (
    SELECT dest_id, day_type, trip_id, min(board_sec) AS dep_sec, min(ride_sec) AS ride_nearest_sec
    FROM reverse_pairs WHERE leg = 'back'
    GROUP BY ALL
),
arr_gaps AS (
    SELECT dest_id, arr_sec,
           lag(arr_sec) OVER (PARTITION BY dest_id ORDER BY arr_sec) AS prev_sec
    FROM arrivals WHERE day_type = 'weekday'
),
union_gaps AS (
    SELECT dest_id, arr_sec,
           lag(arr_sec) OVER (PARTITION BY dest_id ORDER BY arr_sec) AS prev_sec
    FROM arrivals WHERE day_type = 'weekday' AND via_union
),
ret_gaps AS (
    SELECT dest_id, dep_sec,
           lag(dep_sec) OVER (PARTITION BY dest_id ORDER BY dep_sec) AS prev_sec
    FROM returns WHERE day_type = 'weekday'
),
am AS (
    SELECT dest_id, median(arr_sec - prev_sec) / 60.0 AS am_arrival_headway_min,
           max(arr_sec - prev_sec) / 60.0 AS am_arrival_max_gap_min, count(*) AS am_gap_n
    FROM arr_gaps
    WHERE prev_sec IS NOT NULL AND arr_sec BETWEEN {am0} AND {am1} AND prev_sec BETWEEN {am0} AND {am1}
    GROUP BY dest_id
),
am_union AS (
    SELECT dest_id, median(arr_sec - prev_sec) / 60.0 AS am_union_headway_min, count(*) AS am_union_gap_n
    FROM union_gaps
    WHERE prev_sec IS NOT NULL AND arr_sec BETWEEN {am0} AND {am1} AND prev_sec BETWEEN {am0} AND {am1}
    GROUP BY dest_id
),
midday AS (
    SELECT dest_id, max(arr_sec - prev_sec) / 60.0 AS midday_max_gap_min, count(*) AS midday_gap_n
    FROM arr_gaps
    WHERE prev_sec IS NOT NULL AND arr_sec BETWEEN {md0} AND {md1} AND prev_sec BETWEEN {md0} AND {md1}
    GROUP BY dest_id
),
pm AS (
    SELECT dest_id, median(dep_sec - prev_sec) / 60.0 AS pm_return_headway_min, count(*) AS pm_gap_n
    FROM ret_gaps
    WHERE prev_sec IS NOT NULL AND dep_sec BETWEEN {pm0} AND {pm1} AND prev_sec BETWEEN {pm0} AND {pm1}
    GROUP BY dest_id
),
weekday_arr AS (
    SELECT dest_id,
           min(arr_sec) AS first_arrival_sec,
           count(*) FILTER (WHERE arr_sec BETWEEN {am0} AND {am1}) AS am_arrivals,
           count(*) AS weekday_arrivals,
           median(ride_nearest_sec) / 60.0 AS ride_nearest_min,
           median(ride_union_sec) / 60.0 AS ride_union_min
    FROM arrivals WHERE day_type = 'weekday'
    GROUP BY dest_id
),
weekday_ret AS (
    SELECT dest_id, max(dep_sec) AS last_return_sec,
           count(*) FILTER (WHERE dep_sec BETWEEN {pm0} AND {pm1}) AS pm_returns,
           count(*) AS weekday_returns
    FROM returns WHERE day_type = 'weekday'
    GROUP BY dest_id
),
weekend AS (
    SELECT a.dest_id, a.day_type, (r.last_sec - a.first_sec) / 3600.0 AS span_hours
    FROM (SELECT dest_id, day_type, min(arr_sec) AS first_sec FROM arrivals
          WHERE day_type IN ('saturday', 'sunday') GROUP BY ALL) a
    JOIN (SELECT dest_id, day_type, max(dep_sec) AS last_sec FROM returns
          WHERE day_type IN ('saturday', 'sunday') GROUP BY ALL) r USING (dest_id, day_type)
),
weekend_wide AS (
    SELECT dest_id,
           max(CASE WHEN day_type = 'saturday' THEN span_hours END) AS saturday_span_hours,
           max(CASE WHEN day_type = 'sunday' THEN span_hours END) AS sunday_span_hours
    FROM weekend GROUP BY dest_id
)
SELECT s.station_id AS dest_id,
       am.am_arrival_headway_min, am.am_arrival_max_gap_min, am.am_gap_n,
       am_union.am_union_headway_min, am_union.am_union_gap_n,
       midday.midday_max_gap_min, midday.midday_gap_n,
       pm.pm_return_headway_min, pm.pm_gap_n,
       weekday_arr.first_arrival_sec, weekday_arr.am_arrivals, weekday_arr.weekday_arrivals,
       weekday_arr.ride_nearest_min, weekday_arr.ride_union_min,
       weekday_ret.last_return_sec, weekday_ret.pm_returns, weekday_ret.weekday_returns,
       weekend_wide.saturday_span_hours, weekend_wide.sunday_span_hours
FROM destination_stations s
LEFT JOIN am ON am.dest_id = s.station_id
LEFT JOIN am_union ON am_union.dest_id = s.station_id
LEFT JOIN midday ON midday.dest_id = s.station_id
LEFT JOIN pm ON pm.dest_id = s.station_id
LEFT JOIN weekday_arr ON weekday_arr.dest_id = s.station_id
LEFT JOIN weekday_ret ON weekday_ret.dest_id = s.station_id
LEFT JOIN weekend_wide ON weekend_wide.dest_id = s.station_id;
