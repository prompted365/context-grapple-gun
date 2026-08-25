#!/usr/bin/env python3
"""Tests for the boot-read mutation gate's PER-SPAWN AXIS (tic 734).

BACKLOG ROW: bk-boot-gate-missing-per-spawn-axis (HIGH), minted tic 733, ratified for build
at /review 734 ("Ride wave 4"). SOURCE FINDING: A2-733 HIGH, in
audit-logs/governance/harpoon-office/cable-receipts/
  bk-citizen-boot-dedup-fanout-keying-first-drain-tic733.json

THE DEFECT, quoted from that receipt's findings[1] (materialized-row citation, /review 734):
  "The boot-read mutation gate resolves per (entity, tic) with no per-spawn axis, so a WARM
   sibling's complete receipt authorized MY governed writes despite my own receipt honestly
   declaring boot_read_mode='not_available'."

and the probe that measured it, quoted from probes_run[5].verbatim of the same receipt:
  "$ boot-receipt.py gate-check --entity ent_harpoon_drain_citizen --tic 733
   {"allow": true, "via": "boot_read_receipt", ..., "receipt_id": "c8c2e313e8ab7b34"}
   my own receipt id            : aa9a98a50b20f4f2  (boot_read_mode='not_available')
   the receipt the gate USED    : c8c2e313e8ab7b34  (a DIFFERENT spawn — the WARM sibling)
   -> no agent_id anywhere in the selector."

THE CURE, in two coupled halves — NEITHER alone is the discipline:
  (1) SELECTION — gate_decision(..., spawn_id=X) considers ONLY receipts carrying spawn_id X.
      A wave sibling's PASS, and an UNKEYED legacy receipt, are both non-matches.
  (2) IDENTITY IN THE FINGERPRINT — two siblings of one wave emit the same civic body and the
      same attestation, so without spawn_id in content_fingerprint they mint an identical
      receipt_id and the second DEDUPS AWAY. Half (1) without half (2) would demand a receipt
      that half (2)'s absence had just deleted — the tic-643 self-DoS, re-opened.

DEGRADE-TO-TODAY (Probe-Before-Bind; the empty-fallback is load-bearing, the same discipline
as the ARM A spawn_id fallback in subagent-citizen-boot.already_seen): an UNDECLARED check
(the primary orchestrator's own session, a legacy caller, a harness that stops shipping
agent_id) is byte-identical to the pre-734 decision, envelope included. Fail-closed applies to
the new axis ONLY where the caller opted into it.

NEGATIVE CONTROL (falsifiability — "a no-regression claim is only its executed check",
borns-tic733): each cure half is re-tested against a SOURCE-MUTATED copy of the real
boot-receipt.py with that half's lines DELETED. The mutation is asserted to have actually
applied before the control runs, so a silently-no-op control cannot pass vacuously.

ISOLATION: every emit / gate-check runs against a --sink temp file (Self-Locating Artifact
Test Isolation applied to an ENFORCEMENT engine). `test_real_sink_is_never_touched` asserts
the live lane byte-for-byte.

Run:  python3 -m unittest test_boot_receipt_per_spawn_gate_axis   (from cgg-runtime/scripts/)
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_BR_PATH = os.path.join(_HERE, "boot-receipt.py")
_SPEC = importlib.util.spec_from_file_location("boot_receipt_spawn_axis", _BR_PATH)
br = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(br)

CIVIC = {
    "understood_scope": "wave-4 build citizen; bounded to the per-spawn gate axis",
    "accepted_constraints": ["no doctrine writes", "no board artifacts"],
    "abstentions": ["no admission repin"],
    "first_action_or_escalation": "read boot-receipt.py end-to-end",
}

# The attestation a WARM boot honestly emits — boot_read_passes() -> True.
FULL_READ = ["--full-boot-read", "--boot-read-mode", "full", "--chunking", "surface_typed"]
# The attestation a COLD boot honestly emits — the exact t733 value. boot_read_passes() -> False.
COLD_READ = ["--boot-read-mode", "not_available", "--chunking", "n/a"]


# ── the two cure halves, as deletable source anchors for the negative controls ──────────
_MUT_SELECTOR = ("        if declared and receipt_spawn(r) != declared:\n"
                 "            continue\n")
_MUT_FINGERPRINT = ('    if rec.get("spawn_id"):\n'
                    '        sem["spawn_id"] = str(rec["spawn_id"])\n')


def _reverted_script(tmpdir: Path, anchor: str) -> str:
    """A copy of the REAL boot-receipt.py with `anchor` deleted — the axis half reverted.

    Uses the live artifact as the oracle rather than a hand-written 'pre-fix' re-implementation:
    a re-implementation can silently drift from the thing it claims to model. Asserts the
    deletion actually applied, so a control that mutated NOTHING cannot pass vacuously."""
    src = Path(_BR_PATH).read_text(encoding="utf-8")
    assert anchor in src, "negative-control anchor not found — the cure line moved; fix the anchor"
    out = src.replace(anchor, "", 1)
    assert out != src and anchor not in out, "negative-control mutation did not apply"
    p = tmpdir / "boot-receipt-REVERTED.py"
    p.write_text(out, encoding="utf-8")
    return str(p)


def _emit(sink: Path, entity: str, tic: int, *extra, script: str = _BR_PATH) -> dict:
    cmd = [sys.executable, script, "emit", "--sink", str(sink),
           "--entity", entity, "--tic", str(tic),
           "--understood", CIVIC["understood_scope"],
           "--first-action", CIVIC["first_action_or_escalation"]]
    for c in CIVIC["accepted_constraints"]:
        cmd += ["--constraint", c]
    for a in CIVIC["abstentions"]:
        cmd += ["--abstention", a]
    cmd += list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"emit failed: {r.returncode}\n{r.stderr}"
    return json.loads(r.stdout)


def _gate(sink: Path, entity: str, tic: int, spawn: str = None, path: str = None,
          script: str = _BR_PATH) -> tuple:
    cmd = [sys.executable, script, "gate-check", "--sink", str(sink),
           "--entity", entity, "--tic", str(tic)]
    if spawn is not None:
        cmd += ["--spawn-id", spawn]
    if path is not None:
        cmd += ["--path", path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.returncode, json.loads(r.stdout)


def _rows(sink: Path) -> list:
    if not sink.exists():
        return []
    return [json.loads(l) for l in sink.read_text(encoding="utf-8").splitlines() if l.strip()]


class _SinkCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.mkdtemp(prefix="boot-receipt-spawn-axis-")
        self.tmp = Path(self._td)
        self.sink = self.tmp / "fixture-receipts.jsonl"

    def tearDown(self):
        shutil.rmtree(self._td, ignore_errors=True)

    def _wave(self, entity="ent_harpoon_drain_citizen", tic=734,
              warm="agent_WARM_733a", cold="agent_COLD_733b", cold_receipt=True):
        """Replicate the t733 wave: one WARM sibling with a passing receipt, one COLD sibling
        whose own receipt honestly says not_available (or which emitted nothing at all)."""
        w = _emit(self.sink, entity, tic, "--spawn-id", warm, *FULL_READ)
        c = None
        if cold_receipt:
            c = _emit(self.sink, entity, tic, "--spawn-id", cold, *COLD_READ)
        return w, c


# =======================================================================================
# FIXTURE (a) — the A2-733 shape now DENIES
# =======================================================================================
class A2_733_ShapeDenies(_SinkCase):

    def test_cold_spawn_with_its_own_honest_not_available_receipt_is_DENIED(self):
        w, c = self._wave()
        rc, d = _gate(self.sink, "ent_harpoon_drain_citizen", 734, spawn="agent_COLD_733b")
        self.assertEqual(rc, 3, "the exact t733 shape must now BLOCK, not allow")
        self.assertFalse(d["allow"])
        self.assertEqual(d["via"], "none")
        self.assertEqual(d["spawn_axis"], "declared_unmatched")
        self.assertNotEqual(d.get("receipt_id"), w["receipt_id"],
                            "the warm sibling's receipt must never appear in a cold decision")

    def test_cold_spawn_that_emitted_NO_receipt_at_all_is_DENIED(self):
        self._wave(cold_receipt=False)
        rc, d = _gate(self.sink, "ent_harpoon_drain_citizen", 734, spawn="agent_COLD_733b")
        self.assertEqual(rc, 3)
        self.assertFalse(d["allow"])
        self.assertIn("spawn=agent_COLD_733b", d["reason"])

    def test_the_deny_reason_NAMES_the_sibling_so_the_cause_is_legible(self):
        w, _ = self._wave()
        _, d = _gate(self.sink, "ent_harpoon_drain_citizen", 734, spawn="agent_COLD_733b")
        self.assertIn(w["receipt_id"], d["reason"],
                      "a DENY caused by 'someone else proved it' must say so, or the next agent "
                      "re-derives the t733 confusion cold")
        self.assertIn("cannot authorize this spawn", d["reason"])

    def test_an_UNKEYED_legacy_receipt_does_not_satisfy_a_DECLARED_spawn(self):
        """Strictness: '' means UNKEYED, never WILDCARD. A pre-734 receipt is exactly the
        surface the defect ran on — it must not become a universal key by grandfathering."""
        _emit(self.sink, "ent_x", 734, *FULL_READ)          # no --spawn-id at all
        rc, d = _gate(self.sink, "ent_x", 734, spawn="agent_SOME_SPAWN")
        self.assertEqual(rc, 3)
        self.assertEqual(d["spawn_axis"], "declared_unmatched")

    def test_a_DIFFERENT_entitys_spawn_id_collision_still_denies(self):
        """The spawn axis NARROWS; it never widens. Same spawn_id under another entity is
        still the wrong receipt."""
        _emit(self.sink, "ent_other", 734, "--spawn-id", "agent_SHARED", *FULL_READ)
        rc, _ = _gate(self.sink, "ent_x", 734, spawn="agent_SHARED")
        self.assertEqual(rc, 3)


# =======================================================================================
# FIXTURE (b) — a same-spawn PASS still allows, and resolves MY receipt
# =======================================================================================
class SameSpawnStillAllows(_SinkCase):

    def test_my_own_passing_receipt_allows_and_resolves_MY_id(self):
        w, _ = self._wave(cold_receipt=False)
        mine = _emit(self.sink, "ent_harpoon_drain_citizen", 734,
                     "--spawn-id", "agent_COLD_733b", *FULL_READ)
        rc, d = _gate(self.sink, "ent_harpoon_drain_citizen", 734, spawn="agent_COLD_733b")
        self.assertEqual(rc, 0)
        self.assertTrue(d["allow"])
        self.assertEqual(d["via"], "boot_read_receipt")
        self.assertEqual(d["spawn_axis"], "matched")
        self.assertEqual(d["receipt_id"], mine["receipt_id"],
                         "the gate must resolve THIS spawn's receipt, not the warm sibling's")
        self.assertNotEqual(d["receipt_id"], w["receipt_id"])

    def test_the_warm_sibling_is_still_allowed_under_its_own_spawn(self):
        w, _ = self._wave()
        rc, d = _gate(self.sink, "ent_harpoon_drain_citizen", 734, spawn="agent_WARM_733a")
        self.assertEqual(rc, 0)
        self.assertEqual(d["receipt_id"], w["receipt_id"])

    def test_two_siblings_mint_TWO_rows_not_one(self):
        """Cure half (2). Same entity, same tic, same civic body, same attestation — the ONLY
        difference is spawn_id. Without the fingerprint layer these dedup to one row and the
        second spawn's honest proof vanishes (the tic-643 self-DoS on a new coordinate)."""
        a = _emit(self.sink, "ent_x", 734, "--spawn-id", "agent_A", *FULL_READ)
        b = _emit(self.sink, "ent_x", 734, "--spawn-id", "agent_B", *FULL_READ)
        self.assertEqual(a["status"], "recorded")
        self.assertEqual(b["status"], "recorded", "the second sibling must LAND, not dedup away")
        self.assertNotEqual(a["receipt_id"], b["receipt_id"])
        self.assertEqual(len(_rows(self.sink)), 2)
        self.assertEqual({r["spawn_id"] for r in _rows(self.sink)}, {"agent_A", "agent_B"})

    def test_the_SAME_spawn_re_emitting_identical_content_still_dedups(self):
        """Regression control on the idempotency loop-guard: per-spawn keying must not turn
        the deterministic ID into a per-call nonce."""
        a = _emit(self.sink, "ent_x", 734, "--spawn-id", "agent_A", *FULL_READ)
        b = _emit(self.sink, "ent_x", 734, "--spawn-id", "agent_A", *FULL_READ)
        self.assertEqual(b["status"], "deduped")
        self.assertEqual(a["receipt_id"], b["receipt_id"])
        self.assertEqual(len(_rows(self.sink)), 1)


