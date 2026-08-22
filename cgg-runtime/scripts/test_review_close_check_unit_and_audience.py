#!/usr/bin/env python3
"""Tests for the /review 716 review-close-check cures.

Cure A (cpr_mogul_review_close_check_502236e96cf1, SKIP-with-routing — the
class-cure executed): the inscribed-index counter's POPULATION and UNIT are
declared as fields beside the integer (unit_declaration in the diagnostics +
inscribed_index_unit in the report), with the multi-token comment count that
measures the token≠event referent gap. The tic-706 reserved-prefix exclusion
was an instance-cure; this is the class-cure the /review-712 guard-11
refinement ray entails.

Cure B (cpr_mogul_review_close_check_07c597566b16, PROMOTE-as-refinement-ray —
the AUDIENCE/HANDLE ray): the supersession receipt is ALSO written into the
live replacing artifact (the consumer's handle) and a sidecar back-stamp
lands beside the preserved copy (raw bytes stay byte-exact); the receipt key
is comparison-volatile so identical-findings runs still lawfully skip.
Write-path arms are generator-enforced against source (the 6372-cure style):
the conditional's both arms live in the replace branch a unit fixture cannot
cheaply reach; the source asserts pin the wiring, and the first live fire
rides the next real supersession event.

RIDER 1 (/review 724, cgg-ledger#instance-keyed-cures-cannot-see-sibling-routes-
disclosure-parity): the unit_declaration's boundary_rule justified the index's
over-admission by ONE route (a sibling id narrated in provenance prose). At tic
721 a token entered by a route that rationale does not cover — a CPR-shaped
SUBSTRING OF A FILENAME cited in a `Source:` clause. boundary_rule now enumerates
every admission route derived from the MECHANISM, the structurally countable ones
are measured at runtime, and admission itself is UNCHANGED (disclosure parity,
not gating).

RIDER 2 (/review 724, constitution-ledger streak-claims ray): the counter emits a
per-pass PER-UNIT DELTA — delta_tokens, delta_matched_comments, and
units_collapsed_this_pass (true iff the two deltas are equal, so agreement under
collapse is legible AS collapse) — against the previous PASS artifact, with
nulls + delta_baseline_absent when no baseline exists (never fabricated zeros).

Both arms of every documented conditional are exercised
(cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths).
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = (_HERE / "review-close-check.py").read_text(encoding="utf-8")
_spec = importlib.util.spec_from_file_location(
    "review_close_check", _HERE / "review-close-check.py"
)
rcc = importlib.util.module_from_spec(_spec)
sys.modules["review_close_check"] = rcc
_spec.loader.exec_module(rcc)


class _HermeticHome(unittest.TestCase):
    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self._orig_expanduser = os.path.expanduser
        self._orig_home = Path.home
        home = self._home.name
        os.path.expanduser = lambda p: p.replace("~", home, 1) if p.startswith("~") else p
        Path.home = classmethod(lambda cls: Path(home))
        rcc.os.path.expanduser = os.path.expanduser

    def tearDown(self):
        os.path.expanduser = self._orig_expanduser
        rcc.os.path.expanduser = self._orig_expanduser
        Path.home = self._orig_home
        self._home.cleanup()


class TestUnitDeclaration(_HermeticHome):
    def _run(self, claude_md_text, queue_ids=None):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(claude_md_text, encoding="utf-8")
        with tmp:
            diag = {}
            inscribed = rcc.build_inscribed_index(
                str(root), queue_ids=queue_ids, diagnostics=diag)
            return inscribed, diag

    def test_unit_declaration_present_with_all_fields(self):
        _, diag = self._run("<!-- promoted from cpr_one_tic700 -->\n")
        ud = diag["unit_declaration"]
        for key in ("unit", "population", "boundary_rule", "not_the_unit",
                    "matched_comment_count", "multi_token_comment_count"):
            self.assertIn(key, ud)
        self.assertEqual(
            ud["unit"],
            "distinct_cpr_shaped_tokens_inside_matched_provenance_comments")
        self.assertEqual(ud["matched_comment_count"], 1)
        self.assertEqual(ud["multi_token_comment_count"], 0)

    def test_multi_token_comment_counted(self):
        # One compound comment (two distinct admitted tokens) + one single-token
        # comment: multi count is exactly 1 — the referent-gap measurement.
        _, diag = self._run(
            "<!-- promoted from cpr_a_tic700 merged with cpr_b_tic701 -->\n"
            "<!-- promoted from cpr_c_tic702 -->\n")
        ud = diag["unit_declaration"]
        self.assertEqual(ud["matched_comment_count"], 2)
        self.assertEqual(ud["multi_token_comment_count"], 1)

    def test_reserved_token_not_counted_toward_multi(self):
        # A real token + a reserved-namespace token in one comment: the reserved
        # token is excluded BEFORE the distinct count, so the comment is not
        # multi-token (both-arms discipline: exclusion feeds the count).
        _, diag = self._run(
            "<!-- promoted from cpr_real_tic700. era: cpr_era_tic_700_749 -->\n")
        ud = diag["unit_declaration"]
        self.assertEqual(ud["matched_comment_count"], 1)
        self.assertEqual(ud["multi_token_comment_count"], 0)
        self.assertEqual(diag["reserved_excluded_count"], 1)

    def test_repeated_same_token_not_multi(self):
        # The same id appearing twice in one comment is ONE distinct token.
        _, diag = self._run(
            "<!-- promoted from cpr_same_tic700; supersedes cpr_same_tic700 -->\n")
        self.assertEqual(diag["unit_declaration"]["multi_token_comment_count"], 0)


class TestPromoteAsRefinementVerbMatched(_HermeticHome):
    """tic-716 verb-alternation fix (n=2 of the tic-515 class), both arms."""

    def _run(self, text):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(text, encoding="utf-8")
        with tmp:
            return rcc.build_inscribed_index(str(root))

    def test_promote_as_refinement_comment_admitted(self):
        idx = self._run(
            "<!-- PROMOTE-AS-REFINEMENT (ray to some-entry), /review 716. "
            "Promoted from cpr_ray_token_tic716. -->\n")
        self.assertIn("cpr_ray_token_tic716", idx)

    def test_skip_with_home_opening_stays_excluded(self):
        # A SKIP pointer is NOT an inscription witness — excluded by design.
        idx = self._run(
            "<!-- SKIP-WITH-HOME POINTER (cpr_skip_token_tic716, born tic 700) "
            "durable home elsewhere -->\n")
        self.assertNotIn("cpr_skip_token_tic716", idx)


class TestReview719VerbAdmissionsAndLoudCounter(_HermeticHome):
    """/review-719 first-consumer patch (3a40ab346adb, PROMOTE-as-ray + patch,
    Architect-ratified): the census-residue and measured compound heads are
    ADMITTED, and any FUTURE head that fails the alternation is surfaced by the
    unmatched-provenance-shape loud counter instead of dropping out silently.
    Both arms of every documented conditional are exercised."""

    def _run(self, text):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(text, encoding="utf-8")
        with tmp:
            diag = {}
            idx = rcc.build_inscribed_index(str(root), diagnostics=diag)
            return idx, diag

    def test_admitted_heads_all_indexed(self):
        heads = {
            "INSCRIBED": "cpr_inscribed_head_tic719",
            "review-executed": "cpr_review_executed_head_tic719",
            "CONDITIONAL-PROMOTED": "cpr_conditional_head_tic719",
            "MERGE": "cpr_merge_head_tic719",
            "REINFORCED": "cpr_reinforced_head_tic719",
        }
        text = "".join(
            f"<!-- {head} at /review 719, from {token}. -->\n"
            for head, token in heads.items()
        )
        idx, diag = self._run(text)
        for token in heads.values():
            self.assertIn(token, idx)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)

    def test_novel_head_fires_loud_counter_not_index(self):
        idx, diag = self._run(
            "<!-- RATIFIED-INTO some-entry, from cpr_novel_head_tic719. -->\n")
        self.assertNotIn("cpr_novel_head_tic719", idx)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 1)
        sample = diag["unmatched_provenance_shaped_samples"][0]
        self.assertIn("cpr_novel_head_tic719", sample["tokens"])
        self.assertTrue(sample["head"].startswith("<!-- RATIFIED-INTO"))

    def test_skip_head_not_counted_by_loud_counter(self):
        idx, diag = self._run(
            "<!-- SKIP-WITH-HOME POINTER (cpr_skip_loud_tic719) home elsewhere -->\n")
        self.assertNotIn("cpr_skip_loud_tic719", idx)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)

    def test_reserved_only_comment_not_counted(self):
        # A comment whose only token is a reserved sibling-namespace label is
        # metadata, not a shed inscription witness.
        _, diag = self._run("<!-- era boundary marker cpr_era_tic_700_749 -->\n")
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)

    def test_tokenless_unmatched_comment_not_counted(self):
        _, diag = self._run("<!-- an ordinary prose comment, no ids at all -->\n")
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)

    def test_merged_still_admitted_longest_first(self):
        # `merge` was added AFTER `merged` — the longer form must keep matching.
        idx, diag = self._run(
            "<!-- merged from cpr_merged_form_tic719 + cpr_other_form_tic719 -->\n")
        self.assertIn("cpr_merged_form_tic719", idx)
        self.assertEqual(diag["unmatched_provenance_shaped_count"], 0)


class TestReportCarriesUnitBesideInteger(unittest.TestCase):
    def test_report_block_publishes_inscribed_index_unit(self):
        # Generator-enforce: the report dict publishes the unit declaration
        # BESIDE the integer, keyed inscribed_index_unit.
        i_size = _SRC.index('"inscribed_index_size": len(inscribed_ids)')
        i_unit = _SRC.index('"inscribed_index_unit": inscribed_diagnostics.get("unit_declaration")')
        self.assertGreater(i_unit, i_size)
        # ...and within the same report-literal neighborhood (beside, not far).
        self.assertLess(i_unit - i_size, 600)


class TestAudienceHandleCureWiring(unittest.TestCase):
    """Generator-enforce arms for the /review 716 AUDIENCE/HANDLE cure."""

    def test_live_artifact_receipt_written_before_output_write(self):
        i_assign = _SRC.index('report["superseded_receipt"] = superseded_receipt')
        i_write = _SRC.index('Path(output_path).write_text', i_assign)
        self.assertGreater(i_write, i_assign,
                           "the live-artifact receipt must land BEFORE the write")

    def test_sidecar_backstamp_beside_preserved_copy(self):
        self.assertIn('preserved_abs + ".superseded-by.json"', _SRC)
        # The preserved copy itself stays raw-bytes (write_bytes of prior_raw
        # unchanged — the /review 685 preservation law).
        self.assertIn("Path(preserved_abs).write_bytes(prior_raw)", _SRC)

    def test_superseded_receipt_is_comparison_volatile(self):
        self.assertIn('_volatile = ("generated_at", "superseded_receipt")', _SRC)

    def test_log_row_still_carries_receipt_producer_lane_intact(self):
        # The cure ADDS an audience; it never removes the producer-lane sink.
        self.assertIn('log_entry["superseded_receipt"] = superseded_receipt',
                      _SRC.replace("\n        ", "\n"))
        # tolerant match: the exact line exists with its original indentation
        self.assertIn('log_entry["superseded_receipt"] = superseded_receipt', _SRC)


class TestRider1AdmissionRouteDisclosureParity(_HermeticHome):
    """/review 724 RIDER 1: boundary_rule enumerates EVERY admission route the
    boundary cannot discriminate — including the tic-721 FILENAME-substring route
    the sibling-narration rationale never covered — and the structurally
    countable routes are MEASURED at runtime, never asserted as frozen numbers.
    Admission is unchanged: this is disclosure parity, not gating."""

    def _run(self, text):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(text, encoding="utf-8")
        with tmp:
            diag = {}
            idx = rcc.build_inscribed_index(str(root), diagnostics=diag)
            return idx, diag["unit_declaration"]

    # --- the enumeration itself ---------------------------------------------

    def test_boundary_rule_enumerates_the_filename_substring_route(self):
        _, ud = self._run("<!-- promoted from cpr_head_tic724 -->\n")
        rule = ud["boundary_rule"]
        # The tic-721 route is named explicitly, with its concrete shape.
        self.assertIn("FILENAME", rule)
        self.assertIn("DONE_cpr_stepper_advance_tic718.json", rule)
        # ...and the pre-724 route is not dropped in the process.
        self.assertIn("NARRATED", rule)

    def test_boundary_rule_enumerates_every_mechanism_derived_route(self):
        _, ud = self._run("<!-- promoted from cpr_head_tic724 -->\n")
        rule = ud["boundary_rule"].lower()
        for fragment in (
            "head-subject",                 # (a) intended witness
            "narrated",                     # (b) sibling narration
            "filename",                     # (c) tic-721 route
            "longer identifier",            # (d) generalization
            "greedy right extension",       # (e) right over-run
            "cogpr-n",                      # (f) numeric form
            "polarity",                     # (g) contrastive/negated
            "fence",                        # (h) documentary occurrence
            "queue id namespace",           # (i) unresolved-but-admitted
            "not content-deduplicated",     # (j) population vs unit
        ):
            self.assertIn(fragment, rule, f"boundary_rule must enumerate: {fragment}")

    def test_declaration_is_disclosure_not_gating(self):
        _, ud = self._run("<!-- promoted from cpr_head_tic724 -->\n")
        self.assertIn("not gating", ud["boundary_rule"].lower())

    def test_every_declared_route_carries_mechanism_and_countability(self):
        _, ud = self._run("<!-- promoted from cpr_head_tic724 -->\n")
        routes = ud["admission_routes_not_discriminable"]
        self.assertGreaterEqual(len(routes), 10)
        counters = ud["route_occurrence_counts"]
        for r in routes:
            self.assertIn("route", r)
            self.assertIn("mechanism", r)
            self.assertIn("machine_countable", r)
            # machine_countable:True must point at a counter that really exists;
            # machine_countable:False must NOT claim one (not countable by
            # construction — that asymmetry IS the disclosure).
            if r["machine_countable"] is True and r["counter"] in counters:
                self.assertIsInstance(counters[r["counter"]], int)
            if r["machine_countable"] is False:
                self.assertIsNone(r["counter"])

    # --- the routes, measured -------------------------------------------------

    def test_filename_substring_route_counted_sampled_and_still_admitted(self):
        idx, ud = self._run(
            "<!-- promoted from cpr_head_tic724. "
            "Source: DONE_cpr_sibling_advance_tic718.json A1 finding -->\n")
        counts = ud["route_occurrence_counts"]
        # ADMISSION UNCHANGED — the filename-borne token is still indexed.
        self.assertIn("cpr_sibling_advance_tic718", idx)
        self.assertIn("cpr_head_tic724", idx)
        # ...and now DISCLOSED as the filename route.
        self.assertEqual(counts["substring_of_cited_filename_or_path"], 1)
        self.assertEqual(counts["substring_of_longer_identifier"], 1)
        samples = ud["substring_route_samples"]
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["admitted_token"], "cpr_sibling_advance_tic718")
        self.assertEqual(samples[0]["enclosing_identifier"],
                         "DONE_cpr_sibling_advance_tic718.json")
        self.assertEqual(samples[0]["route"],
                         "cpr_shaped_substring_of_a_cited_FILENAME_or_PATH")

    def test_longer_identifier_route_distinguished_from_filename_route(self):
        # The other arm of the enclosing-run conditional: an entity name is a
        # longer identifier but NOT a filename/path.
        idx, ud = self._run(
            "<!-- promoted from cpr_head_tic724. Source: tic 573 ent_cpr_stepper -->\n")
        counts = ud["route_occurrence_counts"]
        self.assertIn("cpr_stepper", idx)
        self.assertEqual(counts["substring_of_longer_identifier"], 1)
        self.assertEqual(counts["substring_of_cited_filename_or_path"], 0)
        self.assertEqual(ud["substring_route_samples"][0]["enclosing_identifier"], None)
        self.assertEqual(ud["substring_route_samples"][0]["route"],
                         "cpr_shaped_substring_of_ANY_longer_identifier")

    def test_clean_comment_fires_no_substring_route(self):
        # Negative arm: a well-formed breadcrumb triggers neither substring route.
        _, ud = self._run("<!-- promoted from cpr_head_tic724 (tic 724) -->\n")
        counts = ud["route_occurrence_counts"]
        self.assertEqual(counts["substring_of_longer_identifier"], 0)
        self.assertEqual(counts["substring_of_cited_filename_or_path"], 0)
        self.assertEqual(ud["substring_route_samples"], [])

    def test_head_and_body_scope_partition_occurrences(self):
        _, ud = self._run(
            "<!-- promoted from cpr_a_tic724, extended by cpr_b_tic724 -->\n"
            "<!-- promoted from cpr_c_tic724 -->\n")
        counts = ud["route_occurrence_counts"]
        self.assertEqual(counts["head_subject_token"], 2)   # one per comment
        self.assertEqual(counts["body_scope_token"], 1)     # the narrated sibling

    def test_cogpr_numeric_form_counted(self):
        _, ud = self._run(
            "<!-- promoted from CogPR-71, extended by CogPR-87 -->\n")
        self.assertEqual(ud["route_occurrence_counts"]["cogpr_numeric_form"], 2)

    def test_greedy_right_extension_counted_only_against_queue_namespace(self):
        # Both arms: with queue_ids the over-run is measurable; without them the
        # counter cannot claim a route it has no namespace to judge against.
        text = "<!-- promoted from cpr_real_tic724_envelope -->\n"
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "CLAUDE.md").write_text(text, encoding="utf-8")
        with tmp:
            diag = {}
            rcc.build_inscribed_index(
                str(root), queue_ids={"cpr_real_tic724"}, diagnostics=diag)
            self.assertEqual(
                diag["unit_declaration"]["route_occurrence_counts"]
                ["greedy_right_extension"], 1)
            diag2 = {}
            rcc.build_inscribed_index(str(root), diagnostics=diag2)
            self.assertEqual(
                diag2["unit_declaration"]["route_occurrence_counts"]
                ["greedy_right_extension"], 0)

    def test_enclosing_pathish_run_helper_both_arms(self):
        seg = "Source: DONE_cpr_x_tic1.json and ent_cpr_y here"
        i = seg.index("cpr_x_tic1")
        self.assertEqual(
            rcc._enclosing_pathish_run(seg, i, i + len("cpr_x_tic1")),
            "DONE_cpr_x_tic1.json")
        j = seg.index("cpr_y")
        self.assertIsNone(rcc._enclosing_pathish_run(seg, j, j + len("cpr_y")))
        # A bare token with no enclosing run at all.
        bare = "from cpr_z tic 1"
        k = bare.index("cpr_z")
        self.assertIsNone(rcc._enclosing_pathish_run(bare, k, k + len("cpr_z")))


class _ZoneRun(_HermeticHome):
    """Zone fixture for run_check integration (RIDER 2)."""

    ENV_TIC = "CGG_OBLIGATION_TIC"
    ENV_MID = "CGG_OBLIGATION_MANDATE_ID"

    def setUp(self):
        super().setUp()
        self._zone_tmp = tempfile.TemporaryDirectory()
        self.zone = Path(self._zone_tmp.name)
        (self.zone / "audit-logs" / "cprs").mkdir(parents=True)
        (self.zone / "audit-logs" / "cprs" / "queue.jsonl").write_text("", encoding="utf-8")
        self._saved = {k: os.environ.pop(k, None)
                       for k in (self.ENV_TIC, self.ENV_MID)}

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._zone_tmp.cleanup()
        super().tearDown()

    def _claude_md(self, text):
        (self.zone / "CLAUDE.md").write_text(text, encoding="utf-8")

    def _run_at(self, tic, dry_run=False):
        os.environ[self.ENV_TIC] = str(tic)
        return rcc.run_check(str(self.zone), dry_run=dry_run)

    def _report_dir(self):
        return self.zone / "audit-logs" / "mogul" / "cycle-reports" / "review-close-checks"


class TestRider2PerUnitDelta(_ZoneRun):
    """/review 724 RIDER 2: the counter owes a per-pass PER-UNIT DELTA in each of
    its declared units, plus the collapse flag. No fabricated zeros."""

    def test_null_baseline_arm_emits_nulls_not_zeros(self):
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        rep = self._run_at(700)
        d = rep["inscribed_index_delta"]
        self.assertTrue(d["delta_baseline_absent"])
        self.assertIsNone(d["delta_tokens"])
        self.assertIsNone(d["delta_matched_comments"])
        self.assertIsNone(d["units_collapsed_this_pass"])
        self.assertEqual(d["baseline"]["reason_absent"], "no_prior_pass_artifact")
        # The current-side measurements are still first-class.
        self.assertEqual(d["current_tokens"], rep["inscribed_index_size"])
        self.assertEqual(d["current_matched_comments"], 1)

    def test_delta_computed_against_previous_pass_artifact(self):
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        self._run_at(700)
        self._claude_md(
            "<!-- promoted from cpr_one_tic700 -->\n"
            "<!-- promoted from cpr_two_tic701 -->\n")
        rep = self._run_at(701)
        d = rep["inscribed_index_delta"]
        self.assertFalse(d["delta_baseline_absent"])
        self.assertEqual(d["baseline"]["artifact"], "tic-700-check.json")
        self.assertEqual(d["baseline"]["selector"], "tic_keyed_prior_tic_700")
        self.assertEqual(d["delta_tokens"], 1)
        self.assertEqual(d["delta_matched_comments"], 1)
        # One new comment carrying exactly one new token — the units moved in
        # lockstep, so this pass cannot tell them apart. Legible AS collapse.
        self.assertTrue(d["units_collapsed_this_pass"])

    def test_units_not_collapsed_when_deltas_differ(self):
        # The other arm: one new comment carrying TWO new tokens separates the
        # units — the token unit moved +2 while the population moved +1.
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        self._run_at(700)
        self._claude_md(
            "<!-- promoted from cpr_one_tic700 -->\n"
            "<!-- promoted from cpr_two_tic701 merged with cpr_three_tic701 -->\n")
        rep = self._run_at(701)
        d = rep["inscribed_index_delta"]
        self.assertEqual(d["delta_tokens"], 2)
        self.assertEqual(d["delta_matched_comments"], 1)
        self.assertFalse(d["units_collapsed_this_pass"])

    def test_negative_delta_is_reported_not_clamped(self):
        self._claude_md(
            "<!-- promoted from cpr_one_tic700 -->\n"
            "<!-- promoted from cpr_two_tic700 -->\n")
        self._run_at(700)
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        rep = self._run_at(701)
        d = rep["inscribed_index_delta"]
        self.assertEqual(d["delta_tokens"], -1)
        self.assertEqual(d["delta_matched_comments"], -1)

    def test_same_tic_reobservation_reuses_the_same_baseline(self):
        """A same-tic re-run is the SAME pass re-run, not a new pass: the run's
        own artifact is excluded from the baseline search, so the delta does not
        silently reset to 0/0 (which would manufacture a content change and
        break the dedup skip branch the /review-685 preservation law needs)."""
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        self._run_at(700)
        self._claude_md(
            "<!-- promoted from cpr_one_tic700 -->\n"
            "<!-- promoted from cpr_two_tic701 -->\n")
        first = self._run_at(701)["inscribed_index_delta"]
        second = self._run_at(701)["inscribed_index_delta"]
        self.assertEqual(first, second)
        self.assertEqual(second["delta_tokens"], 1)
        self.assertEqual(second["baseline"]["artifact"], "tic-700-check.json")

    def test_first_write_and_same_tic_rerun_emit_identical_delta_block(self):
        """The no-baseline arm of the same-pass rule: a first write (lane absent)
        and its same-tic re-run (lane now exists, still holding only this run's
        own artifact) must report the SAME 'no baseline' state. Splitting them
        would manufacture a content delta on an otherwise-identical re-run and
        route it to `replace`, minting a superseded copy for nothing."""
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        first = self._run_at(700)["inscribed_index_delta"]
        second = self._run_at(700)["inscribed_index_delta"]
        self.assertEqual(first, second)
        self.assertEqual(second["baseline"]["reason_absent"], "no_prior_pass_artifact")

    def test_prior_artifact_predating_the_fields_is_absent_not_zero(self):
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        self._run_at(700)
        legacy = self._report_dir() / "tic-700-check.json"
        legacy.write_text(json.dumps({"check_type": "review_close_check"}),
                          encoding="utf-8")
        rep = self._run_at(701)
        d = rep["inscribed_index_delta"]
        self.assertTrue(d["delta_baseline_absent"])
        self.assertIsNone(d["delta_tokens"])
        self.assertIsNone(d["units_collapsed_this_pass"])
        self.assertEqual(d["baseline"]["reason_absent"],
                         "prior_artifact_predates_these_fields")

    def test_unreadable_prior_artifact_is_absent_not_zero(self):
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        self._run_at(700)
        (self._report_dir() / "tic-700-check.json").write_text(
            "{not json —", encoding="utf-8")
        d = self._run_at(701)["inscribed_index_delta"]
        self.assertTrue(d["delta_baseline_absent"])
        self.assertIsNone(d["delta_tokens"])
        self.assertEqual(d["baseline"]["reason_absent"], "prior_artifact_unreadable")

    def test_superseded_lane_is_not_a_pass_in_the_series(self):
        # The preservation lane must never be selected as a baseline.
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        self._run_at(700)
        sup = self._report_dir() / "superseded"
        sup.mkdir(parents=True, exist_ok=True)
        (sup / "tic-9999-check.superseded-1.json").write_text(
            json.dumps({"inscribed_index_size": 999,
                        "inscribed_index_unit": {"matched_comment_count": 999}}),
            encoding="utf-8")
        d = self._run_at(701)["inscribed_index_delta"]
        self.assertEqual(d["baseline"]["artifact"], "tic-700-check.json")

    def test_delta_present_in_dry_run_without_touching_disk(self):
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        rep = self._run_at(700, dry_run=True)
        self.assertIn("inscribed_index_delta", rep)
        self.assertTrue(rep["inscribed_index_delta"]["delta_baseline_absent"])
        self.assertFalse(self._report_dir().exists(),
                         "dry-run must not create the artifact lane")

    def test_delta_lands_in_the_written_artifact(self):
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        self._run_at(700)
        self._claude_md(
            "<!-- promoted from cpr_one_tic700 -->\n"
            "<!-- promoted from cpr_two_tic701 -->\n")
        self._run_at(701)
        on_disk = json.loads(
            (self._report_dir() / "tic-701-check.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["inscribed_index_delta"]["delta_tokens"], 1)
        self.assertTrue(on_disk["inscribed_index_delta"]["units_collapsed_this_pass"])
        # RIDER 1's enumeration reaches the artifact too.
        self.assertIn("FILENAME", on_disk["inscribed_index_unit"]["boundary_rule"])


class TestRider2ArtifactIdentityHoistIsSingleComputation(unittest.TestCase):
    """The output filename is computed ONCE and reused by both consumers (the
    delta's self-exclusion and the writer) — a second computation would let the
    two disagree, which is the divergence the /review-715 discipline forbids."""

    def test_single_filename_computation_site(self):
        self.assertEqual(_SRC.count("_canonical_output_filename("), 2,
                         "expected def + exactly one call site")

    def test_delta_excludes_the_runs_own_artifact(self):
        i_name = _SRC.index("output_filename, identity_kind = _canonical_output_filename(")
        i_delta = _SRC.index("index_delta = compute_unit_deltas(", i_name)
        i_write = _SRC.index("output_path = os.path.join(report_dir, output_filename)")
        self.assertLess(i_name, i_delta)
        self.assertLess(i_delta, i_write)

    def test_identity_ladder_warnings_stay_in_the_write_path(self):
        # Hoisting the computation must not hoist the WARNINGS — only a write
        # can degrade an artifact's identity.
        i_dryrun = _SRC.index("if not dry_run:")
        self.assertGreater(_SRC.index("falling back to mandate-keyed identity"), i_dryrun)
        self.assertGreater(_SRC.index("falling back to timestamp identity"), i_dryrun)


class TestObligationScopeVerdictCountDelta(_ZoneRun):
    """/review 728 obligation-scope ray (c209995ad848): a per-pass delta
    obligation landed on one counter attaches to EVERY counter on the same
    artifact surface — verdict_counts ships its own delta block, and the
    cross-counter disclosure is a typed question, never an asserted invariant."""

    def _queue(self, rows):
        (self.zone / "audit-logs" / "cprs" / "queue.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

    def test_null_baseline_arm_emits_nulls_not_zeros(self):
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        rep = self._run_at(700)
        d = rep["verdict_counts_delta"]
        self.assertTrue(d["delta_baseline_absent"])
        self.assertEqual(d["delta"], {"promoted": None, "deferred": None, "skipped": None})
        self.assertEqual(d["baseline"]["reason_absent"], "no_prior_pass_artifact")
        # Current-side counts are still first-class, and every counter carries
        # its declared unit (the /review-716 class-cure, now surface-wide).
        self.assertEqual(d["current"], rep["verdict_counts"])
        self.assertEqual(set(d["units"]), set(rep["verdict_counts"]))
        # Non-comparable cross-counter read is None, never fabricated agreement.
        x = rep["cross_counter_disclosure"]
        self.assertFalse(x["comparable"])
        self.assertIsNone(x["agree"])

    def test_delta_computed_against_previous_pass_artifact(self):
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        self._run_at(700)
        self._queue([{"id": "cpr_two_tic701", "status": "promoted",
                      "lesson": "x", "source": "s"}])
        self._claude_md(
            "<!-- promoted from cpr_one_tic700 -->\n"
            "<!-- promoted from cpr_two_tic701 -->\n")
        rep = self._run_at(701)
        d = rep["verdict_counts_delta"]
        self.assertFalse(d["delta_baseline_absent"])
        self.assertEqual(d["baseline"]["artifact"], "tic-700-check.json")
        self.assertEqual(d["delta"]["promoted"], 1)
        # Promoted +1 and tokens +1 — the two independently derived counters
        # agree, and the artifact now says so instead of leaving the hand-diff.
        x = rep["cross_counter_disclosure"]
        self.assertTrue(x["comparable"])
        self.assertEqual(x["promoted_delta"], 1)
        self.assertEqual(x["token_delta"], 1)
        self.assertTrue(x["agree"])

    def test_divergence_is_disclosed_not_asserted(self):
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        self._run_at(700)
        # A doctrine-surface edit adds a token with NO promotion behind it —
        # one of the named divergence routes. agree=False is a question with
        # routes attached, not a finding.
        self._claude_md(
            "<!-- promoted from cpr_one_tic700 -->\n"
            "<!-- promoted from cpr_two_tic701 -->\n")
        rep = self._run_at(701)
        x = rep["cross_counter_disclosure"]
        self.assertTrue(x["comparable"])
        self.assertEqual(x["promoted_delta"], 0)
        self.assertEqual(x["token_delta"], 1)
        self.assertFalse(x["agree"])
        self.assertIn("doctrine_edit_narrating_sibling_id_adds_token_without_promotion",
                      x["divergence_routes"])
        # Not a finding: divergence must not manufacture a hazard.
        self.assertNotIn("cross_counter", json.dumps(rep["findings"]))

    def test_prior_artifact_predating_fields_is_absent_not_zero(self):
        rd = self._report_dir()
        rd.mkdir(parents=True)
        (rd / "tic-700-check.json").write_text(
            json.dumps({"inscribed_index_size": 1,
                        "inscribed_index_unit": {"matched_comment_count": 1}}),
            encoding="utf-8")
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        rep = self._run_at(701)
        d = rep["verdict_counts_delta"]
        self.assertTrue(d["delta_baseline_absent"])
        self.assertEqual(d["baseline"]["reason_absent"],
                         "prior_artifact_predates_these_fields")
        self.assertEqual(d["delta"], {"promoted": None, "deferred": None, "skipped": None})

    def test_delta_lands_in_the_written_artifact(self):
        self._claude_md("<!-- promoted from cpr_one_tic700 -->\n")
        self._run_at(700)
        self._run_at(701)
        on_disk = json.loads(
            (self._report_dir() / "tic-701-check.json").read_text(encoding="utf-8"))
        self.assertIn("verdict_counts_delta", on_disk)
        self.assertIn("cross_counter_disclosure", on_disk)
        self.assertEqual(on_disk["verdict_counts_delta"]["delta"]["promoted"], 0)


if __name__ == "__main__":
    unittest.main()
