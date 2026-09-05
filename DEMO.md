# PRAVAAH, the demo runbook

Two apps, one backend, one laptop. Read this on the morning, not on stage.

---

## 1. Start it

Double-click **`START-DEMO.bat`**, or:

```
cd D:\claude\pravaah
.venv\Scripts\python.exe -m uvicorn api:app --host 0.0.0.0 --port 8010
```

Then open **http://localhost:8010** for the control room.

That one process serves both the officer page and the API the phone talks to.
There is nothing else to start and no address to type into the browser.

**Check before you walk up:** the top right of the control room says a green
**live**. If it says amber **cached, no backend**, the page still works from the
numbers baked into it, but the phone will not reach anything. Restart the
backend.

### The control room

The map is a **real basemap**, OpenStreetMap raster tiles in Web Mercator, with
our own layers on top: the flood field, the road network coloured by what can
still use it, the pickup points, the shelters, and live citizen reports. The
tiles come from this server, which fetched each one once and cached it, so the
map draws with the venue wifi unplugged. Pan with a drag, zoom with the wheel or
the buttons, and the square button refits the district.

**All three districts have a map now.** They did not before: the page carried
Patna's geometry and printed "no map for this district yet" over the other two
while their numbers sat in the panel beside it. Right numbers under the wrong
city is the most confusing thing a control room can show.

What time means is different in each, and the bar under the map says which:

| district | the flood layer is | the slider |
| --- | --- | --- |
| Patna | terrain below a water level fitted to the observed satellite extent | hourly, continuous |
| Mahanadi | the C-Flood depth field exactly as published | 8 frames, 3 hours apart, nothing interpolated |
| Delhi | one observed snapshot | none, and the page says why |

**Act** is live. The probability is the share of a 50-member GloFAS ensemble
above a published return period, fetched per district when you open the tab, and
the gauge, its distance and the discharge threshold are printed next to it. It
used to be the number 22 typed into the page under a caption claiming it was
computed. The severity table underneath gives every return period, because in
the monsoon the 2-year and 5-year rows sit at 100% for weeks and say nothing.

Two things on that tab are worth saying out loud before a judge asks:

* The probability is live, for today. The map is a past event, kept because it
  is the one we could check our answer against. The page carries that warning
  where the probability is, since that is where the two get merged.
* At Delhi the modelled reach has a 100-year discharge of about 3,500 m3/s.
  That is the number the published dataset gives for the Yamuna there, and it
  is worth checking against the CWC gauge before acting on a 0%.

**India watch** is the panel to open if somebody asks whether any of this is
real. The map switches to the whole country and draws every CWC forecast station
as it is reading now: red and sized by how far over its own danger mark, amber
above warning, green normal, grey for the ones not reporting. Beside it is the
same set as a table, worst first, with the level, the mark, how far over, and the
hour that station last reported. Hover any dot for its reading.

On the evening this was written that was 23 stations above danger, in a line
along the Ganga through Bihar and eastern Uttar Pradesh, and Gandhighat, the
gauge this district's whole plan is fitted to, was 1.80 m over.

The map follows the panel, not the district selector: choosing another district
while India watch is open leaves the country on screen, because a national panel
beside one district's map is how a wrong number gets quoted in a meeting.

The top bar carries the **measured** reading, its danger mark and the hour it
was taken. The time slider carries the **modelled** level, labelled as modelled.
Those were the same field once, and it showed 48.74 for a gauge the panel below
it was reading at 50.40: one number modelled, one measured, neither labelled.

The **Situation** panel carries the same gauge at the top, above the modelled
plan, on purpose: one line is a measurement taken an hour ago, everything under
it is modelled from a past event, and an officer should be able to see which is
which without being told.

**Citizen reports** now carry how far they are from this district. The app works
anywhere in India, so a report can arrive from a town with no plan at all, and a
report from 666 km away listed silently among local ones would be read as local.

### The phone

The citizen app is built in **SACHET's design language on purpose**: same navy
chrome, same five tabs in the same order (Home, Alerts, Weather, Locations,
More), same severity-coloured alert cards. A flood is the worst possible moment
to make somebody learn a new layout, and SACHET is the alert app a lot of people
in India already have.

