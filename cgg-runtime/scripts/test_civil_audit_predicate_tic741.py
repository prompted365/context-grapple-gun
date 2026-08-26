#!/usr/bin/env python3
"""test_civil_audit_predicate_tic741.py — civil-audit.py `writes_governance_state` fixtures.

The ruled increment: bk-civil-envelope-citation-and-falsification-gate-recurrence,
the REMAINING OPEN HALF — the false-POSITIVE axis of the `writes_governance_state`
predicate. Civil measured a 30% sampled FP rate at tic 690 and WITHHELD the
bypass classification for six consecutive passes (690..740) rather than emit
counts from a known-broken predicate. This file is the RED->GREEN proof for the
refinement, and the regression fence that keeps it honest.

FIXTURE CLASSES (each one is a script the OLD v0 predicate flags and the NEW v1
predicate does not, keyed to the FP class it answers):

  FP-CLASS-A  report/receipt lane      an auditor that READS queue.jsonl and
                                       writes its report under audit-logs/governance/
  FP-CLASS-B  telemetry / CPG plane    a materializer writing audit-logs/economy/
  FP-CLASS-C  doctrine/source surface  an in-place ledger.md inscription
  FP-CLASS-D  out-of-federation        a proposal written to ~/.claude/
  FP-CLASS-E  test / scratch target    a tempfile write
  FP-CLASS-F  local process state      a lockfile / hooks-seen marker

  MENTION-NOT-CALL                     a script whose ONLY contact with a
                                       capability surface or a writer CLI is a
                                       COMMENT. This is the arm that a first cut
                                       of the primitive got WRONG (it matched
                                       SUBPROCESS_WRITER_TOKENS anywhere in the
                                       file text, reproducing the exact v0
                                       defect on mandate-write.py and on
                                       civil-audit.py itself), so it is fenced
                                       here explicitly.

NO-FALSE-NEGATIVE ARMS (the falsification gate trips on ANY false negative, so
these are as load-bearing as the FP fixtures):

  - the three /review-710 formerly-false-negative scripts stay envelope-aware
    against the LIVE corpus (cogpr-ingest.py, cpr-extract.py, ladder-feedback-push.py)
  - a genuine capability writer with no mechanism is still asserted `bypass`
  - a capability write reached only through a function PARAMETER still resolves
    (parameter binding is what keeps real writers from silently clearing)

LABELING: fixture assertions are FIXTURE-GREEN. The three live-corpus arms are
labeled live-corpus and read the real tree WITHOUT writing to it. Neither is
promoted to the other by prose anywhere in this file.

Test isolation follows CGG `Self-Locating Artifact Test Isolation`: civil-audit
resolves its runtime root from `__file__`, so every fixture builds a throwaway
root (scripts/ + agents/) and passes it explicitly via `--root` / `build_report`.
Nothing here writes into the real zone.
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("civil_audit", _HERE / "civil-audit.py")
ca = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ca)


# ---------------------------------------------------------------------------
# fixture zone
# ---------------------------------------------------------------------------

class FixtureZone:
    """A throwaway cgg-runtime-shaped root: scripts/ + agents/."""

    def __init__(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "lib").mkdir()
        (self.root / "agents").mkdir()

    def add(self, name, body):
        p = self.root / "scripts" / name
        p.write_text(body, encoding="utf-8")
        return p

    def classify(self, name):
        p = self.root / "scripts" / name
        return ca.classify_script(p, str(p.relative_to(self.root)))

    def close(self):
        self._td.cleanup()


def zone_with(name, body):
    z = FixtureZone()
    z.add(name, body)
    return z


# ---------------------------------------------------------------------------
# FP-class fixtures: v0 flags, v1 must not
# ---------------------------------------------------------------------------

FP_FIXTURES = {
    # (FP class, expected v1 target-surface class, source body)
    "FP-CLASS-A": ("report_receipt_lane", '''
"""A read-only auditor over the CogPR queue."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
QUEUE_FILE = ROOT / "audit-logs" / "cprs" / "queue.jsonl"
OUT_DIR = ROOT / "audit-logs" / "governance" / "queue-drift-audit"
def main():
    rows = [json.loads(l) for l in QUEUE_FILE.read_text().splitlines() if l]
    out_file = OUT_DIR / "report.json"
    out_file.write_text(json.dumps({"rows": len(rows)}))
