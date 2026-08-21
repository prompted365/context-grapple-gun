#!/usr/bin/env python3
"""Fixtures for the TYPED LADDER DECLINATION in office-worldview.py (/review 724).

RATIFIED ADJUDICATION (/review 724, closing bk-worldview-ladder-retype-adjudication; parent
doctrine cgg-ledger#boot-attestation-demand-must-be-capability-gated-to-worldview-content,
promoted /review 723): the LADDER explainer is gated on `standing == citizen`, so every
NON-citizen standing — resident, recognized_body, registered_artifact, guest,
task_scoped_worker, and the fail-closed unresolved cell — rendered with ZERO ladder content at
EVERY budget while the sink's explain-back demand ("regenerated from THIS boot's text") stood.
That is SILENT STARVATION: the seat could only fabricate from memory (the copy-forward shape
the drift audit exists to catch) or comply silently-not-at-all — and the corpus could not tell
a seat that was never HANDED the ladder from one that carries it thinly.

The verdict is TYPED DECLINATION NOW (granting the ray to non-citizen classes is DEFERRED and
evidence-gated). So the withheld ray must leave a RECEIPT where it would have stood.

Arms (every documented conditional, both sides — cgg-ledger#selftest-fixtures-must-exercise-
documented-conditional-paths):
  1. citizen             — ladder present, NO declination (the gate is untouched)
  2. every non-citizen   — EXACTLY ONE declination line, ladder absent
  3. budget-exemption    — the declination survives max_chars 0 / 20000 / 2200 / 1 (its
                           absence at a tight seam IS the starvation being cured)
  4. unresolved standing — fail-closed cell renders `standing=unresolved`, never silence
  5. badge parity        — the badge is contract-derived (fragment_contract), never a literal
  6. receipt frame       — non-citizen frame prescribes --ladder-declination and NOT
                           --ladder-explainback; citizen frame is the inverse
  7. EMITTER/READER PAIR — the machine token the render stamps is EXACTLY the reader predicate
                           boot-receipt.py keys its reroute on (the closed consumer set)

Run:  python3 -m unittest test_worldview_ladder_declination   (from cgg-runtime/scripts/)
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

_spec = importlib.util.spec_from_file_location("office_worldview", HERE / "office-worldview.py")
ow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ow)

_bspec = importlib.util.spec_from_file_location("boot_receipt", HERE / "boot-receipt.py")
br = importlib.util.module_from_spec(_bspec)
_bspec.loader.exec_module(br)

OFFICE = "ent_test"
TIC = 724

TOKEN = "typed_declination"
LADDER_HEAD = "THE LADDER · dehydration↔rehydration"

# Every standing the ontology policy knows, minus citizen — the full starved cohort.
NON_CITIZEN = sorted(s for s in ow.STANDING_POLICY if s != "citizen")


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


class DeclinationBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.zone = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _registry(self, standing: str, roles=("queue_state_machine",)):
        _write(self.zone / "autonomous_kernel" / "actor-registry.json", {
            "actors": [{"entity_id": OFFICE, "standing": standing, "roles": list(roles),
                        "status": "active", "entity_kind": "agent"}]})

    def _render(self, standing: str, max_chars: int = 0, roles=("queue_state_machine",)):
        """Full human render for an entity at `standing` — the surface a boot seam prints."""
        self._registry(standing, roles)
        frags = ow.compile_fragments(self.zone, OFFICE, TIC)
        base = ow._office_baseline(self.zone, OFFICE, TIC)
        return ow.render_human(OFFICE, TIC, base, frags, max_chars,
                               zone_root=self.zone, receipt_frame=True)


class CitizenArmUntouched(DeclinationBase):
    """Arm 1 — the citizen gate is NOT retyped by this change. The ladder still lands and
    no declination appears; granting/withholding stays exactly where /review 724 left it."""

    def test_citizen_gets_the_ladder_and_no_declination(self):
        out = self._render("citizen", max_chars=0, roles=("interactive_orchestrator",))
        self.assertIn(LADDER_HEAD, out, "citizen must still receive THE LADDER verbatim")
        self.assertNotIn(TOKEN, out, "a citizen render must carry NO declination")

    def test_citizen_receipt_frame_still_asks_the_explainback(self):
        out = self._render("citizen", max_chars=0, roles=("interactive_orchestrator",))
        self.assertIn("--ladder-explainback", out)
        self.assertNotIn("--ladder-declination", out,
                         "the declination prescription must never reach a citizen frame")


class EveryNonCitizenStandingDeclines(DeclinationBase):
    """Arm 2 — the cure's whole point: no capped standing is silently starved any more."""

    def test_each_non_citizen_standing_emits_exactly_one_declination(self):
        for standing in NON_CITIZEN:
            with self.subTest(standing=standing):
                out = self._render(standing, max_chars=0)
                self.assertNotIn(LADDER_HEAD, out,
                                 "the ladder stays withheld (grant-the-ray is DEFERRED)")
                self.assertEqual(out.count(TOKEN), 1,
                                 "exactly one typed declination — never zero (silent "
                                 "starvation), never duplicated")
                self.assertIn(f"standing={standing}", out,
                              "the declination must NAME the standing it was withheld under")
                self.assertIn("LADDER RAY WITHHELD", out)

    def test_declination_says_the_demand_is_unservable_and_names_the_correct_response(self):
        out = self._render("resident", max_chars=0)
        line = next(ln for ln in out.splitlines() if TOKEN in ln)
        self.assertIn("unservable", line)
        self.assertIn("decline-to-fabricate", line)
        self.assertIn("NOT a missing field", line,
                      "declination must be typed as a first-class state, not an absence")

    def test_declination_is_a_single_line(self):
        """Machine-recognizable means ONE line — a multi-line marker cannot be grepped as a
        unit and can be half-cut into a different-reading ray."""
        for standing in NON_CITIZEN:
            with self.subTest(standing=standing):
                out = self._render(standing, max_chars=0)
                hits = [ln for ln in out.splitlines() if TOKEN in ln and "LADDER RAY WITHHELD" in ln]
                self.assertEqual(len(hits), 1)