What is ours is the content: the ward's own expected depth, which vehicle still
works at it, the hour each road near it closes, the allocated shelter, and the
two buttons that send information the other way.

Alerts are **live NDMA SACHET**, relayed unchanged, in whatever language the
issuing agency wrote them. Weather is live Open-Meteo.

The map is **OpenFreeMap** vector tiles, which need no key and no account, with
raster OpenStreetMap as an automatic fallback if that provider is unreachable.
MapLibre itself is bundled into the app rather than fetched from a CDN, so the
map has one network dependency (tiles) instead of two. That matters: on bad wifi
the library was the first thing to fail, and the result was an empty box even
when tiles would have loaded.

### The map without a network

Under **Locations**, each subscribed place has a **Save map** button. It asks
first, with the real size on the button: 327 tiles, about 4.5 MB, roughly 30 km
around the place. That is the whole demo of the offline story, and it is worth
doing on stage: save the map, turn on aeroplane mode, then open the map again.

The tiles come from the district server, never from OpenStreetMap directly. The
OSMF tile policy forbids bulk downloading, and a few thousand phones each pulling
a few hundred tiles is exactly that. The server fetches each tile once, caches it
and serves it to everybody: one polite client instead of a crowd.

Coarse zooms download first, so an interrupted save still draws a whole map, just
a blurry one, rather than a sharp postage stamp in a sea of grey. A pack is only
marked saved if nearly every tile arrived; a half download would show a map with
holes and no way to tell why.

Two things this cost, both found on the emulator with the radio off:

* A saved pack holds zoom 9 to 13. The full map used to open at 8.5, below
  anything on the phone, so it opened grey. Offline the map now opens at 9 and
  cannot be pinched out past it.
* An absolute `file://` tile URL inside a document served from an `https` base is
  cross origin, and the WebView refuses it silently: pins on an empty grey sheet.
  Offline the map document is based on the app's own folder instead, which makes
  the tiles same origin.

The app is already installed on the emulator. If you need to reinstall, use the
**release** APK, not a debug build. `INSTALL-ON-EMULATOR.bat` does the lot,
including booting the emulator, or by hand:

```
adb install -r app\android\app\build\outputs\apk\release\app-release.apk
```

It is 46 MB with the JavaScript bundled inside, so it needs no Metro and no dev
server: install it and it runs. That also means you can hand the file to anyone.

### Anywhere in India, live

The app is not a Patna app. Under **Locations, Add a location** there is no list
to pick from: type any city, town or village and it is found, or tap **Use my
current location** and the phone's own position is named. Both go through the
district server, so the phone holds no key and talks to nobody else.

For any place at all, four things are live and none of them are modelled:

| what | where it comes from | how fresh |
| --- | --- | --- |
| the nearest river gauge, its level and its official danger mark | Central Water Commission's forecasting network, 355 stations | hourly, and the reading's own timestamp is on screen |
| alerts near you | NDMA SACHET, whatever the issuing agency wrote | as issued |
| weather and forecast | Open-Meteo | current hour |
| the map | OpenStreetMap through this server | cached, works offline once saved |

The national snapshot refreshes itself in the background and **refuses to serve
one older than six hours**. It used to serve whatever `build_national.py` last
wrote, which on the day this was found was five days old and said the Ganga at
Patna was below its danger level when it had been above it for three days.

What a place does **not** get, unless the pipeline has been run for its district,
is expected depth for a street, an allocated shelter, or the hour each road
closes. Those need elevation and satellite data prepared district by district,
and they are built from a past event because comparing an answer against what
actually happened is the only way to know it is worth anything. The app says so
on the screen, in those words, rather than showing an empty shelter card. A
search result that does sit inside a modelled district is tagged **district
plan** with its population.

### Putting it on a real phone

Phone and laptop on the same wifi, then in the phone's browser:

```
http://192.168.1.10:8010/get
```

That page detects the address itself and hands over the installer. Or copy
`out/PRAVAAH-v1.0.apk` across by cable.

**The app finds the server on its own.** It tries, in order, whatever was typed
in More, then the laptop's LAN address as it was when the APK was built, then
the emulator's 10.0.2.2, and keeps whichever answers. So an install on a phone
on the same wifi works with nothing typed. If the laptop's address has changed
since the build, More shows the list it tried and takes a new one, no rebuild.

