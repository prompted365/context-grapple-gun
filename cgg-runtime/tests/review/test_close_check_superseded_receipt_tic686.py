#!/usr/bin/env python3
"""
Review-close-check Test — preserve-prior-under-superseded-receipt
(bk-review-close-check-observation-key, tic 686).

Guards the /review-685 ratified fix-site (cpr_mogul_review_close_check_21084d73fe93
PROMOTE — ray on cgg-ledger#artifact-count-1-fix-family): the T4c write ladder's
N=1-per-tic canonical identity is CORRECT and STANDS (tic-{N}-check.json,
latest-wins, the closed consumer set untouched) — the residue is the AXIS: two
distinct mandates within one tic produce two distinct OBSERVATIONS (pre-/review
baseline vs post-/review state), and the replace branch destroyed the earlier
one with only a stderr INFO line (un-receipted; 41/329 tics = 12.5%). The cure
ratified here is preserve-prior-under-superseded-receipt, NOT observation-keyed
or per-mandate filenames (per-mandate re-opens the N!=1 family; a review-phase
detector would be inference, not evidence):

  PRESERVE — before an overwrite, the prior artifact's RAW BYTES land at
             superseded/{stem}.superseded-{seq}.json (sequence-numbered,
             never themselves overwritten).
  RECEIPT  — the review-close-check-log row for the replace carries a
             first-class `superseded_receipt` (preserved_path,
             justification_class, prior_generated_at) — the KI: a
             terminal-essence state change requires a justified receipt and
             may not let signal go dark.
  N=1      — the canonical tic-{N}-check.json still holds exactly the latest
             observation; skip/first-write paths preserve nothing (no receipt
             owed when nothing was destroyed).
"""
import importlib.util
import json
import os
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent.parent / "scripts"
SCRIPT = SCRIPTS / "review-close-check.py"

_load_seq = 0


