---
name: ocas-expansion
version: "1.0.0"
type: workflow
description: >
  Graph Expansion Pipeline: orchestrates Scout → Sift → Weave for batch processing
  of people from the expansion queue. Reads targets from expansion_queue.json,
  runs structural OSINT (Scout), intellectual deep research (Sift), and social graph
  synthesis/upsert (Weave). Use for scheduled enrichment of the social graph with
  provenance-backed person profiles and relationships.
author: Indigo Karasu
email: mx.indigo.karasu@gmail.com
metadata:
  hermes:
    tags: [expansion, pipeline, social-graph, research]
    category: signal
    cron:
      - name: "expansion:run"
        schedule: "0 10 * * *"
        command: "expansion.run"
---

# Expansion Pipeline

Orchestrates the three-phase enrichment pipeline: Scout (Structural OSINT) → Sift (Intellectual Deep Research) → Weave (Synthesis & Graph Upsert). Processes targets from `expansion_queue.json`, enriching each person's profile with provenance-backed findings and updating the Weave social graph.

## When to use

- Scheduled cron enrichment of the social graph
- Batch processing of new contacts/leads from the expansion queue
- Re-enrichment of existing person nodes with fresh OSINT data

## Commands

### expansion.build-queue

Builds `expansion_queue.json` from the Weave DB — **must run before every pipeline execution**. Queries LadybugDB directly to find unenriched contacts, excluding anyone processed in the last 180 days.

**Deduplication is automatic and mandatory.** The system tracks enrichment via `source_ref`:
- Contacts with `source_ref` containing `google-contacts` are **unenriched** (eligible for queue)
- After enrichment, `source_ref` changes to `expansion_YYYYMMDD_scout` — automatically excluding them from future queries
- A 180-day safety cutoff is also enforced via the `notes` field (parses `[scout_enriched: YYYY-MM-DD]`)

Run `python scripts/build_expansion_queue.py` to rebuild the queue. The script opens the Weave LadybugDB read-only, filters by `source_ref` and the notes-based 180-day cutoff, dedupes by lowercased name, and writes the top 10 targets to `expansion_queue.json`. Override paths with `OCAS_WEAVE_DB` and `OCAS_EXPANSION_QUEUE` env vars.

For ad hoc inspection without the script, use the `lbug` CLI:
```bash
lbug "MATCH (n:Person) WHERE n.source_ref CONTAINS 'google-contacts' RETURN n.id, n.name, n.email ORDER BY n.record_time DESC LIMIT 10" /root/.hermes/commons/db/ocas-weave/weave.lbug
```

### expansion.run

Executes the full pipeline. **Always call `expansion.build-queue` first.**

Pipeline steps:
1. Build queue (`expansion.build-queue`)
2. Phase 1 Scout — OSINT via `ddgs`
3. Phase 2 Sift — deep research via `ddgs`
4. Phase 3 Weave — upsert + timestamp recording

## Deduplication Rule

**NEVER re-enrich a contact within 180 days unless the user explicitly requests it.**

Re-enrichment is allowed only when:
1. User explicitly names the contact (e.g., "re-enrich Jian He")
2. 180+ days have passed since last enrichment

The `source_ref` field is the primary dedup mechanism:
- `google-contacts-sync` / `google-contacts-restore` → unenriched
- `expansion_YYYYMMDD_scout` → enriched on that date

The `notes` field is the safety valve — contains `| [scout_enriched: YYYY-MM-DD]` after each enrichment.

## Input

Reads targets from `{agent_root}/commons/data/ocas-expansion/expansion_queue.json`. After `expansion.build-queue` runs, this file contains 10 unenriched contacts with `{"id", "name", "email"}`.

## Pipeline phases

### Phase 1: Scout (Structural OSINT)

Uses `ocas-scout` methodology. For each target:

1. **Search via `ddgs` library** — Use the `ddgs` Python package directly in `execute_code` or `terminal`. Do NOT use `delegate_task` with browser tools — browser subagents get blocked by CAPTCHAs. Run all 10 targets in a single Python script for efficiency.
2. **Search queries per person:**
   - `\"{name} {employer}\"`
   - `\"{name}\" LinkedIn`
   - `\"{name}\" publications research`
3. **Sanitize all text** — `re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', text)` before storing JSON or Cypher queries
4. **Write results to file** — `scout_findings_YYYYMMDD.json` via `json.dump()` in script

### Phase 2: Sift (Intellectual Deep Research)

1. **Search via `ddgs`** — all 10 targets in one script
2. **Deeper queries:**
   - `\"{name}\" publications`
   - `\"{name}\" conference talk`
   - `\"{name}\" site:linkedin.com`
