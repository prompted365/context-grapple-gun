#!/usr/bin/env python3
"""Tests for the invocation-currency stamp in subagent-citizen-boot.py
(bk-agent-status-manifest-currency-writes, tic 695 — filed from the /review-693
PROMOTE ray on cpr_mogul_civil_status_check_1f66077728fe).

The defect under cure: agent-status.manifest.json carries currency fields the
runtime never writes — 19/19 entries report status:current, 14 last-validated
at tic 220 (473+ tics stale), 18/19 lack last_invoked_tic entirely. An
unwritten freshness field suppresses the probe absence would prompt: readers
see a currency claim, not a currency FACT. The manifest is sync_exclude'd
(runtime-sync never copies it), so the invocation route can write it without
minting install-drift noise.

The cure at the invocation seam: SubagentStart (subagent-citizen-boot.py) is
the only per-spawn seam that knows the resolved agent_type AND the tic, so it
stamps `last_invoked_tic` into the agent's existing manifest entry at boot.
Contract teeth, each with a fixture arm (selftest-fixture discipline — every
documented conditional gets a fixture, honest-empty/fail-open included):

  1. known agent_type      -> entry stamped with last_invoked_tic == tic
  2. unknown agent_type    -> manifest byte-identical (NEVER invent an entry —
                              the manifest is curated config; the hook is a
                              currency writer, not a schema author)
  3. sibling entries       -> preserved unchanged (full-envelope preservation)
  4. missing manifest      -> no-op, no crash (fail-soft: never block a boot),
                              and the REAL source manifest stays byte-identical
                              — resolution is ZONE-ROOT-ONLY; the v0 HOOK_DIR
                              fallback let exactly this arm fall through and
                              stamp the real manifest (caught live at tic 695,
                              reverted; the fallback was also dead code — every
                              call site already holds a resolved zone_root)
  5. corrupt manifest      -> no-op, no crash, file left as-is
  6. zone-root resolution  -> a manifest at the zone-root-anchored source
                              path is found without HOOK_DIR leakage
                              (Self-Locating Artifact Test Isolation:
                              root-pinned fixtures never touch the real zone)
  7. restamp same agent    -> last_invoked_tic advances (latest invoke wins)

Suite-wide guard: setUp/tearDown snapshot the REAL manifest and assert
byte-stability after every test — no arm may leak a write into the real zone.

Run:  python3 -m unittest test_citizen_boot_invocation_currency
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_HOOK = os.path.join(_HERE, "..", "hooks", "subagent-citizen-boot.py")

_spec = importlib.util.spec_from_file_location("subagent_citizen_boot", _HOOK)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

MANIFEST_SUBPATH = (
    "canonical_developer/context-grapple-gun/cgg-runtime/config/"
    "agent-status.manifest.json"
)


def _seed_manifest(zone_root: Path, agents: dict) -> Path:
    """Plant a manifest at the zone-root-anchored source path."""
    p = zone_root / MANIFEST_SUBPATH
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "$schema_version": 3,
        "generated_at_tic": 222,
        "last_updated_tic": 597,
        "doctrine": "fixture",
        "axes": {},
        "agents": agents,
    }
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return p


_ENTRY = {
    "status": "current",
    "activity_state": "episodic",
    "parity_state": "verified",
    "routing_state": "wired",
    "last_validated_tic": 220,
    "validation_source": "fixture",
    "decision_required": None,
    "notes": "fixture entry",
}


_REAL_MANIFEST = Path(_HERE).parent / "config" / "agent-status.manifest.json"


class InvocationCurrencyStamp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.zone = Path(self._tmp.name)
        self._real_before = (
            _REAL_MANIFEST.read_bytes() if _REAL_MANIFEST.exists() else None
        )

    def tearDown(self):
        # No arm may leak a write into the real zone (Self-Locating Artifact
        # Test Isolation) — this guard is what catches a resolution fallback.
        real_after = (
            _REAL_MANIFEST.read_bytes() if _REAL_MANIFEST.exists() else None
        )
        self._tmp.cleanup()
        assert real_after == self._real_before, (
            "fixture leaked a write into the REAL agent-status manifest"
        )

    # 1 — known agent gets stamped with the boot tic
    def test_known_agent_stamped(self):
        p = _seed_manifest(self.zone, {"cpr-stepper": dict(_ENTRY)})
        _mod.record_invocation_currency(self.zone, "cpr-stepper", 695)
        doc = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(doc["agents"]["cpr-stepper"]["last_invoked_tic"], 695)

    # 2 — unknown agent NEVER mints an entry; manifest byte-identical
    def test_unknown_agent_no_entry_invented(self):
        p = _seed_manifest(self.zone, {"cpr-stepper": dict(_ENTRY)})
        before = p.read_bytes()
        _mod.record_invocation_currency(self.zone, "does-not-exist-xyz", 695)
        self.assertEqual(p.read_bytes(), before)
        doc = json.loads(p.read_text(encoding="utf-8"))
        self.assertNotIn("does-not-exist-xyz", doc["agents"])

    # 3 — sibling entries preserved unchanged (full-envelope preservation)
    def test_sibling_entries_preserved(self):
        sib = dict(_ENTRY, notes="sibling untouched", last_validated_tic=543)
        p = _seed_manifest(
            self.zone, {"cpr-stepper": dict(_ENTRY), "mogul": sib}
        )
        _mod.record_invocation_currency(self.zone, "cpr-stepper", 695)
        doc = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(doc["agents"]["mogul"], sib)
        # non-currency fields of the stamped entry survive too
        self.assertEqual(
            doc["agents"]["cpr-stepper"]["last_validated_tic"], 220
        )
        self.assertEqual(doc["agents"]["cpr-stepper"]["notes"], "fixture entry")

    # 4 — missing manifest: silent no-op (never block a boot)
    def test_missing_manifest_noop(self):
        _mod.record_invocation_currency(self.zone, "cpr-stepper", 695)
        self.assertFalse((self.zone / MANIFEST_SUBPATH).exists())

    # 5 — corrupt manifest: silent no-op, file untouched
    def test_corrupt_manifest_noop(self):
        p = self.zone / MANIFEST_SUBPATH
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{not json", encoding="utf-8")
        _mod.record_invocation_currency(self.zone, "cpr-stepper", 695)
        self.assertEqual(p.read_text(encoding="utf-8"), "{not json")

    # 6 — resolution is zone-root-first (root-pinned fixture, no HOOK_DIR leak)
    def test_zone_root_first_resolution(self):
        p = _seed_manifest(self.zone, {"civil-engineer": dict(_ENTRY)})
        _mod.record_invocation_currency(self.zone, "civil-engineer", 700)
        doc = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(
            doc["agents"]["civil-engineer"]["last_invoked_tic"], 700
        )
        # the REAL source manifest was not touched by the fixture run
        real = Path(_HERE).parent / "config" / "agent-status.manifest.json"
        if real.exists():
            real_doc = json.loads(real.read_text(encoding="utf-8"))
            ce = real_doc["agents"].get("civil-engineer", {})
            self.assertNotEqual(ce.get("last_invoked_tic"), 700)

    # 7 — restamp advances (latest invoke wins)
    def test_restamp_advances(self):
        p = _seed_manifest(self.zone, {"cpr-stepper": dict(_ENTRY)})
        _mod.record_invocation_currency(self.zone, "cpr-stepper", 693)
        _mod.record_invocation_currency(self.zone, "cpr-stepper", 695)
        doc = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(doc["agents"]["cpr-stepper"]["last_invoked_tic"], 695)


if __name__ == "__main__":
    unittest.main()
