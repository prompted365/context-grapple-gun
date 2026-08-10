#!/usr/bin/env python3
"""Tests for the ladder-audit CHAIN-MEMBERSHIP FENCE + its enumerated disclosure
(bk-ladder-audit-membership-fence; ratified /review 688 from
cpr_mogul_ladder_audit_d3df75aab9fa — PROMOTE-as-ray on
cgg-ledger#precondition-gate-perimeter-completeness, membership axis).

The contract under guard: a discovery walk that assembles a GOVERNED chain must
apply a MEMBERSHIP fence, not merely disclose its INFERENCE method. Declaring HOW
parentage was inferred does not qualify WHETHER an artifact is a chain member at
all. `discover_claude_mds()`'s `skip_dirs` fences NOISE (node_modules, build,
dist, …); it never fenced the ASSESSMENT MEMBRANE — agent-mailboxes /
harpoonTargets / harpoonables / inbound — where material is UNDER assessment and
has NOT been admitted (observe-not-couple).

The tic-685 incident: the audit adopted 2 of 8 files (31 of 316 rules) of
un-admitted mailbox material and emitted a `missing_reference` finding whose
proposed cure was for the FEDERATION ROOT to reference a harpoon ASSESSMENT
TARGET as though it were a governed rung — an inbound-material adoption dressed
as a coherence repair.

Arms (all mandatory):
  (a) membrane-planted CLAUDE.md is NOT discovered AND IS enumerated in the
      `membership_exclusions` disclosure with its reason class
      (`assessment_membrane`) — harpoonTargets, inbound/harpoonables, and the
      mailbox root itself;
  (b) NO-BLANKET-EXCLUSION: a governed CLAUDE.md under `audit-logs/` that is not
      membrane material IS still discovered (the hard scope fence — governed rung
      surfaces under audit-logs/ stay discoverable);
  (c) the disclosure is present and well-formed even at ZERO exclusions (empty
      list, never an absent key) — the honest-empty arm;
  (d) the tic-685 symptom end-to-end: no finding names membrane material, and the
      chain map does not carry it;
  (e) component-exact matching — a directory whose NAME merely contains a membrane
      token (`inbound-notes`, `harpoonTargets-archive`) is NOT over-fenced.

Each case isolates against a TemporaryDirectory (Self-Locating Artifact Test
Isolation KI); nothing touches the real zone.

Run:  python3 -m unittest test_ladder_audit_membership_fence
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

MEMBRANE_REASON = "assessment_membrane"

# The two REAL tic-685 adoptions, reproduced as fixture paths.
HARPOON_TARGET_REL = (
    "audit-logs/agent-mailboxes/ent_homeskillet/harpoonTargets/queue/"
    "overshoot-adapter/CLAUDE.md"
)
INBOUND_HARPOONABLE_REL = (
    "audit-logs/agent-mailboxes/ent_homeskillet/inbound/harpoonables/"
    "ubiq-harpoon-variant/docs/reference/CLAUDE.md"
)
MAILBOX_ROOT_REL = "audit-logs/agent-mailboxes/ent_homeskillet/CLAUDE.md"

# The no-blanket-exclusion arm: a GOVERNED rung surface that lives under
# audit-logs/ but is NOT membrane material. It must stay discoverable.
GOVERNED_UNDER_AUDIT_LOGS_REL = "audit-logs/governance/harpoon-office/CLAUDE.md"

ROOT_DOCTRINE = """# Federation Root (fixture)

## Key Invariants
- governed root body.

See `governance` and `estate-x` for children.
"""

FOREIGN_DOCTRINE = """# CLAUDE.md - Overshoot Vision Adapter (fixture)

## What This Does
Third-party SDK wrapper parked in the mailbox for assessment. NOT admitted.

## Architecture
- types.ts
"""

GOVERNED_CHILD_DOCTRINE = """# Harpoon Office (fixture governed rung)

## Charter
- covenant-strike office; a real governed surface that happens to live under
  audit-logs/.
