# PRAVAAH: how it actually works

`README.md` is the story and the results. This is the engineering reference:
every stage, every algorithm, every file, every knob, and every place the system
refuses to answer.

Read this if you are going to change the code, or if you want to judge whether
the numbers deserve to be believed.

---

## 0. The shape of it in one page

```
                    ┌─────────────────────────────────────────┐
   THE HAZARD       │ a depth raster, in metres, on a 30 m grid│
   (an INPUT)       └─────────────────────────────────────────┘
                          ▲            ▲              ▲
              ┌───────────┘            │              └───────────┐
        stage mode              observed mode              cflood mode
   fit a water level to    FwDET from the observed    CWC's own hydrodynamic
   satellite extent at     extent alone. One          forecast. 30 m, metres,
   known discharge, then   snapshot, no time.         3-hourly to 48 h.
   drive it with GloFAS.
        (Patna)                  (Delhi)                   (Mahanadi)

                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
   EXPOSURE                   NETWORK                    ROUTES
   who is in it               roads carry ground         who can still
   buildings + GHS-POP        elevation, not a           reach a shelter,
   labelled by the            snapshot; mode is          who needs a bridge,
   nearest admin unit         computed per hour          who cannot at all
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   ▼
                              ALLOCATE
                   min-cost flow to shelters whose
                   capacity was measured, not assumed
                                   │
                                   ▼
                               ALERT
                 act when P > cost/loss. P is the share of a
                 50-member ensemble above a published return
                 period. CAP 1.2 XML + 160-character SMS.
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
   four pages                 the backend                 the national
   (single files)             FastAPI + SQLite            watch, 354 CWC
                              writes come back in         stations, live
```

The single most important design decision: **depth is an input, not an output.**
We tried to produce it from terrain, measured that it did not work, and made it a
parameter instead. Everything else follows from that.

---

## 1. The pipeline, stage by stage

`run.py <event>` sequences six scripts and stops at the first failure. Each is
runnable alone. Below, for each: what it reads, what it decides, what it writes.

### 1.1 `build_hazard.py <event> [run_date] [baseline_date]`

Produces the depth field. Behaviour depends on `Event.hazard`.

| mode | reads | writes |
|---|---|---|
| `stage` | DEM window, SAR flood mask, SAR baseline, GloFAS discharge | `out/depth/<ev>_<date>.tif` per day, `out/<ev>_stage.npy`, `out/<ev>_permanent.tif` |
| `observed` | DEM window, SAR flood mask, SAR baseline | one `out/depth/<ev>_<date>.tif`, `out/<ev>_permanent.tif` |
| `cflood` | DEM window, C-Flood WCS, a low-flow C-Flood run | `out/depth/<ev>_<date>_<hh>.tif` per frame, `out/<ev>_frames.npy`, `out/<ev>_permanent.tif` |

The permanent-water mask is written here and masked out by every later stage. It
is derived differently per mode and each choice was forced by a bug:

- `stage` and `observed`: the SAR baseline image, thresholded at `WATER_DB`.
- `cflood`: a **separate low-flow run of the same model**. Deriving it from the
  intersection of the current run's own frames is wrong, because during a
  sustained flood every frame is wet and the flood masks itself out. That hid
  roughly 500 km². OSM water polygons were tried too and caught 8 km² in an
  entire delta.

### 1.2 `build_timeline.py <event>`

Builds the road graph and, in `stage` mode only, the per-road mode timeline.

Reads `data/<ev>_osm_roads.json` and the DEM. Writes `data/<ev>_graph.pkl`.
In non-`stage` modes it builds the graph, says there is no level series, and
exits 0 rather than faking one.

### 1.3 `exposure.py <event> <depth.tif>`

Who is standing in the water. Reads the depth raster, the permanent mask,
`data/<ev>_buildings.gpkg`, GHS-POP (tile chosen from the AOI), and
`data/<ev>_osm_places.json`. Writes `out/<ev>_exposure.csv`.

