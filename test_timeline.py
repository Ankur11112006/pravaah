"""Check the max-bottleneck cut-off against brute force on small random graphs.
If this fails, every evacuation deadline the system prints is wrong."""
import random, sys
import networkx as nx, numpy as np
sys.path.insert(0, ".")
from pravaah import timeline

def brute(G, src, shelters, thr, levels):
    """Highest level at which a path still exists, found by trying every level."""
    best = float("-inf")
    for L in levels:
        ok = [(u, v) for u, v, d in G.edges(data=True) if L - d["bed"] < thr]
        if not ok: continue
        S = G.edge_subgraph(ok)
        if src in S and any(s in S and nx.has_path(S, src, s) for s in shelters):
            best = max(best, L)
    return best

random.seed(7); np.random.seed(7)
checked = 0
for trial in range(40):
    n = random.randint(6, 14)
    G = nx.gnm_random_graph(n, random.randint(n, n*2), seed=trial)
    if G.number_of_edges() == 0: continue
    for u, v in G.edges():
        G[u][v]["bed"] = round(random.uniform(40, 50), 2)
        G[u][v]["structure"] = ""
    shelters = random.sample(list(G.nodes()), 2)
    sources = [x for x in G.nodes() if x not in shelters]
    thr = 0.30
    cut = timeline.cutoff_levels(G, sources, shelters, thr)
    grid = np.arange(39.0, 51.0, 0.01)
    for s in sources:
        got = cut[s]
        exp = brute(G, s, shelters, thr, grid)
        if exp == float("-inf"):
            assert got == float("-inf"), f"trial {trial} node {s}: got {got}, expected no route"
        else:
            # both are "highest level still passable"; allow one grid step
            assert abs(got - exp) <= 0.011 + 1e-9, \
                f"trial {trial} node {s}: cutoff {got:.3f} vs brute force {exp:.3f}"
        checked += 1
print(f"cutoff_levels matches brute force on {checked} source/graph cases")

# bridges must be routable but distinguishable
G = nx.Graph()
G.add_edge(0, 1, bed=41.0, structure="")
G.add_edge(1, 2, bed=41.0, structure="bridge")
with_b = timeline.cutoff_levels(G, [0], [2], 0.30, use_bridges=True)
without = timeline.cutoff_levels(G, [0], [2], 0.30, use_bridges=False)
# the deck does not flood, but the approach road still does, so the ordinary
# edge stays the bottleneck. A bridge must never RAISE a route's survival level.
assert abs(with_b[0] - 41.30) < 1e-9, f"bridge changed the bottleneck: {with_b[0]}"
assert without[0] == float("-inf"), "excluding bridges must break a bridge-only route"
print("bridge handling: does not become the bottleneck, and route dies without it")

# a bridge alone must not cap a route that is otherwise high and dry
H = nx.Graph()
H.add_edge(0, 1, bed=60.0, structure="")
H.add_edge(1, 2, bed=40.0, structure="bridge")
assert timeline.cutoff_levels(H, [0], [2], 0.30)[0] > 60.0,     "a low bridge deck must not drag down a high route"
print("bridge handling: a low deck does not drag down a high approach")

# hourly interpolation must stay inside the daily values it came from
rows = [("2019-09-18", 35155.0, 48.10, 214.0), ("2019-09-19", 38814.0, 48.33, 240.8)]
hrs, lv = timeline.hourly_levels(rows)
assert len(hrs) == len(lv) == 25, len(hrs)
assert 48.10 - 1e-9 <= lv.min() and lv.max() <= 48.33 + 1e-9, "interpolation overshoots"
print("hourly interpolation stays within its daily bounds")