# =======================================================================================
# FIXTURE (c) — UNDECLARED behaviour is byte-equal to today
# =======================================================================================
def legacy_gate_decision(root: Path, entity: str, tic: int, path=None, sink=None) -> dict:
    """The pre-tic-734 gate_decision, frozen verbatim. The oracle for the degrade-to-today
    claim: an undeclared call must return THIS dict, key-for-key and value-for-value."""
    recs = [r for r in br._read_records(br.sink_path(root, sink)) if r.get("tic") == tic]
    for r in recs:
        if entity not in (r.get("entity_id"), r.get("actor")):
            continue
        ok, why = br.boot_read_passes(r)
        if ok:
            return {"allow": True, "via": "boot_read_receipt", "reason": why,
                    "receipt_id": r.get("receipt_id")}
    for r in recs:
        if r.get("override") is True and (r.get("entity_id") == entity or r.get("actor") == entity):
            scope = r.get("override_scope")
            tp = r.get("touched_path")
            if scope in (None, "", "tic", "all") or not path or not tp or tp in path or path in tp:
                return {"allow": True, "via": "override", "reason": r.get("reason", ""),
                        "receipt_id": r.get("receipt_id")}
    near = next(((br.boot_read_passes(r)[1]) for r in recs
                 if entity in (r.get("entity_id"), r.get("actor"))),
                "no receipt for this (entity,tic)")
    return {"allow": False, "via": "none", "reason": near}


