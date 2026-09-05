"""Client for C-Flood, inf.cwc.gov.in, CWC + NRSC + C-DAC under the National
Supercomputing Mission.

This is India's operational inundation forecast: a hydrodynamic run published
daily to a dated GeoServer workspace as depth rasters every 3 hours out to 48
hours, at 30 m in UTM. Depth in metres, which is exactly the input the rest of
this pipeline consumes.

Coverage today is the Mahanadi basin only (Upper, Mid, Delta), not all of India.
The viewer needs no login and neither does this.
"""
import datetime as dt, re, urllib.parse, urllib.request

BASE = "https://inf.cwc.gov.in/geoserver"
UA = {"User-Agent": "Mozilla/5.0 (pravaah flood research)"}
LEAD_SECONDS = list(range(0, 172801, 10800))      # 0 to 48 h, every 3 h


def _get(url, timeout=600):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                  timeout=timeout).read()


def capabilities():
    return _get(f"{BASE}/wms?service=WMS&version=1.3.0&REQUEST=GetCapabilities",
                timeout=900).decode("utf-8", "replace")


def layers(caps=None):
    """Every published layer, as {workspace: [layer, ...]}."""
    caps = caps or capabilities()
    out = {}
    for n in re.findall(r"<Name>([^<]+)</Name>", caps):
        if ":" in n:
            ws, ly = n.split(":", 1)
            out.setdefault(ws, []).append(ly)
    return out


def runs(caps=None):
    """Dated model runs, newest first, as [(date, workspace, [layers])]."""
    got = []
    for ws, ly in layers(caps).items():
        m = re.fullmatch(r"workspace_(\d{2})_(\d{2})_(\d{4})", ws)
        if m:
            d, mo, y = map(int, m.groups())
            got.append((dt.date(y, mo, d), ws, sorted(ly)))
    return sorted(got, reverse=True)


def frames(workspace, layer_list):
    """Forecast frames in one run, as {lead_hours: layer_name}, for that run's
    own date. Workspaces also carry the tail of the previous run, so the date in
    the LAYER name is what decides, not the workspace name."""
    m = re.fullmatch(r"workspace_(\d{2}_\d{2}_\d{4})", workspace)
    if not m:
        return {}
    tag = m.group(1)
    out = {}
    for ly in layer_list:
        mm = re.fullmatch(rf"(.+)_{tag}_(\d+)(?:\.0)?", ly)
        if mm:
            out[int(mm.group(2)) // 3600] = ly
    return dict(sorted(out.items()))


def fetch(workspace, layer, path):
    """Download one depth raster as a GeoTIFF. Depth is in metres."""
    q = urllib.parse.urlencode({
        "service": "WCS", "version": "2.0.1", "request": "GetCoverage",
        "coverageId": layer, "format": "image/geotiff"})
    data = _get(f"{BASE}/{workspace}/wcs?{q}", timeout=1800)
    if data[:4] not in (b"II*\x00", b"MM\x00*"):
        raise SystemExit(f"C-Flood did not return a GeoTIFF for {layer}: "
                         f"{data[:160].decode('utf-8', 'replace')}")
    open(path, "wb").write(data)
    return len(data)


def latest(caps=None):
    """The newest run that actually has frames."""
    for d, ws, ly in runs(caps):
        f = frames(ws, ly)
        if f:
            return d, ws, f
    return None, None, {}
