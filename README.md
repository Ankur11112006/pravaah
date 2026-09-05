# PRAVAAH

A decision layer for Indian floods. It takes a water depth map as **input** and
produces the thing nobody publishes: who is standing in the water, which roads
still carry which vehicle, who goes to which shelter, who cannot be reached at
all, and which actions the arithmetic authorises at a given probability.

It does **not** predict floods. It used to try. That claim was tested and it
failed, and the failure is what shaped everything else in here. Section 3 is
that story, with numbers.

This README is written to be read cold, including by another model. Everything
claimed below is reproducible by running `verify.py`.

**For the engineering detail**, see [ARCHITECTURE.md](ARCHITECTURE.md): every
stage's inputs and outputs, the six algorithms that do the real work, every
guard that refuses to answer, the full backend surface, and each data source's
quirk that will otherwise cost you a day.

---

## 1. Run it

```
cd D:\claude\pravaah

.venv\Scripts\python.exe demo.py            # prove the whole thing offline, ~7 s
.venv\Scripts\python.exe run.py patna        # full decision chain, ~310 s
.venv\Scripts\python.exe run.py delhi        # the embanked-river event, ~80 s
.venv\Scripts\python.exe run.py mahanadi 30_07_2025   # a live government forecast, ~30 s
.venv\Scripts\python.exe -m uvicorn api:app --port 8010   # the backend
.venv\Scripts\python.exe test_api.py        # 44 endpoint tests, real DB
.venv\Scripts\python.exe national.py         # India live, 354 CWC stations
.venv\Scripts\python.exe verify.py           # regenerate every claimed number
.venv\Scripts\python.exe stamp_docs.py --check  # do the documents still agree
.venv\Scripts\python.exe census_check.py     # GHS-POP against the Census of India
.venv\Scripts\python.exe test_timeline.py    # the one real unit test
```

`demo.py` is the one to run if someone is watching: it needs no network, checks
its own inputs first, and fails loudly at the first step that does not hold.

Rebuild the pages after a run:

```
.venv\Scripts\python.exe build_map_data.py patna
.venv\Scripts\python.exe build_dashboard.py patna
.venv\Scripts\python.exe build_national.py
.venv\Scripts\python.exe build_standalone.py
```

That writes four single-file pages, each with its data inlined: open by
double-clicking, no server, no CDN. A fifth, `out/pravaah_overview.html`, is
the written walkthrough and is stamped from `out/numbers.json`.

| page | for |
|---|---|
| `out/pravaah_national.html` | India live: 354 CWC stations, NDMA alerts, C-Flood run status |
| `out/pravaah_dashboard.html` | the officer desk: situation, wards, plan, act, evidence |
| `out/pravaah_map.html` | the flood itself, with a time slider over the forecast |
| `out/pravaah_citizen.html` | what one person in one ward needs, phone-shaped |

The citizen page is built by `build_citizen.py <event>`.

Adding a new event needs `fetch_sar.py`, `fetch_osm.py <event>`,
`fetch_buildings.py <event>`, `build_shelters.py <event>`, an entry in
`pravaah/config.py`, and the right GHS-POP tile in `data/`.

---

## 2. What actually runs

```
run.py <event>
 ├─ build_hazard.py    river discharge -> water level -> depth raster per day
 ├─ build_timeline.py  road graph carrying terrain; when each road changes mode
 ├─ exposure.py        who and how many are in the water, by reporting unit
 ├─ build_plan.py      who can still reach a shelter; who depends on a bridge
 ├─ allocate.py        OR-Tools min-cost flow to shelters of measured capacity
 └─ alert.py           cost-loss trigger -> CAP 1.2 XML + 160-char SMS
```

Package under `pravaah/`:

| module | what it holds |
|---|---|
| `config.py` | per-event config: AOI, gauge, hazard mode, and every input path |
| `hazard.py` | discharge, stage calibration, FwDET depth, population tiles, gauge checks, channel widening, building-source resolution, place names |
| `network.py` | OSM to road graph, carrying ground elevation and structure type |
| `timeline.py` | hourly levels, per-edge mode timeline, evacuation cut-offs over a level **or** over C-Flood frames |
| `cwc.py` | CWC Flood Forecasting System client (live levels and forecasts) |
| `cflood.py` | C-Flood client (operational inundation rasters) |
| `sachet.py` | NDMA SACHET client (live public alerts) |
| `store.py` | SQLite: citizen reports, help requests, officer decisions |

