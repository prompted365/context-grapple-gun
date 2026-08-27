#!/usr/bin/env python3
"""Fixtures for inbox-envelope.py `validate_envelope_type` / `write_envelope` —
the ENVELOPE-TYPE GATE CATEGORY-ERROR cure (F-738-B3; ruled /review 740
KEEP-BOTH-NAMESPACES, re-ruled /review 741 as the next increment on
bk-estate-packet-lane-live-green; OM-4-741).

THE DEFECT (measured at two live fires — wave 8B tic 738, wave 11A tic 741):
`write_envelope` validated `content.envelope_type` through
`validate_envelope_type(manifest, et)`, which checked membership in
`autonomous_kernel/trigger-manifest.yaml#triggers` — a ROUTING-POLICY key
namespace carrying exactly ONE estate key (`estate_inbound_packet`) and none
for estate_outbound at all. Estate envelopes carry the CLASS:TYPE form
(`estate_inbound:state_of_estate`, `estate_outbound:doctrine_baseline`) whose
discriminator lives in `ak_control_room/envelopes.yaml#<class>.
discriminator_values` — 11 values (estate_inbound 5, estate_outbound 6). So a
LAWFUL estate envelope was REFUSED by the gate, and the estate-side adapter
crossed on a `manifest=None` bypass, reporting the bypass in the envelope body.
Every estate envelope in the federation has crossed on that bypass.

Two namespaces of DIFFERENT ARITY naming DIFFERENT OBJECTS: 11 message
class+type discriminators vs 1 routing-policy key. A rename either way is
lossy, so /review 740 ruled KEEP BOTH and ruled the defect a CATEGORY ERROR IN
THE GATE, not a naming collision.

RED-THEN-GREEN spine:
  RED   — `TestRedManifestOnlyGateRefusesLawfulEstateEnvelopes` reproduces the
          pre-cure gate INLINE (the manifest-only membership test, verbatim in
          behaviour) and proves it refuses all 11 real discriminators. This is
          the arm that did not exist when the defect shipped; it pins the
          defect's exact shape so the cure has something to be measured against.
  GREEN — `TestRegistryNamespaceAdmitsEveryRealDiscriminator` and siblings run
          the SAME 11 values through the real `validate_envelope_type` with the
          REAL registry and prove they are admitted, that a bogus type is
          refused with a TYPED reason naming the registry and the class, and
          that every non-registry form still takes the manifest path UNCHANGED.

NEGATIVE CONTROL (the load-bearing arm):
`TestNegativeControlCureIsLoadBearing` reverts the cure IN PLACE — restoring
the pre-cure `validate_envelope_type` body onto the module — and asserts the
estate refusal RETURNS, both at the function and end-to-end through
`write_envelope`. If someone reverts the cure in the source file, the GREEN
arms fail; if someone guts the cure into a no-op that merely LOOKS present,
this arm fails because the reverted behaviour would no longer differ. The pair
is what makes the proof falsifiable rather than decorative.

Per `cgg-ledger#selftest-fixtures-must-exercise-documented-conditional-paths`
every documented conditional gets BOTH arms: registry-owned vs manifest-owned,
known class vs unknown class, class-with-discriminator_values vs
class-without, envelope_type None vs present, registry present vs absent,
manifest present vs absent, and PyYAML present vs ABSENT (the import is
monkeypatched so the fallback line parser is proven to agree with PyYAML on the
real registry, not merely assumed to).

Isolation: every end-to-end case builds its own inbox tree under a
TemporaryDirectory. NOTHING reads or writes any real federation mailbox,
registry or queue. The real `ak_control_room/envelopes.yaml` and
`autonomous_kernel/trigger-manifest.yaml` are READ ONLY, never written.

DOES NOT SATISFY (rider, verbatim, tic 742): "This increment does NOT resolve
the trigger-manifest TYPED-OPEN annotation (doctrine; staged for the lead), does
NOT switch the estate-seed adapter off its bypass (the lead's consumer patch),
and does NOT flip any ratified:false bit."  These fixtures are FIXTURE-GREEN plus
a read-only live probe. NOTHING here is live-green: no estate envelope was
written through the cured gate into a real mailbox at this dispatch.

Run:  python3 -m unittest test_inbox_envelope_type_gate_tic742  (from cgg-runtime/scripts/)
"""
import builtins
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