class BudgetExemption(DeclinationBase):
    """Arm 3 — budget-exempt by construction. The absence of this line at a tight seam is
    PRECISELY the silent starvation being cured, so no budget may cut it (the live citizen
    seam runs --max-chars 2200; max_chars=1 is the degenerate lower bound)."""

    def test_declination_survives_every_budget(self):
        for standing in NON_CITIZEN:
            for max_chars in (0, 20000, 2200, 1):
                with self.subTest(standing=standing, max_chars=max_chars):
                    out = self._render(standing, max_chars=max_chars)
                    self.assertEqual(out.count(TOKEN), 1,
                                     f"declination sealed at --max-chars {max_chars}")

    def test_declination_is_not_swept_into_the_render_bound_manifest(self):
        """The declination is appended AFTER the body is bounded, so it can never appear in
        the RENDER-BOUND omitted-ray manifest (that would re-type it as budget-omitted)."""
        out = self._render("resident", max_chars=1)
        marker = [ln for ln in out.splitlines() if "RENDER-BOUND" in ln]
        for ln in marker:
            self.assertNotIn(TOKEN, ln)


class FailClosedCell(DeclinationBase):
    """Arm 4 — an unresolvable standing must still DECLINE. Fail-closed has always meant
    non-citizen; it must now also mean legible, never silent."""

    def test_missing_registry_declines_as_task_scoped_worker(self):
        # no actor-registry.json at all -> _entity_standing's fail-closed default
        frags = ow.compile_fragments(self.zone, OFFICE, TIC)
        out = ow.render_human(OFFICE, TIC, {}, frags, 0, zone_root=self.zone, receipt_frame=True)
        self.assertIn(TOKEN, out)
        self.assertIn("standing=task_scoped_worker", out)

    def test_no_zone_root_declines_as_unresolved(self):
        """zone_root=None cannot resolve a standing; the arm must still decline, naming the
        unresolved cell rather than rendering a hole."""
        self._registry("resident")
        frags = ow.compile_fragments(self.zone, OFFICE, TIC)
        out = ow.render_human(OFFICE, TIC, {}, frags, 0, zone_root=None, receipt_frame=True)
        self.assertIn(TOKEN, out)
        self.assertIn("standing=unresolved", out)


