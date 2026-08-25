#!/usr/bin/env python3
"""test_drop_lane_fingerprint_mirror_parity.py — M2-734's own suite (tic 735).

THE RAY THIS DISCHARGES (handed up in bk-boot-gate-per-spawn-axis-build-tic734.json, M2-734):

    "Note the shape: the mirror fell behind SILENTLY across two separate increments, and its
     own sibling suite only tested record shapes that happened to hash equal — a parity
     assertion that never fed the diverging field. Worth a ray on 'a mirror-parity test must
     enumerate the ORIGINAL's layers, not the shapes the test author happened to build'."

THE PRE-EXISTING SUITE'S SHAPE (test_boot_receipt_fingerprint_boot_read.SiblingIdentityParity)
is a hand-written `matrix = [...]` of seven record shapes. It is green, it has always been
green, and it was green through TEN TICS of divergence — because no shape in it ever carried
`ladder_explainback_declined` (diverged since /review 724) or `spawn_id` (diverged at tic 734).
A hand-built shape list can only ever test the layers its author remembered.

THE CURE IS AN AXIS CHANGE, not more shapes. This suite DERIVES the layer set by parsing the
ORIGINAL's source (boot-receipt.py::content_fingerprint) for every `sem[...]` assignment key,
then proves the mirror agrees on a record that ACTIVATES each derived layer. A layer added to
the original tomorrow is picked up with no edit here; if it is added without mirroring, THIS
suite goes red rather than staying vacuously green.

GUARD THE GUARD (borns-tic733: "a no-regression claim is only its executed check"). A derived
enumeration that silently derives NOTHING passes for the wrong reason, so:
  * the derivation is asserted to find the layers we can name today (a floor, never a ceiling);
  * every derived layer is asserted to be ACTIVATABLE — a probe record that fails to change the
    original's digest would mean the probe, not the mirror, is what is being tested;
  * a NEGATIVE CONTROL runs the whole derived comparison against a copy of the REAL sweeper with
    one mirrored layer DELETED, and asserts this suite would have caught it. The live artifact is
    the oracle — never a hand-written "pre-fix" re-implementation that can drift from the thing
    it claims to model.

SCOPE / HONEST LIMITS
  * Parity is asserted on `content_fingerprint` + `receipt_id` only — the identity surface the
    two writers share. Nothing here claims the sweeper's ingest/move/reject behavior is mirrored
    (it is not; the sweeper owns that alone and its own --selftest covers it).
  * The derivation reads `sem[<literal>]` subscript targets. A future layer written through a
    non-literal key (a computed name, an `sem.update(...)`) would not be derived — asserted
    explicitly below so the blind spot is a recorded fact, not an assumption.
  * Read-only: this module imports both artifacts and touches no lane. It writes nothing.

RUN: python3 -m pytest test_drop_lane_fingerprint_mirror_parity.py -q
"""
import ast
import importlib.util
import inspect
import textwrap
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_source(src: str, name: str):
    """Load a module from SOURCE TEXT (used by the negative control to exec a mutated copy of
    the real sweeper without ever writing it to the tree)."""
    spec = importlib.util.spec_from_loader(name, loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(src, f"<{name}>", "exec"), mod.__dict__)
    return mod


_BR_PATH = _HERE / "boot-receipt.py"
br = _load(_BR_PATH, "boot_receipt_mirror_parity_ro") if _BR_PATH.is_file() else None
_SWEEPER_PATH = (br.zone_root() / "audit-logs" / "boot-injections" / "receipt-drops-sweep.py"
                 if br is not None else None)
sw = (_load(_SWEEPER_PATH, "receipt_drops_sweep_mirror_parity_ro")
      if _SWEEPER_PATH is not None and _SWEEPER_PATH.is_file() else None)

CIVIC = {
    "understood_scope": "scope",
    "accepted_constraints": ["c1", "c2"],
    "abstentions": ["a1"],
    "first_action_or_escalation": "act",
}

