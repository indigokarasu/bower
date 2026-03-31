---
name: ocas-bower
description: Automatically organizes Google Drive by scanning its full structure and file contents, building a personalized preference profile, applying domain-specific logic (taxes by year, projects by name, home by system, finance by institution, etc.), and executing non-destructive moves, renames, and description writes in the background. Learns your organizational style over time and auto-approves patterns you've consistently accepted. Never deletes files. Always requires approval before applying changes unless a pattern has been promoted.
metadata: {"openclaw":{"emoji":"🪺"}}
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

Bower does: scan Drive structure and file contents, build a preference profile from evidence, detect and apply domain-specific organization logic, identify outliers, propose folder moves, renames, and description writes, auto-approve promoted patterns, apply approved changes via the Google Drive MCP, maintain a full audit trail.

Bower does not: delete files, manage sharing permissions, create top-level taxonomy from scratch (it infers from what exists), interact with any non-Drive storage, apply domain logic to a domain it hasn't detected as clearly started.

Adjacent responsibility: Sift handles web research and document analysis. Elephas handles Chronicle ingestion. Bower is self-contained and does not depend on either.

## Commands

`bower.scan.deep [--founding]` — Full Drive crawl. With `--founding` flag (first use only): after scan and analysis, presents all high-confidence proposals grouped by domain as a single accept/reject batch. One decision bootstraps pattern promotion immediately. Builds or refreshes the structural model and preference profile. Reads file contents for classification and description generation. Detects domains and infers naming conventions, depth preference, folder density, and sacred folders. Checkpoints every 500 files; resumes automatically if interrupted.

`bower.scan.light` — Incremental scan of recently modified files and known outlier zones. Uses existing structural model as baseline. Runs drift detection before proceeding; aborts if drift exceeds threshold. After scan, checks for arrival matches against promoted patterns and auto-applies them immediately if quiet mode is enabled.

`bower.analyze` — Runs analysis against the current structural model and preference profile. Loads feedback suppressions and recalibration data, applies domain logic first then generic rules, expires stale proposals, auto-approves pattern-matched proposals, generates ranked move/rename/description proposals. Does not touch Drive.

`bower.simulate [--path "Folder/Subfolder"] [--depth N]` — Scans the specified folder (and up to N levels deep, default: full depth) without touching anything or writing any state. Produces a narrative report showing exactly what Bower would do: moves, renames, folder creations, description writes, and why. No proposals written to `proposals.jsonl`. No journal written. Purely read-only. Use to preview Bower's behavior before first use, or to understand what it would do to an unfamiliar folder.

`bower.proposals.review [--type move|rename|describe] [--domain taxes|projects|home|...]` — Opens with a Drive health narrative, then lists pending proposals grouped by destination folder. Shows confidence tier, domain tag, content signal indicator, auto-approve status, and reasoning per proposal.

`bower.proposals.approve [--tier high] [--ids p_xxx,p_yyy] [--all] [--type move|rename|describe]` — Approves a subset of proposals for execution. Requires explicit scope. Never approves all without `--all` flag.

`bower.proposals.reject [--ids p_xxx,p_yyy]` — Rejects specific proposals and records feedback. Rejected patterns are suppressed and may trigger demotion of auto-approved patterns.

`bower.apply [--dry-run]` — Executes all approved and auto-approved proposals (up to `apply_cap`) and all description auto-writes (up to `describe_auto_cap`). Each proposal staleness-checked immediately before execution. In quiet mode, skips digest output unless something failed or was skipped. With `--dry-run`, shows the digest without touching Drive.

`bower.undo [--ids mvl_xxx,mvl_yyy] [--last N]` — Reverses executed moves, renames, and description writes. Restores `previous_value` for all operations. Records feedback for move and rename undos; triggers pattern demotion if the undone proposal was auto-approved.

`bower.preferences.show` — Displays the current preference profile: detected naming conventions, depth preference, detected domains and their mode (prescriptive/descriptive), auto-approved patterns and their confidence, suppressed outlier classes, and sacred folders.

`bower.preferences.lock [--field naming|depth|domain:taxes|...] [--pattern key]` — Locks a specific preference field or pattern so Bower's inference never overwrites it.

`bower.preferences.quiet [--on|--off]` — Enables or disables quiet mode. In quiet mode, `bower.apply` executes all approved and auto-approved proposals silently and only surfaces output when something failed, was skipped, or hit a cap. Quiet mode does not change what requires approval -- only suppresses confirmation output for successful runs.

`bower.feedback.clear [--pattern key] [--all]` — Clears learned suppression patterns or demotions.

