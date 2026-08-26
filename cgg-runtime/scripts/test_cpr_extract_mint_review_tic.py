#!/usr/bin/env python3
"""Tests for the review_tic PROSPECTIVE MINT FENCE at cpr-extract's mint sites
(bk-cpr-extract-mint-review-tic-stamp, ratified /review 740 — the A1-733/A1-734
vocabulary-unification half, deferred from the /review 734 fence-side cure).

THE DEFECT UNDER CURE
---------------------
cpr-extract minted NO `review_tic`. cogpr-ingest and pattern-miner DID (the
A2-709 convention: review_tic = birth_tic + maturity). The two mint sites
therefore carried DISJOINT ENVELOPE VOCABULARIES (A1-733), which forced the
cpr-stepper's docket fence to DERIVE the value for the whole friction-born
cohort:

    effective_review_tic = review_tic OR (birth_tic + maturity_window_tics)
                           when review_tic is absent          (/review 734)

Measured at the live queue before this cure (tic 740): 482 cpr-extract-hook
mint rows, only 12 carrying review_tic — and all 12 are historical
(birth_tic ∈ {165, 166, 358, 467}, the tic-167 era update-queue-tic167.py
back-stamp), none produced by the current code path. 6/6 prose-fallback mint
rows carried none.

WHY IT WAS BLOCKED, AND WHAT UNBLOCKED IT
-----------------------------------------
The stamp was deliberately withheld while `review_tic` carried TWO writer
semantics corpus-wide (A1-738 HIGH, /review 738) — a PROSPECTIVE mint fence
AND a RETROSPECTIVE verdict stamp. Minting into a colliding field would have
imported the collision onto a second mint site. /review 739 dissolved it
FORWARD-ONLY: verdict-side stamps write the distinct single-writer field
`adjudicated_at_tic`, so `review_tic` is single-semantic at mint going forward.

THE CONTRACT UNDER TEST (each tooth gets a fixture arm)
-------------------------------------------------------
  1. friction-born block extraction mints review_tic = birth_tic + window
  2. a declared maturity_window_tics is respected by the mint (fence tracks the
     row's OWN window, not a hardcoded 3)
  3. construction_authoritative (window 0) mints review_tic == birth_tic
  4. a SOURCE-DECLARED review_tic passes through UNTOUCHED, never overwritten
  5. prose-fallback mint site carries the field too (both mint sites or
     neither — a half-landed mint recreates the disjoint-vocabulary defect)
  6. FENCE PARITY, the load-bearing arm: for status=extracted rows the minted
     value EQUALS the cpr-stepper's derivation branch, so the fence is
     unchanged in value and its A1-738 `status=extracted` scope restriction is
     untouched
  7. FORWARD-ONLY: extraction mutates no pre-existing queue row (no
     back-stamping — the 115 historically-divergent ids stay as they are)
  8. an unparseable declared review_tic falls back to the derived fence LOUDLY
     (authoring trap surfaced, not silently accepted)

Fixtures are root-pinned to a temp zone (Self-Locating Artifact Test
Isolation); extract_cprs takes an explicit project_dir so no arm can touch the
real zone.

Run:  python3 -m unittest test_cpr_extract_mint_review_tic
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "cpr-extract.py")


def _load_module():
    """Load the hyphenated script as a module (no package import path)."""
    spec = importlib.util.spec_from_file_location("cpr_extract_under_test",
                                                  _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cpr_extract = _load_module()


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _block(cpr_id, extra_lines=""):
    """A canonical Tier-1 --agnostic-candidate block."""
    return (
        "<!-- --agnostic-candidate\n"
        f"id: {cpr_id}\n"
        "status: pending\n"
        "lesson: a durable lesson worth a queue row\n"
        "source: fixture/source.md:1\n"
        f"{extra_lines}"
        "-->\n"
    )


class MintReviewTicTest(unittest.TestCase):
    """Each arm builds its own temp zone; nothing touches the real queue."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="cpr-mint-review-tic-")
        self.zone = Path(self._td.name)
        _write(self.zone / ".ticzone", json.dumps({"name": "fixture-zone"}))
        # Canonical tic authority: get_tic_count reads domain_counter_after
        # from the LATEST tic event (Temporal Scope Discipline).
        _write(
            self.zone / "audit-logs" / "tics" / "fixture.jsonl",
            json.dumps({"type": "tic", "domain_counter_after": 700}) + "\n",
        )
        self.addCleanup(self._td.cleanup)

    def _extract(self, plan_file=None):
        """Run extraction against the pinned fixture zone, capturing stderr."""
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            entries, counters = cpr_extract.extract_cprs(
                str(self.zone), dry_run=True, plan_file=plan_file,
            )
        return entries, counters, err.getvalue()

    def _one(self, entries, cpr_id):
        matches = [e for e in entries if e["id"] == cpr_id]
        self.assertEqual(len(matches), 1,
                         f"expected exactly one row for {cpr_id}, "
                         f"got {[e['id'] for e in entries]}")
        return matches[0]

    # -- Arm 1: the core mint ------------------------------------------------
    def test_friction_born_mints_review_tic_as_birth_plus_window(self):
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _block("cpr_mint_basic", "birth_tic: 500\n"))
        entries, _, _ = self._extract()
        row = self._one(entries, "cpr_mint_basic")
        self.assertEqual(row["birth_tic"], 500)
        self.assertEqual(row["maturity_window_tics"], 3,
                         "friction_born holds the standing window of 3")
        self.assertEqual(row["review_tic"], 503,
                         "review_tic MUST be birth_tic + maturity_window_tics")

    # -- Arm 2: the fence tracks the row's OWN declared window ---------------
    def test_declared_maturity_window_drives_the_mint(self):
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _block(
                   "cpr_mint_window",
                   "birth_tic: 610\nmaturity_window_tics: 8\n"))
        entries, _, _ = self._extract()
        row = self._one(entries, "cpr_mint_window")
        self.assertEqual(row["maturity_window_tics"], 8)
        self.assertEqual(row["review_tic"], 618,
                         "the mint must track the row's own window, not a "
                         "hardcoded 3")

    # -- Arm 3: construction_authoritative waives the temporal hold ----------
    def test_construction_authoritative_mints_review_tic_equal_to_birth(self):
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _block(
                   "cpr_mint_ca",
                   "birth_tic: 640\n"
                   "provenance_class: construction_authoritative\n"
                   "evidence: architect ratified in-tic at /review 640\n"))
        entries, _, _ = self._extract()
        row = self._one(entries, "cpr_mint_ca")
        self.assertEqual(row["provenance_class"], "construction_authoritative")
        self.assertEqual(row["maturity_window_tics"], 0,
                         "construction_authoritative waives the temporal hold")
        self.assertEqual(row["review_tic"], 640,
                         "a waived hold means the fence opens at birth")

    # -- Arm 4: declared-wins — a source review_tic is never overwritten -----
    def test_source_declared_review_tic_passes_through_untouched(self):
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _block(
                   "cpr_mint_declared",
                   "birth_tic: 500\nreview_tic: 777\n"))
        entries, _, _ = self._extract()
        row = self._one(entries, "cpr_mint_declared")
        self.assertEqual(row["review_tic"], 777,
                         "a source-declared review_tic is passed through, "
                         "NEVER overwritten by the derived fence (which would "
                         "have been 503)")

    # -- Arm 5: the paired mint site (both, or the defect returns) ----------
    def test_prose_fallback_mint_site_also_carries_review_tic(self):
        plan = _write(
            self.zone / "plans" / "active-plan.md",
            "# plan\n\n"
            "## CogPR candidate: `cpr_prose_mint_tic512`\n"
            "**status:** pending\n\n"
            "The prose-authored lesson body.\n",
        )
        entries, _, _ = self._extract(plan_file=str(plan))
        row = self._one(entries, "cpr_prose_mint_tic512")
        self.assertEqual(row["extracted_by"], "cpr-extract-prose-fallback")
        self.assertEqual(row["birth_tic"], 512,
                         "prose birth_tic is parsed from the _tic<N> suffix")
        self.assertEqual(row["maturity_window_tics"], 3)
        self.assertEqual(row["review_tic"], 515,
                         "the prose mint site must carry the fence too — a "
                         "half-landed mint recreates A1-733 disjoint vocabulary")

    # -- Arm 6: FENCE PARITY (load-bearing) ---------------------------------
    def test_minted_value_equals_stepper_derivation_for_extracted_rows(self):
        """The cpr-stepper fence is
            effective_review_tic = review_tic OR (birth+window) if absent.
        The mint must make those two branches produce the SAME value on
        status=extracted rows, or the cure moves the fence instead of
        unifying the vocabulary (A1-738 scope restriction stays untouched).
        """
        _write(
            self.zone / "CLAUDE.md",
            "# doctrine\n"
            + _block("cpr_parity_default", "birth_tic: 500\n")
            + _block("cpr_parity_window",
                     "birth_tic: 610\nmaturity_window_tics: 8\n"),
        )
        entries, _, _ = self._extract()
        extracted = [e for e in entries if e["status"] == "extracted"]
        self.assertTrue(extracted, "fixture must produce status=extracted rows")
        for row in extracted:
            derived = row["birth_tic"] + row["maturity_window_tics"]
            self.assertEqual(
                row["review_tic"], derived,
                f"{row['id']}: minted review_tic {row['review_tic']} must "
                f"equal the stepper's derivation {derived} — the explicit "
                f"branch and the derivation branch must agree BY CONSTRUCTION",
            )

    # -- Arm 7: FORWARD-ONLY — no back-stamping of existing rows ------------
    def test_extraction_does_not_mutate_any_pre_existing_queue_row(self):
        """The cure touches MINT TIME only. Historical rows — including the
        divergent-semantics cohort — are left byte-identical."""
        queue = self.zone / "audit-logs" / "cprs" / "queue.jsonl"
        historical = [
            # a legacy row with NO review_tic and NO window: must stay bare
            {"type": "cpr", "id": "cpr_legacy_bare", "status": "extracted",
             "dedup_hash": "aaaaaaaaaaaaaaaa", "birth_tic": 165,
             "lesson": "legacy", "source": "legacy.md:1"},
            # a divergent row: review_tic disagrees with birth+window
            {"type": "cpr", "id": "cpr_legacy_divergent", "status": "extracted",
             "dedup_hash": "bbbbbbbbbbbbbbbb", "birth_tic": 200,
             "maturity_window_tics": 3, "review_tic": 599,
             "lesson": "divergent", "source": "legacy.md:2"},
        ]
        _write(queue, "".join(json.dumps(r) + "\n" for r in historical))
        before = queue.read_bytes()

        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _block("cpr_new_row", "birth_tic: 700\n"))

        # dry_run=False so the write path actually runs against the fixture
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            entries, _ = cpr_extract.extract_cprs(str(self.zone),
                                                  dry_run=False)
        after_lines = queue.read_text(encoding="utf-8").splitlines()

        # the two historical lines are untouched, in place, byte-for-byte
        self.assertEqual(
            "\n".join(after_lines[:2]) + "\n",
            before.decode("utf-8"),
            "pre-existing queue rows MUST NOT be back-stamped or rewritten",
        )
        appended = [json.loads(l) for l in after_lines[2:]]
        self.assertEqual([r["id"] for r in appended], ["cpr_new_row"])
        self.assertEqual(appended[0]["review_tic"], 703,
                         "the NEW row carries the mint; the old ones do not")

    # -- Arm 8: unparseable declaration falls back LOUDLY -------------------
    def test_unparseable_declared_review_tic_falls_back_loudly(self):
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _block(
                   "cpr_mint_bad_decl",
                   "birth_tic: 500\nreview_tic: soon-ish\n"))
        entries, _, stderr = self._extract()
        row = self._one(entries, "cpr_mint_bad_decl")
        self.assertEqual(row["review_tic"], 503,
                         "an unparseable declaration falls back to the fence")
        self.assertIn("review_tic", stderr)
        self.assertIn("soon-ish", stderr,
                      "the authoring trap must be surfaced, not swallowed")


if __name__ == "__main__":
    unittest.main()
