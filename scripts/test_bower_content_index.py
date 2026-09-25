"""Unit tests for ops/bower_content_index.py's --ocr mode and its pure-Python
parts: candidate selection, page joining, the 40-char rule, and budget/limit
stopping.

This build machine has neither tesseract nor pdftoppm, and does not have the
google_auth_mcp module bower_content_index.py imports at load time (that path
only exists on the VPS). Every subprocess call and the Drive service are
stubbed here -- nothing in this file touches the network or a real OCR
binary, matching the "no network" constraint in the OCR brief.

NOT part of the plugin's `tests/` gate: `ops/` is VPS-side tooling and out of
scope for `pytest tests/` (see ../L11_R6_NOTES.md). Run directly:

    /usr/bin/python3 -m pytest ops/test_bower_content_index.py -q
"""
import importlib.util
import sqlite3
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def _load_module():
    """Import bower_content_index.py by path, stubbing the VPS-only
    google_auth_mcp module it imports at module load time."""
    if "google_auth_mcp" not in sys.modules:
        fake = types.ModuleType("google_auth_mcp")
        fake.get_service = lambda *a, **k: object()
        sys.modules["google_auth_mcp"] = fake
    spec = importlib.util.spec_from_file_location(
        "bower_content_index", HERE / "bower_content_index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bci = _load_module()


@pytest.fixture
def content_db(tmp_path, monkeypatch):
    path = str(tmp_path / "drive_content.db")
    monkeypatch.setattr(bci, "CONTENT_DB", path)
    return path


@pytest.fixture
def drive_db(tmp_path, monkeypatch):
    path = str(tmp_path / "drive.db")
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE documents (file_id TEXT PRIMARY KEY, name TEXT, kind TEXT)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(bci, "DRIVE_DB", path)
    return path


def _insert_content(path, rows):
    dst = sqlite3.connect(path)
    bci.ensure(dst)
    for fid, status in rows:
        dst.execute("INSERT INTO document_content VALUES (?,?,?,?,?)",
                     (fid, "", 0, status, "2026-01-01T00:00:00Z"))
    dst.commit()
    return dst


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------

def test_ocr_pending_selects_scanned_only_and_respects_limit(content_db):
    dst = _insert_content(content_db, [
        ("a", "ok"), ("b", "scanned"), ("c", "scanned"), ("d", "failed:X"),
    ])
    assert bci.ocr_pending(dst, limit=None) == ["b", "c"]
    assert bci.ocr_pending(dst, limit=1) == ["b"]
    dst.close()


def test_pending_resumes_regardless_of_prior_status(content_db, drive_db):
    """--uploaded (and --native) must skip a file_id already in
    document_content under ANY status, not just 'ok' -- this is what makes a
    budget-truncated run resumable. Verifying, per the brief, that `pending()`
    already does this (it does: `have` is built from every row with no status
    filter) rather than assuming a fix is needed.
    """
    dconn = sqlite3.connect(drive_db)
    dconn.executemany("INSERT INTO documents VALUES (?,?,?)", [
        ("p1", "one.pdf", "PDF"), ("p2", "two.pdf", "PDF"), ("p3", "three.pdf", "PDF"),
    ])
    dconn.commit()
    dconn.close()

    dst = _insert_content(content_db, [("p1", "ok"), ("p2", "failed:Timeout")])
    todo = bci.pending(dst, ["PDF"], None)
    assert [r["file_id"] for r in todo] == ["p3"]
    dst.close()


# ---------------------------------------------------------------------------
# Page rendering / joining, and the "a page failure marks that page" rule
# ---------------------------------------------------------------------------

def test_page_num_sorts_numerically_not_lexically():
    assert bci._page_num("/x/page-2.png") < bci._page_num("/x/page-10.png")


def test_render_pages_orders_by_page_number(tmp_path, monkeypatch):
    prefix = str(tmp_path / "page")
    for n in (2, 10, 1):
        Path("%s-%d.png" % (prefix, n)).write_bytes(b"")

    seen = {}

    def fake_run(cmd, **kw):
        assert cmd[0] == "pdftoppm"
        seen["cmd"] = cmd
        return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(bci.subprocess, "run", fake_run)

    pages = bci.render_pages("/fake.pdf", prefix, 15)
    assert [bci._page_num(p) for p in pages] == [1, 2, 10]
    # Without -png poppler writes .ppm files, the .png glob above finds nothing,
    # and every scanned document is filed as ocr_empty unread. The first live
    # run on the box did exactly that for two documents.
    assert "-png" in seen["cmd"], seen["cmd"]
    assert seen["cmd"].index("-png") < seen["cmd"].index("-r")


def test_ocr_page_returns_text_on_success(monkeypatch):
    def fake_run(cmd, **kw):
        assert cmd[0] == "tesseract"
        return types.SimpleNamespace(returncode=0, stdout=b"hello world")
    monkeypatch.setattr(bci.subprocess, "run", fake_run)
    assert bci.ocr_page("/fake/page-1.png") == "hello world"


def test_ocr_page_failure_returns_empty_not_raise(monkeypatch):
    """A page failure (crash, timeout, nonzero exit) must not propagate --
    it is caught inside ocr_page and marks only that page."""
    def fake_run(cmd, **kw):
        raise RuntimeError("tesseract crashed")
    monkeypatch.setattr(bci.subprocess, "run", fake_run)
    assert bci.ocr_page("/fake/page-2.png") == ""

    def fake_run_nonzero(cmd, **kw):
        return types.SimpleNamespace(returncode=1, stdout=b"")
    monkeypatch.setattr(bci.subprocess, "run", fake_run_nonzero)
    assert bci.ocr_page("/fake/page-3.png") == ""


def test_pdf_to_text_ocr_joins_pages_and_survives_one_bad_page(monkeypatch):
    monkeypatch.setattr(bci, "download", lambda svc, fid: b"%PDF-fake%")
    fake_pages = ["/x/page-1.png", "/x/page-2.png", "/x/page-3.png"]
    monkeypatch.setattr(bci, "render_pages", lambda pdf, prefix, mp: fake_pages)

    per_page = {
        "/x/page-1.png": "first page text",
        "/x/page-2.png": "",              # this page's OCR failed
        "/x/page-3.png": "third page text",
    }
    monkeypatch.setattr(bci, "ocr_page", lambda p, timeout=120: per_page[p])

    text = bci.pdf_to_text_ocr(object(), "fid1", 15)
    # The document's text is unharmed by the one bad page in the middle.
    assert text == "first page text\n\nthird page text"


# ---------------------------------------------------------------------------
# The 40-char rule
# ---------------------------------------------------------------------------

def test_run_ocr_40_char_rule(content_db, monkeypatch):
    _insert_content(content_db, [("short", "scanned"), ("long", "scanned")]).close()

    monkeypatch.setattr(bci, "get_service", lambda *a, **k: object())
    monkeypatch.setattr(bci, "steal_now", lambda: None)
    texts = {"short": "hi", "long": "x" * 41}
    monkeypatch.setattr(bci, "pdf_to_text_ocr", lambda svc, fid, mp: texts[fid])

    rc = bci.run_ocr(limit=None, budget=60)
    assert rc == 0

    dst = sqlite3.connect(content_db)
    rows = dict(dst.execute("SELECT file_id, status FROM document_content"))
    dst.close()
    assert rows["short"] == "ocr_empty"
    assert rows["long"] == "ocr"


def test_run_ocr_failed_page_render_marks_document_failed(content_db, monkeypatch):
    """A failure below the per-page layer (e.g. pdftoppm rejects a corrupt
    PDF) is a document-level failure, recorded as such, not silently dropped
    or crashing the whole pass."""
    _insert_content(content_db, [("bad", "scanned")]).close()
    monkeypatch.setattr(bci, "get_service", lambda *a, **k: object())
    monkeypatch.setattr(bci, "steal_now", lambda: None)

    def boom(svc, fid, mp):
        raise RuntimeError("corrupt pdf")
    monkeypatch.setattr(bci, "pdf_to_text_ocr", boom)

    bci.run_ocr(limit=None, budget=60)
    dst = sqlite3.connect(content_db)
    status = dst.execute("SELECT status FROM document_content WHERE file_id='bad'").fetchone()[0]
    dst.close()
    assert status.startswith("failed:")


# ---------------------------------------------------------------------------
# --budget / --limit stopping
# ---------------------------------------------------------------------------

def test_run_ocr_limit_caps_candidates_and_work_done(content_db, monkeypatch):
    _insert_content(content_db, [(f, "scanned") for f in "abcde"]).close()
    monkeypatch.setattr(bci, "get_service", lambda *a, **k: object())
    monkeypatch.setattr(bci, "steal_now", lambda: None)
    calls = []
    monkeypatch.setattr(bci, "pdf_to_text_ocr",
                         lambda svc, fid, mp: calls.append(fid) or "x" * 100)

    bci.run_ocr(limit=2, budget=60)
    assert calls == ["a", "b"]


def test_run_ocr_budget_stops_early_and_resumes(content_db, monkeypatch):
    _insert_content(content_db, [(f, "scanned") for f in "abc"]).close()
    monkeypatch.setattr(bci, "get_service", lambda *a, **k: object())
    monkeypatch.setattr(bci, "steal_now", lambda: None)
    monkeypatch.setattr(bci, "pdf_to_text_ocr", lambda svc, fid, mp: "x" * 100)

    # Deterministic fake clock: t0, then "just within budget" for the first
    # item's checks, then "over budget" from the second item's check onward.
    seq = iter([1000.0, 1000.1, 1000.1, 1000.2, 1000.2, 1000.2, 1000.2])
    monkeypatch.setattr(bci.time, "time", lambda: next(seq, 1000.2))

    bci.run_ocr(limit=None, budget=0.15)

    dst = sqlite3.connect(content_db)
    statuses = dict(dst.execute("SELECT file_id, status FROM document_content"))
    dst.close()
    # Exactly the first candidate was processed before the budget cutoff;
    # the rest are untouched and will be picked up -- via ocr_pending()'s
    # status='scanned' filter -- by the next run.
    assert statuses["a"] == "ocr"
    assert statuses["b"] == "scanned"
    assert statuses["c"] == "scanned"


# ---------------------------------------------------------------------------
# --dry-run: no network, no side effects
# ---------------------------------------------------------------------------

def test_ocr_dry_run_prints_first_three_candidates_no_side_effects(content_db, monkeypatch, capsys):
    _insert_content(content_db, [(f, "scanned") for f in "abcde"]).close()

    def boom(*a, **k):
        raise AssertionError("dry-run must not touch the network")
    monkeypatch.setattr(bci, "get_service", boom)
    monkeypatch.setattr(bci, "pdf_to_text_ocr", boom)

    rc = bci.run_ocr(limit=None, budget=60, dry_run=True)
    assert rc == 0
    out = capsys.readouterr().out
    assert [ln.split()[-1] for ln in out.splitlines() if "candidate:" in ln] == ["a", "b", "c"]

    dst = sqlite3.connect(content_db)
    statuses = {row[0] for row in dst.execute("SELECT status FROM document_content")}
    dst.close()
    assert statuses == {"scanned"}   # nothing was processed


def test_native_dry_run_no_network(content_db, drive_db, monkeypatch, capsys):
    dconn = sqlite3.connect(drive_db)
    dconn.execute("INSERT INTO documents VALUES (?,?,?)", ("d1", "Doc One", "Google Doc"))
    dconn.commit()
    dconn.close()

    def boom(*a, **k):
        raise AssertionError("dry-run must not call get_service")
    monkeypatch.setattr(bci, "get_service", boom)

    rc = bci.main(["--dry-run"])
    assert rc == 0
    assert "candidate: d1" in capsys.readouterr().out


def test_main_ocr_dispatch_does_not_run_native_pass(content_db, monkeypatch, capsys):
    _insert_content(content_db, [("s1", "scanned")]).close()

    def boom(*a, **k):
        raise AssertionError("native/uploaded run() should not fire for --ocr")
    monkeypatch.setattr(bci, "run", boom)
    monkeypatch.setattr(bci, "get_service", boom)

    rc = bci.main(["--ocr", "--dry-run"])
    assert rc == 0
    assert "candidate: s1" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Steal guard (modeled on ops/embed_backlog.sh)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("steal,expected", [
    (None, 0.0),
    (0, 0.25), (9.9, 0.25),
    (10, 1.0), (24.9, 1.0),
    (25, 4.0), (49.9, 4.0),
    (50, 12.0), (74.9, 12.0),
    (75, 30.0), (100, 30.0),
])
def test_steal_pace_tiers_match_embed_backlog(steal, expected):
    assert bci.steal_pace(steal) == expected


def test_steal_now_averages_last_three_samples(monkeypatch):
    # First two lines mimic vmstat's header + boot-time-average line, which
    # steal_now() must discard; only the trailing 3 live samples count.
    vmstat_output = "header\nboot avg\nx 10 y\nx 20 y\nx 30 y\n"

    def fake_run(cmd, **kw):
        assert cmd[0] == "vmstat"
        return types.SimpleNamespace(stdout=vmstat_output.encode())
    monkeypatch.setattr(bci.subprocess, "run", fake_run)
    assert bci.steal_now() == pytest.approx(20.0)


def test_steal_now_returns_none_when_vmstat_unavailable(monkeypatch):
    def fake_run(cmd, **kw):
        raise FileNotFoundError("no vmstat on this box")
    monkeypatch.setattr(bci.subprocess, "run", fake_run)
    assert bci.steal_now() is None


# ---------------------------------------------------------------------------
# --self-test: reports tool presence, always exits 0
# ---------------------------------------------------------------------------

def test_self_test_always_exits_zero_tools_missing(monkeypatch, capsys):
    monkeypatch.setattr(bci.shutil, "which", lambda name: None)
    assert bci.run_self_test() == 0
    assert "NOT FOUND" in capsys.readouterr().out


def test_self_test_always_exits_zero_tools_present(monkeypatch, capsys):
    monkeypatch.setattr(bci.shutil, "which", lambda name: "/usr/bin/%s" % name)
    assert bci.run_self_test() == 0
    assert "NOT FOUND" not in capsys.readouterr().out


def test_main_self_test_flag_dispatches(monkeypatch, capsys):
    monkeypatch.setattr(bci.shutil, "which", lambda name: None)
    assert bci.main(["--self-test"]) == 0
