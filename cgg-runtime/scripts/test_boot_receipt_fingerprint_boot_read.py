#!/usr/bin/env python3
"""Tests for boot-receipt.py content_fingerprint boot-read widening (tic 643).

COVENANT: `boot_receipt_fingerprint_includes_boot_read_fields_tic635`
  ADMITTED /review 635 §II (Architect-ratified object-2 admission [15]);
  source CogPR `cpr_boot_receipt_fingerprint_excludes_boot_read_fields_tic422`.
  current_state : content_fingerprint keys on 4 civic fields only; a 2nd emit adding
                  boot-read fields dedups + drops.
  target_state  : every semantically distinguishing boot-read field participates in the
                  fingerprint OR one authoritative emission is enforced; the FORMERLY
                  DROPPED SECOND SHAPE SURVIVES.

THE DEFECT, restated as physics: the receipt sink's idempotency key covered only the CIVIC
half of the record, while the mutation gate (boot_read_passes / gate_decision) reads the
BOOT-READ half. So an agent that closed its civic boot loop first and then emitted its honest
full-read attestation for the same (entity, tic) minted an identical receipt_id — the honest
attestation deduped away, the gate found no passing receipt, and the agent self-DoS'd the very
gate it was satisfying. Perception debt was manufactured out of an honest proof.

APPROACH CHOSEN: fingerprint-widen (ADDITIVE), not single-emission. Single-emission would
make the drop LOUD but would still not preserve the dropped shape without an upsert/merge
into an append-only lane. Widening preserves the shape by construction — two semantically
different receipts are two receipts — and keeps the deterministic-ID loop-guard intact.

ISOLATION: every emit/gate-check here runs against a --sink temp file. NOTHING touches
audit-logs/boot-injections/boot-receipts.jsonl; `test_real_sink_is_never_touched` asserts it
byte-for-byte (Self-Locating Artifact Test Isolation, applied to an enforcement engine).

Run:  python3 -m unittest test_boot_receipt_fingerprint_boot_read   (from cgg-runtime/scripts/)
"""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_BR_PATH = os.path.join(_HERE, "boot-receipt.py")
_SPEC = importlib.util.spec_from_file_location("boot_receipt", _BR_PATH)
br = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(br)

# The SIBLING identity site — receipt-drops-sweep.py mirrors these three functions and MUST
# NOT diverge, or the two writers silently split the dedup space
# (cgg-ledger#named-footgun-guard-leaves-sibling-site-unfixed).
_SWEEPER_PATH = br.zone_root() / "audit-logs" / "boot-injections" / "receipt-drops-sweep.py"
sweeper = None
if _SWEEPER_PATH.exists():
    _SSPEC = importlib.util.spec_from_file_location("receipt_drops_sweep", str(_SWEEPER_PATH))
    sweeper = importlib.util.module_from_spec(_SSPEC)
    _SSPEC.loader.exec_module(sweeper)


