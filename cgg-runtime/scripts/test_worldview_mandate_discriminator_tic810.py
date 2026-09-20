#!/usr/bin/env python3
"""Fixtures for the mandate[pending] DISCRIMINATOR line in office-worldview.py.

Ruled /review 805 round 1 Q1 (receipt audit-logs/governance/receipts/
2026-09-19-tic805-mandate-line-names-the-discriminator-ruling.md, 2,179 bytes,
sha16 354e5ac41989ff63); built tic 810.

THE CURE. The worldview's `mandate[pending]` line stops instructing an
unconditional stand-back and NAMES THE DISCRIMINATOR instead: read the process
table at the executable position first; if no runner is live and the mandate is
pending, the lead dispatches script-route; if one is live, stand back; never
double-spawn. Every OTHER mandate state renders byte-unchanged, and the `mine`
branch (OFFICE, owner == reading office) is byte-unchanged in every state.

WHY. The old line was RIGHT when a human typed at the boundary (the prompt gate
spawned a runner) and WRONG-BY-OMISSION when none did — the ordinary
accept-with-clear boundary fires no prompt event, so no dispatcher carries the
lane and the line told the one reader who could dispatch to stand back. The lead
cannot know which boundary it is on without reading the process table, so the
line names the discriminator rather than choosing a side.

DOES-NOT-SATISFY RIDER (attached by the ruling; travels verbatim):
  "this increment does NOT give the mandate an automatic dispatcher at a boundary
  nobody types at, does NOT change the prompt gate, does NOT move or mirror
  dispatch onto the session-start seam, and does NOT establish why the harness
  skips prompt hooks on an injected prompt."

Arms (every documented conditional, both sides — cgg-ledger#selftest-fixtures-
must-exercise-documented-conditional-paths):
  1. pending + not-mine   — all FOUR discriminator parts present
  2. pending + not-mine   — the renderer takes NO liveness reading itself
                            (zero subprocess calls; the line is a SNAPSHOT that
                            instructs the reader, never a baked liveness verdict)
  3. every OTHER status   — the legacy guard, character for character
     + not-mine             (running/consumed/failed/superseded/completed/
                            in_progress/started/unknown/missing-status)
  4. every status + mine  — NO guard at all; class OFFICE
  5. pending + not-mine   — pertinence class stays FIELD and authority is
                            unchanged (the cure is TEXT-only)
  6. owner display        — a non-Mogul owner renders its own name in both arms

The status value set is SOURCED, never guessed:
  schema enum   cgg-runtime/config/mogul-mandate.schema.json properties.status.enum
                -> pending, running, consumed, failed, superseded
  lived history audit-logs/mogul/mandates/history/*.jsonl
                -> completed (79 rows), in_progress (1 row): historical vocabulary
                   present on disk but ABSENT from the schema enum
  renderer      mandate.get('status','?') -> a MISSING status renders '?'
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

import importlib.util

_spec = importlib.util.spec_from_file_location("office_worldview",
                                               HERE / "office-worldview.py")
ow = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ow)

CYCLES = ["review_close_check", "memory_mining", "harmony_invoke"]
TIC = 810

# The legacy guard, frozen here as the BYTE-UNCHANGED contract for every
# non-pending state. If this string ever has to change, that is a new ruling.
LEGACY_GUARD = " — Mogul-owned; do NOT double-spawn (Mogul consumes it)"

SCHEMA_ENUM_NON_PENDING = ["running", "consumed", "failed", "superseded"]
LIVED_NON_ENUM = ["completed", "in_progress"]
OTHER_STATUSES = SCHEMA_ENUM_NON_PENDING + LIVED_NON_ENUM + [
    "started", "wibble_unknown_status"]
MISSING = "__MISSING__"


def _zone(tmp, status, owner_office="mogul"):
    """A minimal fixture zone. Self-locating renderer is root-pinned via the
    explicit zone_root argument (cgg-ledger#self-locating-artifact-test-isolation)."""
    z = Path(tmp)
    (z / "audit-logs" / "mogul" / "mandates").mkdir(parents=True, exist_ok=True)
    (z / "autonomous_kernel" / "telos").mkdir(parents=True, exist_ok=True)
    (z / ".ticzone").write_text('{"name":"fixture","timezone":"UTC"}')
    (z / "CLAUDE.md").write_text("# fixture\n")
    (z / "autonomous_kernel" / "telos" / "root.yaml").write_text(
        'founding_purpose_compact: "fixture telos"\n')
    (z / "autonomous_kernel" / "actor-registry.json").write_text(json.dumps({
        "actors": [
            {"entity_id": "ent_fixture_citizen", "standing": "citizen",
             "status": "active", "entity_kind": "agent", "roles": ["steward"]},
            {"entity_id": "ent_mogul", "standing": "citizen", "status": "active",
             "entity_kind": "agent", "roles": ["cycle_consumer"]},
        ], "collaboration_edges": []}))
    m = {"mandate_id": "tic-810-FIXTURE",
         "actor": {"office": owner_office, "embodiment": "cgg_runtime"},
         "trigger": {"kind": "cadence", "source_ref": "fixture"},
         "tic_context": {"current_tic": TIC, "review_due_tic": 999},
         "cycle_request": {"run_now": CYCLES, "reason": "fixture"},
         "mode": {"blocking_to_orchestrator": False, "allow_subdelegation": True},
         "created_at": "2026-09-20T00:00:00+00:00"}
    if status != MISSING:
        m["status"] = status
    (z / "audit-logs" / "mogul" / "mandates" / "current.json").write_text(
        json.dumps(m, indent=1))
    return z


def _mandate_frag(z, office):
    for f in ow.compile_fragments(z, office, TIC):
        if f["id"] == "tic.mandate":
            return f
    return None


class MandatePendingNamesTheDiscriminator(unittest.TestCase):

    def test_pending_not_mine_carries_all_four_discriminator_parts(self):
        """ARM 1 — the ruled four parts, all present in the pending line."""
        with tempfile.TemporaryDirectory() as tmp:
            f = _mandate_frag(_zone(tmp, "pending"), "ent_fixture_citizen")
            self.assertIsNotNone(f, "the mandate fragment must render")
            t = f["text"]
            # part 1 — read the process table at the executable position FIRST
            self.assertIn("process table", t)
            self.assertIn("executable position", t)
            self.assertIn("FIRST", t)
            # part 2 — none live + pending -> the LEAD dispatches script-route
            self.assertIn("no runner is live", t)
            self.assertIn("script-route", t)
            self.assertIn("the lead dispatches", t)
            # part 3 — one live -> stand back
            self.assertIn("if one is live, stand back", t)
            # part 4 — never double-spawn
            self.assertIn("never double-spawn", t)
            # the retired shape: the UNCONDITIONAL stand-back is gone from pending
            self.assertNotIn("do NOT double-spawn", t,
                             "the unconditional stand-back must not survive on the "
                             "pending arm — it is what the ruling retired")

    def test_renderer_takes_no_liveness_reading_itself(self):
        """ARM 2 — a render is a SNAPSHOT. The line instructs the READER to take
        the process-table reading; the renderer must never take it, because a
        liveness claim baked into a packet is already stale at delivery."""
        with tempfile.TemporaryDirectory() as tmp:
            z = _zone(tmp, "pending")
            calls = []
            real = ow.subprocess.run

            def spy(*a, **k):
                calls.append(a)
                return real(*a, **k)

            ow.subprocess.run = spy
            try:
                f = _mandate_frag(z, "ent_fixture_citizen")
            finally:
                ow.subprocess.run = real
            self.assertEqual(calls, [], "compile_fragments must not shell out — "
                                        "no ps/process-table read in the renderer")
            t = f["text"]
            self.assertIn("snapshot", t, "the line must declare itself a snapshot")
            # it must not assert a liveness VERDICT as fact
            self.assertNotIn("a runner is live", t.lower().replace("if no ", "X"))

    def test_every_other_status_renders_the_legacy_guard_byte_unchanged(self):
        """ARM 3 — byte-identical legacy guard for every non-pending status,
        including the two lived-but-non-enum values and a missing status."""
        for status in OTHER_STATUSES + [MISSING]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                f = _mandate_frag(_zone(tmp, status), "ent_fixture_citizen")
                shown = "?" if status == MISSING else status
                self.assertEqual(
                    f["text"],
                    f"mandate[{shown}]: {', '.join(CYCLES)}{LEGACY_GUARD}",
                    f"status {status!r} must render byte-unchanged")
                self.assertEqual(f["pertinence"]["class"], "FIELD")

    def test_mine_branch_carries_no_guard_in_every_state(self):
        """ARM 4 — owner == reading office: OFFICE class, no guard, every state."""
        for status in ["pending"] + OTHER_STATUSES + [MISSING]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                f = _mandate_frag(_zone(tmp, status), "ent_mogul")
                shown = "?" if status == MISSING else status
                self.assertEqual(f["text"],
                                 f"mandate[{shown}]: {', '.join(CYCLES)}")
                self.assertEqual(f["pertinence"]["class"], "OFFICE")
                self.assertNotIn("double-spawn", f["text"])
                self.assertNotIn("process table", f["text"])

    def test_cure_is_text_only_class_and_authority_unchanged(self):
        """ARM 5 — the cure touches TEXT only: class stays FIELD and the
        authority block is identical to a non-pending arm's."""
        with tempfile.TemporaryDirectory() as tmp:
            p = _mandate_frag(_zone(tmp, "pending"), "ent_fixture_citizen")
        with tempfile.TemporaryDirectory() as tmp:
            c = _mandate_frag(_zone(tmp, "consumed"), "ent_fixture_citizen")
        self.assertEqual(p["pertinence"]["class"], "FIELD")
        self.assertEqual(p["authority"], c["authority"])
        self.assertEqual(p["receipt"], c["receipt"])

    def test_non_mogul_owner_renders_its_own_name_in_both_arms(self):
        """ARM 6 — the owner display is not hardcoded to Mogul."""
        with tempfile.TemporaryDirectory() as tmp:
            f = _mandate_frag(_zone(tmp, "pending", owner_office="archivist"),
                              "ent_fixture_citizen")
            self.assertIn("archivist-owned and PENDING", f["text"])
            self.assertIn("(archivist consumes it)", f["text"])
        with tempfile.TemporaryDirectory() as tmp:
            f = _mandate_frag(_zone(tmp, "consumed", owner_office="archivist"),
                              "ent_fixture_citizen")
            self.assertEqual(
                f["text"],
                f"mandate[consumed]: {', '.join(CYCLES)}"
                " — archivist-owned; do NOT double-spawn (archivist consumes it)")


if __name__ == "__main__":
    unittest.main()