Computation is on the 30 m grid and never on an administrative boundary; the
place name is attached at the end, for display only. A cell counts as flooded
above `WET_M` and outside the permanent channel.

### 1.4 `build_plan.py <event>`

Route survival. Reads the graph, the depth raster, the permanent mask, GHS-POP.
Writes `out/<ev>_deadlines.json`: per pickup point, its population, its car
cut-off level, and whether it is bridge-dependent.

This is where the three numbers that make the system honest come from: how many
people have a route, how many have none at any level, and how many are placed
only because a bridge is assumed open.

### 1.5 `allocate.py <event> <depth.tif>`

Assign people to shelters. Reads the graph, depth, permanent mask, GHS-POP and
`data/<ev>_shelters_measured.csv`. Writes `out/<ev>_allocation.json`,
`out/<ev>_place_shelter.json`, `out/<ev>_assign.json`.

Prints its own comparison against greedy nearest-shelter on every run.

### 1.6 `alert.py <event>`

When to act and what to say. Reads the exposure table, the per-place shelter
assignment, the graph, and the live GloFAS ensemble. Writes `out/<ev>_cap12.xml`
and `out/<ev>_sms.txt`.

---

## 2. The algorithms that matter

Six pieces do the real work. Everything else is plumbing.

### 2.1 Fitting a water level to what the satellite saw

`hazard.calibrate`, `hazard.check_fit`, `hazard.stage_line`

The problem: we need depth over time, and predicting inundation from terrain
failed the falsification test. The resolution: do not predict the extent, **fit
a level that reproduces an extent that was measured.**

```
for level in arange(percentile(dem,1), percentile(dem,65), 0.05):
    below      = dem < level
    components = label(below, 8-connectivity)
    flooded    = components touching the permanent-water seed
    area[level] = count(flooded) * 900 m²
```

Then for each observation date, take the level whose area is closest to the area
Sentinel-1 actually observed. Two dates give two `(discharge, level)` pairs, and
a line through them is the stage-discharge relation. GloFAS discharge then drives
the level forward, day by day.

**The line is fitted in log(Q), not Q.** A real rating curve is a power law,
`Q = a(h-h0)^b` with `b` between about 1.5 and 2.5, so stage grows roughly as
`Q^0.4` to `Q^0.67`. Two points cannot fit three parameters, but fitting
`h = a*ln(Q) + b` passes through both observations exactly while bending the
right way outside them. A straight line in Q climbs at a fixed rate for ever,
which is wrong at high flow where a widening floodplain absorbs discharge with
little rise, and extrapolation is precisely where a forecast lives.

Patna: 48.10 m at 35,155 m³/s and 48.70 m at 44,667 m³/s, both within 1.6 km² of
observed, giving `level = 2.5054 * ln(Q) + 21.87`.

**The seed is what the radar saw, and nothing else.** `calibrate` both seeds the
connectivity search and derives its area targets from the permanent-water mask,
which makes that mask load-bearing twice over. Widening it to catch riverbed the
radar missed silently moved the targets by 26 km², raised the fitted level by
20 cm and inflated exposure by 21%, while the reported fit error stayed under 2%,
because the fit was still good against the wrong targets. There are now two
masks: `perm` is exactly the radar observation and is the only one calibration
touches; `channel` is the widened version, used only downstream. See 2.5b.

**The connectivity requirement is not decoration.** Without it, every disconnected
depression below the level counts as flooded. With it, only water that can
physically reach the channel does.

**Where it is weak, stated plainly:** two calibration points, a straight line, and
a single flat water surface across 45 km of a river whose own surface slopes by
metres. It survived an external check to 10 cm against CWC's Gandhighat danger
level, which may be partly luck.

### 2.2 The evacuation cut-off, without a search per hour

`timeline.cutoff_levels`

The question: at what water level does a given place lose its last route to any
shelter?