`bower.status [--trend]` — Prints SkillStatus: last scan time, preference profile summary, active domains, quiet mode state, drift rate, proposal counts by tier and type, auto-approved pattern count, suppressed class list, last apply run, caps remaining, any errors. With `--trend`: shows Drive health score over the last 8 weeks.

`bower.init` — Initializes storage, registers background jobs, writes default config. Runs automatically on first use. On first run, prompts: "Run founding scan now? This will scan your Drive and present a one-time batch approval to bootstrap Bower's preferences."

## Execution flow

### First use (founding run)
1. Run `bower.init`. On first run it asks: "Run founding scan now?"
2. Run `bower.scan.deep --founding`.
3. Scan completes. Bower builds structural model, preference profile, and domain detection.
4. Bower runs `bower.analyze` automatically.
5. Present all high-confidence proposals grouped by domain as a single batch: "Bower found 47 high-confidence proposals across 4 domains. Accept all / Review / Reject all."
6. If accepted: mark all high-confidence proposals `approved`, run `bower.apply` immediately. Pattern promotion credit is granted for all executed proposals -- no need to wait for 3 cycles.
7. If reviewed: user approves/rejects per domain group. Execute approved subset.
8. Founding run complete. Bower is now bootstrapped with real preference data.

### Steady state (background)
Daily light scan at 02:00 PT: `bower.scan.light` → arrival detection → `bower.analyze` → auto-apply promoted patterns if quiet mode enabled → digest only if failures or skips occurred.

Weekly deep scan Sunday 01:00 PT: `bower.scan.deep` → `bower.analyze` → emit Drive health signal to Vesper.

Bower never auto-applies proposals that haven't been approved or pattern-promoted. The steady state is silent unless something needs attention.

### Arrival detection
After every `bower.scan.light`, for each newly added or modified file:
1. Classify the file (domain, content summary, outlier class) using the current structural model.
2. Check its `pattern_key` against `auto_approved_patterns` in the preference profile.
3. If a promoted pattern matches with `confidence: high`: generate an `approved` proposal directly (skip `pending`). If quiet mode is on, apply immediately within the same session.
4. If a promoted pattern matches with `confidence: med`: generate a `pending` proposal. Do not auto-apply.
5. If no pattern matches: generate a normal `pending` proposal for next review cycle.

Arrival detection runs within the light scan session. It does not spawn a separate apply run unless quiet mode is on and high-confidence arrivals were found.

### Simulation run
`bower.simulate --path "Folder/Subfolder"`:
1. Fetch the specified folder and its full contents from the Drive MCP (reads only, no writes).
2. Read file contents for classification (same rules as deep scan, same content privacy boundary).
3. Apply the full analysis pipeline: domain logic, generic rules, preference profile, confidence tiers.
4. Do not write to `proposals.jsonl`, `analysis_events.jsonl`, or any log. Do not write a journal.
5. Produce a simulation report (see Simulation output below). Print to user only.

Simulation is completely read-only. It uses the existing preference profile and structural model but does not update them. If no structural model exists yet, simulate using domain logic and generic rules without preference calibration, and note this in the report.

### Simulation output format
```
Bower Simulation — {Folder Path}
Scanned {N} files across {M} subfolders
────────────────────────────────────────
Domain detected: {domain} ({prescriptive|descriptive})

Would create {N} folders:
  + Finance/Invoices/2026/          (domain: finance — no year subfolder exists)

Would move {N} files:
  invoice_march.pdf
    From: Finance/
    To:   Finance/Invoices/2026/
    Why:  Invoice detected in content; year 2026 in filename; prescriptive Finance domain rule.
    Confidence: high

  Copy of Budget v3 final.xlsx
    From: Finance/
    To:   Finance/
    Rename to: 2026-Q1 Budget.xlsx
    Why:  Poor name (contains "copy of", "v3", "final"); sibling convention is YYYY-Q# prefix.
    Confidence: high

Would write descriptions to {N} files (empty field):
  ...

Would propose {N} overwrites for review (existing descriptions):
  ...

Would not move {N} files:
  taxes_2024.pdf — already correctly placed (Taxes/2024/Returns/)
  contract_nda.pdf — permission change would result (source and destination differ)

────────────────────────────────────────
Summary: {N} moves, {N} renames, {N} folder creations, {N} descriptions
         {N} files already correctly placed
         {N} files blocked (permission change)
```

Show "would not move" only for files that are either already correctly placed or explicitly blocked. Do not list every file in the folder.

