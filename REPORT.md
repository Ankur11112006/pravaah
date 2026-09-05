# PRAVAAH falsification test: result

**Run 23 Aug 2026 on two events (Patna 2019, Delhi Yamuna 2023). Verdict: FAILED.**

The spec ([PS3-solution.md](../PS3-solution.md), "The falsification test") says:

> If we cannot beat the dumb elevation baseline, the project is dead.

We cannot beat it. This document says so.

---

## 1. The event had to change, and that is a finding

The spec names **Chennai, Cyclone Michaung, December 2023**, with Sentinel-1 SAR
of 5 Dec 2023 as ground truth. **That image does not exist.**

Sentinel-1 acquisitions over Chennai, Nov 2023 - Jan 2024: **6 Nov, 18 Nov,
30 Nov. Nothing in December.** Confirmed independently against the ASF DAAC
catalogue and the Copernicus Data Space catalogue. Optical fallback is dead too:
every Sentinel-2 scene from 1-16 Dec is 65-99% cloud, and Landsat matches.
Bhuvan's public WMS carries no historical inundation layer, only CWC gauge
points and waterbodies.

So we picked the event by ground-truth availability instead. Of ten major Indian
floods swept, only two have SAR within three days of peak:

| Event | Peak | Nearest post-peak S1 |
|---|---|---|
| **Patna 2019** | 30 Sep | **+0 days (peak day)** |
| Delhi Yamuna 2023 | 14 Jul | +2 days |
| Chennai 2015 | 2 Dec | +4 days |
| Kerala 2018 | 17 Aug | +4 days |
| Hyderabad 2020 / Bengaluru 2022 / Vijayawada 2024 | | +6 to +11 days |
| **Chennai Michaung 2023** | 4 Dec | **none** |

Patna 2019 was used: SAR on the peak day itself, and a clean same-orbit
baseline twelve days earlier.

## 2. What was run

Everything below is free and needs no login.

| Input | Source |
|---|---|
| Flood SAR | Sentinel-1 RTC, 30 Sep 2019 00:12, relOrb 121 desc (Planetary Computer) |
| Baseline SAR | Sentinel-1 RTC, 18 Sep 2019, same relative orbit |
| DEM | Copernicus GLO-30, plus NASADEM and ALOS AW3D30 for the A/B |
| Buildings | Microsoft Global ML Building Footprints, 493,403 in AOI |
| Rainfall | Open-Meteo ERA5 archive |

AOI 84.90-85.35 E, 25.45-25.75 N (1,454 km²): Patna city plus the Ganga and
Punpun floodplain. Rainfall 26-29 Sep: **382 mm**, peaking at 147.5 mm on 28 Sep.

Ground truth = new open water on 30 Sep vs 18 Sep: VV < -15 dB and a drop
> 3 dB. **108 km²**, sensitivity 52-148 km² across reasonable thresholds.

This was run as a **perfect-forecast upper bound**: the model was given the rain
that actually fell, not a T-2 forecast. If the upper bound fails, the
operational version can only be worse, so no forecast pipeline was built.

## 3. Results

**Per 30 m ground cell** (n = 1,605,141, 5.6% flooded):

| Predictor | AUC | best F1 | precision | recall | precision @ recall 70% |
|---|---|---|---|---|---|
| HAND | 0.657 | 0.163 | 0.096 | 0.535 | 0.089 |
| **elevation (dumb baseline)** | **0.657** | **0.169** | 0.101 | 0.527 | 0.085 |
| distance to permanent water | 0.671 | | | | 0.089 |
| target | | | **> 0.50** | **> 0.70** | **> 0.50** |

**Per building** (n = <!--N:buildings_sampled-->455,860<!--/N-->):

| Predictor | AUC | best F1 | precision @ recall 70% |
|---|---|---|---|
| HAND | 0.764 | 0.014 | 0.005 |
| **elevation** | **0.866** | **0.039** | 0.006 |

Three things, all bad:

1. **HAND never beats elevation.** Tied on Copernicus, loses on NASADEM
   (0.644 vs 0.666) and ALOS (0.656 vs 0.688). At building level it loses
   badly (0.764 vs 0.866).
2. **The failure is not a tuning artefact.** Across drainage thresholds from
   acc>500 to acc>200,000, HAND scores 0.439 to 0.657 and never reaches
   elevation's 0.670.
3. **Neither is usable in absolute terms.** Required precision was > 50% at
   > 70% recall. Both deliver **~9%**. Off by a factor of five, not a margin
   that better tuning closes.

And the sharpest one: **"how far from the river" (AUC 0.671) beats the whole
HAND pipeline (0.657).** Whatever was predictable about this flood was the
channel widening, which a distance raster already captures.

## 3b. Second event: Delhi Yamuna 2023

Patna is flat and its flood was pluvial, the worst case for HAND. So the whole
chain was re-run on **Delhi Yamuna 2023** (flood 16 Jul relOrb 27, same-orbit
baseline 22 Jun), which is riverine, HAND's home turf.

| Predictor | AUC | best F1 | precision | recall | precision @ recall 70% |
|---|---|---|---|---|---|
| HAND | 0.706 | 0.027 | 0.014 | 0.225 | 0.011 |
| elevation | 0.663 | 0.024 | 0.012 | 0.803 | 0.012 |
| **distance to river** | **0.939** | 0.100 | 0.058 | 0.373 | 0.049 |

