"""Step 5: what goes where. Assign everyone in the wet zone to a shelter that is
above the water, respecting capacity, minimising total travel time.

Min-cost flow, not a greedy nearest-shelter loop: nearest-first strands the last
wards at full shelters, which is exactly the failure an officer cannot afford."""
import json, pickle, sys, numpy as np, rasterio, networkx as nx
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from pravaah import config as _c, hazard
from scipy.spatial import cKDTree
from ortools.graph.python import min_cost_flow

EV    = sys.argv[1] if len(sys.argv) > 1 else "patna"
cfg_ev = _c.EVENTS[EV]
DEPTH = sys.argv[2] if len(sys.argv) > 2 else f"out/depth/{EV}_2019-09-30.tif"
# Capacity is MEASURED, not assumed. NDMA Guidelines on Minimum Standards of
# Relief, section 2(c): 3.5 sq m of covered area per person. The covered area
# is the building footprint inside each campus boundary. See build_shelters.py.
SHELTER_CSV = f"data/{EV}_shelters_measured.csv"
REACH_MIN = 90

G = pickle.load(open(f"data/{EV}_graph.pkl", "rb"))
with rasterio.open(DEPTH) as s:
    dep, tr, inv = s.read(1), s.transform, ~s.transform
pop = np.zeros(dep.shape, "float32")
from rasterio.warp import reproject, Resampling
pop = hazard.population(pop.shape, tr, "EPSG:4326", cfg_ev.aoi)

nodes = list(G.nodes()); xy = {}
for u, v, d in G.edges(data=True):
    xy.setdefault(u, (d["lon"], d["lat"])); xy.setdefault(v, (d["lon"], d["lat"]))
nid = [n for n in nodes if n in xy]
tree = cKDTree(np.array([xy[n] for n in nid]))

# ---- demand: people standing in water, snapped to the nearest road node ----
with rasterio.open(f"out/{EV}_permanent.tif") as _p: channel = _p.read(1).astype(bool)
wet = (dep > _c.WET_M) & ~channel   # below WET_M is noise, not flood
rr, cc = np.nonzero(wet & (pop > 0))
xs, ys = tr * (cc + .5, rr + .5)
_, k = tree.query(np.c_[xs, ys])
demand = {}
for i, p in zip(k, pop[rr, cc]): demand[nid[i]] = demand.get(nid[i], 0) + float(p)
demand = {n: int(round(p)) for n, p in demand.items() if p >= 1}
print(f"demand: {len(demand)} pickup points, {sum(demand.values()):,} people")

# ---- supply: shelters above the water, with measured capacity ----
import pandas as _pd
_sh = _pd.read_csv(SHELTER_CSV)
shelters = []
for _row_i, row in _sh.iterrows():
    lon, lat = float(row.lon), float(row.lat)
    c, r = inv * (lon, lat); r, c = int(r), int(c)
    if 0 <= r < dep.shape[0] and 0 <= c < dep.shape[1] and dep[r, c] > 0:
        continue                                   # the shelter itself is under water
    _, j = tree.query([lon, lat])
    nm = row["name"] if isinstance(row["name"], str) and row["name"].strip() else ""
    shelters.append(dict(name=nm or f"{row.kind} at {lat:.4f}N {lon:.4f}E",
                         kind=row.kind, cap=int(row.cap), node=nid[j],
                         lon=lon, lat=lat, roof=float(row.roof_m2),
                         # which line of the measured file this is. Matching an
                         # allocation back to a building by rounded coordinates
                         # loses a few every time: the two sides round a float
                         # differently and four of Patna's 55 open shelters
                         # silently reported nobody. A row number cannot drift.
                         row=int(_row_i)))
# Campuses were already merged by geometry in build_shelters.py. Two genuinely
# separate campuses can still snap to one road node; those are summed, not dropped.
byname = {}
for s_ in sorted(shelters, key=lambda x: -x["cap"]):
    if s_["node"] in byname: byname[s_["node"]]["cap"] += s_["cap"]
    else: byname[s_["node"]] = s_
shelters = list(byname.values())
def label(sh): return sh["name"]
print(f"supply: {len(shelters)} shelters above water, "
      f"{sum(s['cap'] for s in shelters):,} capacity")

# ---- travel time on the roads that still work ----
sh_nodes = {s["node"]: i for i, s in enumerate(shelters)}
arcs = []
for dn, ppl in demand.items():
    try:
        dist = nx.single_source_dijkstra_path_length(G, dn, cutoff=REACH_MIN, weight="minutes")
    except nx.NodeNotFound:
        continue
    for n, mins in dist.items():
        if n in sh_nodes: arcs.append((dn, sh_nodes[n], mins))
print(f"reachable demand-shelter pairs within {REACH_MIN} min: {len(arcs):,}")

# ---- min-cost flow ----
dn_list = sorted({a[0] for a in arcs})
di = {n: i for i, n in enumerate(dn_list)}
SRC = len(dn_list) + len(shelters); SNK = SRC + 1
mcf = min_cost_flow.SimpleMinCostFlow()
for n, i in di.items(): mcf.add_arc_with_capacity_and_unit_cost(SRC, i, demand[n], 0)
arc_of = {}
for dn, si, mins in arcs:
    a = mcf.add_arc_with_capacity_and_unit_cost(di[dn], len(dn_list)+si,
                                                demand[dn], int(round(mins*10)))
    arc_of[a] = (dn, si)
for i, s_ in enumerate(shelters):
    mcf.add_arc_with_capacity_and_unit_cost(len(dn_list)+i, SNK, s_["cap"], 0)