3. **Extract domain_expertise** from result snippets
4. **Write to file** — `sift_findings_YYYYMMDD.json`

### Phase 3: Weave (Synthesis)

1. **MERGE upsert** each Person node with enriched fields
2. **Record enrichment timestamp** — append `| [scout_enriched: YYYY-MM-DD]` to `notes` field. LadybugDB cannot add new properties via SET, so encoding in `notes` is required.
3. **Change `source_ref`** from `google-contacts-*` to `expansion_YYYYMMDD_scout` — this is the primary deduplication mechanism
4. **Read-back verify** every upsert
5. **Create Knows relationships** where evidence exists (co-author, same-org colleague, former colleague)

## LadybugDB Integration Patterns

**Use `lbug` CLI or `real_ladybug` Python API.** `lbug` CLI for one-off queries, Python API for scripts.

### Key Patterns

```python
# Open database
import real_ladybug as lb
db = lb.Database('/root/.hermes/commons/db/ocas-weave/weave.lbug', read_only=False)
conn = lb.Connection(db)

# Upsert with enrichment tracking
set_clauses = [
    'p.source_ref = "expansion_20260417_scout"',
    'p.confidence = 0.7',
    'p.record_time = "' + datetime.now(timezone.utc).isoformat() + '"',
]
notes_enriched = existing_notes + '| [scout_enriched: 2026-04-17]' if existing_notes else '[scout_enriched: 2026-04-17]'
set_clauses.append('p.notes = "' + notes_enriched + '"')

query = 'MATCH (p:Person {id: "' + pid + '"}) SET ' + ', '.join(set_clauses)
conn.execute(query)
```

### Critical Pitfalls

1. **UUID hyphens in relationships** — LadybugDB parses hyphens as subtraction. Use **name-based matching** for relationship creation, not two UUIDs in one query:
   ```python
   # BAD
   q = "MATCH (a {id: 'uuid1'}), (b {id: 'uuid2'}) CREATE (a)-[k]->(b)"
   # GOOD
   q = "MATCH (a:Person {name: '" + name1 + "'}), (b:Person {name: '" + name2 + "'}) CREATE (a)-[k]->(b)"
   ```

2. **No SET on non-existent properties** — LadybugDB cannot add new properties via SET. Encode new data in existing string properties (e.g., append to `notes`).

3. **`read_only` on Database, not Connection** — `lb.Database(path, read_only=True)`, not `conn.execute(query, read_only=True)`.

4. **Dense colleague graphs** — O(n²) edge creation. Limit to the current batch only.

## Storage Layout

```
{agent_root}/commons/data/ocas-expansion/
  expansion_queue.json          — current target list (overwritten each build-queue)
  last_run_report.txt           — human-readable pipeline report
  pipeline_completion_*.json    — machine-readable completion records
  scout_findings_YYYYMMDD.json  — Phase 1 output
  sift_findings_YYYYMMDD.json   — Phase 2 output
  final_weave_synthesis.json    — Phase 3 output

{agent_root}/commons/journals/ocas-expansion/
  YYYY-MM-DD/
    {run_id}.json
```

## Output

1. `last_run_report.txt` — Executive Summary, per-phase tables, graph stats
2. `pipeline_completion_*.json` — machine-readable completion record
3. Scout/Sift/Weave data files
4. Journal entry with `entities_observed` array

## Run Completion Checklist

- [ ] Queue built via `expansion.build-queue`
- [ ] All targets processed through Scout
- [ ] All targets processed through Sift
- [ ] All Person nodes upserted with read-back verification
- [ ] `source_ref` updated to `expansion_YYYYMMDD_scout` for each target
- [ ] `[scout_enriched: YYYY-MM-DD]` appended to notes for each target
- [ ] Knows relationships created (current batch only)
- [ ] Graph stats recorded
- [ ] `last_run_report.txt` written
- [ ] `pipeline_completion_*.json` written
- [ ] Journal written

## OKRs

```yaml
skill_okrs:
  - name: pipeline_completion_rate
    metric: fraction of targets completing all 3 phases
    direction: maximize
    target: 0.90
    evaluation_window: 10_runs
  - name: scout_confidence_ratio
    metric: fraction of targets with high Scout confidence
    direction: maximize
    target: 0.80
    evaluation_window: 10_runs
  - name: weave_readback_success
    metric: fraction of upserts confirmed by read-back
    direction: maximize
    target: 1.0
    evaluation_window: 10_runs
  - name: relationship_evidence_ratio
    metric: fraction of Knows edges with co-authorship or org-confirmed evidence
    direction: maximize
    target: 0.70
    evaluation_window: 10_runs
```
