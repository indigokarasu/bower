# 🪺 Bower

Bower keeps Google Drive organized without ever deleting anything. It scans your full Drive structure and file contents, builds a personalized preference profile from your existing organization patterns, applies domain-specific logic where it detects known domains, and executes non-destructive moves, renames, and description writes -- learning your organizational style over time and auto-approving patterns you've consistently accepted. The goal: you go to sleep and wake up to a Drive that looks the way you would have organized it yourself.

---

## Overview

Bower crawls your Google Drive, classifies files by content and context, and proposes moves, renames, and description writes based on a combination of domain-specific rules (taxes by year, projects by name, home by system, finance by institution) and your own inferred preferences. It never deletes files, never changes sharing permissions, and always preserves a full audit trail for undo. Over time, patterns you consistently approve are promoted to auto-approve, so Bower handles routine filing silently in the background.

## Commands

| Command | Description |
|---|---|
| `bower.scan.deep [--founding]` | Full Drive crawl with content reading and description generation |
| `bower.scan.light` | Incremental scan of recent changes with arrival detection |
| `bower.analyze` | Generate ranked proposals from the current structural model |
| `bower.simulate [--path] [--depth]` | Read-only preview of what Bower would do to a folder |
| `bower.proposals.review` | Drive health narrative + pending proposals grouped by destination |
| `bower.proposals.approve` | Approve proposals by tier, ID, type, or all |
| `bower.proposals.reject` | Reject proposals and record feedback |
| `bower.apply [--dry-run]` | Execute approved proposals (capped per run) |
| `bower.undo [--ids] [--last N]` | Reverse executed operations |
| `bower.preferences.show` | Display inferred preferences, domains, and auto-approved patterns |
| `bower.preferences.lock` | Lock a preference field from inference |
| `bower.preferences.quiet` | Enable/disable quiet mode |
| `bower.feedback.clear` | Clear learned suppression patterns |
| `bower.status [--trend]` | System health, proposal counts, auto-approve stats |
| `bower.init` | Initialize storage and register background jobs |

## Setup

`bower.init` runs automatically on first invocation. It creates all required directories, writes default config, and registers background cron jobs. On first run, it prompts to launch a founding scan -- a one-time batch bootstrap that scans your Drive and presents high-confidence proposals as a single accept/reject decision to immediately establish your preferences.

## Domains

Bower recognizes and applies domain-specific organization rules for:

- **Taxes** -- year-first hierarchy (Returns, Supporting Documents, Correspondence)
- **Projects** -- project-name-first hierarchy with optional Active/Archive split
- **Home** -- system-based or year-based (HVAC, Roof, Kitchen, etc.)
- **Finance** -- institution-first, year-second (Statements, Confirmations)
- **Legal** -- document-type-first (Contracts, Personal, Property, Employment, NDAs)
- **Medical** -- person-first with Insurance, Records, Prescriptions subfolders
- **Archive** -- low-intervention, respects intentional archival
- **Education** -- institution/program-first with course subfolders

Each domain can operate in prescriptive mode (moves toward a canonical structure) or descriptive mode (extends your existing variant).

## Dependencies

**OCAS Skills (optional)**
- [Vesper](https://github.com/indigokarasu/vesper) -- receives weekly Drive health signal for briefings
- [Elephas](https://github.com/indigokarasu/elephas) -- may receive folder structure Signals as Chronicle candidates

**External**
- Google Drive MCP -- required for all Drive operations

## Scheduled Tasks

| Job | Schedule | Action |
|---|---|---|
| `bower:scan` | Daily 2:00 AM PT | Light scan + arrival detection + auto-apply if quiet mode on |
| `bower:weekly-deep` | Sunday 1:00 AM PT | Deep scan + analyze + Vesper health signal |

## Key Invariants

- Never deletes files
- Never changes sharing permissions
- Renames are high-confidence only
- Description overwrites require approval; auto-writes to empty fields do not
- Auto-approved proposals still pass staleness and permission checks
- Full audit trail with undo support for every operation
- Medical files: folder path and count only in output, never filenames or content

## Changelog

### v1.0.0 -- March 30, 2026
- Initial release with full scan, analyze, simulate, apply, and undo lifecycle
- Domain support for Taxes, Projects, Home, Finance, Legal, Medical, Archive, Education
- Preference inference, pattern promotion, feedback learning, and confidence recalibration
- Founding run for one-time bootstrap
- Background scheduling: daily light scan, weekly deep scan

---

*Bower is part of the [OpenClaw Agent Suite](https://github.com/indigokarasu) -- a collection of interconnected skills for personal intelligence, autonomous research, and continuous self-improvement. Each skill owns a narrow responsibility and communicates with others through structured signal files, shared journals, and Chronicle, a long-term knowledge graph that accumulates verified facts over time.*