The naive answer is to rebuild the passable subgraph at each hour and run a
shortest path. That is 529 Dijkstras per pickup point, and there are thousands
of points.

The observation that removes the loop: a path is usable at level `L` when every
edge on it has `bed > L - threshold`. So the best a place can tolerate is the
path that **maximises its minimum bed**: a maximum-bottleneck path. And every
maximum-bottleneck path in a graph lies on its maximum spanning tree.

```
sort edges by bed, descending
union-find over nodes, marking components that contain a shelter
for (bed, u, v) in that order:
    merge u and v
    if the merged component now contains a shelter:
        every pending source inside it has its answer: cutoff = bed + threshold
```

One pass, `O(E log E)`, all sources at once. Bridges enter with `bed = 1e6` so a
deck never becomes the bottleneck, and passing `use_bridges=False` measures how
much of the plan rests on them.

Verified in `test_timeline.py` against brute force (rebuild the subgraph at every
level on a 0.01 m grid) on **301 random source/graph cases**.

### 2.3 Allocation as a min-cost flow

`allocate.py`

Model:

```
SOURCE ──capacity = people──▶ pickup point
pickup point ──cost = travel minutes, capacity = demand──▶ shelter
shelter ──capacity = measured capacity──▶ SINK
```

Travel time comes from a Dijkstra out of each pickup point over the mode-passable
subgraph, cut off at 90 minutes. Costs are integers, so minutes are scaled ×10.

**Why not greedy nearest-shelter.** Nearest-first fills the shelters closest to
the densest wards and strands the last wards at full doors. The script prints the
comparison on every run and asserts on **coverage, not cost**:

> min-cost flow places 13,163 more people than greedy, at +13.5 minutes mean trip.

An earlier version of this check compared total person-minutes and made greedy
look cheaper, because greedy served 20,000 fewer people. Comparing cost between
methods that serve different populations is meaningless.

### 2.4 Shelter capacity from measured roof area

`build_shelters.py`

NDMA, *Guidelines on Minimum Standards of Relief*, section 2(c):

> In the relief centers, 3.5 Sq.m. of covered area per person with basic lighting
> facilities shall be catered to accommodate the victims.

So:

```
OSM campus polygons  ∪  OSDMA official shelter points, buffered 60 m
                     → union → distinct campuses
spatial join with the building footprints that cover this AOI
roof_m2  = Σ footprint area, in the AOI's own UTM zone
capacity = roof_m2 / 3.5
```

**Where the shelters come from matters more than the arithmetic.** In the
Mahanadi delta OpenStreetMap has two mapped shelter campuses, which set the
evacuation capacity of a cyclone-prone coast at 252 people. That is a fact about
OSM, not about Odisha: OSDMA publishes 776 built cyclone and flood shelters with
coordinates, 26 of them inside this AOI, and `fetch_osdma.py` pulls them. They
arrive as points, so each takes the footprints within 60 m and is measured by the
same rule; a point that already falls inside an OSM campus is dropped so nobody
is sheltered twice in one building.

**And the zone is derived, not assumed.** Every area here is metres, so the
projection has to suit the event. UTM 45N was hardcoded, which is correct for
Bihar and ten degrees wrong for Delhi, where scale error grows quadratically with
distance from the central meridian and area with its square: Delhi's roofs were
about 2% too large, and nothing in the output looked wrong.

Campuses within 250 m are collapsed by a cKDTree sweep taking the **largest, never
the sum**, because one campus is routinely mapped as several OSM ways. In Patna
that merged 129 duplicates. A grid-cell version of this dedup was tried first and
missed neighbours that fell across cell boundaries.

Patna: 90 usable shelters, 34.0 ha of measured roof, 97,094 capacity. The
assumptions it replaced were wrong in both directions: a school assumed at 500
measured 288; BIT Patna assumed at 1,000 measured 10,020. Mahanadi, with OSDMA
and full footprint coverage: 27 shelters holding 6,374 against 186,908 people in
the water. That shortfall is the finding, and it could not be stated at all while
the answer was "OSM knows two buildings".