def _zone_root() -> str:
    """Walk up to the .federation-root marker. Read-only use only."""
    p = _HERE
    for cand in [p] + list(p.parents):
        if (cand / ".federation-root").is_file():
            return str(cand)
    raise unittest.SkipTest("federation root not found above this test")


ZONE_ROOT = _zone_root()
REAL_REGISTRY = ie.load_envelope_registry(ZONE_ROOT)
REAL_MANIFEST = ie.load_trigger_manifest(ZONE_ROOT)

# The 11 real estate discriminators, read from the live registry at import time
# (never hand-copied: a frozen list would rot the moment the registry grows).
ESTATE_TYPES = tuple(
    f"{cls}:{val}"
    for cls in ("estate_inbound", "estate_outbound")
    for val in REAL_REGISTRY.get(cls, {}).get("discriminator_values", ())
)

# Non-estate forms that must keep taking the manifest path, verbatim as the live
# ent_estate_router registry and the live callers carry them.
MANIFEST_FORMS = ("standing.recalculate", "cadence.obligation",
                  "ladder.rehydration_feedback", "estate_inbound_packet")


# ── the pre-cure gate, reproduced verbatim in behaviour ────────────────────
def _precure_validate_envelope_type(manifest, envelope_type):
    """THE ORIGINAL BODY (inbox-envelope.py:137-144 before this increment)."""
    if envelope_type is None:
        return True, "ok (no type specified)"
    triggers = manifest.get("triggers", {})
    if envelope_type in triggers:
        return True, "ok"
    return False, f"Unknown envelope_type '{envelope_type}' — not in trigger-manifest.yaml"


def _mk_inbox() -> str:
    """Throwaway inbox tree. Never a real mailbox."""
    root = tempfile.mkdtemp(prefix="inbox-type-gate-t742-")
    ibox = os.path.join(root, "ent_fixture_estate_router")
    ie.ensure_inbox(ibox)
    return ibox


def _estate_envelope(etype: str = "estate_inbound:state_of_estate") -> dict:
    return ie.build_envelope(
        sender_id="a0-estate", recipient_id="ent_fixture_estate_router",
        envelope_type=etype, subject=f"{etype} — fixture", body={"packet_id": "pkt-fixture-001"},
        source_tic=742, priority="normal", category="report",
        trust_level="federated", source_event="estate_packet_arrival",
        producer="test_inbox_envelope_type_gate_tic742.py",
    )


# ══════════════════════════════════════════════════════════════════════════
# RED — the defect, reproduced
# ══════════════════════════════════════════════════════════════════════════

class TestRedManifestOnlyGateRefusesLawfulEstateEnvelopes(unittest.TestCase):

    def test_the_registry_actually_carries_eleven_estate_discriminators(self):
        """Arity is the decisive measurement — pin it, do not assume it."""
        self.assertEqual(len(REAL_REGISTRY.get("estate_inbound", {})
                             .get("discriminator_values", ())), 5)
        self.assertEqual(len(REAL_REGISTRY.get("estate_outbound", {})
                             .get("discriminator_values", ())), 6)
        self.assertEqual(len(ESTATE_TYPES), 11)

    def test_manifest_carries_exactly_one_estate_key_and_none_outbound(self):
        keys = [k for k in REAL_MANIFEST.get("triggers", {}) if "estate" in k]
        self.assertEqual(keys, ["estate_inbound_packet"])
        self.assertFalse([k for k in keys if "outbound" in k])

    def test_precure_gate_refuses_every_real_estate_discriminator(self):
        for et in ESTATE_TYPES:
            with self.subTest(envelope_type=et):
                allowed, reason = _precure_validate_envelope_type(REAL_MANIFEST, et)
                self.assertFalse(allowed, f"{et} should have been refused pre-cure")
                self.assertEqual(
                    reason,
                    f"Unknown envelope_type '{et}' — not in trigger-manifest.yaml")

    def test_precure_gate_refuses_the_wave11a_live_fire_type(self):
        """The exact type the tic-741 live fire carried."""
        allowed, reason = _precure_validate_envelope_type(
            REAL_MANIFEST, "estate_inbound:state_of_estate")
        self.assertFalse(allowed)
        self.assertIn("not in trigger-manifest.yaml", reason)


