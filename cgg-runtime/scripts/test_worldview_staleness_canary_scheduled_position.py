#!/usr/bin/env python3
"""Fixtures for the staleness-canary scheduled-position severity split in
office-worldview.py (bk-worldview-staleness-canary-scheduled-position, tic 688).

Ratified cure (/review 687, PROMOTE-as-ray n=2 on
constitution-ledger#presence-observation-fallacy-guard; n=3 live corroboration at
the tic-688 boot): the canary must compare against the producer's SCHEDULED
position. The harmony_invoke / contagion_heartbeat producers RIDE this tic's
mandate, so at boot (pre-mandate) lag==1 is the expected per-tic shape — INFO,
not COUNTER — and the contagion variant's "the heartbeat cycle missed" is a
false causal claim at that position. lag>=2, post-mandate persistence, or an
unresolvable mandate position stay COUNTER (conservative, surface-don't-hide).
Lag surfacing is NEVER removed — every arm still emits the staleness fragment.

Arms (every documented conditional, both sides — cgg-ledger#selftest-fixtures-
must-exercise-documented-conditional-paths):
  1. harmony lag==1 PRE-mandate    — INFO shape: class FIELD, wording names the
                                     scheduled position, no miss assertion
  2. harmony lag==1 POST-mandate   — COUNTER persists (the cycle ran and the
                                     disposition still lags: a genuine miss)
  3. harmony lag>=2 PRE-mandate    — COUNTER (a whole tic was missed regardless
                                     of this tic's mandate state)
  4. contagion lag==1 PRE-mandate  — INFO shape AND the false causal claim
                                     ("the heartbeat cycle missed") absent
  5. contagion lag>=2              — COUNTER with defensible causal wording
                                     ("did not land for its scheduled tic")
  6. unknown position (no mandate) — conservative COUNTER (fail toward loud)
  7. surfacing preserved           — every arm above emits a staleness fragment;
                                     fresh disposition (lag 0) emits none
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

OFFICE = "ent_test"
TIC = 688


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


class StalenessCanaryBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.zone = Path(self.tmp.name)
        # citizen standing so L0 fragments survive _apply_standing_policy
        _write(self.zone / "autonomous_kernel" / "actor-registry.json", {
            "actors": [{"entity_id": OFFICE, "standing": "citizen",
                        "roles": ["interactive_orchestrator"], "status": "active",
                        "entity_kind": "agent"}]})

    def tearDown(self):
        self.tmp.cleanup()

    def _mandate(self, status: str, current_tic: int = TIC,
                 cycles=("harmony_invoke", "contagion_heartbeat")):
        _write(self.zone / "audit-logs" / "mogul" / "mandates" / "current.json", {
            "mandate_id": f"tic-{current_tic}-fixture", "status": status,
            "tic_context": {"current_tic": current_tic},
            "cycle_request": {"run_now": list(cycles)}})

    def _harmony(self, disp_tic: int):
        _write(self.zone / "audit-logs" / "harmony" / "disposition-current.json",
               {"tic": disp_tic, "disposition": {"stance": "steady"}})

    def _contagion(self, ptr_tic: int):
        _write(self.zone / "audit-logs" / "contagion" / "current-pointer.json",
               {"tic": ptr_tic, "one_way_injection": "fixture echo"})

    def _frag(self, fid: str):
        frags = ow.compile_fragments(self.zone, OFFICE, TIC)
        return next((f for f in frags if f["id"] == fid), None)


class HarmonyScheduledPosition(StalenessCanaryBase):
    def test_lag1_pre_mandate_is_info(self):
        """Arm 1: lag==1 while THIS tic's mandate (carrying harmony_invoke) is
        pending — the producer has not reached its scheduled position yet.
        INFO shape: FIELD class, no false-miss assertion."""
        self._harmony(TIC - 1)
        self._mandate("pending")
        f = self._frag("harmony.staleness")
        self.assertIsNotNone(f, "surfacing must never be removed (arm 7)")
        self.assertEqual(f["pertinence"]["class"], "FIELD",
                         "lag==1 pre-mandate is INFO (FIELD), not COUNTER")
        self.assertIn("scheduled position", f["text"] + f["pertinence"]["reason"])

    def test_lag1_post_mandate_is_counter(self):
        """Arm 2: mandate for THIS tic consumed (terminal) and the disposition
        still lags — post-mandate persistence is a genuine miss."""
        self._harmony(TIC - 1)
        self._mandate("consumed")
        f = self._frag("harmony.staleness")
        self.assertIsNotNone(f)
        self.assertEqual(f["pertinence"]["class"], "COUNTER")

    def test_lag1_running_mandate_is_info(self):
        """Arm 1b: 'running' is the real mid-flight status (the lifecycle is
        pending → running → consumed|failed — no 'started'); the obligation is
        still open, so lag==1 stays INFO. Caught live at tic 688: the runner
        stamps 'running', not 'started'."""
        self._harmony(TIC - 1)
        self._mandate("running")
        f = self._frag("harmony.staleness")
        self.assertIsNotNone(f)
        self.assertEqual(f["pertinence"]["class"], "FIELD")

    def test_lag2_pre_mandate_is_counter(self):
        """Arm 3: lag>=2 is a missed tic regardless of this tic's mandate state."""
        self._harmony(TIC - 2)
        self._mandate("pending")
        f = self._frag("harmony.staleness")
        self.assertIsNotNone(f)
        self.assertEqual(f["pertinence"]["class"], "COUNTER")

    def test_no_mandate_is_conservative_counter(self):
        """Arm 6: position unresolvable (no mandate file) — fail toward loud."""
        self._harmony(TIC - 1)
        f = self._frag("harmony.staleness")
        self.assertIsNotNone(f)
        self.assertEqual(f["pertinence"]["class"], "COUNTER")

    def test_fresh_disposition_emits_nothing(self):
        """Arm 7 complement: lag 0 — no staleness fragment."""
        self._harmony(TIC)
        self._mandate("pending")
        self.assertIsNone(self._frag("harmony.staleness"))


