#!/usr/bin/env python3
"""Fixtures for inbox-envelope.py `reconcile_registry` — the derived-None
no-clobber guard (F-738-B1 HIGH cure; ruled /review 738 round 2 ->
bk-inbox-reconcile-none-overwrite-guard).

THE DEFECT (from the ruling's own evidence): the wave-8B fence-scoped sweep
DESTROYED five hand-typed fields on the t737 estate-packet registry row —
envelope_type -> null, subject/sender -> "", source_tic + state_entered_at_tic
-> null — because a NON-MAILBOX-SHAPED packet derives None for every content
field and the old unconditional `{**old, **new}` merge let those Nones win.
The SAME sweep PRESERVED every field on the adapter-shaped packet, so the
divergence was SHAPE, not luck.

RED-THEN-GREEN spine:
  RED   — `TestRedUnguardedMergeNullsThePacket` reproduces the ORIGINAL
          `{**old, **new}` merge inline and proves it nulls all five fields.
          This is the arm that did not exist when the defect shipped; it pins
          the defect's exact shape so the cure has something to be measured
          against.
  GREEN — `TestGuardPreservesPopulatedFields` runs the SAME registry + SAME
          non-mailbox-shaped packet through the real `reconcile_registry` and
          proves all five survive.

NEGATIVE CONTROL (the load-bearing arm): `TestNegativeControlCureIsLoadBearing`
re-runs the identical scenario with `_merge_reconciled` monkey-patched back to
the pre-cure `{**old, **new}` behaviour — i.e. the cure REVERTED in place — and
asserts the damage RETURNS. If someone reverts the cure in the source file,
`TestGuardPreservesPopulatedFields` fails; if someone guts the guard into a
no-op that merely LOOKS present, this arm fails because the reverted behaviour
would no longer differ from the live one. The pair is what makes the proof
falsifiable rather than decorative.

Per `cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths`
every documented conditional gets BOTH arms: derived-absent/derived-present,
cached-populated/cached-empty, always-write key vs guarded key, the
0-and-False-are-populated carve-out, whitespace-only strings, brand-new rows
(no cached row at all), and the lawful WAIT->DONE state/filename flip.

Isolation: every case builds its own inbox tree under a TemporaryDirectory.
Nothing reads or writes any real federation mailbox, registry, or queue.

Run:  python3 -m unittest test_inbox_reconcile_none_overwrite  (from cgg-runtime/scripts/)
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "inbox_envelope", _HERE / "inbox-envelope.py"
)
ie = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ie)


# ── the ruling's two shapes ────────────────────────────────────────────────
# The estate packet: a real, hand-typed registry row whose ON-DISK file is NOT
# mailbox-shaped (no content{}, no sender{}, no lifecycle{}), so every derived
# content field comes back None/"".
NON_MAILBOX_PACKET = {
    "packet_id": "pkt-state-a0-estate-001",
    "packet_type": "state_of_estate",
    "estate": "a0-estate",
    "emitted_at_tic": 737,
}

# The adapter-shaped packet: carries the mailbox envelope keys, so reconcile
# derives real values. This is the cure's proof-of-concept shape.
ADAPTER_PACKET = {
    "message_id": "pkt-doctrine-baseline-a0-estate-001",
    "sender": {"entity_id": "ent_estate_router"},
    "recipient": {"entity_id": "ent_estate_router"},
    "routing": {"priority": "normal"},
    "content": {
        "subject": "doctrine_baseline — upstream",
        "envelope_type": "estate_outbound:doctrine_baseline",
    },
    "lifecycle": {"state": "WAIT", "source_tic": 738, "state_entered_at_tic": 738},
}

# The five hand-typed fields the wave-8B sweep destroyed.
HAND_TYPED_ROW = {
    "state": "WAIT",
    "filename": "WAIT_pkt-state-a0-estate-001.json",
    "envelope_type": "estate_inbound:state_of_estate",
    "subject": "state_of_estate — a0 founding report",
    "sender": "a0-estate",
    "priority": "normal",
    "source_tic": 737,
    "state_entered_at_tic": 737,
    "kind": "flat",
}
FIVE_DESTROYED_FIELDS = (
    "envelope_type", "subject", "sender", "source_tic", "state_entered_at_tic",
)


def _mk_inbox(packets: dict, registry_rows: dict, channel: str = "inbound") -> str:
    """Build a throwaway inbox tree. `packets` maps filename -> json body."""
    root = tempfile.mkdtemp(prefix="inbox-reconcile-guard-")
    ibox = os.path.join(root, "ent_fixture_estate_router")
    ie.ensure_inbox(ibox)
    for fname, body in packets.items():
        Path(os.path.join(ibox, channel, fname)).write_text(
            json.dumps(body, indent=2), encoding="utf-8")
    reg_path = os.path.join(ibox, "indexes", "inbox-registry.json")
    Path(reg_path).write_text(
        json.dumps({"messages": registry_rows, "idempotency_index": {}}, indent=2),
        encoding="utf-8")
    return ibox


def _read_registry(ibox: str) -> dict:
    return json.loads(
        Path(os.path.join(ibox, "indexes", "inbox-registry.json")).read_text(
            encoding="utf-8"))["messages"]


def _row_for(messages: dict, marker: str) -> dict:
    """Find the reconciled row for the non-mailbox packet. Its message id is
    derived from the filename (no message_id key), so match on the marker."""
    for mid, row in messages.items():
        if marker in mid or marker in (row.get("filename") or ""):
            return row
    raise AssertionError(f"no reconciled row matching {marker!r} in {list(messages)}")


# ══════════════════════════════════════════════════════════════════════════
# RED — the defect, reproduced
# ══════════════════════════════════════════════════════════════════════════

class TestRedUnguardedMergeNullsThePacket(unittest.TestCase):
    """The pre-cure merge, reproduced inline, destroys all five fields."""

    def test_unguarded_merge_nulls_all_five_hand_typed_fields(self):
        derived = {
            "state": "WAIT",
            "filename": "WAIT_pkt-state-a0-estate-001.json",
            "subject": "",            # (env.get("content") or {}).get("subject", "")
            "sender": "",             # (env.get("sender") or {}).get("entity_id", "")
            "priority": "normal",
            "envelope_type": None,
            "source_tic": None,
            "state_entered_at_tic": None,
            "kind": "flat",
        }
        # THE ORIGINAL LINE, verbatim in behaviour: messages[mid] = {**old, **new}
        unguarded = {**HAND_TYPED_ROW, **derived}
        self.assertIsNone(unguarded["envelope_type"])
        self.assertEqual(unguarded["subject"], "")
        self.assertEqual(unguarded["sender"], "")
        self.assertIsNone(unguarded["source_tic"])
        self.assertIsNone(unguarded["state_entered_at_tic"])

    def test_guarded_merge_preserves_all_five(self):
        derived = {
            "state": "WAIT", "filename": "WAIT_pkt-state-a0-estate-001.json",
            "subject": "", "sender": "", "priority": "normal",
            "envelope_type": None, "source_tic": None,
            "state_entered_at_tic": None, "kind": "flat",
        }
        guarded = ie._merge_reconciled(HAND_TYPED_ROW, derived)
        for f in FIVE_DESTROYED_FIELDS:
            self.assertEqual(guarded[f], HAND_TYPED_ROW[f],
                             f"{f} was clobbered by a derived absence")


# ══════════════════════════════════════════════════════════════════════════
# GREEN — the real reconcile path, end to end
# ══════════════════════════════════════════════════════════════════════════

class TestGuardPreservesPopulatedFields(unittest.TestCase):

    def test_live_reconcile_preserves_the_five_destroyed_fields(self):
        ibox = _mk_inbox(
            {"WAIT_pkt-state-a0-estate-001.json": NON_MAILBOX_PACKET},
            {"WAIT_pkt-state-a0-estate-001": dict(HAND_TYPED_ROW)},
        )
        # The registry key must match the id reconcile derives from the file.
        msgs_before = _read_registry(ibox)
        derived_id = "WAIT_pkt-state-a0-estate-001"
        self.assertIn(derived_id, msgs_before)

        ie.reconcile_registry(ibox, persist=True)
        row = _row_for(_read_registry(ibox), "pkt-state-a0-estate-001")
        for f in FIVE_DESTROYED_FIELDS:
            self.assertEqual(row[f], HAND_TYPED_ROW[f],
                             f"reconcile nulled {f} on the non-mailbox-shaped packet")

    def test_adapter_shaped_packet_still_derives_real_values(self):
        """The cure must not freeze rows: a populated derived value always wins."""
        ibox = _mk_inbox(
            {"WAIT_adapter.json": ADAPTER_PACKET},
            {"pkt-doctrine-baseline-a0-estate-001": {
                "state": "WAIT", "filename": "old.json",
                "subject": "STALE SUBJECT", "sender": "stale_sender",
                "envelope_type": "stale.type", "source_tic": 1,
                "state_entered_at_tic": 1, "priority": "low", "kind": "flat"}},
        )
        ie.reconcile_registry(ibox, persist=True)
        row = _read_registry(ibox)["pkt-doctrine-baseline-a0-estate-001"]
        self.assertEqual(row["subject"], "doctrine_baseline — upstream")
        self.assertEqual(row["sender"], "ent_estate_router")
        self.assertEqual(row["envelope_type"], "estate_outbound:doctrine_baseline")
        self.assertEqual(row["source_tic"], 738)
        self.assertEqual(row["state_entered_at_tic"], 738)
        self.assertEqual(row["filename"], "WAIT_adapter.json")

    def test_brand_new_row_is_added_unchanged(self):
        """No cached row => nothing to protect; every derived value lands as-is."""
        ibox = _mk_inbox({"WAIT_adapter.json": ADAPTER_PACKET}, {})
        res = ie.reconcile_registry(ibox, persist=True)
        self.assertIn("pkt-doctrine-baseline-a0-estate-001", res["added"])
        row = _read_registry(ibox)["pkt-doctrine-baseline-a0-estate-001"]
        self.assertEqual(row["envelope_type"], "estate_outbound:doctrine_baseline")

    def test_empty_cached_value_is_overwritten_by_derived_absence(self):
        """Guard fires only when the CACHED value is populated."""
        merged = ie._merge_reconciled(
            {"envelope_type": None, "subject": "", "sender": "   "},
            {"envelope_type": None, "subject": "", "sender": None},
        )
        self.assertIsNone(merged["envelope_type"])
        self.assertEqual(merged["subject"], "")
        self.assertIsNone(merged["sender"])


# ══════════════════════════════════════════════════════════════════════════
# NEGATIVE CONTROL — the cure is load-bearing, not decorative
# ══════════════════════════════════════════════════════════════════════════

class TestNegativeControlCureIsLoadBearing(unittest.TestCase):
    """Revert the cure in place; the exact predicted breakage must return."""

    def setUp(self):
        self._real_merge = ie._merge_reconciled

    def tearDown(self):
        ie._merge_reconciled = self._real_merge

    def test_reverting_the_guard_restores_the_wave8b_damage(self):
        ibox = _mk_inbox(
            {"WAIT_pkt-state-a0-estate-001.json": NON_MAILBOX_PACKET},
            {"WAIT_pkt-state-a0-estate-001": dict(HAND_TYPED_ROW)},
        )
        # ── REVERT: restore the pre-cure unconditional merge ──
        ie._merge_reconciled = lambda existing, derived: {**existing, **derived}
        ie.reconcile_registry(ibox, persist=True)
        row = _row_for(_read_registry(ibox), "pkt-state-a0-estate-001")

        self.assertIsNone(row["envelope_type"], "revert did not reproduce the defect")
        self.assertEqual(row["subject"], "")
        self.assertEqual(row["sender"], "")
        self.assertIsNone(row["source_tic"])
        self.assertIsNone(row["state_entered_at_tic"])

        # ── RESTORE and prove the cure heals the same scenario ──
        ie._merge_reconciled = self._real_merge
        ibox2 = _mk_inbox(
            {"WAIT_pkt-state-a0-estate-001.json": NON_MAILBOX_PACKET},
            {"WAIT_pkt-state-a0-estate-001": dict(HAND_TYPED_ROW)},
        )
        ie.reconcile_registry(ibox2, persist=True)
        row2 = _row_for(_read_registry(ibox2), "pkt-state-a0-estate-001")
        for f in FIVE_DESTROYED_FIELDS:
            self.assertEqual(row2[f], HAND_TYPED_ROW[f])


# ══════════════════════════════════════════════════════════════════════════
# The guard's documented conditionals — both arms each
# ══════════════════════════════════════════════════════════════════════════

class TestIsPopulatedPredicate(unittest.TestCase):

    def test_absences(self):
        for v in (None, "", "   ", "\n\t"):
            self.assertFalse(ie._is_populated(v), f"{v!r} should be absent")

    def test_zero_and_false_are_populated_not_absent(self):
        """source_tic 0 is a real tic. This is NOT a truthiness test."""
        for v in (0, False, 0.0):
            self.assertTrue(ie._is_populated(v), f"{v!r} must count as populated")

    def test_ordinary_values_are_populated(self):
        for v in ("x", 737, ["a"], {"k": "v"}):
            self.assertTrue(ie._is_populated(v))

    def test_zero_cached_value_is_protected_from_derived_none(self):
        merged = ie._merge_reconciled({"source_tic": 0}, {"source_tic": None})
        self.assertEqual(merged["source_tic"], 0)


class TestAlwaysWriteFieldsAreExempt(unittest.TestCase):
    """Lawful state-machine transitions are NOT derived values."""

    def test_state_and_filename_and_kind_always_write(self):
        merged = ie._merge_reconciled(
            {"state": "WAIT", "filename": "WAIT_x.json", "kind": "flat",
             "subject": "keep me"},
            {"state": "DONE", "filename": "DONE_x.json", "kind": "dir",
             "subject": None},
        )
        self.assertEqual(merged["state"], "DONE")
        self.assertEqual(merged["filename"], "DONE_x.json")
        self.assertEqual(merged["kind"], "dir")
        self.assertEqual(merged["subject"], "keep me")

    def test_always_write_set_is_exactly_the_state_machine_fields(self):
        self.assertEqual(set(ie._RECONCILE_ALWAYS_WRITE),
                         {"state", "filename", "kind"})

    def test_live_wait_to_done_flip_lands_through_reconcile(self):
        """A real channel move must still flip state + filename on a guarded row."""
        ibox = _mk_inbox(
            {"DONE_pkt-state-a0-estate-001.json": NON_MAILBOX_PACKET},
            {"DONE_pkt-state-a0-estate-001": dict(HAND_TYPED_ROW)},
            channel="archive",
        )
        ie.reconcile_registry(ibox, persist=True)
        row = _row_for(_read_registry(ibox), "pkt-state-a0-estate-001")
        self.assertEqual(row["state"], "DONE")
        self.assertEqual(row["filename"], "DONE_pkt-state-a0-estate-001.json")
        # ...while the guarded content fields still survive the same pass.
        for f in FIVE_DESTROYED_FIELDS:
            self.assertEqual(row[f], HAND_TYPED_ROW[f])


if __name__ == "__main__":
    unittest.main(verbosity=2)
