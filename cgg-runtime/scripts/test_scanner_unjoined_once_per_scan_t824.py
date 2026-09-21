#!/usr/bin/env python3
"""Committed suite for the SCAN-LEVEL signal-correlation declaration.

RULED at /review 822 round 1 Q3 ("Move it to the scan's own report"), built at
tic 824 on `bk-scanner-unjoined-declaration-once-per-scan-t822`:

    The field-wise declaration stands. The `signal_correlation_unjoined` notice
    moves off per-row evidence into the scan's own run output, once per scan, by
    member. First donor row wins for `subsystem`, conflicts reported, as built.

Six arms:
  T1 the notice is ABSENT from every queue row's evidence (the move itself).
  T2 it is declared ONCE per scan, BY MEMBER, in the run output + RUN_COUNTERS.
  T3 members are NOT truncated (the old per-row entry cut `detail` at 10).
  T4 the accumulators RESET between scans in one process ("once per scan" must
     not decay into "once per process").
  T5 the FIELD-WISE half stands: a donor row that exists but carries no
     `subsystem` is declared, not just the no-donor-row half.
  T6 subsystem CONFLICTS are reported once per scan by member; first donor wins.

FIXTURE FIDELITY (this is why the first cure of this reader went green and dead):
the fixture's active-manifest rows carry the key set REAL manifest rows carry and
NO other. Measured read-only against audit-logs/signals/active-manifest.jsonl at
tic 824: 59 rows, 0 carrying `subsystem`, 0 carrying `created_at`, 59 carrying
`signal_id`, 0 carrying `id`. `subsystem` reaches this arm ONLY through a daily
emission row. A fixture manifest row carrying `subsystem` would test nothing.

The live audit-logs tree is NEVER touched: every arm builds its own tree under
pytest tmp_path, and every scanner call is preceded by a pre-flight that resolves
the program's own state paths and asserts each lies inside that fixture root.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(SCRIPTS, "cpr-enrichment-scanner.py")

# Any resolved state path containing this is the REAL zone and fails the pre-flight.
REAL_ZONE_MARKER = os.path.join("canonical", "audit-logs")


def _load_scanner(name):
    spec = importlib.util.spec_from_file_location(name, LIVE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _preflight(mod, root):
    """FIRST ACT of every scanner execution here.

    Resolve the program's state paths the way the PROGRAM resolves them (not the
    way the test wishes they resolved) and assert each lies under the fixture
    root. A build that writes through an ambient root is protected by this; a
    silent escape would otherwise land in the real queue.
    """
    root_s = str(Path(root).resolve())
    tz = mod.load_ticzone(str(root))
    al = mod.audit_logs_path(str(root), tz)
    resolved = {
        "audit_logs": al,
        "queue": os.path.join(al, "cprs", "queue.jsonl"),
        "signals": str(Path(al) / "signals"),
        "enrichment": str(Path(al) / "governance" / "enrichment"),
    }
    for name, p in resolved.items():
        rp = str(Path(p).resolve())
        print(f"[preflight] {name} -> {rp}")
        assert rp == root_s or rp.startswith(root_s + os.sep), \
            f"PRE-FLIGHT FAILED: {name} escapes the fixture root -> {rp}"
        assert REAL_ZONE_MARKER not in rp, \
            f"PRE-FLIGHT FAILED: {name} resolves into the REAL zone -> {rp}"
    return resolved


# --- fixture builders -------------------------------------------------------
# Manifest row shape mirrors the REAL population (see module docstring).
def _manifest_row(signal_id, volume=40):
    return {
        "signal_id": signal_id,
        "kind": "TENSION",
        "band": "COGNITIVE",
        "status": "active",
        "volume": volume,
        "visible_volume": volume,
        "heat": round(volume / 100.0, 4),
        "structural_status": "live",
        "source_file": "audit-logs/signals/2026-09-20.jsonl",
        "summary": f"fixture ray {signal_id}",
        "_v2_projection_provisional": False,
        "_v2_projected_at_tic": 824,
        "_v2_projection_inputs": {"age_unknown": False},
    }


def _daily_row(signal_id, subsystem=None):
    row = {
        "type": "signal",
        "id": signal_id,
        "kind": "TENSION",
        "band": "COGNITIVE",
        "status": "active",
        "volume": 40,
        "source": "fixture-emitter.py",
        "source_date": "2026-09-20",
        "created_at": "2026-09-20T00:00:00+00:00",
    }
    if subsystem is not None:
        row["subsystem"] = subsystem
    return row


def _build(root, manifest_rows, daily_rows, holding_ids=("cpr_holding_one",)):
    al = root / "audit-logs"
    (al / "cprs").mkdir(parents=True)
    (al / "tics").mkdir()
    sig = al / "signals"
    sig.mkdir()
    (root / ".ticzone").write_text(
        json.dumps({"audit_logs_path": "audit-logs"}), encoding="utf-8")
    (root / "fixture_source.md").write_text(
        "FIXTURE LESSON BODY: the scan declares its unjoined ids once.\n",
        encoding="utf-8")

    with open(sig / "active-manifest.jsonl", "w", encoding="utf-8") as f:
        for r in manifest_rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    with open(sig / "2026-09-20.jsonl", "w", encoding="utf-8") as f:
        for r in daily_rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")

    qp = al / "cprs" / "queue.jsonl"
    with open(qp, "w", encoding="utf-8") as f:
        for cid in holding_ids:
            f.write(json.dumps({
                "id": cid,
                "status": "enrichment_needed",
                "lesson": "FIXTURE LESSON BODY: the scan declares its unjoined ids once.",
                "source": "fixture_source.md",
                "source_file": "fixture_source.md",
                "source_date": "2026-09-20",
                "subsystem": "cprs",
                "recommended_scopes": ["fixture_source.md"],
                "birth_tic": 800,
            }, separators=(",", ":")) + "\n")
    return qp


def _rows(qp):
    return [json.loads(l) for l in Path(qp).read_text(encoding="utf-8").splitlines()
            if l.strip()]


def _evidence_types(qp):
    out = set()
    for r in _rows(qp):
        for e in r.get("enrichment", []) or []:
            out.add(e.get("evidence_type"))
    return out


# The standard four-member manifold: one joinable, one with no donor row at all,
# one whose donor row carries no `subsystem`, one whose donors disagree.
def _standard(root, holding_ids=("cpr_holding_one",)):
    manifest = [_manifest_row(s) for s in
                ("sig_joined_a", "sig_nodonor_b", "sig_nosubsys_c", "sig_conflict_d")]
    daily = [
        _daily_row("sig_joined_a", subsystem="cprs"),
        _daily_row("sig_nosubsys_c"),                      # donor exists, no subsystem
        _daily_row("sig_conflict_d", subsystem="cprs"),    # FIRST donor wins
        _daily_row("sig_conflict_d", subsystem="signals"),
    ]
    return _build(root, manifest, daily, holding_ids)


def test_unjoined_notice_absent_from_row_evidence(tmp_path):
    """T1 -- THE MOVE. No queue row may carry the notice as per-row evidence."""
    qp = _standard(tmp_path)
    mod = _load_scanner("scanner_t824_t1")
    _preflight(mod, tmp_path)
    mod.scan_and_enrich(str(tmp_path), quiet=True)

    types = _evidence_types(qp)
    assert "signal_correlation_unjoined" not in types, (
        "the notice must NOT ride a queue row any more; found it in " + repr(sorted(types)))
    # the arm still WORKS -- the joinable id is still correlated on the row
    assert "signal_correlation" in types, (
        "the move must not kill the correlation arm itself; got " + repr(sorted(types)))


def test_unjoined_notice_declared_once_per_scan_by_member(tmp_path, capsys):
    """T2 -- ONCE PER SCAN, BY MEMBER, in the scan's own run output."""
    _standard(tmp_path, holding_ids=("cpr_holding_one", "cpr_holding_two"))
    mod = _load_scanner("scanner_t824_t2")
    _preflight(mod, tmp_path)
    mod.scan_and_enrich(str(tmp_path), quiet=False)
    out = capsys.readouterr().out

    # BY MEMBER, exactly the field-wise set: no-donor-row + donor-without-subsystem
    assert set(mod.RUN_COUNTERS["signal_correlation_unjoined_ids"]) == {
        "sig_nodonor_b", "sig_nosubsys_c"}, mod.RUN_COUNTERS["signal_correlation_unjoined_ids"]
    # the arm ran for BOTH holding rows, but the notice is emitted ONCE
    assert mod.RUN_COUNTERS["signal_correlation_arm_rows"] == 2, mod.RUN_COUNTERS
    assert out.count("signal_correlation_unjoined:") == 1, out
    for member in ("sig_nodonor_b", "sig_nosubsys_c"):
        assert out.count(member) == 1, f"{member} named {out.count(member)}x, want 1\n{out}"
    # a joinable id is NOT in the undeclared set
    assert "sig_joined_a" not in mod.RUN_COUNTERS["signal_correlation_unjoined_ids"]
    # the bare count line stays LAST on stdout (the unchanged consumer contract)
    assert out.strip().splitlines()[-1].strip().isdigit(), out


