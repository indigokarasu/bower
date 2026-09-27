---
warning: 'FALSE TRIGGER RISK: Has had 100% false trigger rate on interactive loads (5/5 auto). Do NOT load for Google Drive organization when the user has not explicitly requested it or when the task is simple folder cleanup — load only when Drive organization is the primary intent and there is clear evidence of organizational mess. Updated 2026-09-25: increased from 50% (1/2) to 100% (5/5).'
name: ocas-bower
license: MIT
source: https://github.com/<agent-handle>/bower
description: >-
  Automatic Google Drive organizer. Use when the user asks to organize, clean up,
  restructure, or audit their Google Drive, reports their Drive as disorganized,
  or asks what Bower found / to apply pending Bower proposals. Scans Drive structure
  and file contents, builds a personalized preference profile, applies domain-specific
  logic (taxes by year, projects by name, home by system, finance by institution),
  and executes non-destructive moves, renames, and description writes. Learns
  organizational style over time and auto-approves consistently accepted patterns.
  Never deletes files. NOT for web research or document analysis (use Sift), Chronicle
  ingestion, permission management, or one-off manual folder cleanup that needs no
  learned preference model.
includes:
- references/**
- scripts/**
metadata:
  author: Indigo Karasu (indigokarasu)
  version: "1.5.0"
  hermes:
    category: utilities
    tags:
    - google-drive
    - file-organization
    - auto-organize
    - ocas-core
    config:
    - key: OCAS_OPERATOR_EMAIL
      description: "Google account whose Drive Bower scans, and the key used to resolve
        shared-file owners in light-scan triage"
      default: "operator@example.com"
    - key: BOWER_CONTENT_BUDGET
      description: "Default wall-clock seconds for one bower_content_index.py pass
        before it stops early and leaves the rest resumable"
      default: "1800"
    - key: HERMES_HOME
      description: "Agent root used to locate commons/data/ocas-bower artifacts and
        the google_auth module; falls back to ~/.hermes"
      default: "~/.hermes"
triggers:
- google drive
- drive organizer
- file organization
- drive cleanup
- auto-organize
---

## Interactive Menu

When invoked interactively, present a two-level menu. See `references/interactive-menu.md` for the full menu structure.

## When to Use

- Google Drive cleanup and organization
- Duplicate file detection and merging
- Folder structure optimization
- Preference-based auto-organization rules
- Drive health monitoring and reporting

# Bower

Bower keeps Google Drive organized without ever deleting anything. It learns your organizational style from your existing structure, applies domain-native logic where it detects known domains, builds a personalized preference profile, and over time auto-approves patterns you consistently accept. The goal: you go to sleep and wake up to a Drive that looks the way you would have organized it yourself.

**Current status:** Weekly deep-scan cadence established. The Drive holds ~23.7K
folders, almost all of them a nested backup/Takeout tree (dominant subtree
`Archive`, ~9.7K descendants) that is **out of Bower's scope** — Bower
organizes, never deletes. Only the 6 curated roots (Bookshelf, Archive, Home,
Projects, Professional, Authenticator Backups, ~516 direct files) are
meaningfully in scope, so deep scans are **sampled** (`scan_coverage: 0.5`):
enumerate all folders once (cached), then sample 300 direct children per
curated root. For current counts, pending-proposal count, and detected
domains, read `commons/data/ocas-bower/drive_digest.json` and
`proposals.jsonl` rather than trusting a number written here — the honest
summary has been stable for months: 2 prescriptive domains (projects, home),
Drive root clean, auto-approval not yet triggered (needs proposal review first),
and most pending proposals are title-keyword false positives (see Gotchas).
Bower's real value on this Drive is drift monitoring, health confirmation, and
executing *reviewed* proposals — not bulk reorganization.

## Trigger conditions

- "Organize my Drive"
- "Clean up my Google Drive"
- "What's disorganized in my Drive?"
- "Show me what Bower found" / "Run a Drive scan"
- "Apply the pending Bower proposals"
- "What has Bower learned about my preferences?"
- "What would you do to this folder?" / "Simulate Bower on my Projects folder"
- "Turn on quiet mode" / "Run silently"
- Bower's background scan job fires on schedule

## When NOT to Use

- Deleting files — Bower never deletes
- Managing sharing permissions — Bower doesn't touch permissions
- Creating top-level taxonomy from scratch — Bower infers from existing structure
- Interacting with non-Drive storage — Bower is Drive-only
- Applying domain logic to undetected domains — needs 5+ files or 2+ subfolders to activate
- Web research or document analysis — use Sift
- Chronicle ingestion

## Responsibility boundary

Bower does: scan Drive structure and file contents, build a preference profile from evidence, detect and apply domain-specific organization logic, identify outliers, propose folder moves, renames, and description writes, auto-approve promoted patterns, apply approved changes using the system's Google Drive access, maintain a full audit trail.

Adjacent responsibility: Sift handles web research and document analysis. Bower emits entity signals in journal payloads for Chronicle ingestion for all Drive artifacts and entities encountered during scans.

## Ontology types

- **Thing/DigitalArtifact** — Drive files and folders that Bower scans, classifies, and organizes. Bower includes signals in journal payloads for all discovered Drive artifacts.
- **Entity/Person** — People referenced in documents, shared-with metadata, and collaborators encountered during scans.
- **Place** — Locations found in documents (travel documents, address lists, venue information).
- **Concept/Event** — Events, projects, or topics that documents are about (e.g., a folder of wedding planning docs, a project kickoff deck).
- **Concept/Idea** — Themes and topics reflected by folder structure and document content (e.g., recurring interest in machine learning across multiple folders).

## Signal emission

Bower includes structured signals in journal payloads for all entities and artifacts encountered during scans. All signals carry `user_relevance: "user"`. Five signal types are emitted: Thing/DigitalArtifact, Entity/Person, Place, Concept/Event, Concept/Idea. One signal per unique artifact/entity, deduplicated by `file_id` (artifacts) or email (persons). Signals are written to the `signal` payload field during `bower.scan.deep` and `bower.scan.light`.

For full JSON schema examples, see `references/signal_examples.md`.

## Commands

| Command | Summary |
|---------|---------|
| `bower.scan.deep` | Full Drive crawl, folder-by-folder. `--founding` for first use. `--analyze-now` for early results. |
| `bower.scan.light` | Incremental scan of recent changes. Arrival detection + auto-apply if quiet mode. |
| `bower.analyze` | Domain logic + generic rules → ranked proposals. Read-only. |
| `bower.simulate` | Read-only scan of a folder. Shows what Bower would do. |
| `bower.proposals.review` | List pending proposals by folder, confidence, domain. |
| `bower.proposals.approve` | Approve a subset. Requires explicit scope. |
| `bower.proposals.reject` | Reject proposals. Suppresses patterns. |
| `bower.apply` | Execute approved proposals. `--dry-run` to preview. |
| `bower.undo` | Reverse moves, renames, description writes. |
| `bower.preferences.show` | Display preference profile. |
| `bower.preferences.lock` | Mark a preference field or pattern as fixed (prevents auto-inference from overwriting it). |
| `bower.preferences.quiet` | Toggle quiet mode (suppresses digest only). |
| `bower.feedback.clear` | Clear suppression patterns or demotions. |
| `bower.status` | SkillStatus summary. `--trend` for 8-week health. |
| `bower.init` | First-use initialization. |

Full flag descriptions and semantics: `references/command_reference.md`

## Workflow

The Bower organization pipeline: **scan → analyze → propose → apply → learn**.

1. Scan Drive structure and file contents
2. Analyze with domain-specific logic (taxes by year, projects by name, etc.)
3. Propose non-destructive moves/renames
4. Apply approved changes
5. Learn from accepted patterns for auto-approval

## Execution flow

### First use (founding run)
`bower.init` → `bower.scan.deep --founding` (Phase 1: tree discovery; Phase 2: scan folders one at a time, resume across sessions) → `bower.analyze` → present high-confidence proposals as batch → if accepted: `bower.apply`. Founding run batch approval grants immediate pattern promotion credit. Use `--analyze-now` for early results before all folders scanned.

Founding run checklist:

- [ ] Run `bower.init` first — it creates the data/journal dirs, writes `config.json`, and registers cron jobs (check for existing jobs first to avoid duplicates)
- [ ] On a Drive with >10K items, do **not** attempt full enumeration; use the sampled strategy (`references/large-drive-scanning.md`)
- [ ] Let Phase 1 enumerate and cache all folders before Phase 2 starts sampling children
- [ ] Resume across sessions rather than restarting — `scan_progress.json` is the source of truth, and `bower_resume_scan.py` does this
- [ ] Run `bower.analyze` incrementally (`--analyze-now`) so proposals appear before the scan completes
- [ ] Present high-confidence proposals as a **batch** and get explicit approval before applying — founding batch approval grants immediate pattern promotion credit, so do not batch-approve reflexively
- [ ] Confirm at least one deep scan completes before enabling quiet-mode auto-apply

### Steady state
Daily light scan at 02:00 PT: `bower.scan.light` → arrival detection → auto-apply promoted high-confidence matches if quiet mode on. Weekly deep scan Sunday 01:00 PT: run the **sampled** deep scan (`commons/data/ocas-bower/deep_scan_sampled.py` — NOT full enumeration) → `bower.analyze` (run `scripts/bower_analyze.py`, which reads the canonical data dir) → emit Drive health signal to Vesper. Silent unless something needs attention. On this ~24K-folder Drive the weekly deep scan stays sampled; it never attempts full enumeration.

### Running scans on this host (verified recipe)

The canonical scan scripts live under the indigo profile data dir, **not** the
skill's own `scripts/`:

- **Light:** `/usr/bin/python3 $HERMES_HOME/../indigo/commons/data/ocas-bower/run_light_scan.py`
- **Deep (weekly, sampled):** `/usr/bin/python3 $HERMES_HOME/../indigo/commons/data/ocas-bower/deep_scan_sampled.py`

Use `/usr/bin/python3` — a stray `python3` on PATH can resolve to a project
`.venv` that lacks `requests` and produces a *false* `auth_or_build_failed`
(see Error handling). Never run `scripts/bower_full_scan.py` here; it
enumerates the full ~24K-folder tree and times out.

Exact commands, credential resolution, output artifacts, and the
`search_files`-phantom-path trap: `references/scan-execution.md`.

### Arrival detection
After every light scan, for each new/modified file: classify → check `pattern_key` against `auto_approved_patterns`. High-confidence match: generate `approved` proposal (auto-apply if quiet mode). Medium-confidence: `pending`. No match: normal `pending`.

### Simulation
Read-only scan of specified folder → apply full analysis pipeline → print narrative report. No proposals, logs, journals, or state changes written. See `references/organization_rules.md` for simulation output format.

### Apply run
Description auto-writes first → sort by confidence tier → apply `apply_cap` → per-proposal staleness check → execute via Google Drive → log to `move_log.jsonl` → produce digest (suppressed in quiet mode if all succeeded) → write Action Journal.

Apply checklist — every item true before the run may be reported complete:

- [ ] Every proposal in the batch is approved
- [ ] `--dry-run` previewed first for batches touching starred files, medical folders, or a domain root
- [ ] Staleness re-checked per proposal immediately before execution (why: a file can move between scan and apply, and a stale proposal moves the wrong thing)
- [ ] `permissions_available: true` for every affected folder
- [ ] Destinations verified through the Drive API, not just written to the log
- [ ] `move_log.jsonl` entry count == executed proposal count; a mismatch is a failed run
- [ ] Any file missing at its destination reported as a **failed move**, not retried blindly (a stale retry can double-move)
- [ ] Action Journal written; digest respects quiet mode

### Undo run
Read move log records → staleness check → restore `previous_value` → execute reversal → log to `undo_log.jsonl` → record feedback → trigger pattern demotion if auto-approved → write Action Journal.

## Decision model

Read these reference files before the operations they govern:

| File | When to read |
|------|-------------|
| `references/gotchas.md` | Before any scan or apply that could surprise you; 24 failure modes, symptom → fix |
| `references/scan-execution.md` | When a scan fails or a dependency looks missing; exact host commands, interpreter/credential resolution, baseline-check rationale |
| `references/organization_rules.md` | Before every `bower.analyze`; preference inference, pattern promotion, proposal rules, permission lookup, cap behavior |
| `references/domains.md` | Before every `bower.analyze`; domain detection, prescriptive/descriptive mode, filing rules per domain |
| `references/analysis_schema.md` | Before `bower.scan.deep` or `bower.analyze`; every data schema — profile, index, progress, proposals, move/undo/feedback logs, config |
| `references/decision-invariants.md` | Before every `bower.analyze` or `bower.apply`; the safety invariants that govern all operations |
| `references/signal_examples.md` | Before emitting signals; JSON schema for all five signal types |
| `references/scan-debug.md` | When debugging scan issues, resume failures, or light-scan anomalies |
| `references/light-scan-triage.md` | After a light scan; the cron deliverable — resolving parent IDs and grouping arrivals |
| `references/cron-drive-fallback.md` | When a scheduled scan hits OAuth/auth failures, or when wiring cron Drive access |
| `references/large-drive-scanning.md` | Before a founding deep scan on >10K items, or on cron timeout; sampled strategy and 500-error handling |
| `references/mcp-drive-tooling.md` | When driving Drive through MCP tooling instead of the python client |
| `references/drift-incident-2026-06-14.md` | When a light scan detects major drift; why modifiedTime-only queries miss bulk moves |
| `references/spec-ocas-recovery.md` | Before implementing or auditing Recovery Behavior; the shared evidence/gap/degraded/compaction contract |
| `references/command_reference.md` | When you need full command flag descriptions and semantics |
| `references/okrs.md` | When reporting status/trend or reviewing targets; full OKR definitions |
| `references/storage-layout.md` | Before reading or writing any artifact by path; the full directory structure |
| `references/interactive-menu.md` | When invoked interactively; the full two-level menu structure |
| `commons/data/ocas-bower/*.py` (canonical data dir) | The RUNNABLE scan/analyze scripts: `deep_scan_sampled.py` (weekly deep, sampled), `run_light_scan.py` (light), plus artifacts (`folder_index.json`, `scans/`, `proposals.jsonl`, `drive_digest.json`, `evidence.jsonl`). Skill `scripts/` holds stale/unsafe equivalents — see Gotchas. |

### Scripts

Every bundled script accepts `--help` (exit 0) and prints its own usage. Run
`python3 scripts/<name>.py --help` before using one; do not guess its flags.

| Script | Purpose | Notes |
|--------|---------|-------|
| `bower_light_triage.py` | Turn a light scan into a disorganization report | Read-only. The normal cron deliverable. Has `--json` |
| `bower_analyze.py` | `bower.analyze` over the canonical data dir | Usable but stale; prefer it over `bower_full_scan.py` |
| `bower_content_index.py` | Extract document *content* into `drive_content.db` | `--native` / `--uploaded` / `--ocr` passes; `--dry-run`, `--self-test`. Its `--help` guard exits before any import or Drive call, so probing it is safe |
| `bower_describe.py` | Auto-write file descriptions | Has `--dry-run` and `--undo` |
| `bower_read_contents.py` | Read + summarize a folder's contents for deep scan | Bounded per run |
| `bower_resume_scan.py` | Resume an interrupted deep scan from `scans/` | Source of truth is the `scans/` dir, not a cursor |
| `bower_full_scan.py` | Bundled full deep scan | **Unsafe on this Drive** — times out on ~24K folders and uses a hardcoded-credential path that triggers `invalid_grant`. Use the sampled script in `commons/data/ocas-bower/` instead |
| `bower_mem_ingest.py` / `bower_mempalace_ingest.py` | Bower → MemPalace fact ingestion | Files meaningful facts only, never file counts |
| `test_bower_content_index.py` | Unit tests for the content indexer's pure logic | Needs pytest; network-free by construction |
