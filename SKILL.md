---
name: ocas-bower
description: 'Bower: automatic Google Drive organizer. Scans Drive structure and file
  contents, builds a personalized preference profile, applies domain-specific logic
  (taxes by year, projects by name, home by system, finance by institution, etc.),
  and executes non-destructive moves, renames, and description writes in the background.
  Learns your organizational style over time and auto-approves patterns you''ve consistently
  accepted. Never deletes files. Trigger phrases: ''organize my Drive'', ''clean up
  my Google Drive'', ''what''s disorganized in my Drive'', ''show me what Bower found'',
  ''run a Drive scan'', ''apply the pending Bower proposals''. Do not use for web
  research (use Sift), document analysis (use Sift), or Chronicle ingestion (use Elephas).

  '
license: MIT
metadata:
  author: Indigo Karasu
  version: 1.4.5
---

# Bower

Bower keeps Google Drive organized without ever deleting anything. It learns your organizational style from your existing structure, applies domain-native logic where it detects known domains, builds a personalized preference profile, and over time auto-approves patterns you consistently accept. The goal: you go to sleep and wake up to a Drive that looks the way you would have organized it yourself.

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

## Responsibility boundary

Bower does: scan Drive structure and file contents, build a preference profile from evidence, detect and apply domain-specific organization logic, identify outliers, propose folder moves, renames, and description writes, auto-approve promoted patterns, apply approved changes using the system's Google Drive access, maintain a full audit trail.

Bower does not: delete files, manage sharing permissions, create top-level taxonomy from scratch (it infers from what exists), interact with any non-Drive storage, apply domain logic to a domain it hasn't detected as clearly started.

Adjacent responsibility: Sift handles web research and document analysis. Elephas handles Chronicle ingestion and receives Bower's entity signals. Bower does not depend on either but emits signals to Elephas for all Drive artifacts and entities encountered during scans.

## Ontology types

- **Thing/DigitalArtifact** — Drive files and folders that Bower scans, classifies, and organizes. Bower emits Signals to Elephas for all discovered Drive artifacts.
- **Entity/Person** — People referenced in documents, shared-with metadata, and collaborators encountered during scans.
- **Place** — Locations found in documents (travel documents, address lists, venue information).
- **Concept/Event** — Events, projects, or topics that documents are about (e.g., a folder of wedding planning docs, a project kickoff deck).
- **Concept/Idea** — Themes and topics reflected by folder structure and document content (e.g., recurring interest in machine learning across multiple folders).

## Signal emission to Elephas

Bower emits structured signals to Elephas for all entities and artifacts encountered during scans. All signals carry `user_relevance: "user"`. Five signal types are emitted: Thing/DigitalArtifact, Entity/Person, Place, Concept/Event, Concept/Idea. One signal per unique artifact/entity, deduplicated by `file_id` (artifacts) or email (persons). Signals are written to the `signal` payload field during `bower.scan.deep` and `bower.scan.light`.

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
| `bower.preferences.lock` | Lock a preference field or pattern. |
| `bower.preferences.quiet` | Toggle quiet mode (suppresses digest only). |
| `bower.feedback.clear` | Clear suppression patterns or demotions. |
| `bower.status` | SkillStatus summary. `--trend` for 8-week health. |
| `bower.init` | First-use initialization. |

Full flag descriptions and semantics: `references/command_reference.md`

## Execution flow

### First use (founding run)
`bower.init` → `bower.scan.deep --founding` (Phase 1: tree discovery; Phase 2: scan folders one at a time, resume across sessions) → `bower.analyze` → present high-confidence proposals as batch → if accepted: `bower.apply`. Founding run batch approval grants immediate pattern promotion credit. Use `--analyze-now` for early results before all folders scanned.

### Steady state
Daily light scan at 02:00 PT: `bower.scan.light` → arrival detection → auto-apply promoted high-confidence matches if quiet mode on. Weekly deep scan Sunday 01:00 PT: `bower.scan.deep` → `bower.analyze` → emit Drive health signal to Vesper. Silent unless something needs attention.

