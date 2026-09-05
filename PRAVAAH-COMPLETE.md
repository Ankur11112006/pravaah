# PRAVAAH, end to end

A single reference for the whole system: what was asked, what was tried, what
failed, what was built instead, every number, and every mistake found on the way.

Nothing in this file is typed by hand. Every figure is stamped from
`out/numbers.json`, which `verify.py` regenerates from the data offline. Run
`stamp_docs.py --check` to confirm this document still agrees with the code.

Last stamped: <!--N:generated-->2026-08-31 21:15 UTC, code cbd657062600<!--/N-->

---

## A. What the problem statement asked

PS3, "Disaster Response Intelligence Platform for Flood Prediction, Emergency
Response". The spec asked for:

1. Flood prediction with **48 to 72 hours** of lead time
2. Inundation mapping with **precision above 0.50 at recall above 0.70**
3. Depth estimates good enough to classify at **0.3 / 0.5 / 1.5 m** thresholds
4. Evacuation routing and shelter allocation
5. Alerts to citizens and officers

Constraint we set ourselves: **free and open data only**, no key, no login, no
licence negotiation. Anything a district office cannot get on a Tuesday morning
does not count.

---

## B. The answer in one paragraph

Requirement 2 cannot be met by anyone using free data, and we proved it rather
than assuming it. So the system stopped trying to predict *where* water goes from
terrain, and instead fits a water **level** to an extent a satellite actually
measured, then drives that level with public river discharge. That gives the time
dimension the problem statement really wanted. On top of it sits the part nobody
else was building: who is in the water, when each road stops carrying each
vehicle, who can still reach a shelter that has measured room, and what an
officer is authorised to do at today's probability. Lead time measured on the
real event: **6 days**, against the 48 to 72 hours asked for.

---

## C. The falsification test, and its result

Before building, we wrote the test that would kill the idea, pre-registered the
pass mark, and ran it. It failed. The negative result is kept on the record
because it is the most useful thing we learned.

### C.1 The design under test

HAND (Height Above Nearest Drainage) is the standard cheap inundation predictor:
compute how high each cell sits above the drainage it flows to, threshold it,
call that the flood. We tested it against a Sentinel-1 observed flood on two real
events, Patna 2019 and the Delhi Yamuna 2023.

### C.2 The result, per 30 m cell, AUC

| predictor | Patna 2019 | Delhi 2023 |
|---|---|---|
| HAND | <!--N:patna_auc_hand-->0.657<!--/N--> | <!--N:delhi_auc_hand-->0.706<!--/N--> |
| plain elevation threshold | <!--N:patna_auc_elev-->0.657<!--/N--> | <!--N:delhi_auc_elev-->0.663<!--/N--> |
| distance to the river | <!--N:patna_auc_dist-->0.662<!--/N--> | **<!--N:delhi_auc_dist-->0.939<!--/N-->** |
| Google inundation history | **0.758** | 0.654 |

No AUC threshold was registered in advance, so this table has no pass mark and
none is invented here. The target that *was* set beforehand was on precision:
above 0.50 at recall above 0.70. Measured: **9% in Patna, 5% in Delhi.**

**HAND does not beat a one-line elevation threshold.** That held across three
DEMs (Copernicus GLO-30, NASADEM, ALOS AW3D30) and six drainage thresholds from
acc>500 to acc>200000. It is not a tuning problem.

### C.3 The bigger finding: the ground truth is not the disaster

The single best predictor on Delhi is **distance to the river**, at 0.939. That
is not a hydrology result, it is a measurement result: free Sentinel-1 is mapping
the river channel widening, not the flood that hurt people.

- Median distance of "flood" from permanent water: **<!--N:patna_median_dist_m-->134<!--/N--> m** (Patna), **<!--N:delhi_median_dist_m-->170<!--/N--> m** (Delhi)
- Of <!--N:buildings_sampled-->455,860<!--/N--> Patna buildings, radar labels **<!--N:buildings_flooded-->659<!--/N--> as flooded**, which is 0.145%
- Building-level AUC: HAND <!--N:bld_auc_hand-->0.764<!--/N-->, plain elevation <!--N:bld_auc_elev-->0.866<!--/N-->

The 2019 Patna disaster was Rajendra Nagar, Kankarbagh, Boring Road and
Pataliputra Colony, all pluvial, all kilometres from the Ganga, and **none of
them are in the radar ground truth**. Urban double-bounce hides standing water
between buildings, and the peak drains before the satellite passes again.

So the test as written cannot be passed by anyone using free data. We say that
plainly rather than tuning until a number looks acceptable.

### C.4 Two more things that do not work

- **Chennai Michaung has no usable ground truth at all.** Sentinel-1 passed on
  6, 18 and 30 November 2023 and then not again until 17 January 2024. The
  cyclone peaked on 4 December, inside a 48-day gap. Verified against ASF and the
  Copernicus Data Space; every December optical scene is 65 to 99% cloud.
- **Depth from an extent alone is not recoverable.** FwDET over the real Patna
  radar map gives a median of <!--N:fwdet_median_m-->0.00<!--/N--> m, with
  <!--N:fwdet_below_30cm_pct-->92.4<!--/N-->% below 0.3 m. The design needs
  0.3 / 0.5 / 1.5 m classes, so that is unusable as a depth source.