class UndeclaredIsByteEqualToToday(_SinkCase):

    def _corpora(self):
        """Every corpus shape the gate distinguishes, so the parity claim is not proven on a
        single happy path."""
        return {
            "empty": lambda: None,
            "passing_unkeyed": lambda: _emit(self.sink, "ent_x", 734, *FULL_READ),
            "failing_unkeyed": lambda: _emit(self.sink, "ent_x", 734, *COLD_READ),
            "passing_spawn_keyed": lambda: _emit(self.sink, "ent_x", 734,
                                                 "--spawn-id", "agent_A", *FULL_READ),
            "wave_warm_and_cold": lambda: self._wave(entity="ent_x"),
            "override_only": lambda: subprocess.run(
                [sys.executable, _BR_PATH, "override", "--sink", str(self.sink),
                 "--actor", "ent_x", "--tic", "734", "--reason", "clipped packet"],
                capture_output=True, text=True, timeout=30, check=True),
        }

    def test_undeclared_decision_matches_the_frozen_pre734_oracle(self):
        root = br.zone_root()
        for name, build in self._corpora().items():
            with self.subTest(corpus=name):
                self.sink.unlink(missing_ok=True)
                build()
                got = br.gate_decision(root, "ent_x", 734, None, str(self.sink), None)
                want = legacy_gate_decision(root, "ent_x", 734, None, str(self.sink))
                self.assertEqual(got, want,
                                 "an undeclared call must be byte-identical to pre-734 — the "
                                 "empty-fallback is load-bearing (Probe-Before-Bind)")

    def test_undeclared_envelope_carries_NO_spawn_keys(self):
        """Presence-keyed disclosure: a caller that did not opt in must not even SEE the axis,
        so no downstream reader can start depending on a field the legacy path never had."""
        _emit(self.sink, "ent_x", 734, "--spawn-id", "agent_A", *FULL_READ)
        for spawn in (None,):
            rc, d = _gate(self.sink, "ent_x", 734, spawn=spawn)
            self.assertEqual(rc, 0)
            self.assertNotIn("spawn_id", d)
            self.assertNotIn("spawn_axis", d)
            self.assertEqual(set(d), {"allow", "via", "reason", "receipt_id", "sink_override"})

    def test_an_empty_string_spawn_id_degrades_to_undeclared_not_to_a_deny(self):
        """The harness dropping agent_id must never be read as 'a spawn named empty-string'."""
        _emit(self.sink, "ent_x", 734, *FULL_READ)
        rc, d = _gate(self.sink, "ent_x", 734, spawn="")
        self.assertEqual(rc, 0, "empty spawn_id is UNDECLARED, never an unmatchable key")
        self.assertNotIn("spawn_axis", d)

    def test_a_spawnless_receipt_still_hashes_exactly_as_pre734(self):
        """Cure half (2) is ADDITIVE: every historical receipt_id must stay reachable."""
        with tempfile.TemporaryDirectory() as td:
            rev = _reverted_script(Path(td), _MUT_FINGERPRINT)
            spec = importlib.util.spec_from_file_location("br_pre734_fp", rev)
            old = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(old)
            plain = dict(CIVIC)
            self.assertEqual(br.content_fingerprint(plain), old.content_fingerprint(plain))
            attested = dict(CIVIC, full_boot_injection_read=True, boot_read_mode="full",
                            chunking="surface_typed", required_unread_ranges=[])
            self.assertEqual(br.content_fingerprint(attested), old.content_fingerprint(attested))
            keyed = dict(attested, spawn_id="agent_A")
            self.assertNotEqual(br.content_fingerprint(keyed), old.content_fingerprint(keyed),
                                "a spawn-keyed record MUST hash differently, or siblings collide")