**The measured file is now the only shelter list in the system.** The router and
the map page each carried their own copy of the guessed capacity table long after
the allocator stopped using it, so a judge clicking a school on the map saw 500
places while the plan behind it had measured 288, and the router was routing
people to sites the allocator could never fill.

**The residual error, unquantified:** a single-storey footprint understates a
multi-storey school, and not every roofed square metre is usable floor. The two
push opposite ways.

### 2.5 Depth from an extent alone

`hazard.fwdet_depth`

Used in `observed` mode, after Cohen's Floodwater Depth Estimation Tool. The
flood edge against dry land *is* the water surface:

```
water = flood | permanent
edge  = water cells adjacent to dry land
for every wet cell, take the elevation of its nearest edge cell
smooth that surface (uniform filter, 9 cells)
depth = surface − ground, clipped at zero
```

The first implementation took the edge of the flood alone, which on a river
fringe means the inner boundary is the river itself, where the DEM reads riverbed.
Every depth came out at zero. Taking the boundary of `flood | permanent` against
dry land is what makes it work.

**Its limit, measured:** on the Patna SAR extent this returns a median of 0.00 m
with 92% below 0.3 m, against road thresholds of 0.3 / 0.5 / 1.5 m. That is why
`stage` mode exists.

### 2.5b What counts as river rather than flood

`hazard.widen_channel`, `hazard.building_mask`

Water standing in the river is not a flood, and counting it inflates both area
and exposure. The channel is found from the radar baseline: whatever was already
water on the low-flow date. That misses the sandbars and side channels that were
dry that day, and each one re-enters the flood as land under a constant depth. At
Patna one reporting unit came back with a median and a maximum both exactly
8.70 m, which is a flat riverbed under a flat water surface.

The DEM gives the rest away. Copernicus GLO-30 flattens inland water to a single
elevation, so a stretch of river reads as a perfect plateau:

```
flat    = (max_filter(dem,3) - min_filter(dem,3)) == 0
channel = flat components connected to the radar permanent water
channel &= ~dilate(building_centroids, 5)     # a roof is evidence of ground
```

Two conditions, not one. Flatness alone is not proof, so only patches
**connected** to known water count. And a patch with buildings on it is kept as
land: the Ganga diara are inhabited sandbars, and a roof is better evidence of
ground than a DEM is of water.

At Patna: 214 km² seen by radar plus 26 km² it missed. Flooded area falls from
164 to 138 km² while the population falls by only 127, which is itself the
check: GHS-POP had correctly put almost nobody in the river, so a mask that
removed real people would have been the wrong mask.

### 2.5c The same cut-off, over frames instead of levels

`timeline.cutoff_levels(..., key=...)`, `build_plan.py`

C-Flood publishes a depth field every three hours. There is no level to fit, so
there is no `bed` to compare a level against, and the obvious move is a second
routing implementation for that case. That is also how two implementations drift
apart until only one of them is right.

The max-bottleneck argument does not actually care that the quantity is a water
level. It needs one thing: a per-edge number where larger means "lasts longer".
For frames that number is the index at which the edge first becomes impassable
to a given mode:

```
depth[frame, edge]              sampled once, every frame, every edge
die[edge] = first frame where depth >= mode limit,  else len(frames)
```

so `cutoff_levels` takes a `key` naming the edge attribute, and the C-Flood path
passes `die_car` / `die_bike` / `die_foot` with a threshold of zero. One routine,
verified against brute force on 301 random graphs, serves both hazard modes.

Two things had to be got right. **"Never closes" must sort strictly above the
last real frame**; giving it the same value as the final frame made car, bike and
foot report identical populations, which cannot happen when their depth limits
differ. And the output has to say which unit it is in, because `car_cutoff` is
metres for Patna and a frame index for Mahanadi: `out/<event>_deadlines.json`
now carries `unit` and `hours`, and `timeline.read_deadlines` is the only reader.