"""


def _write(root, rel, text):
    p = Path(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _rels(root, paths):
    """Discovered paths as zone-relative POSIX strings."""
    return sorted(str(Path(p).relative_to(root)) for p in paths)


def _exclusion_paths(exclusions):
    return sorted(e["path"] for e in exclusions)


class _ZoneCase(unittest.TestCase):
    """Base: an isolated zone with a governed root CLAUDE.md."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        _write(self.root, "CLAUDE.md", ROOT_DOCTRINE)

    def discover(self):
        """The discovery pair: (found_paths, membership_exclusions)."""
        return la.discover_claude_mds_with_exclusions(self.root)


class TestMembraneFencedFromChainDiscovery(_ZoneCase):
    """(a) membrane-planted CLAUDE.md is NOT adopted into the chain."""

    def test_harpoon_target_not_discovered(self):
        _write(self.root, HARPOON_TARGET_REL, FOREIGN_DOCTRINE)
        found, _ = self.discover()
        self.assertNotIn(HARPOON_TARGET_REL, _rels(self.root, found),
                         "harpoon ASSESSMENT TARGET adopted into the governed chain")
        self.assertEqual(_rels(self.root, found), ["CLAUDE.md"])

    def test_inbound_harpoonable_not_discovered(self):
        _write(self.root, INBOUND_HARPOONABLE_REL, FOREIGN_DOCTRINE)
        found, _ = self.discover()
        self.assertNotIn(INBOUND_HARPOONABLE_REL, _rels(self.root, found),
                         "inbound/harpoonables material adopted into the governed chain")

    def test_mailbox_root_not_discovered(self):
        _write(self.root, MAILBOX_ROOT_REL, FOREIGN_DOCTRINE)
        found, _ = self.discover()
        self.assertNotIn(MAILBOX_ROOT_REL, _rels(self.root, found),
                         "agent-mailbox material adopted into the governed chain")

    def test_both_tic685_adoptions_fenced_together(self):
        _write(self.root, HARPOON_TARGET_REL, FOREIGN_DOCTRINE)
        _write(self.root, INBOUND_HARPOONABLE_REL, FOREIGN_DOCTRINE)
        found, exclusions = self.discover()
        self.assertEqual(_rels(self.root, found), ["CLAUDE.md"])
        self.assertEqual(_exclusion_paths(exclusions),
                         sorted([HARPOON_TARGET_REL, INBOUND_HARPOONABLE_REL]))


