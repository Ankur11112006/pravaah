"""Build the control-room page: one file, its data inlined, no server needed.

The page is served by api.py at "/" during a demo, so its API base is its own
origin and there is no address to type. Opened straight off disk it still works,
from the figures baked in here, and says so in the top right rather than
pretending to be live.

All three districts are inlined now. The page used to carry Patna's geometry
alone and print "no map for this district yet" over the other two while their
numbers sat in the panel beside it, which is the most confusing thing a control
room can show: right numbers, wrong city, nothing saying which.

    .venv/Scripts/python.exe build_control.py
"""
import io, json, os, sys, urllib.request
sys.stdout.reconfigure(encoding="utf-8")

SHELL, OUT = "control_shell.html", "out/pravaah_control.html"
API = "http://127.0.0.1:8010"
EVENTS = ["patna", "delhi", "mahanadi"]


def api(path):
    try:
        with urllib.request.urlopen(API + path, timeout=8) as r:
            return json.load(r)
    except Exception:
        return None


def pack(name):
    """One district's geometry, thinned for the wire."""
    src = json.load(io.open(f"out/{name}_map_data.json", encoding="utf-8"))

    # Every second vertex and four decimals is about three metres, finer than
    # the 90 m grid drawn underneath it.
    edges = []
    for geom, bed, bridge, nm in src["edges"]:
        g = geom if len(geom) <= 4 else geom[::2] + [geom[-1]]
        edges.append([[[round(x, 4), round(y, 4)] for x, y in g],
                      None if bed is None else round(bed, 1), bridge,
                      nm[:26] if (bridge or nm) else ""])

    # Patna's level series is hourly over a week. Every sixth hour is still a
    # smooth animation and a sixth of the bytes. A frame series is already
    # coarse, so it is kept whole.
    step = 6 if src["mode"] == "level" else 1
    return dict(
        aoi=src["aoi"], mode=src["mode"], hazard=src["hazard"],
        grid=src["grid"], edges=edges, modes=src["modes"],
        cutoff_unit=src.get("cutoff_unit"),
        people=[[round(p[0], 4), round(p[1], 4), p[2], p[3],
                 None if p[4] is None else round(p[4], 1),
                 None if p[5] is None else round(p[5], 1)] for p in src["people"]],
        shelters=[[round(s[0], 4), round(s[1], 4), s[2], s[3], s[4][:34]]
                  for s in src["shelters"]],
        hours=src["hours"][::step],
        levels=None if src["levels"] is None
               else [round(v, 2) for v in src["levels"][::step]],
    )


def main():
    d = dict(events={}, seed={})
    for name in EVENTS:
        if not os.path.exists(f"out/{name}_map_data.json"):
            print(f"  {name}: no map data, run build_map_data.py {name}")
            continue
        e = pack(name)
        d["events"][name] = e
        nf = len(e["grid"].get("frames", [1]))
        print(f"  {name:9} {len(e['edges']):>6,} roads  {len(e['people']):>5,} points"
              f"  {len(e['shelters']):>4} shelters  {len(e['hours']):>3} steps"
              f"  {nf} grid{'s' if nf > 1 else ''}")

    # The offline fallback, taken from the running backend when there is one, so
    # a page opened off a USB stick shows the same numbers the API serves.
    if api("/api/health") is None:
        print("  backend not running: the page falls back to whatever seed was "
              "last built in. Start api.py and rerun to refresh it.")
    for name in EVENTS:
        plan, units = api(f"/api/events/{name}/plan"), api(f"/api/events/{name}/units")
        sh = api(f"/api/events/{name}/shelters")
        fc = api(f"/api/events/{name}/forecast")
        d["seed"][name] = dict(plan=plan or {}, units=units or [],
                               shelters=(sh or {}).get("shelters", [])[:8],
                               forecast=fc or {})
    nat = api("/api/national")
    d["seed"]["national"] = dict(counts=(nat or {}).get("counts", {}),
                                 alerts=(nat or {}).get("alerts", 0))

    shell = io.open(SHELL, encoding="utf-8").read()
    if "__DATA__" not in shell:
        sys.exit(f"{SHELL} has no __DATA__ placeholder")
    io.open(OUT, "w", encoding="utf-8").write(
        shell.replace("__DATA__", json.dumps(d, separators=(",", ":"))))
    print(f"  wrote {OUT}  {os.path.getsize(OUT) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
