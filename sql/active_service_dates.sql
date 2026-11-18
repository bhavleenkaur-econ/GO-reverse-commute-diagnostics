-- Service ids active on each date of one feed, built from calendar.txt and calendar_dates.txt.
-- {s} is the schema holding that feed. Times are not touched here.
CREATE OR REPLACE TABLE {s}.active_services AS
WITH cal AS (
    SELECT service_id,
           strptime(start_date, '%Y%m%d')::DATE AS start_d,
           strptime(end_date, '%Y%m%d')::DATE AS end_d,
           [sunday, monday, tuesday, wednesday, thursday, friday, saturday] AS dow_flags
    FROM {s}.calendar
),
expanded AS (
    SELECT c.service_id, d::DATE AS service_date
    FROM cal c, generate_series(c.start_d, c.end_d, INTERVAL 1 DAY) AS g(d)
    WHERE c.dow_flags[dayofweek(d::DATE) + 1] = '1'
),
added AS (
    SELECT service_id, strptime(date, '%Y%m%d')::DATE AS service_date
    FROM {s}.calendar_dates WHERE exception_type = '1'
),
removed AS (
    SELECT service_id, strptime(date, '%Y%m%d')::DATE AS service_date
    FROM {s}.calendar_dates WHERE exception_type = '2'
)
SELECT DISTINCT service_id, service_date FROM (
    SELECT * FROM expanded
    UNION ALL
    SELECT * FROM added
)
EXCEPT
SELECT service_id, service_date FROM removed;
