# PRAVAAH, in plain language

No jargon. If you read only one file about this project, read this one.
`PRAVAAH-COMPLETE.md` is the same thing with every number and every proof.

Last stamped: <!--N:generated-->2026-08-31 21:15 UTC, code cbd657062600<!--/N-->

---

## 1. What is the problem?

When a river floods in India, a district officer has to decide, today, with
incomplete information:

- Who is going to be standing in water, and how many?
- Which roads will still work, and until when?
- Where do I send people, and does that building have room?
- Is it time to act, or am I about to evacuate a town for nothing?

Right now those four questions are answered by phone calls and local knowledge.
There is a lot of flood *data* in India. There is very little that turns data
into a decision with a time on it.

---

## 2. What did we build?

A system that takes a river's water level and turns it into an actual plan:

```
   how much water is in the river
              |
              v
   how high the water will stand
              |
              v
   which land goes under, and how deep
              |
      +-------+-------+
      |               |
  who is there    which roads still work,
  (how many)      and until what time
      |               |
      +-------+-------+
              |
              v
   send these people to that shelter,
   which has this much measured room
              |
              v
   and here is what you are allowed to
   do at today's probability
```

Every arrow in that diagram is a real script that runs. Nothing is a mockup.

---

## 3. Why did we build it this way?

Because our first idea failed a test, and we believed the test.

**The first idea** was the standard one: look at the shape of the land, work out
which parts are low-lying near a river, and call those the flood zone. It is
cheap and everyone does it.

**We tested it properly.** We wrote down the pass mark *before* running the test,
then compared the prediction against a flood a satellite had actually
photographed, on two real events: Patna 2019 and Delhi 2023.

**It failed.** Badly. It was no better than a one-line rule that says "low ground
floods". Precision was 9% where we needed 50%.

**Then we found the bigger problem.** We looked at where the satellite said the
flood was, and it was all hugging the river, a median of about 134 metres from
the water's edge. But the actual 2019 Patna disaster was Rajendra Nagar and
Kankarbagh, which are kilometres inland and were under water for days.

Out of 455,860 buildings in Patna, the free satellite marked **659** as flooded.
That is 0.145%.

So the satellite was not photographing the disaster. It was photographing the
river getting wider. Radar cannot see water trapped between buildings in a dense
city, and by the time it flies over again the street has drained.

**This is the most important thing in the project.** We could have quietly tuned
the numbers until something looked good. Instead we wrote it down and changed the
design.

**The change:** stop asking the land where the water will go. Instead take an
extent the satellite genuinely measured, work backwards to the water *level* that
would produce it, and then move that level up and down using public river-flow
data. Now we have the thing the problem actually needed: **time**. Not just "this
area floods" but "this road stops taking cars at 8 p.m. on Wednesday".

---

## 4. How does it work, step by step?

### Step 1: How much water is in the river?

A free European service publishes river flow for anywhere in the world, past and
forecast, no signup. That is our input.

### Step 2: How high does the water stand?

We take two dates where a satellite photographed the actual flood. For each, we
search for the water level that would cover exactly that much land. Two dates
give us a relationship: this much flow means this high a level.

**Does it work?** The Central Water Commission publishes an official danger level
for Patna's Gandhighat gauge: **48.60 metres**. We never looked at that number
while building. Our fitted level for the flood day came out at **48.70 metres**.
Ten centimetres apart, from a completely different method.

### Step 3: Which land goes under?

Level minus ground height equals depth. One rule for everyone.

One trap here worth knowing: the river itself is not a flood. Water sitting in
the Ganga is just the Ganga. Early on we were counting the riverbed as flooded
land, which made whole "wards" show up as being under 8.7 metres of water. Those
wards were the river.

Even after fixing that, some sandbars that were dry on the reference day were
still being counted. We now spot those from the elevation data, **except where
there are buildings on them**, because the Ganga's sandbars have villages on them
and a roof is better proof of dry land than any model.

### Step 4: Who is standing in the water?

A global population grid tells us roughly how many people live in each 100-metre
square. We add up the ones that are wet.

**Can we trust that grid?** We checked. Add up its numbers for all of Patna
district and you get 7,121,932 people. Take the actual Census of India count for
the same district and grow it forward at the district's own measured rate, and
you get 7,071,903. That is **0.7% apart**, which is close enough to use.

### Step 5: Which roads still work?

Every road segment carries its own ground height. Water level minus that height
tells us how deep that road is at any hour, so we know when a car stops working,
then a motorbike, then walking, then only a boat.

**Bridges are treated specially and carefully.** The elevation data reads the
*river underneath* a bridge, not the deck, which at first made every bridge in
Patna look like it was under nine metres of water. Now the system refuses to
guess about bridges in either direction. It says: **17,225 people can only reach
a shelter by crossing a bridge, and nobody has confirmed those bridges are open.**
That is a job for a person, not a model, and the system says so instead of
pretending.

### Step 6: Where do people go?

**We do not guess how many people a school holds.** The national disaster
guidelines say 3.5 square metres per person. So we measure the actual roof area
of every school and community building from satellite footprints and divide.

Our guesses had been wrong in **both** directions: a school we assumed held 500
actually measures 288. A campus we assumed held 1,000 measures 10,020.

Then a solver assigns people to shelters, minimising travel time, respecting real
capacity, and refusing to place anyone more than 90 minutes away. Every run also
prints what a dumb "just go to the nearest one" approach would do, so the clever
method has to prove it is worth it. It does: it reaches **12,943 more people**,
for about 14 more minutes of average journey.

