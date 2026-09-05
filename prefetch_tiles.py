"""Pull the basemap for every district into the server's cache, once.

The control room and the app both read tiles from this server, never from
OpenStreetMap directly: the OSMF tile policy forbids bulk downloading, and a
venue full of phones each pulling a few hundred tiles is exactly that. This
fetches each tile once, politely, so the demo works with the wifi unplugged.

    .venv/Scripts/python.exe prefetch_tiles.py
"""
import sys, time
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")
from pravaah import config, tiles

ZMIN, ZMAX = 9, 13
for name, ev in config.EVENTS.items():
    w, s, e, n = ev.aoi
    todo = tiles.tiles_for(w, s, e, n, ZMIN, ZMAX)
    have = sum(1 for t in todo if tiles.have(*t))
    print(f"{name:9} {len(todo):>5} tiles, {have} already cached")
    t0, got, bad = time.time(), 0, 0
    for z, x, y in todo:
        if tiles.have(z, x, y):
            continue
        if tiles.fetch(z, x, y) is None:
            bad += 1
        else:
            got += 1
        if (got + bad) % 50 == 0:
            print(f"    {got + bad} fetched, {time.time() - t0:.0f}s")
    print(f"    done: {got} new, {bad} failed, {time.time() - t0:.0f}s")
