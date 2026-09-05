#!/usr/bin/env python3
"""B2 WAVE 12 — lib/confidence_tier.py on the shared enum-guard engine.

Ruled by audit-logs/governance/backlog-gunslinger-hoist/B2-wave-12-SIGNED-tic775.json
(self-sha b4f2177919d6bc72 over STAGED cf65b8c68db0dcfe, Architect-signed at tic
775). Row `bk-off-enum-drift-field-generic-writer-topology`; basis OM-W11-4 /
F-773-W11-3 handed up by the wave-11 build citizen.

THREE ARMS, ONE INCREMENT:
  ARM A  lib/confidence_tier.py consumes lib/enum_vocabulary_guard.py for the
         contract READ and the BASE lawful/off_enum decision.
  ARM B  the STRUCTURAL pin below — confidence_tier holds the shared module
         OBJECT by IDENTITY, not a resemblance between two copies. This is the
         same proof shape wave 11 used for the three pending_class writers, now
         extended to the fourth copy of the triple.
  ARM C  the EQUIVALENCE TABLE + the revert-control.

WHY IDENTITY AND NOT RESEMBLANCE (the wave-11 lesson, inherited): a
CONVENTIONAL test — "the writer classifies the same values the engine does" —
stays GREEN even when the guard is two copies quietly drifting apart, because
two faithful copies agree until the day one of them is edited. Only an OBJECT
identity assertion fails on the re-inline. TestRevertControl proves this test
has that tooth by monkeypatching a behaviourally IDENTICAL local copy in and
watching the identity pin go false while every behavioural probe stays green.

THE EQUIVALENCE TABLE IS FROZEN PRE-MIGRATION. Every expectation below was
captured from the module as it stood BEFORE arm A was written (CGG d6171e1,
confidence_tier.py sha256 3a4fc9e2ffa315d3…, 78 lines), across all three import
forms that exist on disk, then pasted here as literal text. Nothing in this file
is read back from the module under test to build its own expectation.

DOES NOT SATISFY (rider carried verbatim from the wave-12 ruling,
B2-wave-12-SIGNED-tic775.json): "this increment does NOT resolve the tier
family's empty-string semantics (unchanged, empty_string_is_absence=False); does
NOT touch the pending_class writers or their guards; does NOT re-truth any
contract JSON; does NOT touch the office_map (standing fence /review 772 Q5);
does NOT author the HOLD generator contract (OM-W11-3, un-slotted); does NOT
cure the standing collection error (P6)."

EVIDENCE CLASS: FIXTURE-GREEN. Every probe here runs against the modules as
imported in this process. Nothing in this file exercises a live queue write, and
no result here is promoted to live-green or wave-green by prose.
"""

import importlib.util
import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_LIB = _HERE / "lib"