### Arrival detection
After every light scan, for each new/modified file: classify → check `pattern_key` against `auto_approved_patterns`. High-confidence match: generate `approved` proposal (auto-apply if quiet mode). Medium-confidence: `pending`. No match: normal `pending`.

### Simulation
Read-only scan of specified folder → apply full analysis pipeline → print narrative report. No proposals, logs, journals, or state changes written. See `references/organization_rules.md` for simulation output format.

### Apply run
Description auto-writes first → sort by confidence tier → apply `apply_cap` → per-proposal staleness check → execute via Google Drive → log to `move_log.jsonl` → produce digest (suppressed in quiet mode if all succeeded) → write Action Journal.

**Verification after apply**: After `bower.apply` completes, read back applied proposal IDs from `move_log.jsonl` and confirm each file exists at its new destination via Google Drive list. Report any mismatches (file not found at destination) as failed moves. Verify the move log entry count matches the number of executed proposals.

### Undo run
Read move log records → staleness check → restore `previous_value` → execute reversal → log to `undo_log.jsonl` → record feedback → trigger pattern demotion if auto-approved → write Action Journal.

## Decision model

Read these reference files before the operations they govern:

| File | When to read |
|------|-------------|
| `references/organization_rules.md` | Before every `bower.analyze` run; defines preference inference, pattern promotion, taxonomy inference, all proposal generation rules, permission lookup, feedback suppression, recalibration, scan resume, cap behavior, digest format, and review narrative |
| `references/domains.md` | Before every `bower.analyze` run; defines domain detection, prescriptive/descriptive mode, canonical structures, and per-domain filing rules for Taxes, Projects, Home, Finance, Legal, Medical, Archive, Education |
| `references/analysis_schema.md` | Before `bower.scan.deep` or `bower.analyze`; defines all data schemas including preference profile, folder_index, scan_progress, proposals, move log, undo log, feedback log, and config |

Key invariants:
- Never propose a delete.
- Never move a starred file unless confidence is high and destination is unambiguous.
- Never flatten a folder with 3+ children.
- Never propose a move into a non-existent folder without a preceding create_folder proposal.
- Renames are `high` confidence only.
- Description overwrites require approval. Auto-writes to empty fields do not.
- Domain logic runs before generic outlier logic per file. Not both.
- Prescriptive domain logic only applies when domain is clearly started (5+ files or 2+ subfolders in domain root).
- Always preserve `previous_value` in move_log before any overwrite.
- Always run staleness check per-proposal immediately before execution.
- Auto-approved proposals still pass staleness gate and permission check.
- Arrival detection auto-approves only high-confidence pattern matches. Med-confidence matches stay pending.
- Founding run batch approval grants immediate pattern promotion credit for all executed proposals.
- Simulation writes nothing: no proposals, no logs, no journal, no state changes of any kind.
- Quiet mode suppresses digest output only. It never changes what requires approval.
- Load feedback suppressions and recalibration data before every `bower.analyze` run.
- Rebuild preference profile on every deep scan; respect locked fields.
- Medical file highlights in apply digest and simulation output: folder path and count only, never filenames or content.
- Full file text must never appear in logs, journals, or output.

## Scan output

`bower.scan.deep` produces: `folder_index.json` (Phase 1), `scans/{folder_id}.json` per folder tree (Phase 2), `drive_digest.json` (updated per folder), `scan_progress.json`, scan event in `scan_events.jsonl`.

`bower.scan.light` produces: updated `scans/{folder_id}.json` files, scan event with drift_rate (aborts if drift exceeds threshold).

`bower.analyze` produces: outlier report in `analysis_events.jsonl`, expired proposals marked in `proposals.jsonl`, new proposals appended with `status: pending` and `expires_at`.

## Google Drive access

Bower uses Google Drive access for: list files/folders, read file content, move file to folder, rename file/folder, create folder, update file description. Bower never calls delete operations. Phase 1 lists all folders (fast metadata query). Phase 2 processes one folder tree at a time, capturing: id, name, mimeType, parents, modifiedTime, starred, size, trashed, description. Exclude trashed files. Fetch permissions for each folder; if unavailable, set `permissions_available: false` and suppress all move proposals.