# ══════════════════════════════════════════════════════════════════════════
# GREEN — the registry namespace admits what it owns
# ══════════════════════════════════════════════════════════════════════════

class TestRegistryNamespaceAdmitsEveryRealDiscriminator(unittest.TestCase):

    def test_all_eleven_admit_through_the_registry(self):
        for et in ESTATE_TYPES:
            with self.subTest(envelope_type=et):
                allowed, reason = ie.validate_envelope_type(
                    REAL_MANIFEST, et, registry=REAL_REGISTRY)
                self.assertTrue(allowed, f"{et} refused: {reason}")
                self.assertIn("ak_control_room/envelopes.yaml#", reason)

    def test_admission_reason_names_the_class_and_its_discriminator(self):
        allowed, reason = ie.validate_envelope_type(
            REAL_MANIFEST, "estate_inbound:state_of_estate", registry=REAL_REGISTRY)
        self.assertTrue(allowed)
        self.assertEqual(
            reason,
            "ok (envelope registry: ak_control_room/envelopes.yaml#"
            "estate_inbound.packet_type=state_of_estate)")

    def test_bogus_type_in_a_real_class_is_refused_with_a_typed_reason(self):
        allowed, reason = ie.validate_envelope_type(
            REAL_MANIFEST, "estate_inbound:not_a_type", registry=REAL_REGISTRY)
        self.assertFalse(allowed)
        self.assertEqual(
            reason,
            "Unknown packet_type 'not_a_type' for envelope class 'estate_inbound' — "
            "not in ak_control_room/envelopes.yaml#estate_inbound.discriminator_values")

    def test_cross_class_type_is_refused_direction_is_not_lost(self):
        """An outbound type on the inbound class is a real error, not a synonym."""
        allowed, reason = ie.validate_envelope_type(
            REAL_MANIFEST, "estate_inbound:doctrine_baseline", registry=REAL_REGISTRY)
        self.assertFalse(allowed)
        self.assertIn("'estate_inbound'", reason)

    def test_empty_type_after_the_colon_is_refused(self):
        allowed, reason = ie.validate_envelope_type(
            REAL_MANIFEST, "estate_inbound:", registry=REAL_REGISTRY)
        self.assertFalse(allowed)
        self.assertIn("estate_inbound.discriminator_values", reason)


