# PRAVAAH — content for the Decode SIH 2026 Finals deck

Written against the template's 10 slides. This is **content only**, not a deck.
Every number below is stamped from `out/numbers.json` and reproducible with
`verify.py`; nothing here is rounded up or guessed. Where a figure is live it
says so, because a live figure will be different on stage than it is here.

Two things to decide before you paste anything:

- **How much text per slide.** Each section below gives you a *spoken* version
  (what you say) and a *slide* version (what goes on the wall). Put the slide
  version on the slide. The wall is not a document.
- **The one risk.** Slide 6 contains a negative result we found and published.
  Say it out loud yourselves, early. If a judge finds it after you have claimed
  otherwise, you lose the room; if you open with it, it is the most credible
  thing in the deck. Full reasoning at the end, under "How to handle the hard
  question".

---

## Every visual, and which slide it belongs on

All of these already exist. Diagrams are in `out/figs/`, phone screenshots in
`out/figs/shots/`. Every diagram is 16 inches wide at 200 dpi, drawn in the
template's own palette (cyan `#00AEEF`, slate `#303642`, Calibri), so dropping
them in full width needs no recolouring and no scaling tricks.

Regenerate them all any time with:

    .venv/Scripts/python.exe make_slide_figs.py

| slide | visual | file |
|---|---|---|
| 2 · Problem | the gap, as a picture | `figs/fig1_problem.png` |
| 3 · Solution | six-stage pipeline flow | `figs/fig3_pipeline.png` |
| **3b · USP (extra slide)** | five things nobody else does | `figs/fig5_usp.png` |
| 4 · Prototype & demo | input → process → output → benefit | `figs/fig6_demoflow.png` |
| 4 · Prototype & demo | **dashboard screenshots** (yours) | see slots below |
| 4 · Prototype & demo | phone screenshots | `figs/shots/app_*.png` |
| 5 · Tech stack | architecture block diagram | `figs/fig2_architecture.png` |
| 6 · Validation | the falsification result, charted | `figs/fig4_validation.png` |

### The extra slide

The template ships **ten** slides and the tenth is empty. Use it, but not at the
end: duplicate it and put it **straight after Slide 3**, as the USP slide. The
order that works is *problem → what we built → why nobody else has it → proof it
runs*. Leaving the USP to the end means the judges have already decided.

### The screenshots, all captured and on disk

Everything is in `out/figs/shots/`. Nothing here is left for you to take.

The dashboard shots were captured headlessly straight from the running backend,
at 1760 x 990, using the deep link the page now supports:

    chrome --headless=new --window-size=1760,990 --virtual-time-budget=22000            --screenshot=dash_1_india_watch.png "http://127.0.0.1:8010/?view=watch"

Retake any of them the morning of the finals, so the live numbers are that day's.
Swap `?view=` for `plan`, `act`, `reports`, `when`, `where` or `log`, and add
`&event=mahanadi` or `&event=delhi` for another district.

| file | what it shows | use it to say |
|---|---|---|
| `dash_1_india_watch.png` | India, all 355 CWC stations, red cluster on the Ganga, 23 named stations above danger in the table | "this is live. Check any of these against the CWC site on your phone." |
| `dash_2_situation.png` | the measured gauge above the modelled plan, flood layer on a real basemap | "measurement on top, model below, and we never mix them" |
| `dash_3_act.png` | live probability, its gauge and threshold, the two-clocks warning, severity by return period, cost-loss ladder | "nobody typed this number, and the page says which clock it is on" |
| `dash_4_reports.png` | the citizen queue with each report's distance from the district | "reports come back, from anywhere in India" |

Phone screenshots are already captured and in `out/figs/shots/`:

| file | what it shows | use it to say |
|---|---|---|
| `app_1_live_anywhere.png` | Guwahati: live Brahmaputra gauge, danger mark, read time, four Assam SDMA alerts | "this works 1,000 km from anywhere we modelled" |
| `app_2_search_any_place.png` | typing "Patna", real places returned, the one with a plan tagged | "no fixed list. Anywhere in India." |
| `app_3_no_plan_honest.png` | the "what this place has / what it does not" card | "it tells you where its knowledge stops" |
| `app_4_map_saved.png` | "Map saved, 5.5 MB, works with no network" | "saved before you need it" |
| `app_5_offline_map.png` | the full map drawn with aeroplane mode on | "this is the phone with the radio off" |
| `app_6_failure_explains.png` | "Cannot reach the district server", with the address tried | "when it fails it says why" |

If you only have room for two phone screenshots, use `app_1` and `app_5`.

---

## Slide 1 — Title

| field | what to put |
|---|---|
| PROJECT NAME | **PRAVAAH** (प्रवाह) |
| One line under it | Flood decision support for a district, built only on data anyone can fetch today |
| PRESENTED BY | your team name |
| Problem Statement ID | **PS3** — Disaster Response Intelligence Platform for Flood Prediction, Emergency Response |

Optional subtitle if the template has room, and it is worth the space:

> We ran the test that would have killed this project before we built it. It
> failed. This deck is what we built after that.

---

## Slide 2 — Problem Statement

> **Visual for this slide: `figs/fig1_problem.png`.**  It says the whole slide
> without text: what India already has on the left, the gap in the middle, what a
> district must decide on the right, and the two findings underneath.  Put it
> across the full width and keep only the three bold lines below as bullets.

### Slide version

**Problem:** PS3, Disaster Response Intelligence Platform for Flood Prediction,
Emergency Response.

**Who faces it**
- District administrations who have to order an evacuation, and are given a
  river level in metres and nothing that converts it into people, roads or beds.
- People in the flood plain, who receive an alert naming a district and a
  severity, and cannot tell whether it means *them*.
- India runs one of the world's largest flood forecasting networks. CWC operates
  **354 forecast stations** with official danger levels, live and public. What
  does not exist in between is the layer that turns "the river is 1.8 m over its
  danger mark" into "these 59,495 people are in the water, this road stops
  carrying a car at 06:00, and this school has room for 288."

**The gap in the current system, in three specifics we hit ourselves**
1. **The gauge is not the ward.** CWC publishes a level at a point. Nothing
   public converts it into who is affected, per settlement.
2. **The national data portal does not cover the river we needed.** NWIC/NWDP
   (CKAN, 76 organisations, 555 APIs) carries CWC telemetry for **15 basins, and
   the Ganga is not one of them.** A search for "patna" returns **0** results.
   We did not read that in a paper. We queried it.
3. **Operational depth exists for exactly one basin.** C-Flood publishes real
   inundation depth at 30 m, in metres, every 3 hours to 48 hours ahead, with
   173 workspaces back to Sep 2024 — **for the Mahanadi only.** Everywhere else
   in India, depth has to be inferred.

**What validates the need**
- On the day we are presenting, our own dashboard is reading the live CWC feed
  and **23 stations across India are above their own official danger level**,
  with the Ganga at Gandhighat 1.80 m over. That number is live; check it on
  stage.
- Patna 2019: the disaster was in Rajendra Nagar and Kankarbagh, kilometres from
  the Ganga. **Neither appears in any satellite flood map of that event,
  including ours.** The people who were actually in the water were invisible to
  the instruments meant to see them.

### Spoken version

"India already forecasts floods well. What it does not have is the step after
the forecast. A District Magistrate gets a number in metres. What they need is
how many people, which roads, which shelter, and by when. That step is missing,
and we can show you three places where we went looking for it in the official
data and it was not there."

---

## Slide 3 — Proposed Solution

> **Visual for this slide: `figs/fig3_pipeline.png`.**  Six stages left to right
> with the real output number under each.  Run it across the bottom half and put
> the 120-word description and the four features above it.

### What are you building (120 words)

PRAVAAH is a district flood decision layer with two faces: a control-room
dashboard for the officer and a citizen app for the person in the flood plain,
both served by one backend a district can run on a single laptop.