---

## D. What was built instead

The pivot: **do not predict the extent. Fit a level to an extent that was
measured, then move that level with discharge.**

```
GloFAS discharge (free, no key, historical and forecast)
        |
        v
stage-discharge relation, fitted to two observed satellite extents
        |
        v
water level per day  ->  depth raster per day  ->  the whole decision layer
```

The terrain is still used, but for what it is good at: holding a water surface
and telling you the ground elevation under a road. It is no longer asked to
predict where water goes, because that is the thing it failed at.

---

## E. The hazard layer, three modes

`pravaah/hazard.py`, `build_hazard.py`. `config.Event.hazard` picks the mode.

### E.1 `stage`, used by Patna

Search every water level in 5 cm steps. At each level take everything below it
that is **hydraulically connected** to the permanent channel, and measure the
area. Pick the level whose area matches what Sentinel-1 observed on that date.
Two dates give two (discharge, level) pairs.

```
for level in arange(percentile(dem,1), percentile(dem,65), 0.05):
    below      = dem < level
    components = label(below, 8-connectivity)
    flooded    = components touching the permanent-water seed
    area[level] = count(flooded) * 900 m2
```

Connectivity is not decoration. Without it every disconnected depression below
the level counts as flood.

Patna fit: **48.10 m at 35,155 m3/s** and **48.70 m at 44,667 m3/s**, both within
1.6 km2 of what the satellite saw.

**The line is fitted in log(Q), not Q.** A real rating curve is a power law,
`Q = a(h-h0)^b` with b around 1.5 to 2.5, so stage grows roughly as Q^0.4 to
Q^0.67. Two points cannot fit three parameters, but `h = a*ln(Q) + b` passes
through both observations exactly and bends the right way outside them. A
straight line in Q climbs at a fixed rate for ever, which is wrong at high flow
where a widening floodplain absorbs discharge with little rise, and extrapolation
is exactly where a forecast lives. Result: `level = 2.5054 * ln(Q) + 21.87`.

**External check, not used to build anything:** CWC's official Gandhighat danger
level is 48.60 m. Our independently fitted level for 30 September 2019 is
48.70 m. Ten centimetres apart.

### E.2 `observed`, used by Delhi

The Yamuna here is embanked. Connected area jumps from 0.0 to 121 km2 across ten
centimetres of level, so **no level reproduces the observed 12.1 km2**. That is
not a failure to hide, it is a property of the river, and `hazard.check_fit`
refuses the fit rather than letting the pipeline run on it.

Depth instead comes from FwDET: the flood edge against dry land is the water
surface, propagate that elevation inward, subtract the ground. One snapshot, and
**no time dimension**, and every output for Delhi says so.

### E.3 `cflood`, used by Mahanadi

CWC's own C-Flood system publishes an operational inundation **depth field**,
30 m, in metres, every three hours out to 48 hours, for the Mahanadi basin.
Nothing is fitted and nothing is inferred from terrain: the frames are clipped to
the AOI and used directly. This is the system running on a real government
operational forecast rather than on a hindcast we chose.

The run used is **30 July 2025 at 16,519 m3/s, which is 1.83x the 2-year return
period**. That date was selected by taking GloFAS discharge at the Mahanadi
main-stem gauge across C-Flood's whole archive and cross-checking which dates
actually have a published workspace.

---

## F. What counts as river rather than flood

Water standing in the river is not a flood, and counting it inflates both area
and exposure.

The channel is found from the radar baseline: whatever was already water on the
low-flow date. That misses the sandbars and side channels that were **dry that
day**, and each of those then re-enters the flood as land under a constant depth.
At Patna one reporting unit came back with a median and a maximum depth both
exactly 8.70 m, which is a flat riverbed under a flat water surface.

The DEM gives the rest away. Copernicus GLO-30 flattens inland water to a single
elevation, so a stretch of river reads as a perfect plateau:

```
flat    = (max_filter(dem,3) - min_filter(dem,3)) == 0
channel = flat components connected to the radar permanent water
channel &= ~dilate(building_centroids, 5)     # a roof is evidence of ground
```

Two conditions, not one. Flatness alone is not proof, so only patches
**connected** to known water count. And a patch with buildings on it is kept as
land, because the Ganga diara are inhabited sandbars and a roof is better
evidence of ground than a DEM is of water.

Patna: 214 km2 seen by radar plus 26 km2 it missed. Flooded area falls from 164
to <!--N:flooded_km2-->138<!--/N--> km2 while the population falls by only 127,
which is itself the check: GHS-POP had correctly put almost nobody in the river,
so a mask that removed real people would have been the wrong mask.

For a C-Flood event there is no radar baseline, so the seed comes from OSM's own
mapped water polygons instead, then is widened the same way.

---

## G. The road network

`pravaah/network.py`, `build_timeline.py`.

Roads are split at **every node used by two or more ways**, not only at way
endpoints. Before that fix the largest connected component held 1.1% of nodes;
after it, 97.8%.

Each segment stores the **controlling ground elevation**, the 10th percentile of
DEM samples along it, so depth at any hour is level(t) minus that. The timeline
is analytic and no hourly rasters are stored.

