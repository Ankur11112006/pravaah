"""The 'when' output: which road changes mode at which hour, and the latest
moment a vehicle can still leave."""
import sys, pickle, numpy as np, datetime as dt
sys.path.insert(0, ".")
from pravaah import config, network, timeline

ev = config.EVENTS[sys.argv[1] if len(sys.argv) > 1 else "patna"]
DEM = ev.dem

G = network.build(f"data/{ev.name}_osm_roads.json", DEM)
beds = np.array([d["bed"] for _, _, d in G.edges(data=True)], dtype="float64")
print(f"road graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
print(f"  bed elevation known for {np.isfinite(beds).mean():.1%} of edges, "
      f"range {np.nanmin(beds):.1f} to {np.nanmax(beds):.1f} m")
pickle.dump(G, open(f"data/{ev.name}_graph.pkl", "wb"))

if ev.hazard != "stage":
    print()
    print(f"  {ev.name} is an observed-snapshot event, so there is no water level")
    print(f"  series and no road-mode timeline. The graph above is still built and")
    print(f"  used; roads take their depth from the single depth raster instead.")
    raise SystemExit(0)

rows = np.load(f"out/{ev.name}_stage.npy", allow_pickle=True)
hrs, lv = timeline.hourly_levels(rows)
print(f"  water level {lv.min():.2f} to {lv.max():.2f} m over "
      f"{hrs[0]:%d %b} to {hrs[-1]:%d %b}\n")

changed, worst_by_name = [], {}
for u, v, d in G.edges(data=True):
    t = timeline.edge_timeline(d["bed"], hrs, lv, config.MODES, config.ORDER,
                               d.get("structure", ""))
    if t is None or t["worst"] == "car": continue
    d["timeline"] = t
    changed.append((d, t))
    if d["name"]:
        p = worst_by_name.get(d["name"])
        if p is None or config.ORDER.index(t["worst"]) > config.ORDER.index(p[1]["worst"]):
            worst_by_name[d["name"]] = (d, t)

br = [d for _, _, d in G.edges(data=True) if d.get("structure") == "bridge"]
brn = sorted({d["name"] for d in br if d["name"]})
print(f"bridges: {len(br)} segments, {len(brn)} named. Status NOT determined from")
print(f"  terrain. These are the single points of failure and need human confirmation.")
names = ", ".join(n[:28] for n in brn[:6]) + (" ..." if len(brn) > 6 else "")
print(f"  named: {names}")
print()

km = sum(d["length"] for d, _ in changed)/1000
print(f"segments that stop carrying cars at some point: {len(changed):,}  ({km:.1f} km)")
print(f"named roads affected: {len(worst_by_name)}\n")
print(f"  {'road':<34}{'worst':<7}{'max d':>7}   first change")
print("  " + "-"*76)
for nm, (d, t) in sorted(worst_by_name.items(),
                         key=lambda x: -config.ORDER.index(x[1][1]["worst"]))[:12]:
    first = t["events"][0] if t["events"] else None
    when = f"{first[0]:%a %d %b %H:%M}  {first[1]} -> {first[2]}" if first else "already"
    print(f"  {nm[:32]:<34}{t['worst']:<7}{t['max_depth']:7.2f}   {when}")

# hour-by-hour count of what is passable, the officer's real question
print(f"\n  {'hour':<18}{'level':>7}{'car-only km lost':>18}{'boat-only segments':>20}")
for i in range(0, len(hrs), 48):
    road = [d for u, v, d in G.edges(data=True)
            if np.isfinite(d["bed"]) and d.get("structure") != "bridge"]
    lost = sum(d["length"] for d in road
               if timeline._cls(lv[i]-d["bed"], config.MODES) != "car")/1000
    boat = sum(1 for d in road
               if timeline._cls(lv[i]-d["bed"], config.MODES) == "boat")
    print(f"  {hrs[i]:%a %d %b %H:%M}{lv[i]:>7.2f}{lost:>18.1f}{boat:>20}")
