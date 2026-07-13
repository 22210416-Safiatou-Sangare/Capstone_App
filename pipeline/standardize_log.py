"""
standardize_log.py  (Safiatou's module — finished version)
----------------------------------------------------------
Converts RAW decoded blackbox CSVs (output of `blackbox_decode`) into the
official project schema used by the app:

    time_ms, lat, lon, alt_m, ground_speed_ms, roll_deg, pitch_deg,
    yaw_deg, vbat_v, sat_count

Features:
  * ALIAS MATCHING  — blackbox column names vary between INAV versions, so
    each schema field has a list of known aliases; matching ignores case
    and spacing. If nothing matches, the script prints every raw column so
    you can add the alias in ten seconds.
  * UNIT AUTO-DETECT — altitude sometimes arrives in cm, coordinates as
    integers scaled by 1e7, attitude in decidegrees. The script detects and
    converts, and REPORTS every decision it made so you can sanity-check.
  * BATCH MODE      — point it at a folder and it converts every CSV inside.

Usage (single file):
    python pipeline/standardize_log.py raw_decoded.csv -o data/flight01.csv
Usage (whole folder):
    python pipeline/standardize_log.py raw_logs/ -o data/
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_HZ = 5          # project-wide sample rate
MIN_ROWS = 10

# schema field -> list of known raw-column aliases (add more as you meet them)
ALIASES = {
    "time":  ["time (us)", "time", "time(us)"],
    "lat":   ["GPS_coord[0]", "GPS_coord0", "gps_coord[0]", "navPos[0]"],
    "lon":   ["GPS_coord[1]", "GPS_coord1", "gps_coord[1]", "navPos[1]"],
    "alt":   ["GPS_altitude", "GPS_altitude (m)", "baroAlt", "navPos[2]",
              "BaroAlt (cm)"],
    "speed": ["GPS_speed (m/s)", "GPS_speed", "GPS_ground_course"],
    "roll":  ["attitude[0]", "roll", "attitude0"],
    "pitch": ["attitude[1]", "pitch", "attitude1"],
    "yaw":   ["attitude[2]", "heading", "attitude2"],
    "vbat":  ["vbat (V)", "vbat", "vbatLatest (V)", "vbatLatest"],
    "sats":  ["GPS_numSat", "GPS_numSats", "gps_numsat"],
}


def _norm(name: str) -> str:
    """normalize a column name for fuzzy comparison."""
    return re.sub(r"[\s_]+", "", name).lower()


def match_columns(raw_cols) -> dict:
    """Return {field: actual_raw_column_name}; raise with help text if missing."""
    lookup = {_norm(c): c for c in raw_cols}
    found, missing = {}, []
    for field, aliases in ALIASES.items():
        hit = next((lookup[_norm(a)] for a in aliases if _norm(a) in lookup), None)
        if hit:
            found[field] = hit
        else:
            missing.append(field)
    if missing:
        raise SystemExit(
            f"\nCould not find columns for: {missing}\n"
            f"Raw file contains these columns:\n  " + "\n  ".join(raw_cols) +
            "\n\nFix: add the correct name to ALIASES in "
            "pipeline/standardize_log.py and rerun."
        )
    return found


def standardize(raw: pd.DataFrame, report: list) -> pd.DataFrame:
    cols = match_columns(raw.columns)
    g = lambda f: pd.to_numeric(raw[cols[f]], errors="coerce")

    out = pd.DataFrame()

    # --- time: detect microseconds vs milliseconds -------------------------
    t = g("time").dropna()
    step = t.diff().median()
    if step > 500:                       # >0.5ms per row -> it's microseconds
        out["time_ms"] = (g("time") / 1000)
        report.append(f"time: detected MICROSECONDS (median step {step:.0f})")
    else:
        out["time_ms"] = g("time")
        report.append("time: detected milliseconds")
    out["time_ms"] = out["time_ms"] - out["time_ms"].iloc[0]

    # --- coordinates: detect 1e7-scaled integers ---------------------------
    lat, lon = g("lat"), g("lon")
    if lat.abs().median() > 1000:
        lat, lon = lat / 1e7, lon / 1e7
        report.append("coords: detected integer*1e7 -> converted to degrees")
    else:
        report.append("coords: already decimal degrees")
    out["lat"], out["lon"] = lat, lon

    # --- altitude: detect centimeters ---------------------------------------
    alt = g("alt")
    if alt.abs().max() > 1000:           # a 5" drone does not fly at 1000 m
        alt = alt / 100.0
        report.append("altitude: detected CENTIMETERS -> /100")
    else:
        report.append("altitude: detected meters")
    out["alt_m"] = alt

    out["ground_speed_ms"] = g("speed")

    # --- attitude: detect decidegrees ---------------------------------------
    yaw = g("yaw")
    if yaw.abs().max() > 400:            # yaw can't exceed 360 degrees
        scale = 10.0
        report.append("attitude: detected DECIDEGREES -> /10")
    else:
        scale = 1.0
        report.append("attitude: detected degrees")
    out["roll_deg"] = g("roll") / scale
    out["pitch_deg"] = g("pitch") / scale
    out["yaw_deg"] = (g("yaw") / scale) % 360

    out["vbat_v"] = g("vbat")
    out["sat_count"] = g("sats")

    # --- clean + decimate to OUTPUT_HZ --------------------------------------
    n_before = len(out)
    out = out.dropna().reset_index(drop=True)
    step_ms = 1000 // OUTPUT_HZ
    out = (out.assign(bucket=(out["time_ms"] // step_ms).astype(int))
              .groupby("bucket", as_index=False).first()
              .drop(columns="bucket"))
    out["time_ms"] = out["time_ms"].round().astype("int64")
    out["sat_count"] = out["sat_count"].round().astype(int)
    out = out.round({"lat": 7, "lon": 7, "alt_m": 2, "ground_speed_ms": 2,
                     "roll_deg": 2, "pitch_deg": 2, "yaw_deg": 1, "vbat_v": 2})
    report.append(f"rows: {n_before} raw -> {len(out)} at {OUTPUT_HZ} Hz")

    # --- final sanity gates (fail loudly, never ship silent garbage) --------
    if len(out) < MIN_ROWS:
        raise SystemExit("Too few valid rows after cleaning — is this a real log?")
    if not out["lat"].between(-90, 90).all() or not out["lon"].between(-180, 180).all():
        raise SystemExit("lat/lon out of range after conversion — check ALIASES "
                         "and the coordinate scaling for this log.")
    return out


def process_file(src: Path, dst: Path):
    report = []
    raw = pd.read_csv(src)
    out = standardize(raw, report)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(dst, index=False)
    print(f"\n=== {src.name} -> {dst} ===")
    for line in report:
        print("  •", line)
    dur = out["time_ms"].iloc[-1] / 1000
    print(f"  ✓ {len(out)} rows, {dur:.0f} s flight, "
          f"sats {out['sat_count'].min()}–{out['sat_count'].max()}, "
          f"vbat {out['vbat_v'].min():.2f}–{out['vbat_v'].max():.2f} V")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="raw decoded CSV, or a folder of them")
    ap.add_argument("-o", "--out", default="data",
                    help="output CSV path, or output folder in batch mode")
    args = ap.parse_args()

    src = Path(args.src)
    if src.is_dir():
        files = sorted(src.glob("*.csv"))
        if not files:
            sys.exit(f"No CSV files found in {src}")
        for i, f in enumerate(files, 1):
            process_file(f, Path(args.out) / f"flight{i:02d}.csv")
    else:
        dst = Path(args.out)
        if dst.is_dir() or not dst.suffix:
            dst = Path(args.out) / (src.stem + "_std.csv")
        process_file(src, dst)


if __name__ == "__main__":
    main()
