"""
simulate.py -- the SIMULATED sensor layers.

Everything in this file is synthetic and must be labeled SIMULATED in the UI.
The trick that makes it feel real: every layer is generated over the bounding
box of the REAL flight path, so the fake sensors "scan" exactly where the
drone actually flew.

Design notes:
- Deterministic (fixed seed) so the demo looks identical every run.
- Pure numpy/scipy -> easy to unit test, no plotting code in here.
- swap-in point: generate_dem() can later be replaced by a real SRTM /
  Copernicus DEM download for the same bounding box, and the rest of the
  app will not change at all.
"""

import numpy as np
from scipy.ndimage import gaussian_filter

GRID = 220  # resolution of the simulated rasters (GRID x GRID pixels)


def flight_bbox(df, pad_frac=0.15):
    """Bounding box of the real flight path, padded a little for margins."""
    lat0, lat1 = df["lat"].min(), df["lat"].max()
    lon0, lon1 = df["lon"].min(), df["lon"].max()
    pad_lat = (lat1 - lat0) * pad_frac or 1e-4
    pad_lon = (lon1 - lon0) * pad_frac or 1e-4
    return (lat0 - pad_lat, lat1 + pad_lat, lon0 - pad_lon, lon1 + pad_lon)


def _smooth_noise(rng, sigma, amplitude):
    """Random field blurred into smooth rolling shapes."""
    field = rng.normal(0, 1, (GRID, GRID))
    field = gaussian_filter(field, sigma)
    field /= max(np.abs(field).max(), 1e-9)
    return field * amplitude


def generate_dem(bbox, seed=7, buried_structure=False):
    """
    Synthetic terrain elevation (meters) over the bbox.
    Rolling ground + gentle regional slope. If buried_structure is True,
    a faint rectangular platform is added -- the kind of subtle relief
    anomaly archaeological LIDAR surveys look for.
    """
    rng = np.random.default_rng(seed)
    dem = 40.0                                   # base elevation
    dem = dem + _smooth_noise(rng, sigma=18, amplitude=6.0)   # big hills
    dem = dem + _smooth_noise(rng, sigma=5,  amplitude=1.2)   # small texture
    xx, yy = np.meshgrid(np.linspace(0, 1, GRID), np.linspace(0, 1, GRID))
    dem = dem + 3.0 * xx + 1.5 * yy              # regional slope

    if buried_structure:
        dem = add_buried_structure(dem)
    return dem


def add_buried_structure(dem):
    """
    Add a faint rectangular platform (~0.6 m, softened edges) to ANY dem --
    real or synthetic. This is what a buried building footprint looks like
    in archaeological LIDAR relief data. Always labeled SYNTHETIC ANOMALY.
    """
    n = dem.shape[0]
    r0, r1 = int(n * 0.40), int(n * 0.55)
    c0, c1 = int(n * 0.35), int(n * 0.62)
    bump = np.zeros_like(dem)
    bump[r0:r1, c0:c1] = 0.6
    return dem + gaussian_filter(bump, 2.5)


def hillshade(dem, azimuth_deg=315.0, altitude_deg=45.0):
    """
    Classic hillshade rendering (0..1) -- the grayscale relief look used
    in archaeological LIDAR papers. Light comes from the northwest.
    """
    az = np.radians(360.0 - azimuth_deg + 90.0)
    alt = np.radians(altitude_deg)
    gy, gx = np.gradient(dem)
    slope = np.pi / 2.0 - np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    shaded = (np.sin(alt) * np.sin(slope)
              + np.cos(alt) * np.cos(slope) * np.cos(az - aspect))
    return np.clip((shaded + 1) / 2, 0, 1)


def generate_thermal(bbox, seed=11, n_anomalies=3):
    """
    Synthetic ground temperature field (deg C) over the bbox:
    base temperature + smooth spatial variation + a few warm anomalies.
    Returns (field, list_of_anomaly_centers_in_grid_coords).
    """
    rng = np.random.default_rng(seed)
    temp = 24.0 + _smooth_noise(rng, sigma=14, amplitude=2.5)

    centers = []
    xx, yy = np.meshgrid(np.arange(GRID), np.arange(GRID))
    for _ in range(n_anomalies):
        cx, cy = rng.integers(GRID*0.2, GRID*0.8, 2)
        strength = rng.uniform(3.0, 6.0)          # +3..+6 deg C hot spot
        radius = rng.uniform(GRID*0.03, GRID*0.07)
        temp += strength * np.exp(-((xx-cx)**2 + (yy-cy)**2) / (2*radius**2))
        centers.append((int(cx), int(cy)))
    return temp, centers


def sample_along_path(field, bbox, df):
    """
    Read the simulated field at the drone's real position for every log row.
    Produces the max/min/avg 'sensor readings over time' timeline, as if a
    downward camera with a small footprint were sampling the field.
    """
    lat0, lat1, lon0, lon1 = bbox
    rows = ((df["lat"] - lat0) / (lat1 - lat0) * (GRID - 1)).astype(int).clip(0, GRID-1)
    cols = ((df["lon"] - lon0) / (lon1 - lon0) * (GRID - 1)).astype(int).clip(0, GRID-1)

    center = field[rows, cols]
    # emulate a sensor footprint: sample a few offsets around the center pixel
    readings = []
    for dr, dc in [(0, 0), (2, 0), (-2, 0), (0, 2), (0, -2)]:
        r = (rows + dr).clip(0, GRID-1)
        c = (cols + dc).clip(0, GRID-1)
        readings.append(field[r.to_numpy(), c.to_numpy()])
    readings = np.stack(readings)
    return {
        "avg": center.to_numpy() if hasattr(center, "to_numpy") else center,
        "max": readings.max(axis=0),
        "min": readings.min(axis=0),
    }
