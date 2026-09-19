#!/usr/bin/env python3
"""Tests for the RUNG WALK's per-axis exclusion counts (tic 807).

RULED /review 804 round 2 (Ruling C) by ent_breyden (the Architect; recommended
option verbatim "Rule it, build after the 805 fire"), RELEASED to the build lane
at /review 806 round 1 (recommended option verbatim "Accept; release the build").
Spec:
audit-logs/governance/receipts/2026-09-19-tic804-ladder-audit-rung-walk-axis-counts-ruling.md
Release:
audit-logs/governance/receipts/2026-09-19-tic806-rung-walk-predicate-satisfied-by-lead-filed-witness-ruling.md

Answers F-803-LA-1 (MEDIUM) and F-803-LA-2 (LOW) of
audit-logs/governance/harpoon-office/cable-receipts/review803-ladder-audit-per-axis-count-lines-tic803.json.
F-803-LA-3 STAYS disclosed and UNCURED — the rider says so.

The contract under guard: `discover_active_rungs` publishes a COUNT per exclusion
axis — the skip-dirs test and the hidden-ancestor test at candidate collection,
and the newest-file walk's prune — mirroring the chain-walk cure. A prose mention
of a skip is not a cardinality. NO BEHAVIOUR CHANGE. The chain walk's noise-set
member that can never fire under first-match-wins (`.git`, caught earlier by the
hidden-directory axis) is DECLARED unreachable in place.

DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT give
`exclusion_axes` a consumer, does NOT change which rungs are admitted, and does
NOT extend the nested-repo predicate beyond the file's own parent (F-803-LA-3
stays disclosed in the predicate text).

THE TWO WALKS ORDER THEIR AXES OPPOSITELY — the fact this increment measured
rather than assumed:
  chain walk : hidden_directory THEN skip_dirs  -> `.git` UNREACHABLE on skip_dirs
  rung  walk : skip_dirs THEN hidden_ancestor   -> `.git` REACHABLE on skip_dirs
Both directions are proven BY EXECUTION below, not by reading the source.

TWO UNITS, NEVER SUMMED: the two candidate-collection axes count MARKER FILES and
reconcile; the newest-file prune counts DIRECTORY PRUNE EVENTS over a different
population and is excluded from the identity.

Arms (all mandatory):
  (a) each ruled axis fires with a KNOWN fixture count, scored member-exact where
      the axis enumerates members;
  (b) a ZERO arm — every count line still RENDERS at zero (a rendered zero is a
      disclosure; an omitted line is not);
  (c) the reconciliation identity holds, and the different-unit axis is excluded
      from it by declaration, not by accident;
  (d) the typed result carries the figures under the named key `exclusion_axes`
      and the RENDER emits one count line per axis WITH ITS UNIT;
  (e) NO BEHAVIOUR CHANGE: the admitted candidate-dir set and the active/dormant
      partition are identical to an INDEPENDENT re-implementation of the pre-cure
      predicates, and `_newest_file_days` keeps its 2-tuple arity;
  (f) the `.git` reachability asymmetry between the two walks, BY EXECUTION;
  (g) the rider travels verbatim into the constant, the typed result and the render.

Each case isolates against a TemporaryDirectory (Self-Locating Artifact Test
Isolation KI); nothing touches the real zone.

Run:  python3 -m unittest test_ladder_audit_rung_walk_axis_counts_tic807
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SPEC = importlib.util.spec_from_file_location(
    "ladder_audit", os.path.join(_HERE, "ladder-audit.py")
)
la = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(la)

# The tic-804 rider, verbatim from the RULING'S OWN TEXT. Any drift in the module
# constant, the typed result or the render is a TEST FAILURE, not a silent rot.
RIDER_VERBATIM_804 = (
    "this increment does NOT give `exclusion_axes` a consumer, does NOT change "
    "which rungs are admitted, and does NOT extend the nested-repo predicate "
    "beyond the file's own parent (F-803-LA-3 stays disclosed in the predicate "
    "text)."
)

RUNG_AXIS_KEYS = ("skip_dirs", "hidden_ancestor", "newest_file_prune")
RECONCILING_AXES = ("skip_dirs", "hidden_ancestor")


def _touch(root, rel, text="fixture\n"):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _ticzone(root, rel, name="fixt"):
    return _touch(root, rel, json.dumps({"name": name}) + "\n")


def _legacy_rung_candidate_oracle(root_str):
    """INDEPENDENT re-implementation of the PRE-tic-807 candidate collection.

    The no-behaviour-change ORACLE: the cured walk must collect EXACTLY this
    candidate-dir set. Deliberately a separate transcription of the original two
    predicates rather than a call into the module, so a regression in the cured
    walk cannot hide by also being present in the oracle.
    """
    root = Path(root_str)
    skip = {"node_modules", "__pycache__", ".git", "dist", "build", "target",
            "evals", "fixtures"}
    marker_names = sorted(set(la.RUNG_TOPOLOGY_MARKERS) | {".ticzone"})
    dirs = set()
    for marker in marker_names:
        for mp in sorted(root.rglob(marker)):
            parts = mp.relative_to(root).parts
            if any(p in skip for p in parts):
                continue
            if any(p.startswith(".") and p != ".claude" for p in parts[:-1]):
                continue
            rung_dir = mp.parent
            dirs.add(str(rung_dir.relative_to(root)) if rung_dir != root else ".")
    return sorted(dirs)


class _AllAxesRungZone(unittest.TestCase):
    """A fixture zone exercising EVERY ruled axis with a KNOWN count.

    KNOWN COUNTS (first-match-wins, in walk order: skip_dirs THEN hidden_ancestor):
      marker files scanned    8
      skip_dirs               3  — node_modules/, .git/ (!), evals/
      hidden_ancestor         2  — .hidden/, .secret/
      marker files admitted   3  — root .domain-root, root .ticzone, good/.domain-root
      candidate dirs          2  — "." and "good"  (root carries TWO markers -> dedup)
      newest_file_prune       9  — 7 prune events in the "." walk + 2 in the "good" walk
    """

    EXPECTED_COUNTS = {"skip_dirs": 3, "hidden_ancestor": 2, "newest_file_prune": 9}
    EXPECTED_SCANNED = 8
    EXPECTED_ADMITTED = 3
    EXPECTED_CANDIDATE_DIRS = ["." , "good"]
    EXPECTED_SKIP_MEMBERS = [
        ".git/sub/.domain-root",
        "evals/fixture-zone/.ticzone",
        "node_modules/inner/.domain-root",
    ]
    EXPECTED_HIDDEN_MEMBERS = [
        ".hidden/child/.domain-root",
        ".secret/.ticzone",
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

        # --- admitted: root carries TWO markers (the dedup arm) ---
        _touch(self.root, ".domain-root", "")
        _ticzone(self.root, ".ticzone")
        # --- admitted: a governed child rung ---
        _touch(self.root, "good/.domain-root", "")
        _touch(self.root, "good/file.txt")
        # --- newest-file prune fodder inside an admitted rung ---
        _touch(self.root, "good/node_modules/junk.txt")
        _touch(self.root, "good/.cache/junk.txt")
        # --- skip_dirs (3) ---
        _touch(self.root, "node_modules/inner/.domain-root", "")
        _ticzone(self.root, "evals/fixture-zone/.ticzone")
        # `.git` is in _RUNG_SKIP_DIRS *and* is a dotted ancestor. On THIS walk
        # skip_dirs runs FIRST, so it must land on skip_dirs — the reachability
        # arm that distinguishes this walk from the chain walk.
        _touch(self.root, ".git/sub/.domain-root", "")
        # --- hidden_ancestor (2) ---
        _touch(self.root, ".hidden/child/.domain-root", "")
        _ticzone(self.root, ".secret/.ticzone")

    def disclose(self):
        return la.discover_active_rungs(self.root)["exclusion_axes"]


class TestEachRuledAxisFiresWithAKnownCount(_AllAxesRungZone):
    """(a) every ruled axis is counted, at its KNOWN fixture count."""

    def test_all_three_ruled_axes_present_in_walk_order(self):
        axes = [a["axis"] for a in self.disclose()["axes"]]
        self.assertEqual(axes, list(RUNG_AXIS_KEYS),
                         "the disclosure must publish every ruled axis, in the "
                         "order the walk applies them")

    def test_each_axis_count_matches_the_known_fixture_count(self):
        by_axis = {a["axis"]: a["count"] for a in self.disclose()["axes"]}
        for axis, expected in self.EXPECTED_COUNTS.items():
            self.assertEqual(by_axis[axis], expected,
                             f"axis `{axis}` counted {by_axis[axis]}, "
                             f"fixture plants {expected}")

    def test_skip_dirs_members_are_member_exact(self):
        ax = next(a for a in self.disclose()["axes"] if a["axis"] == "skip_dirs")
        self.assertEqual(sorted(ax["members"]), sorted(self.EXPECTED_SKIP_MEMBERS))
        self.assertEqual(len(ax["members"]), ax["count"],
                         "the enumerated member list must be the SAME cardinality "
                         "as the published count")

    def test_hidden_ancestor_members_are_member_exact(self):
        ax = next(a for a in self.disclose()["axes"]
                  if a["axis"] == "hidden_ancestor")
        self.assertEqual(sorted(ax["members"]),
                         sorted(self.EXPECTED_HIDDEN_MEMBERS))
        self.assertEqual(len(ax["members"]), ax["count"])

    def test_marker_file_totals(self):
        d = self.disclose()
        self.assertEqual(d["marker_files_scanned"], self.EXPECTED_SCANNED)
        self.assertEqual(d["marker_files_admitted"], self.EXPECTED_ADMITTED)

    def test_every_axis_carries_predicate_reason_unit_and_population(self):
        for a in self.disclose()["axes"]:
            self.assertTrue(a["predicate"], f"{a['axis']} has no predicate")
            self.assertTrue(a["reason"], f"{a['axis']} has no reason")
            self.assertTrue(a["unit"], f"{a['axis']} has no unit")
            self.assertTrue(a["population"], f"{a['axis']} has no population")


class TestReconciliationAndUnits(_AllAxesRungZone):
    """(c) the identity holds, and the different-unit axis is excluded from it
    BY DECLARATION — never summed in by accident."""

    def test_reconciliation_identity_holds(self):
        d = self.disclose()
        self.assertTrue(d["reconciles"])
        self.assertEqual(
            d["marker_files_scanned"],
            d["marker_files_admitted"] + d["reconciled_exclusions"],
            "marker_files_scanned must partition into admitted + the marker-file "
            "exclusion axes")
        self.assertEqual(d["reconciled_exclusions"],
                         self.EXPECTED_COUNTS["skip_dirs"]
                         + self.EXPECTED_COUNTS["hidden_ancestor"])

    def test_prune_axis_is_excluded_from_the_identity(self):
        d = self.disclose()
        by_axis = {a["axis"]: a for a in d["axes"]}
        self.assertFalse(by_axis["newest_file_prune"]["in_reconciliation"],
                         "the prune axis counts DIRECTORY EVENTS over a different "
                         "population — summing it into a marker-file identity is a "
                         "unit error")
        for axis in RECONCILING_AXES:
            self.assertTrue(by_axis[axis]["in_reconciliation"])

    def test_the_two_units_are_distinct_and_declared(self):
        by_axis = {a["axis"]: a for a in self.disclose()["axes"]}
        self.assertEqual(by_axis["skip_dirs"]["unit"], "marker_files")
        self.assertEqual(by_axis["hidden_ancestor"]["unit"], "marker_files")
        self.assertEqual(by_axis["newest_file_prune"]["unit"],
                         "directory_prune_events")

    def test_prune_count_excluded_even_though_it_would_change_the_sum(self):
        """A guard with teeth: the prune count is NON-ZERO here, so an accidental
        sum would visibly break the identity."""
        d = self.disclose()
        prune = next(a["count"] for a in d["axes"]
                     if a["axis"] == "newest_file_prune")
        self.assertGreater(prune, 0, "fixture must make the prune axis non-zero")
        self.assertNotEqual(
            d["marker_files_scanned"],
            d["marker_files_admitted"] + d["reconciled_exclusions"] + prune)

    def test_candidate_dir_dedup_and_partition(self):
        result = la.discover_active_rungs(self.root)
        d = result["exclusion_axes"]
        self.assertEqual(d["candidate_dir_count"], len(self.EXPECTED_CANDIDATE_DIRS))
        self.assertLess(d["candidate_dir_count"], d["marker_files_admitted"],
                        "the fixture's root carries TWO markers, so the dir count "
                        "must be strictly below the admitted marker-file count")
        self.assertEqual(d["candidate_dir_count"],
                         result["active_count"] + result["dormant_count"])

    def test_counting_discipline_discloses_the_opposite_order(self):
        d = self.disclose()
        self.assertIn("FIRST-MATCH-WINS", d["counting_discipline"])
        self.assertIn("OPPOSITE", d["counting_discipline"])
        self.assertIn("PARTITION", d["counting_discipline"])
        self.assertIn("NEVER SUMMED", d["unit_discipline"])
        self.assertTrue(d["_law"])


class TestGitReachabilityAsymmetryByExecution(_AllAxesRungZone):
    """(f) the `.git` asymmetry between the two walks, proven BY EXECUTION."""

    def test_git_IS_reachable_on_the_rung_walks_skip_dirs(self):
        ax = {a["axis"]: a for a in self.disclose()["axes"]}
        self.assertIn(".git/sub/.domain-root", ax["skip_dirs"]["members"],
                      "the rung walk tests skip_dirs FIRST, so a `.git` path must "
                      "be counted there")
        self.assertNotIn(".git/sub/.domain-root",
                         ax["hidden_ancestor"]["members"],
                         "first-match-wins: it must NOT also appear on the later "
                         "hidden_ancestor axis")

    def test_git_is_UNREACHABLE_on_the_chain_walks_skip_dirs(self):
        """The chain walk orders hidden_directory FIRST, so the `.git` member of
        CHAIN_NOISE_SKIP_DIRS can never fire. Shown by running the chain walk on a
        zone whose ONLY exclusion is a `.git` path."""
        with tempfile.TemporaryDirectory() as tmp:
            _touch(tmp, "CLAUDE.md", "# root\n")
            _touch(tmp, ".git/x/CLAUDE.md", "# inside .git\n")
            _found, _mem, axes = la.discover_claude_mds_with_disclosure(tmp)
            by_axis = {a["axis"]: a["count"] for a in axes["axes"]}
            self.assertEqual(by_axis["hidden_directory"], 1,
                             "the `.git` path must land on hidden_directory")
            self.assertEqual(by_axis["skip_dirs"], 0,
                             "the `.git` member of CHAIN_NOISE_SKIP_DIRS is "
                             "structurally unreachable at that locus")

    def test_the_chain_walk_DECLARES_the_unreachability_in_its_disclosure(self):
        """Declared in place, not removed — and the declaration reaches a REPORT
        reader, not only a source reader."""
        self.assertIn(".git", la.CHAIN_NOISE_SKIP_DIRS,
                      "the member is DECLARED unreachable, never removed")
        spec = next(a for a in la.NON_MEMBERSHIP_EXCLUSION_AXES
                    if a["axis"] == "skip_dirs")
        self.assertIn("UNREACHABLE", spec["predicate"])

    def test_the_rung_walk_skip_set_still_carries_git(self):
        self.assertIn(".git", la._RUNG_SKIP_DIRS,
                      "reachable here — removing it WOULD change behaviour")


class TestTypedKeyAndRender(_AllAxesRungZone):
    """(d) the typed named key + the rendered count lines with their units."""

    def test_typed_result_carries_exclusion_axes(self):
        result = la.discover_active_rungs(self.root)
        self.assertIn("exclusion_axes", result,
                      "the typed result must carry the per-axis figures under a "
                      "named key so a consumer need not parse prose")
        json.dumps(result)  # the Stage-0 result is emitted as JSON

    def test_one_count_line_per_axis_with_its_unit(self):
        text = la.format_active_rungs(la.discover_active_rungs(self.root))
        for axis, expected in self.EXPECTED_COUNTS.items():
            self.assertIn(f"Excluded ({axis}): {expected}", text,
                          f"no header count line for axis `{axis}`")
        self.assertIn("[marker_files]", text)
        self.assertIn("[directory_prune_events]", text)

    def test_axis_section_rendered_with_predicate_reason_population(self):
        text = la.format_active_rungs(la.discover_active_rungs(self.root))
        self.assertIn("EXCLUSION AXES (rung discovery", text)
        for axis in RUNG_AXIS_KEYS:
            self.assertIn(f"[{axis}] excluded:", text)
        self.assertIn("population:", text)
        self.assertIn("predicate:", text)
        self.assertIn("reason:", text)
        self.assertIn("NOT in reconciliation", text)

    def test_render_carries_the_reconciliation_and_the_dedup_note(self):
        text = la.format_active_rungs(la.discover_active_rungs(self.root))
        self.assertIn(f"Scanned (marker files seen by the walk): "
                      f"{self.EXPECTED_SCANNED}", text)
        self.assertIn("Candidate rung dirs:", text)
        self.assertIn("reconciliation:", text)

    def test_members_rendered_by_path(self):
        text = la.format_active_rungs(la.discover_active_rungs(self.root))
        for member in self.EXPECTED_SKIP_MEMBERS + self.EXPECTED_HIDDEN_MEMBERS:
            self.assertIn(member, text)

    def test_preexisting_render_lines_untouched(self):
        text = la.format_active_rungs(la.discover_active_rungs(self.root))
        self.assertIn("LADDER DOWN-LANE · Stage-0 active-rung selector", text)
        self.assertIn("ACTIVE RUNGS", text)
        self.assertIn("DORMANT / EXCLUDED", text)
        self.assertIn("scope: ", text)


class TestRiderTravelsVerbatim(_AllAxesRungZone):
    """(g) the rider is byte-equal in the constant, the typed result, the render."""

    def test_rider_constant_is_verbatim(self):
        self.assertEqual(la.RUNG_DISCOVERY_DOES_NOT_SATISFY, RIDER_VERBATIM_804)

    def test_rider_travels_verbatim_in_the_typed_result(self):
        self.assertEqual(self.disclose()["does_not_satisfy"], RIDER_VERBATIM_804)

    def test_rider_travels_verbatim_in_the_render(self):
        text = la.format_active_rungs(la.discover_active_rungs(self.root))
        self.assertIn(RIDER_VERBATIM_804, text)


class TestZeroArm(unittest.TestCase):
    """(b) a rendered ZERO is a disclosure; an omitted line is not."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        _touch(self.root, "good/.domain-root", "")
        _touch(self.root, "good/file.txt")

    def test_every_axis_reads_zero(self):
        d = la.discover_active_rungs(self.root)["exclusion_axes"]
        self.assertEqual(len(d["axes"]), len(RUNG_AXIS_KEYS))
        for a in d["axes"]:
            self.assertEqual(a["count"], 0, f"{a['axis']} should be 0 here")
        for a in d["axes"]:
            if a["enumerates_members"]:
                self.assertEqual(a["members"], [],
                                 "honest-empty: an EMPTY LIST, never an absent key")
        self.assertEqual(d["marker_files_scanned"], 1)
        self.assertEqual(d["marker_files_admitted"], 1)
        self.assertEqual(d["candidate_dir_count"], 1)
        self.assertTrue(d["reconciles"])

    def test_render_still_publishes_every_zero_line(self):
        text = la.format_active_rungs(la.discover_active_rungs(self.root))
        for axis in RUNG_AXIS_KEYS:
            self.assertIn(f"Excluded ({axis}): 0", text,
                          f"axis `{axis}` went dark at zero — an omitted line is "
                          "not a disclosure")
        self.assertIn("[skip_dirs] excluded: 0", text)
        self.assertIn("(none)", text)