**Bridges are never assumed passable and never assumed flooded.** A DEM reads the
river surface *under* a deck, which made every Ganga bridge appear under nine
metres of water. `structure` is tagged from OSM (1,154 bridges, 60 tunnels, 76
embankments); bridges are routable but flagged, and the system reports how many
people depend on one so an officer can send somebody to check.

---

## H. Exposure

`exposure.py`. Population is GHS-POP 2020, 100 m, resampled onto the 30 m grid
with area weighting. A cell counts as flooded above `config.WET_M` = 0.05 m, one
threshold used by every stage.

Reporting units are Voronoi cells around named OSM place points. Points with no
name are dropped, and their cells fall to the nearest named place.

**Patna at the peak: <!--N:people_wet-->59,495<!--/N--> people across
<!--N:reporting_units-->18<!--/N--> reporting units,
<!--N:flooded_km2-->138<!--/N--> km2.**

### H.1 The population model, checked against the Census of India

Every exposure figure rests on GHS-POP, which is a model: it takes census counts
and redistributes them onto a grid using satellite-detected built-up area. If
that redistribution is biased, every number here is wrong by the same factor and
nothing else in the pipeline would notice.

`census_check.py` tests it. The boundary is checked before the population: the
OSM Patna district polygon measures
<!--N:census_polygon_km2-->3,190<!--/N--> km2 against the published 3,202 km2, so
it is the right district, and only then is anything compared.

| | |
|---|---|
| GHS-POP 2020 inside the district | <!--N:ghs_pop_district-->7,121,932<!--/N--> |
| Census 2011 | 5,838,465 |
| Census 2001 | 4,718,592 |
| implied growth | 2.15% per year |
| 2011 carried forward to 2020 | <!--N:census_projected-->7,071,903<!--/N--> |
| **difference** | **<!--N:census_rel_error_pct-->+0.7<!--/N-->%** |

**What this does not test:** how GHS-POP places people *within* the district. A
model can total correctly and still put the wrong people on the floodplain, and
no open dataset we found settles that.

---

## I. Routes and deadlines

`pravaah/timeline.py`, `build_plan.py`.

For every pickup point, the last moment at which a route to **any** shelter still
exists, per travel mode.

Mode thresholds, `config.MODES`: car 0.30 m, bike 0.50 m, foot 1.50 m, then boat.

### I.1 The algorithm

A path is usable at level L when every edge on it has `bed > L - threshold`. So
the best a source can tolerate is the path that **maximises its minimum bed**,
the maximum-bottleneck path. Kruskal in descending bed order with union-find
gives that for every source in one pass, instead of a shortest-path search per
hour. Verified against brute force on **301 random graphs** in
`test_timeline.py`.

### I.2 The same routine over frames

The argument does not care that the quantity is a water level. It needs one
thing: a per-edge number where larger means "lasts longer". So `cutoff_levels`
takes a `key` naming the edge attribute, and a C-Flood event passes the frame
index at which each edge first goes under:

```
depth[frame, edge]              sampled once, every frame, every edge
die[edge] = first frame where depth >= mode limit,  else len(frames)
```

An **observed** event is that same path with a single frame: route existence at
the observed depth is computable even though a closing time is not. One routine,
one brute-force test, three hazard modes.

The output carries its own unit, because `car_cutoff` is metres for Patna and a
frame index for Mahanadi. `out/<event>_deadlines.json` holds `unit` and `hours`,
and `timeline.read_deadlines` is the only reader.

### I.3 What Patna's plan says

| mode | survives | closes in window | already gone | no route ever |
|---|---|---|---|---|
| car | 21,803 | 14,083 | 22,734 | <!--N:no_route-->591<!--/N--> |
| bike | 26,345 | 17,116 | 15,159 | 591 |
| foot | 49,311 | 3,916 | 5,393 | 591 |

Four columns, not two, and an assertion checks they sum to the whole population.
"Closes in window" is a deadline an officer can work to. "Already gone" is not a
deadline, it is a fact, and merging them made 22,734 people look like they had
time that did not exist.

**Bridge dependency: <!--N:bridge_dependent-->17,225<!--/N--> people** reach a
shelter only across a bridge whose state terrain cannot determine. That is a
number an officer resolves by sending someone, and the system says so rather than
quietly assuming the bridge is open.

---

## J. Shelters and allocation

### J.1 Capacity is measured, not assumed

`build_shelters.py`. NDMA, *Guidelines on Minimum Standards of Relief*, section
2(c): **3.5 square metres of covered area per person.**

```
OSM campus polygons  +  OSDMA official shelter points, buffered 60 m
                     -> union -> distinct campuses
spatial join with the building footprints that cover this AOI
roof_m2  = sum of footprint area, in the AOI's own UTM zone
capacity = roof_m2 / 3.5
```

Campuses within 250 m are collapsed by a cKDTree sweep taking the **largest,
never the sum**, because one campus is routinely mapped as several OSM ways. In
Patna that merged 129 duplicates.