# =======================================================================================
# FIXTURE (d) — NEGATIVE CONTROL: revert each cure half, the fixture must FAIL
# =======================================================================================
class NegativeControl(_SinkCase):

    def test_reverting_the_SELECTOR_makes_fixture_a_allow_again(self):
        """Falsifiability of cure half (1). With the two selection lines deleted from the REAL
        script, the exact t733 corpus resolves the WARM sibling's receipt and ALLOWS — the
        measured defect, reproduced on demand."""
        w, _ = self._wave()
        rev = _reverted_script(self.tmp, _MUT_SELECTOR)
        rc, d = _gate(self.sink, "ent_harpoon_drain_citizen", 734,
                      spawn="agent_COLD_733b", script=rev)
        self.assertEqual(rc, 0, "reverted selector must ALLOW — else fixture (a) proves nothing")
        self.assertTrue(d["allow"])
        self.assertEqual(d["receipt_id"], w["receipt_id"],
                         "reverted, the gate resolves the warm SIBLING — the A2-733 measurement")
        # and the cured script, same corpus, same command: DENY.
        rc2, _ = _gate(self.sink, "ent_harpoon_drain_citizen", 734, spawn="agent_COLD_733b")
        self.assertEqual(rc2, 3)
        self.assertNotEqual(rc, rc2, "the fixture must DISCRIMINATE cured from reverted")

    def test_reverting_the_FINGERPRINT_makes_the_second_sibling_dedup_away(self):
        """Falsifiability of cure half (2), and the proof the halves are COUPLED: reverted, the
        second sibling's honest receipt never lands — so a spawn-keyed gate would demand a row
        the dedup had just eaten."""
        rev = _reverted_script(self.tmp, _MUT_FINGERPRINT)
        a = _emit(self.sink, "ent_x", 734, "--spawn-id", "agent_A", *FULL_READ, script=rev)
        b = _emit(self.sink, "ent_x", 734, "--spawn-id", "agent_B", *FULL_READ, script=rev)
        self.assertEqual(b["status"], "deduped",
                         "reverted fingerprint must swallow the sibling — else the coupling "
                         "claim is untested")
        self.assertEqual(a["receipt_id"], b["receipt_id"])
        self.assertEqual(len(_rows(self.sink)), 1)
        # cured script, same two emits, fresh sink: two rows.
        self.sink.unlink(missing_ok=True)
        _emit(self.sink, "ent_x", 734, "--spawn-id", "agent_A", *FULL_READ)
        c = _emit(self.sink, "ent_x", 734, "--spawn-id", "agent_B", *FULL_READ)
        self.assertEqual(c["status"], "recorded")
        self.assertEqual(len(_rows(self.sink)), 2)

    def test_the_mutation_anchors_are_real(self):
        """Guard the guard: a negative control whose mutation silently no-ops passes for the
        wrong reason. _reverted_script asserts application; this pins that it can FAIL."""
        with self.assertRaises(AssertionError):
            _reverted_script(self.tmp, "this text is not in boot-receipt.py at all\n")


