---
name: bower-mempalace-ingest
description: >
  Ingest Bower (Google Drive scan) data into MemPalace. Extracts domain
  structures, content themes, health/finance/travel topics, and people
  references from Bower's scan data and files them as MemPalace drawers
  and knowledge graph facts. Designed to run as a cron job after Bower's
  weekly deep scan.
metadata:
  author: Indigo Karasu
  version: "1.0.0"
---

# Bower → MemPalace Ingestion

## Purpose

Bower scans ~49K files across Google Drive. MemPalace is the agent's long-term memory. This pipeline bridges them — extracting personal insights from Bower's data and filing them where the agent can recall them across sessions.

## Architecture

```
Bower scan (Sunday 01:00 PT)
  → bower_mem_ingest.py (extracts themes, domains, KG facts)
    → mem_ingest_output.json (structured output)
      → cron job (Monday 03:00 UTC) files into MemPalace
        → bower/overview drawer + KG facts
```

## Data Sources

| Bower file | What it contains | Use |
|---|---|---|
| `drive_digest.json` | Total files/folders, scan coverage, domains | Overview stats |
| `preference_profile.json` | Naming conventions, depth preference, domains detected | Organizational patterns |
| `content_summaries.jsonl` | 5,310+ LLM-generated file summaries | Theme extraction, people, health/finance/travel |
| `scans/*.json` | 74K+ folder scan files with file metadata | File type counts |

## Script Location

```
~/.hermes/commons/data/ocas-bower/bower_mem_ingest.py
```

Output: `~/.hermes/commons/data/ocas-bower/mem_ingest_output.json`

## What Gets Extracted

- **Domains**: archive, home, medical, taxes (with mode: prescriptive/descriptive)
- **Content themes**: API, GitHub, code, jobs, design, health, tax, music, finance, etc.
- **Health topics**: lab results, UCSF, vision, surgery, glucose, dental
- **Finance topics**: tax, IRA, budget, credit, banking, investments, RSU, IPO
- **Travel/places**: Japan, Hawaii/Honu Hale, San Francisco, Austin, Europe
- **KG facts**: automatically generates `Jared → visited → X`, `Jared → has_domain → X`

## MemPalace Structure

```
wing: bower
  room: overview        — comprehensive Drive snapshot (updated weekly)
  room: scan-updates    — weekly incremental updates from cron
  room: scan-2026-04-15-findings — initial deep analysis
```

## Cron Job

- **Name**: `bower-mempalace-ingest`
- **Schedule**: `0 3 * * 1` (Monday 03:00 UTC, after Sunday Bower deep scan)
- **Skills**: `mcp-mempalace`
- **Process**: runs script → reads output → files drawer + KG facts

## Key Design Decisions

1. **Aggregate, don't file individually** — 49K files can't become 49K drawers. Summarize at domain/theme level.
2. **Content summaries are gold** — the 5,310 LLM summaries contain personal insights (health, travel, people). Raw file metadata alone is not useful for MemPalace.
3. **KG facts for queryability** — domains, places visited, medical providers as graph facts enable `mcp_mempalace_mempalace_kg_query("Jared")`.
4. **Script outputs JSON, cron files it** — MCP tools can't be called from `execute_code`. Two-phase design: extract (Python) → file (cron agent with MCP access).

## Manual Run

```bash
# Extract insights
python3 ~/.hermes/commons/data/ocas-bower/bower_mem_ingest.py

# Check output
cat ~/.hermes/commons/data/ocas-bower/mem_ingest_output.json | python3 -m json.tool | head -50
```

To file manually into MemPalace, use the MCP tools:
- `mcp_mempalace_mempalace_add_drawer` (wing="bower", room="scan-updates")
- `mcp_mempalace_mempalace_kg_add` (for each fact in the `kg_facts` array)