# One ACTIVATOR per derivable layer key: the record fields that switch that layer ON in the
# ORIGINAL. Keyed by the `sem[...]` name the derivation finds, so an original that grows a layer
# this table does not know about fails LOUDLY (test_every_derived_layer_has_an_activator) rather
# than being silently skipped — the exact failure mode the hand-built matrix had.
_ACTIVATORS = {
    # layer 1 — the civic body; "activating" it means giving it non-default content.
    "understood_scope": dict(CIVIC),
    "accepted_constraints": dict(CIVIC),
    "abstentions": dict(CIVIC),
    "first_action_or_escalation": dict(CIVIC),
    # layer 2 — the tic-643 attestation sub-dict.
    "boot_read_attestation": dict(CIVIC, full_boot_injection_read=True, boot_read_mode="full",
                                  chunking="surface_typed", required_unread_ranges=[],
                                  apophatic_range_bounds=["b", "a"], pertinence_rationale="why",
                                  clipped_preview_detected=True, producer_bounded=True,
                                  producer_bound_kind="budget",
                                  producer_follow_surface="worldview",
                                  sealed_ids_observed=["z", "a"]),
    # layer 3 — A7-644.
    "ladder_explainback": dict(CIVIC, ladder_explainback="a. b. c. d. e."),
    # layer 4 — /review 724. DIVERGED IN THE MIRROR FOR TEN TICS.
    "ladder_explainback_declined": dict(CIVIC, ladder_explainback_declined=True,
                                        ladder_declination_reason="standing=guest render "
                                                                  "carried no ladder content",
                                        ladder_declination_standing="guest"),
    # layer 5 — tic 734 / A2-733. DIVERGED IN THE MIRROR AT BIRTH.
    "spawn_id": dict(CIVIC, spawn_id="agent_wave_sibling_B"),
}

# The floor the derivation must reach. NOT the full expected set — a ceiling assertion would
# have to be edited every time the original grows a layer, which is the maintenance shape that
# let the hand-built matrix rot. This only proves the parser found real work to do.
_KNOWN_LAYERS_FLOOR = {"boot_read_attestation", "ladder_explainback",
                       "ladder_explainback_declined", "spawn_id"}


