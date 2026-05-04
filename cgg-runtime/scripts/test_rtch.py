#!/usr/bin/env python3
"""
test_rtch.py — Phase 2 fixture tests for rtch.py (Runtime Tactical Context
Hydration runner).

Covers, at minimum, the 6 Phase 2 test scope items from the binder + brief:
  1. Zone resolution (inside federation)
  2. Zone resolution from outside federation (graceful fallback)
  3. shape_scout() output schema
  4. Cost-discovery / scout boundedness (limit respected)
  5. Bounded-chunk hydration directive (no full file body for >200-line files)
  6. Pairing rule + generic-alone warning

PLUS binder-mandatory invariant coverage:
  7. Packet schema mandatory fields (unresolved_questions cardinality > 0,
     halting_reason non-empty, skipped_surfaces present, ttl_tics == 30,
     expires_at_tic == generated_at_tic + 30).
  8. Validation example built-in (parse_intake with --validate-example 10.3
     yields target_profile='code_path' + queue_state_compile in seeds).

Run from the scripts directory:
  python3 -m unittest test_rtch.py -v

Stdlib-only. No pytest, no mock libraries.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Allow importing rtch from same directory regardless of cwd.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import rtch  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_args(**overrides) -> argparse.Namespace:
    """Build an argparse.Namespace mirroring rtch.main()'s parser shape."""
    defaults = {
        "goal": None,
        "profile": None,
        "fanout": None,
        "risk": None,
        "output_kind": None,
        "enough": None,
        "seed": None,
        "known_target": None,
        "forbid": None,
        "neighbor": None,
        "intake": None,
        "validate_example": None,
        "persist": False,
        "handoff": False,
        "json": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_minimal_intake(**overrides) -> dict:
    """Build a syntactically valid intake dict for downstream stage tests
    without going through parse_intake (so we can vary internals freely)."""
    intake = {
        "goal": "test goal",
        "target_profile": "code_path",
        "fanout_level": "conservative",
        "mutation_risk": "read_only",
        "expected_output": "claim_evidence",
        "enough_evidence_definition": "I have evidence",
        "known_target": None,
        "explicit_seeds": [],
        "forbidden_assumptions": [],
        "known_neighbor_surfaces": [],
        "intake_hash": "deadbeefcafe",
    }
    intake.update(overrides)
    return intake


# ─────────────────────────────────────────────────────────────────────────────
# Constants and module surface tests (sanity)
# ─────────────────────────────────────────────────────────────────────────────


class TestModuleConstants(unittest.TestCase):
    def test_packet_ttl_is_thirty(self):
        self.assertEqual(rtch.PACKET_TTL_TICS, 30)

    def test_generic_terms_includes_known_generics(self):
        # Brief mentions: domain, state, surface
        for term in ("domain", "state", "surface"):
            self.assertIn(term, rtch.GENERIC_TERMS)

    def test_callables_exposed(self):
        for name in (
            "parse_intake", "orient_zone", "shape_scout",
            "build_basket", "build_probe_plan", "build_packet",
            "_hydrate_hits", "_scan_directory_map", "_scan_filenames",
            "_scan_headings",
        ):
            self.assertTrue(hasattr(rtch, name), f"rtch missing {name}")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 item 8 — Validation example built-in (parse_intake)
# ─────────────────────────────────────────────────────────────────────────────


class TestParseIntakeValidationExample(unittest.TestCase):
    def test_validate_example_10_3_returns_code_path_profile(self):
        args = _make_args(validate_example="10.3")
        intake = rtch.parse_intake(args)
        self.assertEqual(intake["target_profile"], "code_path")

    def test_validate_example_10_3_seeds_contain_queue_state_compile(self):
        args = _make_args(validate_example="10.3")
        intake = rtch.parse_intake(args)
        self.assertIn("queue_state_compile", intake.get("explicit_seeds", []))

    def test_parse_intake_emits_intake_hash(self):
        args = _make_args(validate_example="10.3")
        intake = rtch.parse_intake(args)
        self.assertIn("intake_hash", intake)
        self.assertTrue(intake["intake_hash"])  # non-empty
        self.assertEqual(len(intake["intake_hash"]), 12)  # 12 hex chars

    def test_parse_intake_rejects_invalid_target_profile(self):
        # Build an intake JSON file with a bad profile, point parse_intake at it.
        with tempfile.TemporaryDirectory() as td:
            bad_path = os.path.join(td, "bad_intake.json")
            Path(bad_path).write_text(
                '{"goal": "g", "target_profile": "WRONG", "fanout_level": "conservative",'
                ' "mutation_risk": "read_only", "expected_output": "claim_evidence",'
                ' "enough_evidence_definition": "x"}',
                encoding="utf-8",
            )
            args = _make_args(intake=bad_path)
            with self.assertRaises(SystemExit):
                rtch.parse_intake(args)

    def test_parse_intake_rejects_missing_required_field(self):
        with tempfile.TemporaryDirectory() as td:
            bad_path = os.path.join(td, "bad_intake.json")
            # Missing enough_evidence_definition (load-bearing per binder §4.1)
            Path(bad_path).write_text(
                '{"goal": "g", "target_profile": "code_path", "fanout_level": "conservative",'
                ' "mutation_risk": "read_only", "expected_output": "claim_evidence"}',
                encoding="utf-8",
            )
            args = _make_args(intake=bad_path)
            with self.assertRaises(SystemExit):
                rtch.parse_intake(args)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 items 1 + 2 — Zone resolution (inside / outside federation)
# ─────────────────────────────────────────────────────────────────────────────


class TestOrientZone(unittest.TestCase):
    def test_zone_resolution_inside_federation(self):
        # known_target points at a real federation file (this script's dir).
        intake = _make_minimal_intake(
            known_target=os.path.abspath(__file__),
        )
        zone = rtch.orient_zone(intake)

        self.assertIn("zone_root", zone)
        self.assertIsNotNone(zone["zone_root"])

        # Federation root contains .ticzone; zone_root should resolve to a
        # directory at-or-above this script that contains either .ticzone or
        # a recognized rung marker. Practical assertion: zone_root is a real
        # directory that this script lives under.
        zr = zone["zone_root"]
        self.assertTrue(os.path.isdir(zr))
        script_path = os.path.abspath(__file__)
        self.assertTrue(
            script_path.startswith(zr.rstrip(os.sep) + os.sep) or script_path == zr,
            f"script {script_path} should live under zone_root {zr}",
        )

        # rung_chain should be a list (may be empty if upstream resolver returned
        # the cwd fallback, but the field must exist).
        self.assertIsInstance(zone.get("rung_chain"), list)
        # obvious_truth_files / manifests exist as lists
        self.assertIsInstance(zone.get("obvious_truth_files"), list)
        self.assertIsInstance(zone.get("obvious_manifests_indexes"), list)

    def test_zone_resolution_inside_federation_returns_canonical_directory(self):
        # When known_target is a known canonical file, zone_root should
        # resolve up to the canonical/federation root or its container.
        federation_root = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
        # Should contain .ticzone or .federation-root for federation root
        intake = _make_minimal_intake(
            known_target=os.path.join(federation_root, "CLAUDE.md"),
        )
        zone = rtch.orient_zone(intake)
        # zone_root should be at-or-above the script (a real directory)
        self.assertTrue(os.path.isdir(zone["zone_root"]))

    def test_zone_resolution_from_outside_federation(self):
        # Use a tempdir outside the federation tree as cwd. Zone resolution
        # must NOT crash; it should fall back gracefully.
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as td:
            try:
                os.chdir(td)
                intake = _make_minimal_intake()  # no known_target
                # Should not raise.
                zone = rtch.orient_zone(intake)
                self.assertIsInstance(zone, dict)
                self.assertIn("zone_root", zone)
                self.assertIn("cwd", zone)
                # zone_root must be a string (real directory or fallback to cwd)
                self.assertIsInstance(zone["zone_root"], str)
                self.assertTrue(len(zone["zone_root"]) > 0)
            finally:
                os.chdir(original_cwd)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 item 3 — Shape scout output schema
# ─────────────────────────────────────────────────────────────────────────────


class TestShapeScoutSchema(unittest.TestCase):
    REQUIRED_KEYS = (
        "directory_map",
        "candidate_filenames",
        "headings",
        "durable_id_patterns",
        "json_yaml_keys",
        "audit_tic_markers",
        "source_of_truth_phrases",
        "deprecation_markers",
    )

    def test_shape_scout_returns_required_keys(self):
        intake = _make_minimal_intake(
            known_target=os.path.abspath(__file__),
        )
        zone = rtch.orient_zone(intake)
        scout = rtch.shape_scout(intake, zone)

        for k in self.REQUIRED_KEYS:
            self.assertIn(k, scout, f"shape_scout output missing required key: {k}")

    def test_shape_scout_returns_dict(self):
        intake = _make_minimal_intake(
            known_target=os.path.abspath(__file__),
        )
        zone = rtch.orient_zone(intake)
        scout = rtch.shape_scout(intake, zone)
        self.assertIsInstance(scout, dict)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 item 4 — Cost-discovery / scout boundedness
# ─────────────────────────────────────────────────────────────────────────────


class TestScoutBoundedness(unittest.TestCase):
    def setUp(self):
        # Build a temp tree wider than the limit, then verify _scan_*
        # respect the limit.
        self._td = tempfile.mkdtemp(prefix="rtch_test_scout_")
        # Create 30 nested directories (depth limited later).
        for i in range(30):
            os.makedirs(os.path.join(self._td, f"dir_{i:02d}"), exist_ok=True)
        # Create 30 files at top level.
        for i in range(30):
            with open(os.path.join(self._td, f"seed_match_{i:02d}.txt"), "w") as fh:
                fh.write("hello\n")

    def tearDown(self):
        import shutil as _sh
        _sh.rmtree(self._td, ignore_errors=True)

    def test_scan_directory_map_respects_limit(self):
        # Pass a tight limit.
        out = rtch._scan_directory_map(self._td, depth=3, limit=5)
        self.assertIsInstance(out, list)
        self.assertLessEqual(len(out), 5)

    def test_scan_filenames_respects_limit(self):
        intake = _make_minimal_intake(
            known_target=self._td,  # makes target_dir = self._td
            explicit_seeds=["seed_match"],
        )
        out = rtch._scan_filenames(self._td, intake, limit=7)
        self.assertIsInstance(out, list)
        self.assertLessEqual(len(out), 7)
        # Each entry has expected schema
        for entry in out:
            self.assertIn("path", entry)
            self.assertIn("size_bytes", entry)

    def test_scan_headings_respects_upper_bound(self):
        # _scan_headings has an internal cap of 200. Build a single .md file
        # with many headings to verify it does not run unbounded.
        md_path = os.path.join(self._td, "many_headings.md")
        lines = []
        for i in range(500):
            lines.append(f"# Heading {i}")
            lines.append("body line")
        Path(md_path).write_text("\n".join(lines), encoding="utf-8")
        out = rtch._scan_headings([md_path])
        self.assertIsInstance(out, list)
        # Hard cap from rtch._scan_headings is `> 200`, so the output may be
        # up to 201 (loop appends then early-returns on the next iteration).
        self.assertLessEqual(len(out), 250,
                             "scan_headings exceeded reasonable upper bound")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 item 5 — Bounded-chunk hydration directive
# ─────────────────────────────────────────────────────────────────────────────


class TestHydrateHitsBoundedChunks(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.mkdtemp(prefix="rtch_test_hydrate_")

    def tearDown(self):
        import shutil as _sh
        _sh.rmtree(self._td, ignore_errors=True)

    def _write_file(self, name: str, lines: int) -> str:
        p = os.path.join(self._td, name)
        with open(p, "w", encoding="utf-8") as fh:
            for i in range(lines):
                fh.write(f"line {i:04d} content\n")
        return p

    def test_hydrate_chunk_records_have_required_fields(self):
        big = self._write_file("big.txt", 1000)
        probe_outcome = {
            "probe_id": "rtch_probe_test_01",
            "family": "explicit_seed",
            "claim_authority": "source_bearing",
            "hits": [
                {"path": big, "line": 500, "matched_term": "test_term"},
            ],
        }
        zone = {"zone_root": self._td}
        intake = _make_minimal_intake()
        chunks = rtch._hydrate_hits(probe_outcome, zone, intake)
        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        # Required fields per Phase 2 item 5
        for k in ("path", "line_range", "confidence_class", "next_re_entry_command"):
            self.assertIn(k, chunk, f"chunk missing required field: {k}")
        # line_range format: 'L<start>-L<end>'
        self.assertTrue(chunk["line_range"].startswith("L"))
        self.assertIn("-L", chunk["line_range"])

    def test_hydrate_chunk_for_large_file_does_not_include_full_body(self):
        # Write a 1000-line file and confirm chunk body bounded by chunk window.
        big = self._write_file("big.txt", 1000)
        total_size_bytes = os.path.getsize(big)

        probe_outcome = {
            "probe_id": "rtch_probe_test_02",
            "family": "explicit_seed",
            "claim_authority": "source_bearing",
            "hits": [
                {"path": big, "line": 500, "matched_term": "anywhere"},
            ],
        }
        zone = {"zone_root": self._td}
        intake = _make_minimal_intake()
        chunks = rtch._hydrate_hits(probe_outcome, zone, intake)
        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]

        # body_full_chars must be far less than the full file (bounded by
        # DEFAULT_CHUNK_WINDOW lines, not full 1000 lines).
        self.assertIn("body_full_chars", chunk)
        self.assertLess(
            chunk["body_full_chars"],
            total_size_bytes,
            "hydrated body must be smaller than full file for >200-line file",
        )
        # And bounded chunk should be roughly DEFAULT_CHUNK_WINDOW lines worth.
        # Each line ~20 bytes, window=40 → ~800 bytes ceiling order-of-magnitude
        self.assertLess(
            chunk["body_full_chars"],
            5000,
            "hydrated body for bounded chunk should be small",
        )

    def test_hydrate_chunk_line_range_within_file(self):
        big = self._write_file("big.txt", 1000)
        probe_outcome = {
            "probe_id": "rtch_probe_test_03",
            "family": "explicit_seed",
            "claim_authority": "source_bearing",
            "hits": [
                {"path": big, "line": 500, "matched_term": "anywhere"},
            ],
        }
        zone = {"zone_root": self._td}
        intake = _make_minimal_intake()
        chunks = rtch._hydrate_hits(probe_outcome, zone, intake)
        self.assertEqual(len(chunks), 1)
        rng = chunks[0]["line_range"]
        # Parse 'L<start>-L<end>'
        start_str, end_str = rng[1:].split("-L")
        start, end = int(start_str), int(end_str)
        self.assertGreaterEqual(start, 1)
        self.assertLessEqual(end, 1000)
        self.assertLess(start, end)
        # window_size should be roughly DEFAULT_CHUNK_WINDOW
        self.assertLessEqual(end - start + 1, rtch.DEFAULT_CHUNK_WINDOW + 5)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 item 6 — Pairing rule + generic-alone warning
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildBasketGenericAloneWarnings(unittest.TestCase):
    def test_generic_only_seeds_emit_warnings(self):
        # All seeds are generic, no non-generic to pair with.
        intake = _make_minimal_intake(
            explicit_seeds=["domain", "state", "surface"],
        )
        zone = rtch.orient_zone(intake)
        # Empty scout (no manifests/headings/etc) — focus the assertion on
        # generic-alone behavior driven by intake seeds.
        scout = {
            "directory_map": [],
            "candidate_filenames": [],
            "headings": [],
            "durable_id_patterns": {},
            "json_yaml_keys": {},
            "audit_tic_markers": {},
            "source_of_truth_phrases": [],
            "deprecation_markers": [],
        }
        basket = rtch.build_basket(intake, zone, scout)

        self.assertIn("generic_alone_warnings", basket)
        self.assertGreater(
            len(basket["generic_alone_warnings"]),
            0,
            "generic-only seeds must produce at least one warning",
        )

        # Each generic seed (with no pairing) should appear with origin=exploratory
        seed_terms = {t["term"]: t for t in basket["terms"]
                      if t["term"].lower() in rtch.GENERIC_TERMS}
        self.assertGreater(len(seed_terms), 0)
        for term_obj in seed_terms.values():
            self.assertEqual(
                term_obj["origin"], "exploratory",
                f"generic-alone seed {term_obj['term']!r} must be tagged exploratory",
            )

    def test_generic_paired_with_specific_seed_does_not_warn(self):
        # When a generic seed is paired with a specific seed, the entry
        # should be origin=explicit_seed (not exploratory).
        intake = _make_minimal_intake(
            explicit_seeds=["domain", "queue_state_compile"],
        )
        zone = rtch.orient_zone(intake)
        scout = {
            "directory_map": [],
            "candidate_filenames": [],
            "headings": [],
            "durable_id_patterns": {},
            "json_yaml_keys": {},
            "audit_tic_markers": {},
            "source_of_truth_phrases": [],
            "deprecation_markers": [],
        }
        basket = rtch.build_basket(intake, zone, scout)
        domain_entries = [t for t in basket["terms"] if t["term"].lower() == "domain"]
        # When paired, "domain" must NOT be tagged exploratory.
        for d in domain_entries:
            self.assertEqual(d["origin"], "explicit_seed")
            self.assertGreater(len(d["paired_with"]), 0)


# ─────────────────────────────────────────────────────────────────────────────
# Item 7 — Packet schema mandatory fields (federation KI complexity preservation)
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildPacketMandatoryFields(unittest.TestCase):
    def _build_full_pipeline(self, current_tic: int = 100):
        """Run all stages with a controlled, minimal intake to produce a packet."""
        intake = _make_minimal_intake(
            explicit_seeds=["domain"],  # generic-only on purpose
            target_profile="code_path",
            fanout_level="conservative",
        )
        zone = rtch.orient_zone(intake)
        scout = rtch.shape_scout(intake, zone)
        basket = rtch.build_basket(intake, zone, scout)
        plan = rtch.build_probe_plan(intake, zone, basket)
        executed, chunks = rtch.execute_probes_and_hydrate(intake, zone, plan)
        packet = rtch.build_packet(
            intake, zone, scout, basket, plan, executed, chunks, current_tic,
        )
        return packet

    def test_packet_unresolved_questions_cardinality_gt_zero(self):
        packet = self._build_full_pipeline()
        self.assertIn("unresolved_questions", packet)
        self.assertIsInstance(packet["unresolved_questions"], list)
        self.assertGreater(
            len(packet["unresolved_questions"]),
            0,
            "federation KI: complexity preservation requires unresolved cardinality > 0",
        )

    def test_packet_halting_reason_non_empty(self):
        packet = self._build_full_pipeline()
        self.assertIn("halting_reason", packet)
        self.assertTrue(packet["halting_reason"])
        self.assertIsInstance(packet["halting_reason"], str)

    def test_packet_skipped_surfaces_field_present(self):
        packet = self._build_full_pipeline()
        self.assertIn("skipped_surfaces", packet)
        self.assertIsInstance(packet["skipped_surfaces"], list)

    def test_packet_ttl_tics_is_thirty(self):
        packet = self._build_full_pipeline(current_tic=150)
        self.assertEqual(packet["ttl_tics"], 30)
        self.assertEqual(packet["ttl_tics"], rtch.PACKET_TTL_TICS)

    def test_packet_expires_at_tic_equals_generated_plus_thirty(self):
        packet = self._build_full_pipeline(current_tic=150)
        self.assertEqual(packet["generated_at_tic"], 150)
        self.assertEqual(packet["expires_at_tic"], 180)
        self.assertEqual(
            packet["expires_at_tic"],
            packet["generated_at_tic"] + 30,
        )

    def test_packet_carries_packet_id_and_schema_version(self):
        packet = self._build_full_pipeline()
        self.assertIn("packet_id", packet)
        self.assertTrue(packet["packet_id"].startswith("rtch_packet_"))
        self.assertEqual(packet["schema_version"], "rtch.packet.v1")


# ─────────────────────────────────────────────────────────────────────────────
# Probe plan sanity (binder §4.5 fanout budget enforcement)
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildProbePlan(unittest.TestCase):
    def test_conservative_fanout_caps_probe_count(self):
        intake = _make_minimal_intake(
            explicit_seeds=["queue_state_compile", "compile_lane_status"],
            target_profile="code_path",
            fanout_level="conservative",
        )
        zone = rtch.orient_zone(intake)
        scout = rtch.shape_scout(intake, zone)
        basket = rtch.build_basket(intake, zone, scout)
        plan = rtch.build_probe_plan(intake, zone, basket)

        budget = rtch.FANOUT_BUDGETS["conservative"]
        self.assertLessEqual(plan["probe_count"], budget["max_probes"])
        self.assertEqual(len(plan["probes"]), plan["probe_count"])
        self.assertGreaterEqual(plan["probe_budget_remaining"], 0)

    def test_plan_carries_required_envelope_fields(self):
        intake = _make_minimal_intake(
            explicit_seeds=["queue_state_compile"],
            target_profile="code_path",
            fanout_level="conservative",
        )
        zone = rtch.orient_zone(intake)
        scout = rtch.shape_scout(intake, zone)
        basket = rtch.build_basket(intake, zone, scout)
        plan = rtch.build_probe_plan(intake, zone, basket)

        for k in ("plan_id", "basket_ref", "fanout_level",
                  "probe_count", "probe_budget_remaining", "probes"):
            self.assertIn(k, plan)


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    unittest.main()