class BadgeIsContractDerived(DeclinationBase):
    """Arm 5 — the badge comes from the shared fragment contract, so it can never drift from
    AUTHORITY_DEFAULTS (the same discipline that binds every other badge-bearing ray)."""

    def test_badge_matches_the_substrate_class_ceiling(self):
        line = ow.render_ladder_declination("resident")
        expected = ow._badge("SUBSTRATE", ow.AUTHORITY_DEFAULTS["SUBSTRATE"])
        self.assertIn(expected, line)
        self.assertIn("⟨SUBSTRATE·shape-only⟩", line,
                      "SUBSTRATE is shape-only: the declination is a boundary to honor, "
                      "not an action it authorizes")


class ReceiptFramePairing(DeclinationBase):
    """Arm 6 — the frame is the reader-facing half of the emitter/reader pair: the render
    declines, and the frame tells the seat exactly how to RECORD the declination."""

    def test_non_citizen_frame_prescribes_the_declination_flag(self):
        for standing in NON_CITIZEN:
            with self.subTest(standing=standing):
                out = self._render(standing, max_chars=0)
                self.assertIn("--ladder-declination", out)
                self.assertIn(f'--ladder-declination "standing={standing} render carried no '
                              'ladder content"', out,
                              "the prescribed command must be copy-runnable, standing filled in")
                self.assertNotIn("--ladder-explainback", out,
                                 "never demand an attestation this render cannot ground")
                self.assertIn("· ladder_declination", out, "the owed line must name the state")
                self.assertIn("DO NOT FABRICATE ONE", out)

    def test_frame_without_either_arm_is_unchanged(self):
        """Backward compat: the default (no ladder, no declination) frame carries neither
        prescription — the pre-724 shape for any caller that passes neither."""
        frame = ow.render_receipt_frame(OFFICE, TIC, OFFICE, self.zone)
        self.assertNotIn("--ladder-explainback", frame)
        self.assertNotIn("--ladder-declination", frame)
        self.assertNotIn("ladder_declination", frame)


class EmitterReaderTokenParity(DeclinationBase):
    """Arm 7 — THE closed consumer set. The render is the EMITTER; boot-receipt.py is the
    READER. If the token drifts on either side the reroute goes dark silently, which is the
    failure class this whole fix belongs to (emitter rows must match the reader predicate)."""

    def test_render_token_is_exactly_the_sink_reader_predicate(self):
        self.assertEqual(TOKEN, br._LADDER_DECLINATION_TOKEN)
        self.assertIn(br._LADDER_DECLINATION_TOKEN, ow.render_ladder_declination("resident"))

    def test_sink_reroutes_the_rendered_line_verbatim(self):
        """An agent that pastes the render's withheld-ray line into --ladder-explainback is
        rerouted, not filed into the drift corpus as a fabricated explain-back."""
        line = ow.render_ladder_declination("recognized_body")
        self.assertIn(br._LADDER_DECLINATION_TOKEN, line)
        parsed = br.parse_ladder_declination(line)
        self.assertTrue(parsed["ladder_explainback_declined"])
        self.assertEqual(parsed["ladder_declination_standing"], "recognized_body",
                         "the sink must recover the standing straight out of the rendered line")


if __name__ == "__main__":
    unittest.main(verbosity=2)