**HAND does beat elevation here** (0.706 vs 0.663), so the Patna failure was
partly terrain. But it does not matter: best F1 is 0.027 and precision at 70%
recall is 1.1%. And **distance to the river scores 0.939**, crushing both.

## 3c. What the two events together actually prove

The SAR-visible flood is the river channel, not the disaster.

| | Patna 2019 | Delhi 2023 |
|---|---|---|
| new flood mapped | 108 km² | 6 km² |
| median distance from permanent water | **134 m** | **170 m** |

> Patna's figure read 150 m when this report was first written, on the run
> before `hazard.widen_channel` was added. That fix removed sandbars that
> were dry on the baseline date and had been counted as flood, which moved
> the median in. 134 m is the current value, recomputed by `verify.py` and
> stamped into the other documents; the conclusion is unchanged and slightly
> stronger.
| distance-to-river AUC | 0.671 | 0.939 |
| best topographic predictor | 0.657 | 0.706 |

74% of Patna's mapped flood sits within 300 m of the river. Delhi's is almost
perfectly explained by proximity alone. Depth over the Patna fringe comes out at
a median of 0.00 m and 92% below 0.3 m, which is what a shallow channel margin
looks like, not a city under three feet of water.

Both floods were disasters kilometres from the river: Rajendra Nagar and
Kankarbagh in Patna, Civil Lines and ITO in Delhi. **Neither is in the ground
truth.** Sentinel-1 sees the channel widen, misses urban inundation to
double-bounce, and by the time it passes (+0 to +2 days) the peak has drained.

So the falsification test as written **cannot be passed by anyone** using free
data, because the ground truth does not contain the phenomenon the project
targets. That conclusion is independent of our model.

## 3d. The decision layer is built and runs

All four downstream steps are built and run end to end on one command
(`demo.py`, 121 s). They take a **depth raster as input from any source**, which
is the whole architectural point: ours, NDEM's, C-FLOOD's or Flood Hub's.

```
STEP 3  exposure      43 km2 wet, 3,429 people, 174 buildings, 20 reporting units
                      0 of 451 critical facilities inside the wet zone
STEP 4  roads         53,895 nodes / 65,735 edges / 7,301 km, 97.8% connected
                      99.07% still car-passable, 40 km bike-only, 25 km foot,
                      2.2 km boat-only, 2 named roads degraded
STEP 5  allocation    724 pickup points -> 172 shelters above water
                      3,082 of 3,096 routed, mean trip 23.3 min
                      14 people STRANDED with no shelter within 90 min, reported
                      min-cost flow 71,785 person-min vs greedy 72,596 (1.1% better)
STEP 6  alerts        cost-loss thresholds: at P=42% three actions authorised,
                      full evacuation is NOT (needs 55%)
                      CAP 1.2 XML, 4 info blocks, parses; SMS 103-116 chars
```

Honest notes on this run, all of which belong on the slide:

- **The input is the SAR fringe**, so every number is small. Feed it a real
  hazard layer and the same code produces the real numbers. That is the point of
  making depth an input rather than an output.
- **Shelter capacities are assumed** (school 500, college 1000, community centre
  300). The real source is the district IDRN inventory.
- **The solver's margin over greedy is only 1.1% here**, because shelter capacity
  is abundant (113,200 places for 3,082 people). The solver earns its place when
  capacity binds; on this input a greedy loop would have been nearly as good and
  we say so rather than overselling the optimiser.
- **P = 0.42 in Step 6 is an input, not a forecast.** We have no ensemble. The
  arithmetic that converts a probability into an authorised action is what is
  being demonstrated, not the probability itself.
- Step 5 reports people it **cannot** reach rather than dropping them. Fourteen
  people at six pickup points have no shelter within 90 minutes by any mode.

## 4. The ground truth cannot see the actual disaster

Of <!--N:buildings_sampled-->455,860<!--/N--> buildings, SAR labels **659 as flooded. 0.14%.**

Patna 2019 put Rajendra Nagar and Kankarbagh under water for a week. SAR sees
659 buildings, because in dense built-up areas floodwater raises backscatter
through double-bounce against walls instead of lowering it. Free SAR maps open
water well and urban flooding barely at all.

So the building-level test in the spec **is not runnable with free SAR at all**,
by anyone, for any Indian city. That is independent of whether our model works.

## 5. Caveats, stated plainly

- **FABDEM was not tested.** It needs a University of Bristol licence
  acceptance. The A/B used three DSMs instead. All three agree, but the spec's
  own bare-earth question stays formally open.
- **One event, one region.** A flat alluvial plain is the worst case for HAND:
  median HAND here is 1.3 m, so there is barely anything to threshold.
  Delhi Yamuna 2023 would be a genuinely different terrain test.
- **No forecast skill was measured**, by design. The upper bound failed first.
- Ground truth is open-water extent, not depth, and it is a single snapshot.

## 6. What this means

The spec's own rule applies: this is a fail, and the honest move is to say so
rather than retune until something passes.

What survives:
- The pipeline is real and runs end to end in about a minute on free data.
- The Chennai finding is publishable on its own: **the event everyone cites has
  no usable satellite ground truth.**
- "Distance to river beats HAND" is a real, defensible negative result.

What does not survive: the claim that a HAND-based engine turns a forecast into
building-level flood predictions. On this evidence it does not, and a dumb
elevation threshold is as good or better.

## Reproduce

```
fetch_sar.py -> flood_mask.py -> hand.py -> fetch_buildings.py
            -> build_table.py -> evaluate.py -> robustness.py -> dem_ab.py
```
