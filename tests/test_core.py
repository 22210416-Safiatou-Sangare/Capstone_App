"""
Run all project tests:   python tests/test_core.py
(no pytest needed — plain asserts, exits non-zero on failure)

Covers everything except the browser UI: ingestion, stats, simulation,
DEM sources (offline paths), and the pipeline standardizer with three
different raw-log unit conventions.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "pipeline"))

import dem_sources                     # noqa: E402
import ingest                          # noqa: E402
import simulate                        # noqa: E402
from standardize_log import standardize  # noqa: E402

PASS = 0


def ok(name):
    global PASS
    PASS += 1
    print(f"  ✓ {name}")


# ---------------------------------------------------------------- ingestion
df = ingest.load_flight(ROOT / "data" / "sample_flight.csv")
assert list(df.columns) == ingest.SCHEMA
assert len(df) > 100
ok("sample flight loads and matches schema")

stats = ingest.mission_stats(df)
assert stats["duration_s"] > 60 and stats["distance_m"] > 500
ok("mission stats are sane")

bad = df.rename(columns={"lat": "latitude"})
try:
    import io
    ingest.load_flight(io.StringIO(bad.to_csv(index=False)))
    raise AssertionError("validator accepted a broken schema!")
except ingest.BadFlightFile:
    ok("validator rejects wrong schema")

# --------------------------------------------------------------- simulation
bbox = simulate.flight_bbox(df)
dem = simulate.generate_dem(bbox, buried_structure=True)
assert dem.shape == (simulate.GRID, simulate.GRID) and not np.isnan(dem).any()
ok("synthetic DEM generates")

dem2 = simulate.add_buried_structure(simulate.generate_dem(bbox))
assert (dem2 - simulate.generate_dem(bbox)).max() > 0.3
ok("buried-structure anomaly adds relief")

shade = simulate.hillshade(dem)
assert 0 <= shade.min() and shade.max() <= 1
ok("hillshade in [0,1]")

thermal, centers = simulate.generate_thermal(bbox)
series = simulate.sample_along_path(thermal, bbox, df)
assert len(series["avg"]) == len(df)
assert (series["max"] >= series["min"]).all()
ok("thermal field + path sampling consistent")

# -------------------------------------------------------------- dem sources
d, label = dem_sources.get_dem(bbox, allow_online=False, buried_structure=True)
assert d.shape == (simulate.GRID, simulate.GRID) and label == "synthetic"
ok("dem_sources offline fallback works")

coarse = np.arange(16, dtype=float).reshape(4, 4)
up = dem_sources._upsample(coarse, 20)
assert up.shape == (20, 20) and abs(up[0, 0] - 0) < 1e-9 and abs(up[-1, -1] - 15) < 1e-9
ok("bilinear upsample preserves corners")

# ----------------------------------------------- pipeline: 3 unit dialects
def fake_raw(time_unit, coord_scaled, alt_cm, deci_att):
    n = 400
    t = np.arange(n) * (10_000 if time_unit == "us" else 10)
    lat = 36.85 + np.linspace(0, 5e-4, n)
    lon = 34.75 + np.linspace(0, 8e-4, n)
    return pd.DataFrame({
        "time (us)": t,
        "GPS_coord[0]": lat * (1e7 if coord_scaled else 1),
        "GPS_coord[1]": lon * (1e7 if coord_scaled else 1),
        "GPS_altitude": np.linspace(0, 30, n) * (100 if alt_cm else 1),
        "GPS_speed (m/s)": np.full(n, 8.0),
        "attitude[0]": np.full(n, 25 if deci_att else 2.5),
        "attitude[1]": np.full(n, -80 if deci_att else -8.0),
        "attitude[2]": np.full(n, 900 if deci_att else 90.0),
        "vbat (V)": np.linspace(25.2, 25.0, n),
        "GPS_numSat": np.full(n, 14),
    })


for kwargs, tag in [
    (dict(time_unit="us", coord_scaled=True, alt_cm=True, deci_att=True),
     "INAV-style: us, int coords, cm alt, decideg"),
    (dict(time_unit="us", coord_scaled=False, alt_cm=False, deci_att=False),
     "already-converted: degrees, m, deg"),
    (dict(time_unit="us", coord_scaled=True, alt_cm=False, deci_att=True),
     "mixed: int coords, m alt, decideg"),
]:
    rep = []
    out = standardize(fake_raw(**kwargs), rep)
    assert list(out.columns) == ingest.SCHEMA
    assert out["lat"].between(36.8, 36.9).all(), tag
    assert out["alt_m"].max() < 40, tag
    assert out["yaw_deg"].between(0, 360).all(), tag
    # output must pass the app's own validator -> the contract holds
    import io
    ingest.load_flight(io.StringIO(out.to_csv(index=False)))
    ok(f"pipeline handles {tag}")

# alias failure message is helpful
try:
    standardize(fake_raw(time_unit="us", coord_scaled=True, alt_cm=True,
                         deci_att=True).rename(columns={"vbat (V)": "weird"}), [])
    raise AssertionError("should have failed on missing vbat column")
except SystemExit as e:
    assert "ALIASES" in str(e)
    ok("missing-column error tells you how to fix it")

print(f"\nALL {PASS} TESTS PASSED")