# =======================================================================================
# DISCLOSED HONEST LIMIT — pinned so a future change to it is DELIBERATE
# =======================================================================================
class OverridePathIsEntityScopedByDesign(_SinkCase):

    def test_a_declared_spawn_can_still_be_authorized_by_an_entity_override(self):
        """NOT an oversight. An audited override is emitted by a lead FOR AN ENTITY, typically
        before the spawn exists; narrowing it per-spawn would break the bootstrap case it exists
        for. The declared caller is TOLD (spawn_axis='override_entity_scoped') rather than left
        to assume the axis covered it. Owed motion: whether `override --spawn-id` should exist."""
        subprocess.run([sys.executable, _BR_PATH, "override", "--sink", str(self.sink),
                        "--actor", "ent_x", "--tic", "734", "--reason", "unavailable injection"],
                       capture_output=True, text=True, timeout=30, check=True)
        rc, d = _gate(self.sink, "ent_x", 734, spawn="agent_NEVER_BOOTED")
        self.assertEqual(rc, 0)
        self.assertEqual(d["via"], "override")
        self.assertEqual(d["spawn_axis"], "override_entity_scoped")

    def test_a_clean_spawn_matched_proof_still_OUTRANKS_the_override(self):
        """tic-407 precedence survives the new axis."""
        subprocess.run([sys.executable, _BR_PATH, "override", "--sink", str(self.sink),
                        "--actor", "ent_x", "--tic", "734", "--reason", "bootstrap"],
                       capture_output=True, text=True, timeout=30, check=True)
        mine = _emit(self.sink, "ent_x", 734, "--spawn-id", "agent_A", *FULL_READ)
        rc, d = _gate(self.sink, "ent_x", 734, spawn="agent_A")
        self.assertEqual(rc, 0)
        self.assertEqual(d["via"], "boot_read_receipt")
        self.assertEqual(d["receipt_id"], mine["receipt_id"])