**Before every APK build**, run this or the baked address is somebody else's:

```
cd app && python set-lan.py
```

`python make_icon.py` in the same folder redraws the launcher icon and writes it
into `res/` directly. It does not go through `expo prebuild`, because prebuild
also rewrites `gradle.properties` and the manifest and would undo the ABI list,
the Kotlin daemon heap and the permission trim.

**Do not use the debug APK.** It expects the Expo dev client to fetch JS from
Metro, and on this machine that connection never completes: the app opens to a
blank white screen while Metro logs `ECONNRESET` forever. That path cost an hour
and there is no reason to walk it again.

**If you ever have to rebuild it**, three things on this machine will stop you,
and all three cost an hour to rediscover:

```
set JAVA_HOME=D:\androidddd\jbr
```

1. **JAVA_HOME must be set.** Without it `expo run:android` prints nothing at all
   and simply does not build. Android Studio's JDK is the one to use.
2. **`android\local.properties` needs FORWARD slashes.** A Java properties file
   reads backslash-U as a broken unicode escape, so the backslash version fails
   with a bare "Invalid file path" that names nothing. Write it as
   `sdk.dir=C:/Users/ankur/AppData/Local/Android/Sdk`
3. **Close the emulator while building.** It holds 4.6 GB, and with it running
   Kotlin never gets a heap: the build sits on `compileDebugKotlin` producing no
   class files at all and looks hung rather than failing. Build first, start the
   emulator after.

The app talks to `http://10.0.2.2:8010`, which is the emulator's name for this
laptop. **On a real handset** it must be the laptop's Wi-Fi address instead: the
app's first screen has a **Server address** button when it cannot connect, so you
can fix that in ten seconds without rebuilding. Find the address with `ipconfig`
and use `http://<that>:8010`.

---

## 2. The demo, in order

Roughly six minutes. The order matters: it goes from "is anything happening" to
"what do I do" to "and here is the thing no satellite can see".

### a. The problem, on the map (60s)

Open **http://localhost:8010**. Land on **Situation**.

> "This is Patna, 30 September 2019. 59,495 people are standing in water across
> 138 square kilometres. Real road network, real shelters, real population."

**Drag the time slider.** The water rises, the roads change colour, the level in
the top bar follows.

> "Green means a car still gets through. Orange means only on foot. Red means a
> boat. That is the whole product: not *where* the flood is, but *when each road
> stops working*."

### b. The number nobody else has (60s)

Click **Road timeline**.

> "Four columns, not two. 14,083 people have a deadline you can still work to.
> 22,734 were already cut off before this window even opened. Every other flood
> map merges those, and that makes 22,734 people look like they have time."

Point at the purple box.

> "17,225 people can only reach a shelter across a bridge, and a terrain model
> physically cannot tell you whether a bridge is open. So we do not guess. We
> print the number and tell the officer to send someone."

### c. Where they go (45s)

Click **Shelters**.

> "47,443 placed. Capacity is not assumed by building type, it is measured roof
> area divided by 3.5 square metres, which is the NDMA minimum standard. Our own
> guesses were wrong in both directions: a school we assumed held 500 measures
> 288, and one campus we assumed held 1,000 measures 10,020."

> "11,177 are beyond ninety minutes of any shelter with room. We show that
> instead of hiding it."

### d. The decision (45s)

Click **Act**.

> "Act when the probability beats the cost of acting divided by the cost of being
> wrong. Opening shelters is cheap, so it fires at 2%. Full evacuation is not, so
> it needs 55%. And the probability is computed from 50 ensemble members, not
> typed in."

Press **Approve the three**. It jumps to the **Audit log**.

> "Who, when, and why. A database row, not page state."

Optionally press **Override** and show that the backend refuses one without a
reason code.

### e. The moment that lands (90s)

Now the phone. Open the app on the emulator, side by side with the laptop.

> "Same system, opposite end. This person sees four things: how deep, where to
> go, which roads close and when, and whether a bridge is in the way. No district
> totals. No probability. Nothing they cannot act on."