class TestMembershipExclusionDisclosure(_ZoneCase):
    """(a) the exclusion is an ENUMERATED first-class disclosure, never an
    implicit noise-skip consequence."""

    def test_exclusion_entries_are_well_formed(self):
        _write(self.root, HARPOON_TARGET_REL, FOREIGN_DOCTRINE)
        _, exclusions = self.discover()
        self.assertEqual(len(exclusions), 1)
        e = exclusions[0]
        for key in ("path", "reason", "membrane_marker", "detail"):
            self.assertIn(key, e, f"exclusion entry missing `{key}`")
        self.assertEqual(e["path"], HARPOON_TARGET_REL)
        self.assertEqual(e["reason"], MEMBRANE_REASON)
        # The marker names the OUTERMOST membrane component crossed — here the
        # harpoon queue is nested inside the mailbox, so the mailbox is the fence.
        self.assertEqual(e["membrane_marker"], "agent-mailboxes")
        self.assertTrue(e["detail"])

    def test_each_declared_membrane_name_fires_on_its_own(self):
        """Every name in the declared set is load-bearing — each fences a
        standalone path, not only when nested under agent-mailboxes."""
        standalone = {
            "harpoonTargets": "governance/harpoonTargets/queue/x/CLAUDE.md",
            "harpoonables": "governance/harpoonables/y/CLAUDE.md",
            "inbound": "governance/inbound/z/CLAUDE.md",
            "agent-mailboxes": "governance/agent-mailboxes/ent_x/CLAUDE.md",
        }
        for rel in standalone.values():
            _write(self.root, rel, FOREIGN_DOCTRINE)
        found, exclusions = self.discover()
        self.assertEqual(_rels(self.root, found), ["CLAUDE.md"])
        by_path = {e["path"]: e for e in exclusions}
        for marker, rel in standalone.items():
            self.assertIn(rel, by_path, f"`{marker}` did not fence standalone")
            self.assertEqual(by_path[rel]["membrane_marker"], marker)
            self.assertEqual(by_path[rel]["reason"], MEMBRANE_REASON)

    def test_membrane_marker_names_the_firing_component(self):
        _write(self.root, INBOUND_HARPOONABLE_REL, FOREIGN_DOCTRINE)
        _write(self.root, MAILBOX_ROOT_REL, FOREIGN_DOCTRINE)
        _, exclusions = self.discover()
        by_path = {e["path"]: e for e in exclusions}
        # The mailbox-root file fires on `agent-mailboxes`; the nested inbound
        # file fires on the OUTERMOST membrane component it crosses.
        self.assertEqual(by_path[MAILBOX_ROOT_REL]["membrane_marker"],
                         "agent-mailboxes")
        self.assertEqual(by_path[INBOUND_HARPOONABLE_REL]["membrane_marker"],
                         "agent-mailboxes")

    def test_run_audit_carries_the_disclosure(self):
        _write(self.root, HARPOON_TARGET_REL, FOREIGN_DOCTRINE)
        result = la.run_audit(self.root)
        self.assertIn("membership_exclusions", result,
                      "run_audit output has no membership_exclusions disclosure")
        self.assertEqual(_exclusion_paths(result["membership_exclusions"]),
                         [HARPOON_TARGET_REL])
        self.assertEqual(result["membership_exclusion_count"], 1)
        # JSON-serializable (the audit packet is emitted as JSON).
        json.dumps(result)

    def test_human_readable_output_renders_the_disclosure(self):
        _write(self.root, HARPOON_TARGET_REL, FOREIGN_DOCTRINE)
        text = la.format_human_readable(la.run_audit(self.root))
        self.assertIn("MEMBERSHIP EXCLUSIONS", text)
        self.assertIn(MEMBRANE_REASON, text)
        self.assertIn("overshoot-adapter", text)

    def test_disclosure_present_when_zero_exclusions(self):
        """(c) honest-empty arm: the key is an EMPTY LIST, never absent."""
        result = la.run_audit(self.root)
        self.assertIn("membership_exclusions", result)
        self.assertEqual(result["membership_exclusions"], [])
        self.assertEqual(result["membership_exclusion_count"], 0)
        text = la.format_human_readable(result)
        self.assertIn("MEMBERSHIP EXCLUSIONS", text)

    def test_disclosure_survives_the_no_files_error_path(self):
        """A zone whose ONLY CLAUDE.mds are membrane material must still
        disclose what it fenced — an error return may not swallow the fence."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        _write(tmp.name, HARPOON_TARGET_REL, FOREIGN_DOCTRINE)
        result = la.run_audit(tmp.name)
        self.assertIn("error", result)
        self.assertIn("membership_exclusions", result)
        self.assertEqual(_exclusion_paths(result["membership_exclusions"]),
                         [HARPOON_TARGET_REL])


class TestNoBlanketAuditLogsExclusion(_ZoneCase):
    """(b) HARD SCOPE FENCE: governed rung surfaces under audit-logs/ stay
    discoverable — the fence is on the ASSESSMENT MEMBRANE, not on audit-logs/."""

    def test_governed_claude_md_under_audit_logs_still_discovered(self):
        _write(self.root, GOVERNED_UNDER_AUDIT_LOGS_REL, GOVERNED_CHILD_DOCTRINE)
        found, exclusions = self.discover()
        self.assertIn(GOVERNED_UNDER_AUDIT_LOGS_REL, _rels(self.root, found),
                      "blanket audit-logs exclusion — a governed rung surface "
                      "under audit-logs/ was dropped from the chain")
        self.assertEqual(exclusions, [])

    def test_governed_and_membrane_partition_correctly(self):
        _write(self.root, GOVERNED_UNDER_AUDIT_LOGS_REL, GOVERNED_CHILD_DOCTRINE)
        _write(self.root, HARPOON_TARGET_REL, FOREIGN_DOCTRINE)
        found, exclusions = self.discover()
        self.assertEqual(_rels(self.root, found),
                         sorted(["CLAUDE.md", GOVERNED_UNDER_AUDIT_LOGS_REL]))
        self.assertEqual(_exclusion_paths(exclusions), [HARPOON_TARGET_REL])

    def test_run_audit_counts_governed_child(self):
        _write(self.root, GOVERNED_UNDER_AUDIT_LOGS_REL, GOVERNED_CHILD_DOCTRINE)
        _write(self.root, HARPOON_TARGET_REL, FOREIGN_DOCTRINE)
        result = la.run_audit(self.root)
        self.assertEqual(result["claude_md_count"], 2)
        self.assertIn(GOVERNED_UNDER_AUDIT_LOGS_REL, result["chain_map"])


class TestComponentExactMatching(_ZoneCase):
    """(e) the fence matches PATH COMPONENTS exactly — it must not over-fence a
    directory whose name merely contains a membrane token."""

    def test_lookalike_dirs_are_not_fenced(self):
        lookalikes = [
            "governance/inbound-notes/CLAUDE.md",
            "governance/harpoonTargets-archive/CLAUDE.md",
            "governance/my-agent-mailboxes-doc/CLAUDE.md",
        ]
        for rel in lookalikes:
            _write(self.root, rel, GOVERNED_CHILD_DOCTRINE)
        found, exclusions = self.discover()
        self.assertEqual(exclusions, [], "over-fenced a lookalike directory name")
        for rel in lookalikes:
            self.assertIn(rel, _rels(self.root, found))


class TestTic685SymptomEndToEnd(_ZoneCase):
    """(d) the incident's actual symptom: the finding set proposed that the
    federation root reference a harpoon assessment target. After the fence, no
    finding may name membrane material at all."""

    def test_no_finding_names_membrane_material(self):
        _write(self.root, HARPOON_TARGET_REL, FOREIGN_DOCTRINE)
        _write(self.root, INBOUND_HARPOONABLE_REL, FOREIGN_DOCTRINE)
        result = la.run_audit(self.root)
        blob = json.dumps(result["findings"])
        for token in ("harpoonTargets", "harpoonables", "agent-mailboxes",
                      "overshoot-adapter", "ubiq-harpoon-variant"):
            self.assertNotIn(token, blob,
                             f"a coherence finding still names membrane material "
                             f"({token}) — inbound-material adoption dressed as "
                             f"a coherence repair")

    def test_membrane_rules_not_counted_as_audited_law(self):
        _write(self.root, HARPOON_TARGET_REL, FOREIGN_DOCTRINE)
        _write(self.root, INBOUND_HARPOONABLE_REL, FOREIGN_DOCTRINE)
        result = la.run_audit(self.root)
        self.assertEqual(result["claude_md_count"], 1)
        self.assertEqual(sorted(result["chain_map"]), ["CLAUDE.md"])
        blob = json.dumps(result["rule_classifications"])
        self.assertNotIn("Overshoot", blob,
                         "un-admitted membrane rules counted as governed law")


class TestDiscoveryHelperContract(_ZoneCase):
    """The legacy single-return entry point stays list-returning (no caller
    breakage); the pair-returning helper is the fenced+disclosing surface."""

    def test_legacy_entry_point_still_returns_a_list(self):
        _write(self.root, HARPOON_TARGET_REL, FOREIGN_DOCTRINE)
        found = la.discover_claude_mds(self.root)
        self.assertIsInstance(found, list)
        self.assertEqual(_rels(self.root, found), ["CLAUDE.md"])

    def test_pair_helper_returns_two_values(self):
        found, exclusions = la.discover_claude_mds_with_exclusions(self.root)
        self.assertIsInstance(found, list)
        self.assertIsInstance(exclusions, list)

    def test_membrane_dir_names_declared_as_a_named_set(self):
        self.assertTrue(hasattr(la, "ASSESSMENT_MEMBRANE_DIRS"),
                        "the membrane fence content must be a declared, named set "
                        "(engine/content separation), not an inline literal")
        for name in ("agent-mailboxes", "harpoonTargets", "harpoonables", "inbound"):
            self.assertIn(name, la.ASSESSMENT_MEMBRANE_DIRS)


if __name__ == "__main__":
    unittest.main()
