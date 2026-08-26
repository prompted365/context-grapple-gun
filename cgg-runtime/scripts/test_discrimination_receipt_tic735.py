#!/usr/bin/env python3
"""test_discrimination_receipt_tic735.py — teeth for the emit-side discrimination
receipt (build of backlog `bk-harmony-discrimination-receipt`, ratified at
/review 733 as the discrimination-axis ray on
`ledger.md#can-it-eat-dataflow-liveness-predicate`).

    ⟜ RIDER — reproduced verbatim ⟜
    "no harmony/contagion disposition may be READ as discriminating until built
     AND ruled — your build is the first half; the ruling comes later at /review"
    "Standing rule carried forward: do not read harmony/contagion dispositions
     as discriminating until the receipt fields exist and the A3-732 cause is
     ruled."

The arms:
  1. RATIFIED-FIGURE REGRESSION — the receipt reproduces the /review-733
     measurement from the REAL corpora as they stood at tic 730: harmony
     139 identical emissions over tics 591..730 (prior differing emission at
     590), contagion 185/185 across its entire recorded history 443..730 with
     no change ever. If a future edit silently windows the scan, these fail.
  2. FULL HISTORY, NEVER A WINDOW — the scan denominator equals the corpus.
  3. ADDITIVE-ONLY — stamping adds exactly one top-level key and mutates no
     pre-existing value (the emit-side contract that keeps every consumer
     parsing unchanged).
  4. RIDER TRAVELS — the verbatim rider + `ratified: false` ride INSIDE the
     emitted block, where a reader of the artifact will meet them.
  5. DECLARED, NOT INVENTED — the discriminating condition is extracted live
     from the engines' own deciding code, sha-stamped, and drift-loud.
  6. NEGATIVE CONTROL — a changed value resets the counter.
  7. WIRING — both invoke scripts call the receipt step, fail-soft, and carry
     the rider beside the call.
  8. EMIT-SIDE ONLY — the build touches no consumer.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MODULE = _HERE / "discrimination-receipt.py"
_HARMONY_SH = _HERE / "harmony-invoke.sh"
_CONTAGION_SH = _HERE / "contagion-invoke.sh"

_SPEC = importlib.util.spec_from_file_location("discrimination_receipt", _MODULE)
dr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dr)

_REPO = Path("/Users/breydentaylor/canonical")
_HARMONY_DIR = _REPO / "audit-logs" / "harmony"
_CONTAGION_DIR = _REPO / "audit-logs" / "contagion"

# The /review-733 ratified measurement, quoted from the ledger ray:
#   "the harmony kernel consumed 139/139 fully-DISTINCT input payloads over tics
#    591–730 ... and emitted exactly ONE stance and ONE meaningState for all 139
#    tics, last change at tic 590; the contagion kernel consumed 185/185
#    distinct payloads across its ENTIRE recorded history (tics 443–730) and
#    produced meaning_state 'resonant' 185/185 times."
RATIFIED_AS_OF_TIC = 730
RATIFIED_HARMONY_COUNT = 139
RATIFIED_HARMONY_SPAN = [591, 730]
RATIFIED_HARMONY_PREV_DISTINCT_TIC = 590
RATIFIED_CONTAGION_COUNT = 185
RATIFIED_CONTAGION_SPAN = [443, 730]


class RatifiedFigureRegression(unittest.TestCase):
    """Arm 1 — the ratified constancy figures are reproducible from disk."""

    @unittest.skipUnless(_HARMONY_DIR.is_dir(), "live harmony corpus absent")
    def test_harmony_reproduces_139_over_591_730(self):
        b = dr.build_receipt("harmony", _REPO, as_of_tic=RATIFIED_AS_OF_TIC)
        self.assertEqual(b["consecutive_identical_count"], RATIFIED_HARMONY_COUNT)
        self.assertEqual(b["identical_run_tic_span"], RATIFIED_HARMONY_SPAN)
        self.assertEqual(b["previous_distinct_tic"], RATIFIED_HARMONY_PREV_DISTINCT_TIC)
        self.assertEqual(b["last_change_tic"], 591)
        self.assertFalse(b["never_changed_in_retained_history"])

    @unittest.skipUnless(_CONTAGION_DIR.is_dir(), "live contagion corpus absent")
    def test_contagion_reproduces_185_never_discriminated(self):
        b = dr.build_receipt("contagion", _REPO, as_of_tic=RATIFIED_AS_OF_TIC)
        self.assertEqual(b["consecutive_identical_count"], RATIFIED_CONTAGION_COUNT)
        self.assertEqual(b["identical_run_tic_span"], RATIFIED_CONTAGION_SPAN)
        self.assertTrue(b["never_changed_in_retained_history"])
        self.assertIsNone(b["last_change_tic"])
        self.assertEqual(b["tracked_value"], {"meaningState": "resonant"})
        self.assertEqual(b["distinct_tracked_values_in_retained_history"], 1)


class FullHistoryNeverAWindow(unittest.TestCase):
    """Arm 2 — the denominator is the corpus, not a cap."""

    @unittest.skipUnless(_HARMONY_DIR.is_dir(), "live harmony corpus absent")
    def test_scan_denominator_equals_corpus_size(self):
        b = dr.build_receipt("harmony", _REPO, as_of_tic=RATIFIED_AS_OF_TIC)
        on_disk = sum(
            1 for p in _HARMONY_DIR.glob("disposition-tic-*.json")
            if dr.ARTIFACT_RE.match(p.name)
            and int(dr.ARTIFACT_RE.match(p.name).group(1)) <= RATIFIED_AS_OF_TIC
        )
        self.assertEqual(b["history_scanned"]["artifacts_scanned"], on_disk)
        self.assertIsNone(b["history_scanned"]["window"])

    def test_two_hundred_run_is_not_capped(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "audit-logs" / "contagion"
            d.mkdir(parents=True)
            for t in range(1, 201):
                (d / f"disposition-tic-{t}.json").write_text(json.dumps({"meaningState": "resonant"}))
            b = dr.build_receipt("contagion", root)
            self.assertEqual(b["consecutive_identical_count"], 200)


class AdditiveOnly(unittest.TestCase):
    """Arm 3 — stamping is purely additive; consumers parse unchanged."""

    def test_stamp_adds_exactly_one_key_and_mutates_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "audit-logs" / "contagion"
            d.mkdir(parents=True)
            payload = {
                "type": "contagion.match.disposition",
                "meaningState": "resonant",
                "disposition": {"stance": "s", "unresolvedDissonance": ["a", "b"]},
                "non_citable": True,
                "meta": {"pure": True, "writes": False},
            }
            for t in (10, 11):
                (d / f"disposition-tic-{t}.json").write_text(json.dumps(payload))
            target = d / "disposition-tic-11.json"
            before = json.loads(target.read_text())
            dr.stamp("contagion", target, root)
            after = json.loads(target.read_text())
            self.assertEqual(set(after) - set(before), {"discrimination_receipt"})
            for k, v in before.items():
                self.assertEqual(after[k], v, f"pre-existing key {k} mutated")

    def test_stamp_is_idempotent_in_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "audit-logs" / "harmony"
            d.mkdir(parents=True)
            doc = {"meaningState": "strained", "disposition": {"stance": "x"}}
            for t in (10, 11):
                (d / f"disposition-tic-{t}.json").write_text(json.dumps(doc))
            target = d / "disposition-tic-11.json"
            first = dr.stamp("harmony", target, root)
            second = dr.stamp("harmony", target, root)
            self.assertEqual(first["consecutive_identical_count"],
                             second["consecutive_identical_count"])
            self.assertEqual(set(json.loads(target.read_text())) - {"meaningState", "disposition"},
                             {"discrimination_receipt"})


class RiderTravels(unittest.TestCase):
    """Arm 4 — the withheld thing is said out loud, inside the artifact."""

    def _block(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "audit-logs" / "contagion"
            d.mkdir(parents=True)
            (d / "disposition-tic-10.json").write_text(json.dumps({"meaningState": "resonant"}))
            return dr.build_receipt("contagion", root)

    def test_ratified_bit_is_true_read_half_ruled_736(self):
        # /review 736 ruled the read half LIVE (Architect-ratified in-tic
        # question set, recommended option verbatim). The flip IS the ruling.
        b = self._block()
        self.assertIs(b["ratified"], True)
        self.assertIn("/review 736", b["ratified_by"])

    def test_rider_is_verbatim(self):
        b = self._block()
        self.assertEqual(b["rider"], dr.RIDER_VERBATIM)
        self.assertEqual(b["standing_rule"], dr.STANDING_RULE_VERBATIM)
        # the pre-ruling rider stays banked verbatim for lineage — the ruling
        # supersedes it, it never erases it.
        self.assertEqual(
            b["pre_ruling_rider"],
            "no harmony/contagion disposition may be READ as discriminating until built "
            "AND ruled — your build is the first half; the ruling comes later at /review",
        )

    def test_block_disclaims_diagnosis_of_the_cause(self):
        b = self._block()
        self.assertIn("does NOT diagnose", b["does_not_diagnose"])
        self.assertIn("A3-732", b["does_not_diagnose"])

    def test_rider_rides_both_invoke_scripts_verbatim_and_unwrapped(self):
        # verbatim + on ONE line, so the rider survives a grep and can never be
        # read as a half-sentence.
        for path in (_HARMONY_SH, _CONTAGION_SH):
            text = path.read_text()
            self.assertIn(dr.RIDER_VERBATIM, text, f"rider missing/wrapped in {path.name}")
            self.assertIn(dr.STANDING_RULE_VERBATIM, text,
                          f"standing rule missing/wrapped in {path.name}")

    def test_rider_rides_the_module_constant(self):
        # the RULED rider: readable receipt, non-citable values, unruled cause.
        self.assertIn("READABLE as constancy observability", dr.RIDER_VERBATIM)
        self.assertIn("NON-CITABLE", dr.RIDER_VERBATIM)
        self.assertIn("A3-732", dr.RIDER_VERBATIM)
        self.assertIn("A3-732", dr.STANDING_RULE_VERBATIM)
        self.assertIn("READ as discriminating until built", dr.PRE_RULING_RIDER_VERBATIM)


class DeclaredNotInvented(unittest.TestCase):
    """Arm 5 — the condition is transcribed from the engines' own code."""

    def _engine(self, lane):
        return _REPO / dr.LANES[lane]["engine"]

    @unittest.skipUnless((_REPO / dr.LANES["harmony"]["engine"]).is_file(), "engine absent")
    def test_harmony_condition_is_live_extracted_and_sha_stamped(self):
        b = dr.build_receipt("harmony", _REPO)
        c = b["declared_discriminating_condition"]
        self.assertEqual(c["extraction"], "live", c["extraction"])
        src = self._engine("harmony").read_text()
        self.assertEqual(c["contract_source_sha256"],
                         hashlib.sha256(src.encode("utf-8")).hexdigest())
        self.assertTrue(c["contract_excerpt"])
        for chunk in c["contract_excerpt"]:
            self.assertIn(chunk, src, "excerpt is not verbatim from the engine")

    @unittest.skipUnless((_REPO / dr.LANES["contagion"]["engine"]).is_file(), "engine absent")
    def test_contagion_condition_is_live_extracted_and_sha_stamped(self):
        b = dr.build_receipt("contagion", _REPO)
        c = b["declared_discriminating_condition"]
        self.assertEqual(c["extraction"], "live", c["extraction"])
        src = self._engine("contagion").read_text()
        self.assertEqual(c["contract_source_sha256"],
                         hashlib.sha256(src.encode("utf-8")).hexdigest())
        for chunk in c["contract_excerpt"]:
            self.assertIn(chunk, src, "excerpt is not verbatim from the engine")
        # the OT band edges are the whole discriminating condition here
        self.assertIn("0.85", "\n".join(c["contract_excerpt"]))

    def test_missing_marker_is_loud_not_fabricated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "audit-logs" / "contagion"
            d.mkdir(parents=True)
            (d / "disposition-tic-10.json").write_text(json.dumps({"meaningState": "resonant"}))
            eng = root / dr.LANES["contagion"]["engine"]
            eng.parent.mkdir(parents=True)
            eng.write_text("// an engine that no longer contains the deciding code\n")
            b = dr.build_receipt("contagion", root)
            self.assertTrue(
                b["declared_discriminating_condition"]["extraction"].startswith("partial:"),
                b["declared_discriminating_condition"]["extraction"])


