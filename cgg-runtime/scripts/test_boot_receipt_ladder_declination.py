#!/usr/bin/env python3
"""Tests for the TYPED LADDER DECLINATION sink path in boot-receipt.py (/review 724).

RATIFIED ADJUDICATION (/review 724, closing bk-worldview-ladder-retype-adjudication; parent
doctrine cgg-ledger#boot-attestation-demand-must-be-capability-gated-to-worldview-content,
promoted /review 723): this sink demanded a ladder explain-back "regenerated from THIS boot's
text" from every entity class, while office-worldview.py citizen-gates the LADDER block. A
non-citizen standing therefore booted with ZERO ladder content at ANY budget and could only
fabricate or comply silently-not-at-all — both INVISIBLE in the corpus.

The cure makes DECLINE-TO-FABRICATE a first-class, corpus-visible receipt state:
  * NEVER a missing field  — the ladder was never in _OWED_FIELDS and stays out
  * NEVER a gate input     — boot_read_passes() cannot see it, in either direction
  * NEVER equal to absence — ack, stdout envelope, and stored record all distinguish
                             declined from simply-omitted
  * FULLY backward compatible — a receipt WITHOUT a declination hashes byte-identically to
                             the pre-724 algorithm, so every historical receipt_id stays valid

Arms (every documented conditional, both sides — cgg-ledger#selftest-fixtures-must-exercise-
documented-conditional-paths):
  1. parse            — standing extracted when present; ABSENT (not fabricated) when not
  2. fingerprint      — civic-only + explain-back digests unchanged; declination participates;
                        a CORRECTED declination mints a distinct id (lands beside, not dedup)
  3. owed fields      — a declination never appears in receipt_missing()
  4. gate neutrality  — boot_read_passes() identical with and without the declination
  5. reroute          — an --ladder-explainback carrying the render's machine token reroutes
  6. round-trip       — a real `emit` against an ISOLATION --sink records the state, and a
                        plain emit's stdout envelope carries NO declination keys (byte-compat)

Isolation: every subprocess arm passes --sink (flag-only by design — see sink_path()), so no
test ever writes the live boot-receipts.jsonl.

Run:  python3 -m unittest test_boot_receipt_ladder_declination   (from cgg-runtime/scripts/)
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("boot_receipt", HERE / "boot-receipt.py")
br = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(br)

SCRIPT = str(HERE / "boot-receipt.py")

CIVIC = {
    "understood_scope": "u",
    "accepted_constraints": ["c"],
    "abstentions": ["a"],
    "first_action_or_escalation": "f",
}


def _pre724_fingerprint(rec: dict) -> str:
    """The pre-724 algorithm, transcribed — the byte-compat oracle. (Civic layer + the tic-643
    attestation layer + the A7-644 explain-back layer; NO declination layer.) Any drift in the
    civic/attestation/explainback digest against this would invalidate historical receipt_ids."""
    sem = {
        "understood_scope": rec.get("understood_scope", ""),
        "accepted_constraints": sorted(rec.get("accepted_constraints", [])),
        "abstentions": sorted(rec.get("abstentions", [])),
        "first_action_or_escalation": rec.get("first_action_or_escalation", ""),
    }
    attest = {k: br._fp_norm(rec[k]) for k in br._FINGERPRINT_ATTESTATION_FIELDS if k in rec}
    if attest:
        sem["boot_read_attestation"] = attest
    if "ladder_explainback" in rec:
        sem["ladder_explainback"] = rec["ladder_explainback"]
    blob = json.dumps(sem, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ParseDeclination(unittest.TestCase):
    """Arm 1 — the parse is an ADDITIVE index over the verbatim reason, never a replacement."""

    def test_standing_extracted_from_the_rendered_form(self):
        d = br.parse_ladder_declination("standing=resident render carried no ladder content")
        self.assertTrue(d["ladder_explainback_declined"])
        self.assertEqual(d["ladder_declination_standing"], "resident")
        self.assertEqual(d["ladder_declination_reason"],
                         "standing=resident render carried no ladder content",
                         "the raw reason is preserved verbatim")

    def test_standing_absent_is_absent_not_fabricated(self):
        d = br.parse_ladder_declination("the render carried no ladder content")
        self.assertTrue(d["ladder_explainback_declined"])
        self.assertNotIn("ladder_declination_standing", d,
                         "fail-soft: never invent a standing the reason did not carry")

    def test_every_ontology_standing_parses(self):
        for s in ("citizen", "resident", "recognized_body", "registered_artifact",
                  "guest", "task_scoped_worker", "unresolved"):
            with self.subTest(standing=s):
                d = br.parse_ladder_declination(f"standing={s} render carried no ladder content")
                self.assertEqual(d["ladder_declination_standing"], s)


class FingerprintLayering(unittest.TestCase):
    """Arm 2 — presence-keyed and additive, exactly like the tic-643 attestation layer."""

    def test_civic_only_digest_is_byte_identical_to_pre724(self):
        rec = dict(CIVIC)
        self.assertEqual(br.content_fingerprint(rec), _pre724_fingerprint(rec))

    def test_explainback_digest_is_byte_identical_to_pre724(self):
        rec = dict(CIVIC, ladder_explainback="One. Two. Three. Four. Five.",
                   full_boot_injection_read=True, boot_read_mode="full", chunking="gapless",
                   required_unread_ranges=[])
        self.assertEqual(br.content_fingerprint(rec), _pre724_fingerprint(rec))

    def test_declination_participates(self):
        base = dict(CIVIC)
        declined = dict(CIVIC, **br.parse_ladder_declination("standing=resident no ladder"))
        self.assertNotEqual(br.content_fingerprint(base), br.content_fingerprint(declined),
                            "a declination must be semantically distinguishable from silence")

    def test_corrected_declination_mints_a_distinct_id(self):
        """The tic-643 defect on the declination axis: a corrected/widened declination must
        LAND BESIDE the first, never dedup-vanish."""
        a = dict(CIVIC, **br.parse_ladder_declination("standing=resident no ladder"))
        b = dict(CIVIC, **br.parse_ladder_declination("standing=recognized_body no ladder"))
        ida = br.receipt_id("ent_x", 724, br.content_fingerprint(a))
        idb = br.receipt_id("ent_x", 724, br.content_fingerprint(b))
        self.assertNotEqual(ida, idb)

    def test_identical_declination_dedups(self):
        a = dict(CIVIC, **br.parse_ladder_declination("standing=resident no ladder"))
        b = dict(CIVIC, **br.parse_ladder_declination("standing=resident no ladder"))
        self.assertEqual(br.receipt_id("ent_x", 724, br.content_fingerprint(a)),
                         br.receipt_id("ent_x", 724, br.content_fingerprint(b)))


class NeverAMissingField(unittest.TestCase):
    """Arm 3 — the whole point of "typed declination, not silent starvation" is that declining
    is CORRECT behavior. It must never read as an incomplete receipt."""

    def test_declination_is_not_in_the_owed_civic_set(self):
        self.assertNotIn("ladder_explainback_declined", br._OWED_FIELDS)
        self.assertNotIn("ladder_explainback", br._OWED_FIELDS)

    def test_complete_civic_receipt_with_declination_reports_no_missing(self):
        rec = dict(CIVIC, **br.parse_ladder_declination("standing=resident no ladder"))
        self.assertEqual(br.receipt_missing(rec), [])

    def test_declination_does_not_mask_a_genuinely_incomplete_receipt(self):
        rec = dict(CIVIC, understood_scope="", **br.parse_ladder_declination("standing=guest x"))
        self.assertEqual(br.receipt_missing(rec), ["understood_scope"])


class GateNeutrality(unittest.TestCase):
    """Arm 4 — BOTH directions. The declination can neither unblock a failing attestation nor
    block a passing one; the ladder was never a mutation-gate input and still is not."""

    def _attest(self, **over):
        rec = dict(CIVIC, full_boot_injection_read=True, boot_read_mode="full",
                   chunking="gapless", required_unread_ranges=[])
        rec.update(over)
        return rec

    def test_passing_attestation_still_passes_with_a_declination(self):
        clean = self._attest()
        declined = self._attest(**br.parse_ladder_declination("standing=resident no ladder"))
        self.assertEqual(br.boot_read_passes(clean), br.boot_read_passes(declined))
        self.assertTrue(br.boot_read_passes(declined)[0])

    def test_failing_attestation_still_fails_with_a_declination(self):
        bad = self._attest(required_unread_ranges=["section 5 unread"])
        bad_declined = self._attest(required_unread_ranges=["section 5 unread"],
                                    **br.parse_ladder_declination("standing=resident no ladder"))
        self.assertEqual(br.boot_read_passes(bad), br.boot_read_passes(bad_declined))
        self.assertFalse(br.boot_read_passes(bad_declined)[0])


class SinkRoundTrip(unittest.TestCase):
    """Arms 5 + 6 — real `emit` invocations against an ISOLATION sink (--sink is flag-only by
    design, so the live ledger is never touched)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sink = Path(self.tmp.name) / "receipts.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _emit(self, entity, *extra):
        cmd = [sys.executable, SCRIPT, "emit", "--sink", str(self.sink),
               "--entity", entity, "--tic", "9724",
               "--understood", "u", "--constraint", "c", "--abstention", "a",
               "--first-action", "f", "--route", "cadence/review", "--model", "m",
               "--full-boot-read", "--boot-read-mode", "full", "--chunking", "gapless",
               *extra]
        p = subprocess.run(cmd, capture_output=True, text=True)
        return p, (json.loads(p.stdout) if p.stdout.strip() else None)

    def _rows(self):
        return [json.loads(l) for l in self.sink.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_declination_round_trip(self):
        p, out = self._emit("ent_cpr_stepper",
                            "--ladder-declination", "standing=resident render carried no ladder content")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(out["status"], "recorded")
        self.assertIs(out["ladder_explainback_declined"], True)
        self.assertEqual(out["ladder_declination_standing"], "resident")
        self.assertFalse(out["ladder_explainback_recorded"])
        self.assertEqual(out["missing_fields"], [], "declining is never an incomplete receipt")
        # the ack must NOT be the plain no-explainback nudge
        self.assertIn("DECLINED (typed) and RECORDED", out["ack"])
        self.assertNotIn("the crux drift-audit wants your 5 sentences", out["ack"])
        row = self._rows()[0]
        self.assertTrue(row["ladder_explainback_declined"])
        self.assertEqual(row["ladder_declination_standing"], "resident")
        self.assertNotIn("ladder_explainback", row,
                         "a declination must never masquerade as an explain-back entry")

    def test_plain_and_explainback_envelopes_carry_no_declination_keys(self):
        """Backward compat on the stdout envelope: the new keys are presence-keyed, so an
        existing caller's parsed output is unchanged."""
        for entity, extra in (("ent_plain", ()),
                              ("ent_lb", ("--ladder-explainback", "One. Two. Three. Four. Five."))):
            with self.subTest(entity=entity):
                _, out = self._emit(entity, *extra)
                self.assertNotIn("ladder_explainback_declined", out)
                self.assertNotIn("ladder_declination_standing", out)
                self.assertNotIn("ladder_declination_reason", out)

    def test_plain_emit_keeps_the_no_explainback_nudge(self):
        _, out = self._emit("ent_plain")
        self.assertIn("no --ladder-explainback this tic", out["ack"],
                      "the ABSENT arm must be untouched — declined and absent stay distinct")

    def test_corrected_declination_lands_beside_the_first(self):
        _, a = self._emit("ent_x", "--ladder-declination", "standing=resident no ladder")
        _, dup = self._emit("ent_x", "--ladder-declination", "standing=resident no ladder")
        _, b = self._emit("ent_x", "--ladder-declination", "standing=recognized_body no ladder")
        self.assertEqual(dup["status"], "deduped")
        self.assertEqual(dup["receipt_id"], a["receipt_id"])
        self.assertEqual(b["status"], "recorded")
        self.assertNotEqual(b["receipt_id"], a["receipt_id"])
        self.assertEqual(len(self._rows()), 2)

    def test_rendered_line_pasted_into_explainback_is_rerouted_loudly(self):
        """Arm 5 — keyed on the EXACT machine token the render stamps, never fuzzy prose."""
        line = ("[LADDER RAY WITHHELD · standing=recognized_body · typed_declination] this "
                "render carries no ladder-explainer content by standing-gate.")
        p, out = self._emit("ent_unit_narrative_media", "--ladder-explainback", line)
        self.assertIn("REROUTED to --ladder-declination", p.stderr)
        self.assertIs(out["ladder_explainback_declined"], True)
        self.assertEqual(out["ladder_declination_standing"], "recognized_body")
        self.assertFalse(out["ladder_explainback_recorded"])
        self.assertNotIn("ladder_explainback", self._rows()[0],
                         "the withheld-ray line must NOT be filed into the drift-audit corpus")

    def test_genuine_explainback_is_not_rerouted(self):
        """The reroute must not over-fire: a real five-sentence explain-back has no machine
        token and stays an explain-back."""
        _, out = self._emit("ent_mogul", "--ladder-explainback",
                            "The ladder has two lanes. Dehydration compresses to a centroid. "
                            "Rehydration re-applies it. Judgment travels. Semantics stay home.")
        self.assertTrue(out["ladder_explainback_recorded"])
        self.assertNotIn("ladder_explainback_declined", out)
        self.assertIn("ladder_explainback", self._rows()[0])

    def test_both_flags_are_refused_as_a_usage_error(self):
        """You cannot both ground the crux from this boot's text and declare it carried none."""
        p, _ = self._emit("ent_x", "--ladder-explainback", "One. Two. Three. Four. Five.",
                          "--ladder-declination", "standing=resident no ladder")
        self.assertEqual(p.returncode, 2, "argparse usage error, not a silent both-states record")
        self.assertIn("not allowed with argument", p.stderr)

    def test_payload_explainback_outranks_a_declination(self):
        """The payload form of the same conflict: a GROUNDED explain-back wins and the
        declination is dropped LOUDLY — never a record claiming both."""
        payload = Path(self.tmp.name) / "p.json"
        payload.write_text(json.dumps(dict(CIVIC, ladder_explainback="A. B. C. D. E.")),
                           encoding="utf-8")
        p = subprocess.run(
            [sys.executable, SCRIPT, "emit", "--sink", str(self.sink), "--entity", "ent_x",
             "--tic", "9724", "--payload", str(payload),
             "--ladder-declination", "standing=resident no ladder"],
            capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertIn("The declination is DROPPED", p.stderr)
        row = self._rows()[0]
        self.assertIn("ladder_explainback", row)
        self.assertNotIn("ladder_explainback_declined", row)

    def test_gate_check_allows_on_a_declination_receipt(self):
        """End-to-end gate neutrality: a declining seat with a clean boot-read attestation is
        still allowed to mutate — declining the ladder is not perception debt."""
        self._emit("ent_cpr_stepper", "--ladder-declination", "standing=resident no ladder")
        p = subprocess.run([sys.executable, SCRIPT, "gate-check", "--sink", str(self.sink),
                            "--entity", "ent_cpr_stepper", "--tic", "9724"],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0)
        self.assertTrue(json.loads(p.stdout)["allow"])
        self.assertEqual(json.loads(p.stdout)["via"], "boot_read_receipt")


if __name__ == "__main__":
    unittest.main(verbosity=2)