class TestNoBehaviourChange(_AllAxesRungZone):
    """(e) DISCLOSURE ONLY — which rungs are collected does not move."""

    def test_candidate_dirs_match_the_independent_legacy_oracle(self):
        result = la.discover_active_rungs(self.root)
        got = sorted(e["dir"] for e in result["active"] + result["dormant"])
        self.assertEqual(got, _legacy_rung_candidate_oracle(self.root),
                         "the cured walk collects a DIFFERENT candidate set than "
                         "the pre-cure predicates — this increment is disclosure "
                         "only")

    def test_candidate_dirs_are_the_declared_expected_set(self):
        result = la.discover_active_rungs(self.root)
        got = sorted(e["dir"] for e in result["active"] + result["dormant"])
        self.assertEqual(got, sorted(self.EXPECTED_CANDIDATE_DIRS))

    def test_every_preexisting_result_key_survives(self):
        result = la.discover_active_rungs(self.root)
        for key in ("audited_at", "zone_root", "window_days", "scope_declaration",
                    "active_count", "dormant_count", "active", "dormant"):
            self.assertIn(key, result, f"pre-existing key `{key}` disappeared")

    def test_every_preexisting_per_rung_key_survives(self):
        result = la.discover_active_rungs(self.root)
        for e in result["active"] + result["dormant"]:
            for key in ("rung", "dir", "markers", "own_clock", "agent_mailbox",
                        "signals", "recent_signals", "selected"):
                self.assertIn(key, e, f"per-rung key `{key}` disappeared")
            for key in ("own_ticzone_days", "git_last_commit_days",
                        "mailbox_recent_days", "marker_mtime_days",
                        "newest_file_days", "newest_file_scan_capped"):
                self.assertIn(key, e["signals"],
                              f"per-rung signal `{key}` disappeared")

    def test_newest_file_days_keeps_its_two_tuple_arity(self):
        """The pair helper's arity is preserved; the 3-returning sibling carries
        the disclosure (mirrors the tic-803 pair-helper discipline)."""
        pair = la._newest_file_days(os.path.join(self.root, "good"))
        self.assertEqual(len(pair), 2, "the pair helper must stay a PAIR")
        trio = la._newest_file_days_with_prune_disclosure(
            os.path.join(self.root, "good"))
        self.assertEqual(len(trio), 3)
        self.assertEqual(pair[1], trio[1], "capped flags must agree")
        self.assertEqual(trio[2], 2,
                         "the `good` subtree prunes node_modules/ and .cache/")

    def test_chain_walk_disclosure_is_untouched(self):
        """The tic-803 chain-walk contract is a SIBLING, not this increment's."""
        with tempfile.TemporaryDirectory() as tmp:
            _touch(tmp, "CLAUDE.md", "# root\n")
            _f, _m, axes = la.discover_claude_mds_with_disclosure(tmp)
            self.assertEqual([a["axis"] for a in axes["axes"]],
                             ["hidden_directory", "skip_dirs", "vendor_depth",
                              "nested_repo"])
            self.assertEqual(axes["does_not_satisfy"],
                             la.PER_AXIS_DISCLOSURE_DOES_NOT_SATISFY)


