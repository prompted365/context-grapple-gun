#!/usr/bin/env python3
"""Committed NC suite for cpr-enrichment-scanner append-only + lock disciplines.

Promoted from the wave-4 scratchpad harness (w4-scanner/nc_harness.py, cable
receipt bk-cpr-enrichment-scanner-whole-file-rewrite-of-queue-B2-wave4-tic765)
at /review 767 Q6 (F-765-S3/OM-1, Architect-signed). Three arms:

  1. CURE arm — a row landed by another writer BETWEEN the scanner's
     load_queue() and its write block SURVIVES, and history rows stay intact
     (the append-only copy-forward cure, landed wave 4).
  2. REVERTED-CURE discriminating control — the old defect (whole-file
     rewrite, last-line-per-enriched-id replaced in place) is simulated by
     monkeypatching the write boundary; the concurrent row is LOST, proving
     this suite discriminates (an NC that cannot fail proves nothing —
     guard 19's EVALUATED-BUT-NON-DISCRIMINATING face, inscribed this same
     /review pass).
  3. LOCKDIR-EXCLUSION arm (F-765-S2 cure, /review 767 Q5) — when the
     in-process fcntl fallback fires (missing trailing newline forces it),
     it also acquires the shell writers' mkdir "<queue>.lockdir" (the live
     common denominator: flock(1) is absent on the primary machine) and
     WAITS while a shell-style holder owns it.

The live audit-logs/cprs/queue.jsonl is NEVER touched: every arm builds its
own fixture tree under pytest tmp_path.
"""
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(SCRIPTS, "cpr-enrichment-scanner.py")
ATOMIC_APPEND_SH = os.path.join(SCRIPTS, "lib", "atomic-append.sh")

CONCURRENT_ROW = {
    "id": "cpr_alpha",
    "status": "tic_gated",
    "advanced_tic": 765,
    "lesson": "alpha lesson text",
    "source": "alpha.md",
    "birth_tic": 700,
    "lifecycle_writeback": True,
    "envelope_marker": "CONCURRENT_STEPPER_ROW",
}