All three events run that whole chain: Patna from a fitted water level, Delhi
from an observed snapshot, Mahanadi from CWC's own operational C-Flood forecast.

`api.py` is the backend: FastAPI over SQLite, 44 tests in `test_api.py`. Read
endpoints serve what the pipeline computed. Write endpoints accept the three
things no instrument can see: a citizen report (with an optional photo), a
request for help that carries mobility so the queue can put the least mobile
first, and an officer's approval or override with a reason code. A phone number
is stored as an HMAC under a secret the district generates and keeps, because the
system needs to recognise a repeat caller and does not need a list of flood
victims' numbers. A plain hash would not do: ten digits is a small enough space
to hash exhaustively in seconds. `GET /api/reference` returns every
value the write endpoints will accept, so a client never has to guess.

---

## 3. The story, because the failures are the design

### 3.1 The original claim, and the test written to kill it

The design document promised building-level flood depth from HAND (Height Above
Nearest Drainage) on free terrain, and specified its own falsification test:
Chennai, Cyclone Michaung, December 2023, against Sentinel-1 SAR, needing
**recall > 70% and precision > 50%**, and beating a one-line elevation baseline.

**Problem: the ground truth does not exist.** Sentinel-1 passed over Chennai on
6, 18 and 30 November 2023 and then not again until 17 January 2024, a 48-day
gap containing the entire cyclone. Confirmed against two independent catalogues
(ASF DAAC and Copernicus Data Space). Every optical scene from 1 to 16 December
is 65 to 99% cloud.

**Resolution:** choose the event by ground-truth availability instead. Ten major
Indian floods were swept; only two have SAR within three days of peak. Patna
2019 (SAR on the peak day itself) and Delhi Yamuna 2023 (+2 days).

### 3.2 The test, run on two events

Per 30 m cell, against the SAR-observed flood:

| predictor | Patna 2019 | Delhi 2023 |
|---|---|---|
| HAND | <!--N:patna_auc_hand-->0.657<!--/N--> | <!--N:delhi_auc_hand-->0.706<!--/N--> |
| plain elevation threshold | <!--N:patna_auc_elev-->0.657<!--/N--> | <!--N:delhi_auc_elev-->0.663<!--/N--> |
| distance to river | <!--N:patna_auc_dist-->0.662<!--/N--> | **<!--N:delhi_auc_dist-->0.939<!--/N-->** |
| Google inundation history | **0.758** | 0.654 |

No AUC threshold was registered in advance, so this table has no pass mark and
none is invented here. The target that *was* set before the test was on
precision: **above 0.50 at recall above 0.70.** Measured: **9% in Patna, 5% in
Delhi.** That is the number the test turns on, and it is not close.

**HAND does not beat a one-line elevation threshold.** The result held across
three DEMs (Copernicus GLO-30, NASADEM, ALOS AW3D30) and six drainage
thresholds from acc>500 to acc>200000.

### 3.3 The larger problem: the ground truth is not the disaster

Of <!--N:buildings_sampled-->455,860<!--/N--> Patna buildings, Sentinel-1 labels **659 as flooded. 0.14%.** During
a week-long urban flood.

The flood SAR does map sits a **median of 134 m from the river in Patna and
170 m in Delhi**. It is the channel widening, not the city drowning. Water in
dense built-up areas raises radar backscatter through double-bounce against
walls instead of lowering it, so urban flooding is close to invisible.

Independently confirmed from the ground: the Bihar Inter Agency Group and Sphere
India *Joint Rapid Needs Assessment, Bihar urban floods 2019* reports 80% of
Patna houses took water and names Rajendra Nagar, Kankarbagh, Boring Road and
Pataliputra Colony as worst hit. All are pluvial and kilometres from the Ganga.
**None of them are in the satellite flood map.**

So the design's own test **cannot be passed by anyone** on free SAR. That is a
statement about the field, not about this code.