It takes the public river feed and converts it into decisions. It fits a water
**level** to a flood extent a satellite actually measured, drives that level with
public discharge forecasts, and from it computes who is in the water, the hour
each road stops carrying each vehicle, which shelter has measured room, and what
the officer is authorised to do at today's probability. Everything runs on data
that is free, keyless and fetchable today. Where the system cannot know
something, it says so on the screen rather than filling the gap.

### The 4 key features

**1. A plan, not a forecast.** Six stages run end to end in 121 seconds: hazard →
exposure → routing → allocation → timeline → decision. Output for Patna:
**59,495 people in the water, 47,443 placed in 55 shelters, 11,177 beyond 90
minutes' reach, 591 with no road route at all, 17,225 who reach a shelter only
across a bridge.** The arithmetic closes: placed + beyond reach + no route =
people planned, and the dashboard shows that check in its top bar.

**2. Roads with deadlines, split four ways.** For each mode we report *holds*,
*closes*, and *already gone*. For a car in Patna: 21,803 hold, 14,083 have a
closing time you can still work to, **22,734 were already impassable when the
window opened.** Merging "closes" with "gone" made 22,734 people look like they
had time. That split is the difference between a plan and a wish.

**3. Shelters with measured capacity.** Not a claimed number. Roof footprint from
building data, divided by 3.5 m² per person, the NDMA Minimum Standards of Relief
figure. **90 shelters, 564 building footprints, 33.98 ha of roof, 97,094 places.**
A school we had assumed held 500 measures 288.

**4. Live anywhere in India, and honest about the boundary.** The citizen app has
no fixed list of areas: type any city, town or village, or use your location. For
any point in India it gives the nearest official gauge with its danger mark and
the hour it was read, live alerts, and live weather. Where a district plan does
not exist, it says so in those words rather than showing an empty shelter card.

### What makes it different

- **We published our own negative result.** Before building, we wrote the test
  that would kill the idea, pre-registered the pass mark, and ran it. It failed,
  and `REPORT.md` says so on the first line. Nobody else in this room will hand a
  judge the document that argues against their own project.
- **Measured and modelled are separated on the screen.** The dashboard's top bar
  carries the gauge reading with the hour it was taken; the slider carries the
  modelled level, labelled "modelled". They were one field once, and it showed
  48.74 for a gauge the panel below was reading at 50.40.
- **The citizen report is treated as a sensor, not feedback.** Radar cannot see
  water between buildings. A person standing outside their door can. That is the
  only input in the system that sees urban flooding, and it is wired into the
  officer's queue.
- **It works with the network off.** The map is saved per area, 327 tiles, 4.5 MB,
  from the district's own server. Reads serve their last good answer and say how
  old it is; writes queue on the phone and send themselves later.

---

## Slide 3b — USP  (the template's spare tenth slide, moved here)

> **Visual for this slide: `figs/fig5_usp.png`.**  Five numbered cards across the
> full width.  This slide is the figure; the text below is what you say over it,
> not what you print on it.

**Headline:** What no other flood dashboard does.

| # | the claim | the one sentence that proves it |
|---|---|---|
| 01 | It publishes its own negative result | "Our repository contains the document that argues against our own project, with the numbers." |
| 02 | Measured and modelled are separated on screen | "The top bar is a gauge reading with the hour it was taken. The slider is the model, labelled. They were one field once, and it showed 48.74 for a gauge reading 50.40." |
| 03 | The citizen is a sensor, not a feedback form | "Radar cannot see water between buildings. This is the only input in the system that sees urban flooding." |
| 04 | It works with the network off | "4.5 MB of map per area, saved before you need it. We will show you with aeroplane mode on." |
| 05 | Free and keyless, end to end | "No key, no login, no licence. A district can run this on a Tuesday morning without asking anyone." |

**Say this after the table, and then stop talking:**

> "Any team can build a flood dashboard. The question is whether you can trust
> the number on it. Every one of these five is about that, and every one of them
> is a file we can open for you."

