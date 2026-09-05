# PRAVAAH — speaking script

**Presentation 2:00.  Demo 3:05.**  Measured: 2 minutes 36 seconds of talking in
the demo, plus about half a minute of clicking, counted per step. The per-step
seconds in the headings are real, so you can practise against a stopwatch.

If you are running long, drop the slider drag in step 2 and the report in step 4.
That is 25 seconds and neither is load-bearing.

Speak only what is inside the quote marks. The italic lines are stage directions
for you, not for the room.

| | does what |
|---|---|
| **A** | intro + problem  (Slides 1-2) |
| **B** | solution  (Slide 3) |
| **C** | runs the whole demo |
| **D, E** | answer first in Q&A, D on tech, E on deployment |

**⚡ = a live number.** It changes daily. Open the dashboard that morning and read
the real one off the screen. Never say a live number from memory.

---

# PART 1 — PRESENTATION  (2:00)

## Slide 1 — Title  (15s · A)

> "Good morning. We are Team [name], and this is PRAVAAH — a flood decision layer
> for a district government.
>
> Two minutes on what it does, then three minutes of the real thing running."

---

## Slide 2 — Problem  (45s · A)
*Visual: `fig1_problem.png`*

> "India forecasts floods, and does it well. The Central Water Commission runs
> 354 stations with official danger levels, live and public.
>
> The gap is what happens after the forecast. A District Magistrate is handed a
> number in metres. What they actually need is: how many people are in the water,
> which roads close and when, which shelter has room, and by when they have to
> move. Nothing public does that step.
>
> ⚡ And today, right now, 23 stations across India are above their own danger
> level. We will show you that live in a moment."

---

## Slide 3 — Solution  (60s · B)
*Visual: `fig3_pipeline.png`*

> "PRAVAAH is that missing step. Two faces, one backend that a district runs on a
> single laptop.
>
> A control room dashboard for the officer. A citizen app for the person in the
> flood plain.
>
> It takes the live river level and turns it into decisions, in six stages, end
> to end, in 121 seconds. For Patna: 59,495 people in the water. 47,443 of them
> placed in 55 shelters. 11,177 who cannot reach a shelter within 90 minutes. 591
> with no road route at all.
>
> Every shelter's capacity is measured — roof area divided by the NDMA standard
> of 3.5 square metres per person, not a number somebody claimed. Every road
> carries a deadline. And it runs entirely on free public data: no API key, no
> login, no licence to negotiate.
>
> Let me show you."

*Hand the laptop to C and sit down.*

---

# PART 2 — DEMO  (3:00)

**Before you walk up:** backend running, dashboard top right shows a green
**live**, phone and laptop on the same wifi, aeroplane mode OFF for now.

**Rule:** point at the screen and say what is on it. Do not re-explain the
architecture.

---

## 1 · India  (35s) — dashboard → **Watch**

*The map becomes the whole country.*

> "This is India right now. Every dot is a CWC station. Green normal, amber above
> warning, red above its own official danger level, sized by how far over.
>
> ⚡ 23 above danger this morning. That red line through Bihar is the Ganga.
> ⚡ Sripalpur, 2.68 metres over, read at six.
>
> None of it is modelled. Check any of them against the CWC site on your phone."

---

## 2 · One district  (40s) — click **Situation**

> "Now Patna. Top of the panel is the measurement — ⚡ Gandhighat, 50.43 metres, danger mark
> 48.60, read at 6 a.m.
>
> Below it is the plan: 59,495 people in the water. Real basemap, our layers on
> top. Flood in blue. Every road coloured by what can still use it — green a car,
> orange on foot, red boat only."

*Drag the time slider slowly, about three seconds.*

> "Same plan through time. The roads change colour as the level rises. That is the
> evacuation window, in hours."

---

## 3 · What the officer may do  (35s) — click **Act**

> "⚡ 100 percent, and nobody typed it — that is the share of a live 50-member
> ensemble above a published return period, with the gauge and threshold printed
> beside it.
>
> The ladder authorises each action by its cost divided by the loss it avoids."

*Click Approve.*

> "That is now a database row — who, when, why. Override without a reason code and
> the backend refuses it."

---

## 4 · The phone  (40s) — app → add **Guwahati**

> "Now the person. No list to pick from — you type where you are. Guwahati, a
> thousand kilometres from any district we modelled."

*Add it. Land on Home.*

> "Nearest official gauge, the Brahmaputra at Guwahati D.C. Court, its danger mark,
> and the hour it was read. Live alerts from Assam SDMA. Live weather. Anywhere
> in India, day one."

