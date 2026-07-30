#!/usr/bin/env python3
"""
Review-lane test — enrichment-ontology builds (a)+(b)
(bk-enrichment-ontology-provenance-classes, /review 615 implementation gate,
spec: autonomous_kernel/enrichment-ontology-spec.md).

Build (a) — `provenance_class` provenance coordinate:
  - cpr-extract.py::_resolve_provenance_class is DECLARED-NEVER-INFERRED:
    absent ⇒ friction_born; unknown value ⇒ friction_born (loud);
    construction_authoritative WITHOUT evidence ⇒ friction_born (fail-closed);
    construction_authoritative WITH evidence ⇒ accepted.
  - No lexical inference: ratification-flavored prose without a declaration
    still resolves to friction_born.

Build (b) — `enrichment_unnecessary_proven` named terminal outcome:
  - cpr-enrichment-scanner.py::derive_enrichment_outcome emits the marker on
    (i) construction_authoritative + lineage registered (proof names the
    ratification-bearing evidence) or (ii) honest-zero no_evidence_reason held
    across a full maturity window with a disk-verification scan on record —
    and on NEITHER condition otherwise (both arms of each documented
    conditional exercised, per the selftest-fixture discipline).
  - derive_baseline_classification carries the marker additively (absent when
    unearned — the consolidated schema is unchanged for legacy rows).
  - bench-packet-prep.py::load_enrichment_artifacts passes the marker through;
    cluster_pending_cogprs routes marked dossiers to the DISTINCT
    `enrichment_unnecessary_proven` intake state — not `uncovered`, and
    without disturbing the existing lesson_class routing.

Run: python3 tests/review/test_enrichment_ontology_provenance_tic616.py
Exit 0 = PASS, 1 = FAIL.
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ce = _load("cpr_extract", "cpr-extract.py")
scanner = _load("cpr_enrichment_scanner", "cpr-enrichment-scanner.py")
bpp = _load("bench_packet_prep", "bench-packet-prep.py")


class TestProvenanceClassResolution(unittest.TestCase):
    """Build (a): declared-never-inferred stamping (cpr-extract)."""

    def test_absent_declaration_defaults_friction_born(self):
        self.assertEqual(
            ce._resolve_provenance_class({}, "x.md:1"), "friction_born"
        )

    def test_declared_friction_born_accepted(self):
        block = {"provenance_class": "friction_born"}
        self.assertEqual(
            ce._resolve_provenance_class(block, "x.md:1"), "friction_born"
        )

    def test_construction_authoritative_with_evidence_accepted(self):
        block = {
            "provenance_class": "construction_authoritative",
            "evidence": "Architect-ratified in-tic via AskUserQuestion, /review 615",
        }
        self.assertEqual(
            ce._resolve_provenance_class(block, "x.md:1"),
            "construction_authoritative",
        )

    def test_construction_authoritative_with_evidence_list_accepted(self):
        block = {
            "provenance_class": "construction_authoritative",
            "evidence": ["ratification ref A", "receipt B"],
        }
        self.assertEqual(
            ce._resolve_provenance_class(block, "x.md:1"),
            "construction_authoritative",
        )

    def test_construction_authoritative_without_evidence_fails_closed(self):
        block = {"provenance_class": "construction_authoritative"}
        self.assertEqual(
            ce._resolve_provenance_class(block, "x.md:1"), "friction_born"
        )

    def test_construction_authoritative_empty_evidence_list_fails_closed(self):
        block = {
            "provenance_class": "construction_authoritative",
            "evidence": [],
        }
        self.assertEqual(
            ce._resolve_provenance_class(block, "x.md:1"), "friction_born"
        )

    def test_unknown_value_fails_closed(self):
        block = {"provenance_class": "architect_blessed", "evidence": "ref"}
        self.assertEqual(
            ce._resolve_provenance_class(block, "x.md:1"), "friction_born"
        )

    def test_no_lexical_inference(self):
        # A block whose PROSE screams ratification but declares nothing must
        # stay friction_born — self-granting via lexical shape is the exact
        # fluency-becoming-authority seam the constraint closes.
        block = {
            "lesson": "Architect-ratified in-tic; construction authoritative",
            "source": "borns-tic616-architect-ratified.md",
            "evidence": "in-tic ratification reference",
        }
        self.assertEqual(
            ce._resolve_provenance_class(block, "x.md:1"), "friction_born"
        )

    def test_module_constants(self):
        self.assertEqual(
            ce.PROVENANCE_CLASSES,
            frozenset({"construction_authoritative", "friction_born"}),
        )
        self.assertEqual(ce.PROVENANCE_DEFAULT, "friction_born")


class TestEnrichmentOutcome(unittest.TestCase):
    """Build (b): named terminal outcome derivation (scanner)."""

    def test_construction_authoritative_lineage_registered_emits(self):
        cpr = {
            "id": "cpr_x",
            "provenance_class": "construction_authoritative",
            "relations": {"refines": ["governance-pipeline-single-engine"]},
            "evidence": "Architect-ratified in-tic, /review 615",
        }
        outcome, proof = scanner.derive_enrichment_outcome(cpr, 616)
        self.assertEqual(outcome, "enrichment_unnecessary_proven")
        self.assertEqual(
            proof["basis"], "construction_authoritative_lineage_registered"
        )
        self.assertIn("refines:governance-pipeline-single-engine", proof["lineage"])
        self.assertIn("/review 615", proof["ratification_ref"])

    def test_construction_authoritative_without_lineage_holds(self):
        cpr = {
            "id": "cpr_x",
            "provenance_class": "construction_authoritative",
            "relations": {},
            "evidence": "ratification ref",
        }
        outcome, proof = scanner.derive_enrichment_outcome(cpr, 616)
        self.assertIsNone(outcome)
        self.assertIsNone(proof)

    def test_honest_zero_window_held_emits(self):
        # R2 (/review 663): claims present + advanced_tic anchor — the earned shape.
        cpr = {
            "id": "cpr_y",
            "birth_tic": 590,
            "advanced_tic": 600,
            "lesson": "a real claim",
            "source": "a real source",
            "no_evidence_reason": "no gatherer produced evidence",
            "enrichment_scanned_at": "2026-07-01T00:00:00+00:00",
            "enrichment_scan_count": 2,
        }
        outcome, proof = scanner.derive_enrichment_outcome(cpr, 616)  # 16 >= 10
        self.assertEqual(outcome, "enrichment_unnecessary_proven")
        self.assertEqual(proof["basis"], "honest_zero_window_held")
        self.assertIn("600->616 >= 10", proof["verification_ref"])
        self.assertIn("advanced_tic clock", proof["verification_ref"])

    def test_honest_zero_window_not_yet_held(self):
        cpr = {
            "id": "cpr_y",
            "birth_tic": 600,
            "advanced_tic": 610,
            "lesson": "a real claim",
            "source": "a real source",
            "no_evidence_reason": "no gatherer produced evidence",
            "enrichment_scanned_at": "2026-07-10T00:00:00+00:00",
        }
        outcome, _ = scanner.derive_enrichment_outcome(cpr, 616)  # 6 < 10
        self.assertIsNone(outcome)

    def test_honest_zero_never_disk_verified_holds(self):
        cpr = {
            "id": "cpr_y",
            "birth_tic": 590,
            "advanced_tic": 600,
            "lesson": "a real claim",
            "source": "a real source",
            "no_evidence_reason": "no gatherer produced evidence",
            # no enrichment_scanned_at — never disk-verified
        }
        outcome, _ = scanner.derive_enrichment_outcome(cpr, 616)
        self.assertIsNone(outcome)

    def test_honest_zero_respects_row_window(self):
        cpr = {
            "id": "cpr_y",
            "birth_tic": 590,
            "advanced_tic": 600,
            "lesson": "a real claim",
            "source": "a real source",
            "maturity_window_tics": 20,
            "no_evidence_reason": "no gatherer produced evidence",
            "enrichment_scanned_at": "2026-07-01T00:00:00+00:00",
        }
        outcome, _ = scanner.derive_enrichment_outcome(cpr, 616)  # 16 < 20
        self.assertIsNone(outcome)

    def test_honest_zero_shell_refused_zero_by_missing_input(self):
        # R2 discrimination tooth (/review 663): a content-less shell's zero is
        # zero-by-missing-input (A3 field-strip artifact) — the t244 grant shape.
        # Elapsed window + scan on record, but NO source/lesson -> refused.
        cpr = {
            "id": "cpr_shell",
            "birth_tic": 590,
            "advanced_tic": 600,
            "no_evidence_reason": (
                "no gatherer produced evidence (missing: source, source_date, "
                "subsystem, recommended_scopes)"
            ),
            "enrichment_scanned_at": "2026-07-01T00:00:00+00:00",
        }
        outcome, proof = scanner.derive_enrichment_outcome(cpr, 616)  # 16 >= 10
        self.assertIsNone(outcome)
        self.assertIsNone(proof)

    def test_honest_zero_missing_input_reason_refused_despite_claims(self):
        # R2 discrimination, live-fire regression (C3 grant caught at tic 665):
        # a row can carry a lesson body while the GATHERERS lacked their inputs
        # — the scanner's own "(missing: ...)" reason suffix marks the zero as
        # zero_by_missing_input, and no row-level claims can convert that into
        # proven sufficiency.
        cpr = {
            "id": "cpr_c3_shape",
            "birth_tic": 327,
            "advanced_tic": 635,
            "lesson": "a substantial lesson body is present",
            "no_evidence_reason": (
                "no gatherer produced evidence (missing: source, source_date, "
                "subsystem, recommended_scopes)"
            ),
            "enrichment_scanned_at": "2026-07-30T08:00:00+00:00",
        }
        outcome, proof = scanner.derive_enrichment_outcome(cpr, 665)  # 30 >= 10
        self.assertIsNone(outcome)
        self.assertIsNone(proof)

    def test_honest_zero_birth_span_alone_refused(self):
        # R2 clock tooth (/review 663): the birth-span is vacuously elapsed on
        # any old row; without the advanced_tic anchor the hold is unprovable
        # and the predicate fails closed.
        cpr = {
            "id": "cpr_old",
            "birth_tic": 244,
            "lesson": "a real claim",
            "source": "a real source",
            "no_evidence_reason": "no gatherer produced evidence",
            "enrichment_scanned_at": "2026-07-15T03:53:18+00:00",
            # no advanced_tic — birth-span 244->616 elapsed, but no anchor
        }
        outcome, _ = scanner.derive_enrichment_outcome(cpr, 616)
        self.assertIsNone(outcome)

    def test_plain_friction_born_row_emits_nothing(self):
        cpr = {"id": "cpr_z", "birth_tic": 600, "lesson": "x", "source": "y"}
        outcome, _ = scanner.derive_enrichment_outcome(cpr, 616)
        self.assertIsNone(outcome)

    def test_baseline_classification_carries_marker_when_earned(self):
        cpr = {
            "id": "cpr_x",
            "lesson": "a lesson",
            "source": "a source",
            "provenance_class": "construction_authoritative",
            "relations": {"refines": ["parent-ki"]},
            "evidence": "ratification ref",
        }
        consolidated = scanner.derive_baseline_classification(cpr, [], 616)
        self.assertEqual(
            consolidated["enrichment_outcome"], "enrichment_unnecessary_proven"
        )
        self.assertIn("enrichment_outcome_proof", consolidated)

    def test_baseline_classification_omits_marker_when_unearned(self):
        cpr = {"id": "cpr_z", "lesson": "a lesson", "source": "a source"}
        consolidated = scanner.derive_baseline_classification(cpr, [], 616)
        self.assertNotIn("enrichment_outcome", consolidated)
        self.assertNotIn("enrichment_outcome_proof", consolidated)


class TestBenchPacketIntakeState(unittest.TestCase):
    """Build (b): distinct intake state at the bench-packet surface."""

    def _artifact_dir_with(self, payload):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        enr = Path(tmp.name) / "governance" / "enrichment"
        enr.mkdir(parents=True)
        (enr / f"{payload['record_id']}.consolidated.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        return tmp.name

    def test_loader_passes_marker_through(self):
        payload = {
            "record_id": "cpr_x",
            "tier": "deterministic-lite",
            "agreements": [],
            "enrichment_outcome": "enrichment_unnecessary_proven",
            "enrichment_outcome_proof": {"basis": "honest_zero_window_held"},
        }
        artifacts = bpp.load_enrichment_artifacts(self._artifact_dir_with(payload))
        self.assertEqual(
            artifacts["cpr_x"]["enrichment_outcome"],
            "enrichment_unnecessary_proven",
        )
        self.assertEqual(
            artifacts["cpr_x"]["enrichment_outcome_proof"]["basis"],
            "honest_zero_window_held",
        )

    def test_loader_absent_marker_reads_none(self):
        payload = {"record_id": "cpr_y", "tier": "deterministic-lite", "agreements": []}
        artifacts = bpp.load_enrichment_artifacts(self._artifact_dir_with(payload))
        self.assertIsNone(artifacts["cpr_y"]["enrichment_outcome"])

    def test_cluster_routes_marker_to_distinct_state(self):
        pending = [
            {  # proven-unnecessary — the new distinct lane
                "id": "cpr_proven",
                "enrichment_evidence": {
                    "enrichment_outcome": "enrichment_unnecessary_proven",
                    "key_agreements": {"lesson_class": "engineering"},
                },
            },
            {  # ordinary classified row — existing routing undisturbed
                "id": "cpr_eng",
                "enrichment_evidence": {
                    "key_agreements": {"lesson_class": "engineering"}
                },
            },
            {  # no eyes on it — stays uncovered
                "id": "cpr_dark",
                "enrichment_evidence": None,
            },
            {  # classified to an unknown bucket — stays other
                "id": "cpr_odd",
                "enrichment_evidence": {
                    "key_agreements": {"lesson_class": "mystery"}
                },
            },
        ]
        clusters = bpp.cluster_pending_cogprs(pending)
        self.assertEqual(clusters["enrichment_unnecessary_proven"], ["cpr_proven"])
        self.assertEqual(clusters["engineering"], ["cpr_eng"])
        self.assertEqual(clusters["uncovered"], ["cpr_dark"])
        self.assertEqual(clusters["other"], ["cpr_odd"])
        # The marker outranks lesson_class routing — cpr_proven carries an
        # engineering lesson_class but lands in the distinct intake state.
        self.assertNotIn("cpr_proven", clusters["engineering"])
        # And it is emphatically NOT uncovered.
        self.assertNotIn("cpr_proven", clusters["uncovered"])

    def test_cluster_buckets_include_distinct_state(self):
        clusters = bpp.cluster_pending_cogprs([])
        self.assertIn("enrichment_unnecessary_proven", clusters)


if __name__ == "__main__":
    result = unittest.main(exit=False).result
    sys.exit(0 if result.wasSuccessful() else 1)