Patna: <!--N:shelters_measured-->90<!--/N--> usable shelters,
<!--N:shelter_roof_ha-->34.0<!--/N--> ha of measured roof across
<!--N:shelter_footprints-->564<!--/N--> footprints, capacity
<!--N:shelter_capacity-->97,094<!--/N-->.

The guesses this replaced were wrong in **both** directions: a school assumed at
500 measured 288; BIT Patna assumed at 1,000 measured 10,020.

Residual assumption, stated: every roofed square metre is treated as usable
floor, and a single-storey footprint understates a multi-storey school. The two
errors push opposite ways and neither is quantified, so this is an upper bound.

### J.2 Where the shelters come from matters more than the arithmetic

In the Mahanadi delta OpenStreetMap has **two** mapped shelter campuses, which
would set the evacuation capacity of a cyclone-prone coast at 252 people. That is
a fact about OSM, not about Odisha. OSDMA publishes 776 built cyclone and flood
shelters with coordinates; `fetch_osdma.py` pulls them, and 26 fall inside this
AOI. They arrive as points, so each takes the footprints within 60 m and is
measured by the same rule; a point already inside an OSM campus is dropped so
nobody is sheltered twice in one building.

### J.3 Allocation

`allocate.py`. OR-Tools `SimpleMinCostFlow`: pickup points are sources, shelters
are sinks with measured capacity, arc cost is travel time by the best mode still
available at that depth, and nothing is placed beyond 90 minutes.

Every run prints its own greedy-nearest baseline so the solver has to earn its
place. Patna: **min-cost flow <!--N:placed-->47,443<!--/N--> placed at 72.0 min
mean, greedy 34,500 at 58.2 min**. The solver reaches 12,943 more people for
13.8 more minutes of average journey. The comparison is on **coverage**, not
total cost, because comparing cost between methods that serve different
populations is meaningless.

<!--N:beyond_reach-->11,177<!--/N--> people are beyond 90 minutes of any shelter
with room. That is reported, not hidden.

---

## K. The trigger

`alert.py`. Cost-loss decision rule: act when `P(event) > cost / loss`.

| action | cost | loss | fires above |
|---|---|---|---|
| Check and open shelters | 2 | 100 | 2% |
| Pre-position boats and crews | 12 | 100 | 12% |
| Move livestock to high ground | 20 | 100 | 20% |
| Full evacuation of the ward | 55 | 100 | 55% |

**The probability is computed, not typed.** It is the share of GloFAS's 50-member
ensemble above a published return period at the main-stem gauge, and the line
that prints it says where it came from. If the service is unreachable it falls
back to a constant and says so in the same line.

Outputs: **CAP 1.2 XML** that parses, and 160-character SMS drafts naming the
ward's own assigned shelter rather than the busiest one.

---

## L. The national layer

`national.py`, `pravaah/cwc.py`, `pravaah/sachet.py`, `pravaah/cflood.py`.

All three of India's operational flood systems are open, and we checked rather
than assumed:

| | |
|---|---|
| CWC stations pulled live | 354 |
| above danger level at the last pull | 12 |
| above warning level | 29 |
| normal | 177 |
| not reporting | 136 |
| live NDMA SACHET alerts | 65 |

The "not reporting" count is deliberately shown. A gauge that is silent during a
flood is information, and a dashboard that quietly drops it is lying by omission.

---

## M. The backend

`api.py`, `pravaah/store.py`, `test_api.py`. FastAPI over SQLite in WAL mode.
**44 of 44 tests pass** against the real app with a throwaway database and a real
image upload.

Read endpoints serve what the pipeline computed. Write endpoints accept the three
things no instrument can see:

- a **citizen report**, with an optional photo, because a person outside their
  door is the only sensor that sees urban pluvial flooding
- a **request for help** carrying mobility, so the queue puts stretcher and
  cannot-move cases before walking ones, then group size, then age
- an **officer decision**, approved or overridden, and an override without a
  reason code is refused with a 422

Contact numbers are never stored in the clear. They are stored as a truncated
**HMAC-SHA-256 under a secret this district generates and keeps**
(`data/.contact_key`), so the system can recognise a repeat caller without
holding a list of flood victims' phone numbers.

The secret is the point, and it was not there at first. A plain hash of a phone
number is not protection: there are about a billion of them in India, so anybody
holding the database can hash every possible number in seconds and read the
column straight back. With a district secret mixed in they cannot, unless they
also take the key file, which is why that file is gitignored and must never be
copied alongside the database.

### What the system holds about a person, in full

| what | where it comes from | kept as |
|---|---|---|
| ward name | the person picked it from a list in the app | plain text |
| latitude, longitude | the **centroid of that ward**, not the handset | plain text |
| depth, kind, note | what the person typed | plain text |
| photo | optional, only if the person attaches one | a file on the district's disk |
| phone number | optional, only on a help request | HMAC under the district secret |

The app reads **no GPS**. It holds no account, no login, no device identifier, no
analytics and no advertising SDK. The published APK asks Android for `INTERNET`
and `VIBRATE` and nothing else; it used to ask for fine and coarse location as
well, which came from an Expo module nothing in the app imported. The module and
the permissions are gone, and `aapt2 dump permissions` on the built APK is the
check.

### What is deliberately still open

Being honest about this is cheaper than being caught by it:

