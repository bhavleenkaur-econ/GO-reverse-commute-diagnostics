"""Figures and the flow map. Every number on a figure comes from the destination table or the pairs."""

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

from . import config as C

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 140})

COLORS = {
    "mismatch": "#b45309",
    "market and service": "#1f6f5b",
    "service ahead of market": "#3b6ea5",
    "market and service both thin": "#8a8175",
}
LEGEND_NAMES = {
    "mismatch": "Mismatch: market ahead of service",
    "market and service": "Market and service",
    "service ahead of market": "Service ahead of market",
    "market and service both thin": "Market and service both thin",
}


def _save(fig, name):
    C.FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(C.FIGURES / name, bbox_inches="tight")
    plt.close(fig)


def flow_change(table, top=12):
    df = table.sort_values("reverse_2021", ascending=False).head(top).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.2, 6.2))
    y = range(len(df))
    ax.barh([i + 0.2 for i in y], df.reverse_2016, height=0.4, color="#b7b1a8", label="2016", zorder=3)
    ax.barh([i - 0.2 for i in y], df.reverse_2021, height=0.4, color="#1f4e79", label="2021", zorder=3)
    for i, r in zip(y, df.itertuples()):
        if pd.notna(r.reverse_change_pct):
            ax.text(max(r.reverse_2016, r.reverse_2021) + 600, i, f"{100 * r.reverse_change_pct:+.0f}%", va="center", fontsize=8)
    ax.set_yticks(list(y))
    ax.set_yticklabels(df.csd_name)
    ax.grid(axis="x", color="#ece7df", lw=0.6, zorder=0)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_xlabel("Toronto residents with a usual workplace in the municipality")
    ax.set_title("Toronto residents working in each destination, 2016 and 2021")
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    _save(fig, "flow_change.png")


def quadrant(table):
    fig, ax = plt.subplots(figsize=(11.6, 7.4))
    for name in ["market and service both thin", "service ahead of market", "market and service", "mismatch"]:
        group = table[table.quadrant.eq(name)]
        ax.scatter(
            group.market_score,
            group.rail_score,
            s=64 if name == "mismatch" else 28,
            c=COLORS[name],
            label=LEGEND_NAMES[name],
            zorder=4 if name == "mismatch" else 3,
            linewidths=0,
        )
    no_am = table[table.no_am_arrival]
    ax.scatter(no_am.market_score, no_am.rail_score, s=120, facecolors="none", edgecolors="#7c3a12", lw=0.8, zorder=5,
               label="No train from Toronto arrives 06:30 to 09:30")
    ax.axvline(table.attrs.get("market_median", table.market_score.median()), color="#b7b1a8", lw=0.7, zorder=1)
    ax.axhline(table.attrs.get("rail_median", table.rail_score.median()), color="#b7b1a8", lw=0.7, zorder=1)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 105)
    ax.set_xlabel("Reverse market score, 0 to 100")
    ax.set_ylabel("Counter-peak rail score, 0 to 100")
    ax.set_title("Where the reverse market is ahead of counter-peak service")
    # Names sit to the right of the axes so the leader lines do not cross the other points.
    focus = table[table.quadrant.eq("mismatch")].sort_values(["rail_score", "market_score"], ascending=[True, False])
    box = {"boxstyle": "square,pad=0.12", "facecolor": "white", "edgecolor": "none", "alpha": 0.94}
    gap = 5.0
    top = min(80, float(focus.rail_score.max()) + 8) if len(focus) else 0
    for i, r in enumerate(focus.itertuples()):
        ann = ax.annotate(
            r.csd_name,
            xy=(r.market_score, r.rail_score),
            xytext=(103, top - gap * (len(focus) - 1 - i)),
            textcoords="data",
            fontsize=8,
            color="#7c3a12",
            va="center",
            ha="left",
            arrowprops={"arrowstyle": "-", "color": "#c4a484", "lw": 0.6, "shrinkA": 0, "shrinkB": 0},
            bbox=box,
            annotation_clip=False,
            zorder=6,
        )
        ann.set_clip_on(False)
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    fig.subplots_adjust(right=0.74, bottom=0.2)
    _save(fig, "quadrant.png")


