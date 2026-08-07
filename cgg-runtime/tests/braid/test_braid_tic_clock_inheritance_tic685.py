#!/usr/bin/env python3
"""
Braid Test — tic clock inheritance (bk-braid-tic-clock-inheritance, tic 685).

Guards the /review-684 ratified fix-site: braid-input-builder resolved its tic
from the ECONOMY current-pointer as PRIMARY authority while its parent chain
(harmony-invoke -> harmony-input-builder) resolves from the counter/conformation
lane — making the braid's tic identity ORDER-DEPENDENT within the tic (the lag
direction is set by scheduling, not content). The parent row's ALWAYS clause
("braid resolves tic N-1 on EVERY cadence run") was STRUCK at /review 684 on
live lag-0 evidence, which is exactly why the cure is NOT a constant offset:
a +1 repair is wrong on precisely the lag-0 tics.

The ratified cure, both halves pinned here:
  INHERITANCE — the parent passes its resolved tic down (BRAID_INHERIT_TIC /
      --inherit-tic); the envelope tic IS the chain's clock.
  FIRST-CLASS DIVERGENCE — any pointer disagreement is DECLARED (envelope
      `clock_divergence` block + honest flag), never silently absorbed and
      never "corrected" by an offset.

BOTH lag shapes get a fixture (the constant-offset trap is the reason):
  pointer-BEHIND  (pointer N-1, chain N) — the historically-observed lag-1.
  pointer-ADVANCED (pointer N+1, chain N) — the mirror the offset repair
      would double-wrong.
Plus: aligned (no divergence block), legacy uninherited (pointer-primary
behavior PRESERVED, divergence still declared), pointer-absent under both
resolutions, and the pointer-keyed economy-latest lookup (the economy snapshot
keeps the economy's own clock — two clocks, one envelope).
"""
import importlib.util
import json
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent.parent / "scripts"
BUILDER = SCRIPTS / "braid-input-builder.py"
REAL_ZONE = SCRIPTS.parent.parent.parent.parent  # canonical federation root
REAL_CONF = REAL_ZONE / "audit-logs" / "conformations" / "tic-685.json"

_load_seq = 0


def _make_zone(conf_tic=685, pointer_tic=None, with_snapshot=True):
    """Build an isolated fixture zone; returns its root path."""
    zone = pathlib.Path(tempfile.mkdtemp(prefix="braid-clock-fixture-"))
    (zone / ".ticzone").write_text("{}")
    conf_dir = zone / "audit-logs" / "conformations"
    econ_dir = zone / "audit-logs" / "economy"
    conf_dir.mkdir(parents=True)
    econ_dir.mkdir(parents=True)
    # Real conformation as template so the shape projection runs for real.
    conf = json.loads(REAL_CONF.read_text())
    conf["tic_count_physical"] = conf_tic
    (conf_dir / f"tic-{conf_tic}.json").write_text(json.dumps(conf))
    if pointer_tic is not None:
        (econ_dir / "current-pointer.json").write_text(
            json.dumps({"tic": pointer_tic}))
        if with_snapshot:
            (econ_dir / f"economy-tic-{pointer_tic}.json").write_text(
                json.dumps({"tic": pointer_tic, "g_t": 0.75,
                            "detail": {"fixture": True}}))
    return zone


def _build(zone, inherit_tic=None):
    """Load a FRESH builder module pinned to the fixture zone, run build()."""
    global _load_seq
    _load_seq += 1
    prior = os.environ.get("CLAUDE_PROJECT_DIR")
    os.environ["CLAUDE_PROJECT_DIR"] = str(zone)
    try:
        spec = importlib.util.spec_from_file_location(
            f"braid_input_builder_fixture_{_load_seq}", str(BUILDER))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out_path, flags = mod.build(inherit_tic=inherit_tic)
        return json.loads(pathlib.Path(out_path).read_text()), flags
    finally:
        if prior is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = prior
        shutil.rmtree(zone, ignore_errors=True)


def test_pointer_behind_inherited_chain_clock_wins():
    env, flags = _build(_make_zone(conf_tic=685, pointer_tic=684),
                        inherit_tic=685)
    assert env["tic"] == 685, f"envelope tic must be the CHAIN's: {env['tic']}"
    assert env["tic_authority"] == "inherited_parent_clock", env["tic_authority"]
    dv = env["clock_divergence"]
    assert dv is not None, "pointer-behind divergence must be DECLARED"
    assert dv["economy_pointer_tic"] == 684 and dv["inherited_tic"] == 685, dv
    assert any(f.startswith("clock_divergence_declared") for f in flags), flags


def test_pointer_advanced_inherited_chain_clock_wins():
    env, flags = _build(_make_zone(conf_tic=685, pointer_tic=686),
                        inherit_tic=685)
    assert env["tic"] == 685, ("pointer-ADVANCED must NOT drag the chain "
                               f"forward: {env['tic']}")
    assert env["tic_authority"] == "inherited_parent_clock"
    dv = env["clock_divergence"]
    assert dv is not None and dv["economy_pointer_tic"] == 686, dv
    # The mirror shape a constant-offset "repair" would have double-wronged.
    assert dv["resolved_tic"] == 685, dv


def test_aligned_inherited_no_divergence_block():
    env, _flags = _build(_make_zone(conf_tic=685, pointer_tic=685),
                         inherit_tic=685)
    assert env["tic"] == 685
    assert env["tic_authority"] == "inherited_parent_clock"
    assert env["clock_divergence"] is None, ("aligned clocks must not mint a "
                                             "divergence block")


def test_legacy_uninherited_pointer_primary_preserved_divergence_declared():
    env, flags = _build(_make_zone(conf_tic=685, pointer_tic=684),
                        inherit_tic=None)
    assert env["tic"] == 684, ("standalone braid-invoke keeps pointer-primary "
                               f"behavior: {env['tic']}")
    assert env["tic_authority"] == "economy_pointer"
    dv = env["clock_divergence"]
    assert dv is not None and dv["conformation_tic"] == 685, (
        "legacy path must still DECLARE the observable two-authority "
        f"divergence: {dv}")
    assert any(f.startswith("clock_divergence_declared") for f in flags), flags


def test_legacy_uninherited_pointer_absent_conformation_fallback():
    env, _flags = _build(_make_zone(conf_tic=685, pointer_tic=None),
                         inherit_tic=None)
    assert env["tic"] == 685
    assert env["tic_authority"] == "conformation_fallback"
    assert env["clock_divergence"] is None


def test_inherited_pointer_absent_inherits_cleanly():
    env, flags = _build(_make_zone(conf_tic=685, pointer_tic=None),
                        inherit_tic=685)
    assert env["tic"] == 685
    assert env["tic_authority"] == "inherited_parent_clock"
    assert env["clock_divergence"] is None
    assert any(f.startswith("economy_pointer_absent") for f in flags), flags


def test_economy_latest_keyed_on_pointer_tic_not_chain_tic():
    # pointer 684 + inherit 685: the snapshot that EXISTS is the pointer's;
    # the lookup must read economy-tic-684.json, never economy-tic-685.json.
    env, flags = _build(_make_zone(conf_tic=685, pointer_tic=684),
                        inherit_tic=685)
    assert env["economy"]["latest"] is not None, (
        "economy latest must resolve via the POINTER's clock even when the "
        f"envelope tic is inherited: flags={flags}")
    assert env["economy"]["latest"]["tic"] == 684
    assert env["_sources"]["economy_latest"].endswith("economy-tic-684.json")


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    print(f"\n{'ALL PASS' if failures == 0 else str(failures) + ' FAILED'}")
    sys.exit(1 if failures else 0)