reachable_total = sum(demand[n] for n in dn_list)
stranded = {n: p for n, p in demand.items() if n not in di}
total = reachable_total
mcf.set_node_supply(SRC, total); mcf.set_node_supply(SNK, -total)

st = mcf.solve()
names = {0: "OPTIMAL", 1: "FEASIBLE"}
print(f"\nsolver: {names.get(st, st)}   people routed: ", end="")
if st != mcf.OPTIMAL:
    print("infeasible at full demand, re-solving as max-flow")
    st = mcf.solve_max_flow_with_min_cost()
served, pairs = {}, []
for a in range(mcf.num_arcs()):
    f = mcf.flow(a)
    if f and a in arc_of:
        dn, si = arc_of[a]
        served[si] = served.get(si, 0) + f
        pairs.append((dn, si, f))
print(f"{sum(served.values()):,} of {total:,}")
unserved = total - sum(served.values())
if stranded:
    print(f"STRANDED: {sum(stranded.values()):,} people at {len(stranded)} pickup points "
          f"have NO shelter within {REACH_MIN} min by any mode. The plan cannot reach them; "
          f"they need pre-positioned boats or air, and the dashboard must say so.")
print(f"total person-minutes: {mcf.optimal_cost()/10:,.0f}   "
      f"mean trip {mcf.optimal_cost()/10/max(sum(served.values()),1):.1f} min")
if unserved: print(f"UNSERVED: {unserved:,} people beyond {REACH_MIN} min of any shelter")

print(f"\n{'shelter':<44}{'kind':<17}{'assigned':>9}{'cap':>7}{'use':>7}")
print("-"*84)
for si, n in sorted(served.items(), key=lambda x: -x[1])[:14]:
    s_ = shelters[si]
    nm = s_["name"] or f"unnamed {s_['kind']} @{s_['lat']:.3f},{s_['lon']:.3f}"
    print(f"  {nm[:40]:<42}{s_['kind']:<17}{n:>9,}{s_['cap']:>7,}{n/s_['cap']:>7.0%}")
# check the claim in this file's docstring: is the solver actually better than
# greedy nearest-shelter? If not, delete the solver and ship the loop.
cap_left = {i: s_["cap"] for i, s_ in enumerate(shelters)}
best = {}
for dn, si, mins in arcs: best.setdefault(dn, []).append((mins, si))
greedy_cost = greedy_served = 0
for dn in sorted(best, key=lambda d: -demand[d]):
    left = demand[dn]
    for mins, si in sorted(best[dn]):
        if left <= 0: break
        take = min(left, cap_left[si])
        cap_left[si] -= take; left -= take
        greedy_cost += take*mins; greedy_served += take
opt = mcf.optimal_cost()/10
mcf_n = sum(served.values())
print()
print("SOLVER CHECK   compare on coverage first; a shorter average trip that leaves")
print("               people behind is not a better plan.")
print(f"  min-cost flow  {mcf_n:>7,} placed   {opt/max(mcf_n,1):5.1f} min mean")
print(f"  greedy nearest {greedy_served:>7,} placed   "
      f"{greedy_cost/max(greedy_served,1):5.1f} min mean")
print(f"  the solver places {mcf_n-greedy_served:+,} more people "
      f"at {opt/max(mcf_n,1) - greedy_cost/max(greedy_served,1):+.1f} min mean trip")
assert mcf_n >= greedy_served, (
    "greedy placed more people than the flow; the solver is not earning its place")

# each reporting unit needs ITS OWN shelter in the message, not the busiest one
pl = hazard.named_places(f"data/{EV}_osm_places.json")
ptree = cKDTree(np.array([[q[0], q[1]] for q in pl]))
pname = [q[2] for q in pl]
by_place = {}
for dn, si, f in pairs:
    lo, la = xy[dn]
    place = pname[ptree.query([lo, la])[1]]
    d_ = by_place.setdefault(place, {})
    d_[si] = d_.get(si, 0) + f
place_shelter = {p: dict(shelter=label(shelters[max(v, key=v.get)]),
                         people=sum(v.values()), shelters_used=len(v))
                 for p, v in by_place.items()}
print()
print("primary shelter per reporting unit:")
for p, v in sorted(place_shelter.items(), key=lambda x: -x[1]["people"])[:8]:
    print(f"  {p[:20]:<22}{v['people']:>6,} people -> {v['shelter'][:40]}")
json.dump(place_shelter, open(f"out/{EV}_place_shelter.json","w"), indent=1)
# Keyed by name, kept because several scripts read it that way. It is NOT safe
# to count with: Delhi has five separate buildings called "MCD Primary School",
# so five entries collapse into one and the total quietly loses four of them.
json.dump({label(shelters[si]): n for si, n in served.items()},
          open(f"out/{EV}_allocation.json","w"), indent=1)

# The allocation as a list, one row per site, keyed by nothing. Position is the
# only unique thing a building has: two schools can share a name, and two
# campuses that share a road node were already summed above, so the capacity
# here is the one the router actually filled against. Anything that counts
# people or sites must read this file and not the dict above.
json.dump([dict(name=label(shelters[si]), row=shelters[si]["row"],
                lat=shelters[si]["lat"], lon=shelters[si]["lon"],
                kind=shelters[si]["kind"], cap=shelters[si]["cap"], assigned=n)
           for si, n in sorted(served.items(), key=lambda kv: -kv[1])],
          open(f"out/{EV}_allocation_sites.json","w"), indent=1)
json.dump([dict(place=p, shelter=v["shelter"], people=v["people"],
                shelters_used=v["shelters_used"]) for p, v in place_shelter.items()],
          open(f"out/{EV}_assign.json","w"), indent=1)
print(f"\nshelters used: {len(served)} of {len(shelters)}   -> out/allocation.json")
