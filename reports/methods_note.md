# Methods note

This note records the rules behind the executive brief. Every threshold named here is set in `src/reverse/config.py`, and every result is in `data/processed`.

## Who counts as a reverse commuter

I first classified every 2021 and 2016 commuting flow between census subdivisions. A flow is reverse when the home is the City of Toronto (code 3520005) and the usual workplace is a subdivision that holds a GO or UP station. A flow is inbound when that direction is flipped. A home and a workplace in the same subdivision is local. A Toronto home with a workplace in a subdivision without a station is kept apart, so it does not inflate the reverse market. Everything else is suburb to suburb. Both flow files cover Ontario homes only. I do not report a suburb-to-suburb total, because the 2021 file names workplaces outside the study box without a code, so that class is not comparable across the two years.

The 2021 flow table names the workplace subdivision but gives no code. I matched it on the name and type, for example "Mississauga (CY), Ont.", built from the 2021 boundary file. The 2016 table has codes. I then matched the 2016 codes to the 2021 codes, and the run records any 2021 destination without a 2016 match in `run_meta.json`.

The 2016 flow table is 98-400-X2016325. An earlier draft of the design cited 98-400-X2016391, which is the census-division table. I corrected that before building the 2016 chapter.

## Counter-peak supply

I then took one weekday, one Saturday, and one Sunday inside the current GO feed. GO publishes service by calendar date, so the dates are fixed in the config. For every trip I kept each stop in order and built one-seat pairs: board at a Toronto station, then get off at a later stop outside Toronto (the out leg), and the reverse for the trip home (the back leg). A rider can board at any Toronto station, because the Census places the home only at the subdivision level. The ride from Union is kept as a separate column.

For each destination station I measured:

- the arrival headway from 06:30 to 09:30, as the median gap between arrivals from Toronto;
- the longest midday gap from 09:30 to 15:00;
- the return headway toward Toronto from 15:30 to 18:30;
- the span from the first arrival from Toronto to the last departure back.

A gap counts only when both trains fall inside the band. A band with fewer than two trains gets the band length as its headway, so a station with no service in the band never looks frequent.

## Last mile

I then drew 800 m and 2 km straight-line rings around each destination station and put the 2021 jobs by census tract of work into them by area share. For each subdivision I dissolved the 2 km rings, clipped them to the subdivision, and divided the jobs inside by the subdivision's tract jobs. I linked every local bus stop within 250 m of a destination station, counted the routes leaving in the AM band, and measured the scheduled wait from each AM train arrival to the next bus at least 3 minutes later, capped at 60 minutes. Each local feed uses its own representative weekday, listed in `feeder_service_dates.csv`.

## Scores

Every score is a percentile rank from 0 to 100, and higher is better.

- The station supply score is the mean of four station ranks: arrival headway, return headway, longest midday gap, and span. A station tied at the band-length fill shares the worst rank, not the middle of the tie.
- The best station in a subdivision is the one with the highest supply score. Ties go to more AM arrivals, then more weekday arrivals.
- The market score is the mean of the ranks of the Toronto-resident workers and their share of the subdivision's jobs.
- The rail score is the rank of the best station's supply score.
- The last-mile score is the mean of the ranks of the 2 km job share and the most AM bus routes at any station in the subdivision.

## Mismatch rule

A destination above the market median and below the rail median is a mismatch. A destination whose best station gets no train from Toronto between 06:30 and 09:30 is on the thin-service side at any rank. I added that rule after the first run, because most destinations share that gap, and a relative rank put Vaughan and Markham above the rail median with no morning train at all.

A destination within 5 points of either median is near the cut. I also split the rail score at the 40th and 60th percentiles and report which mismatches hold at every cut.

For each mismatch I compared the rail and last-mile scores with the median of the destinations that have both a strong market and strong service. The larger deficit is the gap I would act on, unless there is no morning arrival, in which case the timetable is the binding gap. A deficit under 10 points gives low confidence. A tie within 10 points, or a destination near a cut, gives medium confidence. The rest are high.

## What I left out

The TTC subway reaches Vaughan Metropolitan Centre, and TTC and local bus routes cross the city line in many places. This analysis is about GO and UP, so a GO gap is not the same as a transit gap. I used straight-line rings instead of a walking network. Bus waits are scheduled. Stratford has no census subdivision inside the study box.