## Background tasks

| Job | Schedule | Action |
|-----|----------|--------|
| `bower:scan` | Daily 02:00 PT | `bower.scan.light` → arrival detection → auto-apply promoted matches if quiet mode on |
| `bower:weekly-deep` | Sunday 01:00 PT | `bower.scan.deep` → `bower.analyze` → emit Drive health signal to Vesper |

Register during `bower.init`. Check for existing scheduled tasks before registering to avoid duplicates. All cron jobs use `sessionTarget: isolated`, `lightContext: true`, `wakeMode: next-heartbeat`.

### Vesper Drive health signal

Emitted weekly after Sunday deep scan as an InsightProposal with `proposal_type: routine_prediction` containing: Drive health score delta, files organized in past 7 days, active auto-approved patterns, domains that gained/lost structure, suppressed outlier classes worth surfacing. Vesper decides whether to include it in the weekly briefing.

## Optional skill cooperation

- **Vesper** — Bower emits a weekly Drive health InsightProposal after each Sunday deep scan. If Vesper is absent, the signal is dropped silently.
- **Elephas** — Bower emits structured signals for all Drive artifacts and entities encountered during scans. If Elephas is absent, signal files accumulate in the journal payload until Elephas processes them.
- **Mentor** — Bower's journals are evaluated by Mentor for OKR scoring. No action required from Bower.

## Inter-skill interfaces

Bower emits to:
- the `briefing` payload field — weekly Drive health InsightProposal (Sunday deep scan only)
- the `signal` payload field — entity and artifact signals for all Drive content (every scan)

Bower receives from: none.

## Journal outputs

Scan commands (`bower.scan.deep`, `bower.scan.light`) and `bower.analyze` emit **Observation Journals**. `bower.apply` and `bower.undo` emit **Action Journals**.

All Observation Journals from scan commands include `entities_observed`, `relationships_observed`, and `preferences_observed` in `decision.payload`. Journal path: `{agent_root}/commons/journals/ocas-bower/YYYY-MM-DD/{run_id}.json`.

## Recovery Behavior

Implements the recovery contract from `spec-ocas-recovery.md`.

- **Evidence**: Every scheduled run writes to `evidence.jsonl`, including no-op runs. `not_activity_reason` is mandatory when no side effects occur.
- **Gap detection**: On every wake, checks evidence log for most recent completed run. If gap exceeds cadence (24h light, 7d deep), logs `gap_detected` and runs a compact remedial pass.
- **Degraded mode**: When Google Drive access fails, enters degraded mode and produces a partial Drive health report. Evidence log records `degraded: google_drive`.
- **Log compaction**: Evidence and decision logs older than 30 days (no-op) or 90 days (error/gap) compacted to weekly summaries. Escalation records never auto-deleted. Last 7 days of raw entries always retained.

## Storage layout

```
{agent_root}/commons/data/ocas-bower/
  config.json
  folder_index.json           -- full folder tree with paths, depths, permissions
  drive_digest.json           -- lightweight holistic Drive summary
  scan_progress.json          -- scan state: folders done/pending, resume point
  scans/                      -- one file per top-level folder tree
    {folder_id}.json
    _root.json                 -- files at Drive root with no parent folder
  preference_profile.json     -- inferred preferences, domains, patterns, class precision
  proposals.jsonl             -- all proposals: pending, approved, executed, failed, skipped, expired
  move_log.jsonl              -- record of every executed operation with previous_value
  undo_log.jsonl              -- record of every executed undo
  feedback_log.jsonl          -- user undo and reject events for suppression/demotion learning
  scan_events.jsonl           -- scan run history
  analysis_events.jsonl       -- analysis run history
  health_history.jsonl        -- weekly Drive health score snapshots
  decisions.jsonl             -- DecisionRecords
  intents.jsonl               -- durable intent queue (append-only)
  evidence.jsonl              -- execution evidence log (append-only)
  reports/                    -- dated apply digest Markdown files

{agent_root}/commons/journals/ocas-bower/
  YYYY-MM-DD/{run_id}.json
```