class SpawnIsNotAnAttestationField(unittest.TestCase):
    """SELECTION vs PASS-STATE. spawn_id answers 'is this receipt MINE?', never 'is it GOOD?' —
    it must stay out of every boot-read surface the gate's pass-state reads."""

    def test_spawn_id_is_not_in_the_boot_read_field_sets(self):
        self.assertNotIn("spawn_id", br._FINGERPRINT_ATTESTATION_FIELDS)
        self.assertNotIn("spawn_id", br._BOOT_READ_FIELDS)
        self.assertNotIn("spawn_id", br._OWED_FIELDS)

    def test_boot_read_passes_is_blind_to_spawn_id(self):
        rec = {"full_boot_injection_read": True, "boot_read_mode": "full",
               "chunking": "surface_typed", "required_unread_ranges": []}
        self.assertEqual(br.boot_read_passes(rec),
                         br.boot_read_passes(dict(rec, spawn_id="agent_A")))
        bad = {"full_boot_injection_read": True, "boot_read_mode": "not_available"}
        self.assertEqual(br.boot_read_passes(bad),
                         br.boot_read_passes(dict(bad, spawn_id="agent_A")))

    def test_a_spawn_id_never_upgrades_a_failing_receipt(self):
        self.assertFalse(br.boot_read_passes({"boot_read_mode": "full", "spawn_id": "a"})[0])

    def test_receipt_spawn_reads_unkeyed_as_empty_never_as_wildcard(self):
        self.assertEqual(br.receipt_spawn({}), "")
        self.assertEqual(br.receipt_spawn({"spawn_id": None}), "")
        self.assertEqual(br.receipt_spawn({"spawn_id": ""}), "")
        self.assertEqual(br.receipt_spawn({"spawn_id": "agent_A"}), "agent_A")


