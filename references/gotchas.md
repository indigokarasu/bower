# Bower Gotchas

Failure modes and hard-won operational facts for Google Drive scanning with
Bower. Each entry is a thing that actually went wrong, what it looks like,
and what to do instead. Read the one you need; they are not sequential.

## Contents

- [Contents](#contents)
- [Stale data after major Drive changes](#stale-data-after-major-drive-changes)
- [Cron jobs cannot use `execute_code`](#cron-jobs-cannot-use-execute-code)
- [Small Drive efficiency](#small-drive-efficiency)
- [Drift threshold aborts light scans](#drift-threshold-aborts-light-scans)
- [Staleness checks execute per-proposal](#staleness-checks-execute-per-proposal)
- [Permission fetch suppresses all move proposals](#permission-fetch-suppresses-all-move-proposals)
- [Simulation writes absolutely nothing](#simulation-writes-absolutely-nothing)
- [Medical file redaction](#medical-file-redaction)
- [Quiet mode suppresses only the digest](#quiet-mode-suppresses-only-the-digest)
- [Small Drive below domain thresholds](#small-drive-below-domain-thresholds)
- [Shared files appear in modifiedTime queries](#shared-files-appear-in-modifiedtime-queries)
- [Light scan misses bulk-moved files](#light-scan-misses-bulk-moved-files)
- [write_file overwrites — use terminal >> for .jsonl append](#write-file-overwrites-use-terminal-for-jsonl-append)
- [Drive file/folder IDs are 33 chars — never truncate](#drive-filefolder-ids-are-33-chars-never-truncate)
- [OAuth invalid_grant — two distinct causes, only one is fatal](#oauth-invalid-grant-two-distinct-causes-only-one-is-fatal)
- [Interpretter / `requests` missing looks like `invalid_grant`](#interpretter-requests-missing-looks-like-invalid-grant)
- [`search_files` can return phantom paths and miss real files under the profile tree](#search-files-can-return-phantom-paths-and-miss-real-files-under-the-profile-tree)
- [Light-scan query window repeats until the next deep scan](#light-scan-query-window-repeats-until-the-next-deep-scan)
- [Timestamp-folder false positives in triage](#timestamp-folder-false-positives-in-triage)
- [Large Drive founding scans timeout](#large-drive-founding-scans-timeout)
- [Bundled `scripts/` scan scripts are unsafe for this Drive](#bundled-scripts-scan-scripts-are-unsafe-for-this-drive)
- [location_outlier move proposals are title-keyword false-positive prone](#location-outlier-move-proposals-are-title-keyword-false-positive-prone)
- [Weekly deep scan yields 0 NEW proposals when prior ones persist](#weekly-deep-scan-yields-0-new-proposals-when-prior-ones-persist)
- [Stale digest causes permanent drift abort loop](#stale-digest-causes-permanent-drift-abort-loop)

---

## Stale data after major Drive changes

— Between scans, the Drive may be cleaned up, migrated, or restructured catastrophically (e.g., 381K files → 17). When a deep scan detects a >50% change in total file/folder count compared to `scan_progress.json` or `drive_digest.json`, treat the previous scan data as stale: reset `scan_progress.json` to `phase: complete` with the new counts, update `drive_digest.json` with new totals, and add a `scan_notes` field documenting the change. Do NOT carry forward old proposals — the old `proposals.jsonl` records reference file/folders that may no longer exist. Let the new scan drive fresh proposals. Optionally archive old scan data (`scans/`, `proposals.jsonl`) to a dated archive directory.
## Cron jobs cannot use `execute_code`

— Scheduled cron runs (light and deep scans on this profile) execute in an isolated context where `execute_code` is blocked. All scan logic must use native Hermes tools (List Google Drive files, Search Google Drive, `write_file`, `terminal` with `>>` for `.jsonl` append). Do not write Python scripts that expect to be run via `execute_code` for scheduled work. The `scripts/` directory is for interactive/scripted runs only.
## Small Drive efficiency

— On Drives with <500 total files, the modifiedTime query may return mostly batch-imported content (e.g., 97 books imported at once). Group by timestamp to identify batch imports vs. real user activity. See `references/scan-debug.md` → "Small Drive light scan efficiency" for the triage pattern.
## Drift threshold aborts light scans

— If the light scan detects significant structural drift, it aborts entirely rather than producing partial results. A subsequent deep scan is needed to re-establish the baseline.
## Staleness checks execute per-proposal

— Even auto-approved, high-confidence proposals pass through a staleness check immediately before execution. A file moved between scan and apply can cause a proposal to quietly skip.
## Permission fetch suppresses all move proposals

— If folder permissions are unavailable (API error or scope missing), Bower suppresses *all* move proposals for that folder—not just the affected files—and falls back to description-only suggestions.
## Simulation writes absolutely nothing

— `bower.simulate` produces no proposals, logs, journals, or state changes. It is safe to run repeatedly but provides no persistent output.
## Medical file redaction

— Medical folder contents are never logged, journaled, or surfaced by filename. Only folder paths and file counts appear in apply digests and simulation output.
## Quiet mode suppresses only the digest

— Enabling quiet mode hides the apply digest output but does not bypass approval requirements, staleness checks, or any safety gate.
## Small Drive below domain thresholds

— When the Drive has fewer than 5 files or 2 subfolders total, no domain logic activates. Analysis falls entirely on generic outlier rules (depth outliers, name inconsistencies). This is expected — report the Drive as "too small for domain detection" and focus proposals on obvious misplacements (files at root that belong in named folders, duplicate filenames).
## Shared files appear in modifiedTime queries

— The Drive API `modifiedTime` filter returns shared files/folders that were recently modified by their owners, even though they're outside the user's Drive tree. These appear with `parents: null` and `ownedByMe: False`. Always check `ownedByMe` and parent location before generating proposals. Shared files are never actionable by Bower. See `references/scan-debug.md` → "Shared files in modifiedTime results" for the full triage pattern.

## Light scan misses bulk-moved files

— The `bower.scan.light` queries by `modifiedTime`, which only catches files *modified* since the last scan. Files that were bulk-moved or bulk-created without recent modification timestamps are invisible to this query. The mandatory structural baseline check (root-level count comparison) before the `modifiedTime` query catches this. Without it, a completely restructured Drive can be reported as "no new files." See the "Light scan structural baseline check" section above.

## write_file overwrites — use terminal >> for .jsonl append

— The `write_file` tool always overwrites the entire file. For append-only logs (`scan_events.jsonl`, `evidence.jsonl`, `move_log.jsonl`, `undo_log.jsonl`, `feedback_log.jsonl`, `proposals.jsonl`, `health_history.jsonl`, `decisions.jsonl`, `intents.jsonl`, `analysis_events.jsonl`), use `terminal` with `>>` to append, or build the full content and write once. Accidentally overwriting these files destroys history. When appending scan events or evidence entries, prefer: `terminal` > `command: "cat >> path.jsonl << 'EOF'\n{...}\nEOF"` . Never use `write_file` on a `.jsonl` unless you intend to replace the entire file.

## Drive file/folder IDs are 33 chars — never truncate

— A valid Drive ID looks like `1uBwL8OJ-XrXaBo4Uv9niZ_Qdx3JaqWHS` (33 chars). If you print/echo/copy an ID and it gets truncated to ~24 (a common terminal wrap or manual copy slip), a later `files().get()` returns `HttpError 404 File not found`. The file is **not** missing — your truncated ID is wrong. Always copy the full 33-char ID verbatim. Confirmed 2026-07-17: five parent lookups 404'd solely due to truncated IDs; the real IDs resolved all 21 arrivals correctly. See `references/light-scan-triage.md` for the full triage recipe (resolving `light_scan_latest.json` parent IDs to folder names + grouping arrivals).
## OAuth invalid_grant — two distinct causes, only one is fatal

— `invalid_grant: Bad Request` surfaces as either (a) a *permanently* dead/revoked refresh token (no recovery short of user re-auth), OR (b) a *recoverable* client_id/refresh-token mismatch: a script loads a cached token file whose embedded `client_id` differs from the `client_id` it passes when constructing `Credentials`. Google rejects the token as issued for another client. Symptom of (b): the *deep* scan works but the *light* scan fails — because deep uses `get_service` (which always pairs the right client secret with the right client_id from `_CLIENTS[account]`), while the broken light-scan script hand-builds `Credentials` with a hardcoded, mismatched `client_id`. Confirmed 2026-06-29 → 2026-07-14: light scans died nightly for 16 days while deep scans succeeded. **Fix for (b):** route the scan through `get_service`; never construct `Credentials` from a token file plus a separate hardcoded client_id. See `references/cron-drive-fallback.md` (ALWAYS-use-get_service note). For (a), handle at the scan entry point: catch `RefreshError`/`HTTPError 401`, write `degraded: google_drive` to `evidence.jsonl`, write an aborted scan event to `scan_events.jsonl`, enter degraded mode, report, and do NOT retry within the same run. If `get_service()` raises `RuntimeError` ("No valid Google credentials found"), that is condition (a) through a different path — handle identically.
## Interpretter / `requests` missing looks like `invalid_grant`

— `run_light_scan.py` imports `get_service` from `$HERMES_HOME/../indigo/scripts/google_auth.py`, which does `import requests` at module load. If the `python3` the cron/shell invokes lacks `requests` (e.g. it resolves to a project `.venv` whose site-packages only has `googleapiclient`), the scan logs `auth_or_build_failed` with `No module named 'requests'` — which looks EXACTLY like an OAuth failure but is NOT. Tell them apart: the error string is `No module named 'requests'` and no HTTP 400 `invalid_grant: Bad Request` appears. Fix: invoke the script with an interpreter that has BOTH `googleapiclient` and `requests`. On this host the working interpreter is `/usr/bin/python3` (3.14); a stray `python3` on PATH (a project `.venv`, 3.13) did not. Always confirm `python3 -c "import googleapiclient, requests"` succeeds before trusting a cron run. A `auth_or_build_failed` that recurs nightly is the classic signature of this mismatch (cf. the 16-day June 2026 `invalid_grant` episode — same degraded output, different root cause). See `references/cron-drive-fallback.md` → "Operational pitfalls".
## `search_files` can return phantom paths and miss real files under the profile tree

— During the 2026-07-24 light scan, `search_files` returned relative phantom paths (`<fs-root>/commons/...` that didn't exist from cwd) AND a literal `0 results` for `google_auth.py` under `~/.hermes`, even though `find ~/.hermes -name 'google_auth*'` proved the file at `$HERMES_HOME/../indigo/scripts/google_auth.py` (the `ls`/`find` were truncated or symlink-indexed). This almost caused a false "DEGRADED: auth module missing" conclusion. When a dependency/locator check returns empty or suspicious, DO NOT trust `search_files` alone: confirm with `find ~/.hermes -name '<file>'` and an absolute-path `ls` before concluding anything is missing. The ripgrep-backed index appears to miss files under nested profile dirs and to emit cwd-relative paths.
## Light-scan query window repeats until the next deep scan

— `run_light_scan.py` sets `cutoff = drive_digest.json["last_updated"]`, which is updated ONLY by `bower.scan.deep` (weekly Sunday run). It is NOT "since the last light scan" or "since yesterday." Consequence: between deep scans, the SAME set of arrivals recurs on every light scan. Identical owned/shared counts day-to-day = "no NEW activity since the last deep scan," NOT a stuck or duplicating scan. Do not conclude the scan is broken when consecutive days return the same owned arrivals — the window simply never advanced. New activity only surfaces after the next deep scan resets `last_updated`. (This is also why a light scan is the wrong tool to detect "what arrived today" — use it for drift-safety + the standing disorganization among already-known arrivals. Run `scripts/bower_light_triage.py` to turn those arrivals into a report.)
## Timestamp-folder false positives in triage

— when flagging `YYYY-MM-DD_HH-MM-SS`-style export/checkpoint folder piles, use the strict regex `^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$`. A naive `name[:4].isdigit()` test false-positives on legitimately-named folders like `2442 Kuhio Avenue 702` (a Real Estate subfolder). `scripts/bower_light_triage.py` already uses the strict regex.
## Large Drive founding scans timeout

— On Drives with 10K+ items, a full founding deep scan can exceed the 10-minute cron timeout during folder/file enumeration, and the Drive API may return 500 Internal Errors under heavy pagination. Solution: use the **sampled deep scan** (`commons/data/ocas-bower/deep_scan_sampled.py`): enumerate all folders once (cached to `folder_full_cache.json` for reuse), then sample up to 300 direct children per curated root. Set `scan_coverage: 0.5` in `drive_digest.json`. See `references/large-drive-scanning.md`. **The weekly `bower:weekly-deep` run ALSO uses the sampled strategy** — it never attempts full enumeration on this ~24K-folder Drive. Always wrap Drive API list calls with exponential backoff for 500/503 errors.

## Bundled `scripts/` scan scripts are unsafe for this Drive

— `scripts/bower_full_scan.py` (the skill's own deep-scan script) does a FULL file enumeration (times out on ~24K folders) AND builds its Drive service via the hardcoded-credential `get_drive_service()` path that triggers `invalid_grant` (see cron-drive-fallback). For real scans, run the maintained scripts in the canonical data dir: `commons/data/ocas-bower/deep_scan_sampled.py` (deep) and `run_light_scan.py` (light). These use `get_service`, honor drift/stale-data handling, and write analyze-compatible artifacts. `scripts/bower_analyze.py` is usable (it reads the canonical `commons/data/ocas-bower` dir) but is stale — prefer it over `bower_full_scan.py`, and never use `bower_full_scan.py` for scan runs.

## location_outlier move proposals are title-keyword false-positive prone

— `bower.analyze` flags a file as `location_outlier` when its *name* contains a domain keyword (home/work/project/house) and it sits outside that domain's root. For books in **Bookshelf** this is almost always WRONG: e.g. *"Learn Hawaiian at Home"*, *"American House Styles"*, *"Work Like A Spy"*, *"Project Hail Mary"* are ebooks, not Home/Projects documents. Do NOT auto-apply such proposals. Rule of thumb: never move contents of an already-curated semantic root (Bookshelf, Archive) to another domain based on title-substring matches alone — require file *content/type* or explicit domain-folder membership. (Also seen: duplicate proposals — the same file listed twice, e.g. *Project Hail Mary*. The analyzer should dedupe by `source_id`.) Review the pending queue (`bower.proposals.review`) and reject the false positives before any `bower.apply`.

## Weekly deep scan yields 0 NEW proposals when prior ones persist

— `bower_analyze.py` dedupes against existing `pending`/`approved` proposals, so a routine weekly deep scan legitimately produces 0 new proposals even when 16 are still pending. That is NOT a sign the scan failed. The deliverable of a weekly deep scan is the refreshed `folder_index.json` + `drive_digest.json` (which advances the light-scan `modifiedTime` cutoff) + the still-pending queue — not new proposals. Report "0 new, N pending" as healthy.

## Stale digest causes permanent drift abort loop

— `drive_digest.json` can get a wrong baseline if a light scan incorrectly concludes that a large-drift event "reverted to baseline." Subsequent scans compare against the wrong baseline and permanently detect 95%+ drift, aborting every run and generating no proposals. Diagnosis: `root_level_file_count` and `root_level_folder_count` in `drive_digest.json` don't match what the Drive API actually returns. Fix: query the Drive API directly (`mimeType = 'application/vnd.google-apps.folder' and parentId = 'root'` for folders; `parentId = 'root' and mimeType != 'application/vnd.google-apps.folder'` for files), then update `drive_digest.json` with the real counts, clear `scan_progress.json`'s `drift_detected: true` flag, and update `folder_index.json` with the actual folder IDs. **Never write a digest update concluding drift has "reverted" unless you verified the root-level counts match the previous baseline.** Confirmed June 2026.
