"""Write the executive brief from the destination table, so every number in the text matches the table."""

import pandas as pd

from . import config as C


def _n(value, digits=0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if number != number:
        return "n/a"
    return f"{number:,.{digits}f}"


def _pct(value, digits=0):
    return "n/a" if value is None or value != value else f"{100 * float(value):.{digits}f}%"


def _join(names):
    names = list(names)
    if not names:
        return "none"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + ", and " + names[-1]


def _date(code):
    return f"{code[:4]}-{code[4:6]}-{code[6:]}"


def _context(toronto, table):
    y16 = toronto[toronto.year.eq(2016)].iloc[0]
    y21 = toronto[toronto.year.eq(2021)].iloc[0]
    share16 = y16.reverse / y16.usual_place_of_work
    share21 = y21.reverse / y21.usual_place_of_work
    lines = ["## Context: 2016 to 2021", ""]
    lines.append(
        f"I first set the 2021 picture against 2016. In 2016, {_n(y16.worked_at_home)} of "
        f"{_n(y16.employed)} employed Toronto residents worked at home ({_pct(y16.wfh_share, 1)}). In 2021 the "
        f"count was {_n(y21.worked_at_home)} of {_n(y21.employed)} ({_pct(y21.wfh_share, 1)}). Toronto "
        f"residents with a usual place of work fell from {_n(y16.usual_place_of_work)} to "
        f"{_n(y21.usual_place_of_work)}."
    )
    lines.append("")
    rev_change = y21.reverse / y16.reverse - 1
    in_change = y21.inbound / y16.inbound - 1
    lines.append(
        f"Toronto residents with a usual workplace in a municipality that has a GO or UP station fell from "
        f"{_n(y16.reverse)} to {_n(y21.reverse)} ({100 * rev_change:+.0f}%). Ontario residents of other "
        f"municipalities with a usual workplace in Toronto fell from {_n(y16.inbound)} to {_n(y21.inbound)} "
        f"({100 * in_change:+.0f}%). As a share of Toronto residents with a usual place of work, the reverse "
        f"commute went from {_pct(share16, 1)} to {_pct(share21, 1)}. I read that as a smaller market that "
        "held its share, not as a reverse commute that grew. The 2021 count was taken during a lockdown."
    )
    lines.append("")
    top = table.sort_values("reverse_2021", ascending=False).head(6)
    bits = [
        f"{r.csd_name} {_n(r.reverse_2016)} to {_n(r.reverse_2021)} ({100 * r.reverse_change_pct:+.0f}%, "
        f"inbound {100 * r.inbound_change_pct:+.0f}%)"
        for r in top.itertuples()
    ]
    lines.append("The largest destinations, 2016 to 2021: " + "; ".join(bits) + ".")
    lines.append("")
    lines.append("![Toronto residents working in each destination](figures/flow_change.png)")
    lines.append("")
    return lines


def _findings(table, meta):
    focus = table[table.quadrant.eq("mismatch")].sort_values("market_score", ascending=False)
    lines = ["## What I found", ""]
    if focus.empty:
        lines.append("The median split did not leave a mismatch. I would inspect the scores before reading that as a finding.")
        lines.append("")
        return lines
    no_am = focus[focus.no_am_arrival]
    lines.append(
        f"I found {len(focus)} destinations where the reverse market is ahead of counter-peak service: "
        f"{_join(focus.csd_name)}. Together they had {_n(focus.reverse_2021.sum())} Toronto residents with a "
        f"usual workplace there in 2021, out of {_n(table.reverse_2021.sum())} across all {len(table)} destinations. "
        + (
            "At every one of them, no GO or UP train from any Toronto station arrives between 06:30 and 09:30."
            if len(no_am) == len(focus)
            else f"At {len(no_am)} of them ({_join(no_am.csd_name)}), no GO or UP train from any Toronto station "
            "arrives between 06:30 and 09:30."
        )
    )
    lines.append("")
    lines.append("| Destination | Best station | Line | Toronto residents, 2021 | Market | Rail | Last mile | First arrival | Gap I would act on | Confidence |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |")
    for r in focus.itertuples():
        lines.append(
            f"| {r.csd_name} | {r.station_name} | {r.line_name} | {_n(r.reverse_2021)} | {r.market_score:.0f} | "
            f"{r.rail_score:.0f} | {r.last_mile_score:.0f} | {r.first_arrival_clock} | "
            f"{C.CONSTRAINT_LABELS[r.primary_gap]} | {r.confidence} |"
        )
    lines.append("")
    lines.append("![Quadrant](figures/quadrant.png)")
    lines.append("")
    late = focus[focus.first_arrival_sec.between(C.AM_ARRIVE[1], C.AM_ARRIVE[1] + 30 * 60)]
    if len(late):
        bits = [f"{r.csd_name} ({r.station_name}, {r.first_arrival_clock})" for r in late.itertuples()]
        lines.append(
            "The first train from Toronto reaches " + _join(bits) + " within 30 minutes after the band closes. "
            + ("That destination is" if len(late) == 1 else "Those destinations are")
            + " one earlier trip away from a usable morning arrival, so "
            + ("it is" if len(late) == 1 else "they are")
            + " the cheapest test of the gap."
        )
        lines.append("")
    pm_only = focus[focus.first_arrival_sec.ge(C.PM_RETURN[0])]
    if len(pm_only):
        lines.append(
            f"At {_join(pm_only.csd_name)}, the first train from Toronto arrives after 15:30. Those lines run "
            "toward Union in the morning and away from it in the evening, so the reverse commute has no train "
            "in either direction when it needs one."
        )
        lines.append("")
    lines.append("![Arrivals from Toronto](figures/timetable_strip.png)")
    lines.append("")
    served = table[table.quadrant.eq("market and service")].sort_values("market_score", ascending=False)
    lines.append(
        f"The {len(served)} destinations with both a strong market and strong service are "
        f"{_join(served.csd_name)}. They form the reference group. Their median rail score is "
        f"{_n(meta.get('reference_rail'))} and their median last-mile score is {_n(meta.get('reference_last_mile'))}."
    )
    lines.append("")
    lines.append(
        f"The median is one cut. I also split the rail score at the 40th percentile ({_n(meta.get('rail_p40'), 1)}) "
        f"and the 60th ({_n(meta.get('rail_p60'), 1)}). Destinations with no morning arrival are a mismatch at every "
        f"cut: {_join(meta.get('mismatch_no_am') or [])}. Among destinations that do have a morning arrival, the ones "
        f"in the mismatch set at all three cuts are: {_join(meta.get('mismatch_clear') or [])}. Threshold-sensitive "
        f"(a mismatch at the median, not at the 40th): {_join(meta.get('mismatch_threshold_sensitive') or [])}. "
        f"Joining only at the 60th: {_join(meta.get('mismatch_looser_only') or [])}."
    )
    lines.append("")
    near = table[table.near_cut].sort_values("market_score", ascending=False)
    if len(near):
        lines.append(
            f"These destinations sit within {C.NEAR_CUT_POINTS} points of a median, so I do not treat their side of the "
            f"cut as firm: {_join(f'{r.csd_name} ({r.quadrant})' for r in near.itertuples())}."
        )
        lines.append("")
    lines.append("![Jobs near stations](figures/jobs_coverage.png)")
    lines.append("")
    return lines


def _evidence(table):
    focus = table[table.quadrant.eq("mismatch")].sort_values("market_score", ascending=False)
    lines = ["## Competing explanations", ""]
    lines.append(
        "For each mismatch, I put the gap I would act on next to the evidence that supports it and the evidence "
        "that cuts against it. When no train arrives in the morning band, I treat the timetable as the binding gap, "
        "because nothing at the station end can be used without a train. Otherwise the larger deficit against the "
        f"reference destinations is the gap. Confidence is low under a {C.LOW_DEFICIT}-point deficit, medium for a "
        f"tie within {C.TIE_MARGIN} points or a destination near a cut, and high otherwise."
    )
    lines.append("")
    lines.append("| Destination | Gap | Confidence | Supporting evidence | Contradictory evidence |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in focus.itertuples():
        lines.append(
            f"| {r.csd_name} | {C.CONSTRAINT_LABELS[r.primary_gap]} | {r.confidence} | "
            f"{r.supporting_evidence} | {r.contradictory_evidence} |"
        )
    lines.append("")
    return lines


def _recommendations(recs, table):
    from .mismatch import ACTIONS

    lines = ["## Recommendations", ""]
    if recs.empty:
        lines.append("There is no mismatch to act on at the median cut.")
        lines.append("")
        return lines
    key_of = {label: key for key, label in C.CONSTRAINT_LABELS.items()}
    for label, group in recs.groupby("primary_gap", sort=False):
        a = ACTIONS[key_of[label]]
        lines.append(
            f"**{label}.** {_join(group.csd_name)}. {a['action']} The owner is {a['owner']}. "
            f"I would track the {a['kpi'][0].lower() + a['kpi'][1:]}."
        )
        lines.append("")
    focus = table[table.quadrant.eq("mismatch")]
    weak_lm = focus[focus.deficit_last_mile.ge(C.LOW_DEFICIT)].sort_values("deficit_last_mile", ascending=False)
    if len(weak_lm):
        bits = [f"{r.csd_name} ({_pct(r.jobs_2km_share)} of jobs within 2 km)" for r in weak_lm.itertuples()]
        lines.append(
            "A train alone would not finish the trip at " + _join(bits) + ". There the station-to-workplace "
            "link is also at least 10 points behind the reference destinations, so I would plan the bus "
            "connection with the municipal operator at the same time as the timetable change."
        )
        lines.append("")
    return lines


def write(table, recs, toronto, meta):
    lines = ["# Reverse commuting from Toronto, and whether GO serves it", ""]
    lines.append("## Objective")
    lines.append("")
    lines.append(
        "I asked where Toronto residents who work in the suburbs are numerous, and where the GO and UP timetable "
        "does not get them to work in the morning and home in the evening. I did not estimate ridership. Station "
        "boardings and PRESTO transactions are not open, so I measured the market from the Census commuting "
        "flows and the service from the published timetable."
    )
    lines.append("")
    lines.append("## What I did, in order")
    lines.append("")
    lines.append(
        f"I first took the 2021 Census commuting flows between census subdivisions and kept Toronto residents "
        f"whose usual workplace is in a municipality with a GO or UP station. I then added the 2016 flows as "
        f"context. I then took the GO and UP Express schedule for Wednesday {_date(C.GO_WEEKDAY)}, the Saturday, "
        "and the Sunday, and found every one-seat ride that boards at a Toronto station and gets off at a "
        "station outside Toronto. The Census places a home only at the municipality level, so a reverse commuter "
        f"can board at any of the {meta.get('n_toronto_stations')} Toronto stations. For each of the "
        f"{meta.get('n_destination_stations')} destination stations I measured the arrival headway from 06:30 to "
        "09:30, the longest midday gap, the return headway toward Toronto from 15:30 to 18:30, and the span from "
        "the first arrival to the last return. I then measured the last mile: jobs within 800 m and 2 km of each "
        "station, the share of the municipality's jobs within 2 km, the local bus routes leaving the station in "
        "the morning band, and the scheduled wait from a train to the next bus. Only then did I score the "
        f"{meta.get('n_destinations')} destination municipalities."
    )
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        "Every score is a percentile rank from 0 to 100, and higher is better. The market score is the mean of two "
        "ranks: the number of Toronto residents working in the municipality, and their share of its jobs. The rail "
        "score ranks the best station in each municipality on the mean of four station ranks: arrival headway, "
        "return headway, longest midday gap, and span. A station with no train in a band shares the worst rank "
        "for that band. The last-mile score is the mean of the 2 km job share and the morning bus routes."
    )
    lines.append("")
    lines.append(
        f"Analysis 1 is a quadrant. The market median is {_n(meta.get('market_median'), 1)} and the rail median is "
        f"{_n(meta.get('rail_median'), 1)}. A destination above the market median and below the rail median is a "
        "mismatch. A destination whose best station gets no train from Toronto between 06:30 and 09:30 counts as "
        "thin service at any rank, because a relative rank cannot flag a gap that most destinations share. "
        f"Analysis 2 compares each mismatch with the {meta.get('reference_n')} destinations that have both a strong "
        "market and strong service, and names the larger gap: the counter-peak timetable or the station-to-workplace link."
    )
    lines.append("")
    lines.extend(_context(toronto, table))
    lines.extend(_findings(table, meta))
    lines.extend(_evidence(table))
    lines.extend(_recommendations(recs, table))
    lines.append("## Constraints")
    lines.append("")
    outside = _join(meta.get("stations_outside_study_area") or [])
    lines.append(
        "The 2021 Census was taken in May 2021, during a lockdown, and Statistics Canada rounds every count at "
        "random to a multiple of 5. I set a 2021 flow beside a 2026 timetable, so the market may have moved since. "
        "The flow table places homes only at the municipality level, so I cannot tell a resident near Union from "
        "one near Kipling. The last mile uses straight-line rings, not a walking network, and bus waits are "
        "scheduled, not observed. The best-station rule picks Pearson for Mississauga, which describes the "
        "airport, not the Lakeshore West or Milton stations. The TTC subway reaches Vaughan Metropolitan Centre "
        "and is outside this GO-only analysis, so the Vaughan gap is a GO gap, not a transit gap. "
        f"{outside} has no census subdivision in the study box and is left out."
    )
    lines.append("")
    lines.append("## What I would measure next")
    lines.append("")
    lines.append(
        "If a morning trip from Toronto is added on a mismatch line, I would track the first arrival, the arrival "
        "headway, and, once boardings exist, counter-peak boardings at the destination station against a station "
        "on a line that did not change. I would also rerun the flows on the 2026 Census when it is released, "
        "because that is the first count after hybrid work settled."
    )
    lines.append("")
    path = C.REPORTS / "executive_brief.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path