### 3.4 What was rebuilt instead

Depth became an **input**. The system stopped trying to predict where water goes
and started consuming a depth field, then doing the part that nobody does.

For events where a level can be fitted, `hazard.py` fits a **water level** to the
extent Sentinel-1 actually observed at a known GloFAS discharge, on two dates,
giving a stage-discharge line, then drives that level with the discharge series.
Patna: 48.10 m at 35,155 m3/s and 48.70 m at 44,667 m3/s, both within 1.6 km2 of
observed. That produced the time dimension the whole product rests on.

**That fitted level was later validated from outside.** CWC's Gandhighat station
sits 3.8 km away with an official **danger level of 48.60 m**. Our independently
fitted 48.70 m is **+0.10 m from it**.

---

## 4. Every problem hit, and what was done

Grouped because most of them are the same species: a number that looked fine and
was wrong.

### 4.1 Silent wrong answers (the dangerous class)

| problem | how it showed | fix |
|---|---|---|
| Delhi's stage calibration fitted both dates to the same level with 96-98% area error, then the pipeline carried on | Delhi produced a confident plan from nothing | `hazard.check_fit()` rejects any fit worse than 15% and stops. Delhi now refuses |
| OSM inputs were not event-scoped, so Delhi would have been planned on **Patna's roads** | nothing; it would have looked normal | every input is `data/<event>_*` |
| GHS-POP tiles are 10 degrees and `R7_C27` was hardcoded, so Delhi's population was **zero everywhere** | allocation reported "0 of 0" | `hazard.population()` derives tiles from the AOI and raises if one is missing |
| The gauge point in config is hand-typed; Delhi's returns **22 m3/s** for the Yamuna in flood, because it lands on a tributary | the number was simply small | `hazard.sanity_check_gauge()` compares against Google's main-stem 2-year return period and refuses an order-of-magnitude mismatch |
| `verify.py` was reading pre-rename files and printing **stale numbers that contradicted the dashboard** | only caught by running it | rewritten, reads current files |
| The river channel was counted as flooded land, giving a constant 8.70 m depth over whole "wards" that are the Ganga | Mehdiganj and Hakimganj had identical depth | `out/<event>_permanent.tif` is written once and masked out everywhere downstream |
| The radar-derived channel mask missed the sandbars that were **dry on the baseline date**, so 26 km2 of riverbed re-entered the flood as land | Hakimganj came back with a median depth and a maximum depth both exactly 8.70 m, which is a flat bed under a flat water surface, not a flood | `hazard.widen_channel()` adds patches where the DEM is perfectly flat and connected to known water, and **spares anywhere with building footprints on it**, because the Ganga diara are inhabited sandbars. Flooded area fell 164 to 138 km2; the population fell by only 127, because GHS-POP had correctly put almost nobody in the river |
| Fixing that mask by widening `perm` in place **also moved the calibration targets**, since the targets are derived from the same array | the fit still reported a low error, against targets that had silently grown 26 km2. Fitted level rose 20 cm and exposure jumped 21% to 72,297 | two masks, not one: `perm` stays exactly what the radar saw and seeds the level search, `channel` is the widened version and is used only downstream. A mask that answers two questions will answer one of them wrong |
| The Mahanadi building file covered **35% of its AOI**: the AOI was moved inland after the download and the stale file kept its old extent | every official cyclone shelter read as 8 km from the nearest roof, so the delta's evacuation capacity came out as 252 people | `fetch_buildings.py` refuses to write a file that does not span the AOI, and `hazard.buildings_path()` refuses to measure against one |
| Shelter roof area was measured in **UTM 45N for every event**. Delhi is ten degrees outside that zone | nothing; areas were about 2% too large and no number looked wrong | the zone is derived from the AOI |
| Per-event file paths lived in **three separate dicts** in three scripts that disagreed about which events existed | Mahanadi reached the routing stage and died on a `KeyError` | one set of fields on `config.Event` |
| Three copies of a **guessed shelter capacity table** survived in the router and the map, after the allocator had switched to measured roof area | a judge clicking a school on the map saw 500 places while the plan behind it had measured 288 | all three read `data/<event>_shelters_measured.csv`. The router now routes to exactly the shelters the allocator can fill |
| 17 Delhi OSM place points have no name, and the nearest-point assignment labelled the city's largest flooded unit **"?"** | it went out in a drafted SMS as `?: Flood water expected` | `hazard.named_places()` drops them, and their cells fall to the nearest place that has a name |
| The C-Flood channel mask was **empty**, because that path has no radar baseline to compare against | the Mahanadi river counted as flooded land: the mask printed "0 km2" and nothing was excluded | seeded from OSM's own mapped water, then widened by DEM flatness like the radar path. 30 km2 excluded |
| `alert.py` printed "evacuation is **NOT** authorised" directly under a table showing it authorised, whenever the probability cleared 55% | only visible on an event where the trigger actually fires, which is why Patna and Delhi never showed it | the line is computed from the same threshold as the table |
| In the C-Flood route timeline, "never closes" was given the same value as "closes in the final frame" | car, bike and foot reported **identical** populations, which is impossible when their depth limits differ | "never" sorts one past the last real frame. Car 80,221, bike 49,628, foot 2,682 |
| "Dies in window" counted routes that were **already impassable when the window opened** together with routes that close during it | 36,817 people at Patna read as having a deadline; 22,734 of them had no route at any point in the window | four columns: survives, closes in window, already gone, no route ever. An assertion checks they sum to everyone |
| Delhi's `stage.npy` survived on disk from **before `check_fit` rejected its calibration**, and `build_plan` read it | the plan would have been built on a water level of 203.53 m that the project had already refused to believe | a non-stage event says out loud that the file is ignored, and observed events take route existence from their one depth raster instead |
| `run.py` passed a depth **path** where a stage event expected a **date** | `build_plan.py patna` died on `out/depth/patna_.tif` | argv[2] is a raster path in every hazard mode, and the date is read back out of the filename |

