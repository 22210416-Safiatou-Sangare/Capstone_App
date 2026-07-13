"""
ingest.py -- load and validate flight CSV files.

The ONE rule of this project: every flight file must match the schema below.
If Safiatou's pipeline and this file agree, the whole project holds together.
"""

import pandas as pd

# The frozen project schema (column name -> expected meaning/unit)
SCHEMA = [
    "time_ms",           # milliseconds since log start
    "lat", "lon",        # decimal degrees, WGS84
    "alt_m",             # meters above takeoff
    "ground_speed_ms",   # meters / second
    "roll_deg", "pitch_deg", "yaw_deg",
    "vbat_v",            # battery volts
    "sat_count",         # GPS satellites in fix
]

MIN_SATS = 6  # rows below this fix quality get dropped


class BadFlightFile(Exception):
    """Raised when a CSV doesn't match the project schema."""


def load_flight(path_or_buffer) -> pd.DataFrame:
    """Read a flight CSV, validate it, clean it, return a DataFrame."""
    try:
        df = pd.read_csv(path_or_buffer)
    except Exception as e:
        raise BadFlightFile(f"Could not read file as CSV: {e}") from e

    missing = [c for c in SCHEMA if c not in df.columns]
    if missing:
        raise BadFlightFile(
            f"File is missing required columns: {missing}. "
            f"Expected schema: {SCHEMA}"
        )

    df = df[SCHEMA].copy()                      # drop any extra columns
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.dropna()                            # remove malformed rows
    df = df[df["sat_count"] >= MIN_SATS]        # remove bad-GPS rows
    df = df.sort_values("time_ms").reset_index(drop=True)

    if len(df) < 10:
        raise BadFlightFile("File has fewer than 10 valid rows after cleaning.")

    # basic sanity: coordinates must look like real lat/lon
    if not (df["lat"].between(-90, 90).all() and df["lon"].between(-180, 180).all()):
        raise BadFlightFile("Latitude/longitude values are out of range — "
                            "check the unit conversion in the pipeline.")
    return df


def mission_stats(df: pd.DataFrame) -> dict:
    """Summary numbers for the dashboard header."""
    import numpy as np
    # distance flown: sum of point-to-point distances (approx, meters)
    m_lat = 111_320.0
    m_lon = 111_320.0 * np.cos(np.radians(df["lat"].mean()))
    dx = df["lon"].diff().fillna(0) * m_lon
    dy = df["lat"].diff().fillna(0) * m_lat
    dist_m = float(np.hypot(dx, dy).sum())
    return {
        "duration_s": float(df["time_ms"].iloc[-1] - df["time_ms"].iloc[0]) / 1000,
        "distance_m": dist_m,
        "max_alt_m": float(df["alt_m"].max()),
        "max_speed_ms": float(df["ground_speed_ms"].max()),
        "min_vbat_v": float(df["vbat_v"].min()),
        "avg_sats": float(df["sat_count"].mean()),
    }
