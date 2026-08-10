#!/usr/bin/env python3
"""test_mandate_write_merge_terminalize.py — merge-terminalize-absorbed fixtures.

Fix-site: bk-mandate-merge-terminalize-absorbed (/review-691 ratified,
PROMOTE-as-refinement-ray on cgg-ledger#mandate-lifecycle-defects, fifth ray:
A MERGE MUST TERMINALIZE WHAT IT CONSUMES). A merge that absorbs a
NEVER-DISPATCHED (pending) predecessor recorded the absorption only on the
absorber (merged_from) — the absorbed record's history-ledger lane stayed
permanently non-terminal, inverting the ledger's declared tiebreaker authority
(cgg-gate.sh failure-protocol step 2.5: "on disagreement the LEDGER is truth").
Evidence n=6 deterministic t680-691 incl. a same-tic reproduction by the
adjudicating tic's own cadence merge.

The cure emits the terminal transition on the ABSORBED record at the merge
site — a pending_to_merged row carrying the successor id — at the true write
boundary (write_mandate, same placement law as the /review-598 validation),
keyed on what current.json holds AT the clobber, not the merge-time snapshot.

Three ratified arms:
  (1) never-dispatched-merge — merging a pending predecessor emits
      pending_to_merged on the absorbed record with the successor id in the row;
  (2) dispatched-then-merged unchanged — a running predecessor gains no
      duplicate terminal (its own runner lands running_to_consumed[_detached]
      via the write-back guard);
  (3) supersede path unchanged — supersede fires only on already-terminal
      records and emits nothing.
Plus: fresh-write no-op, boundary-truth mismatch no-op, idempotency,
successor-row append preserved, and the tic-534 branch-selection discipline
(enumerate-terminal-else-merge) non-regression.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "mandate_write", _HERE / "mandate-write.py"
)
mw = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mw)


def _zone():
    return Path(tempfile.mkdtemp(prefix="mw-merge-term-"))


def _write_current(zone: Path, mandate: dict) -> Path:
    mdir = zone / "audit-logs" / "mogul" / "mandates"
    mdir.mkdir(parents=True, exist_ok=True)
    mf = mdir / "current.json"
    mf.write_text(json.dumps(mandate, indent=2))
    return mf


def _predecessor(status: str, mandate_id: str = "tic-100-pred") -> dict:
    return {
        "mandate_id": mandate_id,
        "status": status,
        "cycle_request": {"run_now": ["signal_scan"], "reason": "test pred"},
    }


def _successor(zone: Path, merged_from: list, supersedes: list) -> dict:
    return mw.build_mandate(
        trigger_kind="cadence",
        trigger_source="test",
        tic=101,
        cycles=["queue_refresh"],
        merged_from=merged_from,
        supersedes=supersedes,
        conformation_ref=None,
        runtime_verified=False,
        zone_root_path=str(zone),
    )


def _history_rows(zone: Path) -> list:
    hdir = zone / "audit-logs" / "mogul" / "mandates" / "history"
    rows = []
    if not hdir.exists():
        return rows
    for f in sorted(hdir.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _merged_rows(zone: Path) -> list:
    return [r for r in _history_rows(zone)
            if r.get("transition") == "pending_to_merged"]


class MergeTerminalizeAbsorbed(unittest.TestCase):
    def test_arm1_pending_predecessor_gets_pending_to_merged_with_successor_id(self):
        """ARM 1 — the observed defect: absorbing a never-dispatched mandate
        must close its ledger lane at the merge site."""
        zone = _zone()
        _write_current(zone, _predecessor("pending"))
        successor = _successor(zone, merged_from=["tic-100-pred"], supersedes=[])
        mw.write_mandate(successor, zone)
        rows = _merged_rows(zone)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mandate_id"], "tic-100-pred")
        self.assertEqual(rows[0]["merged_into"], successor["mandate_id"])
        self.assertIn("timestamp", rows[0])

    def test_arm2_running_predecessor_gains_no_duplicate_terminal(self):
        """ARM 2 — a dispatched predecessor's own runner writes its terminal
        (running_to_consumed[_detached]); the merge site must not double it."""
        zone = _zone()
        _write_current(zone, _predecessor("running"))
        successor = _successor(zone, merged_from=["tic-100-pred"], supersedes=[])
        mw.write_mandate(successor, zone)
        self.assertEqual(_merged_rows(zone), [])

    def test_arm3_supersede_of_terminal_predecessor_emits_nothing(self):
        """ARM 3 — supersede fires only on already-terminal records; the
        supersede path stays emission-free."""
        zone = _zone()
        _write_current(zone, _predecessor("consumed"))
        successor = _successor(zone, merged_from=[], supersedes=["tic-100-pred"])
        mw.write_mandate(successor, zone)
        self.assertEqual(_merged_rows(zone), [])

    def test_fresh_write_with_no_existing_mandate_emits_nothing(self):
        zone = _zone()
        successor = _successor(zone, merged_from=[], supersedes=[])
        mw.write_mandate(successor, zone)
        self.assertEqual(_merged_rows(zone), [])

    def test_boundary_truth_rules_unnamed_resident_is_not_terminalized(self):
        """The clobbered record must be NAMED in merged_from — a mid-race
        replacement (current.json changed since the merge decision) is not
        this successor's absorption to terminalize."""
        zone = _zone()
        _write_current(zone, _predecessor("pending", mandate_id="tic-100-other"))
        successor = _successor(zone, merged_from=["tic-100-pred"], supersedes=[])
        mw.write_mandate(successor, zone)
        self.assertEqual(_merged_rows(zone), [])

    def test_idempotent_rewrite_does_not_duplicate_the_terminal_row(self):
        """After the first write, current.json holds the successor — a second
        write_mandate call must not re-emit for the already-closed lane."""
        zone = _zone()
        _write_current(zone, _predecessor("pending"))
        successor = _successor(zone, merged_from=["tic-100-pred"], supersedes=[])
        mw.write_mandate(successor, zone)
        mw.write_mandate(successor, zone)
        self.assertEqual(len(_merged_rows(zone)), 1)

    def test_successor_full_row_still_appends_to_history(self):
        """Existing behavior preserved: the successor's own mandate row lands
        in the ledger alongside (after) the absorbed lane's terminal row."""
        zone = _zone()
        _write_current(zone, _predecessor("pending"))
        successor = _successor(zone, merged_from=["tic-100-pred"], supersedes=[])
        mw.write_mandate(successor, zone)
        rows = _history_rows(zone)
        mandate_rows = [r for r in rows
                        if r.get("mandate_id") == successor["mandate_id"]
                        and "transition" not in r]
        self.assertEqual(len(mandate_rows), 1)
        # ledger order: close the absorbed lane, then the successor's row
        self.assertEqual(rows[0].get("transition"), "pending_to_merged")

    def test_tic534_branch_discipline_pending_merges_terminal_supersedes(self):
        """Sibling-axis non-regression (tic 534, enumerate-terminal-else-merge):
        the branch selection in merge_or_supersede is untouched by the fix."""
        pending = _predecessor("pending")
        cycles, merged_from, supersedes = mw.merge_or_supersede(pending, ["queue_refresh"])
        self.assertEqual(merged_from, ["tic-100-pred"])
        self.assertEqual(supersedes, [])
        self.assertIn("signal_scan", cycles)

        consumed = _predecessor("consumed")
        cycles, merged_from, supersedes = mw.merge_or_supersede(consumed, ["queue_refresh"])
        self.assertEqual(merged_from, [])
        self.assertEqual(supersedes, ["tic-100-pred"])
        self.assertEqual(cycles, ["queue_refresh"])

        unknown = _predecessor("weird_new_state")
        cycles, merged_from, supersedes = mw.merge_or_supersede(unknown, ["queue_refresh"])
        self.assertEqual(merged_from, ["tic-100-pred"])  # non-destructive default: merge
        self.assertEqual(supersedes, [])

    def test_unrecognized_live_status_is_not_stamped_pending_to_merged(self):
        """The terminal row asserts the FROM-state; an unrecognized live status
        merged for safety must not be mislabeled as pending — scope stays
        exactly on the never-dispatched class."""
        zone = _zone()
        _write_current(zone, _predecessor("weird_new_state"))
        successor = _successor(zone, merged_from=["tic-100-pred"], supersedes=[])
        mw.write_mandate(successor, zone)
        self.assertEqual(_merged_rows(zone), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
