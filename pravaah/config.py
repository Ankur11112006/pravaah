"""One place for everything that changes between regions and events."""
from dataclasses import dataclass, field

@dataclass
class Event:
    name: str
    aoi: tuple                  # lon_min, lat_min, lon_max, lat_max
    route: tuple                # wider window for terrain routing
    dem_tiles: list
    gauge: tuple                # lat, lon to pull river discharge for
    sar_flood: str              # date of the SAR image used for calibration
    sar_base: str
    orbit: int
    # "stage": fit a water level to observed extent and drive it with GloFAS
    #          discharge, which gives a time dimension.
    # "observed": no level can be fitted (embanked river, cliff-like area-level
    #          curve), so take depth from the observed extent alone. One
    #          snapshot, no time dimension, and the system says so.
    hazard: str = "stage"
    stage: dict = field(default_factory=dict)
    # Per-event input paths. These lived as dicts inside three different
    # scripts that disagreed about which events existed, which is how Mahanadi
    # reached the routing stage and died on a KeyError. One place now.
    dem: str = ""              # elevation raster
    sar_mask: str = ""         # SAR flood extent, if the event has one
    sar_baseline: str = ""     # SAR low-flow scene, if the event has one
    end_date: str = ""         # last day of the discharge series to model

    def __post_init__(self):
        if not self.dem:
            self.dem = f"data/{self.name}_dem.tif"

PATNA = Event(
    name="patna",
    aoi=(84.90, 25.45, 85.35, 25.75),
    route=(84.60, 25.20, 85.70, 26.00),
    dem_tiles=["N25_00_E084", "N25_00_E085"],
    gauge=(25.61, 85.14),
    sar_flood="2019-09-30", sar_base="2019-09-18", orbit=121,
    dem="data/dem_route.tif",          # named before the project had events
    sar_mask="data/flood_mask.tif", sar_baseline="data/patna_baseline_vv.tif",
    end_date="2019-10-10",
)

DELHI = Event(
    name="delhi",
    aoi=(77.10, 28.50, 77.40, 28.80),
    route=(77.00, 28.30, 77.60, 29.00),
    dem_tiles=["N28_00_E077"],
    gauge=(28.66, 77.23),
    sar_flood="2023-07-16", sar_base="2023-06-22", orbit=27,
    # The Yamuna here is embanked. Connected area jumps from 0.0 to 121 km2
    # across 10 cm of level, so no level reproduces the observed 12.1 km2.
    # Verified, not assumed: see hazard.check_fit rejecting it.
    hazard="observed",
    dem="data/delhi_dem.tif", sar_mask="data/delhi_flood_mask.tif",
    sar_baseline="data/delhi_base_vv.tif", end_date="2023-07-31",
)

MAHANADI = Event(
    name="mahanadi",
    # Inland delta, deliberately NOT the wettest block. In a delta the wettest
    # cells are the estuary and the Bay of Bengal: the coastal block reads 49%
    # deeper than 2 m and is sea, not flood. This block is 1-2% deep, median
    # 0.57 m, which is what inundation on land actually looks like.
    aoi=(86.10, 19.95, 86.45, 20.25),
    route=(85.95, 19.80, 86.60, 20.40),
    dem_tiles=["N20_00_E086"],
    gauge=(20.30, 86.40),
    sar_flood="", sar_base="", orbit=0,       # no SAR needed: depth arrives ready made
    # C-Flood publishes the depth field itself, 30 m, in metres, every 3 hours to
    # 48 hours. Nothing is fitted, nothing is inferred from terrain.
    hazard="cflood",
    dem="data/Copernicus_DSM_COG_10_N20_00_E086_00_DEM.tif",
)

EVENTS = {e.name: e for e in (PATNA, DELHI, MAHANADI)}

# depth (m) -> what can still use the road
MODES  = [(0.30, "car"), (0.50, "bike"), (1.50, "foot"), (float("inf"), "boat")]
ORDER  = ["car", "bike", "foot", "boat"]
SPEED  = {"car": 30, "bike": 15, "foot": 4, "boat": 8}      # km/h
# A cell counts as flooded above this depth. Below it the value is numerical
# noise, and counting it put a quarter of a million people in 2 cm of water.
WET_M = 0.05

# A wet patch smaller than this is model speckle, not a flood. In one C-Flood
# frame 5,770 such patches held 36 km2 between them, most of it scattered over
# ground 10-20 m above any plausible flood level.
MIN_PATCH_KM2 = 0.05

WATER_DB, DROP_DB = -15.0, 3.0                              # SAR water thresholds