# --------------------------------------------------------------------------------------
# The PRE-FIX algorithm, frozen verbatim. This is the oracle for the backward-parity claim:
# a civic-only record must still hash to EXACTLY this, or every historical receipt_id in
# boot-receipts.jsonl silently becomes unreachable.
# --------------------------------------------------------------------------------------
def legacy_content_fingerprint(rec: dict) -> str:
    sem = {
        "understood_scope": rec.get("understood_scope", ""),
        "accepted_constraints": sorted(rec.get("accepted_constraints", [])),
        "abstentions": sorted(rec.get("abstentions", [])),
        "first_action_or_escalation": rec.get("first_action_or_escalation", ""),
    }
    blob = json.dumps(sem, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


CIVIC = {
    "understood_scope": "task-scoped worker; bounded to the c15 cable",
    "accepted_constraints": ["no git commits", "no queue writes"],
    "abstentions": ["no doctrine inscription"],
    "first_action_or_escalation": "read boot-receipt.py end-to-end",
}

ATTEST_FULL = {
    "full_boot_injection_read": True,
    "boot_read_mode": "full",
    "chunking": "surface_typed",
    "required_unread_ranges": [],
    "omitted_ranges": [],
    "clipped_preview_detected": False,
}


def _emit(sink: Path, entity: str, tic: int, *extra) -> dict:
    """Run the REAL CLI end-to-end against an isolation sink. Returns the parsed JSON."""
    cmd = [sys.executable, _BR_PATH, "emit", "--sink", str(sink),
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


def _gate(sink: Path, entity: str, tic: int) -> tuple:
    cmd = [sys.executable, _BR_PATH, "gate-check", "--sink", str(sink),
           "--entity", entity, "--tic", str(tic)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return r.returncode, json.loads(r.stdout)


def _rows(sink: Path) -> list:
    if not sink.exists():
        return []
    return [json.loads(l) for l in sink.read_text(encoding="utf-8").splitlines() if l.strip()]


class BackwardParity(unittest.TestCase):
    """The widening is ADDITIVE — it must not move any existing identity."""

    def test_civic_only_digest_is_byte_identical_to_pre_fix(self):
        self.assertEqual(br.content_fingerprint(CIVIC), legacy_content_fingerprint(CIVIC),
                         "a civic-only record must hash EXACTLY as it did pre-tic-643, or every "
                         "historical receipt_id in boot-receipts.jsonl becomes unreachable")

    def test_civic_only_receipt_id_is_byte_identical_to_pre_fix(self):
        self.assertEqual(br.receipt_id("ent_x", 643, br.content_fingerprint(CIVIC)),
                         br.receipt_id("ent_x", 643, legacy_content_fingerprint(CIVIC)))

    def test_empty_record_digest_unchanged(self):
        self.assertEqual(br.content_fingerprint({}), legacy_content_fingerprint({}))

    def test_non_attestation_noise_fields_do_not_enter_the_fingerprint(self):
        """created_at / model_of_record / receipt_route / source_drop are provenance, not
        semantics — including them would break dedup on every re-emit."""
        noisy = dict(CIVIC, created_at="2026-07-25T00:00:00Z", model_of_record="opus",
                     receipt_route="cadence/review", source_drop="x.json",
                     ladder_explainback="a. b. c. d. e.")
        self.assertEqual(br.content_fingerprint(noisy), br.content_fingerprint(CIVIC))


class FingerprintDiscrimination(unittest.TestCase):
    """Every semantically distinguishing boot-read field must move the digest."""

    def test_attestation_presence_changes_the_digest(self):
        self.assertNotEqual(br.content_fingerprint(dict(CIVIC, **ATTEST_FULL)),
                            br.content_fingerprint(CIVIC))

    def test_pre_fix_algorithm_collides_the_two_shapes(self):
        """Direct regression witness: under the OLD algorithm the two shapes were the SAME
        id — which is exactly why the second one was dropped."""
        self.assertEqual(legacy_content_fingerprint(CIVIC),
                         legacy_content_fingerprint(dict(CIVIC, **ATTEST_FULL)),
                         "the pre-fix collision is the defect this covenant closes")

    def test_each_gate_read_field_is_discriminating(self):
        base = dict(CIVIC, **ATTEST_FULL)
        base_fp = br.content_fingerprint(base)
        variants = {
            "full_boot_injection_read": dict(base, full_boot_injection_read=False),
            "boot_read_mode": dict(base, boot_read_mode="preview_only"),
            "chunking": dict(base, chunking="gapless"),
            "required_unread_ranges(non-empty)": dict(base, required_unread_ranges=["rows 40-80"]),
            "required_unread_ranges(null three-state)": dict(base, required_unread_ranges=None),
            "apophatic_range_bounds": dict(base, apophatic_range_bounds=["render-bounded rays"]),
            "pertinence_rationale": dict(base, pertinence_rationale="FIELD-class doctrine resident"),
            "clipped_preview_detected": dict(base, clipped_preview_detected=True),
            "coverage_proof_alternate": dict(base, coverage_proof_alternate="hash-parity proof"),
            "producer_bounded": dict(base, producer_bounded=True),
            "producer_bound_kind": dict(base, producer_bound_kind="budget_truncation"),
            "producer_follow_surface": dict(base, producer_follow_surface="active.jsonl"),
            "sealed_ids_observed": dict(base, sealed_ids_observed=["telos.founding"]),
        }
        for name, rec in variants.items():
            with self.subTest(field=name):
                self.assertNotEqual(br.content_fingerprint(rec), base_fp,
                                    f"{name} must be semantically distinguishing")

    def test_null_is_distinct_from_absent_and_from_empty_list(self):
        """The three-state coverage gate (null=N/A vs []=measured-clean) must survive into
        the identity, or a null-coverage receipt collides with a clean-coverage one."""
        absent = dict(CIVIC, full_boot_injection_read=True, boot_read_mode="full")
        empty = dict(absent, required_unread_ranges=[])
        null = dict(absent, required_unread_ranges=None)
        fps = {br.content_fingerprint(absent), br.content_fingerprint(empty),
               br.content_fingerprint(null)}
        self.assertEqual(len(fps), 3, "absent / [] / null must be three distinct identities")

    def test_list_order_is_not_semantic(self):
        """Re-declaring the SAME set of ranges in a different order must still dedup."""
        a = dict(CIVIC, **ATTEST_FULL,
                 apophatic_range_bounds=["worldview:25-rays-render-bounded", "boot-injections:6-pointers"])
        b = dict(CIVIC, **ATTEST_FULL,
                 apophatic_range_bounds=["boot-injections:6-pointers", "worldview:25-rays-render-bounded"])
        self.assertEqual(br.content_fingerprint(a), br.content_fingerprint(b))

    def test_unsortable_list_does_not_raise(self):
        """The fingerprint must never be the thing that crashes a boot receipt."""
        rec = dict(CIVIC, boot_read_mode="full", sealed_ids_observed=[{"a": 1}, "s", 3])
        self.assertEqual(len(br.content_fingerprint(rec)), 64)


class TwoEmissionDifferingFlags(unittest.TestCase):
    """THE COVENANT PROOF — end-to-end through the real CLI, against an isolation sink."""

    def setUp(self):
        self.td = tempfile.mkdtemp(prefix="boot-receipt-fp-tic643-")
        self.sink = Path(self.td) / "boot-receipts.jsonl"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.td, ignore_errors=True)

    def test_dropped_second_shape_survives(self):
        e = "ent_fixture_worker"
        first = _emit(self.sink, e, 643)                       # civic-only (the boot-LOOP close)
        second = _emit(self.sink, e, 643,                      # + boot-READ attestation
                       "--full-boot-read", "--boot-read-mode", "full",
                       "--chunking", "surface_typed")
        self.assertEqual(first["status"], "recorded")
        self.assertEqual(second["status"], "recorded",
                         "THE COVENANT: the second, attestation-bearing shape must LAND, "
                         "not dedup away")
        self.assertNotEqual(first["receipt_id"], second["receipt_id"])
        rows = _rows(self.sink)
        self.assertEqual(len(rows), 2, "both shapes are on the lane")
        attested = [r for r in rows if r.get("boot_read_mode") == "full"]
        self.assertEqual(len(attested), 1)
        self.assertTrue(attested[0]["full_boot_injection_read"])
        self.assertEqual(attested[0]["chunking"], "surface_typed")
        self.assertEqual(attested[0]["required_unread_ranges"], [])

    def test_gate_self_dos_is_closed(self):
        """The consequence that made this a defect rather than a curiosity: with only the
        civic-only receipt on the lane the gate BLOCKS; the honest attestation — formerly
        dropped — flips it to ALLOW via the CLEAN proof path (not via an override)."""
        e = "ent_fixture_worker"
        _emit(self.sink, e, 643)
        rc, d = _gate(self.sink, e, 643)
        self.assertEqual(rc, 3, "civic-only receipt must NOT satisfy the boot-read gate")
        self.assertFalse(d["allow"])

        _emit(self.sink, e, 643, "--full-boot-read", "--boot-read-mode", "full",
              "--chunking", "surface_typed")
        rc, d = _gate(self.sink, e, 643)
        self.assertEqual(rc, 0, "the formerly-dropped attestation must now satisfy the gate")
        self.assertTrue(d["allow"])
        self.assertEqual(d["via"], "boot_read_receipt",
                         "cleared by CLEAN PROOF — not by an override escape-hatch")

    def test_true_idempotency_is_preserved(self):
        """The loop-guard survives: an identical re-emit (civic-only OR attestation-bearing)
        still dedups to ONE line. Widening the key must not turn dedup off."""
        e = "ent_fixture_worker"
        _emit(self.sink, e, 643)
        again = _emit(self.sink, e, 643)
        self.assertEqual(again["status"], "deduped")

        _emit(self.sink, e, 643, "--full-boot-read", "--boot-read-mode", "full",
              "--chunking", "surface_typed")
        attest_again = _emit(self.sink, e, 643, "--full-boot-read", "--boot-read-mode", "full",
                             "--chunking", "surface_typed")
        self.assertEqual(attest_again["status"], "deduped",
                         "an IDENTICAL attestation must still collapse to one line")
        self.assertEqual(len(_rows(self.sink)), 2, "2 distinct shapes, 4 emits, 2 rows")

    def test_corrected_attestation_can_be_appended(self):
        """The operational payoff: an agent that first attested `preview_only` (a blocking
        state) can append the corrected full read and clear the gate honestly."""
        e = "ent_fixture_worker"
        _emit(self.sink, e, 643, "--boot-read-mode", "preview_only", "--chunking", "partial")
        rc, _ = _gate(self.sink, e, 643)
        self.assertEqual(rc, 3)
        corrected = _emit(self.sink, e, 643, "--full-boot-read", "--boot-read-mode", "full",
                          "--chunking", "gapless")
        self.assertEqual(corrected["status"], "recorded")
        rc, d = _gate(self.sink, e, 643)
        self.assertEqual(rc, 0)
        self.assertEqual(d["via"], "boot_read_receipt")

    def test_ranged_read_apophatic_shape_also_survives(self):
        """A partial/ranged read carries apophatic bounds + pertinence rationale — a THIRD
        distinct shape for the same (entity, tic); it must land and pass on its own terms."""
        e = "ent_fixture_worker"
        _emit(self.sink, e, 643)
        ranged = _emit(self.sink, e, 643, "--full-boot-read", "--boot-read-mode", "full",
                       "--chunking", "surface_typed",
                       "--apophatic-bound", "worldview:25-rays-render-bounded",
                       "--pertinence-rationale", "FIELD-class doctrine already resident")
        self.assertEqual(ranged["status"], "recorded")
        self.assertEqual(len(_rows(self.sink)), 2)
        rc, d = _gate(self.sink, e, 643)
        self.assertEqual(rc, 0)
        self.assertEqual(d["via"], "boot_read_receipt")

    def test_override_path_still_works_and_still_loses_to_clean_proof(self):
        """Gate precedence (tic 407) is untouched by the widening."""
        e = "ent_fixture_worker"
        subprocess.run([sys.executable, _BR_PATH, "override", "--sink", str(self.sink),
                        "--actor", e, "--tic", "643", "--reason", "fixture"],
                       capture_output=True, text=True, timeout=30, check=True)
        rc, d = _gate(self.sink, e, 643)
        self.assertEqual((rc, d["via"]), (0, "override"))
        _emit(self.sink, e, 643, "--full-boot-read", "--boot-read-mode", "full",
              "--chunking", "surface_typed")
        rc, d = _gate(self.sink, e, 643)
        self.assertEqual((rc, d["via"]), (0, "boot_read_receipt"),
                         "clean proof still outranks the audited escape-hatch")

    def test_compact_preserves_both_shapes(self):
        """compact dedups on the STORED receipt_id; two distinct shapes are two receipts,
        not duplicates."""
        e = "ent_fixture_worker"
        _emit(self.sink, e, 643)
        _emit(self.sink, e, 643, "--full-boot-read", "--boot-read-mode", "full",
              "--chunking", "surface_typed")
        r = subprocess.run([sys.executable, _BR_PATH, "compact", "--sink", str(self.sink)],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["unique"], 2)
        self.assertEqual(len(_rows(self.sink)), 2)
        rc, d = _gate(self.sink, e, 643)
        self.assertEqual(rc, 0, "the attestation survives a compact pass")


class SiblingIdentityParity(unittest.TestCase):
    """receipt-drops-sweep.py mirrors the identity functions. A divergence silently splits
    the dedup space, so the parity is asserted mechanically, not by comment."""

    @unittest.skipIf(sweeper is None, "receipt-drops-sweep.py not present")
    def test_fingerprint_parity_across_a_shape_matrix(self):
        matrix = [
            {}, CIVIC, dict(CIVIC, **ATTEST_FULL),
            dict(CIVIC, boot_read_mode="preview_only"),
            {**CIVIC, **ATTEST_FULL, "required_unread_ranges": None},
            dict(CIVIC, **ATTEST_FULL, apophatic_range_bounds=["b", "a"],
                 pertinence_rationale="why"),
            dict(CIVIC, **ATTEST_FULL, producer_bounded=True,
                 sealed_ids_observed=["z", "a"]),
        ]
        for i, rec in enumerate(matrix):
            with self.subTest(shape=i):
                self.assertEqual(br.content_fingerprint(rec), sweeper.content_fingerprint(rec))
                self.assertEqual(br.receipt_id("ent_x", 643, br.content_fingerprint(rec)),
                                 sweeper.receipt_id("ent_x", 643, sweeper.content_fingerprint(rec)))

    @unittest.skipIf(sweeper is None, "receipt-drops-sweep.py not present")
    def test_attestation_field_sets_are_identical(self):
        self.assertEqual(br._FINGERPRINT_ATTESTATION_FIELDS,
                         sweeper._FINGERPRINT_ATTESTATION_FIELDS)


class SinkIsolation(unittest.TestCase):
    """The --sink override is flag-only by design: an env var would be inherited by
    boot-read-gate.py's subprocess gate-check, i.e. a fail-closed-gate BYPASS."""

    def test_sink_override_is_not_env_readable(self):
        td = tempfile.mkdtemp(prefix="boot-receipt-envprobe-")
        try:
            fake = Path(td) / "fake.jsonl"
            env = dict(os.environ, CGG_BOOT_RECEIPT_SINK=str(fake),
                       BOOT_RECEIPT_SINK=str(fake))
            r = subprocess.run(
                [sys.executable, _BR_PATH, "gate-check", "--entity", "ent_nonexistent_probe",
                 "--tic", "999999"],
                capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(r.returncode, 3, "no env var may redirect the gate's lane")
            self.assertFalse(fake.exists(), "the gate must not have consulted the env-named sink")
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)

    def test_default_sink_resolves_to_the_real_lane(self):
        root = br.zone_root()
        self.assertEqual(br.sink_path(root),
                         root / "audit-logs" / "boot-injections" / "boot-receipts.jsonl")
        self.assertEqual(br.sink_path(root, "/tmp/x.jsonl"), Path("/tmp/x.jsonl").resolve())


class RealSinkUntouched(unittest.TestCase):
    """Honest-scope proof for the wave constraint: this test module writes NOTHING to the
    real boot-receipts.jsonl lane."""

    def test_real_sink_is_never_touched(self):
        real = br.sink_path(br.zone_root())
        if not real.exists():
            self.skipTest("real lane absent")
        digest = hashlib.sha256(real.read_bytes()).hexdigest()
        td = tempfile.mkdtemp(prefix="boot-receipt-untouched-")
        try:
            sink = Path(td) / "boot-receipts.jsonl"
            _emit(sink, "ent_fixture_worker", 643, "--full-boot-read",
                  "--boot-read-mode", "full", "--chunking", "surface_typed")
            _gate(sink, "ent_fixture_worker", 643)
            self.assertEqual(hashlib.sha256(real.read_bytes()).hexdigest(), digest,
                             "the real receipts lane must be byte-identical after a fixture run")
        finally:
            import shutil
            shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