class TestEngineContentSeparation(_AllAxesRungZone):
    """The axis vocabulary is a declared, named set — not an inline literal."""

    def test_axis_spec_is_a_named_module_level_set(self):
        self.assertTrue(hasattr(la, "RUNG_EXCLUSION_AXES"))
        keys = [a["axis"] for a in la.RUNG_EXCLUSION_AXES]
        self.assertEqual(keys, list(RUNG_AXIS_KEYS))

    def test_each_spec_declares_its_unit_and_reconciliation_membership(self):
        for spec in la.RUNG_EXCLUSION_AXES:
            self.assertIn("unit", spec)
            self.assertIn("in_reconciliation", spec)
            self.assertIn("population", spec)

    def test_the_unruled_file_filter_is_disclosed_not_counted(self):
        """F-807-RW-1: the newest-file walk's sibling FILE filter is a further
        narrowing predicate the ruling does NOT name. It stays UNCOUNTED, and the
        prune axis's own predicate text says so rather than hiding it."""
        spec = next(a for a in la.RUNG_EXCLUSION_AXES
                    if a["axis"] == "newest_file_prune")
        self.assertIn("DOES NOT COUNT", spec["predicate"])
        self.assertIn("_NOISE_FILE_BASENAMES", spec["predicate"])


if __name__ == "__main__":
    unittest.main()