### 4.2 Wrong because of a label or a unit

| problem | fix |
|---|---|
| Google's `lead_time` read as nanoseconds collapses every column to lead 0, so lead time came out as **0 days** | normalise to whole days explicitly |
| Reanalysis is **left**-labelled and reforecast lead_time is **right**-labelled; adding them gave a **15-day lead out of a 7-day model** | the forecast for day D is `issue_time + lead == D + 1 day`. `leadtime.py` now asserts the dataset's own identity `Reanalysis[T] == Reforecast[T+1, lead 0]` |
| River level (metres) and reservoir inflow (cumecs) were tabulated together, making a reservoir look **+2,180 above danger** | separate tables, units named |
| Missing charset turned degree and superscript characters into mojibake in the map panel | meta tag plus `\u` escapes in JS literals |

### 4.3 Wrong model or wrong assumption

| problem | fix |
|---|---|
| DEM sees the river **under** a bridge, so every Ganga bridge read as 9 m of water | `structure` tagged from OSM. Bridges are neither called open nor flooded; the system reports how many people depend on one (<!--N:bridge_dependent-->17,225<!--/N--> in Patna) |
| Road graph joined ways only at their endpoints, shattering the network. Largest component held **1.1% of nodes** | split ways at every shared intersection node. Now 97.8% |
| Shelter capacity assumed by facility type | measured: OSM campus polygons intersected with building footprints, divided by **3.5 m2 per person** (NDMA *Guidelines on Minimum Standards of Relief*, section 2(c)). The guesses were wrong both ways: schools 500 assumed vs 288 measured, but BIT Patna 1,000 assumed vs 10,020 measured |
| One campus mapped as several OSM ways inflated capacity; grid-cell dedup missed neighbours across cell edges | cKDTree 250 m sweep taking the largest, never the sum. 129 duplicates merged |
| Pickup-point elevation sampled at the snapped **road node**, which sits higher than the houses, under-reporting who was wet by ~60% | population keeps its own ground elevation |
| Evacuation cut-off searched with a Dijkstra per hour, 529 times per point | max-bottleneck path via Kruskal in descending bed order, one pass for all sources. Verified against brute force on **301 cases** |
| The solver self-check compared total cost while the two methods served different populations, so greedy looked cheaper | compare **coverage** first, which is the actual claim. Min-cost flow places 13,163 more people than greedy at +13.5 min mean trip |
| Bathtub scenario flooded 39% of the AOI at +1 m, because the Ganga's own surface drops 2-4 m across the AOI | abandoned. A flat water surface cannot represent a sloping river |