class TestManifestNamespaceIsUnchanged(unittest.TestCase):
    """Everything the registry does not own falls through UNCHANGED."""

    def test_non_class_forms_still_take_the_manifest_path(self):
        for et in MANIFEST_FORMS:
            with self.subTest(envelope_type=et):
                with_reg = ie.validate_envelope_type(
                    REAL_MANIFEST, et, registry=REAL_REGISTRY)
                precure = _precure_validate_envelope_type(REAL_MANIFEST, et)
                self.assertEqual(with_reg, precure,
                                 f"{et} diverged from the pre-cure manifest path")
                self.assertEqual(with_reg, (True, "ok"))

    def test_unknown_manifest_key_still_refused_with_the_same_message(self):
        et = "not.a.trigger.key"
        self.assertEqual(
            ie.validate_envelope_type(REAL_MANIFEST, et, registry=REAL_REGISTRY),
            _precure_validate_envelope_type(REAL_MANIFEST, et))

    def test_colon_form_with_an_unknown_class_falls_through_to_the_manifest(self):
        et = "not_a_class:whatever"
        allowed, reason = ie.validate_envelope_type(
            REAL_MANIFEST, et, registry=REAL_REGISTRY)
        self.assertFalse(allowed)
        self.assertEqual(reason,
                         f"Unknown envelope_type '{et}' — not in trigger-manifest.yaml")

    def test_registry_class_without_discriminator_values_falls_through(self):
        """A real class that carries no discriminator_values is undiscriminated,
        not empty-therefore-refuse. It must take the manifest path."""
        undiscriminated = [c for c, n in REAL_REGISTRY.items()
                           if not n.get("discriminator_values")]
        self.assertTrue(undiscriminated, "registry carried no undiscriminated class")
        self.assertIn("artifact.ref", undiscriminated)
        et = "artifact.ref:anything"
        allowed, reason = ie.validate_envelope_type(
            REAL_MANIFEST, et, registry=REAL_REGISTRY)
        self.assertFalse(allowed)
        self.assertEqual(reason,
                         f"Unknown envelope_type '{et}' — not in trigger-manifest.yaml")

    def test_envelope_type_none_still_passes_with_and_without_a_registry(self):
        self.assertEqual(ie.validate_envelope_type(REAL_MANIFEST, None),
                         (True, "ok (no type specified)"))
        self.assertEqual(
            ie.validate_envelope_type(REAL_MANIFEST, None, registry=REAL_REGISTRY),
            (True, "ok (no type specified)"))

    def test_absent_registry_reproduces_pre_cure_behaviour_exactly(self):
        """The honest limit, made executable: no registry => today's gate."""
        for et in ESTATE_TYPES + MANIFEST_FORMS + ("not.a.trigger.key",):
            with self.subTest(envelope_type=et):
                self.assertEqual(
                    ie.validate_envelope_type(REAL_MANIFEST, et, registry=None),
                    _precure_validate_envelope_type(REAL_MANIFEST, et))
                self.assertEqual(
                    ie.validate_envelope_type(REAL_MANIFEST, et, registry={}),
                    _precure_validate_envelope_type(REAL_MANIFEST, et))

    def test_registry_only_call_does_not_crash_on_a_none_manifest(self):
        """write_envelope may now arm the gate with the registry alone."""
        self.assertEqual(
            ie.validate_envelope_type(None, "estate_inbound:state_of_estate",
                                      registry=REAL_REGISTRY)[0], True)
        allowed, reason = ie.validate_envelope_type(
            None, "standing.recalculate", registry=REAL_REGISTRY)
        self.assertFalse(allowed)
        self.assertIn("not in trigger-manifest.yaml", reason)

    def test_positional_two_arg_signature_still_works_for_every_caller(self):
        """The only in-tree call site passes (manifest, et) positionally."""
        self.assertEqual(ie.validate_envelope_type(REAL_MANIFEST, "mogul.mandate"),
                         (True, "ok"))


# ══════════════════════════════════════════════════════════════════════════
# The loader — both arms of the PyYAML conditional
# ══════════════════════════════════════════════════════════════════════════

class TestEnvelopeRegistryLoaderBothParsePaths(unittest.TestCase):

    def test_pyyaml_path_normalizes_every_class(self):
        self.assertGreater(len(REAL_REGISTRY), 30)
        for cls, node in REAL_REGISTRY.items():
            self.assertIsInstance(node, dict)
            self.assertIn("discriminator", node)
            self.assertIsInstance(node["discriminator_values"], tuple)

    def test_no_pyyaml_fallback_agrees_with_pyyaml_exactly(self):
        """Monkeypatch the import: the fallback line parser must produce the
        IDENTICAL normalized map on the REAL registry, class for class."""
        real_import = builtins.__import__

        def _no_yaml(name, *a, **kw):
            if name == "yaml":
                raise ImportError("PyYAML absent (fixture)")
            return real_import(name, *a, **kw)

        builtins.__import__ = _no_yaml
        try:
            fallback = ie.load_envelope_registry(ZONE_ROOT)
        finally:
            builtins.__import__ = real_import
        self.assertEqual(fallback, REAL_REGISTRY)
        self.assertEqual(fallback["estate_inbound"]["discriminator_values"],
                         REAL_REGISTRY["estate_inbound"]["discriminator_values"])

    def test_gate_admits_all_eleven_under_the_no_pyyaml_fallback_too(self):
        real_import = builtins.__import__

        def _no_yaml(name, *a, **kw):
            if name == "yaml":
                raise ImportError("PyYAML absent (fixture)")
            return real_import(name, *a, **kw)

        builtins.__import__ = _no_yaml
        try:
            fallback = ie.load_envelope_registry(ZONE_ROOT)
        finally:
            builtins.__import__ = real_import
        for et in ESTATE_TYPES:
            with self.subTest(envelope_type=et):
                self.assertTrue(
                    ie.validate_envelope_type(REAL_MANIFEST, et, registry=fallback)[0])

    def test_absent_registry_file_returns_empty_map_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(ie.load_envelope_registry(tmp), {})

    def test_unparseable_registry_returns_empty_map_not_a_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "ak_control_room"
            d.mkdir()
            (d / "envelopes.yaml").write_text("envelopes: [this: is: not: a: map\n",
                                              encoding="utf-8")
            self.assertEqual(ie.load_envelope_registry(tmp), {})