---

## Slide 4 — Working Prototype & Demo

> **Visuals for this slide: `figs/fig6_demoflow.png`** as a strip across the top,
> then **`dash_1_india_watch.png`** large, with **`app_1_live_anywhere.png`** and
> **`app_5_offline_map.png`** beside it as two phone frames.  If the table below
> does not fit, cut the table, not the screenshots.

### Which features are currently functional

Everything listed here runs today and was tested on a device, not described.

| built and running | evidence |
|---|---|
| Six-stage pipeline, three districts (Patna, Delhi, Mahanadi) | `demo.py`, 121 s end to end |
| Officer dashboard, live | one HTML file served at `/`, polls every 4 s |
| National live map, 355 CWC stations | colour by status, size by exceedance, hover for the reading |
| Citizen Android app, release APK | 34 MB, installs and runs with no Metro, no dev server |
| Search any place in India, or use GPS | keyless geocoding through our own server |
| Live gauge, alerts, weather for any point | CWC + NDMA SACHET + Open-Meteo |
| Offline map packs | 327 tiles, 4.5 MB per area, verified with aeroplane mode on |
| Citizen report and "I cannot leave" | arrive in the officer's queue, resolvable |
| Decision log | approve or override, override without a reason code is refused by the backend with a 422 |
| Forecast and cost-loss ladder | live GloFAS ensemble, per district |

### The demo flow (Input → Process → Output → Benefit)

Run it in this order. It is built to answer the sceptic first.

**1. Is any of this real? (45 s)** — Open the dashboard, click **India watch**.
The map becomes India with every CWC forecast station drawn as it is reading now.
Red dots along the Ganga through Bihar and eastern UP. The table beside it names
them: Sripalpur +2.64 m, Ballia +2.25 m, Gandhighat +1.80 m, each with the hour it
reported. Say: "this is live, you can check any of these against
ffs.india-water.gov.in on your phone right now."

**2. What does that mean for one district? (90 s)** — Switch to **Situation**.
Top of the panel is the measurement: Gandhighat 50.40 m against a danger mark of
48.60, read at 22:00. Under it, the plan: 59,495 in the water, 59,211 in the plan,
and the 284 difference explained on the same screen. Drag the time slider and the
flood layer moves over a real basemap with the roads recolouring as they close.

**3. What is the officer supposed to do? (45 s)** — **Act** tab. The probability
is the share of a live 50-member GloFAS ensemble above a published return period,
computed per district, with the gauge, its distance and the discharge threshold
printed beside it. The cost-loss ladder authorises actions by cost ÷ loss avoided.
Approve, and it lands in the **Audit log** as a database row with who, when and
why. Try Override without a reason and the backend refuses it.

**4. What does the person get? (60 s)** — Phone. Add **Guwahati**, a city 1,000 km
from any district we modelled. It returns the Brahmaputra at Guwahati D.C. Court,
its danger mark, the hour it was read, four live Assam SDMA alerts with distances,
and live weather. Then it says, in these words: *this place does not have a
district plan, and this app will not invent one.*

**5. The sensor nobody else has (30 s)** — Tap **Report water**, send it, and show
it arriving in the officer's Citizen reports queue with its distance from the
district. Resolve it from the dashboard.

**6. The kill shot (20 s)** — Turn on aeroplane mode. The map still draws, the
depth is still there, and the card says "saved 15 min ago, no network."

**User benefit in one line:** the officer stops guessing who to move and gets a
list with deadlines; the citizen stops guessing whether a district-level alert
means them.

---

## Slide 5 — Tech Stack & Architecture

> **Visual for this slide: `figs/fig2_architecture.png`.**  This is the required
> block diagram.  Full width.  The tech stack and API tables go on the same slide
> underneath if the template allows two blocks, otherwise put the diagram here
> and move the source tables to the appendix.

### Tech stack

