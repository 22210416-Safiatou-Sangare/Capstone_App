"""
dem_sources.py -- where the terrain layer's elevation data comes from.

Three sources, tried in order:
  1. LOCAL CACHE  (data/dem_cache_<bbox>.npz)  -> instant, offline, demo-safe
  2. ONLINE FETCH (open-elevation public API)  -> real ~30-90 m SRTM data
  3. SYNTHETIC    (simulate.generate_dem)      -> always works

The presentation demo therefore NEVER depends on conference-room Wi-Fi:
fetch once at home, the cache file makes every later run offline & instant.
"""

from pathlib import Path

import numpy as np

import simulate

CACHE_DIR = Path(__file__).resolve().parents[1] / "data"
FETCH_GRID = 32          # 32x32 = 1024 points, ~11 API batches
TIMEOUT_S = 20


def _cache_path(bbox):
    lat0, lat1, lon0, lon1 = (round(v, 4) for v in bbox)
    return CACHE_DIR / f"dem_cache_{lat0}_{lat1}_{lon0}_{lon1}.npz"


def _fetch_open_elevation(bbox):
    """Query real SRTM elevations on a coarse grid; returns (grid, ok)."""
    import requests  # local import: app runs fine without network

    lat0, lat1, lon0, lon1 = bbox
    lats = np.linspace(lat0, lat1, FETCH_GRID)
    lons = np.linspace(lon0, lon1, FETCH_GRID)
    pts = [{"latitude": float(la), "longitude": float(lo)}
           for la in lats for lo in lons]

    elev = []
    for i in range(0, len(pts), 100):                    # API batch limit
        r = requests.post("https://api.open-elevation.com/api/v1/lookup",
                          json={"locations": pts[i:i+100]}, timeout=TIMEOUT_S)
        r.raise_for_status()
        elev += [p["elevation"] for p in r.json()["results"]]

    grid = np.array(elev, dtype=float).reshape(FETCH_GRID, FETCH_GRID)
    return grid


def _upsample(coarse, size):
    """Bilinear upsample a coarse grid to (size x size) with pure numpy."""
    src = np.linspace(0, 1, coarse.shape[0])
    dst = np.linspace(0, 1, size)
    tmp = np.empty((coarse.shape[0], size))
    for i, row in enumerate(coarse):                     # interp rows...
        tmp[i] = np.interp(dst, src, row)
    out = np.empty((size, size))
    for j in range(size):                                # ...then columns
        out[:, j] = np.interp(dst, src, tmp[:, j])
    return out


def get_dem(bbox, allow_online=False, buried_structure=False):
    """
    Return (dem_array GRIDxGRID, source_label). source_label is one of
    'real (cached)', 'real (downloaded)', 'synthetic'.
    A synthetic buried-structure bump can be added on top of ANY source,
    since the anomaly is a simulation feature by definition.
    """
    dem, label = None, "synthetic"

    cache = _cache_path(bbox)
    if cache.exists():
        dem = np.load(cache)["dem"]
        label = "real (cached)"
    elif allow_online:
        try:
            coarse = _fetch_open_elevation(bbox)
            dem = _upsample(coarse, simulate.GRID)
            CACHE_DIR.mkdir(exist_ok=True)
            np.savez_compressed(cache, dem=dem)
            label = "real (downloaded)"
        except Exception:
            dem = None                                   # fall through

    if dem is None:
        dem = simulate.generate_dem(bbox, buried_structure=False)

    if buried_structure:
        dem = simulate.add_buried_structure(dem)
    return dem, label