def derive_layer_keys(fn) -> set:
    """THE AXIS. Parse the ORIGINAL content_fingerprint's source and return every literal key it
    assigns into its `sem` dict — i.e. every semantic layer that participates in the digest.

    Derived from the artifact, never from a list this file maintains."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    keys = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            # sem["<literal>"] = ...
            if (isinstance(tgt, ast.Subscript) and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == "sem" and isinstance(tgt.slice, ast.Constant)
                    and isinstance(tgt.slice.value, str)):
                keys.add(tgt.slice.value)
            # sem = { "<literal>": ..., ... }  (the civic body)
            if isinstance(tgt, ast.Name) and tgt.id == "sem" and isinstance(node.value, ast.Dict):
                for k in node.value.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.add(k.value)
    return keys


@unittest.skipIf(br is None or sw is None, "boot-receipt.py / receipt-drops-sweep.py not present")
class DerivedLayerEnumeration(unittest.TestCase):
    """The derivation itself, before it is used to judge anything."""

    def test_derivation_finds_the_layers_we_can_name_today(self):
        got = derive_layer_keys(br.content_fingerprint)
        missing = _KNOWN_LAYERS_FLOOR - got
        self.assertEqual(missing, set(),
                         f"the source derivation missed known layer(s) {missing}: the parser is "
                         f"broken, and a broken parser would make every parity test below pass "
                         f"vacuously. Derived: {sorted(got)}")
        self.assertTrue(all(isinstance(k, str) and k for k in got))

    def test_derivation_is_not_empty(self):
        """GUARD THE GUARD: an ast walk that returns nothing passes every comparison below."""
        self.assertGreaterEqual(len(derive_layer_keys(br.content_fingerprint)), 5)

    def test_every_derived_layer_has_an_activator(self):
        """A layer added to the original that this suite cannot ACTIVATE is a layer this suite
        cannot test. Fail loudly and name it, rather than skipping it into the same silence the
        hand-built matrix provided for ten tics."""
        unknown = derive_layer_keys(br.content_fingerprint) - set(_ACTIVATORS)
        self.assertEqual(
            unknown, set(),
            f"content_fingerprint grew layer(s) {sorted(unknown)} with no activator record here. "
            f"Add one to _ACTIVATORS *and* mirror the layer in receipt-drops-sweep.py — the two "
            f"are one closed consumer set.")

    def test_each_activator_actually_activates_its_layer(self):
        """The probes must be probes: a record that does not change the ORIGINAL's digest away
        from the civic baseline proves nothing about the mirror."""
        base = br.content_fingerprint(CIVIC)
        for key in sorted(derive_layer_keys(br.content_fingerprint) - set(CIVIC)):
            with self.subTest(layer=key):
                self.assertNotEqual(
                    br.content_fingerprint(_ACTIVATORS[key]), base,
                    f"activator for '{key}' does not change the original's digest — it is not "
                    f"exercising the layer it claims to")

    def test_the_derivation_blind_spot_is_recorded_not_assumed(self):
        """Honest limit, asserted: the derivation reads LITERAL subscript/dict keys only. If the
        original ever writes a layer through a computed key or sem.update(...), this suite would
        not see it. Pinned so the day that changes, this test is the thing that says so."""
        src = textwrap.dedent(inspect.getsource(br.content_fingerprint))
        self.assertNotIn("sem.update(", src,
                         "content_fingerprint now writes layers via sem.update() — the literal-key "
                         "derivation above no longer enumerates the original; widen derive_layer_keys")


@unittest.skipIf(br is None or sw is None, "boot-receipt.py / receipt-drops-sweep.py not present")
class MirrorParityOverDerivedLayers(unittest.TestCase):
    """M2-734's actual claim: the mirror agrees with the original on EVERY derived layer."""

    def test_fingerprint_parity_on_every_derived_layer(self):
        for key in sorted(derive_layer_keys(br.content_fingerprint)):
            rec = _ACTIVATORS[key]
            with self.subTest(layer=key):
                self.assertEqual(br.content_fingerprint(rec), sw.content_fingerprint(rec),
                                 f"layer '{key}' diverges between boot-receipt.py and "
                                 f"receipt-drops-sweep.py — the two writers have split the dedup "
                                 f"space (cgg-ledger#named-footgun-guard-leaves-sibling-site-unfixed)")

    def test_receipt_id_parity_on_every_derived_layer(self):
        for key in sorted(derive_layer_keys(br.content_fingerprint)):
            rec = _ACTIVATORS[key]
            with self.subTest(layer=key):
                self.assertEqual(
                    br.receipt_id("ent_x", 735, br.content_fingerprint(rec)),
                    sw.receipt_id("ent_x", 735, sw.content_fingerprint(rec)))

    def test_all_layers_at_once(self):
        """Layers compose; parity must survive the composition, not just each layer alone."""
        rec = {}
        for key in sorted(derive_layer_keys(br.content_fingerprint)):
            rec.update(_ACTIVATORS[key])
        self.assertEqual(br.content_fingerprint(rec), sw.content_fingerprint(rec))

    def test_attestation_field_tuples_are_element_identical(self):
        """Layer 2's CONTENT is a shared tuple; parity of the function is not parity of its
        vocabulary. (Also asserted in the sibling suite; kept here so this file stands alone.)"""
        self.assertEqual(br._FINGERPRINT_ATTESTATION_FIELDS, sw._FINGERPRINT_ATTESTATION_FIELDS)

    def test_backward_parity_a_bare_civic_record_is_unaffected(self):
        """The additive discipline: adding layers 4 and 5 to the mirror must not move the digest
        of any record that carries neither — every historical drop-lane receipt_id stays valid."""
        self.assertEqual(br.content_fingerprint(CIVIC), sw.content_fingerprint(CIVIC))
        self.assertEqual(br.content_fingerprint({}), sw.content_fingerprint({}))

    def test_spawn_id_is_an_identity_coordinate_on_BOTH_sides(self):
        """spawn_id must not have been mirrored by dropping it into the attestation vocabulary —
        that would make it a pass-state input on the drop lane and an identity coordinate on the
        emit lane, which is a worse divergence than the one being cured."""
        self.assertNotIn("spawn_id", br._FINGERPRINT_ATTESTATION_FIELDS)
        self.assertNotIn("spawn_id", sw._FINGERPRINT_ATTESTATION_FIELDS)


