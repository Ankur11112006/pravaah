# PRAVAAH / INDINEER: what to say in the room

Purpose of this sheet: **no question should be able to knock over a claim.**
Read it once before you present. Run `verify.py` if anyone pushes.

---

## Rule zero

Every number below regenerates from `D:\claude\pravaah` by running:

```
.venv\Scripts\python.exe verify.py
```

It needs no internet. If a judge doubts a figure, offer to run it. Nobody
expects a hackathon team to be able to do that, and it ends the argument.

---

## The canonical numbers. Nobody quotes anything else.

| Claim | Number |
|---|---|
| Sentinel-1 over Chennai, Nov 2023 to Jan 2024 | 6, 18, 30 Nov, then **17 Jan**. A **48-day gap** containing all of Michaung |
| Patna cell-level AUC | HAND **0.657**, elevation **0.657**, distance-to-river **0.662** |
| Delhi cell-level AUC | HAND **0.706**, elevation **0.663**, distance-to-river **0.939** |
| Best precision at 70% recall | Patna **9%**, Delhi **5%**. Target was **50%** |
| Buildings labelled flooded by SAR, Patna | **659 of <!--N:buildings_sampled-->455,860<!--/N--> = 0.145%** |
| Median distance of mapped flood from the river | Patna **134 m**, Delhi **170 m** |
| Depth over the 91 km² mapped flood | median **0.00 m**, **92.4%** below 0.3 m |
| Exposure module output | 20 units, 3,429 people, 174 buildings, 43 km² |
| DEMs actually tested | Copernicus GLO-30, NASADEM, ALOS AW3D30 |

**Never say:** "99.9%", "AUC 0.87", "validated", "83% probability", or any
depth figure as a prediction. Each of those is either wrong or unearned, and
each is the kind of thing that gets checked.

---

## Hostile questions, and the answer

**"What's your accuracy?"**
> We measured it and we missed the target. Best precision was 9% at 70% recall
> against a 50% target. That is why the architecture changed: we rank wards, we
> do not output a probability.

Do not dodge this one. Answering it with a real failure buys credibility for
everything else you say.

**"AUC 0.66 is barely better than random. Why should I care?"**
> You shouldn't, as a probability. That is our point. It is enough to order
> wards by relative risk and not enough to tell one household it will flood.
> We report it as a ranking for exactly that reason.

**"A distance-to-river raster beats your model. Why not just ship that?"**
> For the flood Sentinel-1 can see, you should, and that is a real finding we
> published against ourselves. But the flood it can see is the channel widening,
> median 134 m from the river. The disaster was in Rajendra Nagar and
> Kankarbagh, kilometres inland. Neither our model nor the distance rule
> addresses that, and neither does the ground truth.

**"How do you know Sentinel-1 missed Chennai?"**
> Two independent catalogues, ASF and Copernicus Data Space, agree: last pass
> 30 November, next pass 17 January. A 48-day gap with the cyclone inside it.
> The query is cached; I can run it now.

**"How do you know SAR misses urban flooding?"**
> During a week-long flood that displaced people across Patna, SAR labelled 659
> buildings out of <!--N:buildings_sampled-->455,860<!--/N-->. We do not claim to know the true number that
> flooded. We claim 0.145% is not it.

**"So your system does not predict floods."**
> Correct, and we stopped claiming it does. We consume hazard from IMD, GloFAS
> and CWC. What does not exist anywhere is the layer that turns a forecast into
> who moves where, on which road, by when. That is what we build.

**"Then what have you actually built?"**
> Two things, both running. First, the falsification pipeline: satellite fetch,
> flood mapping, terrain analysis, metrics. Second, the whole decision layer:
> exposure counting, road passability by mode, OR-Tools shelter allocation, and
> cost-loss triggers producing CAP 1.2 XML and SMS text. It runs end to end in
> about two minutes on one command. What we do NOT have is a hazard layer good
> enough to feed it, which is exactly what the test proved, so depth is an input
> to our pipeline and not an output of it.

**"Your numbers are tiny. 3,429 people?"**
> Because the flood we could actually map is a river margin, not the city. The
> code does not care how big the input is. Give it NDEM's inundation layer and
> the same run produces the real figure. We would rather show you a small honest
> number from a real event than a large one from a scenario we invented.

**"Does the optimiser actually beat a simple nearest-shelter rule?"**
> On this input, by 1.1%, and we print that comparison every run because we
> wanted to know too. The margin is small here because shelter capacity is
> abundant. It matters when capacity binds, which is the situation the optimiser
> exists for. We are not going to claim more than the number shows.

**"Two events is not a sample."**
> Agreed, and it is listed as a limitation. What we can say is that the result
> held across two events, two terrain types, three DEMs, and six drainage
> thresholds. It is consistent, not conclusive.

**"Why not FABDEM, your own document names it?"**
> It requires a University of Bristol licence acceptance we do not have. We
> substituted NASADEM and ALOS. All three agree, so we do not think the DEM is
> what is carrying the result, but we flag it as formally open.

**"Isn't a negative result just an excuse for not building?"**
> The negative result came out of a pipeline we built. The code is here and it
> runs in about a minute. We could have not run the test and shown you a
> confident number instead. We think you would have asked where the ground
> truth came from.

**"What's your impact number? How many lives?"**
> We do not have one and we are not going to invent one. Our exposure module
> counted 3,429 people in the flood we could actually map. That number is small
> because the map is small, and we would rather show you a small honest number
> than a large invented one.

---

## If you only get one sentence

> We tested our own core assumption, it failed, and the reason it failed is that
> the free satellite ground truth everyone uses does not contain Indian urban
> flooding at all. So we rebuilt the system to be honest about what it knows and
> to plug into a better hazard source the moment we can get one.

---

## What is genuinely new here, if asked

1. Chennai Michaung, the event most Indian flood decks cite, has a 48-day
   satellite gap around it. We have not seen that stated anywhere.
2. Across both events the SAR-visible flood is a river margin, and a one-line
   distance rule explains it better than any terrain model. In Delhi that rule
   scores 0.939.
3. Therefore the building-level validation in our own original design is not
   runnable by anyone on free data. That is a statement about the field, not
   about us.