Mahanadi, on the 30 July 2025 run: 96,501 people keep a car route through the
whole 21-hour forecast, 80,221 lose one inside it, 10,135 never had one.

**An observed snapshot is this path with one frame.** Delhi has no fitted level,
so it long had no plan at all, and a `stage.npy` written before `check_fit`
rejected its calibration was still sitting on disk holding a water level of
203.53 m. Reading it would have produced exactly the confident wrong answer the
rest of this system exists to stop. Instead Delhi runs the frame path with a
single frame: route EXISTENCE at the observed depth is computable, a closing TIME
is not, and the output says which of the two it is holding rather than implying a
deadline that cannot exist.

### 2.6 The road graph carries terrain, not a snapshot

`network.build`, `network.mode_at`, `timeline.edge_timeline`

Each edge stores `bed`, the controlling ground elevation, so depth at any hour is
`level(t) − bed` and the whole timeline is analytic. No hourly rasters are ever
written.

Three details, each of which was a bug first:

- **Ways are split at every node used by two or more ways.** Joining only at way
  endpoints leaves the network shattered: the largest connected component held
  **1.1% of nodes**. After the fix, 97.8%.
- **`bed` is the 10th percentile of DEM samples along the segment, not the
  minimum.** One stray 30 m pixel landing in the river should not condemn a road.
  Bridges and embankments take the 90th percentile instead, because the deck sits
  above the terrain the DEM sampled.
- **A bridge is neither open nor flooded.** `mode_at` returns `"unknown"` for
  `structure == "bridge"`, and the system reports how many people depend on one
  rather than guessing. Before this, the DEM read the river *under* each deck and
  every Ganga bridge appeared under nine metres of water.

Modes, from `config.MODES`:

| depth | still passable by | assumed speed |
|---|---|---|
| under 0.30 m | car | 30 km/h |
| 0.30 to 0.50 m | two-wheeler | 15 km/h |
| 0.50 to 1.50 m | on foot | 4 km/h |
| above 1.50 m | boat only | 8 km/h |

### 2.7 The trigger

`alert.py`, `forecast.py`

Act when `P(event) > cost / loss`. The officer supplies cost and loss; the
threshold is arithmetic. `P` is computed, not typed:

```
gauge      = largest HydroBASINS outlet within 25 km  (never the nearest)
threshold  = that gauge's published 5-year return period
P          = share of the 50-member GloFAS ensemble above it, worst day
```

Live example: 11 of 50 members above 43,982 m³/s gives P = 22%, which authorises
opening shelters (2%), pre-positioning boats (12%) and moving livestock (20%),
and does **not** authorise full evacuation (55%).

**Snap to the largest gauge, never the nearest.** HydroBASINS puts an outlet on
every small catchment. The nearest one to Patna gave the Ganga a 200-year flood
of 148 m³/s.

---

## 3. Every guard that refuses

The system is designed to stop rather than answer wrongly. Each of these exists
because it once produced a confident wrong number.

| guard | refuses when | what it caught |
|---|---|---|
| `hazard.check_fit` | a calibration misses observed extent by more than 15% | Delhi fitted both dates to the same level at 96-98% error, then planned on it |
| `hazard.population` | the GHS-POP tile covering the AOI is absent | Delhi's population read zero everywhere; allocation reported "0 of 0" |
| `hazard.sanity_check_gauge` | discharge disagrees with the main stem's 2-year return period by 10× | Delhi's hand-typed gauge returns 22 m³/s for the Yamuna in flood |
| event-scoped filenames | never; structural | Delhi would have been planned on **Patna's roads** |
| `build_map_data` mode check | the event has no level series | the map page is a time slider with nothing to animate |
| solver coverage assertion | greedy places more people than the flow | the solver would not be earning its place |
| `store.add_decision` | an override carries no reason | an unexplained override in an audit log is worthless |
| cache key includes the run date | never; structural | a second C-Flood run silently reused the first run's rasters |
| `fetch_buildings` coverage check | the downloaded footprints do not span the AOI | the Mahanadi file covered 35% of its box after the AOI was moved inland, and every official shelter read as 8 km from the nearest roof |
| `hazard.buildings_path` | no footprint file spans the AOI | measuring roofs against a file with a hole in it, and reporting the hole as "no buildings here" |
| `hazard.named_places` | every place point in an event is unnamed | a reporting unit called `?`, which had already reached a drafted SMS |
| four-column survival assertion | the columns do not sum to the whole population | a route that was never passable being counted as a deadline an officer could work to |
| `build_map_data` mode check | the event carries no fitted level | the map page is a level slider; an observed snapshot has nothing to animate and a C-Flood event carries frames instead, so both are refused **by name** rather than lumped together |

