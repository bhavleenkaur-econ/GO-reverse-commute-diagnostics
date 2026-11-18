-- Every scheduled GO and UP Express rail stop event on the chosen weekday, Saturday and Sunday.
-- seq is the stop sequence on the trip, so a later stop on the same trip has a larger seq.
-- toward_union and from_union mark stops before and after Union on the same trip.
CREATE OR REPLACE TABLE rail_events AS
WITH rail_trips AS (
    SELECT 'GO' AS operator, t.trip_id, t.service_id, r.route_short_name AS line
    FROM go.trips t JOIN go.routes r USING (route_id)
    WHERE r.route_type = '2'
    UNION ALL
    SELECT 'UP', t.trip_id, t.service_id, 'UP'
    FROM up.trips t
),
st AS (
    SELECT 'GO' AS operator, trip_id, stop_id, stop_sequence::INT AS seq,
           arrival_time, departure_time, coalesce(pickup_type, '0') AS pickup_type,
           coalesce(drop_off_type, '0') AS drop_off_type
    FROM go.stop_times
    UNION ALL
    SELECT 'UP', trip_id, stop_id, stop_sequence::INT, arrival_time, departure_time,
           coalesce(pickup_type, '0'), coalesce(drop_off_type, '0')
    FROM up.stop_times
),
union_seq AS (
    SELECT operator, trip_id, min(seq) AS union_seq FROM st WHERE stop_id = 'UN' GROUP BY ALL
),
service_days AS (
    SELECT 'GO' AS operator, service_id, service_date FROM go.active_services
    UNION ALL
    SELECT 'UP', service_id, service_date FROM up.active_services
)
SELECT st.operator, rt.line, st.trip_id, st.stop_id AS station_id, st.seq, d.service_date,
       CASE dayofweek(d.service_date) WHEN 6 THEN 'saturday' WHEN 0 THEN 'sunday' ELSE 'weekday' END AS day_type,
       split_part(st.arrival_time, ':', 1)::INT * 3600 + split_part(st.arrival_time, ':', 2)::INT * 60
           + split_part(st.arrival_time, ':', 3)::INT AS arr_sec,
       split_part(st.departure_time, ':', 1)::INT * 3600 + split_part(st.departure_time, ':', 2)::INT * 60
           + split_part(st.departure_time, ':', 3)::INT AS dep_sec,
       st.pickup_type <> '1' AS can_board,
       st.drop_off_type <> '1' AS can_alight,
       u.union_seq IS NOT NULL AND st.seq < u.union_seq AS toward_union,
       u.union_seq IS NOT NULL AND st.seq > u.union_seq AS from_union
FROM st
JOIN rail_trips rt USING (operator, trip_id)
JOIN service_days d ON d.operator = st.operator AND d.service_id = rt.service_id
LEFT JOIN union_seq u USING (operator, trip_id)
WHERE d.service_date IN (DATE '{weekday}', DATE '{saturday}', DATE '{sunday}');