# ══════════════════════════════════════════════════════════════════════════
# END TO END — write_envelope with BOTH namespaces, no bypass
# ══════════════════════════════════════════════════════════════════════════

class TestWriteEnvelopeEndToEndNoBypass(unittest.TestCase):

    def test_estate_envelope_delivers_with_manifest_AND_registry_passed(self):
        ibox = _mk_inbox()
        env = _estate_envelope()
        res = ie.write_envelope(env, ibox, manifest=REAL_MANIFEST,
                                registry=REAL_REGISTRY)
        self.assertEqual(res["status"], "delivered", res.get("reason"))
        self.assertTrue(os.path.isfile(res["path"]))

        reg = json.loads(Path(ibox, "indexes", "inbox-registry.json")
                         .read_text(encoding="utf-8"))
        row = reg["messages"][res["message_id"]]
        self.assertEqual(row["envelope_type"], "estate_inbound:state_of_estate")
        self.assertEqual(row["state"], "WAIT")

        events = [json.loads(l) for l in
                  Path(ibox, "indexes", "events.jsonl")
                  .read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertTrue(any(e["message_id"] == res["message_id"]
                            and e["to_state"] == "WAIT" for e in events))

    def test_no_bypass_needed_manifest_is_not_None(self):
        """The wave-8B/11A workaround was `manifest=None`. Prove the gate is
        ARMED here and the envelope still lands."""
        ibox = _mk_inbox()
        res = ie.write_envelope(_estate_envelope(), ibox,
                                manifest=REAL_MANIFEST, registry=REAL_REGISTRY)
        self.assertEqual(res["status"], "delivered")

    def test_all_eleven_deliver_end_to_end(self):
        for et in ESTATE_TYPES:
            with self.subTest(envelope_type=et):
                ibox = _mk_inbox()
                res = ie.write_envelope(_estate_envelope(et), ibox,
                                        manifest=REAL_MANIFEST, registry=REAL_REGISTRY)
                self.assertEqual(res["status"], "delivered", res.get("reason"))

    def test_bogus_estate_type_is_rejected_end_to_end_and_writes_nothing(self):
        ibox = _mk_inbox()
        res = ie.write_envelope(_estate_envelope("estate_inbound:not_a_type"), ibox,
                                manifest=REAL_MANIFEST, registry=REAL_REGISTRY)
        self.assertEqual(res["status"], "rejected")
        self.assertIn("ak_control_room/envelopes.yaml#estate_inbound.discriminator_values",
                      res["reason"])
        self.assertEqual(os.listdir(os.path.join(ibox, "inbound")), [])

    def test_registry_alone_arms_the_gate(self):
        """The shape the lead's adapter opt-in will use: registry, manifest=None."""
        ibox = _mk_inbox()
        ok = ie.write_envelope(_estate_envelope(), ibox,
                               manifest=None, registry=REAL_REGISTRY)
        self.assertEqual(ok["status"], "delivered")
        ibox2 = _mk_inbox()
        bad = ie.write_envelope(_estate_envelope("estate_inbound:not_a_type"), ibox2,
                                manifest=None, registry=REAL_REGISTRY)
        self.assertEqual(bad["status"], "rejected")

    def test_manifest_typed_envelope_still_delivers_unchanged(self):
        ibox = _mk_inbox()
        env = ie.build_envelope(
            sender_id="ent_homeskillet", recipient_id="ent_fixture_estate_router",
            envelope_type="mogul.mandate", subject="fixture mandate", body={},
            source_tic=742)
        res = ie.write_envelope(env, ibox, manifest=REAL_MANIFEST,
                                registry=REAL_REGISTRY)
        self.assertEqual(res["status"], "delivered")

    def test_no_gate_at_all_when_neither_namespace_is_supplied(self):
        """Pre-existing contract: no manifest => no type gate. Unchanged."""
        ibox = _mk_inbox()
        res = ie.write_envelope(_estate_envelope("estate_inbound:not_a_type"), ibox)
        self.assertEqual(res["status"], "delivered")


# ══════════════════════════════════════════════════════════════════════════
# The CLI seam — _resolve carries the registry beside the manifest
# ══════════════════════════════════════════════════════════════════════════

class TestResolveCarriesTheEnvelopeRegistry(unittest.TestCase):

    class _Args:
        zone_root = ZONE_ROOT

    def test_resolve_returns_five_and_the_fifth_is_the_envelope_registry(self):
        out = ie._resolve(self._Args())
        self.assertEqual(len(out), 5)
        zr, ar, actor_reg, man, envreg = out
        self.assertIn("estate_inbound", envreg)
        self.assertEqual(envreg["estate_inbound"]["discriminator"], "packet_type")
        self.assertIn("triggers", man)
        self.assertNotIn("triggers", envreg)  # two namespaces, never merged


# ══════════════════════════════════════════════════════════════════════════
# NEGATIVE CONTROL — the cure is load-bearing, not decorative
# ══════════════════════════════════════════════════════════════════════════

class TestNegativeControlCureIsLoadBearing(unittest.TestCase):
    """Revert the cure in place; the exact predicted breakage must return."""

    def setUp(self):
        self._real_gate = ie.validate_envelope_type

    def tearDown(self):
        ie.validate_envelope_type = self._real_gate

    def test_reverting_the_gate_restores_the_estate_refusal(self):
        # ── REVERT: restore the pre-cure manifest-only gate on the module ──
        ie.validate_envelope_type = (
            lambda manifest, envelope_type, registry=None:
            _precure_validate_envelope_type(manifest, envelope_type))

        ibox = _mk_inbox()
        res = ie.write_envelope(_estate_envelope(), ibox,
                                manifest=REAL_MANIFEST, registry=REAL_REGISTRY)
        self.assertEqual(res["status"], "rejected",
                         "revert did not reproduce the defect")
        self.assertEqual(
            res["reason"],
            "Unknown envelope_type 'estate_inbound:state_of_estate' — "
            "not in trigger-manifest.yaml")
        self.assertEqual(os.listdir(os.path.join(ibox, "inbound")), [])

        # ── RESTORE and prove the cure heals the identical scenario ──
        ie.validate_envelope_type = self._real_gate
        ibox2 = _mk_inbox()
        res2 = ie.write_envelope(_estate_envelope(), ibox2,
                                 manifest=REAL_MANIFEST, registry=REAL_REGISTRY)
        self.assertEqual(res2["status"], "delivered")
        self.assertEqual(len(os.listdir(os.path.join(ibox2, "inbound"))), 1)

    def test_reverted_gate_refuses_all_eleven_cured_gate_admits_all_eleven(self):
        ie.validate_envelope_type = (
            lambda manifest, envelope_type, registry=None:
            _precure_validate_envelope_type(manifest, envelope_type))
        refused = [et for et in ESTATE_TYPES
                   if not ie.validate_envelope_type(
                       REAL_MANIFEST, et, registry=REAL_REGISTRY)[0]]
        self.assertEqual(len(refused), 11)

        ie.validate_envelope_type = self._real_gate
        admitted = [et for et in ESTATE_TYPES
                    if ie.validate_envelope_type(
                        REAL_MANIFEST, et, registry=REAL_REGISTRY)[0]]
        self.assertEqual(len(admitted), 11)

    def test_a_gutted_no_op_cure_would_fail_this_pair(self):
        """If the cure were a no-op, reverted and live behaviour would agree.
        They must DIFFER on exactly the estate forms and AGREE on the rest."""
        live = {et: ie.validate_envelope_type(REAL_MANIFEST, et,
                                              registry=REAL_REGISTRY)[0]
                for et in ESTATE_TYPES + MANIFEST_FORMS}
        pre = {et: _precure_validate_envelope_type(REAL_MANIFEST, et)[0]
               for et in ESTATE_TYPES + MANIFEST_FORMS}
        differ = sorted(k for k in live if live[k] != pre[k])
        self.assertEqual(differ, sorted(ESTATE_TYPES))
        for k in MANIFEST_FORMS:
            self.assertEqual(live[k], pre[k])


if __name__ == "__main__":
    unittest.main(verbosity=2)