class NegativeControl(unittest.TestCase):
    """Arm 6 — a changed disposition resets the counter."""

    def test_counter_resets_on_change(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "audit-logs" / "contagion"
            d.mkdir(parents=True)
            for t in range(10, 17):
                (d / f"disposition-tic-{t}.json").write_text(json.dumps({"meaningState": "resonant"}))
            constant = dr.build_receipt("contagion", root)
            self.assertEqual(constant["consecutive_identical_count"], 7)
            self.assertTrue(constant["never_changed_in_retained_history"])
            # inject the change
            (d / "disposition-tic-17.json").write_text(json.dumps({"meaningState": "tensioned"}))
            changed = dr.build_receipt("contagion", root)
            self.assertEqual(changed["consecutive_identical_count"], 1)
            self.assertEqual(changed["last_change_tic"], 17)
            self.assertEqual(changed["previous_distinct_tic"], 16)
            self.assertFalse(changed["never_changed_in_retained_history"])


class Wiring(unittest.TestCase):
    """Arm 7 — both emission lanes actually call the receipt step, fail-soft."""

    def test_harmony_invoke_calls_the_receipt_step_fail_soft(self):
        text = _HARMONY_SH.read_text()
        self.assertIn("discrimination-receipt.py", text)
        self.assertIn("--lane harmony", text)
        self.assertIn('WARN harmony: discrimination receipt step failed', text)

    def test_contagion_invoke_calls_the_receipt_step_fail_soft(self):
        text = _CONTAGION_SH.read_text()
        self.assertIn("discrimination-receipt.py", text)
        self.assertIn("--lane contagion", text)
        self.assertIn('WARN contagion: discrimination receipt step failed', text)

    def test_scripts_are_syntactically_valid(self):
        for sh in (_HARMONY_SH, _CONTAGION_SH):
            r = subprocess.run(["bash", "-n", str(sh)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)


class EmitSideOnly(unittest.TestCase):
    """Arm 8 — no consumer is touched by this build."""

    CONSUMERS = [
        "office-worldview.py", "cgg-statusline.sh", "harmony-input-builder.py",
        "braid-input-builder.py", "contagion-input-builder.py", "harmony-voice.py",
    ]

    def test_no_consumer_reads_the_receipt_block(self):
        for name in self.CONSUMERS:
            p = _HERE / name
            if not p.is_file():
                continue
            self.assertNotIn(
                "discrimination_receipt", p.read_text(),
                f"{name} reads the receipt block — the A3-732 rider forbids a consumer "
                f"until built AND ruled",
            )

    def test_module_selftest_passes(self):
        r = subprocess.run([sys.executable, str(_MODULE), "--selftest"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