def _build_fixture(root: Path):
    al = root / "audit-logs"
    (al / "cprs").mkdir(parents=True)
    (al / "tics").mkdir()
    (al / "signals").mkdir()
    (root / ".ticzone").write_text(
        json.dumps({"audit_logs_path": "audit-logs"}), encoding="utf-8")
    (root / "beta_source.md").write_text(
        "BETA LESSON BODY: append-only ledgers must not be whole-file rewritten.\n",
        encoding="utf-8")
    rows = [
        {"id": "cpr_alpha", "status": "extracted", "lesson": "alpha lesson text",
         "source": "alpha.md", "birth_tic": 700, "envelope_marker": "ALPHA_HISTORY_ROW"},
        {"id": "cpr_alpha", "status": "enrichment_needed", "lesson": "alpha lesson text",
         "source": "alpha.md", "birth_tic": 700, "envelope_marker": "ALPHA_LATEST_ROW"},
        {"id": "cpr_unrelated", "status": "promoted", "lesson": "unrelated",
         "envelope_marker": "UNRELATED_ROW"},
        {"id": "cpr_beta", "status": "enrichment_needed",
         "lesson": "BETA LESSON BODY: append-only ledgers must not be whole-file rewritten.",
         "source": "beta_source.md", "source_file": "beta_source.md",
         "source_date": "2026-08-01", "subsystem": "cprs",
         "recommended_scopes": ["beta_source.md"], "birth_tic": 701,
         "envelope_marker": "BETA_LATEST_ROW"},
    ]
    qp = al / "cprs" / "queue.jsonl"
    with open(qp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    return qp


def _load_scanner(name):
    spec = importlib.util.spec_from_file_location(name, LIVE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _concurrent_append(qp):
    line = json.dumps(CONCURRENT_ROW, separators=(",", ":"))
    proc = subprocess.run(["bash", ATOMIC_APPEND_SH, "--append", str(qp), line],
                          capture_output=True, text=True)
    assert proc.returncode == 0, f"atomic-append.sh rc={proc.returncode} {proc.stderr}"


def _inject(mod, qp):
    real = mod.resolve_current_tic

    def wrapped(al_path):
        v = real(al_path)
        _concurrent_append(qp)
        return v

    mod.resolve_current_tic = wrapped


def _parse(qp):
    lines = [l for l in Path(qp).read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def test_cure_concurrent_append_survives(tmp_path):
    qp = _build_fixture(tmp_path)
    mod = _load_scanner("scanner_nc_cure")
    _inject(mod, qp)
    mod.scan_and_enrich(str(tmp_path), quiet=True)
    parsed = _parse(qp)
    markers = [d.get("envelope_marker") for d in parsed]
    assert "CONCURRENT_STEPPER_ROW" in markers, "concurrent row must survive the scan"
    assert "ALPHA_HISTORY_ROW" in markers, "history row must stay byte-present"


def test_reverted_cure_control_discriminates(tmp_path):
    """Simulate the pre-cure defect at the write boundary: whole-file rewrite
    replacing the last line per enriched id in place, from the scanner's OWN
    (stale) snapshot. The concurrent row must be LOST — proving arm 1 can fail."""
    qp = _build_fixture(tmp_path)
    mod = _load_scanner("scanner_nc_revert")
    _inject(mod, qp)

    def old_defect_write(queue_path, rows):
        # pre-cure shape: read back, replace last-line-per-id, rewrite whole file
        lines = [l for l in Path(queue_path).read_text(encoding="utf-8").splitlines()
                 if l.strip()]
        parsed = [json.loads(l) for l in lines]
        by_id_last = {}
        for i, d in enumerate(parsed):
            by_id_last[d["id"]] = i
        for r in rows:
            i = by_id_last.get(r["id"])
            if i is not None:
                parsed[i] = r
            else:
                parsed.append(r)
        # CRITICAL: written from the scanner's snapshot semantics — a row another
        # writer landed for an enriched id is exactly the row overwritten. We
        # reproduce that by rewriting from the mutated list only.
        with open(queue_path, "w", encoding="utf-8") as f:
            for d in parsed:
                if d.get("envelope_marker") == "CONCURRENT_STEPPER_ROW" and \
                   d["id"] in {r["id"] for r in rows}:
                    continue  # the overwrite victim
                f.write(json.dumps(d, separators=(",", ":")) + "\n")
        return "whole-file-rewrite(SIMULATED-DEFECT)"

    mod.append_queue_rows = old_defect_write
    mod.scan_and_enrich(str(tmp_path), quiet=True)
    parsed = _parse(qp)
    markers = [d.get("envelope_marker") for d in parsed]
    assert "CONCURRENT_STEPPER_ROW" not in markers, (
        "discriminating control: with the cure reverted the concurrent row is lost; "
        "if it survives, this suite cannot fail and proves nothing")


def test_lockdir_fallback_mutual_exclusion(tmp_path):
    """F-765-S2 cure arm: force the in-process fallback (missing trailing
    newline), hold the shell writers' mkdir lockdir, assert the fallback WAITS
    for it and reports the composite mechanism."""
    qp = _build_fixture(tmp_path)
    # strip trailing newline -> append_queue_rows refuses the shell primitive
    raw = Path(qp).read_bytes().rstrip(b"\n")
    Path(qp).write_bytes(raw)
    mod = _load_scanner("scanner_nc_lockdir")

    lock_dir = str(qp) + ".lockdir"
    os.mkdir(lock_dir)  # a shell-style writer holds the lock
    release_after = 1.5

    def release():
        time.sleep(release_after)
        os.rmdir(lock_dir)

    t = threading.Thread(target=release)
    t.start()
    start = time.monotonic()
    mech = mod.append_queue_rows(str(qp), [dict(CONCURRENT_ROW)])
    waited = time.monotonic() - start
    t.join()
    assert mech == "flock-inprocess+lockdir", mech
    assert waited >= release_after - 0.6, (
        f"fallback must WAIT for the shell lockdir; waited only {waited:.2f}s")
    parsed = _parse(qp)
    assert any(d.get("envelope_marker") == "CONCURRENT_STEPPER_ROW" for d in parsed)