for _p in (str(_LIB), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import confidence_tier  # noqa: E402
import enum_vocabulary_guard  # noqa: E402


# ---------------------------------------------------------------------------
# The FROZEN pre-migration equivalence table.
# ---------------------------------------------------------------------------
# The shared suffix of every refusal message, captured verbatim pre-migration.
_FROZEN_TAIL = (
    " Lawful values: ['convergent', 'measured', 'measured_single_locus', "
    "'reinforced', 'tentative'] or absent. Governing artifact: "
    "contracts/confidence-tier-enum-v1.json (ratified /review 708; ruling rows "
    "audit-logs/reviews/2026-08-12.jsonl decision_id off-enum-ruling-1..4)"
)

# The per-kind refusal DETAIL, captured verbatim pre-migration. `{r}` is the
# frozen repr() of the probe value, also captured pre-migration (below).
_FROZEN_DETAIL = {
    "class_bleed": ("{r} is a lawful confidence_class value in the "
                    "confidence_tier field — field-routing bleed, not a tier"),
    "non_tier_marker": ("{r} asserts no tier — represent 'no tier "
                        "asserted' by omitting the field"),
    "off_enum": "{r} is not a ratified confidence_tier",
}


class _Weird:
    """A non-string with a STABLE repr (no memory address in the text)."""

    def __repr__(self):
        return "<_Weird>"


_StrSub = type("S", (str,), {})

# (probe_id, value, FROZEN expected kind, FROZEN expected repr)
# 32 probes: all four kinds, None, empty string, hashable AND unhashable
# non-strings, a str subclass, unicode, and whitespace/case near-misses.
_PROBES = [
    ("none", None, "lawful", "None"),
    ("empty_string", "", "off_enum", "''"),

    ("lawful.convergent", "convergent", "lawful", "'convergent'"),
    ("lawful.measured", "measured", "lawful", "'measured'"),
    ("lawful.measured_single_locus", "measured_single_locus", "lawful",
     "'measured_single_locus'"),
    ("lawful.reinforced", "reinforced", "lawful", "'reinforced'"),
    ("lawful.tentative", "tentative", "lawful", "'tentative'"),

    ("class_bleed.descriptive", "descriptive", "class_bleed", "'descriptive'"),
    ("class_bleed.inferential", "inferential", "class_bleed", "'inferential'"),
    ("class_bleed.exact", "exact", "class_bleed", "'exact'"),
    ("class_bleed.mixed", "mixed", "class_bleed", "'mixed'"),

    ("non_tier_marker.unknown", "unknown", "non_tier_marker", "'unknown'"),
    ("non_tier_marker.observed", "observed", "non_tier_marker", "'observed'"),

    ("off_enum.high", "high", "off_enum", "'high'"),
    ("off_enum.extremely_sure", "extremely_sure", "off_enum", "'extremely_sure'"),
    ("off_enum.medium", "medium", "off_enum", "'medium'"),
    ("off_enum.MEASURED_upper", "MEASURED", "off_enum", "'MEASURED'"),
    ("off_enum.measured_space", " measured", "off_enum", "' measured'"),
    ("off_enum.unicode", "mesuré", "off_enum", "'mesuré'"),

    # non-strings, HASHABLE
    ("nonstring.int", 5, "off_enum", "5"),
    ("nonstring.zero", 0, "off_enum", "0"),
    ("nonstring.float", 1.5, "off_enum", "1.5"),
    ("nonstring.bool_true", True, "off_enum", "True"),
    ("nonstring.bool_false", False, "off_enum", "False"),
    ("nonstring.tuple", ("measured",), "off_enum", "('measured',)"),
    ("nonstring.object", _Weird(), "off_enum", "<_Weird>"),

    # non-strings, UNHASHABLE — these are the probes that crash any refinement
    # that runs a membership test before re-asserting the isinstance(str) guard.
    ("nonstring.list", ["measured"], "off_enum", "['measured']"),
    ("nonstring.dict", {"a": 1}, "off_enum", "{'a': 1}"),
    ("nonstring.set", {1, 2}, "off_enum", "{1, 2}"),

    # str SUBCLASS — isinstance(str) is True, membership still resolves
    ("strsubclass.lawful", _StrSub("measured"), "lawful", "'measured'"),
    ("strsubclass.offenum", _StrSub("nope"), "off_enum", "'nope'"),
]

_REFUSABLE_KINDS = ("class_bleed", "non_tier_marker", "off_enum")


def _frozen_refusal(frozen_repr, kind):
    """Build the expected message from FROZEN parts only."""
    return _FROZEN_DETAIL[kind].format(r=frozen_repr) + "." + _FROZEN_TAIL


def _load_under(name, path):
    """Load a module from an explicit file path under an explicit name."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# ARM B — the structural pin
# ---------------------------------------------------------------------------
class TestArmBSharedEngineStructuralPin(unittest.TestCase):
    """confidence_tier consumes the shared module OBJECT, by identity."""

    def test_confidence_tier_holds_the_shared_engine_module_object(self):
        self.assertIs(confidence_tier.enum_vocabulary_guard,
                      enum_vocabulary_guard,
                      "confidence_tier must hold THE shared engine object, not "
                      "a second copy loaded under another name")

    def test_the_engine_is_the_sys_modules_singleton(self):
        self.assertIs(confidence_tier.enum_vocabulary_guard,
                      sys.modules["enum_vocabulary_guard"])

    def test_classify_is_the_engine_callable_by_identity(self):
        self.assertIs(confidence_tier.enum_vocabulary_guard.classify,
                      enum_vocabulary_guard.classify)

    def test_load_contract_is_the_engine_callable_by_identity(self):
        self.assertIs(confidence_tier.enum_vocabulary_guard.load_contract,
                      enum_vocabulary_guard.load_contract)

    def test_the_engine_module_resolves_to_the_shared_lib_file(self):
        self.assertEqual(
            Path(confidence_tier.enum_vocabulary_guard.__file__).resolve(),
            (_LIB / "enum_vocabulary_guard.py").resolve())

    def test_the_source_names_the_shared_import(self):
        """A re-inline that leaves a stale attribute behind is still caught."""
        src = (_LIB / "confidence_tier.py").read_text(encoding="utf-8")
        self.assertIn("import enum_vocabulary_guard", src)
        self.assertIn("enum_vocabulary_guard.classify(", src)
        self.assertIn("enum_vocabulary_guard.load_contract(", src)

    def test_the_base_classification_is_delegated_not_reimplemented(self):
        """The module must not carry its own inline base membership test."""
        src = (_LIB / "confidence_tier.py").read_text(encoding="utf-8")
        body = src.split("def classify_tier_value", 1)[1].split("def refusal_message", 1)[0]
        self.assertIn("enum_vocabulary_guard.classify(", body)
        self.assertIn("empty_string_is_absence=False", body,
                      "the tier family's empty-string semantics must stay "
                      "EXPLICIT at the call, never inherited by default")

    def test_all_four_contract_guarded_writers_share_one_engine_object(self):
        """The wave-11 three-writer pin, extended to the fourth copy.

        Wave 11 unified queue-lifecycle-writeback / cpr-extract /
        queue_event_writer. confidence_tier was the fourth instance of the same
        triple (F-773-W11-3). All four must now name ONE engine.
        """
        writers = {
            "queue-lifecycle-writeback.py": _HERE / "queue-lifecycle-writeback.py",
            "cpr-extract.py": _HERE / "cpr-extract.py",
            "queue_event_writer.py": _HERE / "queue_event_writer.py",
            "lib/confidence_tier.py": _LIB / "confidence_tier.py",
        }
        for label, path in writers.items():
            with self.subTest(writer=label):
                src = path.read_text(encoding="utf-8")
                self.assertIn("import enum_vocabulary_guard", src,
                              f"{label} must consume the shared engine")

    def test_the_engine_holds_no_tier_vocabulary(self):
        """Engine-content separation: the engine must stay content-free."""
        src = (_LIB / "enum_vocabulary_guard.py").read_text(encoding="utf-8")
        for token in ("confidence-tier-enum-v1.json", "TIER_ENUM",
                      "class_bleed", "non_tier_marker"):
            with self.subTest(token=token):
                self.assertNotIn(
                    token, src,
                    "the shared engine must hold NO vocabulary — the tier "
                    "family's content stays caller-side")


# ---------------------------------------------------------------------------
# ARM C — the equivalence table
# ---------------------------------------------------------------------------
class TestArmCEquivalenceTable(unittest.TestCase):
    """Public API byte-compatibility against the FROZEN pre-migration table."""

    def test_classify_matches_the_frozen_table(self):
        for pid, value, expected_kind, _repr in _PROBES:
            with self.subTest(probe=pid):
                self.assertEqual(confidence_tier.classify_tier_value(value),
                                 expected_kind)

    def test_every_probe_returns_one_of_the_four_ruled_strings(self):
        allowed = {"lawful", "class_bleed", "non_tier_marker", "off_enum"}
        for pid, value, _kind, _repr in _PROBES:
            with self.subTest(probe=pid):
                self.assertIn(confidence_tier.classify_tier_value(value), allowed)

    def test_the_four_kinds_are_all_actually_exercised(self):
        """Guard against a table that silently stops covering a kind."""
        covered = {k for _pid, _v, k, _r in _PROBES}
        self.assertEqual(
            covered, {"lawful", "class_bleed", "non_tier_marker", "off_enum"})

    def test_refusal_messages_are_byte_identical_to_the_frozen_table(self):
        for pid, value, _kind, frozen_repr in _PROBES:
            for kind in _REFUSABLE_KINDS:
                with self.subTest(probe=pid, kind=kind):
                    self.assertEqual(confidence_tier.refusal_message(value, kind),
                                     _frozen_refusal(frozen_repr, kind))

    def test_refusal_on_a_lawful_kind_still_raises_keyerror(self):
        """Pre-migration behaviour: 'lawful' is not a refusal kind."""
        with self.assertRaises(KeyError):
            confidence_tier.refusal_message("measured", "lawful")

    def test_unhashable_non_strings_do_not_raise(self):
        """The isinstance(str) guard must stay AHEAD of every membership test.

        A refinement that hashes before re-asserting the guard raises
        TypeError: unhashable type. This is the probe that catches it.
        """
        for pid, value, expected_kind, _r in _PROBES:
            if not pid.startswith("nonstring."):
                continue
            with self.subTest(probe=pid):
                try:
                    got = confidence_tier.classify_tier_value(value)
                except TypeError as exc:  # pragma: no cover - the defect shape
                    self.fail(f"{pid} raised TypeError: {exc}")
                self.assertEqual(got, expected_kind)

    def test_module_level_bindings_are_present_and_frozensets(self):
        self.assertEqual(sorted(confidence_tier.TIER_ENUM),
                         ["convergent", "measured", "measured_single_locus",
                          "reinforced", "tentative"])
        self.assertEqual(sorted(confidence_tier.CONFIDENCE_CLASS_VALUES),
                         ["descriptive", "exact", "inferential", "mixed"])
        self.assertEqual(sorted(confidence_tier.NON_TIER_MARKERS),
                         ["observed", "unknown"])
        for name in ("TIER_ENUM", "CONFIDENCE_CLASS_VALUES", "NON_TIER_MARKERS"):
            with self.subTest(binding=name):
                self.assertIsInstance(getattr(confidence_tier, name), frozenset)

    def test_governing_text_is_byte_identical(self):
        self.assertEqual(
            confidence_tier.GOVERNING,
            "contracts/confidence-tier-enum-v1.json (ratified /review 708; "
            "ruling rows audit-logs/reviews/2026-08-12.jsonl "
            "decision_id off-enum-ruling-1..4)")

    def test_the_contract_is_loaded_and_module_level(self):
        self.assertIsInstance(confidence_tier._CONTRACT, dict)
        self.assertIn("enum", confidence_tier._CONTRACT)
        self.assertIn("refused_as_tier", confidence_tier._CONTRACT)

    def test_bindings_are_read_at_call_time_not_captured_at_import(self):
        """The ruled STAYED-state discipline.

        A lib-cached copy of the enum would keep classifying against the
        ORIGINAL set after a rebind, defeating any drift control. Rebinding the
        module-level name must change the verdict.
        """
        original = confidence_tier.TIER_ENUM
        try:
            confidence_tier.TIER_ENUM = frozenset({"measured"})
            self.assertEqual(
                confidence_tier.classify_tier_value("tentative"), "off_enum",
                "classify must read TIER_ENUM at CALL time")
            self.assertEqual(confidence_tier.classify_tier_value("measured"),
                             "lawful")
        finally:
            confidence_tier.TIER_ENUM = original
        self.assertEqual(confidence_tier.classify_tier_value("tentative"),
                         "lawful", "the binding must be restored")

    def test_class_bleed_refinement_reads_its_binding_at_call_time(self):
        original = confidence_tier.CONFIDENCE_CLASS_VALUES
        try:
            confidence_tier.CONFIDENCE_CLASS_VALUES = frozenset()
            self.assertEqual(confidence_tier.classify_tier_value("exact"),
                             "off_enum")
        finally:
            confidence_tier.CONFIDENCE_CLASS_VALUES = original
        self.assertEqual(confidence_tier.classify_tier_value("exact"),
                         "class_bleed")

    def test_non_tier_marker_refinement_reads_its_binding_at_call_time(self):
        original = confidence_tier.NON_TIER_MARKERS
        try:
            confidence_tier.NON_TIER_MARKERS = frozenset()
            self.assertEqual(confidence_tier.classify_tier_value("observed"),
                             "off_enum")
        finally:
            confidence_tier.NON_TIER_MARKERS = original
        self.assertEqual(confidence_tier.classify_tier_value("observed"),
                         "non_tier_marker")

    def test_empty_string_semantics_are_unchanged_off_enum(self):
        """The rider's first clause, pinned.

        `""` is OFF_ENUM for the tier family (empty_string_is_absence=False).
        The wave-12 increment does NOT resolve the empty-string question — it
        carries this family's existing answer byte-for-byte.
        """
        self.assertEqual(confidence_tier.classify_tier_value(""), "off_enum")
        self.assertEqual(
            enum_vocabulary_guard.classify("", confidence_tier.TIER_ENUM,
                                           empty_string_is_absence=False),
            enum_vocabulary_guard.OFF_ENUM)


# ---------------------------------------------------------------------------
# ARM C — import-form parity (the three forms that exist on disk)
# ---------------------------------------------------------------------------
class TestArmCImportFormParity(unittest.TestCase):
    """All three real import forms must behave identically.

    Measured at tic 775, not assumed:
      form 1  `from confidence_tier import ...`     queue-lifecycle-writeback.py:172
      form 2  `from lib.confidence_tier import ...` cogpr-ingest.py:331
      form 3  spec_from_file_location, arbitrary name
                                          test_proof_horizon_ladder_tic769.py:490
    """

    def test_spec_from_file_location_form_matches_the_frozen_table(self):
        mod = _load_under("confidence_tier_parity_probe_tic775",
                          _LIB / "confidence_tier.py")
        for pid, value, expected_kind, frozen_repr in _PROBES:
            with self.subTest(probe=pid):
                self.assertEqual(mod.classify_tier_value(value), expected_kind)
                self.assertEqual(mod.refusal_message(value, "off_enum"),
                                 _frozen_refusal(frozen_repr, "off_enum"))

    def test_cogpr_ingest_import_form_resolves_the_engine(self):
        """cogpr-ingest.py puts ONLY scripts/ on sys.path — never scripts/lib.

        Before this increment confidence_tier imported nothing but stdlib, so
        that worked by accident. Consuming a sibling lib makes the path question
        LOAD-BEARING: a bare `import enum_vocabulary_guard` raises
        ModuleNotFoundError under this form. Run in a SUBPROCESS so this
        process's already-populated sys.path/sys.modules cannot mask the defect.
        """
        code = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(_HERE)!r})   # exactly cogpr-ingest.py:89
            from lib.confidence_tier import classify_tier_value, refusal_message
            assert classify_tier_value("measured") == "lawful"
            assert classify_tier_value("exact") == "class_bleed"
            assert classify_tier_value("observed") == "non_tier_marker"
            assert classify_tier_value("high") == "off_enum"
            assert classify_tier_value(["x"]) == "off_enum"
            print("OK")
        """)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, env=env,
                              cwd=str(_HERE))
        self.assertEqual(proc.returncode, 0,
                         f"cogpr-ingest's import form broke:\n{proc.stderr}")
        self.assertIn("OK", proc.stdout)

    def test_writeback_import_form_resolves_the_engine(self):
        code = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(_HERE)!r})
            sys.path.insert(0, {str(_LIB)!r})    # exactly queue-lifecycle-writeback.py:163-164
            from confidence_tier import classify_tier_value
            import confidence_tier, enum_vocabulary_guard
            assert confidence_tier.enum_vocabulary_guard is enum_vocabulary_guard
            assert classify_tier_value("measured") == "lawful"
            print("OK")
        """)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, env=env,
                              cwd=str(_HERE))
        self.assertEqual(proc.returncode, 0,
                         f"the writeback import form broke:\n{proc.stderr}")
        self.assertIn("OK", proc.stdout)


# ---------------------------------------------------------------------------
# ARM C — the revert-control
# ---------------------------------------------------------------------------
class TestRevertControl(unittest.TestCase):
    """Prove the ARM-B pin has teeth.

    The shared-engine consumption is reverted IN MEMORY ONLY — a behaviourally
    identical LOCAL COPY of the engine is monkeypatched in, exactly what a
    future re-inline would produce. The file on disk is never touched.

    PREDICTED: every behavioural probe stays green (the copy is faithful) and
    ONLY the identity pins go false. That asymmetry is the whole point — it is
    what a resemblance-based test cannot see.
    """

    def setUp(self):
        self._real = confidence_tier.enum_vocabulary_guard
        # a SECOND module object from the SAME source file — a faithful copy
        self._copy = _load_under("enum_vocabulary_guard_local_copy_tic775",
                                 _LIB / "enum_vocabulary_guard.py")

    def tearDown(self):
        confidence_tier.enum_vocabulary_guard = self._real

    def test_the_local_copy_is_behaviourally_identical(self):
        """The control is only meaningful if the copy really is faithful."""
        for pid, value, _kind, _r in _PROBES:
            with self.subTest(probe=pid):
                self.assertEqual(
                    self._real.classify(value, confidence_tier.TIER_ENUM,
                                        empty_string_is_absence=False),
                    self._copy.classify(value, confidence_tier.TIER_ENUM,
                                        empty_string_is_absence=False))

    def test_the_identity_pin_goes_false_under_the_revert(self):
        confidence_tier.enum_vocabulary_guard = self._copy
        self.assertIsNot(confidence_tier.enum_vocabulary_guard,
                         enum_vocabulary_guard,
                         "PREDICTED: the module-object pin fails")
        self.assertIsNot(confidence_tier.enum_vocabulary_guard.classify,
                         enum_vocabulary_guard.classify,
                         "PREDICTED: the callable-identity pin fails")

    def test_behaviour_survives_the_revert_only_identity_discriminates(self):
        """The load-bearing asymmetry, measured member-for-member."""
        confidence_tier.enum_vocabulary_guard = self._copy
        for pid, value, expected_kind, frozen_repr in _PROBES:
            with self.subTest(probe=pid):
                self.assertEqual(confidence_tier.classify_tier_value(value),
                                 expected_kind,
                                 "behaviour must NOT discriminate — a faithful "
                                 "copy classifies identically")
                self.assertEqual(confidence_tier.refusal_message(value, "off_enum"),
                                 _frozen_refusal(frozen_repr, "off_enum"))

    def test_the_pin_returns_after_the_control(self):
        confidence_tier.enum_vocabulary_guard = self._copy
        self.assertIsNot(confidence_tier.enum_vocabulary_guard,
                         enum_vocabulary_guard)
        confidence_tier.enum_vocabulary_guard = self._real
        self.assertIs(confidence_tier.enum_vocabulary_guard,
                      enum_vocabulary_guard,
                      "the restored state must be byte-identical to the real one")
        self.assertEqual(confidence_tier.classify_tier_value("measured"), "lawful")

    def test_the_file_on_disk_was_never_touched_by_this_control(self):
        src = (_LIB / "confidence_tier.py").read_text(encoding="utf-8")
        self.assertIn("import enum_vocabulary_guard", src)
        self.assertIn("enum_vocabulary_guard.classify(", src)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
