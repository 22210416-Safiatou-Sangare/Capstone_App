"""
generate_sample_flight.py
-------------------------
Creates a FAKE but realistic flight log CSV in the official project schema:

    time_ms, lat, lon, alt_m, ground_speed_ms, roll_deg, pitch_deg,
    yaw_deg, vbat_v, sat_count

It simulates a classic "lawnmower" survey pattern (the same pattern real
LIDAR survey drones fly) over an outdoor field, at 5 Hz.

WHY THIS EXISTS: it lets the app team (Muath) and the pipeline team
(Safiatou) build and test EVERYTHING before the drone even exists.
When real flights happen, the real CSV simply replaces this file.

Usage:
    python scripts/generate_sample_flight.py
Output:
    data/sample_flight.csv
"""

import numpy as np
import pandas as pd
from pathlib import Path

# ----------------------------- settings ------------------------------------
SEED = 42                     # fixed seed -> same file every time (reproducible)
HZ = 5                        # samples per second (matches pipeline output rate)
FIELD_LAT = 36.8500           # southwest corner of the survey field (decimal deg)
FIELD_LON = 34.7500
FIELD_W_M = 150.0             # field width  (east-west), meters
FIELD_H_M = 100.0             # field height (north-south), meters
N_LANES = 6                   # number of lawnmower lanes
CRUISE_ALT = 30.0             # survey altitude, meters
CRUISE_SPEED = 8.0            # m/s
VBAT_FULL, VBAT_END = 25.2, 21.8   # 6S LiPo: 4.2 V/cell -> ~3.63 V/cell

# meters -> degrees conversion (approximate, fine at this scale)
M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LON = 111_320.0 * np.cos(np.radians(FIELD_LAT))


def build_waypoints():
    """Corner points of the lawnmower pattern, in local meters (x=E, y=N)."""
    pts = [(0.0, 0.0)]                      # takeoff corner
    lane_gap = FIELD_H_M / (N_LANES - 1)
    for i in range(N_LANES):
        y = i * lane_gap
        if i % 2 == 0:                      # fly east on even lanes...
            pts += [(0.0, y), (FIELD_W_M, y)]
        else:                               # ...and back west on odd lanes
            pts += [(FIELD_W_M, y), (0.0, y)]
    pts.append(pts[-1])                     # land where the last lane ended
    return np.array(pts)


def interpolate_path(pts, speed, hz):
    """Turn corner waypoints into a smooth position sample every 1/hz seconds."""
    xs, ys = [], []
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        dist = np.hypot(x1 - x0, y1 - y0)
        n = max(int(dist / speed * hz), 1)
        t = np.linspace(0, 1, n, endpoint=False)
        xs.append(x0 + (x1 - x0) * t)
        ys.append(y0 + (y1 - y0) * t)
    return np.concatenate(xs), np.concatenate(ys)


def main():
    rng = np.random.default_rng(SEED)
    x, y = interpolate_path(build_waypoints(), CRUISE_SPEED, HZ)
    n = len(x)
    t_ms = (np.arange(n) * (1000 / HZ)).astype(int)

    # --- altitude: ramp up (takeoff), hold with small noise, ramp down -----
    ramp = min(HZ * 8, n // 4)                       # ~8 s takeoff / landing
    alt = np.full(n, CRUISE_ALT)
    alt[:ramp] = np.linspace(0, CRUISE_ALT, ramp)
    alt[-ramp:] = np.linspace(CRUISE_ALT, 0, ramp)
    alt += rng.normal(0, 0.35, n)                    # baro noise
    alt = alt.clip(min=0)

    # --- speed from actual positions (so it's self-consistent) -------------
    dx, dy = np.gradient(x), np.gradient(y)
    speed = np.hypot(dx, dy) * HZ + rng.normal(0, 0.25, n)
    speed = speed.clip(min=0)

    # --- attitude: yaw follows travel direction, small roll/pitch noise ----
    yaw = (np.degrees(np.arctan2(dx, dy)) + 360) % 360   # 0 = North
    roll = rng.normal(0, 2.5, n)
    pitch = -8 + rng.normal(0, 2.0, n)               # nose-down while cruising
    pitch[:ramp] = rng.normal(0, 2.0, ramp)
    pitch[-ramp:] = rng.normal(0, 2.0, ramp)

    # --- battery drains roughly linearly with small sag noise --------------
    vbat = np.linspace(VBAT_FULL, VBAT_END, n) + rng.normal(0, 0.04, n)

    # --- GPS satellites: healthy fix wobbling between 11 and 17 ------------
    sats = np.clip(14 + rng.integers(-3, 4, n), 8, 20)

    df = pd.DataFrame({
        "time_ms": t_ms,
        "lat": FIELD_LAT + y / M_PER_DEG_LAT,
        "lon": FIELD_LON + x / M_PER_DEG_LON,
        "alt_m": alt.round(2),
        "ground_speed_ms": speed.round(2),
        "roll_deg": roll.round(2),
        "pitch_deg": pitch.round(2),
        "yaw_deg": yaw.round(1),
        "vbat_v": vbat.round(2),
        "sat_count": sats,
    })

    out = Path(__file__).resolve().parents[1] / "data" / "sample_flight.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} rows ({t_ms[-1]/1000:.0f} s flight) -> {out}")


if __name__ == "__main__":
    main()