- **The LAN traffic is not encrypted.** The phone talks to the district server
  over plain HTTP, so a report and a phone number cross the local wifi in the
  clear. Fine on an isolated demo network, not fine on a district's network.
  This needs TLS before anybody deploys it.
- **The API has no authentication.** Anybody who can reach the server can read
  the help queue and log a decision. A district deployment needs at minimum a
  shared district credential on the write endpoints.
- **CORS is wide open** (`allow_origins=["*"]`), which with no authentication
  means any page in a browser on that network can call it.

`/api/events/{ev}/plan` returns **two** population totals under separate names:

| field | Patna | what it is |
|---|---|---|
| `people_wet` | <!--N:people_wet-->59,495<!--/N--> | everyone the exposure step found in water |
| `people_planned` | <!--N:pickup_people-->59,211<!--/N--> | the subset the plan is built on |
| `not_planned` | <!--N:pickup_gap-->284<!--/N--> | the difference, returned explicitly |

A pickup point needs a road within reach and at least one whole person, so
isolated fractional cells carry no point. The arithmetic
`placed + beyond_reach + no_route` closes on `people_planned`, never on
`people_wet`, and the response says so in an `arithmetic` field.

---

## N. The pages

Five single files, each with its data inlined. No server, no CDN, no build step:
double-click to open.

| page | for |
|---|---|
| `out/pravaah_national.html` | India live: 354 CWC stations, NDMA alerts, C-Flood run status |
| `out/pravaah_dashboard.html` | the officer desk: situation, wards, plan, act, evidence |
| `out/pravaah_map.html` | the flood itself, with a time slider over the forecast |
| `out/pravaah_citizen.html` | what one person in one ward needs, phone-shaped |
| `out/pravaah_overview.html` | the written walkthrough |

The map renders on canvas with the elevation grid inlined as base64, so there is
no mapping library and nothing to fetch.

---

## O. How the numbers are kept honest

This is the part that matters most, because a review found the plan quoting
61,633 people while the exposure table said 59,622. Two scripts, two thresholds,
one of them stale.

1. **`verify.py`** recomputes every claimed figure from `data/` and `out/`,
   offline, in two parts: the falsification record and the working system. It
   writes all 44 figures to `out/numbers.json` with a provenance block: UTC
   timestamp, Python version, and a SHA-256 over every source file, so a number
   can be traced to the exact code that produced it outside a git checkout.
2. **`stamp_docs.py`** fills those figures into the documents. Each document
   carries a **marker**, not a copy: in markdown an HTML comment naming the key,
   wrapped around the value and closed by a matching comment; in HTML a `span`
   carrying a `data-n` attribute. `--check` exits non-zero if any document
   disagrees with what the code last computed. A document that holds its own copy
   of a number will eventually hold a wrong one.
3. **`census_check.py`** tests the population model against the census, boundary
   first.
4. **`demo.py`** runs all of it with **no network**: inputs present, numbers
   recomputed, documents in agreement, backend tests passing. It stops at the
   first failure, so a pass means four things held rather than that nothing ran.

```
.venv\Scripts\python.exe demo.py
```

About nine seconds, 0.84 GB of cached inputs, nothing reaching the internet.

**This mechanism bit us once, which is worth recording.** An earlier draft of
this very section wrote an example opening marker in prose without closing it.
The stamper matched it, ran forward to the next real closing tag, and replaced
two entire sections of this document with a single number. The regex now refuses
to let a span cross another marker, and refuses outright to stamp anything longer
than 120 characters or containing a blank line, because a stamped value is a
number and never a paragraph.

---

## P. Every data source, with its real status

All free. None needs a key or a login.

### Live Indian systems

| source | gives | limits |
|---|---|---|
| **CWC Flood Forecasting System** | 354 stations: official danger, warning and highest-ever levels, live observed level, issued forecasts | Spring-Data JSON "specification" query language; needs a normal User-Agent |
| **C-Flood** | operational inundation **depth**, 30 m, metres, frames every 3 h to 48 h, 173 workspaces back to Sep 2024 | **Mahanadi basin only.** Workspace-scoped WCS; the unscoped endpoint is 404 |
| **NDMA SACHET** | live public alerts, severity, area, centroid, local-language text | severity mixes CAP words with IMD colours |
| **NWDP / NWIC** | CKAN, 76 organisations, 555 APIs | **CWC telemetry covers 15 basins and the Ganga is not one.** A search for "patna" returns 0 |
| **OSDMA shelter locations** | 776 built cyclone and flood shelters across 23 Odisha districts, with coordinates | records sit in an inline JS array that carries a trailing comma, so it is not strict JSON |

### Global open data

