#!/usr/bin/env python3
"""test_review_close_check_mutable_address_tic783.py — THE MUTABLE-ADDRESS face.

Fix-site: /review 783 Q2 ratified same-pass cure (cpr id ending 55eb70c0a49b —
new cgg-ledger anchor #an-antecedent-named-by-a-mutable-address-is-not-named,
refining the ADDRESSING half of constitution-ledger#terminal-state-change-
requires-receipt-and-no-signal-goes-dark). An antecedent named by the LIVE
tic-keyed path — which the same run may overwrite — is not named; the cure
emits antecedent_durable_address at COMPOSITION: content sha256-16 +
generated_at + the projected preserved path under the write block's own
first-free-seq naming, with the skip-branch condition declared.

Four arms:
  (1) POPULATED — a live prior artifact exists: the durable address carries the
      sha256-16 of the ACTUAL bytes on disk, the prior's generated_at, and a
      projected path of superseded-1 when no preservation exists yet;
  (2) SEQ-ADVANCE — an existing superseded-1 file advances the projection to
      superseded-2 (the first-free-seq conditional's other arm), matching the
      write block's own naming exactly;
  (3) ABSENT — the tic's first fire: no durable address is fabricated, the
      reason_absent contract is byte-identical to pre-cure;
  (4) NOTE — the MUTABLE-ADDRESS clause rides in _SAME_TIC_OBS_NOTE append-only
      (the READ-INSTANT prefix marks still present — the t781 pins survive).
"""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("review_close_check", _HERE / "review-close-check.py")
rcc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rcc)


def _write_prior(report_dir, filename, body):
    p = Path(report_dir) / filename
    p.write_text(json.dumps(body), encoding="utf-8")
    return p.read_bytes()


class TestMutableAddressFace(unittest.TestCase):
    def test_populated_arm_durable_address_from_actual_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            raw = _write_prior(d, "tic-999-check.json",
                               {"generated_at": "2026-09-08T00:00:00+00:00"})
            prior, block = rcc._read_same_tic_prior_observation(d, "tic-999-check.json")
            self.assertTrue(block["present"])
            ada = block["antecedent_durable_address"]
            self.assertEqual(ada["content_sha256_16"],
                             hashlib.sha256(raw).hexdigest()[:16])
            self.assertEqual(ada["generated_at"], "2026-09-08T00:00:00+00:00")
            self.assertEqual(ada["will_be_preserved_as_if_superseded"],
                             "superseded/tic-999-check.superseded-1.json")
            self.assertIn("skip-branch", ada["condition"])

    def test_seq_advances_past_existing_preservation(self):
        with tempfile.TemporaryDirectory() as d:
            _write_prior(d, "tic-999-check.json", {"generated_at": "x"})
            sup = Path(d) / "superseded"
            sup.mkdir()
            (sup / "tic-999-check.superseded-1.json").write_text("{}", encoding="utf-8")
            _prior, block = rcc._read_same_tic_prior_observation(d, "tic-999-check.json")
            ada = block["antecedent_durable_address"]
            self.assertEqual(ada["will_be_preserved_as_if_superseded"],
                             "superseded/tic-999-check.superseded-2.json")
            # the earlier preservation is ALSO listed (pre-existing field intact)
            self.assertEqual(block["earlier_preserved_same_tic_artifacts"],
                             ["tic-999-check.superseded-1.json"])

    def test_absent_arm_no_fabricated_address(self):
        with tempfile.TemporaryDirectory() as d:
            prior, block = rcc._read_same_tic_prior_observation(d, "tic-999-check.json")
            self.assertIsNone(prior)
            self.assertFalse(block["present"])
            self.assertEqual(block["reason_absent"], "no_same_tic_prior_observation")
            self.assertNotIn("antecedent_durable_address", block)

    def test_note_extended_append_only(self):
        # The MUTABLE-ADDRESS clause rides beside the READ-INSTANT clause; the
        # t781 substring pins survive because the extension is append-only.
        self.assertIn("MUTABLE-ADDRESS (/review 783", rcc._SAME_TIC_OBS_NOTE)
        self.assertIn("antecedent_durable_address", rcc._SAME_TIC_OBS_NOTE)
        self.assertIn("READ-INSTANT (/review 781", rcc._SAME_TIC_OBS_NOTE)
        self.assertIn("they are NOT", rcc._SAME_TIC_OBS_NOTE)


if __name__ == "__main__":
    unittest.main()
