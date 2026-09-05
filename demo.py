"""Prove the whole system in front of someone, with the network unplugged.

    .venv/Scripts/python.exe demo.py

A live demo that depends on the internet is a demo that fails in a hall with bad
wifi, and a judge who sees a spinner concludes nothing was built. So everything
here reads from disk: the satellite scenes, the elevation, the population grid,
the road graph, the last national pull and the last C-Flood run are all cached.

It runs four things in order and stops at the first failure:

  1. preflight  every input the demo needs is on disk, named, and sized
  2. verify.py  recomputes every claimed number from that data
  3. stamp_docs --check  the documents agree with what was just computed
  4. test_api.py  the backend works, against a throwaway database

Only step 4 starts a process; nothing here opens a socket to the outside world.
"""
import os, subprocess, sys, time
sys.stdout.reconfigure(encoding="utf-8")

EV = "patna"
NEED = [
    ("data/dem_route.tif",              "Copernicus GLO-30 elevation"),
    ("data/hand.tif",                   "HAND, the predictor that failed"),
    ("data/flood_mask.tif",             "Sentinel-1 flood extent, 30 Sep 2019"),
    ("data/patna_baseline_vv.tif",      "Sentinel-1 baseline, 18 Sep 2019"),
    ("data/buildings_table.csv",        "buildings with HAND, elevation and label"),
    ("data/patna_buildings.gpkg",       "Microsoft building footprints"),
    ("data/patna_shelters_measured.csv", "shelters with measured roof area"),
    ("data/patna_osm_places.json",      "reporting unit names"),
    ("data/patna_district.json",        "Patna district boundary for the census check"),
    ("data/chennai_s1_query.json",      "the Chennai catalogue gap"),
    ("data/depth.tif",                  "FwDET depth"),
    (f"out/{EV}_stage.npy",             "fitted water level per day"),
    (f"out/{EV}_permanent.tif",         "river channel mask"),
    (f"out/depth/{EV}_2019-09-30.tif",  "depth at the peak"),
    (f"out/{EV}_exposure.csv",          "who is in the water"),
    (f"out/{EV}_deadlines.json",        "when each road closes"),
    (f"out/{EV}_allocation.json",       "min-cost flow result"),
    ("out/census_check.json",           "GHS-POP against the Census of India"),
    ("data/osdma_shelters.json",        "776 official Odisha shelters, from OSDMA"),
    ("data/mahanadi_buildings_google.gpkg", "Google footprints where Microsoft stops"),
    ("out/delhi_exposure.csv",          "Delhi: the embanked-river event"),
    ("out/mahanadi_deadlines.json",     "Mahanadi: routes from C-Flood frames"),
    ("data/mahanadi_shelters_measured.csv", "Mahanadi: OSDMA shelters, roofs measured"),
    ("out/national_data.json",          "last national pull, 354 CWC stations"),
    ("out/pravaah_national.html",       "page: India live"),
    ("out/pravaah_dashboard.html",      "page: the officer's dashboard"),
    ("out/pravaah_map.html",            "page: the map"),
    ("out/pravaah_citizen.html",        "page: what a resident sees"),
    ("out/pravaah_overview.html",       "page: the walkthrough"),
]
GLOB = [("data/GHS_POP_*.tif", "GHS-POP population tiles")]


def preflight():
    import glob
    print("=" * 74)
    print("1  PREFLIGHT   everything the demo reads, on disk")
    print("=" * 74)
    missing, total = [], 0
    for path, what in NEED:
        ok = os.path.exists(path)
        size = os.path.getsize(path) if ok else 0
        total += size
        print(f"  {'ok ' if ok else 'MISSING'}  {path:<38}{size/1e6:8.1f} MB  {what}")
        if not ok:
            missing.append(path)
    for pat, what in GLOB:
        hits = glob.glob(pat)
        size = sum(os.path.getsize(h) for h in hits)
        total += size
        print(f"  {'ok ' if hits else 'MISSING'}  {pat:<38}{size/1e6:8.1f} MB  "
              f"{what} ({len(hits)} files)")
        if not hits:
            missing.append(pat)
    print(f"\n  {total/1e9:.2f} GB cached. Nothing below needs the network.")
    if missing:
        print(f"\n  {len(missing)} inputs are missing, so the demo cannot run offline:")
        for m in missing:
            print(f"    {m}")
        print("  regenerate them with the fetch_*.py scripts while you still have a")
        print("  connection, then run this again.")
        return False
    return True


def step(n, title, cmd, tail=0):
    print("\n" + "=" * 74)
    print(f"{n}  {title}")
    print("=" * 74)
    r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = r.stdout.rstrip().splitlines()
    print("\n".join(out[-tail:] if tail and len(out) > tail else out))
    if r.returncode:
        print(r.stderr[-1500:])
        print(f"\nFAILED at step {n}. Nothing further is claimed.")
        sys.exit(1)
    return r


def main():
    t0 = time.time()
    if not preflight():
        sys.exit(1)
    step(2, "VERIFY       every claimed number, recomputed from that data",
         ["verify.py"])
    step(3, "DOCUMENTS    do they still agree with what was just computed",
         ["stamp_docs.py", "--check"])
    step(4, "BACKEND      the real app, a throwaway database, a real upload",
         ["test_api.py"], tail=6)
    print("\n" + "=" * 74)
    print(f"all four steps passed in {time.time() - t0:.0f}s, with no network")
    print("=" * 74)
    print("open out/pravaah_overview.html for the walkthrough, or start the")
    print("backend with:  .venv/Scripts/python.exe -m uvicorn api:app --port 8010")


if __name__ == "__main__":
    main()