| layer | what | why this |
|---|---|---|
| Pipeline | Python 3.13, rasterio, numpy, scipy, pysheds, NetworkX, OR-Tools | all open, all installable offline from a wheel cache |
| Backend | FastAPI + Uvicorn, SQLite in WAL mode | one process, one file, no database server for a district to maintain |
| Officer dashboard | one self-contained HTML file, canvas rendering, no framework | opens off a USB stick with no server and says so in the corner |
| Citizen app | React Native via Expo SDK 57, release APK | one 34 MB file, sideloadable, no Play Store dependency for a pilot |
| Maps | MapLibre GL bundled into the APK, OpenStreetMap raster tiles proxied and cached by the district server | no key in the APK; anything shipped in an APK can be pulled out with `unzip` and `strings` |

### APIs and data — where every input was requested from

**Indian government sources**

| source | what we take | how it was obtained |
|---|---|---|
| **CWC Flood Forecasting System** | 354 stations: official danger, warning and highest-ever level, live observed level, issued forecasts | public JSON API, `ffs.india-water.gov.in`. Needs a normal User-Agent and a Spring-Data query grammar |
| **C-Flood (NRSC/ISRO)** | operational inundation depth, 30 m, in metres, every 3 h to 48 h | workspace-scoped WCS. Mahanadi basin only |
| **NDMA SACHET** | live public alerts with severity, area, centroid and local-language text | public CAP feed |
| **NWIC / NWDP** | searched for basin telemetry | CKAN API. **Result: the Ganga is not among the 15 covered basins.** A negative result we report rather than hide |
| **OSDMA** | 776 built cyclone and flood shelters across 23 Odisha districts, with coordinates | published page; the records sit in an inline JS array with a trailing comma, so it is not strict JSON and has to be parsed as JS |
| **Census of India 2011** | district population, to validate our population raster | published tables |

**Global open sources, all keyless**

| source | what we take | licence / access |
|---|---|---|
| **Sentinel-1 RTC** | flood extent from radar | Microsoft Planetary Computer, anonymous SAS signing |
| **Copernicus GLO-30 / NASADEM / ALOS AW3D30** | terrain | AWS and Planetary Computer, anonymous |
| **GHS-POP 2020** | population at 100 m | 10-degree tiles, matched to the AOI |
| **Microsoft Global ML Buildings** | 493,403 footprints in Patna | open. Coverage **ends at longitude 86.247** in the Mahanadi delta, where 51% of that AOI's population lives |
| **Google Open Buildings v3** | footprints where Microsoft stops | CC-BY-4.0. One 1.8 GB gzipped tile, streamed and filtered without landing on disk: 159,185 in the Mahanadi AOI against Microsoft's 17,009 |
| **Google GRRR** | streamflow reanalysis 1980–2023, reforecast, return periods for 1,031,646 gauges | CC-BY-4.0 |
| **GloFAS via Open-Meteo** | 50-member ensemble discharge forecast | no key |
| **OpenStreetMap via Overpass** | roads, shelters, places, water | ODbL. The query must be a `data=` form field; a raw POST returns 406 |
| **Open-Meteo geocoding + Nominatim** | place search and reverse geocoding | keyless; Nominatim's one-request-per-second and caching policy honoured server-side |

**Self-imposed constraint:** free and open only. No key, no login, no licence
negotiation. If a district office cannot get it on a Tuesday morning, it does not
count. Every source above meets that bar.

### Architecture (block diagram — describe it as these five boxes, left to right)

```
 PUBLIC SOURCES            DISTRICT SERVER (one laptop)             CLIENTS
 ─────────────             ────────────────────────────             ───────
 CWC gauges      ─┐        ┌──────────────────────────┐        ┌── Officer
 NDMA SACHET     ─┤        │ live.py    what is true  │        │   dashboard
 GloFAS/Open-Meteo┤───────▶│            right now,    │───────▶│   (browser)
 Sentinel-1 SAR  ─┤        │            anywhere      │        │
 Copernicus DEM  ─┤        ├──────────────────────────┤        └── Citizen app
 GHS-POP         ─┤        │ pipeline   what a flood  │            (Android)
 OSM / buildings ─┘        │            would do here │◀───────    reports,
 C-Flood         ─┘        ├──────────────────────────┤            help requests
                           │ FastAPI + SQLite (WAL)   │
                           │ OSM tile cache           │
                           └──────────────────────────┘
```

