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

### OAuth invalid_grant — Drive access permanently broken until re-auth

**Symptom:** Light scan (or any Drive API call) fails with `google.auth.exceptions.RefreshError: ('invalid_grant: Bad Request')` or `HTTP 401 UNAUTHENTICATED`. The `creds.valid` property may still return `True` even though the token is unusable — the library checks internal state, not the actual token expiry.

**Cause:** The OAuth refresh token has been revoked or expired at the Google side. This happens when:
- The user revokes app access in Google Account settings
- The refresh token expires (Google tokens can expire after 6+ months of inactivity)
- The OAuth client was deleted or regenerated in Google Cloud Console

**Diagnosis:**
```python
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json, urllib.request

# Load token file
d = json.loads(Path("/root/.google_workspace_mcp/credentials/google-workspace-user.json").read_text())
print(f"Token expiry: {d.get('expiry')}")  # If past, token is expired

# Test with direct REST API (bypasses library auto-refresh)
req = urllib.request.Request(
    "https://www.googleapis.com/drive/v3/about?fields=user",
    headers={"Authorization": f"Bearer {d['token']}"}
)
try:
    resp = urllib.request.urlopen(req, timeout=15)
    print("Token still valid")
except urllib.error.HTTPError as e:
    print(f"Token rejected: {e.code} {e.read().decode()[:200]}")
```

**Handling in Bower:**
1. Catch `RefreshError` and `HTTPError 401` at the scan entry point
2. Write `degraded: google_drive` to evidence.jsonl with the specific error
3. Write an aborted scan event to scan_events.jsonl
4. **Do NOT retry** — the refresh token will not recover without user interaction
5. Enter degraded mode: produce a partial Drive health report using last known state from `scan_progress.json` and `drive_digest.json`
6. The cron job will retry next cycle; if auth is restored by then, the scan will succeed automatically

**Recovery requires user interaction:** Re-run OAuth consent flow with `access_type=offline&prompt=consent` to obtain a fresh refresh token. This cannot be automated.

**Gotcha:** The `google_auth.py` helper's `get_service()` catches refresh failures and tries the next account, but if all accounts fail it raises `RuntimeError`. Bower's scan scripts should catch this at the top level and enter degraded mode rather than crashing with an unhandled exception.

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

### Transient drift — Drive self-corrects between cycles

**Scenario**: A light scan detects massive drift (e.g., root level goes from 6 items to 314+), triggering `drift_detected` and `needs_deep_scan`. A subsequent light scan finds the Drive has returned to its previous baseline (e.g., 6 root items again).

**What happened**: The drift was temporary — likely a sync/migration artifact where files were briefly visible at root level before being moved to their correct folders by an external process (Google Drive sync, migration tool, or bulk move operation).

**Handling**:
1. If the current scan count matches the pre-drift baseline (from `drive_digest.json` `previous_scan_file_count`), classify the drift as **transient** rather than structural.
2. Update `scan_progress.json` back to `phase: complete`, `status: stable` — set `total_files` and `total_folders` to the current counts.
3. Add a `scan_notes` entry documenting the transient drift event (peak count, resolution).
4. Reset `drive_digest.json` `scan_notes` to remove the stale drift warning.
5. **Do NOT trigger a deep scan** — the baseline was never actually broken; the scan window caught a mid-migration snapshot.
6. Write evidence explaining the transient drift; include both the spike count and the resolved count.
7. Skip `bower.analyze` — no proposals should be generated for a Drive that is back to its known-good state.

**Note**: This is different from the "Stale data after major Drive changes" gotcha in the main SKILL.md. That gotcha addresses a *permanent* structural change that invalidates old proposals. Transient drift resolves itself and the old baseline remains valid.

### Critical: No bower_analyze.py script may exist
If no `bower_analyze.py` exists, create it based on `references/organization_rules.md`, `references/domains.md`, and `references/analysis_schema.md`.
