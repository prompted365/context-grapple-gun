#!/usr/bin/env python3
"""test_enrichment_scanner_surface_anchor.py — surface#anchor scope resolution.

Fix-site: bk-enrichment-scanner-surface-anchor-target-resolution (filed HIGH
tic 691, struck tic 692). gather_target_absence treated '<surface>#<anchor>'
scope forms (cgg-ledger#..., constitution-ledger#...) as literal filesystem
paths — Path(project_dir)/'cgg-ledger#...' never exists — manufacturing a
FALSE 'target_absence_confirmed (file missing)' evidence row on every
ledger-scoped CogPR (found live: 3a7579a80e8e's docket claimed the
mandate-lifecycle-defects anchor 'file missing' while it sat at ledger.md:391).

The cure routes the form through the shared doctrine-surface owner
(lib/doctrine_surfaces.resolve_surface_anchor — COORDINATE, not duplicate:
the alias→ledger mapping extends the same module that closed the dehydration
reason at t335). Arms: one per surface alias (both real anchor conventions —
explicit <a id=> tags AND heading slugs), lesson-present, anchor-missing,
unresolvable-alias fallback, and literal-path arms proving the existing
behavior byte-preserved.
"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
_SPEC = importlib.util.spec_from_file_location(
    "cpr_enrichment_scanner", _HERE / "cpr-enrichment-scanner.py"
)
scanner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(scanner)

from lib.doctrine_surfaces import (  # noqa: E402
    anchor_present, ledger_alias_map, resolve_surface_anchor,
)

LESSON = "A merge must terminalize what it consumes at the merge site."


def _zone():
    zone = Path(tempfile.mkdtemp(prefix="scanner-anchor-"))
    # federation ledger — heading-slug anchor convention
    fed = zone / "audit-logs" / "governance" / "constitution-ledger"
    fed.mkdir(parents=True)
    (fed / "ledger.md").write_text(
        "## Index\n\n## Structural Transform Implies Closed Consumer Set Obligation\n\n"
        "Body of the federation entry. " + LESSON + "\n"
    )
    # domain ledger — explicit <a id=> anchor convention (the cgg-ledger form)
    dom = zone / "canonical_developer" / "context-grapple-gun" / "cgg-ledger"
    dom.mkdir(parents=True)
    (dom / "ledger.md").write_text(
        "## Mandate Lifecycle Defects\n"
        '<a id="mandate-lifecycle-defects"></a>\n\n'
        "Four structural defects... fifth ray pending.\n"
    )
    # literal-path surfaces
    docs = zone / "docs"
    docs.mkdir()
    (docs / "notes.md").write_text("notes. " + LESSON + "\n")
    return zone


def _cpr(scope):
    return {"lesson": LESSON, "recommended_scopes": [scope]}


def _evidence(zone, scope):
    return scanner.gather_target_absence(_cpr(scope), str(zone))


class SurfaceAnchorResolution(unittest.TestCase):
    def test_alias_map_discovers_both_ledgers(self):
        zone = _zone()
        m = ledger_alias_map(zone)
        self.assertIn("constitution-ledger", m)
        self.assertIn("cgg-ledger", m)
        self.assertTrue(m["cgg-ledger"].endswith("cgg-ledger/ledger.md"))

    def test_resolve_surface_anchor_forms(self):
        zone = _zone()
        ledger, anchor = resolve_surface_anchor("cgg-ledger#mandate-lifecycle-defects", zone)
        self.assertIsNotNone(ledger)
        self.assertEqual(anchor, "mandate-lifecycle-defects")
        # literal path with '/' is NOT an alias form
        self.assertEqual(resolve_surface_anchor("docs/notes.md#frag", zone), (None, None))
        # no '#' at all
        self.assertEqual(resolve_surface_anchor("docs/notes.md", zone), (None, None))

    def test_anchor_present_both_conventions(self):
        explicit = '## Heading\n<a id="mandate-lifecycle-defects"></a>\n'
        heading = "## Structural Transform Implies Closed Consumer Set Obligation\n"
        self.assertTrue(anchor_present(explicit, "mandate-lifecycle-defects"))
        self.assertTrue(anchor_present(
            heading, "structural-transform-implies-closed-consumer-set-obligation"))
        # compact-root truncated slug still resolves (prefix containment)
        self.assertTrue(anchor_present(
            heading, "structural-transform-implies-closed-consumer-set-obl"))
        self.assertFalse(anchor_present(heading, "completely-different-anchor"))

    def test_cgg_ledger_anchor_scope_is_not_file_missing(self):
        """THE observed defect: the anchor exists — absence must be truthful
        (lesson not yet inscribed), never '(file missing)'."""
        zone = _zone()
        ev = _evidence(zone, "cgg-ledger#mandate-lifecycle-defects")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["evidence_type"], "target_absence_confirmed")
        self.assertNotIn("file missing", ev[0]["detail"][0])
        self.assertNotIn("anchor missing", ev[0]["detail"][0])

    def test_constitution_ledger_scope_with_lesson_reads_already_present(self):
        zone = _zone()
        ev = _evidence(
            zone,
            "constitution-ledger#structural-transform-implies-closed-consumer-set-obligation",
        )
        self.assertEqual(ev[0]["evidence_type"], "target_already_present")

    def test_parenthetical_description_still_stripped_on_anchor_forms(self):
        zone = _zone()
        ev = _evidence(zone, "cgg-ledger#mandate-lifecycle-defects (the fifth ray home)")
        self.assertEqual(ev[0]["evidence_type"], "target_absence_confirmed")
        self.assertNotIn("file missing", ev[0]["detail"][0])

    def test_missing_anchor_reported_as_anchor_missing_not_file_missing(self):
        zone = _zone()
        ev = _evidence(zone, "cgg-ledger#no-such-anchor-here")
        self.assertEqual(ev[0]["evidence_type"], "target_absence_confirmed")
        self.assertIn("anchor missing", ev[0]["detail"][0])

    def test_unresolvable_alias_keeps_honest_file_missing_fallback(self):
        zone = _zone()
        ev = _evidence(zone, "nonexistent-ledger#some-anchor")
        self.assertEqual(ev[0]["evidence_type"], "target_absence_confirmed")
        self.assertIn("file missing", ev[0]["detail"][0])

    def test_literal_path_present_behavior_preserved(self):
        zone = _zone()
        ev = _evidence(zone, "docs/notes.md")
        self.assertEqual(ev[0]["evidence_type"], "target_already_present")

    def test_literal_path_missing_behavior_preserved(self):
        zone = _zone()
        ev = _evidence(zone, "docs/gone.md")
        self.assertEqual(ev[0]["evidence_type"], "target_absence_confirmed")
        self.assertIn("file missing", ev[0]["detail"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