The split down the middle is the design. The **left half is live and national**:
it answers for any point in India and holds no model. The **right half is
modelled and per district**: it is built from a past event, because comparing an
answer with what actually happened is the only way to know it is worth anything.
The two are never mixed on screen without a label.

### How security, reliability and scalability are handled

**Security and privacy**
- **No account, no login, no tracking, no analytics SDK, no advertising SDK.**
- **The app reads no GPS unless you press the button**, and it is read on that
  press only, never in the background.
- The published APK asks Android for **INTERNET and VIBRATE** and nothing else
  beyond that one location permission. `aapt2 dump permissions` on the APK is the
  check, and we invite it. It used to ask for fine and coarse location because of
  an Expo module nothing in the code imported; the module and the permissions
  were removed.
- **Phone numbers are never stored.** A help request keeps a truncated
  **HMAC-SHA-256 under a secret the district generates and keeps**. A plain hash
  would not do: there are about a billion Indian mobile numbers, so anyone
  holding the database could hash all of them in seconds and read the column
  back. The key file is gitignored and must never travel with the database.
- No API key is shipped in the APK, because a key in an APK is extractable.
- **Known and stated, not hidden:** LAN traffic is plain HTTP, and the API has no
  authentication. Fine for an isolated pilot network; a district deployment needs
  TLS and a district credential on the write endpoints. It is in the docs as an
  open item.

**Reliability**
- Every read on the phone caches its last good answer **and says how old it is**.
  A stale shelter address is worth having; a spinner is not.
- Every write that fails is queued on the device and retried. Somebody saying "I
  cannot leave" must not lose that to a busy tower.
- The map works with the radio off, from a 4.5 MB saved pack.
- The dashboard falls back to figures baked into the file and prints "cached, no
  backend" rather than going blank.
- The live national snapshot **refuses to serve anything older than six hours**.
  It used to serve whatever was last built by hand, and on the day we found it,
  it was five days old and said the Ganga at Patna was below its danger level
  while it had been above it for three days.
- CWC's own forecast endpoint returns HTTP 500 intermittently. We degrade: the
  forecast column is dropped, every live level is kept.

**Scalability**
- **Per district, the runtime is a laptop.** SQLite in WAL mode, one FastAPI
  process, no cluster, nothing to operate. That is deliberate: a district with an
  unreliable link cannot depend on a cloud.
- **Nationally, the live half already scales**, because it is the same four
  public feeds for every point in India. Adding a district costs nothing there.
- **The modelled half scales per district at a fixed, measured cost:** one
  pipeline run, 121 seconds of compute on the AOI, plus the one-time data pulls.
  Three districts across three states (Bihar, Delhi, Odisha) already run through
  the identical code path with no per-district special-casing left in it. Adding
  the fourth is a config entry and a run.
- **Tiles scale by sharing, not by multiplying.** The district server fetches each
  OSM tile once and serves it to every phone. OSM's tile policy forbids bulk
  downloading, and a thousand handsets each pulling a few hundred tiles is
  exactly that. One polite client instead of a crowd: currently 13 MB of cache
  covers three districts plus all of India at coarse zoom.
- **Bandwidth was engineered, not assumed.** The officer's shelter poll was
  164 kB every four seconds for Delhi; it now sends only the open shelters and a
  count, 2.3 kB.

---

## Slide 6 — Validation, Feasibility & Impact

> **Visual for this slide: `figs/fig4_validation.png`.**  Two real charts: terrain
> against distance-to-river, and how close the mapped flood sits to permanent
> water.  Do not summarise them into a bullet.  The chart is the argument.

