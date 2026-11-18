-- Scheduled wait from each weekday AM train arrival from Toronto to the next local bus departure
-- within the feeder radius of the station, at least {min_transfer} seconds later.
-- Waits are capped at {cap} seconds, so a station with no bus does not produce an unbounded number.
CREATE OR REPLACE TABLE train_to_bus AS
WITH train_arr AS (
    SELECT dest_id AS station_id, trip_id, min(alight_sec) AS arr_sec
    FROM reverse_pairs
    WHERE leg = 'out' AND day_type = 'weekday'
    GROUP BY ALL
    HAVING min(alight_sec) BETWEEN {am0} AND {am1}
),
ready AS (
    SELECT station_id, trip_id, arr_sec, arr_sec + {min_transfer} AS ready_sec FROM train_arr
),
bus_dep AS (
    SELECT station_id, agency, route_id, dep_sec FROM local_events WHERE can_board
)
SELECT t.station_id, t.trip_id, t.arr_sec, b.agency, b.route_id,
       least(coalesce(b.dep_sec - t.arr_sec, {cap}), {cap}) AS wait_sec
FROM ready t
ASOF LEFT JOIN bus_dep b ON t.station_id = b.station_id AND b.dep_sec >= t.ready_sec;