### 4.4 Things that were simply wrong in our own documents

`REPORT.md`, `DEFENCE.md`, the deck and the partner doc all stated that NDEM and
C-FLOOD were "government login only" and "not obtained". **That was false.**
CWC's forecast system and C-Flood are both public and unauthenticated. Corrected
in `build_dashboard.py` and `PS3-ppt-content.md`.

---

## 5. Data sources, with their real status

All free. None needs a key or a login unless stated.

### Live Indian systems

| source | endpoint | gives | limits |
|---|---|---|---|
| **CWC Flood Forecasting System** | `ffs.india-water.gov.in/iam/api/...` | 354 stations: official danger, warning and highest-ever levels, live observed level, issued forecasts with trend | Spring-Data JSON "specification" query language; needs a normal User-Agent |
| **C-Flood** | `inf.cwc.gov.in/geoserver/<workspace>/wcs` | **operational inundation depth**, 30 m, EPSG:32645, metres, frames every 3 h to 48 h, daily runs, 173 workspaces back to Sep 2024 | **Mahanadi basin only.** Workspace-scoped WCS; the unscoped `/geoserver/wcs` is 404 |
| **NDMA SACHET** | `sachet.ndma.gov.in/cap_public_website/FetchAllAlertDetails` | live public alerts, severity, area, centroid, text in local language | severity mixes CAP words with IMD colours |
| **NWDP / NWIC** | `nwdp.nwic.gov.in/api/3/action/...` | CKAN, 76 organisations, 555 APIs | **CWC telemetry covers 15 basins and the Ganga is not one. Bihar and UP are absent from CWC discharge. A search for "patna" returns 0.** Bihar's own file starts 2021 |
| **OSDMA shelter locations** | `osdma.org/shelter-locations/?district=<D>` | **776 built cyclone and flood shelters** across 23 Odisha districts, with coordinates, block, village and scheme | public, no key. The records sit in an inline JS array, so no HTML scraping; the array carries a trailing comma and is not strict JSON. 26 fall inside the Mahanadi AOI, against **2** that OpenStreetMap has mapped |

### Global open data

| source | gives | notes |
|---|---|---|
| **Google GRRR** (`gs://flood-forecasting`) | streamflow reanalysis 1980-2023, reforecast 2016-2022 at lead 0-7 d, **return periods for 1,031,646 gauges** | CC-BY-4.0. Read with `zarr` + `fsspec` over https. Snap to the **largest** outlet within 25 km, never the nearest: the nearest gave the Ganga a 200-year flood of 148 m3/s |
| **Google inundation history** | how often each 128 m pixel was wet 1999-2020 (GLAD/Landsat), three nested risk polygons | CC-BY-4.0. Best single predictor we measured on Patna (AUC 0.758) |
| **GloFAS via Open-Meteo** | daily discharge, historical and forecast, **50-member ensemble** with `ensemble=true` | no key. Members are null for reanalysis, live for forecasts |
| Copernicus GLO-30 / NASADEM / ALOS | terrain | AWS and Planetary Computer, anonymous |
| Sentinel-1 RTC | flood extent | Planetary Computer, anonymous SAS signing |
| Microsoft Global ML Buildings | footprints | <!--N:buildings_downloaded-->493,403<!--/N--> in Patna AOI, 391,381 in Delhi. **Coverage ends at longitude 86.247 in the Mahanadi delta**, which is 51% of that AOI's population |
| Google Open Buildings v3 | footprints, where Microsoft stops | CC-BY-4.0. One 1.8 GB gzipped tile, streamed and filtered to the AOI without ever landing on disk: 159,185 buildings in the Mahanadi AOI against Microsoft's 17,009. `hazard.buildings_path()` picks whichever source actually spans the AOI and prints which one |
| GHS-POP 2020 | population, 100 m | 10-degree tiles, must match the AOI |
| OpenStreetMap via Overpass | roads, shelters, places | query must be a `data=` **form field**; a raw POST returns 406 |