### What testing was done, and what it showed

**We pre-registered a falsification test before building, and it failed.** Put
this on the slide.

The test: predict flood extent from terrain against a Sentinel-1 ground truth,
pass mark precision > 0.50 at recall > 0.70, on two independent events.

| | Patna 2019 | Delhi Yamuna 2023 |
|---|---|---|
| new flood mapped | 108 km² | 6 km² |
| best topographic predictor (AUC) | 0.657 | 0.706 |
| distance-to-river alone (AUC) | 0.671 | **0.939** |
| median distance of "flood" from permanent water | **134 m** | **170 m** |

**What that means:** the flood a free satellite can see is the river channel
widening, not the disaster. 74% of Patna's mapped flood sits within 300 m of the
river. Delhi's is almost perfectly explained by proximity alone. Depth over the
Patna fringe comes out at a median of **0.00 m with 92% below 0.3 m**, which is
what a shallow channel margin looks like, not a city under three feet of water.

Both real disasters were kilometres from the river — Rajendra Nagar and
Kankarbagh in Patna, Civil Lines and ITO in Delhi — and **neither is in the
ground truth at all.** Sentinel-1 misses urban inundation to double-bounce, and
by the time it passes the peak has drained.

So the requirement as written **cannot be met by anyone using free data**,
because the ground truth does not contain the phenomenon. That conclusion is
independent of our model, and it is why the design changed: stop predicting
*where* water goes from terrain, fit a *level* to an extent a satellite actually
measured, and drive it with public discharge.

**What we can therefore stand behind, measured:**

| claim | measured value |
|---|---|
| useful lead time on the real event | **6 days** at the 2-year threshold, against the 48–72 hours asked for |
| population model validated | GHS-POP against Census 2011 projected: **0.7% error** over a 3,190 km² district |
| shelter capacity | measured from **564 roof footprints, 33.98 ha**, at the NDMA 3.5 m²/person standard |
| arithmetic closes | placed 47,443 + beyond reach 11,177 + no route 591 = people planned 59,211 |
| pipeline runtime | 121 s end to end |
| districts running | 3, in 3 states, on one code path |
| every figure reproducible | `verify.py` recomputes all of them; `stamp_docs.py --check` reports **94 markers, 0 stale** |

**Bugs found by our own checks, each fixed at source** (this is the slide's
credibility, not a confession): a plan quoting 61,633 people while exposure said
59,622; the river channel counted as flooded land; the allocation keyed by
shelter *name* when Delhi has five separate buildings called "MCD Primary
School"; a depth grid decimated so hard that most of a 12 km² Delhi flood
vanished off the map while the numbers beside it stayed right.

### What real-world deployment requires

**Already true today**
- Free, keyless data only. No procurement, no MoU, no licence.
- Runs on one laptop, offline-capable, no cloud dependency.
- Android APK sideloadable; no Play Store gate for a pilot.

**Needed before a district goes live** — stated plainly rather than waved away:
1. **TLS and authentication.** Plain HTTP on a LAN and an unauthenticated API are
   fine for a pilot, not for a district network. Estimated small, and scoped.
2. **A validated shelter list per district.** We derive capacity from roofs. A
   district has its own official list, and the two should be reconciled.
3. **Bridge state.** Terrain reads the river under a deck, not the deck. 17,225
   people in Patna reach a shelter only across a bridge, and the system says so
   rather than assuming it is open. That needs a human input channel.
4. **Formal data access for depth.** C-Flood covers the Mahanadi. Extending
   operational depth to other basins is an ISRO/NRSC decision, not an
   engineering one. Everything downstream of depth already takes a depth raster
   **from any source**, so the day that arrives, it plugs in.
5. **A district owner** for the decision log, since it is an accountability
   record.

### Impact at scale

- **Immediately:** for any point in India, a person gets the nearest official
  gauge, its danger mark, the hour it was read, live alerts and live weather —
  today, with no per-district work at all. That half is national from day one.
