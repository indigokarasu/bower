# MemPalace Ingestion

Extract insights from Bower's Google Drive scan data and file them in MemPalace for long-term agent memory.

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
{agent_root}/commons/data/ocas-bower/scripts/bower_mem_ingest.py
```

Output: `{agent_root}/commons/data/ocas-bower/mem_ingest_output.json`

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

## Usage

### Manual Run
```python
# In execute_code
exec(open('{agent_root}/commons/data/ocas-bower/scripts/bower_mem_ingest.py').read())

# Check output
import json
with open('{agent_root}/commons/data/ocas-bower/mem_ingest_output.json') as f:
    output = json.load(f)
print(json.dumps(output, indent=2)[:1000])
```

### File to MemPalace
After the script runs, use MCP tools to file the output:

```python
# File main content drawer
mcp_mempalace_mempalace_add_drawer(
    wing="bower", 
    room="scan-updates",
    content=output['main_content']
)

# Add KG facts
for fact in output['kg_facts']:
    mcp_mempalace_mempalace_kg_add(
        subject=fact['subject'],
        predicate=fact['predicate'], 
        object=fact['object']
    )
```

## Cron Integration

- **Name**: `bower-mempalace-ingest`
- **Schedule**: `0 3 * * 1` (Monday 03:00 UTC, after Sunday Bower deep scan)
- **Skills**: `mcp-mempalace`
- **Process**: runs script → reads output → files drawer + KG facts

## Key Design Decisions

1. **Aggregate, don't file individually** — 49K files can't become 49K drawers. Summarize at domain/theme level.
2. **Content summaries are gold** — the 5,310 LLM summaries contain personal insights (health, travel, people). Raw file metadata alone is not useful for MemPalace.
3. **KG facts for queryability** — domains, places visited, medical providers as graph facts enable `mcp_mempalace_mempalace_kg_query("Jared")`.
4. **Script outputs JSON, cron files it** — MCP tools can't be called from `execute_code`. Two-phase design: extract (Python) → file (cron agent with MCP access).