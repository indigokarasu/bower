# Bower Scan Debug & Resume

## Critical File Layout Facts

### folder_index.json — Single JSON Object (Not JSONL)
```json
{"scan_timestamp":"...","total_folders":73900,"folders":[{"id":"...","name":"..."}]}
```
Load with `json.load(f)`, NOT line-by-line.

### scans/ — Authoritative Source of Truth
Each `.json` file = one scanned folder. Count files directly:
```bash
ls {agent_root}/commons/data/ocas-bower/scans/ | wc -l
```

### scan_progress.json — Unreliable for Resume
The `scanned_folders` array is often stale/empty even when `scans/` has files. Always use `scans/` as ground truth.

## Diagnosis Commands

```python
# Count actual scanned folders
import json
from pathlib import Path
scanned = len(list(Path("{agent_root}/commons/data/ocas-bower/scans").glob("*.json")))

# Total folders
with open("{agent_root}/commons/data/ocas-bower/folder_index.json") as f:
    d = json.load(f)
total = d.get("total_folders")
remaining = total - scanned
```

## Resume Pattern

```python
from pathlib import Path
import json

scans_dir = Path("{agent_root}/commons/data/ocas-bower/scans")
folder_index = json.load(open("{agent_root}/commons/data/ocas-bower/folder_index.json"))

# Build scanned set from scans/ directory
scanned_ids = {f.stem for f in scans_dir.glob("*.json")}

# Find unscanned folders
unscanned = [fd for fd in folder_index["folders"] if fd["id"] not in scanned_ids]
```

## Two-Phase Deep Scan

**Phase 1**: Tree discovery → `folder_index.json`
**Phase 2**: Scan each folder → `scans/{folder_id}.json`
**Content enrichment**: `bower_read_contents.py` → `content_summaries.jsonl`

All three produce distinct outputs. Proposal generation requires Phase 2 + content.

## Scripts Location

- `bower_resume_scan.py` — resumable folder scanner
- `bower_read_contents.py` — content enrichment
- `bower_full_scan.py` — full scan with content reading

Run in background:
```bash
cd {agent_root}/commons/data/ocas-bower
nohup python3 bower_resume_scan.py > /tmp/bower_resume.log 2>&1 &
echo "PID: $!"
```

## Light Scan Lessons

### Drive is overwhelmingly automated
A typical light scan finds 2,000–4,000 recently modified items. Most are:
- **System agent files**: `session_*.json`, `decisions.jsonl`, `config.json`, `messages.jsonl`
- **Agent skill artifacts**: `SKILL.md`, `.pyc` bytecode, `outbound_ckpt.txt`, drafts
- **Automated backups**: Files inside timestamped folders like `2026-04-20_06-00-01/`

Only ~1-2% are actual user content. Filter aggressively:
```python
hermes_re = re.compile(r"^20\d{2}-\d{2}-\d{2}_\d{2}-\d{2}")
code_markers = {"node_modules", "dist", ".git", "build", "__pycache__", "vendor",
                "coverage", "compiled", "objects", "refs", "checkpoints"}
system_patterns = ["session_", "decisions.jsonl", "config.json", "messages.jsonl",
                   "issues.jsonl", "fixes.jsonl", "ingest_", "state.db", "agent.log",
                   "gateway.pid", ".lbug", "FETCH_HEAD", "SKILL.md", "draft-"]
```

### folder_index.json is incomplete for parent lookups
The `folder_index.json` only contains ~72K folders from the original deep scan. Many parent IDs from Shared Drives or newer folders are NOT in the index. Use the Drive API to look up parent folder names directly.

### Proposals JSONL field names
The `proposals.jsonl` uses `proposal_type` and `confidence_tier` (NOT `type` and `confidence`).

### Critical: No bower_analyze.py script may exist
If no `bower_analyze.py` exists, create it based on `references/organization_rules.md`, `references/domains.md`, and `references/analysis_schema.md`.
