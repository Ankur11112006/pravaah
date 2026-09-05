"""Can a free DEM resolve half-metre flood depths on the Gangetic plain?
Measure the DEM's own local roughness where the ground is genuinely flat.
If roughness >= the depths we claim to report, depth is unrecoverable."""
import numpy as np, rasterio
from rasterio.windows import from_bounds
from scipy.ndimage import uniform_filter

AOI = (84.90, 25.45, 85.35, 25.75)
for name, path in [("Copernicus GLO-30","data/dem_route.tif"),
                   ("NASADEM","tmp/dem_nasadem.tif"),
                   ("ALOS AW3D30","tmp/dem_alos-dem.tif")]:
    try:
        with rasterio.open(path) as d:
            w = from_bounds(*AOI, d.transform).round_offsets().round_lengths()
            a = d.read(1, window=w).astype("float32")
    except Exception as e:
        print(f"{name:<20} unavailable ({e.__class__.__name__})"); continue
    a[a <= 0] = np.nan
    # local std over a 5x5 (150 m) window: on flat floodplain this is DEM noise
    m  = uniform_filter(np.nan_to_num(a), 5)
    m2 = uniform_filter(np.nan_to_num(a)**2, 5)
    rough = np.sqrt(np.maximum(m2 - m**2, 0))
    flat = rough < np.nanpercentile(rough, 60)      # the flattest 60% of the AOI
    r = rough[flat & np.isfinite(a)]
    print(f"{name:<20} local vertical roughness over flat ground: "
          f"med={np.median(r):.2f} m  p90={np.percentile(r,90):.2f} m")

print("\ndepth classes the spec wants to report: 0-0.3 m | 0.3-1 m | >1 m")
print("road thresholds the spec needs:          0.3 | 0.5 | 1.5 m")