## OKRs

```yaml
skill_okrs:
  - name: proposal_precision
    metric: fraction of executed proposals not subsequently undone
    direction: maximize
    target: 0.80
    evaluation_window: 30_runs
  - name: apply_success_rate
    metric: fraction of approved proposals successfully applied
    direction: maximize
    target: 0.95
    evaluation_window: 30_runs
  - name: auto_approve_precision
    metric: fraction of auto-approved proposals not subsequently undone
    direction: maximize
    target: 0.90
    evaluation_window: 30_runs
  - name: data_integrity
    metric: fraction of Drive scans that pass schema validation
    direction: maximize
    target: 1.00
    evaluation_window: 30_runs
```

Tracked metrics: `proposal_precision` (≥0.80), `apply_success_rate` (≥0.95), `staleness_skip_rate` (≤0.05), `auto_approve_precision` (≥0.90), `false_positive_rate` (≤0.10), `scan_coverage` (1.0), `proposal_expiry_rate` (≤0.20), plus tracking-only: `content_influence_rate`, `description_coverage_rate`, `domain_proposal_rate`, `feedback_suppression_rate`.

## Initialization

`bower.init`: creates data/journal directories, writes `config.json` with defaults, registers cron jobs `bower:scan` and `bower:weekly-deep` (check platform registry first to avoid duplicates).

## Self-update

`bower.update` pulls the latest package from the `source:` URL in frontmatter. Compares local vs. remote version via GitHub API. If different: downloads tarball, extracts, replaces. Retries once on failure. Output: `I updated Bower from version {old} to {new}`. Silent if already current.

## Visibility

public

## Gotchas

- **Drift threshold aborts light scans** — If the light scan detects significant structural drift, it aborts entirely rather than producing partial results. A subsequent deep scan is needed to re-establish the baseline.
- **Staleness checks execute per-proposal** — Even auto-approved, high-confidence proposals pass through a staleness check immediately before execution. A file moved between scan and apply can cause a proposal to quietly skip.
- **Permission fetch suppresses all move proposals** — If folder permissions are unavailable (API error or scope missing), Bower suppresses *all* move proposals for that folder—not just the affected files—and falls back to description-only suggestions.
- **Simulation writes absolutely nothing** — `bower.simulate` produces no proposals, logs, journals, or state changes. It is safe to run repeatedly but provides no persistent output.
- **Medical file redaction** — Medical folder contents are never logged, journaled, or surfaced by filename. Only folder paths and file counts appear in apply digests and simulation output.
- **Quiet mode suppresses only the digest** — Enabling quiet mode hides the apply digest output but does not bypass approval requirements, staleness checks, or any safety gate.

## Support file map

| File | When to read |
|------|-------------|
| `references/organization_rules.md` | Before every `bower.analyze` run; defines preference inference, pattern promotion, taxonomy inference, all proposal generation rules, permission lookup, feedback suppression, recalibration, scan resume, cap behavior, digest format, and review narrative |
| `references/domains.md` | Before every `bower.analyze` run; defines domain detection, prescriptive/descriptive mode, canonical structures, and per-domain filing rules for Taxes, Projects, Home, Finance, Legal, Medical, Archive, Education |
| `references/analysis_schema.md` | Before `bower.scan.deep` or `bower.analyze`; defines all data schemas including preference profile, folder_index, scan_progress, proposals, move log, undo log, feedback log, and config |
| `references/signal_examples.md` | Before emitting signals to Elephas; JSON schema examples for all five signal types |
| `references/scan-debug.md` | When debugging scan issues, resume failures, or light scan anomalies |
| `references/command_reference.md` | When you need full command flag descriptions and semantics |

## Scan Debug & Operational Notes

Debug procedures, resume patterns, file layout facts, and light scan lessons.
Full documentation: `references/scan-debug.md`
