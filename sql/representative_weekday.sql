-- The Wednesday with the most scheduled trips in one feed. I use it as that feed's typical weekday,
-- because local feeds are published on different cycles and do not share a single calendar date.
SELECT a.service_date, count(*) AS trips
FROM {s}.active_services a
JOIN {s}.trips t USING (service_id)
WHERE dayofweek(a.service_date) = 3
GROUP BY a.service_date
ORDER BY trips DESC, abs(datediff('day', a.service_date, DATE '{target}')) ASC
LIMIT 1;
