"""Project settings. Every date, window, threshold and rule used in the analysis lives here."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
SQL = ROOT / "sql"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"

GTFS_DIR = INTERIM / "gtfs"
CENSUS_DIR = RAW / "census"

CRS_METRIC = "EPSG:3347"
CRS_WGS84 = "EPSG:4326"

# Study area, the same box as the GO station scorecard: every GO rail station plus a margin.
STUDY_BBOX = {"xmin": -80.75, "ymin": 42.95, "xmax": -78.55, "ymax": 44.55}

# Service dates inside the current GO feed. GO publishes service by calendar date.
GO_WEEKDAY = "20261118"
GO_SATURDAY = "20261121"
GO_SUNDAY = "20261122"

# Time bands, in seconds after midnight. The reverse commuter arrives at work in the morning
# band and leaves for Toronto in the afternoon band.
AM_ARRIVE = (6 * 3600 + 30 * 60, 9 * 3600 + 30 * 60)
MIDDAY = (9 * 3600 + 30 * 60, 15 * 3600)
PM_RETURN = (15 * 3600 + 30 * 60, 18 * 3600 + 30 * 60)

# Last mile.
FEEDER_RADIUS_M = 250
MIN_TRANSFER_S = 3 * 60
WAIT_CAP_MIN = 60
RING_NEAR_M = 800
RING_FAR_M = 2000

# Toronto, the home side of every reverse commute.
TORONTO_CODE = "3520005"
TORONTO_DGUID = "2021A00053520005"
TORONTO_WORK_NAME = "Toronto (C), Ont."

# Classification thresholds, the same rules as the scorecard.
NEAR_CUT_POINTS = 5
TIE_MARGIN = 10
LOW_DEFICIT = 10

LOCAL_AGENCIES = {
    "barrie": "Barrie Transit",
    "brampton": "Brampton Transit",
    "burlington": "Burlington Transit",
    "durham": "Durham Region Transit",
    "grt_bus": "Grand River Transit",
    "grt_ion": "Grand River Transit ION",
    "guelph": "Guelph Transit",
    "hsr": "Hamilton Street Railway",
    "milton": "Milton Transit",
    "miway": "MiWay",
    "niagara": "Niagara Region Transit",
    "oakville": "Oakville Transit",
    "ttc": "Toronto Transit Commission",
    "yrt": "York Region Transit",
}

LINE_NAMES = {
    "BR": "Barrie",
    "KI": "Kitchener",
    "LE": "Lakeshore East",
    "LW": "Lakeshore West",
    "MI": "Milton",
    "RH": "Richmond Hill",
    "ST": "Stouffville",
    "UP": "UP Express",
}

CONSTRAINT_LABELS = {"rail": "Counter-peak timetable", "last_mile": "Station to workplace"}
