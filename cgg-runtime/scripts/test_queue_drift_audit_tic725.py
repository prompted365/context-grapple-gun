#!/usr/bin/env python3
"""test_queue_drift_audit_tic725.py — queue-drift-audit.py regression + census fixtures.

Two ratified /review 725 verdicts are covered here.

A. PER-PREDICATE LIVENESS (ledger `#can-it-eat-dataflow-liveness-predicate`,
   per-predicate-liveness refinement ray). The `overdue_active` predicate was
   DEAD: `TIC_FILE` pointed at `audit-logs/tics/current.json`, a path that has
   never existed, so `load_current_tic()` returned None, `age_tics` stayed None,
   and the guard could never fire — while its loud sibling
   `terminal_with_duplicates` supplied the instrument's entire evidence-of-life.
   The repair itself landed at /review 723 (commit a2bb88b: TIC_FILE ->
   TIC_LOG_DIR, resolving `domain_counter_after` from the canonical tic log per
   Temporal Scope Discipline). It shipped WITHOUT a test. These fixtures are the
   missing RED->GREEN proof, retained as a regression fence: the dead shape is
   reproduced explicitly (`test_dead_shape_*`) so a future regression to a
   non-existent tic source fails loudly instead of silently re-killing the
   predicate.

B. CENSUS RATE AT FLAG ALTITUDE (ledger
   `#breach-flag-at-saturation-is-a-census-rate-rides-at-flag-altitude`).
   `terminal_with_duplicates` fires on EVERY run by construction — entailed by
   the federation's own mandated copy-forward writeback discipline, growing
   monotonically 280 -> 803 across the report history. A flag at ~100% base rate
   is a census wearing the word BREACH. The ratified cure keeps the flag and
   raises the RATE to the flag's altitude, with a severity word tracking the
   rate. These fixtures pin all five severity arms, backward compatibility of
   `breaches` + exit codes, and — per the t724 lane-A placement scar — assert
   the new keys land at TOP LEVEL of the ACTUALLY-WRITTEN report file, not one
   level down in a detail object.

Test isolation follows CGG `Self-Locating Artifact Test Isolation`: the module
resolves FEDERATION_ROOT from `__file__`, so every mutating fixture repins
QUEUE_FILE / OUT_DIR / TIC_LOG_DIR into a tmpdir. Only the two read-only
real-zone assertions touch the live federation, and they write nothing.
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "queue_drift_audit", _HERE / "queue-drift-audit.py"
)
qda = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(qda)

# The tic source retired at /review 723. Named here so the regression fence can
# assert it is still absent — the whole reason the predicate was dead.
RETIRED_TIC_SOURCE = qda.FEDERATION_ROOT / "audit-logs" / "tics" / "current.json"


@contextmanager
def pinned_zone(queue_rows=None, tic_events=None, prior_reports=None):
    """Repin the module's self-located surfaces into a throwaway zone."""
    saved = (qda.QUEUE_FILE, qda.OUT_DIR, qda.TIC_LOG_DIR)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        queue = root / "queue.jsonl"
        out = root / "reports"
        tics = root / "tics"
        out.mkdir()
        tics.mkdir()

        queue.write_text(
            "".join(json.dumps(r) + "\n" for r in (queue_rows or [])),
            encoding="utf-8",
        )
        if tic_events:
            (tics / "2026-08-21.jsonl").write_text(
                "".join(json.dumps(e) + "\n" for e in tic_events), encoding="utf-8"
            )
        for name, body in (prior_reports or {}).items():
            (out / name).write_text(json.dumps(body, indent=2), encoding="utf-8")

        qda.QUEUE_FILE, qda.OUT_DIR, qda.TIC_LOG_DIR = queue, out, tics
        try:
            yield root
        finally:
            qda.QUEUE_FILE, qda.OUT_DIR, qda.TIC_LOG_DIR = saved