class SpawnVocabularyComposesWithArmA(unittest.TestCase):
    """One spawn identity concept, two consumers. The ARM A build (same tic) keyed
    subagent-citizen-boot.already_seen on a `spawn_id` parameter sourced from the harness
    `agent_id`; this gate keys on the same name and the same source. A fork in the vocabulary
    is how two mechanisms end up disagreeing about who a spawn is."""

    @staticmethod
    def _hook():
        """Import the ARM A hook by path. Read-only and side-effect-free: the module guards
        every action behind `if __name__ == "__main__"`. Signature-based, NOT text-matching —
        a formatting change in another lane's file must not fail this lane's suite."""
        p = Path(_HERE).parent / "hooks" / "subagent-citizen-boot.py"
        if not p.is_file():
            return None
        spec = importlib.util.spec_from_file_location("subagent_citizen_boot_ro", str(p))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_the_hook_and_the_gate_use_the_same_parameter_name(self):
        m = self._hook()
        if m is None:
            self.skipTest("subagent-citizen-boot.py not present")
        import inspect
        params = inspect.signature(m.already_seen).parameters
        self.assertIn(br._SPAWN_ID_FIELD, params,
                      "one spawn identity concept, two consumers — a vocabulary fork is how two "
                      "mechanisms end up disagreeing about who a spawn is")
        self.assertEqual(br._SPAWN_ID_FIELD, "spawn_id")

    def test_the_hook_and_the_gate_share_the_empty_fallback_discipline(self):
        """Both degrade to EXACTLY the pre-734 behaviour when the harness ships no agent_id —
        never to a per-call nonce (hook side) and never to an unmatchable key (gate side)."""
        m = self._hook()
        if m is None:
            self.skipTest("subagent-citizen-boot.py not present")
        import inspect
        self.assertEqual(inspect.signature(m.already_seen).parameters["spawn_id"].default, "",
                         "the hook's empty-spawn fallback is load-bearing (Probe-Before-Bind)")
        with tempfile.TemporaryDirectory() as td:
            zr = Path(td)
            m.already_seen(zr, "sessF", "ent_f", "BRIEF", "")
            seen = json.loads((zr / "audit-logs" / "hooks" / "citizen-boot-seen.json")
                              .read_text(encoding="utf-8"))
            self.assertEqual(list(seen), ["sessF:ent_f"], "hook degrades to the legacy key shape")


