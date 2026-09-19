#!/usr/bin/env python3
"""Tests for the ladder-audit PER-AXIS EXCLUSION COUNT LINES (tic 803).

RULED /review 803 round 1 Q1 (ent_breyden, the Architect; recommended option
verbatim "ABSORB + tail + rule cure"). Spec:
audit-logs/governance/receipts/2026-09-19-tic803-ladder-audit-per-axis-count-lines-ruling.md

Row cpr_mogul_ladder_audit_d458dbccb162 (birth 800), ABSORBED into guard 18 of
the presence-observation family (per-axis cardinality disclosure, born tic 735)
with the UNRENDERED-AXIS tail. THIRD recurrence of the per-axis family on this
one instrument (membership axis tic 688; type axis tic 735; noise axis tic 800)
— a Case 2: the law exists, the application was missing at its locus.

The contract under guard: the ladder-audit render publishes, BESIDE its existing
enumerated MEMBERSHIP exclusions, ONE COUNT LINE PER non-membership exclusion
axis the CLAUDE.md-chain discovery walk applies (hidden_directory, skip_dirs,
vendor_depth, nested_repo), each measured BY THE WALK ITSELF in the SAME pass.
The nested-repo axis additionally ENUMERATES ITS MEMBERS BY PATH, because its
members are governed surfaces (each a rung governing itself), not build noise.
The typed JSON report carries the same figures under the named key
`exclusion_axes`.

The tic-800 symptom: the rendered report printed `CLAUDE.md files: 6` and
`Fenced (membership): 2` and carried NO line for the NINE files dropped by the
nested-repo predicate, so a reader who honored every disclosure computed a
population of 8. The nine are CORRECTLY excluded; the verdict was right and the
disclosure was thin.

DOES-NOT-SATISFY RIDER (travels verbatim): this increment does NOT admit any
nested repo into the chain, does NOT audit any of the nine, does NOT change the
membership fence ruled at /review 688, and does NOT satisfy guard 18's type-axis
consumer (that one landed at /review 738).

Arms (all mandatory):
  (a) EVERY axis is counted, with a KNOWN count per axis on a fixture tree that
      exercises all four plus the membership fence and the admitted chain;
  (b) the nested-repo axis enumerates its MEMBERS BY PATH; the noise axes do not;
  (c) the typed JSON carries the figures under the named key `exclusion_axes`,
      including on the honest-empty path and the empty-chain error path;
  (d) the RENDER emits one count line per axis + the member enumeration;
  (e) NO BEHAVIOUR CHANGE: the admitted chain member set is identical to an
      INDEPENDENT re-implementation of the pre-cure predicates (the oracle), and
      the pair-returning helper's arity contract is intact;
  (f) the counting discipline (FIRST-MATCH-WINS) and the reconciliation identity
      are disclosed BESIDE the numbers, and the rider travels verbatim.

Each case isolates against a TemporaryDirectory (Self-Locating Artifact Test
Isolation KI); nothing touches the real zone.

Run:  python3 -m unittest test_ladder_audit_per_axis_exclusion_counts_tic803
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

# The rider, verbatim. Any drift in the module constant is a test failure.
RIDER_VERBATIM = (
    "this increment does NOT admit any nested repo into the chain, does NOT "
    "audit any of the nine, does NOT change the membership fence ruled at "
    "/review 688, and does NOT satisfy guard 18's type-axis consumer (that one "
    "landed at /review 738)."
)

AXIS_KEYS = ("hidden_directory", "skip_dirs", "vendor_depth", "nested_repo")

DOCTRINE = """# Fixture CLAUDE.md

