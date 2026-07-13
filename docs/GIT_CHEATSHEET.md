# Git & GitHub Cheat Sheet (for this team)

## One-time setup (each member, once per computer)

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

One person creates the repo on GitHub (private, no template files), then:

```bash
cd drone-survey
git init
git add .
git commit -m "Initial project skeleton: app, pipeline, sample data, docs"
git branch -M main
git remote add origin https://github.com/<user>/drone-survey.git
git push -u origin main
```

Then add the other 3 members as collaborators:
GitHub repo → Settings → Collaborators → Add people.

Everyone else:

```bash
git clone https://github.com/<user>/drone-survey.git
```

## Daily workflow (the only 6 commands you really need)

```bash
git pull                          # ALWAYS first — get teammates' latest work
git checkout -b feat/thermal-tab  # new branch for your task
# ... edit code ...
git add .                         # stage your changes
git commit -m "Add thermal timeline graph"   # save a snapshot
git push -u origin feat/thermal-tab          # upload your branch
```

Then on GitHub: **Open a Pull Request** from your branch into `main`,
a teammate glances at it, click **Merge**. Done.

## Team rules (these prevent 90% of disasters)

1. **Never commit directly to `main`.** Always branch → PR → merge.
2. **Pull before you start working.** Every single time.
3. **Small commits, clear messages.** "Fix altitude unit conversion" ✅,
   "stuff" ❌. A commit message finishes the sentence: *"This commit will…"*
4. **One task = one branch.** Branch names like `feat/map-tab`,
   `fix/csv-validation`, `docs/readme`.
5. **Never commit:** the virtual environment, giant raw blackbox files,
   or IDE junk — the `.gitignore` already blocks these. Raw flight logs
   are shared via Drive; only standardized CSVs under ~5 MB go in `data/`.

## When things go wrong

```bash
git status                 # what did I change? (use constantly)
git restore <file>         # undo my uncommitted edits to a file
git log --oneline -10      # recent history
git stash                  # shelve my messy changes; git stash pop brings them back
```

**Merge conflict?** Don't panic. Open the file, look for `<<<<<<<` markers,
keep the correct lines, delete the markers, then `git add .` and
`git commit`. If truly stuck, ask before force-pushing anything — never
run a command with `--force` without a teammate watching.

## Commit message style for the final grade

Professors love a readable history. Pattern:
`Add ...` / `Fix ...` / `Update ...` / `Docs: ...`
Example history that looks professional:

```
Add 3D terrain view to LIDAR tab
Fix lat/lon swap in blackbox standardizer
Update README with data schema table
Docs: add pre-flight checklist
```
