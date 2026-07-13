# Safiatou's Runbook — From Flight to CSV

The complete, repeatable procedure. After two flights this takes 10 minutes.

## Part A — One-time setup

1. **Install INAV Configurator** (desktop app) from the INAV GitHub releases
   page. You'll use its Blackbox tab.
2. **Get `blackbox_decode`**: download "blackbox-tools" from the
   betaflight/blackbox-tools GitHub releases (Windows .exe available).
   Put `blackbox_decode.exe` in a folder like `C:\tools\` and remember the path.
3. **SD card prep**: name-brand 16 GB card, formatted **FAT32**. (Cards over
   32 GB are SDXC and will NOT work.) Insert into the flight controller's slot.

## Part B — One-time INAV configuration (with the Flight Lead)

1. Connect the FC by USB, open INAV Configurator.
2. **Blackbox tab** → logging device: **SD card** → logging rate: **1/16** or
   similar low divider (we need GPS-rate data, not 1 kHz gyro data — low rate
   = tiny files = easier everything).
3. Save & reboot. Arm the drone briefly on the bench (PROPS OFF): a new
   `.TXT` log file must appear on the card. If the file is 0 KB, the card is
   bad or wrongly formatted — fix before ever flying.

## Part C — After every flight

1. Pull the SD card (or use USB mass-storage mode), copy the new log into
   the project under `raw_logs/YYYY-MM-DD/` on your laptop.
   `raw_logs/` is git-ignored — share raw files via Drive, not git.
2. **Decode** (one command; adjust paths):

   ```
   C:\tools\blackbox_decode.exe --stdout raw_logs\2026-07-20\LOG00001.TXT > raw_logs\2026-07-20\log1_decoded.csv
   ```

   (If the log contains several sessions, blackbox_decode writes several
   numbered outputs — decode without `--stdout` and it creates one CSV per
   session next to the file.)
3. **Standardize** into the project schema:

   ```
   python pipeline/standardize_log.py raw_logs/2026-07-20/log1_decoded.csv -o data/flight03.csv
   ```

   Read the printed report — it tells you every unit conversion it detected.
   First real log ever: if it exits saying columns are missing, it prints all
   raw column names; add the right one to `ALIASES` in the script, commit that
   fix, rerun. You will likely do this exactly once.
4. **Verify visually** (non-negotiable): run the app
   (`streamlit run app/streamlit_app.py`), select your new CSV, and check the
   map — the path must look like the field you actually flew over. A path in
   the ocean = broken conversion, do not deliver.
5. **Deliver**: commit the standardized CSV.

   ```
   git checkout -b data/flight03
   git add data/flight03.csv
   git commit -m "Add flight03: first autonomous lawnmower mission"
   git push -u origin data/flight03
   ```

   Open the PR, Muath merges. His app picks up the new file automatically.

## Troubleshooting quick table

| Symptom | Likely cause | Fix |
|---|---|---|
| No log file after arming | Blackbox not enabled / card not detected | INAV Blackbox tab; reformat FAT32 |
| 0 KB or corrupt log | Bad/slow/SDXC card | Use name-brand 16 GB SDHC |
| Script: "missing columns" | INAV version renamed columns | Add name to `ALIASES` (script prints all raw names) |
| Path plots in wrong country | Coordinate scaling | Script auto-detects; if it guessed wrong, check the report lines |
| Altitude looks 100x too big | cm vs m | Auto-detected; verify report says CENTIMETERS |
| Very few rows survive | GPS had no fix (indoor arming) | Only arm outdoors with 8+ sats for data sessions |