| source | gives | notes |
|---|---|---|
| **GloFAS via Open-Meteo** | daily discharge, historical and forecast, 50-member ensemble | no key |
| **Google GRRR** | streamflow reanalysis 1980-2023, reforecast at lead 0-7 d, return periods for 1,031,646 gauges | CC-BY-4.0. Snap to the **largest** outlet within 25 km, never the nearest: the nearest gave the Ganga a 200-year flood of 148 m3/s |
| **Google inundation history** | how often each 128 m pixel was wet 1999-2020 | CC-BY-4.0. Best single predictor measured on Patna |
| **Sentinel-1 RTC** | flood extent | Planetary Computer, anonymous SAS signing |
| **Copernicus GLO-30 / NASADEM / ALOS** | terrain | AWS and Planetary Computer, anonymous |
| **Microsoft Global ML Buildings** | footprints | <!--N:buildings_downloaded-->493,403<!--/N--> in Patna. **Coverage ends at longitude 86.247 in the Mahanadi delta**, where 51% of that AOI's population lives |
| **Google Open Buildings v3** | footprints where Microsoft stops | CC-BY-4.0. One 1.8 GB gzipped tile, streamed and filtered without landing on disk: 159,185 in the Mahanadi AOI against Microsoft's 17,009 |
| **GHS-POP 2020** | population, 100 m | 10-degree tiles, must match the AOI |
| **OpenStreetMap via Overpass** | roads, shelters, places, water | the query must be a `data=` form field; a raw POST returns 406 |

---

## Q. Every mistake found, and what caught it

This is the longest section on purpose. Each of these produced a confident wrong
number at some point.

### Q.1 Silent wrong answers

| problem | how it showed | fix |
|---|---|---|
| Delhi's calibration fitted both dates to the same level at 96-98% area error, then the pipeline carried on | Delhi produced a confident plan from nothing | `hazard.check_fit` rejects any fit worse than 15% and stops |
| OSM inputs were not event-scoped | nothing; Delhi would have been planned on **Patna's roads** | every input is `data/<event>_*` |
| The GHS-POP tile was hardcoded, so Delhi's population read **zero everywhere** | allocation reported "0 of 0" | `hazard.population` derives tiles from the AOI and raises if one is missing |
| The gauge point is hand-typed; Delhi's landed on a tributary and returned **22 m3/s** for the Yamuna in flood | the number was simply small | `hazard.sanity_check_gauge` refuses an order-of-magnitude mismatch against the main stem's 2-year return period |
| `verify.py` read pre-rename files and printed **stale numbers contradicting the dashboard** | only caught by running it | rewritten |
| The river channel counted as flooded land | constant 8.70 m depth over whole "wards" that are the Ganga | `out/<event>_permanent.tif`, masked everywhere downstream |
| The C-Flood cache key omitted the run date | a second run silently reused the first run's rasters | the key includes the date |
| "Permanent water" derived as the intersection of a run's own frames | during a sustained flood every frame is wet, so the flood masks itself out. Hid roughly 500 km2 | permanent water comes from a separate low-flow run |
| `build_plan.py` never received the `WET_M` fix and still counted `depth > 0` | the plan quoted 61,633 people while exposure said 59,622 | one threshold, from `config`, in every stage |
| The radar channel mask missed sandbars that were **dry on the baseline date** | one unit had a median and a maximum depth both exactly 8.70 m | `hazard.widen_channel`, sparing anywhere with buildings |
| Widening `perm` in place **also moved the calibration targets**, since the targets derive from the same array | the fit still reported under 2% error, against targets that had silently grown 26 km2. Exposure jumped 21% | two masks: `perm` is exactly what radar saw and seeds calibration, `channel` is widened and used only downstream |
| The Mahanadi building file covered **35% of its AOI** after the AOI was moved inland | every official shelter read as 8 km from the nearest roof | `fetch_buildings.py` refuses to write a file that does not span the AOI |
| The allocation was keyed by shelter **name**, and Delhi has five separate buildings called "MCD Primary School" | four of the five collapsed into one key. The dict lost entries, so `placed` under-counted, and the dashboard showed all five sites the same six people | the allocator also writes `<event>_allocation_sites.json`, a list carrying the line number in the measured file; anything that counts reads that |
| Two campuses that snap to one road node are filled as one site, but the dashboard divided by one building's roof | "Astipur Middle School, 446 in, capacity 239, **187% full**", which reads as an overloaded shelter when nothing is overloaded | the allocation carries the capacity it actually filled against |
| The dashboard matched allocations back to buildings by rounded coordinates | both sides rounded the same float differently, and **four of Patna's 55 open shelters reported nobody** | matched by line number, which cannot drift |
| The depth grid for the map was decimated by taking every third pixel | the Yamuna through Delhi is two or three pixels wide, so **most of a 12 km2 flood vanished** from the control-room map while the numbers beside it were right | reduced by maximum over each block, which keeps thin channels |
| The Act tab printed `P = 22%` under a caption saying it was computed live | nothing, until somebody read the source | `/api/events/{ev}/forecast` computes it per district from the live ensemble, and the page shows the gauge, its distance and the threshold |
| The published APK asked Android for fine and coarse **location** | nothing; the app never reads GPS. The permission came from an Expo module nothing imported | the module is removed and `aapt2 dump permissions` is the check |
| A contact number was stored as a plain truncated SHA-256 | nothing, and that is the point: ten digits is a small enough space to hash exhaustively in seconds, so the column was reversible by anybody holding the file | HMAC under a per-district secret kept outside the database |
| Delhi's `stage.npy` survived from **before `check_fit` rejected its calibration** | the plan would have used a water level of 203.53 m the project had already refused to believe | a non-stage event says the file is ignored, and takes route existence from its depth raster |