---

## 4. Configuration

`pravaah/config.py`. Every value, and what changing it means.

```python
WET_M         = 0.05    # a cell is flooded above this depth, metres
MIN_PATCH_KM2 = 0.05    # smaller isolated wet patches are model speckle
WATER_DB      = -15.0   # Sentinel-1 VV water threshold, dB
DROP_DB       = 3.0     # backscatter drop that marks new water, dB
```

`WET_M` matters more than it looks. It was once 0 in `exposure.py` and 0.05 in
`build_hazard.py`, which put **249,582 people in 2 cm of water**. It is now
defined once.

`MIN_PATCH_KM2` exists because one C-Flood frame carried 6,045 separate wet
components; 5,770 of them were under 0.05 km² and held 36 km² between them,
mostly shallow and scattered over high ground.

An `Event` carries:

| field | meaning |
|---|---|
| `aoi` | the analysis window, lon/lat |
| `route` | a wider window for terrain routing, so drainage is not truncated |
| `dem_tiles` | Copernicus GLO-30 tiles to mosaic |
| `gauge` | reference point for discharge; snapped to the main stem downstream |
| `sar_flood`, `sar_base`, `orbit` | the Sentinel-1 pair, same relative orbit |
| `hazard` | `stage`, `observed` or `cflood`. A property of the river, not a preference |

Configured events:

| event | hazard | why that mode |
|---|---|---|
| `patna` | `stage` | a wide alluvial river; the area-level curve is smooth enough to fit |
| `delhi` | `observed` | the Yamuna is embanked; connected area jumps 0 → 121 km² across 10 cm |
| `mahanadi` | `cflood` | CWC publishes the depth field itself for this basin |

---

## 5. The backend

`api.py` over `pravaah/store.py`. FastAPI, SQLite in WAL mode, one file, no
daemon. `test_api.py` runs the real app against a throwaway database: **44 of 44
pass**, including a real image upload and read-back.

### Schema

```sql
reports   (id, ts, event, place, lat, lon, kind, depth_cm, note,
           photo, road, status, resolved_at, resolved_by)
help      (id, ts, event, place, lat, lon, people, mobility, contact,
           note, status, assigned, eta, closed_at)
decisions (id, ts, event, action, decision, probability, threshold,
           reason, officer)
```

Photos are written to `data/photos/` and only their filename is stored, so a
district's database file stays small enough to copy onto a pen drive. Contact
numbers are stored as a truncated SHA-256: the system needs to recognise a repeat
caller, it does not need a list of flood victims' numbers.

### Endpoints

