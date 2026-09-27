# Scan Execution Detail

Host-specific recipes and the reasoning behind the light-scan structural
baseline check. `SKILL.md` keeps the commands and the rules; this file keeps
the detail you only need when something is actually wrong.

## Contents

- [Running scans on this host](#running-scans-on-this-host)
- [Light scan structural baseline check](#light-scan-structural-baseline-check)

---

## Running scans on this host

The canonical scan scripts live under the indigo profile data dir, NOT the skill's own `scripts/`. Use these exact commands (verified 2026-07-24):

- **Light scan:** `/usr/bin/python3 $HERMES_HOME/../indigo/commons/data/ocas-bower/run_light_scan.py`
  - Interpreter: `/usr/bin/python3` (3.14) — has BOTH `googleapiclient` and `requests`. A stray `python3` on PATH (a project `.venv`, 3.13) lacks `requests` and produces a false `auth_or_build_failed` (see Gotchas).
  - Credentials: `<gworkspace-creds>/credentials/<user-google-email>.json`, read by `scripts/google_auth.py` → `get_service`. The script inserts `$HERMES_HOME/../indigo/scripts` onto `sys.path` itself, so run it from any cwd.
  - Exit 0 + JSON `"status": "OK"` = success. Artifacts: `light_scan_latest.json`, appended `scan_events.jsonl` / `evidence.jsonl`, and an Observation Journal under `commons/journals/ocas-bower/YYYY-MM-DD/`.
- **Deep scan (weekly, sampled):** `/usr/bin/python3 $HERMES_HOME/../indigo/commons/data/ocas-bower/deep_scan_sampled.py` (use the sampled script, never `scripts/bower_full_scan.py`).

Never trust a `search_files` `0 results` for `google_auth.py` — the ripgrep-backed index has returned phantom relative paths and missed real files under the profile tree. If a dependency check fails, confirm with `find ~/.hermes -name 'google_auth*'` and absolute `ls` before concluding auth is broken (see Gotchas).

## Light scan structural baseline check

The baseline comparison is **mandatory** before the `modifiedTime` query —
a root-level count query is all that catches a Drive restructuring, because
every file in a bulk move can predate the scan cutoff.

**Why this matters (2026-06-14 incident):** A Drive restructuring placed 89+ files and 12+ folders at root level. All files had `modifiedTime` dates before the last scan's cutoff, so the `modifiedTime` query returned 0 results. The drift was invisible to the light scan. Only a root-level count comparison caught it. Without this check, the light scan would have reported "no new files" while the Drive was completely restructured.
