-- Scheduled local transit stop events at stops within the feeder radius of a GO station,
-- on that feed's representative weekday. feeder_stops maps (agency, stop_id) to station_id.
INSERT INTO local_events
SELECT '{agency}' AS agency, f.station_id, st.stop_id, t.route_id, st.trip_id,
       split_part(st.arrival_time, ':', 1)::INT * 3600 + split_part(st.arrival_time, ':', 2)::INT * 60
           + split_part(st.arrival_time, ':', 3)::INT AS arr_sec,
       split_part(st.departure_time, ':', 1)::INT * 3600 + split_part(st.departure_time, ':', 2)::INT * 60
           + split_part(st.departure_time, ':', 3)::INT AS dep_sec,
       coalesce(st.drop_off_type, '0') <> '1' AS can_alight,
       coalesce(st.pickup_type, '0') <> '1' AS can_board
FROM {s}.stop_times st
JOIN {s}.trips t USING (trip_id)
JOIN {s}.active_services a ON a.service_id = t.service_id AND a.service_date = DATE '{date}'
JOIN feeder_stops f ON f.agency = '{agency}' AND f.stop_id = st.stop_id
WHERE st.arrival_time IS NOT NULL AND st.arrival_time <> '';
