# Changelog

All notable changes to ocas-expansion are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: OCAS policy — patch = bugfix/text, minor = new commands, major = new features.

## [1.0.0] - 2026-04-18

### Added
- Initial release as a standalone skill (previously proposed as a sub-skill of `ocas-bower`; see closed bower PR #2).
- SKILL.md defining the three-phase **Scout → Sift → Weave** enrichment pipeline with per-phase search strategies, LadybugDB upsert patterns, and a run-completion checklist.
- `expansion.build-queue` command — queries Weave LadybugDB for unenriched Person nodes and writes the top 10 targets to `expansion_queue.json`.
- `expansion.run` command — executes the full Scout → Sift → Weave pipeline against the current queue. Scheduled daily at 10:00 UTC via hermes cron.
- `scripts/build_expansion_queue.py` — extracted queue-builder script with overridable paths via `OCAS_WEAVE_DB` and `OCAS_EXPANSION_QUEUE` environment variables.
- Storage layout under `{agent_root}/commons/data/ocas-expansion/` and journals under `{agent_root}/commons/journals/ocas-expansion/`.
- Skill OKRs for pipeline completion rate, Scout confidence, Weave read-back success, and relationship evidence ratio.

### Architecture decisions
- **Primary deduplication via `source_ref` rewrite**: enrichment changes `google-contacts-*` → `expansion_YYYYMMDD_scout`, so enriched contacts are excluded from subsequent queue builds by construction.
- **Secondary 180-day safety cutoff** parsed from the `notes` field (`[scout_enriched: YYYY-MM-DD]`). Protects against accidental re-enrichment even if `source_ref` was already rewritten.
- **LadybugDB-specific constraints documented**: UUID-hyphen parsing requires name-based matching for relationship creation; SET cannot add new properties (enrichment timestamps encoded in `notes`); `read_only` lives on `Database`, not `Connection`.
- **`ddgs` for search, not browser subagents** — browser tooling is CAPTCHA-blocked for the query shapes this skill needs.