'''),
    "FP-CLASS-B": ("telemetry_cpg", '''
"""A CPG-class telemetry materializer."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
SIGNALS = ROOT / "audit-logs" / "signals"
OUT = ROOT / "audit-logs" / "economy" / "heartbeat.json"
def main():
    OUT.write_text(json.dumps({"seen": len(list(SIGNALS.glob("*.jsonl")))}))
'''),
    "FP-CLASS-C": ("doctrine_source_surface", '''
"""An in-place doctrine inscription (a /review-gated governance write)."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
QUEUE = ROOT / "audit-logs" / "cprs" / "queue.jsonl"
LEDGER = ROOT / "audit-logs" / "governance" / "constitution-ledger" / "ledger.md"
def main():
    _ = QUEUE.read_text()
    LEDGER.write_text(LEDGER.read_text() + "\\n<!-- stamped -->\\n")
'''),
    "FP-CLASS-D": ("out_of_federation", '''
"""A proposal writer landing outside the canonical zone."""
import os
from pathlib import Path
def main(signals_dir, output=None):
    output_path = output or os.path.expanduser("~/.claude/grapple-proposals/latest.md")
    _ = list(Path(signals_dir).glob("*.jsonl"))
    Path(output_path).write_text("proposals")
'''),
    "FP-CLASS-E": ("test_scratch", '''
"""A scratch/tempfile writer that reads the mailbox tree."""
import json, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
MAILBOXES = ROOT / "audit-logs" / "agent-mailboxes"
def main():
    scratch = tempfile.mkdtemp()
    Path(scratch).write_text(json.dumps({"n": len(list(MAILBOXES.iterdir()))}))
'''),
    "FP-CLASS-F": ("local_process_state", '''
"""A hook-seen marker writer that inspects the signal manifold."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
SIGNALS = ROOT / "audit-logs" / "signals" / "active-manifest.jsonl"
SEEN = ROOT / "audit-logs" / "hooks" / "cadence-seen.json"
def main():
    n = len(SIGNALS.read_text().splitlines())
    SEEN.write_text(json.dumps({"n": n}))
'''),
}

MENTION_ONLY = '''
"""A pure reader that only MENTIONS capability surfaces and writer CLIs.

# LOCKSTEP MIRRORS (no import, to avoid a circular import):
#   this mirrors cadence-ops.py pending_statuses.
#   inbox-envelope.py owns the mailbox write; trigger-router.py owns dispatch.
#   the queue lives at audit-logs/cprs/queue.jsonl.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "audit-logs" / "governance" / "mention-only-report.json"
def main():
    REPORT.write_text("{}")
'''

BYPASS_FIXTURE = '''
"""A real capability writer with NONE of the six ratified mechanisms."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
SIGNAL_FILE = ROOT / "audit-logs" / "signals" / "2026-08-26.jsonl"
def emit(record):
    with open(SIGNAL_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\\n")
'''

AWARE_FIXTURE = '''
"""A capability writer routed through the ratified dedup-at-write primitive."""
from pathlib import Path
from lib.atomic_append import dedup_signal_append
ROOT = Path(__file__).resolve().parents[3]
SIGNAL_FILE = ROOT / "audit-logs" / "signals" / "2026-08-26.jsonl"
def emit(record):
    dedup_signal_append(str(SIGNAL_FILE), record)
'''

PARAM_REACHED_FIXTURE = '''
"""A capability write reachable ONLY through a function parameter.

