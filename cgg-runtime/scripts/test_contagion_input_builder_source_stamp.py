#!/usr/bin/env python3
"""test_contagion_input_builder_source_stamp.py — as-of stamp fixtures.

Fix-site: the contagion disposition packet's `currentShapeProvenance` carried
the conformation's TRANSCRIBED figures (pending_cogprs, active_signals,
manifold_state, byte counts) but dropped the conformation's `snapshot_at`, and
the packet carried no timestamp anywhere. Measured defect (tic 721): a
33-minute-stale conformation read drove `pending_pressure` to 0.6667 when live
truth was 1.0, and nothing in the artifact let its own reader detect the
staleness.

Ratified law (/review 724): a provenance block that transcribes measured values
across a boundary must carry the SOURCE's as-of stamp — the volatility
obligation travels with the transcription.

Both stamps live INSIDE the provenance block by construction, not at envelope
top level: `contagion-engine.mjs` destructures a fixed key set and forwards
ONLY `shapeProvenance` verbatim (as `currentShapeProvenance`), so that block is
the sole builder->disposition channel that survives without a kernel-rung
change. The placement test below is the guard on that structural fact.

Root-pinned before import per Self-Locating Artifact Test Isolation — the
builder resolves its zone root at module scope, so an unpinned import would
aim fixtures at the real zone.
"""

import atexit
import datetime
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent

# Root-pin BEFORE the module is loaded: resolve_zone_root() runs at import.
_PIN = tempfile.mkdtemp(prefix="cib-zone-")
atexit.register(shutil.rmtree, _PIN, True)
Path(_PIN, ".ticzone").write_text(json.dumps({"name": "test-zone"}))
os.environ["CLAUDE_PROJECT_DIR"] = _PIN


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cib = _load("contagion_input_builder", _HERE / "contagion-input-builder.py")

# Shaped like a live conformation, trimmed to the fields the builder reads.
CONF = {
    "type": "conformation",
    "tic_count_physical": 724,
    "tic": "2026-08-21T20:47:19Z",
    "snapshot_at": "2026-08-21T20:47:19.783590+00:00",
    "active_signals": [{"id": "sig_some_drift_thing"}],
    "counts": {"active_signals": 56, "active_warrants": 0, "pending_cogprs": 10},
    "rules_in_force": {"site": {"bytes": 39878}, "global": {"bytes": 13017}},
    "governance_query_enrichment": {"manifold_state": "ACTIVE", "estate_profile": "hazard"},
    "posture": "OPS/DIRECT",
}


class SourceStampTravelsWithTheTranscription(unittest.TestCase):
    def test_source_snapshot_at_copied_from_conformation(self):
        """THE defect: derived_from copied the figures and dropped the stamp."""
        _, prov = cib.conformation_shape(CONF)
        self.assertEqual(
            prov["derived_from"]["source_snapshot_at"],
            "2026-08-21T20:47:19.783590+00:00",
        )

    def test_stamp_rides_inside_derived_from_beside_the_figures(self):
        """The obligation belongs to the transcription, so the stamp sits in the
        same block as the values it dates — not loose elsewhere."""
        _, prov = cib.conformation_shape(CONF)
        df = prov["derived_from"]
        self.assertIn("source_snapshot_at", df)
        self.assertEqual(df["pending_cogprs"], 10)

    def test_falls_back_to_tic_when_snapshot_at_absent(self):
        """32 of 703 conformations predate snapshot_at; `tic` is the coarser
        ISO fallback rather than no stamp at all."""
        conf = dict(CONF)
        conf.pop("snapshot_at")
        _, prov = cib.conformation_shape(conf)
        self.assertEqual(prov["derived_from"]["source_snapshot_at"], "2026-08-21T20:47:19Z")

    def test_absent_source_stamp_reports_none_never_synthesized(self):
        """An unstamped source is reported as unstamped. Substituting the read's
        own clock would launder a stale read as fresh — the exact failure."""
        conf = dict(CONF)
        conf.pop("snapshot_at")
        conf.pop("tic")
        _, prov = cib.conformation_shape(conf)
        self.assertIsNone(prov["derived_from"]["source_snapshot_at"])


class PacketStampsItsOwnBuildTime(unittest.TestCase):
    def test_built_at_is_parseable_iso8601_utc(self):
        _, prov = cib.conformation_shape(CONF)
        parsed = datetime.datetime.fromisoformat(prov["built_at"])
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(parsed.utcoffset(), datetime.timedelta(0))

    def test_staleness_is_a_computable_delta_for_the_reader(self):
        """The falsifiability property: with both stamps present a reader can
        subtract them. Pre-fix this was impossible — no timestamp anywhere."""
        _, prov = cib.conformation_shape(CONF)
        built = datetime.datetime.fromisoformat(prov["built_at"])
        source = datetime.datetime.fromisoformat(prov["derived_from"]["source_snapshot_at"])
        self.assertGreaterEqual((built - source).total_seconds(), 0)


class AdditiveOnlyAndConsumerSafe(unittest.TestCase):
    def test_preexisting_provenance_keys_survive_unrenamed(self):
        """Downstream consumers exist (the contagion heartbeat engine reads the
        forwarded block); the patch adds fields and renames/removes none."""
        _, prov = cib.conformation_shape(CONF)
        for key in ("dims", "schema", "values", "derived_from", "note"):
            self.assertIn(key, prov)
        for key in ("active_signals", "failure_shaped_signals", "manifold_state",
                    "estate_profile", "pending_cogprs", "site_bytes", "global_bytes"):
            self.assertIn(key, prov["derived_from"])

    def test_vector_is_untouched_by_the_stamps(self):
        """Stamps are provenance, never inputs — no new axis enters the match."""
        vec, prov = cib.conformation_shape(CONF)
        self.assertEqual(len(vec), cib.N_DIMS)
        self.assertEqual(set(prov["values"]), set(cib.STRUCT_DIMS))

    def test_stamps_land_in_the_engine_forwarded_block_not_top_level(self):
        """Structural guard: contagion-engine.mjs forwards ONLY shapeProvenance
        (as currentShapeProvenance). A stamp at envelope top level would be
        silently dropped and never reach the disposition packet."""
        with tempfile.TemporaryDirectory() as td:
            zone = Path(td)
            conf_dir = zone / "audit-logs" / "conformations"
            conf_dir.mkdir(parents=True)
            (conf_dir / "tic-724.json").write_text(json.dumps(CONF))
            out_dir = zone / "audit-logs" / "contagion"

            orig = (cib.ROOT, cib.CONFORMATION_DIR, cib.CONTAGION_DIR)
            cib.ROOT, cib.CONFORMATION_DIR, cib.CONTAGION_DIR = (
                str(zone), str(conf_dir), str(out_dir))
            try:
                envelope = json.loads(Path(cib.build()).read_text())
            finally:
                cib.ROOT, cib.CONFORMATION_DIR, cib.CONTAGION_DIR = orig

        prov = envelope["shapeProvenance"]
        self.assertIn("built_at", prov)
        self.assertIn("source_snapshot_at", prov["derived_from"])
        self.assertNotIn("built_at", envelope)
        self.assertNotIn("source_snapshot_at", envelope)


if __name__ == "__main__":
    unittest.main(verbosity=2)
