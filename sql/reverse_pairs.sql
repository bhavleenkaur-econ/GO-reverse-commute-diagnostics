-- One-seat rides between a Toronto station and a destination station outside Toronto.
-- Out: board at a Toronto station, alight later on the same trip at a destination station.
-- Back: board at the destination station, alight later on the same trip at a Toronto station.
-- toronto_stations and destination_stations are registered from Python.
CREATE OR REPLACE TABLE reverse_pairs AS
SELECT 'out' AS leg, o.operator, o.line, o.trip_id, o.day_type,
       o.station_id AS toronto_id, d.station_id AS dest_id,
       o.dep_sec AS board_sec, d.arr_sec AS alight_sec, d.arr_sec - o.dep_sec AS ride_sec
FROM rail_events o
JOIN rail_events d
  ON d.operator = o.operator AND d.trip_id = o.trip_id AND d.service_date = o.service_date AND d.seq > o.seq
WHERE o.can_board AND d.can_alight
  AND o.station_id IN (SELECT station_id FROM toronto_stations)
  AND d.station_id IN (SELECT station_id FROM destination_stations)
UNION ALL
SELECT 'back', o.operator, o.line, o.trip_id, o.day_type,
       d.station_id, o.station_id,
       o.dep_sec, d.arr_sec, d.arr_sec - o.dep_sec
FROM rail_events o
JOIN rail_events d
  ON d.operator = o.operator AND d.trip_id = o.trip_id AND d.service_date = o.service_date AND d.seq > o.seq
WHERE o.can_board AND d.can_alight
  AND o.station_id IN (SELECT station_id FROM destination_stations)
  AND d.station_id IN (SELECT station_id FROM toronto_stations);