### Q.2 Wrong because of a label or a unit

| problem | fix |
|---|---|
| Google's `lead_time` read as nanoseconds collapsed every column to lead 0, so lead time came out as **0 days** | normalise to whole days explicitly |
| Reanalysis is **left**-labelled and reforecast lead_time is **right**-labelled; adding them gave a **15-day lead from a 7-day model** | the forecast for day D is `issue_time + lead == D + 1 day`, asserted against the dataset's own identity |
| River level (metres) and reservoir inflow (cumecs) tabulated together made a reservoir look **+2,180 above danger** | separate tables, units named |
| Roof area measured in **UTM 45N for every event**; Delhi is ten degrees outside that zone | the zone is derived from the AOI. Delhi's roofs were about 2% too large and nothing looked wrong |
| Missing charset turned degree and superscript characters into mojibake | meta tag plus escapes in JS literals |

### Q.3 Wrong model or wrong assumption

| problem | fix |
|---|---|
| A DEM reads the river **under** a bridge, so every Ganga bridge read as 9 m of water | `structure` from OSM; bridges are neither called open nor flooded, and the dependent population is reported |
| The road graph joined ways only at their endpoints, shattering the network. Largest component held **1.1% of nodes** | split at every shared intersection node. Now 97.8% |
| Shelter capacity assumed by facility type | measured roof area / 3.5 m2. The guesses were wrong both ways |
| Grid-cell dedup missed campuses across cell boundaries | cKDTree 250 m sweep taking the largest, never the sum |
| Pickup-point elevation sampled at the snapped **road node**, which sits higher than the houses | population keeps its own ground elevation. This had under-reported who was wet by about 60% |
| The solver self-check compared **total cost** while the two methods served different populations | compare coverage |
| An AOI's "wettest block" in a delta is **the sea** | moved inland, with the reason in `config` |
| Evacuation cut-off searched with a Dijkstra per hour, 529 times per point | max-bottleneck via Kruskal, one pass, verified against brute force on 301 cases |

### Q.4 Two things saying different things

| problem | fix |
|---|---|
| **Three** copies of a guessed capacity table survived in the router and the map after the allocator switched to measured roof area | a judge clicking a school on the map saw 500 places while the plan behind it had measured 288. All three now read the measured file |
| Per-event paths lived in **three separate dicts** in three scripts that disagreed about which events existed | Mahanadi reached routing and died on a `KeyError`. One set of fields on `config.Event` |
| 17 Delhi place points have no name, and nearest-point assignment labelled the largest flooded unit **"?"** | it reached a drafted SMS as `?: Flood water expected`. `hazard.named_places` drops them |
| `alert.py` printed "evacuation is **NOT** authorised" directly under a table showing it authorised | the line is computed from the same threshold as the table |
| In the frame timeline, "never closes" had the same value as "closes in the final frame" | car, bike and foot reported **identical** populations, which is impossible when their limits differ. "Never" sorts one past the last real frame |
| "Dies in window" merged already-impassable routes with routes that close during it | four columns, with an assertion that they sum to everyone |
| `run.py` passed a depth **path** where a stage event expected a **date** | argv[2] is a raster path in every mode |

---

## R. Results, all three events

### R.1 Patna, 30 September 2019, fitted level

| | |
|---|---|
| people in the water | <!--N:people_wet-->59,495<!--/N--> |
| area | <!--N:flooded_km2-->138<!--/N--> km2 across <!--N:reporting_units-->18<!--/N--> reporting units |
| the plan is built on | <!--N:pickup_people-->59,211<!--/N--> at pickup points |
| placed | <!--N:placed-->47,443<!--/N--> in <!--N:shelters_used-->55<!--/N--> of <!--N:shelters_measured-->90<!--/N--> measured shelters, 72.0 min mean |
| beyond 90 minutes of a shelter with room | <!--N:beyond_reach-->11,177<!--/N--> |
| no road route at any water level | <!--N:no_route-->591<!--/N--> |
| placed only because a bridge is assumed open | <!--N:bridge_dependent-->17,225<!--/N--> |
| useful lead time | 6 days at the 2-year threshold |

### R.2 Delhi, 16 July 2023, observed snapshot

425 people over 3 km2 across 13 units, 350 placed, 3 with no route, 8
bridge-dependent, 929 measured shelters.

The numbers are small and that is the honest consequence of C.4: FwDET depth over
this event is mostly below five centimetres, so very little of the observed
extent clears the flood threshold. Delhi is in the system to show the refusal
working, not to show a big number.

### R.3 Mahanadi, 30 July 2025, CWC's own operational forecast

| | |
|---|---|
| people in the water | 186,908 |
| area | 526 km2, growing from 516 to 530 km2 across the 21-hour window |
| measured shelters | 27, holding **6,374** |
| placed | 4,766 |
| beyond reach | 171,956 |
| no route at all | 10,135 |
| keep a car route through the whole forecast | 96,501 |
| lose a car route inside it | 80,221 |

**The shortfall is the finding.** 186,908 people against 6,374 shelter places is
not a good answer, it is a true one, and it could not be stated at all while the
answer was "OpenStreetMap knows two buildings".

---

## S. What is not done