def test_unjoined_members_not_truncated_at_ten(tmp_path, capsys):
    """T3 -- BY MEMBER means every member. The old per-row entry cut at 10."""
    ids = [f"sig_nodonor_{i:02d}" for i in range(12)]
    _build(tmp_path, [_manifest_row(s) for s in ids], [])
    mod = _load_scanner("scanner_t824_t3")
    _preflight(mod, tmp_path)
    mod.scan_and_enrich(str(tmp_path), quiet=False)
    out = capsys.readouterr().out

    assert len(mod.RUN_COUNTERS["signal_correlation_unjoined_ids"]) == 12
    missing = [s for s in ids if s not in out]
    assert not missing, f"{len(missing)} member(s) dropped from the run output: {missing}"


def test_scan_notices_reset_between_scans(tmp_path):
    """T4 -- once per SCAN, not once per PROCESS."""
    _standard(tmp_path)
    mod = _load_scanner("scanner_t824_t4")
    _preflight(mod, tmp_path)
    mod.scan_and_enrich(str(tmp_path), quiet=True)
    first = list(mod.RUN_COUNTERS["signal_correlation_unjoined_ids"])
    rows_first = mod.RUN_COUNTERS["signal_correlation_arm_rows"]
    mod.scan_and_enrich(str(tmp_path), quiet=True)
    second = list(mod.RUN_COUNTERS["signal_correlation_unjoined_ids"])

    assert first == second, f"members accumulated across scans: {first} -> {second}"
    assert mod.RUN_COUNTERS["signal_correlation_arm_rows"] == rows_first, (
        "arm_rows accumulated across scans: "
        f"{rows_first} -> {mod.RUN_COUNTERS['signal_correlation_arm_rows']}")


