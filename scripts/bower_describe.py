"""Write LLM-generated abstracts into the Description field of Drive files.

Bower indexes documents so they can be FOUND. This puts a one-sentence
characterisation of each document into Drive's own Description field, which
makes Drive's native search useful and gives a human scanning a folder some
idea what a file is without opening it.

Safety rules, in order of importance:

  1. NEVER overwrite a description that already exists. Jared's own words are
     not ours to replace. The current value is fetched from Drive per file --
     drive.db does not carry it -- and a non-empty one is a hard skip.
  2. Every write is recorded to an undo ledger BEFORE the API call, fsynced.
     If the write then fails, the ledger says old=X new=Y for a file still
     holding X; undoing that is a no-op. Losing an undo record is the failure
     we cannot tolerate; a redundant one costs nothing.
  3. Files with no extracted content get NO description. A wrong description
     is worse than an absent one because it will be trusted.
  4. No key resolved, or a model that returns nothing -> skip the file. Never
     invent an abstract, never write a placeholder.

Model/key/base_url are resolved from the profile config at call time. Nothing
here is pinned to a provider.

Usage:
  bower_describe.py --limit 10 --dry-run    # show what would be written
  bower_describe.py --limit 10              # write 10, for review
  bower_describe.py                         # write all candidates
  bower_describe.py --undo                  # revert every write in the ledger
"""
import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request

import yaml

sys.path.insert(0, "/root")
sys.path.insert(0, "/root/.hermes/profiles/indigo/scripts")

from google_auth_mcp import get_service  # noqa: E402

CFG = "/root/.hermes/profiles/indigo/config.yaml"
DRIVE_DB = "/root/.hermes/data/drive.db"
LEDGER = "/root/.hermes/data/bower_description_ledger.jsonl"
SCOPES = ["https://www.googleapis.com/auth/drive"]

MIN_CONTENT = 200      # below this there is nothing to characterise
MAX_DESC = 480         # Drive accepts more; a listing does not want more
PACE_S = 0.35          # gentle on the Drive API and on a throttled box

PROMPT = (
    "Write a one-sentence description of this document for the Description "
    "field in a file listing. Say what the document IS and what it covers as "
    "a whole -- not just how it opens. No preamble, no quotes, one sentence.\n\n"
    "Filename: {name}\nType: {kind}\n\nContent:\n{content}"
)


def creds():
    cfg = yaml.safe_load(open(CFG))
    m = cfg.get("model") or {}
    key = os.environ.get("OPENROUTER_API_KEY") or m.get("api_key")
    if not key:
        for p in ("/root/.hermes/profiles/indigo/.env", "/root/.hermes/.env"):
            if not os.path.exists(p):
                continue
            for ln in open(p):
                if ln.startswith("OPENROUTER_API_KEY="):
                    key = ln.split("=", 1)[1].strip().strip('"').strip("'")
                    break
            if key:
                break
    base = (m.get("base_url") or "https://openrouter.ai/api/v1").rstrip("/")
    return key, m.get("default"), base


def abstract(key, model, base, name, kind, content):
    """One sentence, or None. Never a guess, never a placeholder."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT.format(
            name=name, kind=kind or "document", content=content[:4000])}],
        # Reasoning models bill their trace against max_tokens. Measured need
        # was ~258 completion tokens; 4000 leaves room for a long trace so a
        # truncated trace never masquerades as an API failure.
        "max_tokens": 4000,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(
        base + "/chat/completions", data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            d = json.load(r)
    except Exception as e:
        print(f"    LLM error: {e}")
        return None
    txt = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    txt = " ".join(txt.split()).strip().strip('"')
    if len(txt) < 15:
        return None
    return txt[:MAX_DESC]


def log(entry):
    """Append to the undo ledger and force it to disk before we act on it."""
    with open(LEDGER, "a") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()
        os.fsync(f.fileno())


def undo(svc):
    if not os.path.exists(LEDGER):
        print("no ledger; nothing to undo")
        return 0
    entries = [json.loads(l) for l in open(LEDGER) if l.strip()]
    writes = [e for e in entries if e.get("action") == "write"]
    print(f"reverting {len(writes)} writes")
    for e in reversed(writes):
        try:
            svc.files().update(
                fileId=e["file_id"], body={"description": e.get("old") or ""},
                supportsAllDrives=True).execute()
            print(f"  reverted {e['name'][:50]}")
        except Exception as ex:
            print(f"  FAILED {e['name'][:50]}: {ex}")
        time.sleep(PACE_S)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--undo", action="store_true")
    a = ap.parse_args()

    svc = get_service("drive", "v3", SCOPES)
    if a.undo:
        return undo(svc)

    key, model, base = creds()
    if not key or not model:
        print("no API key or model resolved -- refusing to guess", file=sys.stderr)
        return 1
    print(f"model={model}  dry_run={a.dry_run}\n")

    db = sqlite3.connect(DRIVE_DB)
    rows = db.execute(
        "select file_id, name, kind, content from documents "
        "where content is not null and length(content) >= ? "
        "order by length(content) desc", (MIN_CONTENT,)).fetchall()
    if a.limit:
        rows = rows[:a.limit]
    print(f"{len(rows)} candidates\n")

    wrote = skipped_existing = skipped_nollm = skipped_readonly = failed = 0
    for i, (fid, name, kind, content) in enumerate(rows, 1):
        # Fetch the live description. drive.db does not carry it, and we must
        # not overwrite one that is already there.
        try:
            cur = svc.files().get(
                fileId=fid, fields="id,name,description,capabilities/canEdit",
                supportsAllDrives=True).execute()
        except Exception as e:
            print(f"{i:4d}. {name[:44]:46s} FETCH FAILED: {e}")
            failed += 1
            continue

        existing = (cur.get("description") or "").strip()
        if existing:
            skipped_existing += 1
            print(f"{i:4d}. {name[:44]:46s} SKIP (has description)")
            continue

        if not cur.get("capabilities", {}).get("canEdit"):
            # Shared with Jared but owned by someone else. update() returns
            # 403 insufficientFilePermissions. Checked here so we never spend
            # an LLM call on a file whose description we cannot set.
            skipped_readonly += 1
            print(f"{i:4d}. {name[:44]:46s} SKIP (read-only, not owner)")
            continue

        text = abstract(key, model, base, name, kind, content)
        if not text:
            skipped_nollm += 1
            print(f"{i:4d}. {name[:44]:46s} SKIP (no abstract)")
            continue

        if a.dry_run:
            print(f"{i:4d}. {name[:44]:46s}\n        WOULD WRITE: {text}")
            wrote += 1
            continue

        log({"action": "write", "file_id": fid, "name": name,
             "old": existing, "new": text, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                               time.gmtime())})
        try:
            svc.files().update(fileId=fid, body={"description": text},
                               supportsAllDrives=True).execute()
            wrote += 1
            print(f"{i:4d}. {name[:44]:46s}\n        WROTE: {text}")
        except Exception as e:
            failed += 1
            print(f"{i:4d}. {name[:44]:46s} WRITE FAILED: {e}")
        time.sleep(PACE_S)

    verb = "would write" if a.dry_run else "wrote"
    print(f"\n--- {verb}={wrote}  skip_existing={skipped_existing}  "
          f"skip_readonly={skipped_readonly}  skip_no_abstract={skipped_nollm}  "
          f"failed={failed} ---")
    if not a.dry_run and wrote:
        print(f"undo ledger: {LEDGER}")
        print("revert with: bower_describe.py --undo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
