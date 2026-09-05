"""Pull Sentinel-1 RTC VV for the Patna 2019 flood pair, clipped to the AOI.
Windowed COG read: we fetch only the AOI, not the 1 GB scene."""
import json, os, urllib.parse, urllib.request
import numpy as np, rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

AOI = (84.90, 25.45, 85.35, 25.75)          # Patna: city + Ganga/Punpun confluence
PAIRS = {"baseline": "2019-09-18", "flood": "2019-09-30"}   # both relOrb 121 descending
OUT = "D:/claude/pravaah/data"

os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                  CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff")

def post(url, body):
    r = urllib.request.Request(url, json.dumps(body).encode(),
                               {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=90))

def sign(href):
    p = urllib.parse.urlparse(href)
    account = p.netloc.split(".")[0]
    container = p.path.lstrip("/").split("/")[0]
    tok = json.load(urllib.request.urlopen(
        f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{account}/{container}",
        timeout=60))["token"]
    return f"{href}?{tok}"

for label, day in PAIRS.items():
    res = post("https://planetarycomputer.microsoft.com/api/stac/v1/search",
               {"collections": ["sentinel-1-rtc"], "bbox": list(AOI),
                "datetime": f"{day}T00:00:00Z/{day}T23:59:59Z", "limit": 10})
    feats = [f for f in res["features"] if f["properties"].get("sat:relative_orbit") == 121]
    assert feats, f"no relOrb 121 scene on {day}"
    print(f"{label:8} {day}  scenes: {len(feats)}")

    mosaic = None
    for f in feats:
        with rasterio.open(sign(f["assets"]["vv"]["href"])) as src:
            b = transform_bounds("EPSG:4326", src.crs, *AOI)
            win = from_bounds(*b, src.transform).round_offsets().round_lengths()
            arr = src.read(1, window=win, boundless=True, fill_value=np.nan)
            prof = src.profile | {"height": arr.shape[0], "width": arr.shape[1],
                                  "transform": src.window_transform(win),
                                  "count": 1, "dtype": "float32", "compress": "deflate"}
        mosaic = arr if mosaic is None else np.where(np.isnan(mosaic), arr, mosaic)
        print(f"         tile {arr.shape}  valid {np.isfinite(arr).mean():.1%}")

    path = f"{OUT}/patna_{label}_vv.tif"
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(mosaic.astype("float32"), 1)
    print(f"         -> {path}  {mosaic.shape}  valid {np.isfinite(mosaic).mean():.1%}")