Without interprocedural parameter binding this resolves to `unresolved` and a
real writer silently clears — the worst false negative this audit can produce.
"""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
MAILBOX = ROOT / "audit-logs" / "agent-mailboxes" / "ent_mogul" / "inbound"
def _write(target, payload):
    with open(target, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload))
def deliver(payload):
    _write(MAILBOX / "envelope.json", payload)
'''


class TestFalsePositiveClasses(unittest.TestCase):
    """FIXTURE-GREEN. Each FP class: v0 flags it, v1 clears it with a cited cause."""

    def test_each_fp_class_flagged_by_v0(self):
        for fp_class, (_expected, body) in FP_FIXTURES.items():
            with self.subTest(fp_class=fp_class):
                z = zone_with("fixture.py", body)
                try:
                    row = z.classify("fixture.py")
                    self.assertTrue(
                        row["v0_legacy_flagged"],
                        f"{fp_class}: the reconstructed v0 predicate must flag this "
                        f"fixture, else it is not a false-positive fixture at all",
                    )
                finally:
                    z.close()

    def test_each_fp_class_cleared_by_v1(self):
        for fp_class, (expected_surface, body) in FP_FIXTURES.items():
            with self.subTest(fp_class=fp_class):
                z = zone_with("fixture.py", body)
                try:
                    row = z.classify("fixture.py")
                    self.assertEqual(row["writes_governance_state"], "no", f"{fp_class}")
                    self.assertEqual(row["classification"], "not_a_governance_writer")
                    self.assertIn(expected_surface, row["target_surface_classes"],
                                  f"{fp_class}: the cited cause must be the measured one")
                    self.assertIn(fp_class, row["fp_classes_answered"])
                finally:
                    z.close()

    def test_v1_still_sees_a_real_write_call_site_in_every_fp_fixture(self):
        """PREMISE FENCE. tic 690 attributed its FPs to 'read-only auditors'.

        The tic-741 probe falsified that: the three scripts tic 690 named all
        contain REAL write call sites. These fixtures reproduce that shape, so a
        future 'is there any write at all' predicate cannot pass this file by
        clearing them for the WRONG reason.
        """
        for fp_class, (_expected, body) in FP_FIXTURES.items():
            with self.subTest(fp_class=fp_class):
                z = zone_with("fixture.py", body)
                try:
                    row = z.classify("fixture.py")
                    self.assertGreater(
                        row["write_sites_total"], 0,
                        f"{fp_class}: fixture must contain a real write call site — "
                        f"it is cleared by TARGET CLASS, not by absence of a write",
                    )
                finally:
                    z.close()


class TestMentionIsNotAWrite(unittest.TestCase):
    """FIXTURE-GREEN. The defect a first cut of this primitive shipped."""

    def test_comment_mentions_do_not_make_a_governance_writer(self):
        z = zone_with("fixture.py", MENTION_ONLY)
        try:
            row = z.classify("fixture.py")
            self.assertTrue(row["v0_legacy_flagged"])
            self.assertEqual(row["writes_governance_state"], "no")
            self.assertEqual(row["subprocess_writer_call_sites"], [])
            self.assertTrue(
                row["subprocess_writer_tokens_mentioned_not_called"],
                "the mention/call-site gap must be RECORDED as a diagnostic, "
                "never silently dropped",
            )
        finally:
            z.close()

    def test_civil_audit_does_not_flag_itself(self):
        """Its own registry names all three writer CLIs; a mention arm self-flags."""
        row = ca.classify_script(_HERE / "civil-audit.py", "scripts/civil-audit.py")
        self.assertEqual(row["writes_governance_state"], "no")
        self.assertEqual(row["classification"], "not_a_governance_writer")


class TestNoFalseNegative(unittest.TestCase):
    """The gate trips on ANY false negative — these arms are load-bearing."""

    def test_capability_writer_without_mechanism_is_bypass(self):
        z = zone_with("fixture.py", BYPASS_FIXTURE)
        try:
            row = z.classify("fixture.py")
            self.assertEqual(row["writes_governance_state"], "yes")
            self.assertEqual(row["classification"], "bypass")
            self.assertTrue(row["all_six_mechanisms_absent"])
            self.assertEqual(row["capability_write_sites"][0]["surface_detail"],
                             "signal_manifold")
        finally:
            z.close()

    def test_capability_writer_with_ratified_mechanism_is_aware(self):
        z = zone_with("fixture.py", AWARE_FIXTURE)
        try:
            row = z.classify("fixture.py")
            self.assertEqual(row["writes_governance_state"], "yes")
            self.assertEqual(row["classification"], "envelope_aware_via:dedup_append")
        finally:
            z.close()

    def test_capability_write_reached_only_through_a_parameter_resolves(self):
        z = zone_with("fixture.py", PARAM_REACHED_FIXTURE)
        try:
            row = z.classify("fixture.py")
            self.assertEqual(row["writes_governance_state"], "yes",
                             "parameter binding is what keeps real writers from "
                             "silently clearing")
            self.assertEqual(row["capability_write_sites"][0]["surface_detail"], "mailbox")
        finally:
            z.close()


class TestEvidenceAttribution(unittest.TestCase):
    """The spec forbids aggregate-only reporting; the citation IS the audit trail."""

    def test_matched_target_is_the_candidate_that_classified(self):
        z = zone_with("fixture.py", BYPASS_FIXTURE)
        try:
            row = z.classify("fixture.py")
            site = row["capability_write_sites"][0]
            self.assertIsNotNone(site["matched_target"])
            self.assertIn("audit-logs/signals/", site["matched_target"])
            self.assertGreater(site["line"], 0)
            self.assertTrue(site["verb"])
        finally:
            z.close()

    def test_every_non_capability_site_names_the_fp_class_it_answers(self):
        for fp_class, (_expected, body) in FP_FIXTURES.items():
            with self.subTest(fp_class=fp_class):
                z = zone_with("fixture.py", body)
                try:
                    row = z.classify("fixture.py")
                    answered = {s["fp_class_answered"] for s in row["write_sites"]
                                if s["surface_class"] != "unresolved"}
                    self.assertIn(fp_class, answered)
                finally:
                    z.close()


class TestFalsificationGateMechanics(unittest.TestCase):
    """The gate must be able to FAIL. A gate that cannot trip is not a gate."""

    def _rows(self, **overrides):
        rows = []
        for name, label in ca.CONTROL_SET.items():
            expect = overrides.get(name, label["expect"])
            cls = {"not_a_governance_writer": "not_a_governance_writer",
                   "envelope_aware": "envelope_aware_via:dedup_append",
                   "bypass": "bypass",
                   "indeterminate": "indeterminate"}[expect]
            wgs = {"not_a_governance_writer": "no", "indeterminate": "indeterminate"}.get(
                expect, "yes")
            rows.append({"script": f"scripts/{name}", "class": "production",
                         "classification": cls, "writes_governance_state": wgs})
        return rows

    def test_all_labels_satisfied_is_not_falsified(self):
        g = ca.run_gate(self._rows())
        self.assertFalse(g["predicate_falsified"])
        self.assertEqual(g["false_positive_count"], 0)
        self.assertEqual(g["false_negative_count"], 0)

    def test_asserting_a_labeled_negative_as_a_writer_is_a_false_positive(self):
        g = ca.run_gate(self._rows(**{"queue-drift-audit.py": "bypass"}))
        self.assertEqual(g["false_positive_count"], 1)
        self.assertTrue(g["predicate_falsified"])
        self.assertEqual(g["false_positives_asserted"][0]["script"], "queue-drift-audit.py")

    def test_losing_a_labeled_envelope_aware_script_is_a_false_negative(self):
        g = ca.run_gate(self._rows(**{"cogpr-ingest.py": "not_a_governance_writer"}))
        self.assertEqual(g["false_negative_count"], 1)
        self.assertTrue(g["predicate_falsified"])

    def test_losing_a_labeled_bypass_is_a_false_negative(self):
        """A real bypass counted compliant is the failure this office exists for."""
        g = ca.run_gate(self._rows(**{"runtime-sync.py": "not_a_governance_writer"}))
        self.assertEqual(g["false_negative_count"], 1)
        self.assertTrue(g["predicate_falsified"])

    def test_declining_on_a_labeled_negative_is_reported_not_hidden(self):
        g = ca.run_gate(self._rows(**{"queue-drift-audit.py": "indeterminate"}))
        self.assertEqual(g["false_positive_count"], 0,
                         "declining to assert is not asserting")
        self.assertEqual(g["declined_count"], 1)
        self.assertGreater(g["false_positive_rate_strict_pct"],
                           g["false_positive_rate_pct"],
                           "the STRICT reading must be published and must be higher")
        self.assertEqual(
            g["declined_to_assert_on_labeled_negative"][0]["script"],
            "queue-drift-audit.py")

    def test_gate_text_is_the_spec_text(self):
        g = ca.run_gate(self._rows())
        self.assertIn("do not silently widen", g["gate_text"])
        self.assertEqual(g["threshold_pct"], 5.0)


class TestRatifiedOrGateUntouched(unittest.TestCase):
    """The six-mechanism OR-gate was ratified at /review 710. It stays as-is."""

    def test_all_six_mechanisms_are_present_in_the_registry(self):
        self.assertEqual(
            set(ca.SIX_MECHANISM_TOKENS),
            {"inbox_envelope", "dedup_append", "atomic_write_json",
             "envelope_type", "envelopes_yaml"},
        )
        self.assertIn("dedup_signal_append", ca.SIX_MECHANISM_TOKENS["dedup_append"])
        self.assertIn("dedup_queue_append", ca.SIX_MECHANISM_TOKENS["dedup_append"])
        self.assertIn("inbox-envelope.py", ca.SIX_MECHANISM_TOKENS["inbox_envelope"])

    def test_mechanism_six_is_the_provenance_field_set(self):
        self.assertEqual(ca.MECHANISM_6_MIN_FIELDS, 3)
        self.assertIn("envelope_id", ca.MECHANISM_6_FIELDS)

    def test_atomic_append_jsonl_is_not_a_ratified_mechanism(self):
        """The 'seventh mechanism' question is SURFACED, never silently widened."""
        flat = {t for toks in ca.SIX_MECHANISM_TOKENS.values() for t in toks}
        self.assertNotIn("atomic_append_jsonl", flat)
        self.assertNotIn("atomic-append.sh", flat)


class TestDeterminism(unittest.TestCase):
    """A governance instrument whose verdict depends on hash seed is not an instrument.

    Found by THIS file: a first cut sliced an unsorted candidate set, so
    PYTHONHASHSEED randomization made ladder-feedback-push.py resolve its
    `subprocess.run(cmd)` writer CLI on the full-corpus run and NOT on the
    single-script run. Same input, two verdicts. Fenced here.
    """

    LONG_CMD_FIXTURE = '''
"""Routes through the validated CLI with a long argv list."""
import subprocess, sys
from pathlib import Path
_HERE = Path(__file__).resolve().parent
def push(office, body_file, idem, tic):
    ie = Path(_HERE) / "inbox-envelope.py"
    cmd = [
        sys.executable, str(ie), "write",
        "--sender", "ent_homeskillet", "--recipient", office,
        "--type", "ladder.rehydration_feedback",
        "--subject", "Rehydration feedback",
        "--body-file", str(body_file),
        "--source-tic", str(tic),
        "--priority", "normal", "--delivery-mode", "session_scoped",
        "--idempotency-key", idem, "--dedupe-policy", "first_wins",
        "--source-event", "ladder.rehydration_feedback",
        "--producer", "ladder-feedback-push.py",
    ]
    return subprocess.run(cmd, capture_output=True, text=True)
'''

    def test_writer_cli_survives_a_long_argv_list(self):
        z = zone_with("fixture.py", self.LONG_CMD_FIXTURE)
        try:
            row = z.classify("fixture.py")
            self.assertEqual(row["writes_governance_state"], "yes")
            self.assertEqual(row["predicate_arm"],
                             "arm2_subprocess_to_validated_writer_cli")
            self.assertIn("inbox-envelope.py",
                          row["subprocess_writer_call_sites"][0]["writer_cli"])
        finally:
            z.close()

    def test_repeated_classification_is_stable(self):
        z = zone_with("fixture.py", self.LONG_CMD_FIXTURE)
        try:
            seen = {json.dumps(z.classify("fixture.py"), sort_keys=True, default=str)
                    for _ in range(5)}
            self.assertEqual(len(seen), 1, "classification must be reproducible")
        finally:
            z.close()

    def test_candidate_cap_is_sorted_and_path_first(self):
        capped = ca._cap({"zzz", "aaa", "x/one", "y/two"} | {f"n{i}" for i in range(40)})
        self.assertEqual(len(capped), ca._MAX_CANDIDATES)
        self.assertIn("x/one", capped, "path-shaped candidates must survive capping")
        self.assertIn("y/two", capped)


class TestLiveCorpusNoFalseNegative(unittest.TestCase):
    """LIVE-CORPUS (read-only). NOT fixture-green — these read the real tree."""

    REVIEW_710_CONTROL = ("cogpr-ingest.py", "cpr-extract.py", "ladder-feedback-push.py")

    def test_review_710_formerly_false_negative_scripts_stay_envelope_aware(self):
        for name in self.REVIEW_710_CONTROL:
            with self.subTest(script=name):
                p = _HERE / name
                if not p.exists():
                    self.skipTest(f"{name} absent from the live corpus")
                row = ca.classify_script(p, f"scripts/{name}")
                self.assertTrue(
                    str(row["classification"]).startswith("envelope_aware_via:"),
                    f"{name} was disposed compliant at /review 710; losing it here "
                    f"is a false negative and trips the falsification gate",
                )

    def test_tic_690_named_false_positives_are_not_asserted_as_writers(self):
        for name in ("queue-drift-audit.py", "ripple-assessor.py"):
            with self.subTest(script=name):
                p = _HERE / name
                if not p.exists():
                    self.skipTest(f"{name} absent from the live corpus")
                row = ca.classify_script(p, f"scripts/{name}")
                self.assertNotEqual(row["classification"], "bypass")
                self.assertEqual(row["writes_governance_state"], "no")


class TestReadOnlyDiscipline(unittest.TestCase):
    """The primitive is read-only over the corpus by contract."""

    def test_stdout_mode_writes_nothing(self):
        z = FixtureZone()
        try:
            z.add("fixture.py", BYPASS_FIXTURE)
            before = sorted(p.name for p in z.root.rglob("*"))
            rc = ca.main(["--root", str(z.root), "--stdout"])
            after = sorted(p.name for p in z.root.rglob("*"))
            self.assertEqual(rc, 0)
            self.assertEqual(before, after, "--stdout must create no artifact")
        finally:
            z.close()

    def test_report_lands_only_at_the_declared_out_path(self):
        z = FixtureZone()
        try:
            z.add("fixture.py", BYPASS_FIXTURE)
            out = z.root / "report.json"
            rc = ca.main(["--root", str(z.root), "--out", str(out)])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            payload = json.loads(out.read_text())
            self.assertEqual(payload["artifact"], "civil-audit")
            self.assertEqual(payload["declared_scan_scope"], ["scripts", "scripts/lib"])
            self.assertIn("measurement_scope_disclosure", payload["falsification_gate"])
        finally:
            z.close()

    def test_fail_on_falsified_exits_two(self):
        z = FixtureZone()
        try:
            z.add("fixture.py", BYPASS_FIXTURE)
            out = z.root / "report.json"
            # Every control-set script is absent from this fixture zone, so the
            # gate has nothing to measure and must NOT invent a falsification.
            rc = ca.main(["--root", str(z.root), "--out", str(out), "--fail-on-falsified"])
            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text())
            self.assertEqual(
                len(payload["falsification_gate"]["control_set_missing_from_scope"]),
                len(ca.CONTROL_SET),
                "an empty control set must be DECLARED missing, never scored as pass",
            )
        finally:
            z.close()


class TestScopeIsDeclared(unittest.TestCase):
    """Apophatic-aperture disclosure: the scan scope names its exclusions."""

    def test_report_declares_scope_and_exclusions(self):
        z = FixtureZone()
        try:
            z.add("fixture.py", BYPASS_FIXTURE)
            report = ca.build_report(z.root, None, False)
            self.assertEqual(report["declared_scan_scope"], ["scripts", "scripts/lib"])
            self.assertTrue(report["scope_exclusions_declared"])
            self.assertIn("RATIFIED /review 710", report["or_gate_status"])
        finally:
            z.close()

    def test_test_fixtures_are_excluded_and_counted_separately(self):
        z = FixtureZone()
        try:
            z.add("test_something.py", BYPASS_FIXTURE)
            report = ca.build_report(z.root, None, False)
            self.assertEqual(report["summary"]["excluded_test_fixtures"], 1)
            self.assertEqual(report["summary"]["production"], 0)
        finally:
            z.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
