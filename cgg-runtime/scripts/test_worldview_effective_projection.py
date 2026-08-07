#!/usr/bin/env python3
"""Fixtures for the b3 effective-record projection in office-worldview.py
(bk-worldview-projection-aware-b3, tic 683).

Arms (every documented conditional, both sides — cgg-ledger#selftest-fixtures-
must-exercise-documented-conditional-paths):
  1. corrected-row override    — a row with a resolved correction renders its
                                 effective_record, not the raw row
  2. blocked-row drop          — a row whose correction is unresolved/review-held
                                 is dropped row-scoped
  3. no-correction identity    — untouched rows pass through byte-identical
  4. projection-unavailable    — eff=None withholds the source ([]), never raw
  5. declaration fragment      — compile_fragments emits boot.effective_projection
                                 (SUBSTRATE when active, COUNTER when unavailable)
  6. live-zone integration     — the real zone builds a projection; the live
                                 corrected rows are picked up; the render carries
                                 the declaration (read-only on the real zone)

The unit arms drive _jsonl_rows_effective directly with a synthetic projection
tuple (the correction-envelope authorization chain is digest-bound to the real
migrations inventory and is deliberately NOT reproduced in fixtures — the lib has
its own suite; this suite tests the RENDERER's consumption seam).
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

import importlib.util

_spec = importlib.util.spec_from_file_location("office_worldview", HERE / "office-worldview.py")
ow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ow)

from effective_record import record_identifiers  # lib


def _proj(corrections=None, blocked=None):
    """A synthetic _effective_projection return using the resolver's OWN
    record addressing (exact parity is the contract)."""
    corrections = corrections or {}
    blocked = blocked or set()
    meta = {"status": "corrected" if corrections or blocked else "safe",
            "corrected": len(corrections), "blocked": len(blocked),
            "source_digest": "fixturedigest"}
    return (corrections, blocked, record_identifiers, meta)


class JsonlRowsEffective(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.zone = Path(self.tmp.name)
        (self.zone / "audit-logs" / "signals").mkdir(parents=True)
        self.surface = self.zone / "audit-logs" / "signals" / "active-manifest.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, rows):
        self.surface.write_text("\n".join(json.dumps(r) for r in rows) + "\n",
                                encoding="utf-8")

    def test_corrected_row_override(self):
        raw = {"id": "sig_a", "volume": 10, "summary": "raw"}
        other = {"id": "sig_b", "volume": 20}
        self._write([raw, other])
        eff_row = {"id": "sig_a", "volume": 35, "summary": "corrected"}
        key = ("audit-logs/signals/active-manifest.jsonl", "sig_a")
        rows = ow._jsonl_rows_effective(self.surface, self.zone, _proj({key: eff_row}))
        self.assertIn(eff_row, rows)
        self.assertNotIn(raw, rows)
        self.assertIn(other, rows)

    def test_blocked_row_drop(self):
        held = {"id": "sig_held", "volume": 5}
        kept = {"id": "sig_ok", "volume": 6}
        self._write([held, kept])
        key = ("audit-logs/signals/active-manifest.jsonl", "sig_held")
        rows = ow._jsonl_rows_effective(self.surface, self.zone, _proj(blocked={key}))
        self.assertNotIn(held, rows)
        self.assertIn(kept, rows)

    def test_no_correction_identity(self):
        raw = [{"id": "sig_1", "volume": 1}, {"id": "sig_2", "volume": 2}]
        self._write(raw)
        rows = ow._jsonl_rows_effective(self.surface, self.zone, _proj())
        self.assertEqual(rows, raw)

    def test_projection_unavailable_withholds(self):
        self._write([{"id": "sig_1", "volume": 1}])
        self.assertEqual(ow._jsonl_rows_effective(self.surface, self.zone, None), [])

    def test_correction_on_other_surface_suppresses_nothing(self):
        raw = [{"id": "sig_1", "volume": 1}]
        self._write(raw)
        key = ("audit-logs/cprs/queue.jsonl", "some_cpr_id")
        rows = ow._jsonl_rows_effective(self.surface, self.zone,
                                        _proj({key: {"id": "some_cpr_id"}}))
        self.assertEqual(rows, raw)


class DeclarationFragment(unittest.TestCase):
    """The declaration fragment rides plane L0 ('boot.' prefix) — visible to citizen
    standings; the fixture registry mints a citizen so the standing policy keeps it."""

    def test_active_projection_declares_substrate(self):
        corrections = {("audit-logs/cprs/queue.jsonl", "x"): {"id": "x"}}
        frag_texts = self._compile_with(_proj(corrections))
        decl = [f for f in frag_texts if f["id"] == "boot.effective_projection"]
        self.assertEqual(len(decl), 1)
        self.assertEqual(decl[0]["pertinence"]["class"], "SUBSTRATE")
        self.assertIn("projection ACTIVE", decl[0]["text"])

    def test_unavailable_projection_declares_counter(self):
        frag_texts = self._compile_with(None)
        decl = [f for f in frag_texts if f["id"] == "boot.effective_projection"]
        self.assertEqual(len(decl), 1)
        self.assertEqual(decl[0]["pertinence"]["class"], "COUNTER")
        self.assertIn("UNAVAILABLE", decl[0]["text"])

    def test_no_contract_zone_declares_nothing_and_renders_raw(self):
        """A zone without audit-logs/corrections/ has no correction contract:
        no declaration fragment, and JSONL rows pass through raw (the real
        _effective_projection, not a monkeypatch)."""
        with tempfile.TemporaryDirectory() as td:
            zone = self._fixture_zone(Path(td))
            sig_dir = zone / "audit-logs" / "signals"
            sig_dir.mkdir(parents=True)
            (sig_dir / "active-manifest.jsonl").write_text(
                json.dumps({"signal_id": "sig_x", "volume": 12, "band": "COGNITIVE"}) + "\n",
                encoding="utf-8")
            frags = ow.compile_fragments(zone, "ent_fixture", 1)
            self.assertFalse(any(f["id"] == "boot.effective_projection" for f in frags))
            sig = [f for f in frags if f["id"] == "tic.signals"]
            self.assertEqual(len(sig), 1)
            self.assertIn("sig_x", sig[0]["text"])

    @staticmethod
    def _fixture_zone(zone: Path) -> Path:
        (zone / ".ticzone").write_text("{}", encoding="utf-8")
        (zone / "audit-logs").mkdir(exist_ok=True)
        ak = zone / "autonomous_kernel"
        ak.mkdir(exist_ok=True)
        (ak / "actor-registry.json").write_text(json.dumps({
            "actors": [{"entity_id": "ent_fixture", "standing": "citizen",
                        "status": "active", "entity_kind": "agent", "roles": []}]
        }), encoding="utf-8")
        return zone

    def _compile_with(self, proj):
        with tempfile.TemporaryDirectory() as td:
            zone = self._fixture_zone(Path(td))
            orig = ow._effective_projection
            ow._effective_projection = lambda _zr, _vp=None: proj
            try:
                return ow.compile_fragments(zone, "ent_fixture", 1)
            finally:
                ow._effective_projection = orig


class LiveZoneIntegration(unittest.TestCase):
    """Read-only against the real zone: the projection builds and the live
    corrected rows are picked up. Skipped when run outside the zone."""

    ZONE = Path("/Users/breydentaylor/canonical")

    def test_live_projection_builds_and_declares(self):
        if not (self.ZONE / ".ticzone").is_file():
            self.skipTest("real zone unavailable")
        eff = ow._effective_projection(self.ZONE)
        self.assertIsNotNone(eff, "projection failed to build on the live zone")
        corrections, blocked, _rid, meta = eff
        self.assertGreaterEqual(meta["corrected"], 1)
        # the live corrected surfaces are queue.jsonl + reviews files today —
        # none of them are worldview-consumed; assert none target the manifest
        self.assertTrue(all(s != "audit-logs/signals/active-manifest.jsonl"
                            for s, _ in corrections))
        frags = ow.compile_fragments(self.ZONE, "ent_homeskillet", 683)
        decl = [f for f in frags if f["id"] == "boot.effective_projection"]
        self.assertEqual(len(decl), 1)
        self.assertEqual(decl[0]["pertinence"]["class"], "SUBSTRATE")
        # the signals ray must still render (projection did not withhold it)
        self.assertTrue(any(f["id"] == "tic.signals" for f in frags))


if __name__ == "__main__":
    unittest.main(verbosity=2)