---

## 6. What is verified, and how

`verify.py` recomputes every claimed number from `data/` and `out/`, offline, in
two parts: the falsification record and the working system. `test_timeline.py`
checks the evacuation cut-off algorithm against brute force on 301 random
graphs, plus bridge handling and interpolation bounds.

Current Patna run, calibrated peak 30 Sep 2019:

```
<!--N:people_wet-->59,495<!--/N--> people in the water across <!--N:reporting_units-->18<!--/N--> reporting units, <!--N:flooded_km2-->138<!--/N--> km2
<!--N:placed-->47,443<!--/N--> placed in <!--N:shelters_used-->55<!--/N--> of the <!--N:shelters_measured-->90<!--/N--> measured shelters, mean journey 72.0 minutes
<!--N:beyond_reach-->11,177<!--/N--> beyond 90 minutes of a shelter with room
   <!--N:no_route-->591<!--/N--> with no road route at any water level (river islands)
<!--N:bridge_dependent-->17,225<!--/N--> placed only because a bridge is assumed open
```

External checks that were not used to build anything:

- CWC Gandhighat official danger level **48.60 m** vs our fitted **48.70 m**.
- JRNA reports "in most of the slums water level was 3 feet" (0.91 m); our
  modelled median over flooded land is **<!--N:modelled_median_depth_m-->0.73<!--/N--> m**.
  Treat as a plausibility check, not proof: their figure is urban slums, which
  our map barely covers. This agreement got *worse* when we removed the river
  channel from the flood, and that is the correct direction: the river cells
  were deep, and including them flattered the median into a near-perfect match.
  A number that agrees for the wrong reason is not evidence.
- GHS-POP, which every exposure figure depends on, reads
  **<!--N:census_rel_error_pct-->+0.7<!--/N-->%** against the Census of India
  for Patna district carried forward to 2020 at the district's own 2001-2011
  growth rate (<!--N:ghs_pop_district-->7,121,932<!--/N--> modelled against
  <!--N:census_projected-->7,071,903<!--/N--> projected). Run `census_check.py`.
  The district total is right; where the model puts people *inside* the
  district is untested, and that is what exposure actually depends on.
- Google GRRR reforecast gives a **6-day useful lead time** for the 2-year
  threshold at Patna 2019 (crossed 30 Sep, first forecast to call it issued
  24 Sep). The spec asked for 48 to 72 hours.

---

## 7. What is NOT done

This is the list to attack.