## Key Invariants
- fixture body.
"""


def _write(root, rel, text=DOCTRINE):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _mkgit(root, rel_dir):
    """Plant a nested-repo marker: a real .git DIRECTORY at rel_dir."""
    p = Path(root) / rel_dir / ".git"
    p.mkdir(parents=True, exist_ok=True)
    (p / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    return p


def _rels(root, paths):
    return sorted(str(Path(p).relative_to(root)) for p in paths)


def _legacy_reference_walk(root_str):
    """INDEPENDENT re-implementation of the PRE-tic-803 discovery predicates.

    This is the no-behaviour-change ORACLE: the cured walk must admit EXACTLY
    this member set. It is deliberately a separate transcription of the original
    predicates rather than a call into the module, so a regression in the cured
    walk cannot hide by also being present in the oracle.
    """
    root = Path(root_str)
    skip_dirs = {"node_modules", "__pycache__", ".git", "dist", "build", "target"}
    found = []
    for md in sorted(root.rglob("CLAUDE.md")):
        rel = str(md.relative_to(root))
        parts = rel.split(os.sep)
        if la._membrane_marker(parts) is not None:
            continue
        if any(p.startswith(".") and p != ".claude" for p in parts):
            continue
        if any(p in skip_dirs for p in parts):
            continue
        vendor_idx = next((i for i, p in enumerate(parts) if p == "vendor"), -1)
        if vendor_idx >= 0 and (len(parts) - vendor_idx - 1) > 3:
            continue
        if (md.parent / ".git").exists() and md.parent != root:
            continue
        found.append(md)
    return found


class _AllAxesZone(unittest.TestCase):
    """A fixture tree exercising EVERY axis with a KNOWN count per axis.

    KNOWN COUNTS (first-match-wins, in walk order):
      membership       2  — agent-mailboxes + standalone harpoonTargets
      hidden_directory 2  — .hidden/ and .cache/deep/
      skip_dirs        3  — node_modules/, build/, dist/sub/
      vendor_depth     1  — vendor/a/b/c/d/  (depth below vendor == 5 > 3)
      nested_repo      2  — nested_repo_one/ and nested_repo_two/ (own .git)
      chain members    3  — root, governed child, vendor/a/b/ (depth 3, NOT > 3)
      scanned_total   13
    """

    EXPECTED = {
        "hidden_directory": 2,
        "skip_dirs": 3,
        "vendor_depth": 1,
        "nested_repo": 2,
    }
    EXPECTED_MEMBERSHIP = 2
    EXPECTED_SCANNED = 13
    EXPECTED_MEMBERS = [
        "CLAUDE.md",
        "governed/child/CLAUDE.md",
        os.path.join("vendor", "a", "b", "CLAUDE.md"),
    ]
    EXPECTED_NESTED_MEMBERS = [
        "nested_repo_one/CLAUDE.md",
        "nested_repo_two/CLAUDE.md",
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

        # --- admitted chain members (3) ---
        _write(self.root, "CLAUDE.md")
        _write(self.root, "governed/child/CLAUDE.md")
        # vendor at depth 3 below vendor/ -> NOT over the limit -> admitted.
        _write(self.root, "vendor/a/b/CLAUDE.md")

        # --- membership fence (2) ---
        _write(self.root, "audit-logs/agent-mailboxes/ent_x/CLAUDE.md")
        _write(self.root, "governance/harpoonTargets/queue/y/CLAUDE.md")

        # --- hidden_directory (2) ---
        _write(self.root, ".hidden/CLAUDE.md")
        _write(self.root, ".cache/deep/CLAUDE.md")

        # --- skip_dirs (3) ---
        _write(self.root, "node_modules/CLAUDE.md")
        _write(self.root, "build/CLAUDE.md")
        _write(self.root, "dist/sub/CLAUDE.md")

        # --- vendor_depth (1): depth below vendor == 5 ---
        _write(self.root, "vendor/a/b/c/d/CLAUDE.md")

        # --- nested_repo (2) ---
        _write(self.root, "nested_repo_one/CLAUDE.md")
        _mkgit(self.root, "nested_repo_one")
        _write(self.root, "nested_repo_two/CLAUDE.md")
        _mkgit(self.root, "nested_repo_two")

    def disclose(self):
        return la.discover_claude_mds_with_disclosure(self.root)


class TestEveryAxisCountedWithKnownCount(_AllAxesZone):
    """(a) every axis is counted, and each count is the KNOWN fixture count."""

    def test_all_four_axes_present_in_the_disclosure(self):
        _found, _mem, axes_disc = self.disclose()
        rendered = [a["axis"] for a in axes_disc["axes"]]
        self.assertEqual(rendered, list(AXIS_KEYS),
                         "the disclosure must publish every non-membership axis, "
                         "in the order the walk applies them")

    def test_each_axis_count_matches_the_known_fixture_count(self):
        _found, _mem, axes_disc = self.disclose()
        by_axis = {a["axis"]: a["count"] for a in axes_disc["axes"]}
        for axis, expected in self.EXPECTED.items():
            self.assertEqual(by_axis[axis], expected,
                             f"axis `{axis}` counted {by_axis[axis]}, "
                             f"fixture plants {expected}")

    def test_membership_axis_still_enumerated_and_unchanged(self):
        _found, membership, _axes = self.disclose()
        self.assertEqual(len(membership), self.EXPECTED_MEMBERSHIP)
        for e in membership:
            self.assertEqual(e["reason"], "assessment_membrane")

    def test_scanned_total_and_reconciliation_identity_hold(self):
        found, membership, axes_disc = self.disclose()
        self.assertEqual(axes_disc["scanned_total"], self.EXPECTED_SCANNED)
        self.assertEqual(axes_disc["chain_members"], len(found))
        self.assertEqual(axes_disc["membership_exclusions"], len(membership))
        self.assertEqual(axes_disc["non_membership_exclusions"],
                         sum(self.EXPECTED.values()))
        self.assertTrue(axes_disc["reconciles"])
        self.assertEqual(
            axes_disc["scanned_total"],
            axes_disc["chain_members"] + axes_disc["membership_exclusions"]
            + axes_disc["non_membership_exclusions"],
            "scanned_total must partition into chain + membership + non-membership")

    def test_counting_discipline_is_disclosed_beside_the_numbers(self):
        """(f) FIRST-MATCH-WINS is a narrowing predicate between cardinalities;
        guard 18 requires it to ride BESIDE the number, not sit in the source."""
        _f, _m, axes_disc = self.disclose()
        self.assertIn("FIRST-MATCH-WINS", axes_disc["counting_discipline"])
        self.assertIn("PARTITION", axes_disc["counting_discipline"])
        self.assertTrue(axes_disc["_law"])


class TestNestedRepoEnumeratesMembers(_AllAxesZone):
    """(b) the nested-repo axis names its members; the noise axes do not."""

    def test_nested_repo_members_enumerated_by_path(self):
        _f, _m, axes_disc = self.disclose()
        nested = next(a for a in axes_disc["axes"] if a["axis"] == "nested_repo")
        self.assertTrue(nested["enumerates_members"])
        self.assertEqual(sorted(nested["members"]),
                         sorted(self.EXPECTED_NESTED_MEMBERS))
        self.assertEqual(len(nested["members"]), nested["count"],
                         "the enumerated member list must be the SAME cardinality "
                         "as the published count")

    def test_noise_axes_publish_a_count_only(self):
        _f, _m, axes_disc = self.disclose()
        for a in axes_disc["axes"]:
            if a["axis"] == "nested_repo":
                continue
            self.assertFalse(a["enumerates_members"])
            self.assertNotIn("members", a,
                             f"noise axis `{a['axis']}` must publish a count only")

    def test_every_axis_entry_carries_its_predicate_and_reason(self):
        _f, _m, axes_disc = self.disclose()
        for a in axes_disc["axes"]:
            self.assertTrue(a["predicate"], f"{a['axis']} has no predicate")
            self.assertTrue(a["reason"], f"{a['axis']} has no reason")


class TestTypedReportNamedKey(_AllAxesZone):
    """(c) the typed JSON carries the figures under the named key."""

    def test_run_audit_carries_exclusion_axes(self):
        result = la.run_audit(self.root)
        self.assertIn("exclusion_axes", result,
                      "the typed report must carry the per-axis figures under a "
                      "named key so a consumer need not parse prose")
        by_axis = {a["axis"]: a["count"] for a in result["exclusion_axes"]["axes"]}
        for axis, expected in self.EXPECTED.items():
            self.assertEqual(by_axis[axis], expected)
        json.dumps(result)  # the audit packet is emitted as JSON

    def test_nested_repo_members_survive_into_the_typed_report(self):
        result = la.run_audit(self.root)
        nested = next(a for a in result["exclusion_axes"]["axes"]
                      if a["axis"] == "nested_repo")
        self.assertEqual(sorted(nested["members"]),
                         sorted(self.EXPECTED_NESTED_MEMBERS))

    def test_rider_travels_verbatim_in_the_typed_report(self):
        result = la.run_audit(self.root)
        self.assertEqual(result["exclusion_axes"]["does_not_satisfy"],
                         RIDER_VERBATIM)


class TestRenderPublishesOneCountLinePerAxis(_AllAxesZone):
    """(d) the RENDER emits one count line per axis + the member enumeration."""

    def test_one_count_line_per_axis_in_the_header(self):
        text = la.format_human_readable(la.run_audit(self.root))
        for axis, expected in self.EXPECTED.items():
            self.assertIn(f"Excluded ({axis}): {expected}", text,
                          f"no header count line for axis `{axis}`")

    def test_exclusion_axes_section_rendered(self):
        text = la.format_human_readable(la.run_audit(self.root))
        self.assertIn("EXCLUSION AXES", text)
        for axis in AXIS_KEYS:
            self.assertIn(f"[{axis}] excluded:", text)

    def test_nested_repo_members_rendered_by_path(self):
        text = la.format_human_readable(la.run_audit(self.root))
        for member in self.EXPECTED_NESTED_MEMBERS:
            self.assertIn(member, text,
                          "a nested-repo member must be named by path in the render")

    def test_render_carries_the_scanned_reconciliation(self):
        text = la.format_human_readable(la.run_audit(self.root))
        self.assertIn(f"Scanned (CLAUDE.md seen by the walk): {self.EXPECTED_SCANNED}",
                      text)

    def test_rider_travels_verbatim_in_the_render(self):
        text = la.format_human_readable(la.run_audit(self.root))
        self.assertIn(RIDER_VERBATIM, text)

    def test_membership_disclosure_still_rendered_unchanged(self):
        """The pre-existing enumerated membership disclosure is untouched."""
        text = la.format_human_readable(la.run_audit(self.root))
        self.assertIn("MEMBERSHIP EXCLUSIONS", text)
        self.assertIn("assessment_membrane", text)
        self.assertIn(f"Fenced (membership): {self.EXPECTED_MEMBERSHIP}", text)


class TestNoBehaviourChangeToDiscovery(_AllAxesZone):
    """(e) DISCLOSURE ONLY — which files are in the chain does not move."""

    def test_member_set_matches_the_independent_legacy_oracle(self):
        found, _m, _a = self.disclose()
        oracle = _legacy_reference_walk(self.root)
        self.assertEqual(_rels(self.root, found), _rels(self.root, oracle),
                         "the cured walk admits a DIFFERENT chain than the "
                         "pre-cure predicates — this increment is disclosure only")

    def test_member_set_is_the_declared_expected_set(self):
        found, _m, _a = self.disclose()
        self.assertEqual(_rels(self.root, found), sorted(self.EXPECTED_MEMBERS))

    def test_pair_helper_arity_contract_intact_and_agrees(self):
        """The guarded 2-tuple contract survives; both surfaces agree."""
        pair = la.discover_claude_mds_with_exclusions(self.root)
        self.assertEqual(len(pair), 2, "the pair helper must stay a PAIR")
        found_pair, mem_pair = pair
        found_tri, mem_tri, _axes = self.disclose()
        self.assertEqual(_rels(self.root, found_pair), _rels(self.root, found_tri))
        self.assertEqual(mem_pair, mem_tri)

    def test_legacy_single_return_entry_point_unchanged(self):
        found = la.discover_claude_mds(self.root)
        self.assertIsInstance(found, list)
        self.assertEqual(_rels(self.root, found), sorted(self.EXPECTED_MEMBERS))

    def test_rules_audited_and_counts_unmoved(self):
        result = la.run_audit(self.root)
        self.assertEqual(result["claude_md_count"], len(self.EXPECTED_MEMBERS))
        self.assertEqual(sorted(result["chain_map"]), sorted(self.EXPECTED_MEMBERS))
        self.assertIsInstance(result["rules_audited"], int)


class TestHonestEmptyAndErrorPaths(unittest.TestCase):
    """(c) the disclosure is well-formed at ZERO, and survives the empty-chain
    error return — a zero is a CLAIM the walk makes, not a silence."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def test_zero_counts_are_still_published(self):
        _write(self.root, "CLAUDE.md")
        result = la.run_audit(self.root)
        axes_disc = result["exclusion_axes"]
        self.assertEqual(len(axes_disc["axes"]), len(AXIS_KEYS))
        for a in axes_disc["axes"]:
            self.assertEqual(a["count"], 0)
        nested = next(a for a in axes_disc["axes"] if a["axis"] == "nested_repo")
        self.assertEqual(nested["members"], [],
                         "honest-empty: an EMPTY LIST, never an absent key")
        self.assertEqual(axes_disc["scanned_total"], 1)
        self.assertTrue(axes_disc["reconciles"])

    def test_render_publishes_the_zero_lines(self):
        _write(self.root, "CLAUDE.md")
        text = la.format_human_readable(la.run_audit(self.root))
        for axis in AXIS_KEYS:
            self.assertIn(f"Excluded ({axis}): 0", text)

    def test_disclosure_survives_the_no_files_error_path(self):
        """A zone whose only CLAUDE.mds are excluded must STILL publish the axes
        — they are exactly what explains the empty result."""
        _write(self.root, "nested/CLAUDE.md")
        _mkgit(self.root, "nested")
        result = la.run_audit(self.root)
        self.assertIn("error", result)
        self.assertIn("exclusion_axes", result,
                      "the per-axis disclosure went dark on the empty-chain path, "
                      "exactly where it explains the emptiness")
        nested = next(a for a in result["exclusion_axes"]["axes"]
                      if a["axis"] == "nested_repo")
        self.assertEqual(nested["count"], 1)
        self.assertEqual(nested["members"], ["nested/CLAUDE.md"])


class TestAxisContentIsDeclaredNotInline(unittest.TestCase):
    """Engine/content separation (federation KI): the axis vocabulary is a
    declared, named set — not an inline literal buried in the walk."""

    def test_axis_spec_is_a_named_module_level_set(self):
        self.assertTrue(hasattr(la, "NON_MEMBERSHIP_EXCLUSION_AXES"))
        keys = [a["axis"] for a in la.NON_MEMBERSHIP_EXCLUSION_AXES]
        self.assertEqual(keys, list(AXIS_KEYS))

    def test_noise_skip_dirs_hoisted_to_a_named_set(self):
        self.assertTrue(hasattr(la, "CHAIN_NOISE_SKIP_DIRS"))
        for name in ("node_modules", "__pycache__", "dist", "build", "target"):
            self.assertIn(name, la.CHAIN_NOISE_SKIP_DIRS)

    def test_rider_constant_is_verbatim(self):
        self.assertEqual(la.PER_AXIS_DISCLOSURE_DOES_NOT_SATISFY, RIDER_VERBATIM)


if __name__ == "__main__":
    unittest.main()
