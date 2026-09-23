#!/usr/bin/env python3
"""Extract full document CONTENT from Drive so Chronicle can embed what files SAY.

Until now Drive reached Chronicle as metadata only -- filename, kind, folder,
owner, dates. That answers "find the file called X" and cannot answer "which
document said we'd use quartz countertops". The recall looked better than it
was: "kitchen remodel plans" matched `Kitchen Section Details.pdf` because the
FOLDER PATH said "Design Docs/Drawings", not because anything read the drawing.

PRIORITY ORDER is Jared's: native Google formats first, then uploaded files.
That is also the right order on the merits --

  native (901 files)   `files.export` returns clean text. No download of a
                       binary, no OCR, no parsing library. Docs -> text/plain,
                       Sheets -> text/csv, Slides -> text/plain.
  uploaded (4,396 PDF) must be downloaded (10.6 GB in total) and parsed, and an
                       unknown share are scans with no text layer at all.
                       Bounded per run and resumable for exactly that reason.

CONTENT LIVES IN ITS OWN DATABASE, deliberately. `drive.db` is rebuilt from
scratch every night by drive_to_sqlite.py (tmp file + atomic rename), so a
content column there would be destroyed daily and re-extracted from 10.6 GB of
PDFs forever. `drive_content.db` survives; drive_to_sqlite.py joins it in.

  python bower_content_index.py [--native] [--uploaded] [--limit N] [--budget S]
"""
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".hermes" / "scripts"))
from google_auth_mcp import get_service  # noqa: E402

DRIVE_DB = "/root/.hermes/data/drive.db"
CONTENT_DB = "/root/.hermes/data/drive_content.db"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Native Google formats and the text type each exports cleanly to.
NATIVE = {
    "Google Doc": "text/plain",
    "Google Sheet": "text/csv",
    "Google Slides": "text/plain",
    "Drawing": None,       # vector image; no text to export
    "Form": None,          # structure, not prose
}
MAX_BYTES = 25 * 1024 * 1024     # skip absurd files rather than stall a run
MAX_CHARS = 40000                # store a generous head; embedding caps far lower


def ensure(db):
    db.execute("""CREATE TABLE IF NOT EXISTS document_content (
        file_id TEXT PRIMARY KEY,
        content TEXT,
        chars INTEGER,
        status TEXT,
        extracted_at TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_dc_status ON document_content(status)")
    db.commit()


def clean(t):
    if not t:
        return ""
    t = t.replace("﻿", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()[:MAX_CHARS]


def export_native(svc, file_id, mime_out):
    data = svc.files().export(fileId=file_id, mimeType=mime_out).execute()
    if isinstance(data, bytes):
        return data.decode("utf-8", "ignore")
    return str(data)


def download(svc, file_id):
    return svc.files().get_media(fileId=file_id).execute()


def pdf_to_text(blob):
    """pdftotext (poppler) rather than a Python PDF library.

    It is already installed, it is C and therefore cheap on a box with a
    history of CPU throttling, and `-layout` keeps tables readable. A pure
    Python parser would be slower and hold the whole document in memory.
    A PDF with no text layer returns almost nothing -- that is a scan, and it
    is recorded as `scanned` rather than retried forever.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(blob)
        path = fh.name
    try:
        r = subprocess.run(["pdftotext", "-layout", "-q", path, "-"],
                           capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", "ignore")
    finally:
        os.unlink(path)


def pending(dst, kinds, limit):
    """Files of these kinds that have no content row yet."""
    src = sqlite3.connect("file:%s?mode=ro" % DRIVE_DB, uri=True)
    src.row_factory = sqlite3.Row
    have = {r[0] for r in dst.execute("SELECT file_id FROM document_content")}
    qmarks = ",".join("?" * len(kinds))
    rows = src.execute(
        "SELECT file_id, name, kind FROM documents WHERE kind IN (%s)" % qmarks,
        list(kinds)).fetchall()
    src.close()
    out = [r for r in rows if r["file_id"] not in have]
    return out[:limit] if limit else out


def run(phase, kinds, limit, budget):
    svc = get_service("drive", "v3", SCOPES)
    dst = sqlite3.connect(CONTENT_DB, timeout=60)
    ensure(dst)
    todo = pending(dst, kinds, limit)
    print("== %s: %d files pending" % (phase, len(todo)))
    if not todo:
        return 0

    t0 = time.time()
    done = empty = failed = scanned = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for i, r in enumerate(todo, 1):
        if time.time() - t0 > budget:
            print("  [budget] stopping at %d/%d; the rest resumes next run" % (i, len(todo)))
            break
        fid, name, kind = r["file_id"], r["name"], r["kind"]
        status, text = "ok", ""
        try:
            if kind in NATIVE and NATIVE[kind]:
                text = export_native(svc, fid, NATIVE[kind])
            elif kind == "PDF":
                blob = download(svc, fid)
                if len(blob) > MAX_BYTES:
                    status = "toolarge"
                else:
                    text = pdf_to_text(blob)
                    # A PDF that yields almost nothing has no text layer.
                    if len(re.sub(r"\s", "", text or "")) < 40:
                        status, text = "scanned", ""
            else:
                status = "unsupported"
        except Exception as exc:                       # noqa: BLE001
            status = "failed:%s" % type(exc).__name__
        text = clean(text)
        if status == "ok" and not text:
            status = "empty"
        dst.execute("INSERT OR REPLACE INTO document_content"
                    "(file_id, content, chars, status, extracted_at) VALUES(?,?,?,?,?)",
                    (fid, text, len(text), status, now))
        if status == "ok":
            done += 1
        elif status == "scanned":
            scanned += 1
        elif status == "empty":
            empty += 1
        else:
            failed += 1
        if i % 50 == 0:
            dst.commit()
            print("  %d/%d  ok=%d scanned=%d empty=%d failed=%d  (%.0fs)"
                  % (i, len(todo), done, scanned, empty, failed, time.time() - t0), flush=True)
    dst.commit()

    tot = dst.execute("SELECT COUNT(*) FROM document_content").fetchone()[0]
    chars = dst.execute("SELECT COALESCE(SUM(chars),0) FROM document_content").fetchone()[0]
    print("  extracted %d (scanned %d, empty %d, failed %d) in %.0fs"
          % (done, scanned, empty, failed, time.time() - t0))
    print("  content rows: %d, %.1f MB of text" % (tot, chars / 1e6))
    dst.close()
    return 0


def main(argv):
    limit = None
    budget = float(os.environ.get("BOWER_CONTENT_BUDGET", "1800"))
    for i, a in enumerate(argv):
        if a == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1])
        if a == "--budget" and i + 1 < len(argv):
            budget = float(argv[i + 1])
    want_native = "--native" in argv or not ("--uploaded" in argv)
    want_uploaded = "--uploaded" in argv

    rc = 0
    if want_native:
        rc |= run("native (Docs/Sheets/Slides)",
                  [k for k, v in NATIVE.items() if v], limit, budget)
    if want_uploaded:
        rc |= run("uploaded (PDF)", ["PDF"], limit, budget)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
