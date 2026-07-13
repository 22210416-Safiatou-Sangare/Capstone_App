# Integration Plan — pushing the finished code piece by piece

You have all the code now. DON'T push it as one giant commit — push it as the
sequence below. Each step is a branch + PR that adds ONE understandable thing,
so the GitHub history tells the story of the project being built. Professors
read commit history; this makes yours look like a real engineering team.

For every step the ritual is identical:

```
git pull origin main
git checkout -b <branch-name>
# copy in ONLY the files listed for that step
git add .
git commit -m "<commit message>"
git push -u origin <branch-name>
# open PR on GitHub -> teammate reviews -> Merge
```

After merging each step, run the check listed — never stack a new step on a
broken one.

| # | Branch | Files to add | Commit message | Check before merging |
|---|--------|--------------|----------------|----------------------|
| 1 | `chore/skeleton` | `README.md`, `.gitignore`, `requirements.txt`, `.streamlit/config.toml`, `docs/GIT_CHEATSHEET.md` | `Add project skeleton: README, gitignore, requirements` | README renders nicely on GitHub |
| 2 | `feat/sample-data` | `scripts/generate_sample_flight.py`, `data/sample_flight.csv` | `Add synthetic sample flight generator + bundled sample` | `python scripts/generate_sample_flight.py` runs |
| 3 | `feat/ingestion` | `app/ingest.py` | `Add CSV ingestion with schema validation and mission stats` | — |
| 4 | `feat/simulation` | `app/simulate.py` | `Add simulated terrain (DEM+hillshade) and thermal field` | — |
| 5 | `test/core` | `tests/test_core.py` | `Add test suite for ingestion, simulation, pipeline` | `python tests/test_core.py` → will FAIL until step 7 exists; either merge 6–7 first or run tests after step 7. Recommended order if you want green tests each step: 6, 7, then 5. |
| 6 | `feat/dashboard` | `app/streamlit_app.py`, `app/dem_sources.py`, `app/report.py` | `Add Streamlit dashboard: map, telemetry, simulated layers, report export` | `streamlit run app/streamlit_app.py` shows all tabs |
| 7 | `feat/pipeline` (Safiatou pushes this one!) | `pipeline/standardize_log.py`, `pipeline/RUNBOOK.md` | `Add blackbox standardizer with unit auto-detection + runbook` | `python tests/test_core.py` → ALL PASS |
| 8 | `docs/team` | roles matrix + specs from earlier (put in `docs/`) | `Docs: team roles, responsibility matrix, module specs` | — |

Steps 1–4 in one sitting today. Step 6 tomorrow. Give step 7 to Safiatou to
push from HER machine/account so her contribution graph shows it. Later, real
flight CSVs arrive as `data/flightNN` branches (see pipeline/RUNBOOK.md).

## Who owns what going forward

- **Muath** owns `app/`. His remaining TODO list (each = one branch):
  polish colors/labels, try the "Fetch REAL elevation" toggle once at home
  (creates the offline cache file — commit that `.npz` so demos are safe),
  add a second sample flight to demo the flight selector.
- **Safiatou** owns `pipeline/`. Her TODO: install INAV Configurator +
  blackbox_decode now, walk the RUNBOOK with the sample data, then the first
  real log (expect one ALIASES fix — that's normal, the script guides you).
- **Nabil & Ahmed** own `docs/`: build log with photos, wiring map,
  pre-flight checklist, flight test reports. Same branch->PR flow.

## Definition of done (end of month)

1. `python tests/test_core.py` → all pass on a fresh clone.
2. Fresh clone + README quickstart → dashboard runs, no extra steps needed.
3. At least one REAL flight CSV in `data/` that came through the pipeline.
4. One generated HTML mission report saved in `docs/` for the submission.
5. Every member has commits in the history.