class ContagionScheduledPosition(StalenessCanaryBase):
    FALSE_CAUSAL = "the heartbeat cycle missed"

    def test_lag1_pre_mandate_is_info_without_false_causal_claim(self):
        """Arm 4: lag==1 pre-mandate — INFO shape AND the false causal claim
        absent (the cycle has not run yet; asserting it 'missed' is the exact
        presence-observation fallacy the ray names)."""
        self._contagion(TIC - 1)
        self._mandate("pending")
        f = self._frag("contagion.staleness")
        self.assertIsNotNone(f, "surfacing must never be removed (arm 7)")
        self.assertEqual(f["pertinence"]["class"], "FIELD",
                         "lag==1 pre-mandate is INFO (FIELD), not COUNTER")
        self.assertNotIn(self.FALSE_CAUSAL, f["text"],
                         "pre-mandate lag must not assert the cycle missed")

    def test_lag2_is_counter_with_defensible_wording(self):
        """Arm 5: lag>=2 — COUNTER, causal wording scoped to the scheduled tic."""
        self._contagion(TIC - 2)
        self._mandate("pending")
        f = self._frag("contagion.staleness")
        self.assertIsNotNone(f)
        self.assertEqual(f["pertinence"]["class"], "COUNTER")
        self.assertNotIn(self.FALSE_CAUSAL, f["text"],
                         "the blanket miss claim stays retired even at COUNTER")

    def test_lag1_post_mandate_is_counter(self):
        """Arm 2 (contagion side): post-mandate persistence is a genuine miss."""
        self._contagion(TIC - 1)
        self._mandate("consumed")
        f = self._frag("contagion.staleness")
        self.assertIsNotNone(f)
        self.assertEqual(f["pertinence"]["class"], "COUNTER")

    def test_fresh_pointer_emits_nothing(self):
        self._contagion(TIC)
        self._mandate("pending")
        self.assertIsNone(self._frag("contagion.staleness"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