### Step 7: Should we act yet?

There is a rule from decision theory: act when the probability of the event
exceeds the cost of acting divided by the cost of being wrong.

Opening shelters is cheap, so it fires at 2% probability. Full evacuation is
expensive and disruptive, so it needs 55%.

**The probability is computed, not typed in.** A weather service runs 50
different forecasts; we count how many of them cross a dangerous flow level. If
that service is unreachable, the system falls back to a fixed number **and says
so on the same line**, so nobody is misled.

The output is a proper emergency alert file plus 160-character SMS drafts that
name each ward's own assigned shelter.

---

## 5. Where does it run, and on what?

**Where:** three real places, three different kinds of flood.

| Place | What kind | What the system says |
|---|---|---|
| **Patna, Bihar** (Sep 2019) | River flood, water level fitted from satellite | 59,495 people in the water, 47,443 placed in shelters |
| **Delhi Yamuna** (Jul 2023) | Embanked river, one snapshot only | Small numbers, and the system explains why rather than inflating them |
| **Mahanadi delta, Odisha** (Jul 2025) | Live government forecast | 186,908 people in the water, only 6,374 shelter places |

That last row is not a failure of the software. It is the software finally being
able to *state* a problem: the delta does not have enough shelter capacity, and
until now nobody could put a number on it.

**Delhi is in here on purpose even though its numbers are small.** Its river runs
between embankments, so the flood area jumps from nothing to everything across
ten centimetres of level. There is no honest level to fit. The system **refuses**
to fit one rather than producing a confident wrong plan. Being able to say "I
cannot answer this" is a feature we built deliberately.

**On what data:** everything is free and public. No key, no login, no licence.

- River flow: a free European forecast service
- Satellite flood photos: Sentinel-1 radar, free
- Ground height: Copernicus 30-metre elevation, free
- Buildings: Microsoft and Google open building datasets, free
- Population: a global open population grid, free
- Roads and places: OpenStreetMap, free
- India's own live systems: Central Water Commission gauges, NDMA public alerts,
  and CWC's C-Flood inundation forecasts. **All three turned out to be open.** We
  had assumed they were not, and we were wrong, so we checked and corrected our
  own documents.
- Odisha's official cyclone shelters: the state disaster authority publishes 776
  of them with coordinates.

---

## 6. What is actually running right now?

- **The full chain, on all three places.** One command each.
- **A backend.** A real API with a real database. 44 automated tests, all
  passing. It accepts the three things no satellite can see: a citizen saying how
  deep the water is outside their door, a person saying they cannot leave on
  their own, and an officer approving or overriding a recommendation.
- **A national view.** 354 government gauges pulled live, plus public alerts.
- **Five web pages**, each a single file you can double-click. No server needed.
- **A national map, an officer dashboard, and a citizen page.**

Phone numbers, by the way, are never stored in readable form. The system can tell
that the same person called twice without ever holding a list of flood victims'
phone numbers.

---

## 7. Why should anyone believe the numbers?

This is the part we are most proud of, and it came out of getting caught.

Someone reviewing our documents noticed the plan said **61,633 people** while a
table two pages earlier said **59,622**. Both were printed by our own code. One
of them was stale.

The real cause turned out to be a genuine bug: two scripts were using two
different thresholds for what counts as "flooded". Fixing that fixed the numbers.

But the deeper problem was that our documents held **copies** of numbers. A copy
goes stale the moment the code changes, and nobody notices.

So now:

1. `verify.py` recomputes **every single number** this project claims, from the
   raw data, offline, and writes them to one file.
2. The documents do not contain numbers. They contain **placeholders** that get
   filled from that file.
3. `stamp_docs.py --check` fails loudly if any document disagrees with what the
   code just computed.

A stale number is now structurally impossible, not just unlikely.

And there is one command that proves the whole thing **with the internet
unplugged**:

```
.venv\Scripts\python.exe demo.py
```

Nine seconds. It checks every input file is present, recomputes every number,
confirms the documents agree, and runs all 44 backend tests. It stops at the
first failure, so if it passes, four things passed.

---

## 8. What does it NOT do?

We would rather say this ourselves than have it found.

1. **It cannot see city flooding.** Water trapped in the streets of Rajendra
   Nagar, which is the actual disaster people remember, is invisible to every
   free dataset we could find. This is the honest ceiling on the whole approach,
   and it is why the citizen reporting feature exists: a person outside their
   door is the only sensor that sees it.

2. **The plan works on one area at a time.** The watch layer covers India; the
   detailed plan does not.

3. **Delhi has no timeline.** One snapshot, no "when". Stated everywhere it
   matters.

4. **The citizen page can read but not write yet.** The backend accepts reports
   and is fully tested; the page just is not wired to it. That is frontend work.

5. **The map does not yet have a slider for the Odisha forecast.** The data is
   ready; the page needs a change.

6. **Shelter capacity is an upper limit,** not a promise. We count every roofed
   square metre as usable floor, which is optimistic, and we do not count extra
   storeys, which is pessimistic. Both are stated.

---

## 9. The one-sentence version

We tried the standard approach, tested it honestly, found it does not work with
free data and said so, then built something that does work: a system that turns
public river data into who is in the water, when each road closes, where they can
go, and whether it is time to act, with every number in every document
regenerated from the code so none of them can quietly go wrong.
