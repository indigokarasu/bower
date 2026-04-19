# ocas-expansion

Graph Expansion Pipeline for the OCAS ecosystem: batch enrichment of Person nodes in the Weave social graph via a three-phase **Scout → Sift → Weave** pipeline.

**Status:** initial release. Canonical home for the expansion pipeline (previously proposed as a sub-skill of `ocas-bower`; see closed bower PR #2).

**Visibility:** private.

## What this skill does

For each target on the expansion queue, ocas-expansion runs:

1. **Scout** — structural OSINT via the `ddgs` library (employer, LinkedIn, publications).
2. **Sift** — intellectual deep research (conference talks, domain expertise, writing).
3. **Weave** — synthesis and upsert into the Weave LadybugDB graph, including `Knows` relationships where co-authorship or org evidence exists.

Deduplication is the whole point: enrichment rewrites `source_ref` from `google-contacts-*` to `expansion_YYYYMMDD_scout`, so the same contact never re-enters the queue unless an operator explicitly asks. A 180-day `notes`-based cutoff is the safety valve.

## Install

Clone into the OCAS workspace skill directory:

```
~/.openclaw/skills/ocas-expansion/
```

No install-time side effects. On first `expansion.build-queue` run, ocas-expansion creates `{agent_root}/commons/data/ocas-expansion/` if absent.

## Directory layout

See `SKILL.md` for the full storage layout. Short version:

```
{agent_root}/commons/data/ocas-expansion/     # pipeline outputs
  expansion_queue.json                        # current batch (overwritten per run)
  scout_findings_YYYYMMDD.json                # Phase 1 output
  sift_findings_YYYYMMDD.json                 # Phase 2 output
  final_weave_synthesis.json                  # Phase 3 output
  last_run_report.txt                         # human-readable report
  pipeline_completion_*.json                  # machine-readable completion record

{agent_root}/commons/journals/ocas-expansion/ # daily journal files
  YYYY-MM-DD/{run_id}.json

~/.openclaw/skills/ocas-expansion/            # this skill package
  SKILL.md
  README.md
  CHANGELOG.md
  scripts/
    build_expansion_queue.py
```

## Commands

| Command | Purpose |
|---|---|
| `expansion.build-queue` | Query Weave DB for unenriched Person nodes, write `expansion_queue.json` (10 targets). Must run before every pipeline execution. |
| `expansion.run` | Execute the full Scout → Sift → Weave pipeline against the current queue. Scheduled daily at 10:00 UTC via hermes cron. |

## Consumer / producer relationship

ocas-expansion is the **producer**. Other skills consume its outputs:

- **ocas-bower** reads expansion outputs (Scout/Sift findings, final Weave synthesis) as upstream signal for drive/document organization and analysis.
- **ocas-weave** is the underlying graph the pipeline upserts into; ocas-expansion is a write-heavy client of Weave.
- Downstream analytical skills can point at `commons/journals/ocas-expansion/` for provenance-backed enrichment events.

## Development

This is a private skill. Do not publish publicly — the LadybugDB query shapes and enrichment heuristics are operational.

Run the queue builder locally:

```bash
python scripts/build_expansion_queue.py
```

Override defaults with `OCAS_WEAVE_DB` and `OCAS_EXPANSION_QUEUE` environment variables.

## Versioning

OCAS policy — patch = bugfix/text, minor = new commands, major = new features. See `CHANGELOG.md` for the per-release history.

## License

Private / unlicensed.