| method | path | purpose |
|---|---|---|
| GET | `/api/health` | status, per-event readiness, store counts |
| GET | `/api/events` | configured events and their hazard mode |
| GET | `/api/national` | 354 CWC stations with counts by status |
| GET | `/api/national/alerts` | live NDMA alerts |
| GET | `/api/national/above-danger` | stations over their danger level, worst first |
| GET | `/api/events/{ev}/plan` | both totals, placed, beyond reach, no route, bridge-dependent |
| GET | `/api/events/{ev}/units` | reporting units |
| GET | `/api/events/{ev}/units/{place}` | one ward, with nearby roads and open reports |
| GET | `/api/events/{ev}/roads` | roads that change mode, and when |
| GET | `/api/events/{ev}/shelters` | capacity, occupancy, and the basis for capacity |
| GET | `/api/reference` | every value the write endpoints accept |
| POST | `/api/reports` | citizen report, optional photo |
| POST | `/api/reports/{id}/resolve` | officer closes it |
| GET | `/api/reports/{id}/photo` | serve the image |
| POST | `/api/help` | "I cannot leave", with mobility |
| POST | `/api/help/{id}/assign` | assign a team and an ETA |
| POST | `/api/help/{id}/close` | close it |
| POST | `/api/decisions` | approve or override, with a reason code |
| GET | `/api/decisions` | the audit log |

The help queue is ordered by mobility (`stretcher`, `cannot_move`, `needs_help`,
`walking`), then group size, then age. That ordering is the whole point of having
a separate queue.

`/plan` returns **two** population totals under separate names, and the
distinction is not pedantry:

| field | Patna | what it is |
|---|---|---|
| `people_wet` | 59,495 | everyone the exposure step found standing in water |
| `people_planned` | 59,211 | the subset the plan is built on |
| `not_planned` | 284 | the difference, returned explicitly |

A pickup point needs a road within reach and at least one whole person, so
isolated fractional cells carry no point and cannot be planned for. The
arithmetic `placed + beyond_reach + no_route` closes on `people_planned`, never
on `people_wet`, and the response says so in an `arithmetic` field. This endpoint
previously returned the planned figure under the name `people_wet`, which is how
the plan came to quote one number while the exposure table quoted another. Two
quantities sharing a name will eventually be reported as each other.

### Why writes exist at all

Every failure this project measured came from the same place: **the instruments
miss urban flooding.** Radar labelled 659 of 455,860 Patna buildings as flooded
during a week-long flood. No gauge sits in Rajendra Nagar. C-Flood does not cover
the Ganga.

A citizen report is the only sensor that does see it. That is not a feature; it
is the only route by which the thing the system most needs ever reaches it.

---

## 6. Data sources, with their quirks

| source | endpoint | quirk that will cost you a day |
|---|---|---|
| CWC FFS | `ffs.india-water.gov.in/iam/api/...` | Spring-Data JSON "specification" query language; needs a normal User-Agent |
| C-Flood | `inf.cwc.gov.in/geoserver/<workspace>/wcs` | **workspace-scoped** WCS only; unscoped `/geoserver/wcs` is 404 |
| NDMA SACHET | `sachet.ndma.gov.in/cap_public_website/FetchAllAlertDetails` | severity mixes CAP words with IMD colours; centroid order is undocumented |
| Google GRRR | `gs://flood-forecasting/hydrologic_predictions/...` | reanalysis is **left**-labelled, reforecast lead is **right**-labelled |
| Google inundation history | `gs://flood-forecasting/inundation_history/` | three nested risk polygons, not an event |
| GloFAS | `flood-api.open-meteo.com/v1/flood` | `ensemble=true` gives 50 members; null for reanalysis dates |
| Sentinel-1 RTC | Planetary Computer STAC | anonymous SAS signing; asset is `.tiff`, not `.tif` |
| OpenStreetMap | `overpass-api.de/api/interpreter` | query must be a `data=` **form field**; a raw POST returns 406 |
| GHS-POP | JRC tiles | 10-degree tiles; the wrong one returns zeros in silence |
| Microsoft buildings | `minedbuildings.z5.web.core.windows.net` | `Size` column is a string like `74.6MB` |

All free. None needs a key or a login.

---

## 7. Adding a new event

1. Add an `Event` to `pravaah/config.py`. Pick `hazard` by asking what the river
   does, not what is convenient.