def row(rid, status, birth_tic=None, **extra):
    d = {"id": rid, "status": status}
    if birth_tic is not None:
        d["birth_tic"] = birth_tic
    d.update(extra)
    return d


def run_main(argv):
    """Drive main() through its REAL writer path; return the exit code."""
    saved_argv = sys.argv
    sys.argv = ["queue-drift-audit.py"] + list(argv)
    try:
        qda.main()
    except SystemExit as exc:
        return exc.code
    finally:
        sys.argv = saved_argv
    raise AssertionError("main() returned without sys.exit")


# ---------------------------------------------------------------------------
# A. Per-predicate liveness: the overdue_active repair (RED -> GREEN)
# ---------------------------------------------------------------------------
class DeadPredicateRepairRegression(unittest.TestCase):
    def test_dead_shape_retired_tic_source_path_does_not_exist(self):
        """RED evidence: the pre-723 source is a path that never existed."""
        self.assertFalse(
            RETIRED_TIC_SOURCE.exists(),
            f"{RETIRED_TIC_SOURCE} exists — the tic-723 finding's premise would "
            "be void and this regression fence must be re-derived.",
        )
        self.assertFalse(
            hasattr(qda, "TIC_FILE"),
            "TIC_FILE was retired at /review 723; its return would re-kill "
            "overdue_active.",
        )
        self.assertTrue(hasattr(qda, "TIC_LOG_DIR"))

    def test_dead_shape_unresolvable_tic_source_returns_none(self):
        """RED reproduction: with no tic log, the loader yields None again."""
        with pinned_zone(tic_events=None):
            self.assertIsNone(qda.load_current_tic())

    def test_dead_shape_overdue_active_cannot_fire_without_a_tic(self):
        """RED reproduction: an ancient active row stays invisible at tic=None.

        This is exactly the pre-723 behaviour — the guard is unreachable, not
        merely quiet, because age_tics never becomes an int.
        """
        with pinned_zone(queue_rows=[row("cpr_ancient", "pending", birth_tic=1)]):
            report, code = qda.audit(current_tic=None)
        overdue = [f for f in report["findings"] if f["breach_class"] == "overdue_active"]
        self.assertEqual(overdue, [])
        self.assertIsNone(report["tic_at_audit"])

    def test_green_load_current_tic_returns_the_real_federation_tic(self):
        """GREEN: read-only against the live zone; writes nothing."""
        tic = qda.load_current_tic()
        self.assertIsInstance(tic, int)
        self.assertNotIsInstance(tic, bool)

        # Independently re-derive from the canonical tic log rather than
        # trusting the loader we are testing.
        expected = None
        for path in reversed(sorted(qda.TIC_LOG_DIR.glob("*.jsonl"))):
            for line in reversed(path.read_text(encoding="utf-8").splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                val = event.get("domain_counter_after")
                if isinstance(val, int):
                    expected = val
                    break
            if expected is not None:
                break
        self.assertIsNotNone(expected, "canonical tic log carried no counter")
        self.assertEqual(tic, expected)

    def test_green_loader_prefers_domain_counter_after_over_string_tic(self):
        """The real event schema puts an ISO timestamp in `tic`; ignore it."""
        with pinned_zone(
            tic_events=[{"type": "tic", "tic": "2026-08-21T22:54:30Z",
                         "domain_counter_after": 725}]
        ):
            self.assertEqual(qda.load_current_tic(), 725)

    def test_green_overdue_active_fires_on_a_synthetic_overdue_row(self):
        with pinned_zone(
            queue_rows=[row("cpr_stale", "pending", birth_tic=700)],
            tic_events=[{"domain_counter_after": 725}],
        ):
            report, code = qda.audit()

        overdue = [f for f in report["findings"] if f["breach_class"] == "overdue_active"]
        self.assertEqual(len(overdue), 1, "the repaired predicate must now fire")
        self.assertEqual(overdue[0]["id"], "cpr_stale")
        self.assertEqual(overdue[0]["age_tics"], 25)
        self.assertEqual(report["tic_at_audit"], 725)
        self.assertIn("overdue_active:1", report["breaches"])
        self.assertEqual(code, 1)

    def test_green_overdue_active_stays_silent_on_a_fresh_row(self):
        with pinned_zone(
            queue_rows=[row("cpr_fresh", "pending", birth_tic=720)],
            tic_events=[{"domain_counter_after": 725}],
        ):
            report, code = qda.audit()

        overdue = [f for f in report["findings"] if f["breach_class"] == "overdue_active"]
        self.assertEqual(overdue, [], "a 5-tic-old row is not overdue at threshold 20")
        self.assertEqual(report["tic_at_audit"], 725)
        self.assertTrue(report["healthy"])
        self.assertEqual(code, 0)

    def test_green_threshold_boundary_is_inclusive(self):
        with pinned_zone(
            queue_rows=[row("cpr_edge", "pending", birth_tic=705)],
            tic_events=[{"domain_counter_after": 725}],
        ):
            report, _ = qda.audit()
        self.assertIn("overdue_active:1", report["breaches"])


# ---------------------------------------------------------------------------
# B. Census rate at flag altitude
# ---------------------------------------------------------------------------
CENSUS_TOP_LEVEL_KEYS = (
    "terminal_with_duplicates_count",
    "terminal_with_duplicates_delta",
    "terminal_with_duplicates_rate_per_tic",
    "terminal_with_duplicates_severity",
    "census_baseline",
    "breach_classification",
)

# Two rows for one id, latest terminal => one terminal_with_duplicates finding.
DUP_PAIR = [row("cpr_a", "extracted", 700), row("cpr_a", "promoted", 700)]


def dup_rows(n):
    out = []
    for i in range(n):
        out.append(row(f"cpr_{i}", "extracted", 700))
        out.append(row(f"cpr_{i}", "promoted", 700))
    return out


def legacy_report(count, tic=None):
    """A pre-725 report: no top-level count key, only the breaches strings."""
    return {
        "tic_at_audit": tic,
        "timestamp_utc": "2026-08-01T00:00:00+00:00",
        "breaches": [f"terminal_with_duplicates:{count}"],
        "healthy": False,
    }


class CensusRateAtFlagAltitude(unittest.TestCase):
    def test_placement_new_fields_are_top_level_in_the_written_report(self):
        """t724 lane-A scar: prove the writer did not drop or demote the keys.

        Drives main()'s real write path and re-reads the file from disk.
        """
        with pinned_zone(
            queue_rows=DUP_PAIR,
            tic_events=[{"domain_counter_after": 725}],
        ) as root:
            code = run_main([])
            written = sorted((root / "reports").glob("*.json"))
            self.assertEqual(len(written), 1, "exactly one report must be written")
            report = json.loads(written[0].read_text(encoding="utf-8"))

        self.assertEqual(code, 1)
        for key in CENSUS_TOP_LEVEL_KEYS:
            self.assertIn(
                key, report, f"{key} missing from the WRITTEN report's top level"
            )
        # And not demoted into a detail object — the failure mode the ledger
        # anchor names explicitly ("never one level down in a detail object").
        for container in ("duplicate_summary", "status_breakdown"):
            for key in CENSUS_TOP_LEVEL_KEYS:
                self.assertNotIn(key, report[container])
        self.assertEqual(report["terminal_with_duplicates_count"], 1)
        self.assertTrue(written[0].name.endswith("-tic-725.json"))

    def test_backward_compat_breaches_strings_and_exit_codes_unchanged(self):
        with pinned_zone(
            queue_rows=DUP_PAIR, tic_events=[{"domain_counter_after": 725}]
        ):
            breach_report, breach_code = qda.audit()
        self.assertEqual(breach_report["breaches"], ["terminal_with_duplicates:1"])
        self.assertFalse(breach_report["healthy"])
        self.assertEqual(breach_code, 1)

        with pinned_zone(
            queue_rows=[row("cpr_clean", "promoted", 700)],
            tic_events=[{"domain_counter_after": 725}],
        ):
            clean_report, clean_code = qda.audit()
        self.assertEqual(clean_report["breaches"], [])
        self.assertTrue(clean_report["healthy"])
        self.assertEqual(clean_code, 0)

    def test_entailed_class_stays_loud_and_is_labelled_census(self):
        """Never silently suppressed — visible AND labelled."""
        with pinned_zone(
            queue_rows=DUP_PAIR, tic_events=[{"domain_counter_after": 725}]
        ):
            report, code = qda.audit()

        self.assertIn("terminal_with_duplicates:1", report["breaches"])
        self.assertEqual(code, 1)
        meta = report["breach_classification"]["terminal_with_duplicates"]
        self.assertEqual(meta["kind"], "census")
        self.assertTrue(meta["entailed"])
        self.assertFalse(meta["discriminating"])
        self.assertIn("copy-forward", meta["rationale"])

    def test_overdue_active_is_classified_discriminating_not_census(self):
        with pinned_zone(
            queue_rows=[row("cpr_stale", "pending", birth_tic=700)],
            tic_events=[{"domain_counter_after": 725}],
        ):
            report, _ = qda.audit()
        meta = report["breach_classification"]["overdue_active"]
        self.assertEqual(meta["kind"], "discriminating")
        self.assertTrue(meta["discriminating"])

    def test_severity_no_baseline_when_no_prior_report_exists(self):
        with pinned_zone(
            queue_rows=DUP_PAIR, tic_events=[{"domain_counter_after": 725}]
        ):
            report, _ = qda.audit()
        self.assertEqual(report["terminal_with_duplicates_severity"], "no_baseline")
        self.assertIsNone(report["terminal_with_duplicates_delta"])
        self.assertIsNone(report["terminal_with_duplicates_rate_per_tic"])
        self.assertIsNone(report["census_baseline"])

    def test_severity_expected_census_for_in_band_growth(self):
        # 8 new ids over 20 tics = 0.4/tic, inside the 5.0/tic band.
        with pinned_zone(
            queue_rows=dup_rows(10),
            tic_events=[{"domain_counter_after": 725}],
            prior_reports={"2026-08-01T000000-tic-705.json": legacy_report(2, tic=705)},
        ):
            report, _ = qda.audit()
        self.assertEqual(report["terminal_with_duplicates_count"], 10)
        self.assertEqual(report["terminal_with_duplicates_delta"], 8)
        self.assertAlmostEqual(report["terminal_with_duplicates_rate_per_tic"], 0.4)
        self.assertEqual(report["terminal_with_duplicates_severity"], "expected_census")
        self.assertEqual(report["census_baseline"]["tic_delta"], 20)
        self.assertEqual(report["census_baseline"]["rate_band_per_tic"], 5.0)

    def test_severity_anomalous_jump_above_the_band(self):
        # 18 new ids over 1 tic = 18.0/tic, far above the 5.0/tic band.
        with pinned_zone(
            queue_rows=dup_rows(20),
            tic_events=[{"domain_counter_after": 725}],
            prior_reports={"2026-08-01T000000-tic-724.json": legacy_report(2, tic=724)},
        ):
            report, _ = qda.audit()
        self.assertEqual(report["terminal_with_duplicates_delta"], 18)
        self.assertAlmostEqual(report["terminal_with_duplicates_rate_per_tic"], 18.0)
        self.assertEqual(report["terminal_with_duplicates_severity"], "anomalous_jump")

    def test_severity_zero_growth_is_expected_census_without_a_tic_delta(self):
        with pinned_zone(
            queue_rows=dup_rows(3),
            tic_events=[{"domain_counter_after": 725}],
            prior_reports={"2026-08-01T000000.json": legacy_report(3, tic=None)},
        ):
            report, _ = qda.audit()
        self.assertEqual(report["terminal_with_duplicates_delta"], 0)
        self.assertEqual(report["terminal_with_duplicates_severity"], "expected_census")

    def test_severity_untimed_baseline_refuses_to_invent_a_rate(self):
        """The live tic-725 case: every prior report carries tic_at_audit=null.

        Growth is real but its RATE is not derivable, so the classifier says so
        rather than dividing by an assumed cadence.
        """
        with pinned_zone(
            queue_rows=dup_rows(9),
            tic_events=[{"domain_counter_after": 725}],
            prior_reports={"2026-08-01T000000.json": legacy_report(3, tic=None)},
        ):
            report, _ = qda.audit()
        self.assertEqual(report["terminal_with_duplicates_delta"], 6)
        self.assertIsNone(report["terminal_with_duplicates_rate_per_tic"])
        self.assertEqual(report["terminal_with_duplicates_severity"], "untimed_baseline")
        self.assertIsNone(report["census_baseline"]["tic_at_audit"])
        self.assertIsNone(report["census_baseline"]["tic_delta"])

    def test_severity_census_regression_when_the_count_falls(self):
        with pinned_zone(
            queue_rows=dup_rows(2),
            tic_events=[{"domain_counter_after": 725}],
            prior_reports={"2026-08-01T000000-tic-720.json": legacy_report(50, tic=720)},
        ):
            report, _ = qda.audit()
        self.assertEqual(report["terminal_with_duplicates_delta"], -48)
        self.assertEqual(
            report["terminal_with_duplicates_severity"], "census_regression"
        )

    def test_baseline_selection_is_the_newest_prior_report(self):
        with pinned_zone(
            queue_rows=dup_rows(10),
            tic_events=[{"domain_counter_after": 725}],
            prior_reports={
                "2026-07-01T000000-tic-600.json": legacy_report(1, tic=600),
                "2026-08-01T000000-tic-705.json": legacy_report(2, tic=705),
            },
        ):
            report, _ = qda.audit()
        self.assertEqual(report["census_baseline"]["report"],
                         "2026-08-01T000000-tic-705.json")
        self.assertEqual(report["census_baseline"]["terminal_with_duplicates_count"], 2)

    def test_breach_class_count_reads_both_schema_generations(self):
        self.assertEqual(qda.breach_class_count(legacy_report(803), "terminal_with_duplicates"), 803)
        self.assertEqual(
            qda.breach_class_count(
                {"terminal_with_duplicates_count": 815}, "terminal_with_duplicates"
            ),
            815,
        )
        # Findings fallback when neither key nor breach string is present.
        self.assertEqual(
            qda.breach_class_count(
                {"findings": [{"breach_class": "terminal_with_duplicates"}] * 4},
                "terminal_with_duplicates",
            ),
            4,
        )
        # Absent class reads as None (distinct from a genuine zero).
        self.assertIsNone(qda.breach_class_count({"breaches": []}, "terminal_with_duplicates"))
        self.assertIsNone(qda.breach_class_count(None, "terminal_with_duplicates"))

    def test_classify_census_rate_rejects_bool_baselines(self):
        """isinstance(True, int) is True in Python — guard the coercion."""
        severity, delta, rate = qda.classify_census_rate(5, True, 10)
        self.assertEqual(severity, "no_baseline")
        self.assertIsNone(delta)
        self.assertIsNone(rate)

    def test_corrupt_prior_report_is_skipped_not_fatal(self):
        with pinned_zone(
            queue_rows=dup_rows(4),
            tic_events=[{"domain_counter_after": 725}],
            prior_reports={"2026-08-01T000000-tic-700.json": legacy_report(2, tic=700)},
        ) as root:
            (root / "reports" / "2026-08-02T000000.json").write_text(
                "{not json", encoding="utf-8"
            )
            report, _ = qda.audit()
        # Falls back past the corrupt newest file to the readable one.
        self.assertEqual(report["census_baseline"]["report"],
                         "2026-08-01T000000-tic-700.json")
        self.assertEqual(report["terminal_with_duplicates_delta"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