1. **Urban pluvial flooding is unsolved and unmeasured.** Rajendra Nagar and
   Kankarbagh are the actual 2019 disaster and no open dataset we found sees
   them. This is the honest ceiling on the whole approach.
2. The decision layer is **per-AOI**. The watch layer is national, the plan is
   not.
3. **Delhi has no time dimension.** One snapshot, and every output says so.
4. The citizen page **reads but does not write.** The backend accepts reports,
   help requests and decisions and is tested end to end, but the page is not
   wired to it. Photo reporting, rescue ETA and the volunteer task list are
   served but not reachable from a screen. Frontend work, not a missing
   capability.
5. **The map page has no frame slider.** Mahanadi's data is ready, but the page's
   level arithmetic does not apply to published frames. Listed here rather than
   quietly skipped.
6. **FABDEM untested.** It needs a University of Bristol licence. Three other
   DSMs were substituted and all agree.
7. **Shelter capacity is an upper bound**, per J.1.
8. **The alert probability degrades to a constant offline** and says so, but a
   demo without a network is running on a fallback.

---

## T. How to run everything

```
cd D:\claude\pravaah

.venv\Scripts\python.exe demo.py            # prove the whole thing offline, ~9 s
.venv\Scripts\python.exe run.py patna        # full decision chain, ~310 s
.venv\Scripts\python.exe run.py delhi        # the embanked-river event, ~90 s
.venv\Scripts\python.exe run.py mahanadi 30_07_2025   # a live government forecast, ~30 s

.venv\Scripts\python.exe national.py         # India live, 354 CWC stations
.venv\Scripts\python.exe verify.py           # regenerate every claimed number
.venv\Scripts\python.exe stamp_docs.py --check   # do the documents still agree
.venv\Scripts\python.exe census_check.py     # GHS-POP against the Census of India
.venv\Scripts\python.exe test_timeline.py    # 301-case brute-force check
.venv\Scripts\python.exe test_api.py         # 44 endpoint tests, real DB
.venv\Scripts\python.exe -m uvicorn api:app --port 8010   # the backend
```

Rebuild the pages after a run:

```
.venv\Scripts\python.exe build_map_data.py patna
.venv\Scripts\python.exe build_dashboard.py patna
.venv\Scripts\python.exe build_citizen.py patna
.venv\Scripts\python.exe build_national.py
.venv\Scripts\python.exe build_standalone.py
```

Adding a new event needs `fetch_sar.py`, `fetch_osm.py <event>`,
`fetch_buildings.py <event>`, `build_shelters.py <event>`, an entry in
`pravaah/config.py`, and the right GHS-POP tile in `data/`.

---

## U. File inventory

```
pravaah/            the package
  config.py         per-event AOI, gauge, hazard mode, and every input path
  hazard.py         discharge, calibration, FwDET, population, gauge checks,
                    channel widening, building-source resolution, place names
  network.py        OSM to road graph, carrying ground elevation and structure
  timeline.py       hourly levels, per-edge timeline, cut-offs over a level or
                    over frames, the deadlines reader
  cwc.py            CWC Flood Forecasting System client
  cflood.py         C-Flood client (operational inundation rasters)
  sachet.py         NDMA SACHET client (live public alerts)
  store.py          SQLite: citizen reports, help requests, officer decisions

run.py              the six-stage chain for one event
demo.py             one command that proves the whole thing with no network
verify.py           regenerate every claimed number, offline, writes numbers.json
stamp_docs.py       fill the documents from numbers.json (--check to audit)
census_check.py     GHS-POP against the Census of India, with a boundary check
national.py         India live from CWC
api.py              the backend
test_api.py         44 checks against the real app and a throwaway database
test_timeline.py    the cut-off algorithm against brute force, 301 graphs

the chain:          build_hazard.py build_timeline.py exposure.py
                    build_plan.py allocate.py alert.py
data acquisition:   fetch_sar.py fetch_osm.py fetch_buildings.py
                    fetch_google_buildings.py fetch_osdma.py fetch_water.py
                    fetch_rivers.py build_shelters.py
the pages:          build_map_data.py build_dashboard.py build_national.py
                    build_citizen.py build_standalone.py
the falsification
record:             flood_mask.py hand.py depth.py build_table.py evaluate.py
                    robustness.py dem_ab.py eval_delhi.py eval_buildings.py
                    noisefloor.py calib.py scan_events.py figure.py
                    truth_mask.py prep_grid.py check_urban_blindness.py
                    probe_google.py forecast.py leadtime.py test_google_ih.py
                    run_test.py

REPORT.md           the falsification result in full
DEFENCE.md          hostile questions and honest answers
README.md           the story and the results
ARCHITECTURE.md     the engineering reference
PRAVAAH-SIMPLE.md   the same thing in plain language
out/pravaah_*.html  five self-contained pages
data/               2.0 GB of inputs, not in version control
```

---

## V. The one thing to remember

The most valuable output of this project is a negative result we could have
hidden and did not: **free satellite data maps the river widening, not the
disaster.** Every design decision after that follows from taking it seriously
instead of tuning around it. The system that exists is smaller in scope than the
problem statement asked for, and every place it falls short is written down with
a number attached.
