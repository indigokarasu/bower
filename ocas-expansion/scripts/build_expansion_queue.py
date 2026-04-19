#!/usr/bin/env python3
"""Build expansion_queue.json from the Weave LadybugDB.

Selects up to 10 Person nodes that:
  - have source_ref containing 'google-contacts' (unenriched), and
  - have not been scout-enriched in the last 180 days (per notes field).

The `source_ref` rewrite on successful Weave upsert is the primary
deduplication mechanism. The 180-day notes check is a safety valve
for contacts whose source_ref was already rewritten but that we want
to protect against accidental re-enrichment anyway.

Usage:
    python scripts/build_expansion_queue.py

Paths are read from environment when present, else default to the
canonical OCAS agent-root layout.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone

import real_ladybug as lb

DB = os.environ.get(
    "OCAS_WEAVE_DB",
    "/root/.hermes/commons/db/ocas-weave/weave.lbug",
)
QUEUE = os.environ.get(
    "OCAS_EXPANSION_QUEUE",
    "/root/.hermes/commons/data/ocas-expansion/expansion_queue.json",
)
CUTOFF = datetime.now(timezone.utc) - timedelta(days=180)
LIMIT = 10

ENRICHED_PATTERNS = (
    r"\[scout_enriched:\s*(\d{4}-\d{2}-\d{2})\]",
    r"last_scout_enrichment:\s*(\d{4}-\d{2}-\d{2})",
)


def was_enriched_recently(notes: str | None, cutoff: datetime) -> bool:
    if not notes:
        return False
    for pattern in ENRICHED_PATTERNS:
        m = re.search(pattern, str(notes))
        if m:
            d = datetime.strptime(m.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if d > cutoff:
                return True
    return False


def build_queue() -> list[dict]:
    db = lb.Database(DB, read_only=True)
    conn = lb.Connection(db)
    try:
        rows = list(conn.execute(
            """
            MATCH (n:Person)
            WHERE n.source_ref CONTAINS 'google-contacts'
              AND n.name IS NOT NULL
              AND n.name <> 'Test Person 2'
            RETURN n.id, n.name, n.email, n.source_ref, n.notes
            ORDER BY n.record_time DESC
            LIMIT 50
            """
        ))
    finally:
        conn.close()
        db.close()

    seen: set[str] = set()
    queue: list[dict] = []
    for pid, name, email, _src_ref, notes in rows:
        key = name.lower()
        if key in seen:
            continue
        if was_enriched_recently(notes, CUTOFF):
            continue
        seen.add(key)
        queue.append({"id": pid, "name": name, "email": email})
    return queue[:LIMIT]


def main() -> None:
    queue = build_queue()
    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    with open(QUEUE, "w") as f:
        json.dump(queue, f, indent=2)
    print(f"wrote {len(queue)} targets to {QUEUE}")


if __name__ == "__main__":
    main()
