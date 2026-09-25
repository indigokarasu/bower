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

OCR IS A SEPARATE, LATER PASS over rows the text pass already marked
`scanned` (no text layer). It is not folded into the text pass because it is
an order of magnitude slower per page (render + recognize vs. a library call)
and only worth paying once pdftotext has already proven there is nothing to
read. A vision LLM was considered and rejected for this: these are typed
documents run through a scanner, not photos, and a local OCR engine (already
installed, no network call, no per-page cost) reads them fine.

  python bower_content_index.py [--native] [--uploaded] [--ocr] [--limit N]
                                 [--budget S] [--dry-run] [--self-test]
"""
import glob
import os
import re
import shutil
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
OCR_MAX_PAGES = 15               # tesseract cost is linear in pages; this bounds
                                  # worst-case run time on multi-hundred-page scans
STEAL_PROBE_INTERVAL = 60.0      # seconds between hypervisor-throttle checks;
                                  # vmstat itself samples for ~9s, so probing every
                                  # document would waste as much time as the OCR


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
    t = t.replace("", "")
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


def _page_num(png_path):
    """Sort key for pdftoppm's `<prefix>-<n>.png` output.

    poppler pads `<n>` to the width of the largest page number in the
    requested range, so a plain string sort would put page 10 before page 2.
    """
    m = re.search(r"-(\d+)\.png$", png_path)
    return int(m.group(1)) if m else 0


def render_pages(pdf_path, prefix, max_pages):
    """pdftoppm one PNG per page, capped at `max_pages`.

    `-png` is not optional: without it pdftoppm writes `<prefix>-<n>.ppm`, the
    glob below matches nothing, and every scanned document is filed as
    `ocr_empty` having never been read (the first live run did exactly that).
    `-gray` shrinks tesseract's input (color is wasted on a scanned page) and
    `-r 200` is a DPI floor tesseract reads reliably without the memory blowup
    of rendering at print resolution. A render failure (corrupt PDF, timeout)
    raises here and is caught by the caller as a document-level failure --
    there is nothing to OCR yet, unlike a single bad page after a good render.
    """
    subprocess.run(["pdftoppm", "-png", "-r", "200", "-gray", "-f", "1", "-l", str(max_pages),
                    pdf_path, prefix], capture_output=True, timeout=300, check=True)
    return sorted(glob.glob(prefix + "-*.png"), key=_page_num)


def ocr_page(png_path, timeout=120):
    """Run tesseract on one already-rendered page.

    Caught here, not by the caller: a single corrupt or unreadable page must
    mark only that page, not fail a document most of whose pages are fine.
    """
    try:
        r = subprocess.run(["tesseract", png_path, "-", "-l", "eng", "--psm", "3"],
                           capture_output=True, timeout=timeout)
        if r.returncode != 0:
            return ""
        return r.stdout.decode("utf-8", "ignore")
    except Exception:                                    # noqa: BLE001
        return ""


def pdf_to_text_ocr(svc, file_id, max_pages):
    """OCR a PDF pdftotext already proved has no text layer.

    Re-downloads the file: the text pass discards the blob once it has its
    verdict (`scanned`), so nothing is cached to render from. `download()` is
    the same Drive call the uploaded-PDF path already makes; the OCR itself
    (pdftoppm + tesseract) is local, no network.
    """
    blob = download(svc, file_id)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(blob)
        pdf_path = fh.name
    tmpdir = tempfile.mkdtemp(prefix="bower_ocr_")
    try:
        pages = render_pages(pdf_path, os.path.join(tmpdir, "page"), max_pages)
        texts = [ocr_page(p) for p in pages]
        return "\n\n".join(t for t in texts if t)
    finally:
        os.unlink(pdf_path)
        shutil.rmtree(tmpdir, ignore_errors=True)


def steal_now():
    """Mean of three vmstat samples, discarding vmstat's own first line (a
    boot-time average, not a live one) -- same sampling as
    ops/embed_backlog.sh's steal_now(), because a single live sample is noisy
    (an hourly backup spike reads the same as a sustained hypervisor cap).
    Returns None, not 0, when vmstat is unavailable or unparseable, so a probe
    failure skips pacing instead of being mistaken for a calm box.
    """
    try:
        r = subprocess.run(["vmstat", "3", "4"], capture_output=True, timeout=15)
        lines = [ln for ln in r.stdout.decode("utf-8", "ignore").splitlines() if ln.strip()]
        samples = lines[-3:]
        vals = [float(ln.split()[-2]) for ln in samples]
        return sum(vals) / len(vals) if vals else None
    except Exception:                                    # noqa: BLE001
        return None


def steal_pace(steal):
    """Seconds to sleep between OCR documents at a given steal%.

    Same tiers and pace values as ops/embed_backlog.sh's WORKERS/PACE_MS
    ladder (this loop is single-document, so only the pace half applies).
    High steal means slower, never stopped: a hard stop-gate blocked an
    earlier backlog permanently because this box idles at 35-90% steal from
    host-side pressure even when its own CPU use is near zero.
    """
    if steal is None:
        return 0.0
    if steal >= 75:
        return 30.0   # crawl
    if steal >= 50:
        return 12.0   # slow
    if steal >= 25:
        return 4.0    # gentle
    if steal >= 10:
        return 1.0    # normal
    return 0.25        # turbo


def pending(dst, kinds, limit):
    """Files of these kinds that have no content row yet.

    `have` is every file_id already in document_content REGARDLESS of status
    (ok/empty/scanned/failed/toolarge/unsupported) -- a file that was already
    tried, however it came out, is not tried again by this pass. That is what
    makes --uploaded resumable across a budget cutoff.
    """
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


def ocr_pending(dst, limit):
    """Rows the text pass marked `scanned` -- no text layer, never OCR'd.

    Re-running --ocr after a budget cutoff resumes for free: a row's status
    flips to `ocr`/`ocr_empty`/`failed:...` as soon as it is processed, so it
    no longer matches this query. Returns plain file_id strings, not Row
    objects: unlike `pending()`'s DRIVE_DB read, CONTENT_DB connections in
    this file never set row_factory.
    """
    rows = [r[0] for r in dst.execute(
        "SELECT file_id FROM document_content WHERE status='scanned' ORDER BY file_id")]
    return rows[:limit] if limit else rows


def run(phase, kinds, limit, budget, dry_run=False):
    dst = sqlite3.connect(CONTENT_DB, timeout=60)
    ensure(dst)
    todo = pending(dst, kinds, limit)
    print("== %s: %d files pending" % (phase, len(todo)))
    if dry_run:
        for r in todo[:3]:
            print("  candidate: %s  %s" % (r["file_id"], r["name"]))
        dst.close()
        return 0
    if not todo:
        dst.close()
        return 0

    svc = get_service("drive", "v3", SCOPES)
    t0 = time.time()
    done = empty = failed = scanned = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for i, r in enumerate(todo, 1):
        if time.time() - t0 > budget:
            print("  [budget] stopping at %d/%d; the rest resumes next run" % (i, len(todo)))
            break
        fid, kind = r["file_id"], r["kind"]
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


def run_ocr(limit, budget, max_pages=OCR_MAX_PAGES, dry_run=False):
    dst = sqlite3.connect(CONTENT_DB, timeout=60)
    ensure(dst)
    todo = ocr_pending(dst, limit)
    print("== ocr: %d scanned files pending" % len(todo))
    if dry_run:
        for fid in todo[:3]:
            print("  candidate: %s" % fid)
        dst.close()
        return 0
    if not todo:
        dst.close()
        return 0

    svc = get_service("drive", "v3", SCOPES)
    t0 = time.time()
    done = empty = failed = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    last_probe = 0.0
    pace = 0.0
    for i, fid in enumerate(todo, 1):
        if time.time() - t0 > budget:
            print("  [budget] stopping at %d/%d; the rest resumes next run" % (i, len(todo)))
            break
        now_t = time.time()
        if now_t - last_probe >= STEAL_PROBE_INTERVAL:
            st = steal_now()
            pace = steal_pace(st)
            last_probe = now_t
            if st is not None:
                print("  steal=%.0f%% pace=%.1fs" % (st, pace))
        status, text = "ocr", ""
        try:
            text = pdf_to_text_ocr(svc, fid, max_pages)
        except Exception as exc:                       # noqa: BLE001
            status, text = "failed:%s" % type(exc).__name__, ""
        text = clean(text)
        if status == "ocr" and len(re.sub(r"\s", "", text or "")) < 40:
            status, text = "ocr_empty", ""
        dst.execute("INSERT OR REPLACE INTO document_content"
                    "(file_id, content, chars, status, extracted_at) VALUES(?,?,?,?,?)",
                    (fid, text, len(text), status, now))
        if status == "ocr":
            done += 1
        elif status == "ocr_empty":
            empty += 1
        else:
            failed += 1
        if i % 20 == 0:
            dst.commit()
            print("  %d/%d  ocr=%d ocr_empty=%d failed=%d  (%.0fs)"
                  % (i, len(todo), done, empty, failed, time.time() - t0), flush=True)
        if pace:
            time.sleep(pace)
    dst.commit()

    print("  ocr'd %d (empty %d, failed %d) in %.0fs"
          % (done, empty, failed, time.time() - t0))
    dst.close()
    return 0


def run_self_test():
    """Report whether the OCR toolchain is on PATH and always exit 0.

    This box may not have tesseract/pdftoppm installed yet; that is a fact to
    report, not a reason to fail a build or a dry pass that never calls them.
    """
    for name in ("tesseract", "pdftoppm", "pdftotext"):
        path = shutil.which(name)
        print("%s: %s" % (name, path or "NOT FOUND"))
    return 0


def main(argv):
    limit = None
    budget = float(os.environ.get("BOWER_CONTENT_BUDGET", "1800"))
    for i, a in enumerate(argv):
        if a == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1])
        if a == "--budget" and i + 1 < len(argv):
            budget = float(argv[i + 1])

    if "--self-test" in argv:
        return run_self_test()

    dry_run = "--dry-run" in argv
    want_uploaded = "--uploaded" in argv
    want_ocr = "--ocr" in argv
    want_native = "--native" in argv or not (want_uploaded or want_ocr)

    rc = 0
    if want_native:
        rc |= run("native (Docs/Sheets/Slides)",
                  [k for k, v in NATIVE.items() if v], limit, budget, dry_run)
    if want_uploaded:
        rc |= run("uploaded (PDF)", ["PDF"], limit, budget, dry_run)
    if want_ocr:
        rc |= run_ocr(limit, budget, OCR_MAX_PAGES, dry_run)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
