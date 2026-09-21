#!/usr/bin/env python3
"""Tests for the confidence_tier VOCABULARY GUARD at cpr-extract's birth boundary
(row `bk-cpr-extract-tier-guard-typed-refusal-t823`, RULED /review 823 round 2
Q2 — Architect-ratified, recommended option verbatim: "One build increment:
guard cpr-extract"; the cpr-stepper's finding A2-822).

THE DEFECT UNDER CURE
---------------------
/review 708 made the confidence_tier vocabulary WRITE-BOUNDARY PHYSICS: the
value carries a ratified-enum member or is ABSENT, and "the vocabulary must not
depend on producer restraint" (A6-707). That guard landed at TWO writers —
cogpr-ingest.py (birth) and queue-lifecycle-writeback.py (verdict writeback).

cpr-extract.py is the OTHER BIRTH WRITER and carried no reference to the
contract at all: no enum check, no refusal, a declared tier copied straight onto
the queue row. A2-822 located it BY MEMBER — the unguarded writer is the one
that minted the off-enum value on queue row 3,276.

THE CONTRACT UNDER TEST (each tooth gets a fixture arm)
-------------------------------------------------------
  1. a lawful declared tier passes through UNTOUCHED (no marker, no notice)
  2. the ruling-3 admitted `measured` family passes (contract DATA, not inlined)
  3. an ABSENT declaration stays absent and is NEVER refused — `""` is not an
     absence form for this family (empty_string_is_absence=False), so a
     classify-everything guard would refuse every born that declares no tier
  4. the tier2/tier3 "tentative" default still fires when nothing is declared
  5. a non_tier_marker is stripped to ABSENT + typed marker + stderr notice
  6. a confidence_class value is named `class_bleed` (ruling 1's seam)
  7. a novel coinage is named `off_enum`
  8. THE LESSON IS NEVER DROPPED — a refusal marks the row, it does not reject
     it (a row-level reject at a background birth surface would be its own
     coverage drop; guard 10's shape)
  9. a REFUSED declaration is NOT laundered into the lawful-looking "tentative"
     default on the tier2/tier3 path (decode-or-refuse)
 10. a NON-STRING declaration is refused without raising — the isinstance guard
     in lib/confidence_tier is load-bearing (an unhashable value would raise
     TypeError on `in`)
 11. the prose-fallback mint site carries no tier and no refusal — prose can
     declare nothing, so there is nothing to classify (a scope statement)

FIXTURE KEY SETS ARE DRAWN FROM A REAL BORN, never from memory of the shape:
audit-logs/governance/borns-tic820-moving-a-reader-onto-a-new-population-owes-a-row-shape-read-against-the-fields-it-joins-on.md
— whose own lesson is that a cure can be "green on fixtures that happen to
carry the right keys, and dead on the real population". Its candidate block
carries: id / status / source / lesson_type / confidence_tier /
apophatic_exclusions / relations / deferred_facets / cost_of_inaction /
cost_of_action / recommended_scopes / lesson. All three borns on the tic-82x
frontier declare `confidence_tier: tentative` in a Tier-1 block — the exact
path that was unguarded.

SCOPE FENCE (verbatim from the ruling): It does NOT repair existing off-enum rows.
Fixtures are root-pinned to a temp zone (Self-Locating Artifact Test Isolation)
and every arm runs dry_run=True, so no arm can touch the real queue.

Run:  python3 -m unittest test_cpr_extract_tier_guard_tic824
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
    spec = importlib.util.spec_from_file_location("cpr_extract_tier_under_test",
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


def _born_block(cpr_id, tier_lines=""):
    """A Tier-1 block carrying the REAL born frontier's key set.

    Key order and key set mirror
    borns-tic820-moving-a-reader-onto-a-new-population-...md verbatim in shape;
    only the values are fixture values. `tier_lines` carries the
    confidence_tier declaration under test (or nothing, for the absent arm).
    """
    return (
        "<!-- --agnostic-candidate\n"
        f"id: {cpr_id}\n"
        "status: pending\n"
        "source: audit-logs/governance/borns-tic824-fixture.md\n"
        "lesson_type: refinement_ray\n"
        f"{tier_lines}"
        "apophatic_exclusions:\n"
        "  - NOT a claim about any existing off-enum row\n"
        "relations:\n"
        "  - sibling:contracts/confidence-tier-enum-v1.json\n"
        "deferred_facets:\n"
        "  - the live population is untouched by this fixture\n"
        "cost_of_inaction: an unguarded birth writer mints an off-enum tier silently\n"
        "cost_of_action: one classify call at the write boundary\n"
        "recommended_scopes:\n"
        "  - cgg-runtime/scripts/cpr-extract.py\n"
        "lesson: a durable lesson worth a queue row\n"
        "-->\n"
    )


def _tier2_block(cpr_id, tier_lines=""):
    """A Tier-2 block: status pending + title + evidence, and NO source.

    _classify_tier checks tier1 (lesson AND source) FIRST, so omitting `source`
    is what routes this block to the title+evidence tier.
    """
    return (
        "<!-- --agnostic-candidate\n"
        f"id: {cpr_id}\n"
        "status: pending\n"
        "title: a title-and-evidence candidate\n"
        "evidence: the measured thing that made it worth minting\n"
        f"{tier_lines}"
        "-->\n"
    )


class TierGuardAtExtractBirthTest(unittest.TestCase):
    """Each arm builds its own temp zone; nothing touches the real queue."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="cpr-extract-tier-guard-")
        self.zone = Path(self._td.name)
        _write(self.zone / ".ticzone", json.dumps({"name": "fixture-zone"}))
        _write(
            self.zone / "audit-logs" / "tics" / "fixture.jsonl",
            json.dumps({"type": "tic", "domain_counter_after": 824}) + "\n",
        )
        self.addCleanup(self._td.cleanup)

    def _extract(self, plan_file=None):
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

    # -- Arm 1: lawful declared value passes untouched ------------------------
    def test_lawful_declared_tier1_passes_untouched(self):
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _born_block(
                   "cpr_tier_lawful", "confidence_tier: reinforced\n"))
        entries, _, err = self._extract()
        row = self._one(entries, "cpr_tier_lawful")
        self.assertEqual(row["confidence_tier"], "reinforced")
        self.assertNotIn("tier_refusal", row)
        self.assertNotIn("TIER-REFUSAL", err)

    # -- Arm 2: the ruling-3 admitted measured family -------------------------
    def test_admitted_measured_family_passes(self):
        for value in ("measured", "measured_single_locus"):
            with self.subTest(value=value):
                self.setUp()
                _write(self.zone / "CLAUDE.md",
                       "# doctrine\n" + _born_block(
                           f"cpr_tier_{value}", f"confidence_tier: {value}\n"))
                entries, _, err = self._extract()
                row = self._one(entries, f"cpr_tier_{value}")
                self.assertEqual(row["confidence_tier"], value)
                self.assertNotIn("tier_refusal", row)
                self.assertNotIn("TIER-REFUSAL", err)

    # -- Arm 3: THE REGRESSION GUARD — absent is never refused ----------------
    def test_absent_declaration_stays_absent_on_tier1(self):
        """`""` is OFF_ENUM for this family (empty_string_is_absence=False).

        A guard that classified the UNSET field would mint a refusal on every
        born that declares no tier. Tier 1 does not impose a default, so the
        lawful outcome is: no confidence_tier key, no marker, no notice.
        """
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _born_block("cpr_tier_absent"))
        entries, _, err = self._extract()
        row = self._one(entries, "cpr_tier_absent")
        self.assertNotIn("confidence_tier", row)
        self.assertNotIn("tier_refusal", row)
        self.assertNotIn("TIER-REFUSAL", err)

    # -- Arm 4: the tier2 default still fires when nothing is declared --------
    def test_tier2_absent_declaration_keeps_tentative_default(self):
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _tier2_block("cpr_tier2_default"))
        entries, _, err = self._extract()
        row = self._one(entries, "cpr_tier2_default")
        self.assertEqual(row["tier"], "tier2")
        self.assertEqual(row["confidence_tier"], "tentative")
        self.assertNotIn("tier_refusal", row)
        self.assertNotIn("TIER-REFUSAL", err)

    # -- Arm 5: non_tier_marker stripped to absent + typed marker -------------
    def test_non_tier_marker_stripped_to_absent_with_typed_marker(self):
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _born_block(
                   "cpr_tier_observed", "confidence_tier: observed\n"))
        entries, _, err = self._extract()
        row = self._one(entries, "cpr_tier_observed")
        self.assertNotIn("confidence_tier", row)
        self.assertEqual(row["tier_refusal"]["value"], "observed")
        self.assertEqual(row["tier_refusal"]["reason"], "non_tier_marker")
        self.assertEqual(row["tier_refusal"]["ruling"], "review-708")
        self.assertIn("TIER-REFUSAL", err)
        self.assertIn("cpr_tier_observed", err)

    # -- Arm 6: class bleed is NAMED, not lumped into off_enum ----------------
    def test_class_bleed_stripped_and_named(self):
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _born_block(
                   "cpr_tier_bleed", "confidence_tier: exact\n"))
        entries, _, err = self._extract()
        row = self._one(entries, "cpr_tier_bleed")
        self.assertNotIn("confidence_tier", row)
        self.assertEqual(row["tier_refusal"]["reason"], "class_bleed")
        self.assertIn("TIER-REFUSAL", err)

    # -- Arm 7: novel coinage -------------------------------------------------
    def test_novel_coinage_stripped_as_off_enum(self):
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _born_block(
                   "cpr_tier_coinage", "confidence_tier: extremely_sure\n"))
        entries, _, err = self._extract()
        row = self._one(entries, "cpr_tier_coinage")
        self.assertNotIn("confidence_tier", row)
        self.assertEqual(row["tier_refusal"]["reason"], "off_enum")
        self.assertIn("TIER-REFUSAL", err)

    # -- Arm 8: the lesson is never dropped -----------------------------------
    def test_lesson_never_dropped_by_tier_refusal(self):
        """A refusal MARKS the row; it does not reject it."""
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _born_block(
                   "cpr_tier_lesson_survives", "confidence_tier: high\n"))
        entries, counters, _ = self._extract()
        row = self._one(entries, "cpr_tier_lesson_survives")
        self.assertEqual(row["lesson"], "a durable lesson worth a queue row")
        self.assertEqual(row["status"], "extracted")
        self.assertEqual(counters["blocks_extracted"], 1)
        self.assertEqual(row["tier_refusal"]["value"], "high")

    # -- Arm 9: a refusal is NOT laundered into the default -------------------
    def test_tier2_refused_declaration_is_not_laundered_to_tentative(self):
        """decode-or-refuse: a refused declaration is not "nothing declared".

        The tier2/tier3 path resolves `declared or "tentative"`. If the refusal
        merely blanked the value, the row would silently carry the lawful-
        looking "tentative" — asserting a tier the born never lawfully declared,
        which is laundering malformed input into well-formed WRONG data.
        """
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _tier2_block(
                   "cpr_tier2_refused", "confidence_tier: high\n"))
        entries, _, err = self._extract()
        row = self._one(entries, "cpr_tier2_refused")
        self.assertEqual(row["tier"], "tier2")
        self.assertNotIn("confidence_tier", row)
        self.assertEqual(row["tier_refusal"]["value"], "high")
        self.assertEqual(row["tier_refusal"]["reason"], "off_enum")
        self.assertIn("TIER-REFUSAL", err)

    # -- Arm 10: non-string declaration, the isinstance guard -----------------
    def test_non_string_declaration_refused_without_crash(self):
        """A YAML list value reaches the guard as a list (the block parser's
        list branch). The base engine returns OFF_ENUM for every non-string
        WITHOUT hashing it, and the four-kind refinement re-asserts isinstance
        before touching either refused_as_tier set — an unhashable value would
        otherwise raise TypeError on `in`."""
        _write(self.zone / "CLAUDE.md",
               "# doctrine\n" + _born_block(
                   "cpr_tier_list",
                   "confidence_tier:\n  - reinforced\n"))
        entries, _, err = self._extract()
        row = self._one(entries, "cpr_tier_list")
        self.assertNotIn("confidence_tier", row)
        self.assertEqual(row["tier_refusal"]["value"], ["reinforced"])
        self.assertEqual(row["tier_refusal"]["reason"], "off_enum")
        self.assertIn("TIER-REFUSAL", err)

    # -- Arm 11: the prose mint site declares nothing -------------------------
    def test_prose_fallback_mints_no_tier_and_no_refusal(self):
        """SCOPE STATEMENT, not an omission: the prose-fallback mint site
        carries no structured fields, so no tier can be declared and there is
        nothing to classify. It mints neither a tier nor a refusal."""
        plan = _write(self.zone / "plan.md",
                      "## CogPR candidate: `cpr_prose_tier_824`\n"
                      "**status:** pending\n"
                      "the prose body that becomes the lesson\n")
        entries, _, err = self._extract(plan_file=str(plan))
        row = self._one(entries, "cpr_prose_tier_824")
        self.assertEqual(row["extracted_by"], "cpr-extract-prose-fallback")
        self.assertNotIn("confidence_tier", row)
        self.assertNotIn("tier_refusal", row)
        self.assertNotIn("TIER-REFUSAL", err)


if __name__ == "__main__":
    unittest.main()
