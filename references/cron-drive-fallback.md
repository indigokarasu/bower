# Cron / isolated-context Drive fallback (local SDK)

The MCP `google_workspace` Drive tools (`mcp__google_workspace__list_drive_items`,
`mcp__google_workspace__search_drive_files`) are the documented Bower interface
(see `mcp-drive-tooling.md`). **But in isolated/cron Hermes sessions they are NOT
registered** — the tool registry contains only the standard Hermes tool set. Calling
them returns: `Tool '<name>' does not exist. Available tools: browser_back, ...`.

## When to use this fallback
- A scheduled `bower:scan` / `bower:weekly-deep` cron run.
- Any session where `tool_search` / `tool_describe` for `mcp__google_workspace__*`
  returns "not found" or the call returns "does not exist".

## The local SDK path
- Credential helper: `~/.hermes/profiles/indigo/scripts/google_auth.py`
  exposes `get_service(api_name, api_version, scopes, account=...)`.
- Cached token (carries the `drive` scope): `google_token.json` ->
  `/root/indigo-repo/credentials/indigo_google_credentials.json`.
- Build the service:
  ```python
  from google_auth import get_service
  svc = get_service("drive", "v3",
                    ["https://www.googleapis.com/auth/drive"],
                    account="google-workspace-user")
  # raises on dead refresh token (HTTP 400 invalid_grant)
  svc.about().get(fields="user").execute()  # smoke test
  ```
- Run the scan script via `terminal` (cron blocks `execute_code`):
  `python3 scripts/bower_drive_sdk_light_scan.py [--cutoff ...] [--dry-run]`
  It writes the same artifacts as the MCP path (`light_scan_latest.json`,
  `scan_events.jsonl`, `evidence.jsonl`) and honors every invariant
  (structural baseline check, owned-vs-shared split, no deletes).

## API call mapping (same semantics as the MCP table)
| Bower step | SDK call |
|------------|----------|
| Root baseline (pageSize=10) | `svc.files().list(q="'root' in parents and trashed=false", pageSize=10, includeItemsFromAllDrives=False, supportsAllDrives=False, fields="nextPageToken, files(id,name,mimeType)")` |
| modifiedTime arrival | `svc.files().list(q=f"modifiedTime > '{CUTOFF}' and trashed=false", corpora="user", includeItemsFromAllDrives=False, orderBy="modifiedTime desc", pageSize=200, fields="nextPageToken, files(...)")` |

## Auth failure -> degraded mode
A revoked/expired refresh token raises `HTTP 400 invalid_grant: Bad Request`
(even when `Credentials.valid` is `True`). This is **permanent** — no retry
recovers it. Handle at the scan entry point:
1. Catch the exception.
2. Write `degraded: google_drive` to `evidence.jsonl` (`not_activity_reason` mandatory).
3. Write an aborted `light_scan` event to `scan_events.jsonl`.
4. Report degraded; do NOT generate proposals; never delete.
5. Tell owner to re-authenticate via OAuth consent
   (`access_type=offline&prompt=consent`) for `google-workspace-user`.

First observed 2026-06-29; recurred 2026-07-14 (16 days of silent light-scan
failures). `scripts/bower_drive_sdk_light_scan.py` implements this contract.