### Apply run
1. If `--dry-run`, compute and print the digest without touching Drive, then exit.
2. **Description auto-writes:** execute up to `describe_auto_cap`. Log each to `move_log.jsonl`.
3. Check that approved proposals exist with `status: approved`.
4. Sort: folder creations → high-confidence moves → high-confidence renames → med/low moves → description overwrites.
5. Apply `apply_cap`. Mark held proposals `skipped` with `skip_reason: cap_exceeded`.
6. Per-proposal staleness check immediately before execution.
7. Execute via Google Drive MCP.
8. On success: update to `executed`, append to `move_log.jsonl`.
9. On failure: update to `failed`, log error, continue.
10. If quiet mode off, or if any failure/skip occurred: produce and print apply digest, save to `reports/YYYY-MM-DD-apply.md`.
11. If quiet mode on and all succeeded: no output.
12. Write Action Journal.

### Undo run
1. Read specified move log records from `move_log.jsonl`.
2. Per-record staleness check. If the file has moved again since apply, skip and warn.
3. Restore `previous_value` for renames and description operations.
4. Execute reversal via MCP.
5. On success: append to `undo_log.jsonl`. Append feedback record for move and rename undos. Trigger pattern demotion if proposal was auto-approved.
6. On failure: log error, continue.
7. Write Action Journal.

## Decision model

Read `references/organization_rules.md` before generating proposals. That file defines:
- Preference inference: how to build the preference profile from evidence (naming, depth, density, sacred folders, domain detection)
- Pattern promotion: threshold (3 executions, no undos), auto-approve behavior, demotion rules
- Taxonomy inference: how preference profile shapes proposal style
- Domain logic: prescriptive vs. descriptive mode selection; domain rules run before generic rules
- Content classification: what to read, how to summarize, how to weight content signals
- Description generation: when to auto-write vs. propose overwrite, the "meaningfully better" test
- Rename rules: high-confidence only, five required conditions, forbidden categories
- Outlier classification criteria including domain-specific outlier classes
- Confidence tier assignment: domain-prescriptive starts high, domain-descriptive starts med
- Forbidden move and rename categories
- Permission safety: use `folder_index` for O(1) comparison; any difference blocks the proposal
- Feedback learning: suppression map, suppression tiers
- Confidence recalibration: class precision tracking, automatic tier downgrade and suppression
- Scan resume: checkpoint every 500 files, 24-hour resume window
- Apply cap: `apply_cap` for approved proposals, `describe_auto_cap` for auto-writes, independent
- Apply digest: format, highlights grouping, medical file privacy restriction
- Review narrative: Drive health paragraph + destination-grouped proposals

Read `references/domains.md` before running `bower.analyze`. That file defines detection vocabulary, canonical structure, and prescriptive rules for: Taxes, Projects, Home, Finance, Legal, Medical, Archive, Education, multi-domain resolution, and unknown domain candidate logging.

Read `references/analysis_schema.md` before `bower.scan.deep` or `bower.analyze` for all data schemas including preference profile structure.

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

`bower.scan.deep` produces:
- A structural model written to `structural_model.json` (full Drive tree with metadata, permissions, content summaries, existing descriptions, and proposed descriptions)
- A scan event appended to `scan_events.jsonl` (includes content_read_count, content_skip_count, description_proposed_count)

`bower.scan.light` produces:
- An updated structural model for changed files only
- A scan event with drift_rate; aborts and does not update the model if drift exceeds threshold

`bower.analyze` produces:
- An outlier report appended to `analysis_events.jsonl`
- Expired proposals marked in `proposals.jsonl`
- New move, rename, and description proposals appended to `proposals.jsonl` with `status: pending` and `expires_at` set

## Google Drive MCP usage

Bower uses the Google Drive MCP for all Drive operations. Available operations:
- List files and folders (used during scan)
- Read file content (used during deep scan for content classification and description generation)
- Move file to folder
- Rename file or folder
- Create folder
- Update file description field

Bower never calls delete operations. If the MCP exposes a delete operation, Bower must not invoke it under any circumstances.

During `bower.scan.deep`, paginate through all files using the MCP list operation. Capture for each file: id, name, mimeType, parents, modifiedTime, starred, size, trashed, description. Exclude trashed files from the structural model.

For every folder in the results, additionally fetch its permissions resource and store the full permission set (direct + inherited) in the structural model. Permission data is required for move proposal generation. If the MCP does not expose permissions, set `permissions_available: false` in the scan event and suppress all move proposals.

## Background tasks

| Job | Mechanism | Schedule | Action |
|-----|-----------|----------|--------|
| `bower:scan` | cron | Daily at 02:00 PT | `bower.scan.light` → arrival detection → auto-apply promoted matches if quiet mode on |
| `bower:weekly-deep` | cron | Sunday at 01:00 PT | `bower.scan.deep` → `bower.analyze` → emit Drive health signal to Vesper |

Register during `bower.init`. Check for existing jobs with `openclaw cron list` before registering to avoid duplicates.

All cron jobs use `sessionTarget: isolated`, `lightContext: true`, `wakeMode: next-heartbeat`.