Point at the bridge warning if the ward has one.

Tap **Report water** → *There is water here* → **Knee** → Send.

**Switch to the laptop.** Within four seconds the **Citizen reports** badge ticks
up and a blue pin pulses on the map.

> "That is the part that matters. Our own falsification test proved free radar
> cannot see water standing between buildings: out of 455,860 buildings in Patna
> it labelled 659 as flooded. The real 2019 disaster, Rajendra Nagar and
> Kankarbagh, is missing from our own flood map. A person outside their door is
> the only sensor that sees it, and this is that sensor."

Then tap **I cannot leave** → *Cannot be moved without a stretcher* → Send, and
show it arriving in **Help queue**.

> "Ordered by who can move least, not who asked first. Their phone number is
> stored scrambled under a key this district keeps, so the control room can tell
> the same person called twice without ever holding a list of flood victims'
> numbers. Not a plain hash: ten digits is small enough to hash all of them."

If a judge asks what the app collects, the whole answer is: the ward they picked,
what they typed, and optionally a phone number. It reads no GPS. Show them:

```
aapt2 dump permissions app-release.apk
```

It asks for INTERNET and VIBRATE.

### f. The close (60s)

Back on the laptop, in a terminal:

```
.venv\Scripts\python.exe demo.py
```

> "Nine seconds, no internet. It checks every input file is present, recomputes
> every number this project claims from the raw data, checks that our documents
> still agree with what the code just computed, and runs 44 backend tests. If any
> one of those fails it stops and says which."

> "So every number you just saw on both screens can be regenerated in front of
> you, offline, right now."

---

## 3. If something breaks

| what you see | what to do |
|---|---|
| Control room says **cached, no backend** | The backend died. Restart it. The page keeps working on its baked-in numbers, so keep talking; nothing on screen is fake, it is just not live. |
| Phone says **Cannot reach the district** | Tap **Server address**. On the emulator it is `http://10.0.2.2:8010`. On a real phone, `http://<laptop wifi ip>:8010`. |
| Phone says **Saved on this phone** after sending | That is the offline queue working, not a failure. Say so: "no network, so it is held on the device and goes automatically when there is." It is a feature, demo it deliberately if the wifi is bad. |
| Emulator is slow or dead | `START-DEMO.bat` still gives you the whole officer app. The citizen screen also exists as the phone panel in `out/pravaah_ui.html`. |
| The map is blank | You are on Delhi or Mahanadi in the district dropdown. The inlined map geometry is Patna's; the numbers still switch. Go back to Patna. |
| Somebody asks for the APK | `app\android\app\build\outputs\apk\debug\app-debug.apk` |

**Rule for the room:** nothing on either screen is a mockup, so if something
misbehaves, say what it actually is rather than covering. The whole pitch is that
this project reports its own limits, and behaving that way live is worth more
than a clean run.

---

## 4. The three questions you will be asked

**"Does the prediction actually work?"**
> Our fitted water level for the flood day was 48.70 m. CWC's published danger
> level for that gauge is 48.60 m, and we never looked at it while fitting. Ten
> centimetres apart, by a completely different method. Measured lead time was six
> days, against the 48 to 72 hours the problem statement asked for.

**"How do we know the population numbers are right?"**
> Summed over Patna district, GHS-POP reads 7,121,932. The Census of India count
> for the same district, carried forward at the district's own 2001 to 2011
> growth rate, gives 7,071,903. That is 0.7% apart. `census_check.py` runs it.

**"What does it not do?"**
> It cannot see urban pluvial flooding, and we proved that rather than assuming
> it. That is why the citizen report button exists, and it is written down in the
> README as the ceiling on the whole approach.

---

## 5. What each file is

| file | what |
|---|---|
| `START-DEMO.bat` | starts the backend and opens the control room |
| `http://localhost:8010` | **the officer app**, live |
| `http://localhost:8010/ui` | the layout walkthrough, if someone asks about design |
| `app/` | **the citizen app**, Expo React Native |
| `demo.py` | the offline proof, nine seconds |
| `PRAVAAH-SIMPLE.md` | the project in plain language |
| `PRAVAAH-COMPLETE.md` | every number and every proof |