def _load_module():
    global _load_seq
    _load_seq += 1
    spec = importlib.util.spec_from_file_location(
        f"review_close_check_fixture_{_load_seq}", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_zone(tic=910, mandate_id=None, queue_rows=None):
    """Isolated zone: .ticzone + queue + mandate current.json."""
    zone = pathlib.Path(tempfile.mkdtemp(prefix="rcc-superseded-fixture-"))
    (zone / ".ticzone").write_text("{}")
    al = zone / "audit-logs"
    (al / "cprs").mkdir(parents=True)
    (al / "mogul" / "mandates").mkdir(parents=True)
    rows = queue_rows or []
    (al / "cprs" / "queue.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows))
    (al / "mogul" / "mandates" / "current.json").write_text(json.dumps({
        "mandate_id": mandate_id or f"tic-{tic}-fixture",
        "tic": tic,
    }))
    return zone


def _report_dir(zone):
    return zone / "audit-logs" / "mogul" / "cycle-reports" / "review-close-checks"


def _log_rows(zone):
    log = zone / "audit-logs" / "services" / "review-close-check-log.jsonl"
    if not log.exists():
        return []
    return [json.loads(l) for l in log.read_text().splitlines() if l.strip()]


_SKIPPED_ROW = {"id": "cpr_fixture_skipped_a", "status": "skipped"}
# A second queue shape whose verdict_counts differ → prior_norm != report_norm.
_SKIPPED_ROWS_2 = [
    {"id": "cpr_fixture_skipped_a", "status": "skipped"},
    {"id": "cpr_fixture_skipped_b", "status": "skipped"},
]


# ---------------------------------------------------------------------------
# [1] First write: canonical artifact lands, NO superseded residue, no receipt.
# ---------------------------------------------------------------------------
def test_first_write_no_superseded_residue():
    zone = _make_zone(queue_rows=[_SKIPPED_ROW])
    mod = _load_module()
    mod.run_check(str(zone))
    canon = _report_dir(zone) / "tic-910-check.json"
    assert canon.exists()
    assert not (_report_dir(zone) / "superseded").exists()
    rows = _log_rows(zone)
    assert rows[-1]["decision"] == "write"
    assert "superseded_receipt" not in rows[-1]


# ---------------------------------------------------------------------------
# [2] Identical re-run: skip path — nothing preserved, no receipt owed
#     (nothing was destroyed).
# ---------------------------------------------------------------------------
def test_skip_path_preserves_nothing():
    zone = _make_zone(queue_rows=[_SKIPPED_ROW])
    mod = _load_module()
    mod.run_check(str(zone))
    mod.run_check(str(zone))
    rows = _log_rows(zone)
    assert rows[-1]["decision"] == "skip"
    assert "superseded_receipt" not in rows[-1]
    assert not (_report_dir(zone) / "superseded").exists()


# ---------------------------------------------------------------------------
# [3] The replace path — the ratified cure, all three teeth:
#     prior bytes preserved · first-class receipt with justification_class ·
#     canonical N=1 latest-wins intact.
# ---------------------------------------------------------------------------
def test_replace_preserves_prior_under_receipt():
    zone = _make_zone(queue_rows=[_SKIPPED_ROW])
    mod = _load_module()
    first = mod.run_check(str(zone))
    canon = _report_dir(zone) / "tic-910-check.json"
    prior_bytes = canon.read_bytes()

    # Second observation, same tic: the queue moved (the pre/post-/review shape).
    q = zone / "audit-logs" / "cprs" / "queue.jsonl"
    q.write_text("".join(json.dumps(r) + "\n" for r in _SKIPPED_ROWS_2))
    mod2 = _load_module()
    second = mod2.run_check(str(zone))

    rows = _log_rows(zone)
    assert rows[-1]["decision"] == "replace"
    receipt = rows[-1]["superseded_receipt"]
    assert receipt["justification_class"] == "superseded_by_same_tic_reobservation"
    preserved = zone / receipt["preserved_path"]
    assert preserved.exists()
    # PRESERVE: raw prior bytes, byte-identical — the observation did not go dark.
    assert preserved.read_bytes() == prior_bytes
    assert receipt["prior_generated_at"] == first["generated_at"]
    # N=1: the canonical name holds exactly the LATEST observation.
    current = json.loads(canon.read_text())
    assert current["generated_at"] == second["generated_at"]
    assert current["verdict_counts"]["skipped"] == 2
    # The superseded copy lives OUTSIDE the canonical name (no N=2 regression).
    assert preserved.name != canon.name


# ---------------------------------------------------------------------------
# [4] Successive replaces sequence-number their preserved copies — the second
#     replace never overwrites the first preserved observation.
# ---------------------------------------------------------------------------
def test_successive_replaces_never_overwrite_preserved():
    zone = _make_zone(queue_rows=[_SKIPPED_ROW])
    mod = _load_module()
    mod.run_check(str(zone))
    q = zone / "audit-logs" / "cprs" / "queue.jsonl"

    q.write_text("".join(json.dumps(r) + "\n" for r in _SKIPPED_ROWS_2))
    _load_module().run_check(str(zone))
    q.write_text(json.dumps({"id": "cpr_fixture_skipped_c", "status": "skipped"}) + "\n")
    _load_module().run_check(str(zone))

    rows = [r for r in _log_rows(zone) if r["decision"] == "replace"]
    assert len(rows) == 2
    paths = [r["superseded_receipt"]["preserved_path"] for r in rows]
    assert len(set(paths)) == 2
    for p in paths:
        assert (zone / p).exists()


# ---------------------------------------------------------------------------
# [5] Corrupt prior: replace still preserves the raw bytes (honest evidence,
#     even unparseable) under a corrupt_prior_replaced justification.
# ---------------------------------------------------------------------------
def test_corrupt_prior_preserved_with_corrupt_justification():
    zone = _make_zone(queue_rows=[_SKIPPED_ROW])
    mod = _load_module()
    mod.run_check(str(zone))
    canon = _report_dir(zone) / "tic-910-check.json"
    canon.write_text("{not json —")
    corrupt_bytes = canon.read_bytes()

    _load_module().run_check(str(zone))
    rows = _log_rows(zone)
    assert rows[-1]["decision"] == "replace"
    receipt = rows[-1]["superseded_receipt"]
    assert receipt["justification_class"] == "corrupt_prior_replaced"
    assert receipt["prior_generated_at"] is None
    preserved = zone / receipt["preserved_path"]
    assert preserved.read_bytes() == corrupt_bytes
    # Canonical name healed to a parseable current report.
    json.loads(canon.read_text())


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    passed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] {name}: {type(exc).__name__}: {exc}")
    print("=" * 74)
    print(f"RESULT: {passed}/{len(fns)} — {'OK' if passed == len(fns) else 'FAIL'}")
    sys.exit(0 if passed == len(fns) else 1)