### Vesper Drive health signal

Emitted once per week after the Sunday deep scan. Written to the Vesper intake directory per `spec-ocas-interfaces.md`. Format: an InsightProposal with `proposal_type: routine_prediction` containing:
- Drive health score this week vs. last week (delta)
- Files organized in the past 7 days (count)
- Active auto-approved patterns (count)
- Any domains that gained or lost structure
- Any suppressed outlier classes worth surfacing

Vesper decides whether to include it in the weekly briefing. Bower emits it regardless.

## Optional skill cooperation

Bower may cooperate with these skills when present but never depends on them:

- **Vesper** -- Bower emits a weekly Drive health InsightProposal to Vesper's intake directory after each Sunday deep scan. Vesper decides whether to surface it. If Vesper is absent, the signal is dropped silently.
- **Elephas** -- Bower may emit Signals for newly discovered folder structures or naming patterns as Chronicle candidates. Optional.
- **Mentor** -- Bower's journals are evaluated by Mentor for OKR scoring. No action required from Bower.

## Inter-skill interfaces

Bower emits to:
- `~/openclaw/data/ocas-vesper/intake/{proposal_id}.json` -- weekly Drive health InsightProposal (Sunday deep scan only)

Bower receives from: none.

## Journal outputs

`bower.scan.deep` and `bower.scan.light` emit **Observation Journals** -- no external side effects.

`bower.analyze` emits an **Observation Journal** -- no external side effects.

`bower.apply` and `bower.undo` emit **Action Journals** -- external side effects (file moves, renames, description writes) occurred.

Journal path: `~/openclaw/journals/ocas-bower/YYYY-MM-DD/{run_id}.json`

## Storage layout

```
~/openclaw/data/ocas-bower/
  config.json
  structural_model.json       -- current Drive tree with folder_index (overwritten each deep scan)
  preference_profile.json     -- inferred preferences, domains, patterns, class precision (updated each deep scan)
  proposals.jsonl             -- all proposals: pending, approved, executed, failed, skipped, expired
  move_log.jsonl              -- record of every executed operation with previous_value
  undo_log.jsonl              -- record of every executed undo
  feedback_log.jsonl          -- user undo and reject events for suppression and demotion learning
  scan_events.jsonl           -- scan run history
  analysis_events.jsonl       -- analysis run history
  health_history.jsonl        -- weekly Drive health score snapshots (appended each Sunday)
  decisions.jsonl             -- DecisionRecords
  reports/                    -- dated apply digest Markdown files
  staging/
    scan_checkpoint.json      -- deep scan resume checkpoint (deleted on completion)

~/openclaw/journals/ocas-bower/
  YYYY-MM-DD/{run_id}.json
```

## OKR targets

| Metric | Target | Direction |
|--------|--------|-----------|
| `proposal_precision` | >= 0.80 | maximize |
| `apply_success_rate` | >= 0.95 | maximize |
| `staleness_skip_rate` | <= 0.05 | minimize |
| `content_influence_rate` | track | maximize |
| `description_coverage_rate` | track | maximize |
| `domain_proposal_rate` | track | maximize |
| `auto_approve_precision` | >= 0.90 | maximize |
| `false_positive_rate` | <= 0.10 | minimize |
| `scan_coverage` | 1.0 | fixed |
| `proposal_expiry_rate` | <= 0.20 | minimize |
| `feedback_suppression_rate` | track | track |

`proposal_precision` -- fraction of executed proposals not subsequently undone.
`staleness_skip_rate` -- fraction of approved proposals skipped due to source_moved or description_changed.
`domain_proposal_rate` -- fraction of proposals generated by domain logic vs. generic rules; higher over time indicates better domain coverage.
`auto_approve_precision` -- fraction of auto-approved proposals not subsequently undone; must exceed 0.90 or pattern promotion thresholds tighten.
`feedback_suppression_rate` -- fraction of potential proposals suppressed by feedback; tracked to detect over-suppression.

## Visibility

public

## Support files

| File | When to read |
|------|-------------|
| `references/organization_rules.md` | Before every `bower.analyze` run; defines preference inference, pattern promotion, taxonomy inference, all proposal generation rules, permission lookup, feedback suppression, recalibration, scan resume, cap behavior, digest format, and review narrative |
| `references/domains.md` | Before every `bower.analyze` run; defines domain detection, prescriptive/descriptive mode, canonical structures, and per-domain filing rules for Taxes, Projects, Home, Finance, Legal, Medical, Archive, Education |
| `references/analysis_schema.md` | Before `bower.scan.deep` or `bower.analyze`; defines all data schemas including preference profile, structural model, folder_index, proposals, move log, undo log, feedback log, scan checkpoint, and config |