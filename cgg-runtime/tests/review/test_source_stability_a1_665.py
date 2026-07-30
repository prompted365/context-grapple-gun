"""A1-665 regression: gather_source_stability must consult the stamped
`source_file` field before falling back to the colon-heuristic over the
free-prose `source` sentence.

Filed by the cpr-stepper at tic 665 (reviews/2026-07-30.jsonl, A1-665) while
exercising the CPR-STEP lane: the consumer resolved prose as a path and never
read the field the producer stamps, minting FALSE source_missing rays
(35/50 at the census, 13/13 of the live enrichment_needed cohort, -0.30
each) — inverting Gate-1 where it feeds docket readiness. Repaired in-lane
same tic (fix-found-defects-in-lane discipline).
"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_SCANNER = (
    Path(__file__).resolve().parents[2] / "scripts" / "cpr-enrichment-scanner.py"
)
_spec = importlib.util.spec_from_file_location("cpr_enrichment_scanner", _SCANNER)
scanner = importlib.util.module_from_spec(_spec)
sys.modules["cpr_enrichment_scanner"] = scanner
_spec.loader.exec_module(scanner)


class TestSourceStabilityResolutionOrder(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = self._tmp.name
        self.real = Path(self.project_dir) / "borns-real-file.md"
        self.real.write_text(
            "the lesson body lives here: a tool's path-argument law derives "
            "from each argument's surface class",
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_stamped_source_file_outranks_prose_source(self):
        # The A1-665 shape: prose `source` sentence resolves to nothing; the
        # stamped `source_file` is the real path. Pre-fix this minted a FALSE
        # source_missing ray.
        cpr = {
            "id": "cpr_a",
            "source": "learned while exercising the emitter against the live board",
            "source_file": "borns-real-file.md",
            "lesson": "the lesson body lives here",
        }
        ev = scanner.gather_source_stability(cpr, self.project_dir)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["evidence_type"], "source_stable")

    def test_legacy_colon_heuristic_still_works_without_stamp(self):
        cpr = {
            "id": "cpr_b",
            "source": "borns-real-file.md:12",
            "lesson": "the lesson body lives here",
        }
        ev = scanner.gather_source_stability(cpr, self.project_dir)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["evidence_type"], "source_stable")

    def test_source_missing_only_when_both_fail(self):
        cpr = {
            "id": "cpr_c",
            "source": "a prose sentence that is not a path",
            "source_file": "genuinely-absent-file.md",
            "lesson": "irrelevant",
        }
        ev = scanner.gather_source_stability(cpr, self.project_dir)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["evidence_type"], "source_missing")
        # The ray names every path it tried — auditable, not bare.
        self.assertIn("genuinely-absent-file.md", ev[0]["value"])

    def test_stamped_field_alone_suffices(self):
        # A row with source_file but no prose source is still checkable.
        cpr = {
            "id": "cpr_d",
            "source_file": "borns-real-file.md",
            "lesson": "the lesson body lives here",
        }
        ev = scanner.gather_source_stability(cpr, self.project_dir)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["evidence_type"], "source_stable")

    def test_no_fields_no_evidence(self):
        ev = scanner.gather_source_stability({"id": "cpr_e"}, self.project_dir)
        self.assertEqual(ev, [])


class TestExclusiveEvidenceSupersession(unittest.TestCase):
    """A1-665 completion: a fresh source-surface observation supersedes a
    contradicted stale one in the merge — the same file must not read as both
    present and absent on one row."""

    def _merge(self, existing_enrichment, all_evidence):
        # Mirror of the scan-loop merge block (the logic under test is the
        # supersession computation; reproduced minimally with the same
        # group table the scanner carries).
        existing_types = {e.get("evidence_type") for e in existing_enrichment}
        new_evidence = [
            e for e in all_evidence if e["evidence_type"] not in existing_types
        ]
        fresh_types = {e["evidence_type"] for e in all_evidence}
        superseded_types = set()
        for group in ({"source_stable", "source_diverged", "source_missing"},):
            hit = group & fresh_types
            if hit:
                superseded_types |= (group - hit) & existing_types
        changed = bool(new_evidence) or bool(superseded_types)
        kept = [
            e for e in existing_enrichment
            if e.get("evidence_type") not in superseded_types
        ]
        return changed, kept + new_evidence

    def test_fresh_stable_supersedes_stale_missing(self):
        existing = [
            {"evidence_type": "source_missing", "value": "false ray (A1-665)"},
            {"evidence_type": "cross_reference", "value": "kept"},
        ]
        fresh = [{"evidence_type": "source_stable", "value": "file exists"}]
        changed, merged = self._merge(existing, fresh)
        self.assertTrue(changed)
        types = [e["evidence_type"] for e in merged]
        self.assertIn("source_stable", types)
        self.assertIn("cross_reference", types)
        self.assertNotIn("source_missing", types)

    def test_supersession_fires_even_when_fresh_type_already_present(self):
        # The re-run shape: source_stable already landed on the row, the
        # false source_missing still sits beside it. No NEW type arrives,
        # but the supersession is itself a row change.
        existing = [
            {"evidence_type": "source_missing", "value": "false ray"},
            {"evidence_type": "source_stable", "value": "landed last run"},
        ]
        fresh = [{"evidence_type": "source_stable", "value": "file exists"}]
        changed, merged = self._merge(existing, fresh)
        self.assertTrue(changed)
        types = [e["evidence_type"] for e in merged]
        self.assertEqual(types.count("source_stable"), 1)
        self.assertNotIn("source_missing", types)

    def test_no_change_when_no_new_and_no_contradiction(self):
        existing = [{"evidence_type": "source_stable", "value": "stable"}]
        fresh = [{"evidence_type": "source_stable", "value": "stable again"}]
        changed, merged = self._merge(existing, fresh)
        self.assertFalse(changed)
        self.assertEqual(len(merged), 1)

    def test_unrelated_types_still_accrete(self):
        existing = [{"evidence_type": "source_stable", "value": "stable"}]
        fresh = [{"evidence_type": "git_activity", "value": "3 commits"}]
        changed, merged = self._merge(existing, fresh)
        self.assertTrue(changed)
        self.assertEqual(len(merged), 2)


if __name__ == "__main__":
    unittest.main()