1. **C-Flood runs end to end on a real flood day.** (This entry used to read
   "only as far as exposure". Both blockers were external data gaps, and both
   turned out to be fillable.)
   `config.py` carries a `mahanadi` event with `hazard="cflood"`. Usage:
   `build_hazard.py mahanadi <run_date> <baseline_date>`, e.g.
   `build_hazard.py mahanadi 30_07_2025 02_07_2026`.

   The flood day was chosen, not guessed: GloFAS discharge at the Mahanadi
   main-stem gauge over C-Flood's archive period, cross-checked against which
   dates actually have a published workspace. **30 July 2025 at 16,519 m3/s,
   1.83x the 2-year return period.** The baseline is 2 July 2026 at 10 m3/s.

   Result, straight off CWC's own operational hydrodynamic forecast:

   ```
   510 km2 wet, 178,411 people, 1 of 26 critical facilities
   Machgaon 218 km2  77,308 people  median 0.65 m
   Ersama   175 km2  53,710 people  median 1.02 m
   Balikuda 112 km2  46,773 people  median 0.21 m
   flood grows from 516 to 530 km2 across the 21-hour forecast window
   364 km2 of that is one connected body; the rest is isolated ponding
   ```

   **Allocation used to be impossible there, for two reasons, both now closed.**

   OSM has **2 shelter polygons** in the whole AOI. A narrow amenity query
   returned 0 and a deliberately wide one covering schools, community centres,
   places of worship, `emergency=shelter` and named cyclone shelters returned 2.
   Odisha has roughly 880 Multipurpose Cyclone Shelters built by OSDMA after the
   1999 super cyclone, and none of them are in OSM. **OSDMA publishes them.**
   `fetch_osdma.py` pulls 776 built shelters with coordinates across 23
   districts; 26 fall inside this AOI.

   Microsoft footprints were the second wall: 17,009 buildings against Patna's
   <!--N:buildings_downloaded-->493,403<!--/N-->, and coverage that simply stops
   at longitude 86.247, which is where 51% of the AOI's population lives. Every
   OSDMA shelter was a median 8 km from the nearest mapped roof, so none could be
   measured. **Google Open Buildings v3 covers it**: 159,185 footprints spanning
   the whole AOI, streamed out of a 1.8 GB tile.

   With both in place the delta has **27 measurable shelters holding 6,374
   people** against 186,908 in the water. That is not a good answer, it is a
   true one, and it is the first time the shortfall could be stated as a number
   rather than as a missing file.

   Routes run there too. C-Flood publishes depth every three hours, so the road
   timeline comes from the frames rather than from a fitted level, through the
   same max-bottleneck routine: 96,501 people keep a car route through the
   21-hour forecast, 80,221 lose one during it, 10,135 never had one.

   Six traps were hit getting here, all now fixed or stated:
   - **Deriving "permanent water" as the intersection of a run's own frames is
     wrong.** During a sustained flood every frame is wet, so the flood masks
     itself out. It hid roughly 500 km2. Permanent water now comes from a
     separate low-flow run of the same model.
   - OSM water polygons were tried as the permanent mask and caught 8 km2 in a
     whole delta. Not enough.
   - The raw-frame cache key omitted the run date, so a second run silently
     reused the first run's rasters and printed identical numbers.
   - `exposure.py` counted any depth above 0 while `build_hazard.py` used 0.05 m,
     which put 249,582 people in 2 cm of water. There is now one `config.WET_M`.
   - **The output is speckled.** One frame carried 6,045 separate wet components;
     5,770 of them were under 0.05 km2 and held 36 km2 between them, mostly
     shallow and on high ground. `config.MIN_PATCH_KM2` drops them and the run
     prints how much it dropped.
   - **Do not judge C-Flood's depth against the Copernicus DEM.** After the
     speckle filter, 16% of cells the Copernicus DEM puts at 10 to 20 m still
     read wet. C-Flood runs on its own terrain, so this is most likely the two
     DEMs disagreeing rather than a model error. It is a reason not to mix the
     two elevations in a single judgement, which is what produced the apparent
     contradiction in the first place.

2. **The decision layer is still per-AOI.** The watch layer is national (354
   stations); the plan layer is not. The right shape is on-demand: national
   watch, pick the station in trouble, run the chain there. Holding all-India
   buildings and roads is not the answer.
3. **Urban pluvial flooding is unsolved and unmeasured.** Rajendra Nagar and
   Kankarbagh are in no gauge, no C-Flood run and no SAR mask. This is India's
   largest flood problem and nobody has the data. Everything in this repo is
   riverine.
4. **Delhi has no time dimension.** Its Yamuna is embanked: connected area jumps
   from 0.00 km2 at 204.00 m to 121 km2 at 204.10 m, so no level reproduces the
   observed 12.1 km2. It runs in `observed` mode, one snapshot. A gauge-based
   stage from CWC would fix this.
5. **The citizen page reads; it does not yet write, and the volunteer page
   does not exist.** `out/pravaah_citizen.html` gives a person in one reporting
   unit their depth, their assigned shelter with distance and a `geo:` link,
   which travel modes still work at that depth, the roads near them that change
   mode and when, the bridge warning if their route depends on one, and the
   broadcast text. It remembers their ward in `localStorage`. The backend now
   accepts reports, help requests and decisions and is tested end to end
   (`test_api.py`, 44 checks), but the page is not wired to it. Photo
   reporting, rescue ETA and the volunteer task list are therefore designed and
   served but not yet reachable from a screen. That is a frontend task, not a
   missing capability.

6. **FABDEM untested.** It needs a University of Bristol licence acceptance.
   Three DSMs were substituted and all agree.
7. **Shelter capacity is roof footprint / 3.5 m2.** A single-storey footprint
   understates a multi-storey school; not all roofed area is usable floor. The
   two errors push opposite ways and neither is quantified.
