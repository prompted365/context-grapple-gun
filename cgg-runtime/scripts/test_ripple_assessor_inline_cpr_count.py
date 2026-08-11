#!/usr/bin/env python3
"""Tests for ripple-assessor's inline pending-CPR counter
(bk-ripple-assessor-inline-cpr-count-dead-predicate, tic 697 — filed from the
tic-695 membrane-fence sibling survey, site 3; unblocked by the tic-696
declared-emitter allow-list strike).

The defect under cure: count_pending_cprs_inline returned 0 UNCONDITIONALLY —
a false all-clear on the assessor's own cross-check line. Two independent
faults, one dead counter:
  - same-line predicate ("agnostic-candidate" AND "pending" on ONE line) never
    matches the mandated block form, where the marker line and the
    `status: pending` line are DIFFERENT lines (CogPR Marker Syntax
    Discipline) — 0 matches zone-wide; and the same predicate would
    false-positive on any prose line that merely MENTIONS both tokens.
  - CLAUDE.md-only rglob + blanket `audit-logs` skip excluded the borns home
    (audit-logs/governance/borns-tic<N>-*.md), the primary live emitter.

The cure: consume the declared-emitter set (cpr-extract.find_governance_files
— ONE universe by construction, the tic-696 allow-list) + block-aware parsing
(cpr-extract.BLOCK_RE + parse_cpr_block), so the counter can never diverge
from what the extractor actually reaches. The replacement must NOT become
"audit-logs minus membrane": the boundary is the declared doctrine-tree /
data-tree split the allow-list already resolves, never a hand-carved path
exclusion. And the counter must be HONEST-UNKNOWN on failure: None (rendered
"unavailable"), never a fabricated 0 — a 0 on this line reads as all-clear,
which is the exact defect class under cure.

Contract teeth, each with a fixture arm (selftest-fixture discipline):
  1. block-form pending candidate in doctrine-tree CLAUDE.md -> counted
     (RED pre-fix: same-line predicate misses the block form)
  2. borns-home pending candidate -> counted
     (RED pre-fix: blanket audit-logs skip excluded the borns home)
  3. prose line mentioning both tokens, no valid block -> NOT counted
     (RED pre-fix: the same-line predicate false-positives on it)
  4. non-pending-status block -> NOT counted (block-aware status resolution)
  5. membrane mailbox CLAUDE.md carrying a pending block -> NOT counted
     (the declared data-tree boundary, not "audit-logs minus membrane")
  6. counter=None renders "unavailable" in the report, never a numeric 0
  7. counter=int renders the number (regression guard on the report line)

Fixtures are root-pinned to a temp zone (Self-Locating Artifact Test
Isolation); count_pending_cprs_inline takes an explicit project_dir so no arm
can touch the real zone.

Run:  python3 -m unittest test_ripple_assessor_inline_cpr_count
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_ra = _load("ripple_assessor", "ripple-assessor.py")


CANDIDATE_BLOCK = """<!-- --agnostic-candidate
id: {cid}
status: {status}
lesson: {lesson}
source: {source}
-->
"""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class InlineCprCountTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="ripple-inline-count-test-")
        self.zone = Path(self._tmp.name)
        _write(self.zone / "CLAUDE.md", "# root doctrine\n")

    def tearDown(self):
        self._tmp.cleanup()

    # -- Arm 1: doctrine-tree block form is counted -------------------------
    def test_counts_block_form_pending_in_doctrine_tree(self):
        _write(
            self.zone / "domain_a" / "CLAUDE.md",
            "# domain doctrine\n"
            + CANDIDATE_BLOCK.format(
                cid="cpr_doctrine_pending_tic1", status="pending",
                lesson="doctrine lesson", source="doctrine source"),
        )
        self.assertEqual(
            _ra.count_pending_cprs_inline(str(self.zone)), 1,
            "block-form pending candidate in doctrine-tree CLAUDE.md must be "
            "counted (the marker and status lines are DIFFERENT lines — a "
            "same-line predicate structurally misses the mandated form)")

    # -- Arm 2: borns home is counted ---------------------------------------
    def test_counts_borns_home_pending_block(self):
        _write(
            self.zone / "audit-logs" / "governance" / "borns-tic12-test-born.md",
            "# born detail doc\n"
            + CANDIDATE_BLOCK.format(
                cid="cpr_born_pending_tic12", status="pending",
                lesson="born lesson", source="born source"),
        )
        self.assertEqual(
            _ra.count_pending_cprs_inline(str(self.zone)), 1,
            "borns-home pending candidate must be counted — the borns home is "
            "the primary live emitter; a blanket audit-logs skip excludes it")

    # -- Arm 3: prose mention is NOT counted ---------------------------------
    def test_prose_mention_of_both_tokens_not_counted(self):
        _write(
            self.zone / "domain_b" / "CLAUDE.md",
            "# doctrine\n"
            "The --agnostic-candidate block requires status: pending near id.\n",
        )
        self.assertEqual(
            _ra.count_pending_cprs_inline(str(self.zone)), 0,
            "a prose line merely mentioning both tokens on one line is not a "
            "candidate block — the counter must parse blocks, not grep lines")

    # -- Arm 4: non-pending status NOT counted --------------------------------
    def test_non_pending_status_block_not_counted(self):
        _write(
            self.zone / "domain_c" / "CLAUDE.md",
            "# doctrine\n"
            + CANDIDATE_BLOCK.format(
                cid="cpr_settled_tic2", status="promoted",
                lesson="settled lesson", source="settled source"),
        )
        self.assertEqual(
            _ra.count_pending_cprs_inline(str(self.zone)), 0,
            "a block whose status is not pending must not be counted — the "
            "count is of PENDING flags, resolved from the block body")

    # -- Arm 5: membrane mailbox file NOT counted -----------------------------
    def test_membrane_mailbox_pending_block_not_counted(self):
        _write(
            self.zone / "audit-logs" / "agent-mailboxes" / "ent_test"
            / "inbound" / "dump" / "CLAUDE.md",
            "# inbound dump masquerading by basename\n"
            + CANDIDATE_BLOCK.format(
                cid="cpr_membrane_never_count_tic3", status="pending",
                lesson="membrane lesson", source="membrane source"),
        )
        self.assertEqual(
            _ra.count_pending_cprs_inline(str(self.zone)), 0,
            "a membrane mailbox file named CLAUDE.md is FIELD evidence, never "
            "an emitter surface — the declared-emitter universe excludes the "
            "data tree; the counter must consume that universe, not re-carve "
            "an 'audit-logs minus membrane' exclusion")

    # -- Arm 6: honest-unknown renders unavailable, never 0 -------------------
    def test_report_renders_unavailable_for_none_count(self):
        classified = {
            "active_signals": {}, "working_signals": {},
            "warranted_signals": {}, "active_warrants": {},
            "acknowledged_warrants": {}, "resolved": {},
        }
        report = _ra.compile_proposals(
            None, classified, [], {"count": 0, "last_tic": "unknown"},
            None, None,
        )
        line = next(l for l in report.splitlines()
                    if l.startswith("- **Inline pending CPRs**"))
        self.assertIn("unavailable", line,
                      "None (emitter universe unresolved) must render as "
                      "unavailable — an honest unknown")
        self.assertNotIn(": 0", line,
                         "None must never render as a numeric 0 — a fabricated "
                         "0 on this line is a false all-clear, the defect class "
                         "under cure")

    # -- Arm 7: integer count renders the number ------------------------------
    def test_report_renders_integer_count(self):
        classified = {
            "active_signals": {}, "working_signals": {},
            "warranted_signals": {}, "active_warrants": {},
            "acknowledged_warrants": {}, "resolved": {},
        }
        report = _ra.compile_proposals(
            None, classified, [], {"count": 0, "last_tic": "unknown"},
            None, 3,
        )
        line = next(l for l in report.splitlines()
                    if l.startswith("- **Inline pending CPRs**"))
        self.assertIn("3", line, "an integer count must render as its number")


if __name__ == "__main__":
    unittest.main()