2. Download the Copernicus DEM tiles covering `route`.
3. Download the GHS-POP tile covering `aoi`. Get it wrong and
   `hazard.population` will tell you which one you need.
4. `fetch_osm.py <event>` for roads, shelters, shelter polygons and places.
5. `fetch_buildings.py <event>` for Microsoft footprints.
6. `build_shelters.py <event>` to measure capacity.
7. For `stage` mode, `fetch_sar.py` for the same-orbit Sentinel-1 pair.
8. `run.py <event>`.
9. `build_citizen.py <event>`, `build_map_data.py <event>`,
   `build_dashboard.py <event>`, `build_standalone.py`.

Expect step 4 to be the one that fails. OSM coverage collapses outside cities: in
the Mahanadi delta it returned **2 shelter polygons** for the whole area, against
Patna's 158.

---

## 8. Verification

- `test_timeline.py` runs the cut-off algorithm against brute force on 301
  random graphs, plus bridge handling and interpolation bounds.
- `test_api.py` runs 44 endpoint tests against a real database, including that
  the plan's arithmetic closes: `placed + beyond_reach + no_route == people_wet`.
- `verify.py` regenerates every number the project claims, offline, in two
  parts: the falsification record and the working system. It writes every figure
  it computes to `out/numbers.json` with a provenance block: UTC timestamp, the
  Python version, and a SHA-256 over every source file, so a number can be traced
  to the exact code that produced it outside a git checkout.
- `stamp_docs.py` fills those figures into the documents. Each one carries a
  marker rather than a copy, `<!--N:people_wet-->59,495<!--/N-->` in markdown and
  `<span data-n="people_wet">` in HTML, and `--check` exits non-zero if any
  document disagrees with what the code last computed. This exists because a
  reviewer found the plan quoting 61,633 people while the exposure table said
  59,622: two scripts, two thresholds, one of them stale. A document that holds
  its own copy of a number will eventually hold a wrong one.
- `census_check.py` tests the population model against the thing it claims to
  redistribute, since every exposure figure depends on GHS-POP and nothing else
  in the pipeline counts people. It checks the boundary before the population:
  the OSM Patna district polygon measures 3,190 km² against the published
  3,202 km², so it is the right district, and only then compares.
- `demo.py` runs the whole chain of checks with no network: inputs present,
  numbers recomputed, documents in agreement, backend tests passing. It stops at
  the first failure, so a pass means four things held, not that nothing ran.

External checks, none of which were used to build anything:

| claim | independent source | ours |
|---|---|---|
| water level, 30 Sep 2019 | CWC Gandhighat danger level 48.60 m | 48.70 m |
| slum water depth | rapid needs assessment, "3 feet" = 0.91 m | 0.73 m median |
| population total | Census of India 2011, Patna district, carried to 2020 at its own 2001-2011 rate: 7,071,903 | GHS-POP 7,121,932, +0.7% |
| useful lead time | Google reforecast archive | 6 days at the 2-year threshold |

The slum depth agreement got *worse* after the river channel was removed from
the flood, and that is the correct direction: river cells were deep, and
including them flattered the median into a near-perfect match with a figure it
had no business matching. The census check is the strongest of the four, and it
still only tests the district total. Whether GHS-POP puts the right people on
the floodplain, which is what exposure actually depends on, is untested, and we
found no open dataset that settles it.

---

## 9. Known weaknesses, ranked

1. **Urban pluvial flooding is not modelled and cannot be, on open data.** Every
   layer here is riverine.
2. **The stage-discharge fit is two points and a straight line**, on a flat water
   surface across a river that slopes.
3. **Population is GHS-POP**, modelled, with 30-50% local error, snapped to road
   nodes for the pickup-point aggregation.
4. **Shelter capacity has an unquantified two-way error** (storeys up, usable
   fraction down).
5. **The plan layer is per-area.** The watch layer is national; the plan is not.
6. **The citizen page does not yet write to the backend.** The backend accepts
   the writes and is tested; the wiring is a frontend task.