*Tap Report water, choose a depth, send.*

> "A satellite cannot see water between buildings. A person outside their door
> can. So they send it back."

---

## 5 · The loop closes, with the network off  (35s)

*Switch to the dashboard, Citizen reports.*

> "There it is in the officer's queue, with how far away it came from."

*Now turn on aeroplane mode in front of them, and reopen the map on the phone.*

> "And a flood is exactly when the network is not there. Radio off. The map still
> draws, and the card says 'saved fifteen minutes ago, no network' instead of
> pretending to be live.
>
> 4.5 megabytes, saved on a calm day, from the district's own server."

*Stop. Put the phone down. That is the end.*

---

# If they ask questions

**"Where does the data come from?"**
> "All of it is free, public and keyless. CWC for the gauges, NDMA SACHET for
> alerts, ISRO's C-Flood and Sentinel-1 for water extent, Copernicus for terrain,
> GHS-POP for population, OpenStreetMap for roads and shelters, and Open-Meteo
> for weather and discharge forecasts. Nothing needed a licence or a login."

**"Will it scale?"**
> "Half of it already has. The live half is the same public feeds for every point
> in India, working nationally today with no per-district work. The modelled half
> is 121 seconds of compute per district, and we have run three districts in
> three different states on one code path."

**"Is it deployment ready?"**
> "For a pilot, yes — it runs on one laptop with no procurement. Before a full
> district deployment it needs TLS and authentication on the write endpoints, and
> the shelter list reconciled against the district's own records."

---

# The corridor version

Thirty seconds, if that is all you get:

> "India forecasts floods well. Nobody converts that forecast into which people,
> which roads, and by when. We built that layer, on free public data, and it runs
> on one laptop."

---

# APPENDIX — every data source, and what we take from it

Not for the slides. This is so you can answer precisely if a judge asks.
**Everything below is free, public, and needs no key, no login and no licence.**

## Indian government sources

| source | what we take | how we get it |
|---|---|---|
| **CWC Flood Forecasting System** | 354 stations: official danger, warning and highest-ever levels, live observed level, issued forecasts | public JSON API at `ffs.india-water.gov.in` |
| **C-Flood (NRSC / ISRO)** | operational inundation **depth**, 30 m, in metres, every 3 h out to 48 h | public WCS, Mahanadi basin |
| **NDMA SACHET** | live public alerts: severity, area, centroid, local-language text | public CAP feed |
| **OSDMA (Odisha)** | 776 built cyclone and flood shelters across 23 districts, with coordinates | published shelter list |
| **Census of India 2011** | district population, used to check our population raster | published tables |

## Global open sources

| source | what we take | licence |
|---|---|---|
| **Sentinel-1 SAR** (ESA) | flood extent from radar, sees through cloud | open, via Microsoft Planetary Computer |
| **Copernicus GLO-30 / NASADEM / ALOS** | terrain elevation at 30 m | open |
| **GHS-POP 2020** (EU JRC) | population at 100 m resolution | open |
| **Microsoft Global ML Buildings** | 493,403 building footprints in Patna | open |
| **Google Open Buildings v3** | footprints where Microsoft's coverage ends | CC-BY-4.0 |
| **Google GRRR / Flood Hub** | return periods for 1,031,646 river gauges | CC-BY-4.0 |
| **GloFAS via Open-Meteo** | 50-member ensemble discharge forecast | free, no key |
| **Open-Meteo** | live weather, forecast, and place search | free, no key |
| **OpenStreetMap** | roads, shelters, places, water bodies | ODbL |
| **Nominatim** | turning a GPS fix into a place name | ODbL |

## How each one is used

- **Who is in the water** → GHS-POP population, on the flood depth grid
- **Where the water is** → C-Flood depth where it exists, Sentinel-1 extent plus
  Copernicus terrain elsewhere
- **Which roads close and when** → OpenStreetMap road network, with each road's
  bed elevation from the terrain
- **Which shelter, and does it fit** → OSM and OSDMA shelter locations, capacity
  from Microsoft and Google building roof area at the NDMA standard of
  3.5 m² per person
- **How much warning** → GloFAS ensemble against Google Flood Hub return periods
- **What is happening right now** → CWC gauges, NDMA SACHET alerts, Open-Meteo
  weather, all live, refreshed in the background

One line if you need it in a sentence:

> "Every input is a public feed an Indian district could fetch on a Tuesday
> morning without asking anyone's permission."
