#!/usr/bin/env python3
"""Tests for the ladder-audit TWO-ALTITUDES disclosure (ruled /review 758 Q1 from
cpr_mogul_ladder_audit_18aea9c55cf5 — PROMOTE-as-refinement-ray on the
presence-observation family tail, breadcrumb at #disagreement-as-evidence:
ledger.md#a-shared-instrument-name-across-two-altitudes-discloses-its-altitude-and-its-siblings-standing-count).

The contract under guard: one token ("ladder_audit") names TWO instruments at
different altitudes — the BASE chain scan (CLAUDE.md rule coherence, `run_audit`)
and the ladder DOWN-LANE audit (per-rung KI rehydration-in-spirit, this script's
subcommand family). A clean base result printed alone converts a scope-limited
clean into a false all-clear (tic 755: summary {coherent: 375} / findings []
beside 53 open sig_ladder_down_audit_finding_* rays = 91.4% of the active
manifold). The instrument's result must therefore name WHICH instrument ran and
disclose the sibling's standing count — computed from the manifold the scan
already reads, never a second read, and DECLARED with its predicate so a reader
can re-derive it.

Arms (all mandatory):
  (a) the base-scan result carries `instrument`, `altitude == "base_chain_scan"`,
      `altitude_disclosure` (non-empty prose naming the down-lane sibling), and
      `sibling_instruments.ladder_down_audit.{open_findings_on_manifold, of_active_rays,
      predicate, ids}` — keys present even when the count is ZERO (the honest-empty arm);
  (b) the sibling count equals the number of ACTIVE rays whose subsystem is
      `ladder_downlane` OR whose id carries the `sig_ladder_down_audit_finding_`
      prefix, over the same latest-per-id read `signal_subsystems_active` uses —
      resolved / dismissed rays are NOT counted;
  (c) a manifold with down-lane rays present yields a non-zero count whose `ids`
      re-derive the number (len(ids) == open_findings_on_manifold) — the
      membership set rides beside the headline (the re-derivability axis).

Run: python3 -m pytest -q cgg-runtime/scripts/test_ladder_audit_altitude_disclosure_tic758.py
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("ladder_audit_mod", HERE / "ladder-audit.py")
la = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(la)


def _zone(tmp: Path, signals: list[dict]) -> str:
    """A minimal governed zone: one CLAUDE.md, a .ticzone, and a signal lane."""
    (tmp / ".ticzone").write_text(json.dumps({"tic": 758, "rung": "site"}), encoding="utf-8")
    (tmp / "CLAUDE.md").write_text("# root\n\n- **Rule one** — a governed rule.\n", encoding="utf-8")
    sig_dir = tmp / "audit-logs" / "signals"
    sig_dir.mkdir(parents=True)
    with open(sig_dir / "2026-09-01.jsonl", "w", encoding="utf-8") as f:
        for s in signals:
            f.write(json.dumps(s) + "\n")
    return str(tmp)


def _ray(sid, subsystem="ladder_downlane", status="active", kind="LESSON"):
    return {"type": "signal", "id": sid, "signal_id": sid, "subsystem": subsystem, "status": status,
            "kind": kind, "band": "COGNITIVE", "volume": 10, "emitted_tic": 700}


def test_a_keys_present_even_at_zero():
    with tempfile.TemporaryDirectory() as td:
        zr = _zone(Path(td), [_ray("sig_maps_stale", subsystem="maps", kind="WATCH")])
        r = la.run_audit(zr)
    assert r["altitude"] == "base_chain_scan"
    assert "BASE chain scan" in r["instrument"]
    assert "DOWN-LANE" in r["altitude_disclosure"]
    sib = r["sibling_instruments"]["ladder_down_audit"]
    for k in ("open_findings_on_manifold", "of_active_rays", "predicate", "ids"):
        assert k in sib, k
    assert sib["open_findings_on_manifold"] == 0 and sib["ids"] == []
    assert sib["of_active_rays"] == 1


def test_b_count_is_active_downlane_rays_only():
    rays = [
        _ray("sig_ladder_down_audit_finding_aaaaaaaa"),
        _ray("sig_ladder_down_audit_finding_bbbbbbbb", subsystem="unknown"),      # prefix arm
        _ray("sig_other_downlane_shaped", subsystem="ladder_downlane"),           # subsystem arm
        _ray("sig_ladder_down_audit_finding_cccccccc", status="resolved"),       # NOT counted
        _ray("sig_ladder_down_audit_finding_dddddddd", status="dismissed"),      # NOT counted
        _ray("sig_maps_stale", subsystem="maps", kind="WATCH"),                   # not a sibling ray
    ]
    with tempfile.TemporaryDirectory() as td:
        zr = _zone(Path(td), rays)
        r = la.run_audit(zr)
    sib = r["sibling_instruments"]["ladder_down_audit"]
    assert sib["open_findings_on_manifold"] == 3
    assert sorted(sib["ids"]) == ["sig_ladder_down_audit_finding_aaaaaaaa",
                                  "sig_ladder_down_audit_finding_bbbbbbbb",
                                  "sig_other_downlane_shaped"]
    assert sib["of_active_rays"] == 4  # the three siblings + maps_stale; resolved/dismissed excluded


def test_c_ids_rederive_the_headline():
    rays = [_ray(f"sig_ladder_down_audit_finding_{i:08x}") for i in range(7)]
    with tempfile.TemporaryDirectory() as td:
        zr = _zone(Path(td), rays)
        r = la.run_audit(zr)
    sib = r["sibling_instruments"]["ladder_down_audit"]
    assert sib["open_findings_on_manifold"] == 7 == len(sib["ids"])
    assert "latest-per-id" in sib["predicate"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
