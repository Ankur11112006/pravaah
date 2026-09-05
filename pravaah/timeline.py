"""The 'when' layer. Everything the product claims that a map cannot give you."""
import datetime as dt
import numpy as np

def hourly_levels(stage_rows, a=None, b=None):
    """Daily GloFAS -> hourly water level by linear interpolation.
    The discharge is daily; the level between two days is interpolated, not
    invented, and it is a smooth quantity so this is honest."""
    days = [dt.date.fromisoformat(r[0]) for r in stage_rows]
    lv   = np.array([float(r[2]) for r in stage_rows])
    t0 = dt.datetime.combine(days[0], dt.time())
    hrs, out = [], []
    for i in range(len(days)-1):
        for h in range(24):
            hrs.append(t0 + dt.timedelta(days=i, hours=h))
            out.append(lv[i] + (lv[i+1]-lv[i]) * h/24)
    hrs.append(t0 + dt.timedelta(days=len(days)-1)); out.append(lv[-1])
    return hrs, np.array(out)

def edge_timeline(bed, hrs, levels, modes, order, structure=""):
    """When this segment stops carrying each mode, and when it comes back.
    Bridges return None: terrain cannot tell us, and we do not pretend."""
    if structure == "bridge" or not np.isfinite(bed): return None
    d = np.maximum(0.0, levels - bed)
    cls = np.empty(len(d), dtype=object)
    for i, x in enumerate(d):
        for lim, m in modes:
            if x < lim: cls[i] = m; break
    ev = []
    for i in range(1, len(cls)):
        if cls[i] != cls[i-1]:
            ev.append((hrs[i], cls[i-1], cls[i],
                       "closing" if order.index(cls[i]) > order.index(cls[i-1]) else "reopening"))
    return dict(events=ev, worst=order[max(order.index(c) for c in cls)],
                max_depth=float(d.max()))

def cutoff_levels(G, sources, shelters, threshold, use_bridges=True, key="bed"):
    """For every source, the last point at which a route to ANY shelter exists.

    With the default key this is a water LEVEL: a path is usable at level L when
    every edge on it has bed > L - threshold, so the best a source can tolerate
    is the path maximising its minimum bed, the maximum-bottleneck path. Kruskal
    in descending order gives that for every source in one pass, instead of a
    shortest-path search per hour.

    The same argument holds for any per-edge quantity where larger means "lasts
    longer", so `key` lets a C-Flood event pass the frame index at which each
    edge becomes impassable and get back the frame at which each source is cut
    off. One verified algorithm, two hazard modes, rather than a second
    implementation to keep in step with this one.
    """
    BRIDGE_BED = 1e6      # a deck is above the water; whether it survives is unknown
    edges = sorted((((BRIDGE_BED if d.get("structure") == "bridge" else d[key]), u, v)
                    for u, v, d in G.edges(data=True)
                    if np.isfinite(d[key]) and
                    (use_bridges or d.get("structure") != "bridge")),
                   key=lambda e: -e[0])
    parent, rank = {}, {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(x, y):
        rx, ry = find(x), find(y)
        if rx == ry: return rx
        if rank.get(rx, 0) < rank.get(ry, 0): rx, ry = ry, rx
        parent[ry] = rx
        if rank.get(rx, 0) == rank.get(ry, 0): rank[rx] = rank.get(rx, 0) + 1
        return rx
    has_shelter = {}
    for s_ in shelters: has_shelter[find(s_)] = True
    pending, out = set(sources), {}
    for bed, u, v in edges:
        ru, rv = find(u), find(v)
        sh = has_shelter.get(ru, False) or has_shelter.get(rv, False)
        r = union(u, v)
        has_shelter[r] = sh
        if not sh: continue
        for node in list(pending):
            if find(node) == r:
                out[node] = bed + threshold      # level at which this route dies
                pending.discard(node)
        if not pending: break
    for node in pending: out[node] = float("-inf")   # never connected to a shelter
    return out

def last_hour_below(hrs, levels, cutoff):
    """Latest hour at which the water is still below a cut-off level."""
    ok = np.nonzero(levels < cutoff)[0]
    return (hrs[ok[-1]], ok[-1]) if len(ok) else (None, None)


def _cls(depth, modes):
    depth = max(0.0, depth)
    for lim, m in modes:
        if depth < lim: return m


def read_deadlines(path):
    """The plan file, tolerating the flat shape it used to have.

    It now carries its unit: `car_cutoff` is a water level in metres for a
    stage-fitted event and a frame index for a C-Flood one. Older files are a
    bare mapping of node to record, which is assumed to be metres because that
    is the only kind that existed then.
    """
    import json
    d = json.load(open(path, encoding="utf-8"))
    if "points" in d:
        return d["points"], d.get("unit", "metres"), d.get("hours")
    return d, "metres", None


def survival(points, first, last):
    """Split a plan's population four ways, the way build_plan reports it.

    Survives / closes inside the window / was already gone when it opened / never
    had a route. The middle two are the ones that must not be merged: one is a
    deadline an officer can work to, the other is a fact."""
    out = dict(survives=0, closes=0, gone=0, never=0)
    for v in points.values():
        c, n = v["car_cutoff"], v["people"]
        if c == float("-inf"):
            out["never"] += n
        elif c < first:
            out["gone"] += n
        elif c <= last:
            out["closes"] += n
        else:
            out["survives"] += n
    return out