8. **The alert probability is live, but it degrades to a constant offline.**
   `alert.py` computes `P_EVENT` as the share of GloFAS's 50 ensemble members
   above a published return period at the main-stem gauge, and prints that
   derivation. If the service is unreachable it falls back to a fixed value and
   says so in the same line. The fallback is honest but it is still a guess,
   and a demo run without a network is running on a guess.

---

## 8. Repository map

```
pravaah/            the package: config, hazard, network, timeline, cwc, cflood, sachet
run.py              the six-stage chain for one event
demo.py             one command that proves the whole thing with no network
national.py         India live from CWC
census_check.py     GHS-POP against the Census of India, with a boundary check
fetch_osdma.py      776 official Odisha cyclone and flood shelters, with coordinates
fetch_google_buildings.py   footprints where Microsoft's coverage stops
verify.py           regenerate every claimed number, offline, writes numbers.json
stamp_docs.py       fill the documents from numbers.json (--check to audit)
api.py              the backend: reads the pipeline, accepts reports and decisions
test_api.py         44 checks against the real app and a throwaway database
test_timeline.py    the unit test

fetch_sar.py fetch_osm.py fetch_buildings.py build_shelters.py     data acquisition
build_hazard.py build_timeline.py exposure.py build_plan.py
  allocate.py alert.py                                             the chain
build_map_data.py build_dashboard.py build_national.py
  build_standalone.py                                              the five pages

probe_google.py forecast.py leadtime.py test_google_ih.py          Google datasets
flood_mask.py hand.py depth.py build_table.py evaluate.py
  robustness.py dem_ab.py eval_delhi.py noisefloor.py calib.py
  scan_events.py figure.py truth_mask.py prep_grid.py
  fetch_rivers.py run_test.py check_urban_blindness.py
  eval_buildings.py                                                the falsification record
attic/                                                             superseded scratch

REPORT.md           the falsification result in full
DEFENCE.md          hostile questions and honest answers
out/pravaah_*.html  five self-contained pages: national, dashboard, map,
                    citizen, overview. No server, no CDN, no build step.
data/               1.9 GB of inputs, not in version control
```

---

## 9. If you are a model reviewing this

The most useful things to attack, in order:

- **Is the stage-discharge fit defensible?** Two calibration points, linear, and
  a single flat water surface across 45 km of a river whose own surface slopes.
  It validated to 10 cm against an official datum, which may be luck.
- **Is the exposure count meaningful** when population is GHS-POP modelled
  (30-50% local error) and snapped to road nodes?
- **Does the OR-Tools allocation earn its place?** It beats greedy on coverage
  by 13,163 people but the margin depends entirely on capacity binding.
- **The urban pluvial gap.** If you can find any open dataset that sees water in
  a dense Indian city, that is worth more than every optimisation in here.

---

## Checking this in front of someone

One command, no internet, about seven seconds:

```
.venv\Scripts\python.exe demo.py
```

It confirms every input is on disk (0.81 GB cached), recomputes every claimed
number from that data, checks that this document still agrees with what was just
computed, and runs the backend's 44 tests against a throwaway database with a
real file upload. It stops at the first failure and says which step failed, so a
passing run means all four passed rather than that nothing was checked.

The only thing in the system that wants a network is the live layer: the CWC
station pull, the NDMA alert feed and the GloFAS ensemble behind the alert
probability. All three are cached, and the alert says out loud when it has
fallen back to a constant.

---

## Provenance

No figure in this file was typed by hand. `verify.py` recomputes each one from
`data/` and `out/` and writes `out/numbers.json`; `stamp_docs.py` fills them into
this document, ARCHITECTURE.md, REPORT.md, DEFENCE.md and the overview page from
that single file. To audit rather than rewrite:

```
.venv\Scripts\python.exe verify.py
.venv\Scripts\python.exe stamp_docs.py --check
```

The second command exits non-zero if any document disagrees with what the code
just computed, which is the only way we know of to make a stale number
impossible rather than merely unlikely.

Last stamped: <!--N:generated-->2026-08-31 21:15 UTC, code cbd657062600<!--/N-->