def test_field_wise_declaration_stands_for_donor_row_missing_subsystem(tmp_path):
    """T5 -- the FIELD-WISE half. A row-wise-only reading declares ZERO here."""
    manifest = [_manifest_row("sig_nosubsys_only")]
    daily = [_daily_row("sig_nosubsys_only")]  # donor EXISTS, carries no subsystem
    _build(tmp_path, manifest, daily)
    mod = _load_scanner("scanner_t824_t5")
    _preflight(mod, tmp_path)
    mod.scan_and_enrich(str(tmp_path), quiet=True)

    # row-wise ("no donor row at all") would be EMPTY here -- that is the point
    assert mod.RUN_COUNTERS["signal_correlation_unjoined_ids"] == ["sig_nosubsys_only"], \
        mod.RUN_COUNTERS["signal_correlation_unjoined_ids"]


def test_subsystem_conflict_reported_once_by_member(tmp_path, capsys):
    """T6 -- conflicts reported; first donor row still wins (as built)."""
    _standard(tmp_path)
    mod = _load_scanner("scanner_t824_t6")
    _preflight(mod, tmp_path)
    mod.scan_and_enrich(str(tmp_path), quiet=False)
    out = capsys.readouterr().out

    conflicts = mod.RUN_COUNTERS["signal_correlation_subsystem_conflicts"]
    assert len(conflicts) == 1, conflicts
    assert conflicts[0]["id"] == "sig_conflict_d", conflicts
    assert sorted(conflicts[0]["values"]) == ["cprs", "signals"], conflicts
    assert out.count("signal_correlation_subsystem_conflict:") == 1, out
    assert "sig_conflict_d" in out, out
    # FIRST donor row wins, unchanged: sig_conflict_d's first donor says `cprs`,
    # so it is correlated to the holding CPR's subsystem and is NOT undeclared.
    assert "sig_conflict_d" not in mod.RUN_COUNTERS["signal_correlation_unjoined_ids"]