- **Per district onboarded:** in Patna alone the plan covers 59,495 people in the
  water, identifies 11,177 who cannot reach a shelter within 90 minutes and 591
  with no road route at all. Those are the people a district would otherwise
  discover on the day.
- **The number that matters most is 22,734:** the people whose road was already
  gone when the window opened, and who look like they have time if you merge
  "closes" with "gone". Finding them before the water does is the entire point.
- **A reusable public artefact:** our falsification report documents, with
  numbers, that free-satellite ground truth cannot validate urban flood
  prediction in Indian cities. Any team that reads it saves the months we spent
  finding out.

---

## Slide 7 — Roadmap & Closing

### Next milestones

**Now → 1 month (harden what exists)**
- TLS and a district credential on the write endpoints; close the two open
  security items we already document.
- Officer dashboard hardening from real desk use, not demo use.
- A second Bihar district on the same code path, to prove the config-entry claim.

**1 → 3 months (pilot)**
- One district pilot with a real control room: the decision log becomes a real
  accountability record, and citizen reports get a staffed queue.
- Reconcile derived shelter capacity against the district's official list, and
  publish the difference. We expect it to be large and in the direction of "less
  room than assumed", because that is what happened at every school we measured.
- Add the bridge-state input channel.

**3 → 12 months (widen)**
- Extend to the basins where C-Flood publishes operational depth, where our
  weakest link disappears entirely.
- Push for depth coverage beyond the Mahanadi; the system is already built to
  consume it.
- Local-language alert text end to end (SACHET already carries it; we relay it
  unchanged today and should render it).

### Why this should move forward

1. **It is honest in a domain where being wrong kills people.** We ran the test
   designed to kill this project, it failed, and we published the failure. The
   system separates measured from modelled on screen and refuses to serve stale
   data as live. That discipline is the product.
2. **It has no procurement barrier.** Free, keyless, open data; one laptop.
3. **The missing layer is the one it builds.** India forecasts floods well
   already. Nothing public converts that forecast into people, roads, deadlines
   and beds.
4. **Half of it is national today**, and the other half costs 121 seconds of
   compute per district.

**Prototype/demo link:** the officer dashboard at `http://<district-laptop>:8010`,
the citizen APK from `/get` on the same address. Fill in whatever public link you
publish for the finals.

**Repository:** fill in.

---

## Slide 8 — Team Members

Names, roles, and one contribution each. Suggested role split that matches what
actually exists in the repository, so it survives a question:

- data pipeline and hazard modelling
- routing, allocation and the decision layer
- backend and API
- citizen app
- officer dashboard and validation

---

## Slide 9 — Thank You

Leave as is. If the template allows one line, use:

> Every number in this deck is reproducible with one command, and the test that
> failed is in the repository.

---

## How to handle the hard question

A judge will eventually ask some version of: *"So your prediction does not work?"*

Do not get defensive, and do not soften it. The answer is:

> "Correct — and we are the ones who proved it. Predicting where water goes from
> free terrain data cannot be validated in Indian cities, because the free ground
> truth does not contain urban flooding at all. Sentinel-1 sees the channel
> widen; the 2019 Patna disaster was two kilometres from the river and is in no
> satellite flood map. So we stopped doing the thing that cannot be validated.
> We fit a water level to an extent that *was* measured, drive it with public
> discharge that gives six days of lead, and build the decision layer nobody else
> was building on top. And for the part that still cannot be seen from orbit, we
> put a sensor in the field: the person standing outside their door, whose report
> lands in the officer's queue."

Two supporting lines to keep in your pocket:

- **If asked about accuracy:** "Ask us which number and we will tell you how it
  was measured and what it does not cover. Every figure in this deck is stamped
  from a file that `verify.py` regenerates, and the check reports 94 markers and
  0 stale."
- **If asked what is not done:** "TLS, API authentication, a reconciled shelter
  list, and bridge state. They are written down in our own docs as open items,
  which is where we would rather you find them than on stage."