def timetable_strip(pairs, table):
    """Each tick is a weekday train from Toronto arriving at the best station in each destination."""
    out = pairs[pairs.leg.eq("out") & pairs.day_type.eq("weekday")]
    arrivals = out.groupby(["dest_id", "trip_id"]).alight_sec.min().reset_index()
    rows = table.sort_values(["line_name", "market_score"], ascending=[True, False])[["csd_name", "station_id", "station_name", "line_name"]]
    fig, ax = plt.subplots(figsize=(11, 0.34 * len(rows) + 1.6))
    for band, color in [(C.AM_ARRIVE, "#fbe8d3"), (C.PM_RETURN, "#e3ecf5")]:
        ax.axvspan(band[0] / 3600, band[1] / 3600, color=color, zorder=0)
    for i, r in enumerate(rows.itertuples()):
        t = arrivals.loc[arrivals.dest_id.eq(r.station_id), "alight_sec"] / 3600
        ax.scatter(t, [i] * len(t), marker="|", s=90, color="#1f4e79", lw=1.1, zorder=3)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{r.csd_name} ({r.station_name}, {r.line_name})" for r in rows.itertuples()], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(5, 25)
    ax.set_xticks(range(5, 26, 2))
    ax.set_xticklabels([f"{h % 24:02d}:00" for h in range(5, 26, 2)])
    ax.set_xlabel(f"Arrival time from a Toronto station, weekday {C.GO_WEEKDAY[6:]} Nov {C.GO_WEEKDAY[:4]}")
    ax.set_title("Trains from Toronto arriving at each destination's best station")
    ax.legend(
        handles=[Patch(facecolor="#fbe8d3", label="AM arrival band, 06:30 to 09:30"),
                 Patch(facecolor="#e3ecf5", label="PM return band, 15:30 to 18:30")],
        frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.06), ncol=2,
    )
    _save(fig, "timetable_strip.png")


def jobs_coverage(table):
    df = table.sort_values("jobs_2km_share")
    fig, ax = plt.subplots(figsize=(9.2, 7.4))
    ax.barh(df.csd_name, 100 * df.jobs_2km_share, color=[COLORS[q] for q in df.quadrant], zorder=3)
    ax.grid(axis="x", color="#ece7df", lw=0.6, zorder=0)
    ax.set_xlabel("Share of the municipality's jobs within 2 km of a GO or UP station, %")
    ax.set_title("How much of each destination's employment a station can reach")
    ax.legend(
        handles=[Patch(facecolor=c, label=LEGEND_NAMES[q]) for q, c in COLORS.items()],
        frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2,
    )
    fig.subplots_adjust(bottom=0.18)
    _save(fig, "jobs_coverage.png")


def flow_map(table, subdivisions, stations):
    import folium

    shapes = subdivisions.merge(table[["csd_code", "reverse_2021", "reverse_2016", "quadrant"]], on="csd_code", how="inner")
    shapes = shapes.to_crs(C.CRS_WGS84)
    shapes["geometry"] = shapes.geometry.simplify(0.0005)
    fmap = folium.Map(location=[43.75, -79.6], zoom_start=9, tiles="OpenStreetMap")
    folium.Choropleth(
        geo_data=shapes[["csd_code", "geometry"]].to_json(),
        data=shapes,
        columns=["csd_code", "reverse_2021"],
        key_on="feature.properties.csd_code",
        fill_color="YlOrBr",
        fill_opacity=0.65,
        line_opacity=0.4,
        legend_name="Toronto residents working in the municipality, 2021",
    ).add_to(fmap)
    folium.GeoJson(
        shapes[["csd_name", "reverse_2021", "reverse_2016", "quadrant", "geometry"]].to_json(),
        style_function=lambda f: {"fillOpacity": 0, "weight": 0},
        tooltip=folium.GeoJsonTooltip(
            fields=["csd_name", "reverse_2021", "reverse_2016", "quadrant"],
            aliases=["Municipality", "Toronto residents, 2021", "Toronto residents, 2016", "Class"],
        ),
    ).add_to(fmap)
    points = stations.to_crs(C.CRS_WGS84) if hasattr(stations, "to_crs") else stations
    for r in points.itertuples():
        folium.CircleMarker(
            [r.lat, r.lon],
            radius=3 if r.in_toronto else 4,
            color="#444" if r.in_toronto else "#1f4e79",
            fill=True,
            fill_opacity=0.9,
            tooltip=f"{r.station_name} ({r.line_name})",
        ).add_to(fmap)
    C.REPORTS.mkdir(parents=True, exist_ok=True)
    fmap.save(str(C.REPORTS / "flow_map.html"))


def all_figures(table, pairs, subdivisions, stations):
    flow_change(table)
    quadrant(table)
    timetable_strip(pairs, table)
    jobs_coverage(table)
    flow_map(table, subdivisions, stations)