@unittest.skipIf(br is None or sw is None, "boot-receipt.py / receipt-drops-sweep.py not present")
class NegativeControl(unittest.TestCase):
    """FALSIFIABILITY. Re-run the derived comparison against a copy of the REAL sweeper with one
    mirrored layer surgically removed, and prove this suite catches it. Without this, "the mirror
    is reconciled" is an assertion about code I wrote, not a measurement."""

    @staticmethod
    def _sweeper_without(anchor: str):
        src = _SWEEPER_PATH.read_text(encoding="utf-8")
        if anchor not in src:
            raise AssertionError(f"negative-control anchor not found in the real sweeper: {anchor!r}")
        mutated = src.replace(anchor, "")
        assert mutated != src, "the deletion did not apply — the control would pass for the wrong reason"
        return _load_source(mutated, "receipt_drops_sweep_reverted_ro")

    _SPAWN_ANCHOR = ('    if rec.get("spawn_id"):\n'
                     '        sem["spawn_id"] = str(rec["spawn_id"])\n')
    _DECLINATION_ANCHOR = ('    if rec.get("ladder_explainback_declined"):\n'
                           '        sem["ladder_explainback_declined"] = {\n'
                           '            "reason": rec.get("ladder_declination_reason", ""),\n'
                           '            "standing": rec.get("ladder_declination_standing", ""),\n'
                           '        }\n')

    def test_reverting_the_spawn_layer_is_CAUGHT(self):
        reverted = self._sweeper_without(self._SPAWN_ANCHOR)
        rec = _ACTIVATORS["spawn_id"]
        self.assertNotEqual(br.content_fingerprint(rec), reverted.content_fingerprint(rec),
                            "the spawn layer was deleted from the mirror and the digests still "
                            "matched — this suite does not discriminate")
        self.assertEqual(br.content_fingerprint(CIVIC), reverted.content_fingerprint(CIVIC),
                         "reverting the spawn layer must not disturb a spawnless record "
                         "(proves the layer is additive, and that the mutation was surgical)")

    def test_reverting_the_declination_layer_is_CAUGHT(self):
        reverted = self._sweeper_without(self._DECLINATION_ANCHOR)
        rec = _ACTIVATORS["ladder_explainback_declined"]
        self.assertNotEqual(br.content_fingerprint(rec), reverted.content_fingerprint(rec),
                            "the /review-724 declination layer was deleted from the mirror and "
                            "the digests still matched — this suite does not discriminate")
        self.assertEqual(br.content_fingerprint(CIVIC), reverted.content_fingerprint(CIVIC))

    def test_the_control_itself_can_fail(self):
        """GUARD THE GUARD: a negative control whose mutation silently no-ops passes for the
        wrong reason. Prove the anchor assertion has teeth."""
        with self.assertRaises(AssertionError):
            self._sweeper_without("### this anchor does not exist in the sweeper ###")


@unittest.skipIf(br is None or sw is None, "boot-receipt.py / receipt-drops-sweep.py not present")
class RealLaneUntouched(unittest.TestCase):
    """Honest-scope proof: this module is pure read + in-memory hashing."""

    def test_no_write_to_the_receipt_lane(self):
        real = br.sink_path(br.zone_root())
        before = real.read_bytes() if real.exists() else b""
        for rec in _ACTIVATORS.values():
            br.content_fingerprint(rec)
            sw.content_fingerprint(rec)
        after = real.read_bytes() if real.exists() else b""
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