class DropLaneMirrorLatency(unittest.TestCase):
    """THE SIBLING FINGERPRINT SITE — receipt-drops-sweep.py mirrors content_fingerprint, and
    the sibling suite states it "MUST NOT diverge, or the two writers silently split the dedup
    space" (cgg-ledger#named-footgun-guard-leaves-sibling-site-unfixed).

    MEASURED AT TIC 734, honestly, both directions:
      * the mirror was ALREADY divergent BEFORE this increment — it carries the civic,
        attestation and ladder_explainback layers but NOT the tic-724 ladder DECLINATION layer;
      * this increment's spawn_id layer adds a SECOND divergence.
    BOTH are LATENT, not live, for one reason only: the Write-path receipt frame (the sole
    producer of drop records) asks for NEITHER field, so no drop record carries either — the
    two writers agree on every record that actually exists today.

    Latency is not safety, it is a PRECONDITION. These tests guard the precondition rather than
    asserting the divergence: they pass now, they still pass once the mirror is reconciled, and
    they FIRE the moment the drop frame starts producing a field the mirror cannot hash. The
    reconciliation itself is handed UP (out of this increment's write fence — the sweeper lives
    under audit-logs/, not in this lane)."""

    @staticmethod
    def _sweeper():
        p = br.zone_root() / "audit-logs" / "boot-injections" / "receipt-drops-sweep.py"
        if not p.is_file():
            return None
        spec = importlib.util.spec_from_file_location("receipt_drops_sweep_ro", str(p))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    @staticmethod
    def _drop_frame():
        p = Path(_HERE).parent / "hooks" / "subagent-citizen-boot.py"
        if not p.is_file():
            return None
        spec = importlib.util.spec_from_file_location("subagent_citizen_boot_frame_ro", str(p))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m.render_write_path_receipt_frame("ent_ladder_auditor", 734)

    def test_mirror_parity_holds_for_every_shape_the_live_drop_lane_can_PRODUCE(self):
        """The invariant that is actually true today — and stays true after the mirror is
        reconciled. Scoped to the fields the drop frame prescribes, not to hypothetical ones."""
        sw = self._sweeper()
        if sw is None:
            self.skipTest("receipt-drops-sweep.py not present")
        live_shapes = {
            "civic only": CIVIC,
            "civic+full attestation": dict(CIVIC, full_boot_injection_read=True,
                                           boot_read_mode="full", chunking="gapless",
                                           required_unread_ranges=[], apophatic_range_bounds=[],
                                           pertinence_rationale="", clipped_preview_detected=False),
            "civic+attestation+explainback": dict(CIVIC, full_boot_injection_read=True,
                                                  boot_read_mode="full", chunking="surface_typed",
                                                  required_unread_ranges=[],
                                                  ladder_explainback="a. b. c. d. e."),
        }
        for name, rec in live_shapes.items():
            with self.subTest(shape=name):
                self.assertEqual(br.content_fingerprint(rec), sw.content_fingerprint(rec))
                self.assertEqual(br.receipt_id("ent_x", 734, br.content_fingerprint(rec)),
                                 sw.receipt_id("ent_x", 734, sw.content_fingerprint(rec)))

    def test_TRIPWIRE_the_drop_frame_must_not_prescribe_spawn_id_before_the_mirror_mirrors_it(self):
        """THE FORWARD GUARD. The day the Write-path frame starts asking a no-Bash citizen for
        spawn_id, two siblings' drops become distinguishable to boot-receipt.py and STILL
        identical to the sweeper — the collision this increment's fingerprint half exists to
        prevent, re-opened on the drop lane. Fix the mirror in the SAME atom as the frame."""
        frame = self._drop_frame()
        if frame is None:
            self.skipTest("subagent-citizen-boot.py not present")
        sw = self._sweeper()
        if sw is None:
            self.skipTest("receipt-drops-sweep.py not present")
        keyed = dict(CIVIC, spawn_id="agent_A")
        mirror_handles_spawn = br.content_fingerprint(keyed) == sw.content_fingerprint(keyed)
        self.assertTrue(
            f'"{br._SPAWN_ID_FIELD}"' not in frame or mirror_handles_spawn,
            "the drop frame now prescribes spawn_id but receipt-drops-sweep.py does not hash "
            "it — the two writers have split the dedup space (owed motion M2-734)")


class RealSinkUntouched(unittest.TestCase):
    """Honest-scope proof: this module writes NOTHING to the live boot-receipts.jsonl lane."""

    def test_real_sink_is_never_touched(self):
        real = br.sink_path(br.zone_root())
        before = real.read_bytes() if real.exists() else b""
        with tempfile.TemporaryDirectory() as td:
            sink = Path(td) / "s.jsonl"
            _emit(sink, "ent_probe", 999999, "--spawn-id", "agent_probe", *FULL_READ)
            _gate(sink, "ent_probe", 999999, spawn="agent_probe")
        after = real.read_bytes() if real.exists() else b""
        self.assertEqual(before, after, "the real receipt lane must be byte-identical")


if __name__ == "__main__":
    unittest.main(verbosity=2)
